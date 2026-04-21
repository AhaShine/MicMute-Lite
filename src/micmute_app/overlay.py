from __future__ import annotations

import ctypes
import tkinter as tk
from ctypes import wintypes
from dataclasses import dataclass
from typing import Callable

from PIL import Image, ImageDraw, ImageFilter, ImageTk

from .assets import load_overlay_icon
from .config import AppConfig


user32 = ctypes.windll.user32
LONG_PTR = ctypes.c_longlong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_long

GWL_EXSTYLE = -20
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_SHOWWINDOW = 0x0040
WS_EX_TOOLWINDOW = 0x00000080
MONITORINFOF_PRIMARY = 0x00000001

TRANSPARENT_COLOR = "#010101"
BASE_SIZE = 112
MIN_SCALE = 0.6
MAX_SCALE = 2.2
RESIZE_ZONE = 24


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


class MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", RECT),
        ("rcWork", RECT),
        ("dwFlags", wintypes.DWORD),
    ]


MonitorEnumProc = ctypes.WINFUNCTYPE(ctypes.c_int, wintypes.HANDLE, wintypes.HDC, ctypes.POINTER(RECT), wintypes.LPARAM)

user32.EnumDisplayMonitors.argtypes = [wintypes.HDC, ctypes.POINTER(RECT), MonitorEnumProc, wintypes.LPARAM]
user32.EnumDisplayMonitors.restype = wintypes.BOOL
user32.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MONITORINFO)]
user32.GetMonitorInfoW.restype = wintypes.BOOL
user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetWindowLongPtrW.restype = LONG_PTR
user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, LONG_PTR]
user32.SetWindowLongPtrW.restype = LONG_PTR
user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
user32.SetWindowPos.restype = wintypes.BOOL


@dataclass(frozen=True)
class MonitorBounds:
    left: int
    top: int
    width: int
    height: int
    primary: bool


def list_monitors() -> list[MonitorBounds]:
    monitors: list[MonitorBounds] = []

    @MonitorEnumProc
    def _callback(handle, _hdc, _rect, _lparam):
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        user32.GetMonitorInfoW(handle, ctypes.byref(info))
        monitors.append(
            MonitorBounds(
                left=info.rcMonitor.left,
                top=info.rcMonitor.top,
                width=info.rcMonitor.right - info.rcMonitor.left,
                height=info.rcMonitor.bottom - info.rcMonitor.top,
                primary=bool(info.dwFlags & MONITORINFOF_PRIMARY),
            )
        )
        return 1

    user32.EnumDisplayMonitors(None, None, _callback, 0)
    monitors.sort(key=lambda item: (not item.primary, item.left, item.top))
    return monitors or [MonitorBounds(0, 0, 1920, 1080, True)]


def get_target_monitor() -> MonitorBounds:
    monitors = list_monitors()
    for monitor in monitors:
        if monitor.primary:
            return monitor
    return monitors[0]


def _apply_overlay_window_style(hwnd: int) -> None:
    styles = user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
    styles |= WS_EX_TOOLWINDOW
    user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, LONG_PTR(styles))


def _set_topmost(hwnd: int, enabled: bool) -> None:
    user32.SetWindowPos(
        hwnd,
        HWND_TOPMOST if enabled else HWND_NOTOPMOST,
        0,
        0,
        0,
        0,
        SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW,
    )


