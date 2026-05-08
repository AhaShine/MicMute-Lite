from __future__ import annotations

import ctypes
import queue
import tkinter as tk
import time
from ctypes import wintypes
from tkinter import font as tkfont
from tkinter import ttk

from PIL import Image, ImageDraw, ImageTk

from . import APP_NAME
from .assets import load_app_icon, load_overlay_icon
from .audio import MicrophoneInfo, MicrophoneService, MicrophoneState, SoundService
from .config import ConfigStore, set_autostart
from .guardian import start_guardian
from .hooks import GlobalHookManager
from .hotkeys import HotkeySpec
from .ipc import SingleInstanceBridge
from .overlay import OverlayManager
from .tray import TrayController
from .wincompat import enable_dpi_awareness


LRESULT = ctypes.c_longlong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_long
LONG_PTR = ctypes.c_longlong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_long


try:
    dwmapi = ctypes.windll.dwmapi
except OSError:
    dwmapi = None
else:
    dwmapi.DwmSetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
    dwmapi.DwmSetWindowAttribute.restype = ctypes.c_long


try:
    uxtheme = ctypes.WinDLL("uxtheme")
    AllowDarkModeForWindow = uxtheme[133]
    AllowDarkModeForWindow.argtypes = [wintypes.HWND, wintypes.BOOL]
    AllowDarkModeForWindow.restype = wintypes.BOOL
    SetPreferredAppMode = uxtheme[135]
    SetPreferredAppMode.argtypes = [ctypes.c_int]
    SetPreferredAppMode.restype = ctypes.c_int
    FlushMenuThemes = uxtheme[136]
    FlushMenuThemes.argtypes = []
    FlushMenuThemes.restype = None
except (OSError, AttributeError, TypeError):
    AllowDarkModeForWindow = None
    SetPreferredAppMode = None
    FlushMenuThemes = None


DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_USE_IMMERSIVE_DARK_MODE_OLD = 19
DWMWA_BORDER_COLOR = 34
DWMWA_CAPTION_COLOR = 35
DWMWA_TEXT_COLOR = 36
GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000
WM_SETREDRAW = 0x000B
RDW_INVALIDATE = 0x0001
RDW_UPDATENOW = 0x0100
RDW_ALLCHILDREN = 0x0080
RDW_FRAME = 0x0400
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020
GA_ROOT = 2
SW_RESTORE = 9
HWND_TOPMOST = wintypes.HWND(-1)
HWND_NOTOPMOST = wintypes.HWND(-2)

user32 = ctypes.windll.user32
user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.SendMessageW.restype = LRESULT
user32.RedrawWindow.argtypes = [wintypes.HWND, ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT]
user32.RedrawWindow.restype = wintypes.BOOL
user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetWindowLongPtrW.restype = LONG_PTR
user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, LONG_PTR]
user32.SetWindowLongPtrW.restype = LONG_PTR
user32.GetParent.argtypes = [wintypes.HWND]
user32.GetParent.restype = wintypes.HWND
user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
user32.GetAncestor.restype = wintypes.HWND
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.ShowWindow.restype = wintypes.BOOL
user32.BringWindowToTop.argtypes = [wintypes.HWND]
user32.BringWindowToTop.restype = wintypes.BOOL
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.restype = wintypes.BOOL
user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
user32.SetWindowPos.restype = wintypes.BOOL

MODE_ORDER = ("toggle", "push_to_talk", "push_to_mute")

TEXTS = {
    "ru": {
        "mode_toggle": "Toggle",
        "mode_push_to_talk": "Push-to-talk",
        "mode_push_to_mute": "Push-to-mute",
        "unassigned": "Не назначено",
        "capture": "Нажми клавишу или кнопку мыши...",
        "mic": "Микрофон",
        "refresh": "Обновить",
        "mode": "Режим",
        "bind": "Бинд",
        "assign": "Назначить",
        "clear": "Очистить",
        "toggle_now": "Переключить",
        "sounds_enabled": "Звуки on/off",
        "autostart": "Автозапуск",
        "general": "Общее",
        "overlay": "Overlay",
        "show_overlay": "Показывать overlay",
        "edit_overlay": "Изменить",
        "edit_overlay_active": "Готово",
        "default_device": "По умолчанию: {name}",
        "status_on": "Микрофон включен",
        "status_off": "Микрофон выключен",
        "status_unavailable": "Микрофон недоступен",
        "status_pick_other": "Выбери другое устройство",
        "tray_settings": "Настройки",
        "tray_exit": "Выход",
        "tray_mic_label": "Микрофон",
        "tray_state_on": "включен",
        "tray_state_off": "выключен",
        "tray_state_unavailable": "недоступен",
        "tray_toggle_on": "Выключить микрофон",
        "tray_toggle_off": "Включить микрофон",
        "tray_toggle_unavailable": "Микрофон недоступен",
    },
    "en": {
        "mode_toggle": "Toggle",
        "mode_push_to_talk": "Push-to-talk",
        "mode_push_to_mute": "Push-to-mute",
        "unassigned": "Unassigned",
        "capture": "Press a key or a mouse button...",
        "mic": "Microphone",
        "refresh": "Refresh",
        "mode": "Mode",
        "bind": "Bind",
        "assign": "Assign",
        "clear": "Clear",
        "toggle_now": "Toggle",
        "sounds_enabled": "On/off sounds",
        "autostart": "Autostart",
        "general": "General",
        "overlay": "Overlay",
        "show_overlay": "Show overlay",
        "edit_overlay": "Edit",
        "edit_overlay_active": "Done",
        "default_device": "Default: {name}",
        "status_on": "Microphone is on",
        "status_off": "Microphone is off",
        "status_unavailable": "Microphone unavailable",
        "status_pick_other": "Pick another device",
        "tray_settings": "Settings",
        "tray_exit": "Exit",
        "tray_mic_label": "Microphone",
        "tray_state_on": "on",
        "tray_state_off": "off",
        "tray_state_unavailable": "unavailable",
        "tray_toggle_on": "Mute microphone",
        "tray_toggle_off": "Unmute microphone",
        "tray_toggle_unavailable": "Microphone unavailable",
    },
}

PALETTES = {
    "dark": {
        "window_bg": "#080808",
        "surface_bg": "#111111",
        "surface_raised": "#151515",
        "input_bg": "#0B0B0B",
        "border": "#2B2B2B",
        "border_hot": "#464646",
        "text": "#F2F2F2",
        "muted": "#A8A8A8",
        "button_bg": "#181818",
        "button_hover": "#262626",
        "accent_on": "#24D17E",
        "accent_off": "#F0445E",
        "warn": "#F4B860",
    },
}


def _hex_to_colorref(hex_color: str) -> int:
    value = hex_color.lstrip("#")
    red = int(value[0:2], 16)
    green = int(value[2:4], 16)
    blue = int(value[4:6], 16)
    return red | (green << 8) | (blue << 16)


def _enable_dark_app_mode() -> None:
    if SetPreferredAppMode is None or FlushMenuThemes is None:
        return
    try:
        SetPreferredAppMode(2)
        FlushMenuThemes()
    except (OSError, ValueError):
        pass


def _window_handles(window: tk.Toplevel) -> list[int]:
    handles: list[int] = []
    try:
        base = int(window.winfo_id())
    except tk.TclError:
        return handles

    for handle in (
        base,
        int(user32.GetParent(wintypes.HWND(base)) or 0),
        int(user32.GetAncestor(wintypes.HWND(base), GA_ROOT) or 0),
    ):
        if handle and handle not in handles:
            handles.append(handle)
    return handles


def _apply_window_titlebar_theme(window: tk.Toplevel, dark: bool, palette: dict[str, str] | None = None) -> None:
    if dwmapi is None:
        return
    try:
        window.update_idletasks()
        value = ctypes.c_int(1 if dark else 0)
        for handle in _window_handles(window):
            hwnd = wintypes.HWND(handle)
            if AllowDarkModeForWindow is not None:
                AllowDarkModeForWindow(hwnd, wintypes.BOOL(1 if dark else 0))
            for attribute in (DWMWA_USE_IMMERSIVE_DARK_MODE, DWMWA_USE_IMMERSIVE_DARK_MODE_OLD):
                dwmapi.DwmSetWindowAttribute(hwnd, attribute, ctypes.byref(value), ctypes.sizeof(value))
            if palette is not None:
                caption = wintypes.DWORD(_hex_to_colorref(palette["window_bg"]))
                border = wintypes.DWORD(_hex_to_colorref(palette["border"]))
                text = wintypes.DWORD(_hex_to_colorref("#FFFFFF" if dark else "#16202A"))
                dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_CAPTION_COLOR, ctypes.byref(caption), ctypes.sizeof(caption))
                dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_BORDER_COLOR, ctypes.byref(border), ctypes.sizeof(border))
                dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_TEXT_COLOR, ctypes.byref(text), ctypes.sizeof(text))
            user32.SetWindowPos(
                hwnd,
                wintypes.HWND(0),
                0,
                0,
                0,
                0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED,
            )
    except (tk.TclError, OSError, ValueError):
        pass


def _apply_appwindow_style(window: tk.Toplevel) -> None:
    try:
        window.update_idletasks()
        hwnd = wintypes.HWND(window.winfo_id())
        style = int(user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE))
        style &= ~WS_EX_TOOLWINDOW
        style |= WS_EX_APPWINDOW
        user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, LONG_PTR(style))
        user32.SetWindowPos(
            hwnd,
            wintypes.HWND(0),
            0,
            0,
            0,
            0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED,
        )
    except tk.TclError:
        pass