class OverlayManager:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.window = tk.Toplevel(root)
        self.window.withdraw()
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        self.window.configure(bg=TRANSPARENT_COLOR)
        try:
            self.window.wm_attributes("-transparentcolor", TRANSPARENT_COLOR)
        except tk.TclError:
            pass
        self.window.geometry("1x1+0+0")

        self.canvas = tk.Canvas(
            self.window,
            bg=TRANSPARENT_COLOR,
            highlightthickness=0,
            bd=0,
            relief="flat",
            cursor="",
        )
        self.canvas.pack(fill="both", expand=True)
        self._image_id = self.canvas.create_image(0, 0, anchor="nw")

        self._image_ref: ImageTk.PhotoImage | None = None
        self._dark_theme = True
        self._last_muted = True
        self._screen = get_target_monitor()
        self._visible = False
        self._editing = False
        self._action: str | None = None
        self._current_scale = 1.0
        self._current_size = self._size_from_scale(1.0)
        self._current_x = 0.5
        self._current_y = 0.14
        self._start_pointer_x = 0
        self._start_pointer_y = 0
        self._start_left = 0
        self._start_top = 0
        self._start_size = self._current_size
        self._edit_callback: Callable[[float, float, float, bool], None] | None = None

        for widget in (self.window, self.canvas):
            widget.bind("<ButtonPress-1>", self._on_button_press)
            widget.bind("<B1-Motion>", self._on_drag_motion)
            widget.bind("<ButtonRelease-1>", self._on_button_release)
            widget.bind("<Motion>", self._on_hover)

        self.window.update_idletasks()
        _apply_overlay_window_style(self.window.winfo_id())

    def update(self, config: AppConfig, is_muted: bool, mic_name: str) -> None:
        del mic_name
        self._last_muted = is_muted
        self._screen = get_target_monitor()
        if not self._editing:
            self._current_scale = max(MIN_SCALE, min(MAX_SCALE, config.overlay_scale))
            self._current_size = self._size_from_scale(self._current_scale)
            self._current_x = config.overlay_position_x
            self._current_y = config.overlay_position_y

        self._apply_visuals(config.dark_theme, is_muted)
        self._move_to_normalized(self._current_x, self._current_y)

        if config.overlay_enabled or self._editing:
            self.show()
        else:
            self.hide()

    def begin_edit(
        self,
        config: AppConfig,
        is_muted: bool,
        callback: Callable[[float, float, float, bool], None],
    ) -> None:
        self._editing = True
        self._edit_callback = callback
        self._current_scale = max(MIN_SCALE, min(MAX_SCALE, config.overlay_scale))
        self._current_size = self._size_from_scale(self._current_scale)
        self._current_x = config.overlay_position_x
        self._current_y = config.overlay_position_y
        self.update(config, is_muted, "")
        self._set_cursor("fleur")
        self.show()

    def finish_edit(self, commit: bool = True) -> None:
        callback = self._edit_callback
        current_x = self._current_x
        current_y = self._current_y
        current_scale = self._current_scale
        self._editing = False
        self._action = None
        self._edit_callback = None
        self._set_cursor("")
        if commit and callback is not None:
            callback(current_x, current_y, current_scale, True)

    def pulse(self) -> None:
        if not self._visible:
            return
        self.window.attributes("-topmost", True)
        _set_topmost(self.window.winfo_id(), True)

    def show(self) -> None:
        self._visible = True
        self.window.deiconify()
        self.window.lift()
        self.pulse()

    def hide(self) -> None:
        self._visible = False
        self.window.withdraw()

    def destroy(self) -> None:
        self.window.destroy()

    def _size_from_scale(self, scale: float) -> int:
        return max(76, int(BASE_SIZE * max(MIN_SCALE, min(MAX_SCALE, scale))))

    def _scale_from_size(self, size: int) -> float:
        return max(MIN_SCALE, min(MAX_SCALE, size / BASE_SIZE))

    def _render_image(self, dark_theme: bool, is_muted: bool) -> Image.Image:
        size = self._current_size
        border_width = max(3, int(size * 0.035))
        inset = max(3, border_width // 2 + 2)
        radius = max(18, int(size * 0.24))
        fill = (12, 14, 18, 255) if dark_theme else (244, 247, 251, 255)
        inner = (255, 255, 255, 18) if dark_theme else (255, 255, 255, 30)
        border = (217, 77, 87, 255) if is_muted else (43, 182, 115, 255)
        handle = (145, 154, 166, 255) if dark_theme else (112, 123, 136, 255)

        image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle(
            (inset, inset, size - inset - 1, size - inset - 1),
            radius=radius,
            fill=fill,
            outline=border,
            width=border_width,
        )

        inner_inset = inset + border_width + 2
        if inner_inset * 2 < size:
            draw.rounded_rectangle(
                (inner_inset, inner_inset, size - inner_inset - 1, size - inner_inset - 1),
                radius=max(0, radius - border_width - 2),
                outline=inner,
                width=1,
            )

        icon_size = min(88, max(48, int(size * 0.54)))
        icon = load_overlay_icon(is_muted, icon_size).filter(ImageFilter.UnsharpMask(radius=1.1, percent=170, threshold=2))
        icon_x = (size - icon.width) // 2
        icon_y = (size - icon.height) // 2 - max(0, size // 34)
        image.alpha_composite(icon, (icon_x, icon_y))

        if self._editing:
            grip = max(10, int(size * 0.13))
            gap = max(4, grip // 3)
            right = size - inset - 10
            bottom = size - inset - 10
            for offset in range(3):
                start_x = right - grip + offset * gap
                start_y = bottom
                end_x = right
                end_y = bottom - grip + offset * gap
                draw.line((start_x, start_y, end_x, end_y), fill=handle, width=2)

        return image

    def _apply_visuals(self, dark_theme: bool, is_muted: bool) -> None:
        self._dark_theme = dark_theme
        image = self._render_image(dark_theme, is_muted)
        self._image_ref = ImageTk.PhotoImage(image)
        self.window.geometry(f"{self._current_size}x{self._current_size}")
        self.window.configure(bg=TRANSPARENT_COLOR)
        self.window.attributes("-alpha", 0.87 if dark_theme else 0.95)
        self.canvas.configure(width=self._current_size, height=self._current_size, bg=TRANSPARENT_COLOR)
        self.canvas.coords(self._image_id, 0, 0)
        self.canvas.itemconfigure(self._image_id, image=self._image_ref)

    def _set_cursor(self, cursor: str) -> None:
        self.window.configure(cursor=cursor)
        self.canvas.configure(cursor=cursor)

    def _hit_mode(self, x_root: int, y_root: int) -> str:
        local_x = x_root - self.window.winfo_x()
        local_y = y_root - self.window.winfo_y()
        if local_x >= self._current_size - RESIZE_ZONE and local_y >= self._current_size - RESIZE_ZONE:
            return "resize"
        return "move"

    def _move_to_normalized(self, normalized_x: float, normalized_y: float) -> None:
        x_range = max(0, self._screen.width - self._current_size)
        y_range = max(0, self._screen.height - self._current_size)
        x = self._screen.left + int(x_range * max(0.0, min(1.0, normalized_x)))
        y = self._screen.top + int(y_range * max(0.0, min(1.0, normalized_y)))
        self.window.geometry(f"{self._current_size}x{self._current_size}+{x}+{y}")

    def _normalized_from_absolute(self, left: int, top: int) -> tuple[float, float]:
        x_range = max(1, self._screen.width - self._current_size)
        y_range = max(1, self._screen.height - self._current_size)
        clamped_left = max(self._screen.left, min(self._screen.left + self._screen.width - self._current_size, left))
        clamped_top = max(self._screen.top, min(self._screen.top + self._screen.height - self._current_size, top))
        return (
            (clamped_left - self._screen.left) / x_range,
            (clamped_top - self._screen.top) / y_range,
        )

    def _emit_edit_change(self, is_final: bool) -> None:
        if self._edit_callback is not None:
            self._edit_callback(self._current_x, self._current_y, self._current_scale, is_final)

    def _on_hover(self, event: tk.Event) -> None:
        if not self._editing or self._action is not None:
            return
        mode = self._hit_mode(event.x_root, event.y_root)
        self._set_cursor("size_nw_se" if mode == "resize" else "fleur")

    def _on_button_press(self, event: tk.Event) -> None:
        if not self._editing:
            return
        self._action = self._hit_mode(event.x_root, event.y_root)
        self._start_pointer_x = event.x_root
        self._start_pointer_y = event.y_root
        self._start_left = self.window.winfo_x()
        self._start_top = self.window.winfo_y()
        self._start_size = self._current_size
        self._set_cursor("size_nw_se" if self._action == "resize" else "fleur")

    def _on_drag_motion(self, event: tk.Event) -> None:
        if not self._editing or self._action is None:
            return

        if self._action == "move":
            left = event.x_root - (self._start_pointer_x - self._start_left)
            top = event.y_root - (self._start_pointer_y - self._start_top)
            self._current_x, self._current_y = self._normalized_from_absolute(left, top)
            self._move_to_normalized(self._current_x, self._current_y)
            self._emit_edit_change(False)
            return

        dx = event.x_root - self._start_pointer_x
        dy = event.y_root - self._start_pointer_y
        delta = dx if abs(dx) >= abs(dy) else dy
        size = max(self._size_from_scale(MIN_SCALE), min(self._size_from_scale(MAX_SCALE), self._start_size + delta))
        self._current_size = size
        self._current_scale = self._scale_from_size(size)
        self._apply_visuals(self._dark_theme, self._last_muted)
        self._current_x, self._current_y = self._normalized_from_absolute(self.window.winfo_x(), self.window.winfo_y())
        self._move_to_normalized(self._current_x, self._current_y)
        self._emit_edit_change(False)

    def _on_button_release(self, event: tk.Event) -> None:
        if not self._editing or self._action is None:
            return
        self._action = None
        self._on_hover(event)
        self._emit_edit_change(True)