class DarkSelect(tk.Canvas):
    def __init__(self, parent: tk.Widget, palette_provider, command=None, height: int = 30) -> None:
        super().__init__(parent, height=height, bd=0, highlightthickness=0, cursor="hand2")
        self._palette_provider = palette_provider
        self._command = command
        self._height = height
        self._items: list[str] = []
        self._selected_index = -1
        self._dropdown: tk.Toplevel | None = None
        self._hover = False
        self._suppress_owner_click_until = 0.0
        self._image_ref: ImageTk.PhotoImage | None = None
        self._font = tkfont.Font(family="Segoe UI", size=9)

        self.bind("<Configure>", lambda _event: self._draw())
        self.bind("<ButtonPress-1>", self._owner_click)
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)
        self.bind("<MouseWheel>", lambda _event: "break")
        self.apply_theme()

    def set_options(self, options: list[str], selected_index: int = 0, notify: bool = False) -> None:
        self._items = list(options)
        if not self._items:
            self._selected_index = -1
            self._draw()
            self.close_dropdown()
            return
        self.set_current(max(0, min(selected_index, len(self._items) - 1)), notify=notify)

    def current(self) -> int:
        return self._selected_index

    def set_current(self, index: int, notify: bool = False) -> None:
        if index < 0 or index >= len(self._items):
            return
        changed = index != self._selected_index
        self._selected_index = index
        self._draw()
        if notify and changed and self._command is not None:
            self._command()

    def apply_theme(self) -> None:
        colors = self._palette_provider()
        self.configure(bg=self._parent_bg(), height=self._height)
        self._draw()

    def _owner_click(self, _event) -> str:
        if time.monotonic() < self._suppress_owner_click_until:
            self._suppress_owner_click_until = 0.0
            return "break"
        self.toggle_dropdown()
        return "break"

    def toggle_dropdown(self) -> None:
        if self._dropdown is not None and self._dropdown.winfo_exists():
            self.close_dropdown()
        else:
            self.open_dropdown()

    def open_dropdown(self) -> None:
        if not self._items:
            return
        self.close_dropdown()
        colors = self._palette_provider()
        dropdown = tk.Toplevel(self)
        dropdown.overrideredirect(True)
        dropdown.attributes("-topmost", True)
        dropdown.configure(bg=colors["border"])
        self._dropdown = dropdown

        width = max(self.winfo_width(), 160)
        item_height = 26
        visible_count = min(len(self._items), 8)
        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height() + 2
        dropdown.geometry(f"{width}x{visible_count * item_height + 2}+{x}+{y}")

        box = tk.Frame(dropdown, bg=colors["surface_raised"])
        box.pack(fill="both", expand=True, padx=1, pady=1)
        for index, value in enumerate(self._items[:visible_count]):
            bg = colors["button_hover"] if index == self._selected_index else colors["surface_raised"]
            item = tk.Label(box, text=value, anchor="w", padx=9, bg=bg, fg=colors["text"], font=("Segoe UI", 9))
            item.pack(fill="x", ipady=4)
            item.bind("<Button-1>", lambda _event, item_index=index: self._pick(item_index))
            item.bind("<Enter>", lambda _event, widget=item: widget.configure(bg=colors["button_hover"]))
            item.bind("<Leave>", lambda _event, widget=item, item_index=index: widget.configure(bg=colors["button_hover"] if item_index == self._selected_index else colors["surface_raised"]))

        dropdown.bind("<FocusOut>", lambda _event: self.close_dropdown(suppress_owner_click=True))
        dropdown.after(10, dropdown.focus_force)

    def close_dropdown(self, suppress_owner_click: bool = False) -> None:
        if suppress_owner_click:
            self._suppress_owner_click_until = time.monotonic() + 0.25
        if self._dropdown is not None and self._dropdown.winfo_exists():
            self._dropdown.destroy()
        self._dropdown = None

    def _pick(self, index: int) -> None:
        self.set_current(index, notify=True)
        self.close_dropdown()

    def _enter(self, _event) -> None:
        self._hover = True
        self._draw()

    def _leave(self, _event) -> None:
        self._hover = False
        self._draw()

    def _parent_bg(self) -> str:
        try:
            return self.master.cget("bg")
        except tk.TclError:
            return "#0B0B0B"

    def _trim_text(self, text: str, max_width: int) -> str:
        if self._font.measure(text) <= max_width:
            return text
        ellipsis = "..."
        available = max(0, max_width - self._font.measure(ellipsis))
        trimmed = text
        while trimmed and self._font.measure(trimmed) > available:
            trimmed = trimmed[:-1]
        return trimmed.rstrip() + ellipsis

    def _draw(self) -> None:
        colors = self._palette_provider()
        width = max(2, self.winfo_width())
        height = self._height
        border = colors["border_hot"] if self._hover or (self._dropdown is not None and self._dropdown.winfo_exists()) else colors["border"]
        self._image_ref = _rounded_photo(width, height, 8, colors["input_bg"], border, self._parent_bg())
        self.delete("all")
        self.create_image(0, 0, anchor="nw", image=self._image_ref)
        arrow_x = width - 27
        self.create_line(arrow_x, 5, arrow_x, height - 5, fill=colors["border"])
        self.create_polygon(
            arrow_x + 9,
            height // 2 - 2,
            arrow_x + 16,
            height // 2 - 2,
            arrow_x + 12,
            height // 2 + 3,
            fill=colors["muted"],
            outline="",
        )
        text = self._items[self._selected_index] if 0 <= self._selected_index < len(self._items) else ""
        self.create_text(10, height // 2, text=self._trim_text(text, max(20, width - 45)), fill=colors["text"], font=self._font, anchor="w")


def _rounded_points(x1: int, y1: int, x2: int, y2: int, radius: int) -> list[int]:
    radius = max(1, min(radius, (x2 - x1) // 2, (y2 - y1) // 2))
    return [
        x1 + radius,
        y1,
        x2 - radius,
        y1,
        x2,
        y1,
        x2,
        y1 + radius,
        x2,
        y2 - radius,
        x2,
        y2,
        x2 - radius,
        y2,
        x1 + radius,
        y2,
        x1,
        y2,
        x1,
        y2 - radius,
        x1,
        y1 + radius,
        x1,
        y1,
    ]


def _rounded_photo(width: int, height: int, radius: int, fill: str, outline: str, outer_bg: str, border_width: int = 1) -> ImageTk.PhotoImage:
    scale = 3
    width = max(2, int(width))
    height = max(2, int(height))
    image = Image.new("RGB", (width * scale, height * scale), outer_bg)
    draw = ImageDraw.Draw(image)
    rect = (0, 0, width * scale - 1, height * scale - 1)
    draw.rounded_rectangle(
        rect,
        radius=max(1, radius * scale),
        fill=fill,
        outline=outline,
        width=max(1, border_width * scale),
    )
    image = image.resize((width, height), Image.Resampling.LANCZOS)
    return ImageTk.PhotoImage(image)


class RoundedPanel(tk.Canvas):
    def __init__(self, parent: tk.Widget, palette_provider, height: int, fill_key: str = "surface_bg", radius: int = 12, padding: int = 12) -> None:
        super().__init__(parent, height=height, bd=0, highlightthickness=0)
        self._palette_provider = palette_provider
        self._height = height
        self._fill_key = fill_key
        self._radius = radius
        self._padding = padding
        self._image_ref: ImageTk.PhotoImage | None = None
        colors = self._palette_provider()
        self.inner = tk.Frame(self, bg=colors[fill_key])
        self._inner_window = self.create_window(padding, padding, anchor="nw", window=self.inner)
        self.bind("<Configure>", lambda _event: self._draw())
        self.apply_theme()

    def apply_theme(self) -> None:
        colors = self._palette_provider()
        self.configure(bg=colors["window_bg"], height=self._height)
        self.inner.configure(bg=colors[self._fill_key])
        self._draw()

    def _parent_bg(self) -> str:
        try:
            return self.master.cget("bg")
        except tk.TclError:
            return "#0B0B0B"

    def _draw(self) -> None:
        colors = self._palette_provider()
        width = max(2, self.winfo_width())
        height = max(2, self._height)
        self.delete("panel")
        self._image_ref = _rounded_photo(width, height, self._radius, colors[self._fill_key], colors["border"], self._parent_bg())
        self.create_image(0, 0, anchor="nw", image=self._image_ref, tags="panel")
        inner_width = max(10, width - self._padding * 2)
        inner_height = max(10, height - self._padding * 2)
        self.itemconfigure(self._inner_window, width=inner_width, height=inner_height)


class RoundButton(tk.Canvas):
    def __init__(
        self,
        parent: tk.Widget,
        text: str,
        command,
        colors: dict[str, str],
        width_chars: int | None = None,
        height: int = 34,
        width_px: int | None = None,
        font: tuple[str, int] | tuple[str, int, str] = ("Segoe UI", 9),
        align: str = "center",
    ) -> None:
        width = width_px if width_px is not None else (86 if width_chars is None else max(42, width_chars * 8 + 24))
        super().__init__(parent, width=width, height=height, bd=0, highlightthickness=0, cursor="hand2")
        self._command = command
        self._text = text
        self._width = width
        self._height = height
        self._radius = 9
        self._align = align
        self._font = tkfont.Font(family=font[0], size=font[1], weight=font[2] if len(font) > 2 else "normal")
        self._image_ref: ImageTk.PhotoImage | None = None
        self._fill = colors["button_bg"]
        self._hover = colors["button_hover"]
        self._pressed = "#303030"
        self._fg = colors["text"]
        self._border = colors["border"]
        self._over = False
        self._down = False
        self._state = "normal"
        super().configure(bg=self._parent_bg())
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)
        self.bind("<ButtonPress-1>", self._press)
        self.bind("<ButtonRelease-1>", self._release)
        self._draw()

    def configure(self, cnf=None, **kwargs):
        if cnf:
            kwargs.update(cnf)
        if not kwargs:
            return super().configure()

        if "text" in kwargs:
            self._text = kwargs.pop("text")
        if "command" in kwargs:
            self._command = kwargs.pop("command")
        if "bg" in kwargs:
            self._fill = kwargs.pop("bg")
        if "fg" in kwargs:
            self._fg = kwargs.pop("fg")
        if "activebackground" in kwargs:
            self._hover = kwargs.pop("activebackground")
        if "highlightbackground" in kwargs:
            self._border = kwargs.pop("highlightbackground")
        if "state" in kwargs:
            self._state = kwargs.pop("state")
        kwargs.pop("activeforeground", None)
        kwargs.pop("highlightcolor", None)
        kwargs.pop("disabledforeground", None)
        kwargs.pop("relief", None)
        kwargs.pop("borderwidth", None)
        if kwargs:
            super().configure(**kwargs)
        self._draw()

    config = configure

    def apply_theme(self, colors: dict[str, str]) -> None:
        self.configure(bg=colors["button_bg"], fg=colors["text"], activebackground=colors["button_hover"], highlightbackground=colors["border"])

    def _parent_bg(self) -> str:
        try:
            return self.master.cget("bg")
        except tk.TclError:
            return "#080808"

    def _draw(self) -> None:
        super().configure(bg=self._parent_bg())
        self.delete("all")
        disabled = self._state == "disabled"
        fill = self._pressed if self._down else (self._hover if self._over else self._fill)
        self._image_ref = _rounded_photo(self._width, self._height, self._radius, fill, self._border, self._parent_bg())
        self.create_image(0, 0, anchor="nw", image=self._image_ref)
        fg = "#8D8D8D" if disabled else self._fg
        if self._align == "left":
            text = self._trim_text(self._text, max(20, self._width - 22))
            self.create_text(11, self._height // 2, text=text, fill=fg, font=self._font, anchor="w")
        else:
            self.create_text(self._width // 2, self._height // 2, text=self._text, fill=fg, font=self._font)

    def _trim_text(self, text: str, max_width: int) -> str:
        if self._font.measure(text) <= max_width:
            return text
        ellipsis = "..."
        available = max(0, max_width - self._font.measure(ellipsis))
        trimmed = text
        while trimmed and self._font.measure(trimmed) > available:
            trimmed = trimmed[:-1]
        return trimmed.rstrip() + ellipsis

    def _enter(self, _event) -> None:
        self._over = True
        self._draw()

    def _leave(self, _event) -> None:
        self._over = False
        self._down = False
        self._draw()

    def _press(self, _event) -> None:
        if self._state == "disabled":
            return
        self._down = True
        self._draw()

    def _release(self, event) -> None:
        if self._state == "disabled":
            return
        was_down = self._down
        self._down = False
        self._draw()
        if was_down and 0 <= event.x <= self._width and 0 <= event.y <= self._height and self._command is not None:
            self._command()


class MicMuteApp:
    def __init__(self, start_hidden: bool = False) -> None:
        self.should_exit_immediately = False
        self.command_queue: queue.Queue[tuple[str, object | None]] = queue.Queue()
        self.ipc = SingleInstanceBridge(lambda: self.command_queue.put(("show_settings", None)))
        if not self.ipc.start_or_signal_existing():
            self.should_exit_immediately = True
            return

        self.config_store = ConfigStore()
        self.first_run = not self.config_store.path.exists()
        self.config = self.config_store.load()
        self.config.suppress_hotkey = False
        if abs(self.config.overlay_position_x - 0.88) < 0.001 and abs(self.config.overlay_position_y - 0.1) < 0.001:
            self.config.overlay_position_x = 0.5
            self.config.overlay_position_y = 0.14
            self.config_store.save(self.config)

        self.audio = MicrophoneService()
        self.sounds = SoundService()
        self.hooks = GlobalHookManager(self._enqueue_hook_event)

        _enable_dark_app_mode()
        enable_dpi_awareness()

        self.hooks.start()
        self.root = tk.Tk()
        self.root.geometry("1x1+-32000+-32000")
        self.root.overrideredirect(True)
        self.root.title(APP_NAME)
        self._app_icon_small_ref: ImageTk.PhotoImage | None = None
        self._app_icon_large_ref: ImageTk.PhotoImage | None = None
        self._status_icon_ref: ImageTk.PhotoImage | None = None
        self._apply_app_icon(self.root)
        self.root.withdraw()

        self.settings_window: tk.Toplevel | None = None
        self.tray_menu: tk.Toplevel | None = None
        self._settings_ready = False
        self._overlay_edit_active = False
        self._tray_menu_hotkeys_paused = False
        self._tray_menu_resume_job: str | None = None
        self._localized_widgets: list[tuple[tk.Widget, str]] = []
        self._guardian_device_ids: set[str] = set()

        self.tray = TrayController(self.command_queue, self._text)
        self.overlay = OverlayManager(self.root)
        self.devices: list[MicrophoneInfo] = []
        self.hotkey_is_held = False
        self.current_state = MicrophoneState(id="", name="", is_muted=True, is_available=False, is_default=True)

        self.mic_var = tk.StringVar()
        self.mode_var = tk.StringVar(value=self._mode_label(self.config.mode))
        self.hotkey_var = tk.StringVar(value=self.config.hotkey.label if self.config.hotkey else self._text("unassigned"))
        self.status_var = tk.StringVar()
        self.substatus_var = tk.StringVar()
        self.sounds_var = tk.BooleanVar(value=self.config.sounds_enabled)
        self.autostart_var = tk.BooleanVar(value=self.config.autostart)
        self.overlay_var = tk.BooleanVar(value=self.config.overlay_enabled)
        self.overlay_x_var = tk.DoubleVar(value=self.config.overlay_position_x * 100)
        self.overlay_y_var = tk.DoubleVar(value=self.config.overlay_position_y * 100)
        self.overlay_scale_var = tk.DoubleVar(value=self.config.overlay_scale * 100)

        self.mic_combo: DarkSelect | None = None
        self.mode_combo: DarkSelect | None = None
        self.status_label: tk.Label | None = None
        self.substatus_label: tk.Label | None = None
        self.status_icon_label: tk.Label | None = None
        self.hotkey_button: RoundButton | None = None
        self.overlay_edit_button: RoundButton | None = None
        self.lang_ru_button: RoundButton | None = None
        self.lang_en_button: RoundButton | None = None

        self._load_microphones()
        self._ensure_guardian_if_muted()
        self._apply_runtime_state(enforce_idle_state=True, play_sound=False, refresh_state=False)
        self.tray.start(
            self.current_state.is_muted,
            self.config.overlay_enabled,
            self.current_state.name,
            self.current_state.is_available,
        )

        self._process_queue()
        self._poll_microphone_state()
        self._pulse_overlay()

        if not start_hidden:
            self.show_settings()

    def _text(self, key: str) -> str:
        language = self.config.language if self.config.language in TEXTS else "ru"
        return TEXTS[language].get(key, key)

    def _mode_label(self, mode: str) -> str:
        return self._text(f"mode_{mode}")

    def _mode_values(self) -> list[str]:
        return [self._mode_label(mode) for mode in MODE_ORDER]

    def _selected_mode(self) -> str:
        if self.mode_combo is not None:
            index = self.mode_combo.current()
            if 0 <= index < len(MODE_ORDER):
                return MODE_ORDER[index]
        current = self.mode_var.get()
        for mode in MODE_ORDER:
            if current == self._mode_label(mode):
                return mode
        return "toggle"

    def _palette(self) -> dict[str, str]:
        return PALETTES["dark"]

    def _tag(self, widget: tk.Widget, role: str) -> tk.Widget:
        setattr(widget, "_theme_role", role)
        return widget

    def _localize(self, widget: tk.Widget, key: str) -> tk.Widget:
        setattr(widget, "_text_key", key)
        self._localized_widgets.append((widget, key))
        widget.configure(text=self._text(key))
        return widget

    def _iter_widgets(self, widget: tk.Widget):
        yield widget
        for child in widget.winfo_children():
            yield from self._iter_widgets(child)

    def _setup_styles(self) -> None:
        colors = self._palette()
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(
            "MicMute.TCombobox",
            fieldbackground=colors["input_bg"],
            foreground=colors["text"],
            background=colors["input_bg"],
            bordercolor=colors["border"],
            lightcolor=colors["border"],
            darkcolor=colors["border"],
            arrowcolor=colors["text"],
            selectbackground=colors["button_hover"],
            selectforeground=colors["text"],
            padding=4,
        )
        style.map(
            "MicMute.TCombobox",
            fieldbackground=[("readonly", colors["input_bg"])],
            foreground=[("readonly", colors["text"])],
            selectbackground=[("readonly", colors["button_hover"])],
            selectforeground=[("readonly", colors["text"])],
            background=[("readonly", colors["input_bg"])],
            arrowcolor=[("readonly", colors["text"])],
        )

    def _update_language_buttons_state(self) -> None:
        selected = self.config.language
        if self.lang_ru_button is not None:
            self.lang_ru_button.configure(state="disabled" if selected == "ru" else "normal")
        if self.lang_en_button is not None:
            self.lang_en_button.configure(state="disabled" if selected == "en" else "normal")

    def _apply_theme(self) -> None:
        if self.settings_window is None or not self.settings_window.winfo_exists():
            return

        self._setup_styles()
        colors = self._palette()
        self.settings_window.configure(bg=colors["window_bg"])

        for widget in self._iter_widgets(self.settings_window):
            role = getattr(widget, "_theme_role", None)

            if isinstance(widget, RoundedPanel):
                widget.apply_theme()
                continue

            if isinstance(widget, RoundButton):
                widget.apply_theme(colors)
                continue

            if isinstance(widget, DarkSelect):
                widget.apply_theme()
                continue

            if role == "window_frame":
                widget.configure(bg=colors["window_bg"])
            elif role == "window_border":
                widget.configure(bg=colors["border"])
            elif role == "surface_frame":
                widget.configure(bg=colors["surface_bg"], highlightbackground=colors["border"])
            elif role == "raised_frame":
                widget.configure(bg=colors["surface_raised"], highlightbackground=colors["border"])
            elif role == "window_text":
                widget.configure(bg=colors["window_bg"], fg=colors["text"])
            elif role == "surface_text":
                widget.configure(bg=colors["surface_bg"], fg=colors["text"])
            elif role == "raised_text":
                widget.configure(bg=colors["surface_raised"], fg=colors["text"])
            elif role == "muted_window":
                widget.configure(bg=colors["window_bg"], fg=colors["muted"])
            elif role == "muted_surface":
                widget.configure(bg=colors["surface_bg"], fg=colors["muted"])
            elif role == "muted_raised":
                widget.configure(bg=colors["surface_raised"], fg=colors["muted"])
            elif role == "input_label":
                widget.configure(
                    bg=colors["input_bg"],
                    fg=colors["text"],
                    highlightbackground=colors["border"],
                    highlightcolor=colors["border"],
                )
            elif role == "button":
                widget.configure(
                    bg=colors["button_bg"],
                    fg=colors["text"],
                    activebackground=colors["button_hover"],
                    activeforeground=colors["text"],
                    highlightbackground=colors["border"],
                    highlightcolor=colors["border"],
                    disabledforeground=colors["muted"],
                )
            elif role == "check":
                widget.configure(
                    bg=colors["surface_bg"],
                    fg=colors["text"],
                    activebackground=colors["surface_bg"],
                    activeforeground=colors["text"],
                    selectcolor=colors["input_bg"],
                    disabledforeground=colors["muted"],
                )
            elif role == "surface_scale":
                widget.configure(
                    bg=colors["surface_bg"],
                    fg=colors["text"],
                    troughcolor=colors["border"],
                    activebackground=colors["button_hover"],
                    highlightthickness=0,
                    bd=0,
                )

        self._update_language_buttons_state()
        self._sync_overlay_edit_button_state()
        self._refresh_status_ui()
        self._refresh_titlebar_theme()

    def _button(
        self,
        parent: tk.Widget,
        text: str,
        command,
        width: int | None = None,
        *,
        pixel_width: int | None = None,
        height: int = 34,
        font: tuple[str, int] | tuple[str, int, str] = ("Segoe UI", 9),
        align: str = "center",
    ) -> RoundButton:
        colors = self._palette()
        button = RoundButton(parent, text, command, colors, width_chars=width, height=height, width_px=pixel_width, font=font, align=align)
        return self._tag(button, "button")

    def _checkbutton(self, parent: tk.Widget, text: str, variable: tk.BooleanVar, command) -> tk.Checkbutton:
        colors = self._palette()
        widget = tk.Checkbutton(
            parent,
            text=text,
            variable=variable,
            command=command,
            anchor="w",
            bg=colors["surface_bg"],
            fg=colors["text"],
            activebackground=colors["surface_bg"],
            activeforeground=colors["text"],
            selectcolor=colors["input_bg"],
            highlightthickness=0,
            borderwidth=0,
            font=("Segoe UI", 10),
            padx=0,
            pady=2,
            cursor="hand2",
        )
        return self._tag(widget, "check")

    def _apply_app_icon(self, window: tk.Misc) -> None:
        if self._app_icon_small_ref is None:
            self._app_icon_small_ref = ImageTk.PhotoImage(load_app_icon(16))
        if self._app_icon_large_ref is None:
            self._app_icon_large_ref = ImageTk.PhotoImage(load_app_icon(32))
        try:
            window.iconphoto(True, self._app_icon_large_ref, self._app_icon_small_ref)
        except tk.TclError:
            pass

    def _get_status_icon(self) -> ImageTk.PhotoImage:
        self._status_icon_ref = ImageTk.PhotoImage(load_overlay_icon(self.current_state.is_muted, 42))
        return self._status_icon_ref

    def _ensure_settings_window(self) -> None:
        self._setup_styles()

        if self.settings_window is None or not self.settings_window.winfo_exists():
            self.settings_window = tk.Toplevel(self.root)
            self.settings_window.title(APP_NAME)
            self.settings_window.geometry("430x448")
            self.settings_window.resizable(False, False)
            self.settings_window.protocol("WM_DELETE_WINDOW", self.hide_window)
            self.settings_window.bind("<Escape>", lambda _event: self.hide_window())
            self.settings_window.bind("<Alt-F4>", lambda _event: (self.hide_window(), "break")[1])
            self.settings_window.bind("<Map>", lambda _event: self._refresh_titlebar_theme())
            self._apply_app_icon(self.settings_window)
            _apply_appwindow_style(self.settings_window)
            self._refresh_titlebar_theme()
            self._settings_ready = False

        if self._settings_ready:
            self._apply_theme()
            self._sync_settings_ui()
            return

        colors = self._palette()
        window = self.settings_window
        window.configure(bg=colors["window_bg"])
        self._localized_widgets.clear()

        root_frame = self._tag(tk.Frame(window, bg=colors["window_bg"], highlightthickness=1, highlightbackground=colors["border"]), "window_frame")
        root_frame.pack(fill="both", expand=True)

        content = self._tag(tk.Frame(root_frame, bg=colors["window_bg"]), "window_frame")
        content.pack(fill="both", expand=True, padx=8, pady=10)

        header = self._tag(tk.Frame(content, bg=colors["window_bg"]), "window_frame")
        header.pack(fill="x", pady=(0, 10))

        self._tag(
            tk.Label(header, text="MicMute Lite", bg=colors["window_bg"], fg=colors["text"], font=("Segoe UI Semibold", 14)),
            "window_text",
        ).pack(side="left")

        lang_box = self._tag(tk.Frame(header, bg=colors["window_bg"]), "window_frame")
        lang_box.pack(side="right")
        self.lang_ru_button = self._button(lang_box, "RU", lambda: self._set_language("ru"), width=4)
        self.lang_ru_button.pack(side="left")
        self.lang_en_button = self._button(lang_box, "EN", lambda: self._set_language("en"), width=4)
        self.lang_en_button.pack(side="left", padx=(6, 0))

        status_card = RoundedPanel(content, self._palette, height=72, fill_key="surface_raised", radius=14, padding=10)
        status_card.pack(fill="x")
        status_box = status_card.inner

        status_box.grid_columnconfigure(0, weight=1)
        status_left = self._tag(tk.Frame(status_box, bg=colors["surface_raised"]), "raised_frame")
        status_left.grid(row=0, column=0, sticky="nsew")

        self.status_icon_label = self._tag(
            tk.Label(status_left, image=self._get_status_icon(), bg=colors["surface_raised"]),
            "raised_text",
        )
        self.status_icon_label.pack(side="left", padx=(0, 10))

        status_texts = self._tag(tk.Frame(status_left, bg=colors["surface_raised"]), "raised_frame")
        status_texts.pack(side="left", fill="both", expand=True)

        self.status_label = self._tag(
            tk.Label(status_texts, textvariable=self.status_var, bg=colors["surface_raised"], fg=colors["accent_off"], font=("Segoe UI Semibold", 11)),
            "raised_text",
        )
        self.status_label.pack(anchor="w", pady=(1, 2))

        self.substatus_label = self._tag(
            tk.Label(status_texts, textvariable=self.substatus_var, bg=colors["surface_raised"], fg=colors["muted"], font=("Segoe UI", 8)),
            "muted_raised",
        )
        self.substatus_label.pack(anchor="w")

        toggle_button = self._localize(self._button(status_box, "", self.toggle_microphone, pixel_width=108, height=32), "toggle_now")
        toggle_button.grid(row=0, column=1, sticky="e", padx=(8, 0), pady=8)

        form = self._tag(tk.Frame(content, bg=colors["window_bg"]), "window_frame")
        form.pack(fill="both", expand=True, pady=(8, 0))
        form.grid_columnconfigure(0, weight=1, uniform="columns")
        form.grid_columnconfigure(1, weight=1, uniform="columns")

        mic_card = self._card(form, 0, 0, 2, height=80)
        self._add_label(mic_card, "mic")
        mic_row = self._tag(tk.Frame(mic_card, bg=colors["surface_bg"]), "surface_frame")
        mic_row.pack(fill="x", pady=(6, 0))
        mic_row.grid_columnconfigure(0, weight=1)
        self.mic_combo = DarkSelect(mic_row, self._palette, command=self._on_microphone_selected)
        self.mic_combo.grid(row=0, column=0, sticky="ew")
        self._button(mic_row, "\uE72C", self._load_microphones, pixel_width=32, height=30, font=("Segoe MDL2 Assets", 9)).grid(row=0, column=1, padx=(6, 0))

        mode_card = self._card(form, 1, 0, 1, height=84)
        self._add_label(mode_card, "mode")
        self.mode_combo = DarkSelect(mode_card, self._palette, command=self._on_mode_changed)
        self.mode_combo.pack(fill="x", pady=(6, 0))

        bind_card = self._card(form, 1, 1, 1, height=84)
        self._add_label(bind_card, "bind")
        hotkey_row = self._tag(tk.Frame(bind_card, bg=colors["surface_bg"]), "surface_frame")
        hotkey_row.pack(fill="x", pady=(6, 0))
        hotkey_row.grid_columnconfigure(0, weight=1)

        self.hotkey_button = self._button(
            hotkey_row,
            self.hotkey_var.get(),
            self._start_hotkey_capture,
            pixel_width=126,
            height=30,
            font=("Consolas", 10),
            align="left",
        )
        self.hotkey_button.grid(row=0, column=0, sticky="w")
        self._button(hotkey_row, "\uE711", self._clear_hotkey, pixel_width=34, height=30, font=("Segoe MDL2 Assets", 9)).grid(row=0, column=1, padx=(6, 0))

        general_card = self._card(form, 2, 0, 1, height=110)
        self._add_label(general_card, "general")
        self._localize(self._checkbutton(general_card, "", self.autostart_var, self._on_autostart_changed), "autostart").pack(anchor="w", pady=(8, 2))
        self._localize(self._checkbutton(general_card, "", self.sounds_var, self._save_general_settings), "sounds_enabled").pack(anchor="w", pady=(2, 0))

        overlay_box = self._card(form, 2, 1, 1, height=110)
        self._add_label(overlay_box, "overlay")
        self._localize(self._checkbutton(overlay_box, "", self.overlay_var, self._save_visual_settings), "show_overlay").pack(anchor="w", pady=(8, 4))
        self.overlay_edit_button = self._localize(self._button(overlay_box, "", self._toggle_overlay_edit, pixel_width=86, height=30), "edit_overlay")
        self.overlay_edit_button.pack(anchor="w", pady=(2, 0))

        self._settings_ready = True
        self._apply_theme()
        self._sync_settings_ui()

    def _refresh_titlebar_theme(self) -> None:
        if self.settings_window is None or not self.settings_window.winfo_exists():
            return
        _apply_window_titlebar_theme(self.settings_window, True, self._palette())
        for delay in (50, 160, 320):
            self.settings_window.after(
                delay,
                lambda: _apply_window_titlebar_theme(self.settings_window, True, self._palette())
                if self.settings_window and self.settings_window.winfo_exists()
                else None,
            )

    def _card(self, parent: tk.Widget, row: int, column: int, columnspan: int, height: int) -> tk.Frame:
        card = RoundedPanel(parent, self._palette, height=height, fill_key="surface_bg", radius=14, padding=10)
        right_pad = 0 if columnspan > 1 or column == 1 else 5
        card.grid(row=row, column=column, columnspan=columnspan, sticky="ew", pady=(0, 8), padx=(0 if column == 0 else 5, right_pad))
        card.inner.grid_columnconfigure(0, weight=1)
        return card.inner

    def _add_label(self, parent: tk.Widget, key: str) -> None:
        self._localize(
            self._tag(
                tk.Label(parent, bg=self._palette()["surface_bg"], fg=self._palette()["text"], font=("Segoe UI Semibold", 9)),
                "surface_text",
            ),
            key,
        ).pack(anchor="w")

    def _set_hotkey_text(self, text: str) -> None:
        self.hotkey_var.set(text)
        if self.hotkey_button is not None:
            self.hotkey_button.configure(text=text)

    def _sync_settings_ui(self) -> None:
        self.mode_var.set(self._mode_label(self.config.mode))
        self._set_hotkey_text(self.config.hotkey.label if self.config.hotkey else self._text("unassigned"))
        self.sounds_var.set(self.config.sounds_enabled)
        self.autostart_var.set(self.config.autostart)
        self.overlay_var.set(self.config.overlay_enabled)
        self.overlay_x_var.set(round(self.config.overlay_position_x * 100))
        self.overlay_y_var.set(round(self.config.overlay_position_y * 100))
        self.overlay_scale_var.set(round(self.config.overlay_scale * 100))
        self._sync_microphone_combo()
        self._sync_overlay_edit_button_state()
        if self.mode_combo is not None:
            selected_index = MODE_ORDER.index(self.config.mode) if self.config.mode in MODE_ORDER else 0
            self.mode_combo.set_options(self._mode_values(), selected_index)
        self._update_language_buttons_state()

    def _sync_microphone_combo(self) -> None:
        if self.mic_combo is None:
            return

        values = []
        selected_index = 0
        for index, device in enumerate(self.devices):
            label = self._text("default_device").format(name=device.name) if device.is_default else device.name
            values.append(label)
            if self.config.microphone_id:
                if device.id == self.config.microphone_id:
                    selected_index = index
            elif device.is_default:
                selected_index = index

        if values:
            self.mic_combo.set_options(values, selected_index)
            self.mic_var.set(values[selected_index])
        else:
            self.mic_combo.set_options([])

    def _ensure_guardian_for_device(self, device_id: str | None = None) -> None:
        target_device_id = self.config.microphone_id if device_id is None else device_id
        if target_device_id in self._guardian_device_ids:
            return
        if start_guardian(target_device_id):
            self._guardian_device_ids.add(target_device_id)

    def _ensure_guardian_if_muted(self) -> None:
        if self.current_state.is_available and self.current_state.is_muted:
            self._ensure_guardian_for_device()

    def _load_microphones(self) -> None:
        self.devices = self.audio.list_devices()
        self.current_state = self.audio.get_state(self.config.microphone_id)
        self._sync_microphone_combo()
        self._refresh_status_ui()
        self._apply_overlay()

    def _save_general_settings(self) -> None:
        self.config.mode = self._selected_mode()
        self.config.suppress_hotkey = False
        self.config.sounds_enabled = self.sounds_var.get()
        self.config_store.save(self.config)
        self._apply_runtime_state(enforce_idle_state=True, play_sound=False)

    def _save_visual_settings(self) -> None:
        self.config.overlay_enabled = self.overlay_var.get()
        self.config.overlay_position_x = self.overlay_x_var.get() / 100
        self.config.overlay_position_y = self.overlay_y_var.get() / 100
        self.config.overlay_scale = self.overlay_scale_var.get() / 100
        if not self.config.overlay_enabled and self._overlay_edit_active:
            self._overlay_edit_active = False
            self.overlay.finish_edit(commit=True)
        self.config_store.save(self.config)
        self._sync_overlay_edit_button_state()
        self._apply_overlay()

    def _set_language(self, language: str) -> None:
        if language == self.config.language:
            return
        self.config.language = language
        self.config_store.save(self.config)
        self.tray.set_language()
        self._refresh_localized_text()
        self._refresh_status_ui()

    def _on_autostart_changed(self) -> None:
        self.config.autostart = self.autostart_var.get()
        try:
            set_autostart(self.config.autostart)
        except OSError:
            self.config.autostart = False
            self.autostart_var.set(False)
        self.config_store.save(self.config)

    def _refresh_localized_text(self) -> None:
        for widget, key in list(self._localized_widgets):
            try:
                if widget.winfo_exists():
                    widget.configure(text=self._text(key))
            except tk.TclError:
                continue
        self._set_hotkey_text(self.config.hotkey.label if self.config.hotkey else self._text("unassigned"))
        if self.mode_combo is not None:
            selected_index = MODE_ORDER.index(self.config.mode) if self.config.mode in MODE_ORDER else 0
            self.mode_combo.set_options(self._mode_values(), selected_index)
        self._sync_microphone_combo()
        self._update_language_buttons_state()
        self._sync_overlay_edit_button_state()

    def _toggle_overlay_edit(self) -> None:
        if self._overlay_edit_active:
            self._overlay_edit_active = False
            self.overlay.finish_edit(commit=True)
            self._sync_overlay_edit_button_state()
            self._apply_overlay()
            return
        if not self.overlay_var.get():
            self.overlay_var.set(True)
            self._save_visual_settings()
        self._overlay_edit_active = True
        self._sync_overlay_edit_button_state()
        self.overlay.begin_edit(self.config, self.current_state.is_muted, self._on_overlay_edit)

    def _sync_overlay_edit_button_state(self) -> None:
        if self.overlay_edit_button is None:
            return
        colors = self._palette()
        active = self._overlay_edit_active
        background = colors["accent_on"] if active else colors["button_bg"]
        hover = "#239863" if active else colors["button_hover"]
        border = colors["accent_on"] if active else colors["border"]
        foreground = "#F7FAFC" if active else colors["text"]
        self.overlay_edit_button.configure(
            text=self._text("edit_overlay_active" if active else "edit_overlay"),
            bg=background,
            fg=foreground,
            activebackground=hover,
            activeforeground=foreground,
            highlightbackground=border,
            highlightcolor=border,
            relief="sunken" if active else "flat",
        )

    def _on_overlay_edit(self, normalized_x: float, normalized_y: float, scale: float, is_final: bool) -> None:
        self.config.overlay_position_x = normalized_x
        self.config.overlay_position_y = normalized_y
        self.config.overlay_scale = scale
        self.overlay_x_var.set(round(normalized_x * 100))
        self.overlay_y_var.set(round(normalized_y * 100))
        self.overlay_scale_var.set(round(scale * 100))
        if is_final:
            self.config_store.save(self.config)
            self._apply_overlay()

    def _on_microphone_selected(self, _event=None) -> None:
        if self.mic_combo is None:
            return
        index = self.mic_combo.current()
        if index < 0 or index >= len(self.devices):
            return
        self.config.microphone_id = "" if self.devices[index].is_default else self.devices[index].id
        self.config_store.save(self.config)
        self.current_state = self.audio.get_state(self.config.microphone_id)
        self._ensure_guardian_if_muted()
        self._apply_runtime_state(enforce_idle_state=True, play_sound=False)

    def _on_mode_changed(self, _event=None) -> None:
        self.hotkey_is_held = False
        self._save_general_settings()

    def _start_hotkey_capture(self) -> None:
        self._set_hotkey_text(self._text("capture"))
        self.hooks.begin_capture()

    def _clear_hotkey(self) -> None:
        self.config.hotkey = None
        self.config_store.save(self.config)
        self._set_hotkey_text(self._text("unassigned"))
        self._apply_runtime_state(enforce_idle_state=False, play_sound=False)

    def _enqueue_hook_event(self, event_name: str, hotkey: HotkeySpec | None) -> None:
        self.command_queue.put((event_name, hotkey))

    def _process_queue(self) -> None:
        while True:
            try:
                event_name, payload = self.command_queue.get_nowait()
            except queue.Empty:
                break

            if event_name == "hotkey_down":
                self._handle_hotkey_down()
            elif event_name == "hotkey_up":
                self._handle_hotkey_up()
            elif event_name == "capture":
                self._handle_hotkey_capture(payload)
            elif event_name == "show_settings":
                self.show_settings()
            elif event_name == "toggle_microphone":
                self.toggle_microphone()
            elif event_name == "toggle_overlay":
                self.overlay_var.set(not self.overlay_var.get())
                self._save_visual_settings()
            elif event_name == "show_tray_menu":
                if isinstance(payload, tuple) and len(payload) == 2:
                    self._show_tray_menu(int(payload[0]), int(payload[1]))
            elif event_name == "exit":
                self.exit_app()

        self.root.after(40, self._process_queue)

    def _handle_hotkey_capture(self, payload: object | None) -> None:
        if not isinstance(payload, HotkeySpec):
            self._set_hotkey_text(self.config.hotkey.label if self.config.hotkey else self._text("unassigned"))
            return
        self.config.hotkey = payload
        self._set_hotkey_text(payload.label)
        self.config_store.save(self.config)
        self._apply_runtime_state(enforce_idle_state=False, play_sound=False)

    def _handle_hotkey_down(self) -> None:
        mode = self.config.mode
        if mode == "toggle":
            self.toggle_microphone()
            return

        if self.hotkey_is_held:
            return
        self.hotkey_is_held = True

        if mode == "push_to_talk":
            self.set_microphone_muted(False, trigger="ptt_press")
        elif mode == "push_to_mute":
            self.set_microphone_muted(True, trigger="ptm_press")

    def _handle_hotkey_up(self) -> None:
        if not self.hotkey_is_held:
            return
        self.hotkey_is_held = False

        if self.config.mode == "push_to_talk":
            self.set_microphone_muted(True, trigger="ptt_release")
        elif self.config.mode == "push_to_mute":
            self.set_microphone_muted(False, trigger="ptm_release")

    def _apply_runtime_state(self, enforce_idle_state: bool, play_sound: bool, refresh_state: bool = True) -> None:
        self.hooks.set_hotkey(self.config.hotkey, self.config.suppress_hotkey)
        if enforce_idle_state:
            self._apply_mode_idle_state(play_sound=play_sound)
        if refresh_state:
            self.current_state = self.audio.get_state(self.config.microphone_id)
        self._refresh_status_ui()
        self._apply_overlay()

    def _apply_mode_idle_state(self, play_sound: bool) -> None:
        if self.config.mode == "push_to_talk" and not self.current_state.is_muted:
            self.set_microphone_muted(True, trigger="mode_change", play_feedback=play_sound)
        elif self.config.mode == "push_to_mute" and self.current_state.is_muted:
            self.set_microphone_muted(False, trigger="mode_change", play_feedback=play_sound)

    def _apply_overlay(self) -> None:
        self.overlay.update(self.config, self.current_state.is_muted, self.current_state.name)
        self.tray.update_state(
            self.current_state.is_muted,
            self.config.overlay_enabled,
            self.current_state.name,
            self.current_state.is_available,
        )

    def _pulse_overlay(self) -> None:
        self.overlay.pulse()
        self.root.after(900, self._pulse_overlay)

    def _poll_microphone_state(self) -> None:
        state = self.audio.get_state(self.config.microphone_id)
        if state != self.current_state:
            self.current_state = state
            self._refresh_status_ui()
            self._apply_overlay()
        self.root.after(800, self._poll_microphone_state)

    def _refresh_status_ui(self) -> None:
        colors = self._palette()
        if self.current_state.is_available:
            muted = self.current_state.is_muted
            status_text = self._text("status_off" if muted else "status_on")
            sub_text = self.current_state.name
            accent = colors["accent_off"] if muted else colors["accent_on"]
        else:
            status_text = self._text("status_unavailable")
            sub_text = self._text("status_pick_other")
            accent = "#F5A524"

        self.status_var.set(status_text)
        self.substatus_var.set(sub_text)
        if self.status_label is not None:
            self.status_label.configure(fg=accent, bg=colors["surface_raised"])
        if self.substatus_label is not None:
            self.substatus_label.configure(fg=colors["muted"], bg=colors["surface_raised"])
        if self.status_icon_label is not None:
            self.status_icon_label.configure(image=self._get_status_icon())

    def toggle_microphone(self) -> None:
        previous_state = self.audio.get_state(self.config.microphone_id)
        if not previous_state.is_available:
            self.current_state = previous_state
            self._refresh_status_ui()
            self._apply_overlay()
            return

        target_muted = not previous_state.is_muted
        if target_muted:
            self._ensure_guardian_for_device()
        self.current_state = self.audio.set_muted(self.config.microphone_id, target_muted)
        self._play_feedback_if_needed("toggle")
        self._refresh_status_ui()
        self._apply_overlay()

    def set_microphone_muted(self, muted: bool, trigger: str, play_feedback: bool = True) -> None:
        previous_state = self.current_state
        if muted:
            self._ensure_guardian_for_device()
        self.current_state = self.audio.set_muted(self.config.microphone_id, muted)
        if play_feedback and previous_state.is_muted != self.current_state.is_muted:
            self._play_feedback_if_needed(trigger)
        self._refresh_status_ui()
        self._apply_overlay()

    def _play_feedback_if_needed(self, trigger: str) -> None:
        if not self.config.sounds_enabled or not self.current_state.is_available:
            return

        if trigger == "ptt_press" and not self.current_state.is_muted:
            self.sounds.play("ptt_on")
        elif trigger == "ptt_release" and self.current_state.is_muted:
            self.sounds.play("ptt_off")
        elif trigger == "ptm_press" and self.current_state.is_muted:
            self.sounds.play("ptt_off")
        elif trigger == "ptm_release" and not self.current_state.is_muted:
            self.sounds.play("ptt_on")
        else:
            self.sounds.play("mute" if self.current_state.is_muted else "unmute")

    def _show_tray_menu(self, x: int, y: int) -> None:
        self._hide_tray_menu()
        if self._tray_menu_resume_job is not None:
            try:
                self.root.after_cancel(self._tray_menu_resume_job)
            except tk.TclError:
                pass
            self._tray_menu_resume_job = None
        self.tray.set_custom_menu_active(True)
        self._tray_menu_hotkeys_paused = True
        self.hooks.set_hotkey(None, False)
        colors = self._palette()
        menu = tk.Toplevel(self.root)
        menu.overrideredirect(True)
        menu.attributes("-topmost", True)
        menu.configure(bg=colors["surface_bg"])
        self.tray_menu = menu

        box = tk.Frame(menu, bg=colors["surface_bg"])
        box.pack(fill="both", expand=True)

        self._tray_menu_item(box, "tray_settings", self.show_settings).pack(fill="x")
        self._tray_menu_item(box, "tray_exit", self.exit_app).pack(fill="x")

        width = 118
        height = 58
        menu.geometry(f"{width}x{height}+{x - width}+{y - height}")
        menu.bind("<FocusOut>", lambda _event: self._hide_tray_menu())
        menu.after(10, menu.focus_force)

    def _tray_menu_item(self, parent: tk.Widget, key: str, command) -> tk.Label:
        colors = self._palette()
        item = tk.Label(parent, text=self._text(key), anchor="w", padx=12, pady=6, bg=colors["surface_bg"], fg=colors["text"], font=("Segoe UI", 9))
        item.configure(cursor="hand2")
        item.bind("<Enter>", lambda _event: item.configure(bg=colors["button_hover"]))
        item.bind("<Leave>", lambda _event: item.configure(bg=colors["surface_bg"]))
        item.bind("<Button-1>", lambda _event: (self._hide_tray_menu(), command()))
        return item

    def _hide_tray_menu(self) -> None:
        if self.tray_menu is not None and self.tray_menu.winfo_exists():
            self.tray_menu.destroy()
        self.tray_menu = None
        if self._tray_menu_resume_job is None:
            self._tray_menu_resume_job = self.root.after(450, self._resume_hotkeys_after_tray_menu)

    def _resume_hotkeys_after_tray_menu(self) -> None:
        self._tray_menu_resume_job = None
        self.tray.set_custom_menu_active(False)
        if not self._tray_menu_hotkeys_paused:
            return
        self._tray_menu_hotkeys_paused = False
        self.hooks.set_hotkey(self.config.hotkey, self.config.suppress_hotkey)

    def _force_settings_foreground(self) -> None:
        if self.settings_window is None or not self.settings_window.winfo_exists():
            return
        try:
            self.settings_window.attributes("-topmost", True)
            self.settings_window.lift()
            self.settings_window.focus_force()
            for handle in _window_handles(self.settings_window):
                hwnd = wintypes.HWND(handle)
                user32.ShowWindow(hwnd, SW_RESTORE)
                user32.BringWindowToTop(hwnd)
                user32.SetForegroundWindow(hwnd)
                user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_FRAMECHANGED)
                user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_FRAMECHANGED)
            self.settings_window.after(350, lambda: self.settings_window.attributes("-topmost", False) if self.settings_window and self.settings_window.winfo_exists() else None)
        except (tk.TclError, OSError, ValueError):
            pass

    def show_settings(self) -> None:
        self._ensure_settings_window()
        self._sync_settings_ui()
        self._refresh_status_ui()
        self._sync_overlay_edit_button_state()
        assert self.settings_window is not None
        self.settings_window.deiconify()
        self.settings_window.update_idletasks()
        _apply_appwindow_style(self.settings_window)
        self._refresh_titlebar_theme()
        self._force_settings_foreground()
        self.settings_window.after(
            80,
            lambda: (_apply_appwindow_style(self.settings_window), self._refresh_titlebar_theme(), self._force_settings_foreground())
            if self.settings_window and self.settings_window.winfo_exists()
            else None,
        )

    def hide_window(self) -> None:
        if self._overlay_edit_active:
            self._overlay_edit_active = False
            self.overlay.finish_edit(commit=True)
        if self.settings_window is not None and self.settings_window.winfo_exists():
            self.settings_window.withdraw()

    def run(self) -> None:
        self.root.mainloop()

    def _restore_microphone_on_exit(self) -> None:
        try:
            state = self.audio.get_state(self.config.microphone_id)
            if state.is_available and state.is_muted:
                self.current_state = self.audio.set_muted(self.config.microphone_id, False)
        except Exception:
            pass

    def exit_app(self) -> None:
        if self._overlay_edit_active:
            self._overlay_edit_active = False
            self.overlay.finish_edit(commit=True)
        self._restore_microphone_on_exit()
        self.config_store.save(self.config)
        try:
            self.overlay.destroy()
        finally:
            self.ipc.stop()
            self.hooks.stop()
            self.tray.stop()
            if self.settings_window is not None and self.settings_window.winfo_exists():
                self.settings_window.destroy()
            self.root.destroy()
