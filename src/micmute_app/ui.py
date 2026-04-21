from __future__ import annotations

import ctypes
import queue
import tkinter as tk
from ctypes import wintypes
from tkinter import ttk

from PIL import ImageTk

from . import APP_NAME, APP_VERSION
from .assets import load_app_icon
from .audio import MicrophoneInfo, MicrophoneService, SoundService
from .config import ConfigStore
from .hooks import GlobalHookManager
from .hotkeys import HotkeySpec
from .ipc import SingleInstanceBridge
from .overlay import OverlayManager
from .tray import TrayController


LRESULT = ctypes.c_longlong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_long
LONG_PTR = ctypes.c_longlong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_long


try:
    dwmapi = ctypes.windll.dwmapi
except OSError:
    dwmapi = None
else:
    dwmapi.DwmSetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
    dwmapi.DwmSetWindowAttribute.restype = ctypes.c_long


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

user32 = ctypes.windll.user32
user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.SendMessageW.restype = LRESULT
user32.RedrawWindow.argtypes = [wintypes.HWND, ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT]
user32.RedrawWindow.restype = wintypes.BOOL
user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetWindowLongPtrW.restype = LONG_PTR
user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, LONG_PTR]
user32.SetWindowLongPtrW.restype = LONG_PTR
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
        "toggle_now": "Переключить сейчас",
        "dark_theme": "Тёмная тема",
        "sounds_enabled": "Звуки on/off",
        "overlay": "Overlay",
        "show_overlay": "Показывать overlay",
        "edit_overlay": "Редактировать overlay",
        "edit_overlay_active": "Редактирование overlay: ON",
        "overlay_drag_hint": "Тяни overlay мышкой. За правый нижний угол можно менять размер.",
        "sound_note": "Если рядом с exe лежат on.mp3 / off.mp3, программа подхватит их сама. Если файл не откроется, она тихо вернётся на встроенные звуки.",
        "hide": "Скрыть",
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
        "toggle_now": "Toggle now",
        "dark_theme": "Dark theme",
        "sounds_enabled": "On/off sounds",
        "overlay": "Overlay",
        "show_overlay": "Show overlay",
        "edit_overlay": "Edit overlay",
        "edit_overlay_active": "Overlay edit: ON",
        "overlay_drag_hint": "Drag the overlay. Use the bottom-right corner to resize it.",
        "sound_note": "If on.mp3 / off.mp3 are next to the exe, the app will use them first. If the file cannot be played, it will quietly fall back to built-in sounds.",
        "hide": "Hide",
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
        "window_bg": "#111315",
        "surface_bg": "#181B1F",
        "input_bg": "#0E1013",
        "border": "#2D3138",
        "text": "#F5F7FA",
        "muted": "#9AA4B2",
        "button_bg": "#20242A",
        "button_hover": "#2B3037",
        "accent_on": "#2BB673",
        "accent_off": "#D94D57",
    },
    "light": {
        "window_bg": "#E7ECF1",
        "surface_bg": "#F2F5F8",
        "input_bg": "#ECF1F5",
        "border": "#C5CED8",
        "text": "#16202A",
        "muted": "#6A7380",
        "button_bg": "#E1E8F0",
        "button_hover": "#D5DEE8",
        "accent_on": "#0F8A57",
        "accent_off": "#C53D45",
    },
}


def _hex_to_colorref(hex_color: str) -> int:
    value = hex_color.lstrip("#")
    red = int(value[0:2], 16)
    green = int(value[2:4], 16)
    blue = int(value[4:6], 16)
    return red | (green << 8) | (blue << 16)


def _apply_window_titlebar_theme(window: tk.Toplevel, dark: bool, palette: dict[str, str] | None = None) -> None:
    if dwmapi is None:
        return
    try:
        window.update_idletasks()
        hwnd = wintypes.HWND(window.winfo_id())
        value = ctypes.c_int(1 if dark else 0)
        for attribute in (DWMWA_USE_IMMERSIVE_DARK_MODE, DWMWA_USE_IMMERSIVE_DARK_MODE_OLD):
            dwmapi.DwmSetWindowAttribute(hwnd, attribute, ctypes.byref(value), ctypes.sizeof(value))
        if palette is not None:
            caption = wintypes.DWORD(_hex_to_colorref(palette["surface_bg"] if dark else palette["window_bg"]))
            border = wintypes.DWORD(_hex_to_colorref(palette["border"]))
            text = wintypes.DWORD(_hex_to_colorref("#F5F7FA" if dark else "#16202A"))
            dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_CAPTION_COLOR, ctypes.byref(caption), ctypes.sizeof(caption))
            dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_BORDER_COLOR, ctypes.byref(border), ctypes.sizeof(border))
            dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_TEXT_COLOR, ctypes.byref(text), ctypes.sizeof(text))
    except tk.TclError:
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


class MicMuteApp:
    def __init__(self) -> None:
        self.should_exit_immediately = False
        self.command_queue: queue.Queue[tuple[str, object | None]] = queue.Queue()
        self.ipc = SingleInstanceBridge(lambda: self.command_queue.put(("show_settings", None)))
        if not self.ipc.start_or_signal_existing():
            self.should_exit_immediately = True
            return

        self.config_store = ConfigStore()
        self.first_run = not self.config_store.path.exists()
        self.config = self.config_store.load()
        self.config.suppress_hotkey = True
        if abs(self.config.overlay_position_x - 0.88) < 0.001 and abs(self.config.overlay_position_y - 0.1) < 0.001:
            self.config.overlay_position_x = 0.5
            self.config.overlay_position_y = 0.14
            self.config_store.save(self.config)

        self.audio = MicrophoneService()
        self.sounds = SoundService()
        self.hooks = GlobalHookManager(self._enqueue_hook_event)
        self.hooks.start()

        self.root = tk.Tk()
        self.root.geometry("1x1+-32000+-32000")
        self.root.overrideredirect(True)
        self.root.title(APP_NAME)
        self._app_icon_small_ref: ImageTk.PhotoImage | None = None
        self._app_icon_large_ref: ImageTk.PhotoImage | None = None
        self._titlebar_icon_ref: ImageTk.PhotoImage | None = None
        self._apply_app_icon(self.root)
        self.root.withdraw()

        self.settings_window: tk.Toplevel | None = None
        self._settings_ready = False
        self._overlay_edit_active = False

        self.tray = TrayController(self.command_queue, self._text)
        self.overlay = OverlayManager(self.root)
        self.devices: list[MicrophoneInfo] = []
        self.hotkey_is_held = False
        self.current_state = self.audio.get_state(self.config.microphone_id)

        self.mic_var = tk.StringVar()
        self.mode_var = tk.StringVar(value=self._mode_label(self.config.mode))
        self.hotkey_var = tk.StringVar(value=self.config.hotkey.label if self.config.hotkey else self._text("unassigned"))
        self.status_var = tk.StringVar()
        self.substatus_var = tk.StringVar()
        self.theme_var = tk.BooleanVar(value=self.config.dark_theme)
        self.sounds_var = tk.BooleanVar(value=self.config.sounds_enabled)
        self.overlay_var = tk.BooleanVar(value=self.config.overlay_enabled)
        self.overlay_x_var = tk.DoubleVar(value=self.config.overlay_position_x * 100)
        self.overlay_y_var = tk.DoubleVar(value=self.config.overlay_position_y * 100)
        self.overlay_scale_var = tk.DoubleVar(value=self.config.overlay_scale * 100)
        self._window_drag_offset_x = 0
        self._window_drag_offset_y = 0

        self.mic_combo: ttk.Combobox | None = None
        self.mode_combo: ttk.Combobox | None = None
        self.status_label: tk.Label | None = None
        self.substatus_label: tk.Label | None = None
        self.overlay_edit_button: tk.Button | None = None
        self.lang_ru_button: tk.Button | None = None
        self.lang_en_button: tk.Button | None = None
        self.titlebar_frame: tk.Frame | None = None
        self.titlebar_icon_label: tk.Label | None = None
        self.titlebar_label: tk.Label | None = None
        self.titlebar_minimize_button: tk.Button | None = None
        self.titlebar_close_button: tk.Button | None = None

        self._load_microphones()
        self._apply_runtime_state(enforce_idle_state=True, play_sound=False)
        self.tray.start(
            self.current_state.is_muted,
            self.config.overlay_enabled,
            self.current_state.name,
            self.current_state.is_available,
        )

        self._process_queue()
        self._poll_microphone_state()
        self._pulse_overlay()

        if self.first_run:
            self.show_settings()

    def _text(self, key: str) -> str:
        language = self.config.language if self.config.language in TEXTS else "ru"
        return TEXTS[language].get(key, key)

    def _mode_label(self, mode: str) -> str:
        return self._text(f"mode_{mode}")

    def _mode_values(self) -> list[str]:
        return [self._mode_label(mode) for mode in MODE_ORDER]

    def _selected_mode(self) -> str:
        current = self.mode_var.get()
        for mode in MODE_ORDER:
            if current == self._mode_label(mode):
                return mode
        return "toggle"

    def _palette(self) -> dict[str, str]:
        return PALETTES["dark" if self.config.dark_theme else "light"]

    def _tag(self, widget: tk.Widget, role: str) -> tk.Widget:
        setattr(widget, "_theme_role", role)
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

    def _style_combobox_popdown(self, combo: ttk.Combobox | None) -> None:
        if combo is None:
            return
        colors = self._palette()
        try:
            popdown = combo.tk.call("ttk::combobox::PopdownWindow", combo)
            listbox = combo.nametowidget(f"{popdown}.f.l")
            listbox.configure(
                bg=colors["input_bg"],
                fg=colors["text"],
                selectbackground=colors["button_hover"],
                selectforeground=colors["text"],
                highlightthickness=0,
                bd=0,
            )
        except (tk.TclError, KeyError):
            pass

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
        self.settings_window.configure(bg=colors["border"])

        for widget in self._iter_widgets(self.settings_window):
            role = getattr(widget, "_theme_role", None)

            if isinstance(widget, ttk.Combobox):
                widget.configure(style="MicMute.TCombobox")
                continue

            if role == "window_frame":
                widget.configure(bg=colors["window_bg"])
            elif role == "window_border":
                widget.configure(bg=colors["border"])
            elif role == "surface_frame":
                widget.configure(bg=colors["surface_bg"], highlightbackground=colors["border"])
            elif role == "titlebar_frame":
                widget.configure(bg=colors["surface_bg"])
            elif role == "titlebar_icon":
                widget.configure(bg=colors["surface_bg"])
            elif role == "titlebar_text":
                widget.configure(bg=colors["surface_bg"], fg=colors["text"])
            elif role == "window_text":
                widget.configure(bg=colors["window_bg"], fg=colors["text"])
            elif role == "surface_text":
                widget.configure(bg=colors["surface_bg"], fg=colors["text"])
            elif role == "muted_window":
                widget.configure(bg=colors["window_bg"], fg=colors["muted"])
            elif role == "muted_surface":
                widget.configure(bg=colors["surface_bg"], fg=colors["muted"])
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
            elif role == "titlebar_button":
                widget.configure(
                    bg=colors["surface_bg"],
                    fg=colors["text"],
                    activebackground=colors["button_hover"],
                    activeforeground=colors["text"],
                    highlightbackground=colors["surface_bg"],
                    highlightcolor=colors["surface_bg"],
                    disabledforeground=colors["muted"],
                )
            elif role == "titlebar_close_button":
                widget.configure(
                    bg=colors["surface_bg"],
                    fg=colors["text"],
                    activebackground=colors["accent_off"],
                    activeforeground="#F7FAFC",
                    highlightbackground=colors["surface_bg"],
                    highlightcolor=colors["surface_bg"],
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

        self._style_combobox_popdown(self.mic_combo)
        self._style_combobox_popdown(self.mode_combo)
        self._update_language_buttons_state()
        self._sync_overlay_edit_button_state()
        self._refresh_status_ui()
        if self.titlebar_icon_label is not None:
            self.titlebar_icon_label.configure(image=self._get_titlebar_icon())
        _apply_window_titlebar_theme(self.settings_window, self.config.dark_theme, colors)

    def _button(self, parent: tk.Widget, text: str, command, width: int | None = None) -> tk.Button:
        colors = self._palette()
        button = tk.Button(
            parent,
            text=text,
            command=command,
            relief="flat",
            borderwidth=1,
            highlightthickness=1,
            highlightbackground=colors["border"],
            highlightcolor=colors["border"],
            bg=colors["button_bg"],
            fg=colors["text"],
            activebackground=colors["button_hover"],
            activeforeground=colors["text"],
            disabledforeground=colors["muted"],
            padx=10,
            pady=6,
            cursor="hand2",
            width=width,
        )
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

    def _get_titlebar_icon(self) -> ImageTk.PhotoImage:
        if self._titlebar_icon_ref is None:
            self._titlebar_icon_ref = ImageTk.PhotoImage(load_app_icon(14))
        return self._titlebar_icon_ref

    def _titlebar_button(self, parent: tk.Widget, glyph: str, command, close: bool = False) -> tk.Button:
        colors = self._palette()
        button = tk.Button(
            parent,
            text=glyph,
            command=command,
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            bg=colors["surface_bg"],
            fg=colors["text"],
            activebackground=colors["accent_off"] if close else colors["button_hover"],
            activeforeground="#F7FAFC" if close else colors["text"],
            disabledforeground=colors["muted"],
            padx=0,
            pady=0,
            cursor="hand2",
            width=4,
            font=("Segoe MDL2 Assets", 10),
        )
        return self._tag(button, "titlebar_close_button" if close else "titlebar_button")

    def _start_window_drag(self, event: tk.Event) -> None:
        if self.settings_window is None or not self.settings_window.winfo_exists():
            return
        self._window_drag_offset_x = event.x_root - self.settings_window.winfo_x()
        self._window_drag_offset_y = event.y_root - self.settings_window.winfo_y()

    def _drag_window(self, event: tk.Event) -> None:
        if self.settings_window is None or not self.settings_window.winfo_exists():
            return
        x = event.x_root - self._window_drag_offset_x
        y = event.y_root - self._window_drag_offset_y
        self.settings_window.geometry(f"+{x}+{y}")

    def _rebuild_settings_window(self) -> None:
        if self.settings_window is None or not self.settings_window.winfo_exists():
            return
        hwnd = wintypes.HWND(self.settings_window.winfo_id())
        previous_alpha = 1.0
        try:
            try:
                previous_alpha = float(self.settings_window.attributes("-alpha"))
            except (tk.TclError, TypeError, ValueError):
                previous_alpha = 1.0
            self.settings_window.attributes("-alpha", 0.0)
            user32.SendMessageW(hwnd, WM_SETREDRAW, 0, 0)
            for child in self.settings_window.winfo_children():
                child.destroy()
            self._settings_ready = False
            self._ensure_settings_window()
        finally:
            user32.SendMessageW(hwnd, WM_SETREDRAW, 1, 0)
            user32.RedrawWindow(hwnd, None, None, RDW_INVALIDATE | RDW_UPDATENOW | RDW_ALLCHILDREN | RDW_FRAME)
            try:
                self.settings_window.attributes("-alpha", previous_alpha)
            except tk.TclError:
                pass

    def _ensure_settings_window(self) -> None:
        self._setup_styles()

        if self.settings_window is None or not self.settings_window.winfo_exists():
            self.settings_window = tk.Toplevel(self.root)
            self.settings_window.title(f"{APP_NAME} {APP_VERSION}")
            self.settings_window.geometry("430x594")
            self.settings_window.resizable(False, False)
            self.settings_window.protocol("WM_DELETE_WINDOW", self.hide_window)
            self.settings_window.bind("<Escape>", lambda _event: self.hide_window())
            self.settings_window.bind("<Alt-F4>", lambda _event: (self.hide_window(), "break")[1])
            self.settings_window.overrideredirect(True)
            self._apply_app_icon(self.settings_window)
            _apply_appwindow_style(self.settings_window)
            self._settings_ready = False

        if self._settings_ready:
            self._apply_theme()
            self._sync_settings_ui()
            return

        colors = self._palette()
        window = self.settings_window
        window.configure(bg=colors["border"])

        root_frame = self._tag(tk.Frame(window, bg=colors["window_bg"]), "window_frame")
        root_frame.pack(fill="both", expand=True, padx=1, pady=1)

        self.titlebar_frame = self._tag(tk.Frame(root_frame, bg=colors["surface_bg"], height=34), "titlebar_frame")
        self.titlebar_frame.pack(fill="x")
        self.titlebar_frame.pack_propagate(False)
        for widget in (self.titlebar_frame,):
            widget.bind("<ButtonPress-1>", self._start_window_drag)
            widget.bind("<B1-Motion>", self._drag_window)

        titlebar_left = self._tag(tk.Frame(self.titlebar_frame, bg=colors["surface_bg"]), "titlebar_frame")
        titlebar_left.pack(side="left", fill="y")
        titlebar_left.bind("<ButtonPress-1>", self._start_window_drag)
        titlebar_left.bind("<B1-Motion>", self._drag_window)

        self.titlebar_icon_label = self._tag(
            tk.Label(
                titlebar_left,
                image=self._get_titlebar_icon(),
                bg=colors["surface_bg"],
                padx=10,
                pady=0,
            ),
            "titlebar_icon",
        )
        self.titlebar_icon_label.pack(side="left", fill="y")
        self.titlebar_icon_label.bind("<ButtonPress-1>", self._start_window_drag)
        self.titlebar_icon_label.bind("<B1-Motion>", self._drag_window)

        self.titlebar_label = self._tag(
            tk.Label(
                titlebar_left,
                text=f"{APP_NAME} {APP_VERSION}",
                bg=colors["surface_bg"],
                fg=colors["text"],
                font=("Segoe UI", 9),
                anchor="w",
                padx=0,
            ),
            "titlebar_text",
        )
        self.titlebar_label.pack(side="left", fill="y")
        self.titlebar_label.bind("<ButtonPress-1>", self._start_window_drag)
        self.titlebar_label.bind("<B1-Motion>", self._drag_window)

        titlebar_buttons = self._tag(tk.Frame(self.titlebar_frame, bg=colors["surface_bg"]), "titlebar_frame")
        titlebar_buttons.pack(side="right", fill="y")
        self.titlebar_minimize_button = self._titlebar_button(titlebar_buttons, "\uE921", self.hide_window)
        self.titlebar_minimize_button.pack(side="left", fill="y")
        self.titlebar_close_button = self._titlebar_button(titlebar_buttons, "\uE8BB", self.hide_window, close=True)
        self.titlebar_close_button.pack(side="left", fill="y")

        content = self._tag(tk.Frame(root_frame, bg=colors["window_bg"]), "window_frame")
        content.pack(fill="both", expand=True, padx=12, pady=12)

        header = self._tag(tk.Frame(content, bg=colors["window_bg"]), "window_frame")
        header.pack(fill="x", pady=(0, 8))

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

        status_box = self._tag(
            tk.Frame(content, bg=colors["surface_bg"], highlightthickness=1, highlightbackground=colors["border"]),
            "surface_frame",
        )
        status_box.pack(fill="x")

        self.status_label = self._tag(
            tk.Label(status_box, textvariable=self.status_var, bg=colors["surface_bg"], fg=colors["accent_off"], font=("Segoe UI Semibold", 12)),
            "surface_text",
        )
        self.status_label.pack(anchor="w", padx=12, pady=(8, 2))

        self.substatus_label = self._tag(
            tk.Label(status_box, textvariable=self.substatus_var, bg=colors["surface_bg"], fg=colors["muted"], font=("Segoe UI", 9)),
            "muted_surface",
        )
        self.substatus_label.pack(anchor="w", padx=12, pady=(0, 8))

        self._button(status_box, self._text("toggle_now"), self.toggle_microphone).pack(anchor="e", padx=12, pady=(0, 8))

        form = self._tag(tk.Frame(content, bg=colors["window_bg"]), "window_frame")
        form.pack(fill="both", expand=True, pady=(10, 0))
        form.grid_columnconfigure(0, weight=1)

        self._add_label(form, self._text("mic"), 0)
        self.mic_combo = ttk.Combobox(form, textvariable=self.mic_var, state="readonly", width=38, style="MicMute.TCombobox")
        self.mic_combo.grid(row=1, column=0, sticky="ew")
        self.mic_combo.bind("<<ComboboxSelected>>", self._on_microphone_selected)
        self._button(form, self._text("refresh"), self._load_microphones, width=10).grid(row=1, column=1, padx=(8, 0))

        self._add_label(form, self._text("mode"), 2, pady=(10, 0))
        self.mode_combo = ttk.Combobox(form, textvariable=self.mode_var, values=self._mode_values(), state="readonly", width=22, style="MicMute.TCombobox")
        self.mode_combo.grid(row=3, column=0, sticky="w")
        self.mode_combo.bind("<<ComboboxSelected>>", self._on_mode_changed)

        self._add_label(form, self._text("bind"), 4, pady=(10, 0))
        hotkey_row = self._tag(tk.Frame(form, bg=colors["window_bg"]), "window_frame")
        hotkey_row.grid(row=5, column=0, columnspan=2, sticky="ew")
        hotkey_row.grid_columnconfigure(0, weight=1)

        self._tag(
            tk.Label(
                hotkey_row,
                textvariable=self.hotkey_var,
                bg=colors["input_bg"],
                fg=colors["text"],
                font=("Consolas", 10),
                anchor="w",
                relief="flat",
                highlightthickness=1,
                highlightbackground=colors["border"],
                highlightcolor=colors["border"],
                padx=8,
                pady=7,
            ),
            "input_label",
        ).grid(row=0, column=0, sticky="ew")
        self._button(hotkey_row, self._text("assign"), self._start_hotkey_capture, width=10).grid(row=0, column=1, padx=(8, 0))
        self._button(hotkey_row, self._text("clear"), self._clear_hotkey, width=9).grid(row=0, column=2, padx=(6, 0))

        options = self._tag(
            tk.Frame(form, bg=colors["surface_bg"], highlightthickness=1, highlightbackground=colors["border"]),
            "surface_frame",
        )
        options.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        self._checkbutton(options, self._text("dark_theme"), self.theme_var, self._on_theme_changed).pack(anchor="w", padx=10, pady=(8, 0))
        self._checkbutton(options, self._text("sounds_enabled"), self.sounds_var, self._save_general_settings).pack(anchor="w", padx=10, pady=(0, 8))

        self._add_label(form, self._text("overlay"), 7, pady=(10, 0))
        overlay_box = self._tag(
            tk.Frame(form, bg=colors["surface_bg"], highlightthickness=1, highlightbackground=colors["border"]),
            "surface_frame",
        )
        overlay_box.grid(row=8, column=0, columnspan=2, sticky="ew")

        self._checkbutton(overlay_box, self._text("show_overlay"), self.overlay_var, self._save_visual_settings).pack(anchor="w", padx=10, pady=(8, 4))

        move_row = self._tag(tk.Frame(overlay_box, bg=colors["surface_bg"]), "surface_frame")
        move_row.pack(fill="x", padx=10, pady=(0, 4))
        self.overlay_edit_button = self._button(move_row, self._text("edit_overlay"), self._toggle_overlay_edit)
        self.overlay_edit_button.pack(side="left")
        self._tag(
            tk.Label(
                move_row,
                text=self._text("overlay_drag_hint"),
                bg=colors["surface_bg"],
                fg=colors["muted"],
                font=("Segoe UI", 9),
                wraplength=200,
                justify="left",
            ),
            "muted_surface",
        ).pack(side="left", padx=(10, 0))

        self._tag(
            tk.Label(
                form,
                text=self._text("sound_note"),
                bg=colors["window_bg"],
                fg=colors["muted"],
                wraplength=390,
                justify="left",
                font=("Segoe UI", 9),
            ),
            "muted_window",
        ).grid(row=9, column=0, columnspan=2, sticky="w", pady=(10, 0))

        bottom = self._tag(tk.Frame(content, bg=colors["window_bg"]), "window_frame")
        bottom.pack(fill="x", pady=(10, 0))
        self._button(bottom, self._text("hide"), self.hide_window, width=10).pack(side="right")

        self._settings_ready = True
        self._apply_theme()
        self._sync_settings_ui()

    def _add_label(self, parent: tk.Widget, text: str, row: int, pady: tuple[int, int] = (0, 0)) -> None:
        self._tag(
            tk.Label(parent, text=text, bg=self._palette()["window_bg"], fg=self._palette()["text"], font=("Segoe UI Semibold", 9)),
            "window_text",
        ).grid(row=row, column=0, columnspan=2, sticky="w", pady=pady)

    def _sync_settings_ui(self) -> None:
        self.mode_var.set(self._mode_label(self.config.mode))
        self.hotkey_var.set(self.config.hotkey.label if self.config.hotkey else self._text("unassigned"))
        self.theme_var.set(self.config.dark_theme)
        self.sounds_var.set(self.config.sounds_enabled)
        self.overlay_var.set(self.config.overlay_enabled)
        self.overlay_x_var.set(round(self.config.overlay_position_x * 100))
        self.overlay_y_var.set(round(self.config.overlay_position_y * 100))
        self.overlay_scale_var.set(round(self.config.overlay_scale * 100))
        self._sync_microphone_combo()
        self._sync_overlay_edit_button_state()
        self._style_combobox_popdown(self.mic_combo)
        self._style_combobox_popdown(self.mode_combo)
        if self.mode_combo is not None:
            self.mode_combo.configure(values=self._mode_values())
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

        self.mic_combo["values"] = values
        if values:
            self.mic_combo.current(selected_index)
            self.mic_var.set(values[selected_index])

    def _load_microphones(self) -> None:
        self.devices = self.audio.list_devices()
        self.current_state = self.audio.get_state(self.config.microphone_id)
        self._sync_microphone_combo()
        self._refresh_status_ui()
        self._apply_overlay()

    def _save_general_settings(self) -> None:
        self.config.mode = self._selected_mode()
        self.config.dark_theme = self.theme_var.get()
        self.config.suppress_hotkey = True
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
        self.hotkey_var.set(self.config.hotkey.label if self.config.hotkey else self._text("unassigned"))
        if self.settings_window is not None and self.settings_window.winfo_exists():
            self._rebuild_settings_window()
        self._refresh_status_ui()

    def _on_theme_changed(self) -> None:
        self.config.dark_theme = self.theme_var.get()
        self.config_store.save(self.config)
        self._apply_theme()
        self._apply_overlay()

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
        self._apply_runtime_state(enforce_idle_state=True, play_sound=False)

    def _on_mode_changed(self, _event=None) -> None:
        self.hotkey_is_held = False
        self._save_general_settings()

    def _start_hotkey_capture(self) -> None:
        self.hotkey_var.set(self._text("capture"))
        self.hooks.begin_capture()

    def _clear_hotkey(self) -> None:
        self.config.hotkey = None
        self.config_store.save(self.config)
        self.hotkey_var.set(self._text("unassigned"))
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
            elif event_name == "exit":
                self.exit_app()

        self.root.after(40, self._process_queue)

    def _handle_hotkey_capture(self, payload: object | None) -> None:
        if not isinstance(payload, HotkeySpec):
            self.hotkey_var.set(self.config.hotkey.label if self.config.hotkey else self._text("unassigned"))
            return
        self.config.hotkey = payload
        self.hotkey_var.set(payload.label)
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

    def _apply_runtime_state(self, enforce_idle_state: bool, play_sound: bool) -> None:
        self.hooks.set_hotkey(self.config.hotkey, True)
        if enforce_idle_state:
            self._apply_mode_idle_state(play_sound=play_sound)
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
        self.root.after(500, self._poll_microphone_state)

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
            self.status_label.configure(fg=accent, bg=colors["surface_bg"])
        if self.substatus_label is not None:
            self.substatus_label.configure(fg=colors["muted"], bg=colors["surface_bg"])

    def toggle_microphone(self) -> None:
        self.current_state = self.audio.toggle(self.config.microphone_id)
        self._play_feedback_if_needed("toggle")
        self._refresh_status_ui()
        self._apply_overlay()

    def set_microphone_muted(self, muted: bool, trigger: str, play_feedback: bool = True) -> None:
        previous_state = self.current_state
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

    def show_settings(self) -> None:
        self._ensure_settings_window()
        self._sync_settings_ui()
        self._refresh_status_ui()
        self._sync_overlay_edit_button_state()
        assert self.settings_window is not None
        self.settings_window.deiconify()
        self.settings_window.update_idletasks()
        _apply_appwindow_style(self.settings_window)
        _apply_window_titlebar_theme(self.settings_window, self.config.dark_theme, self._palette())
        self.settings_window.lift()
        self.settings_window.focus_force()
        self.settings_window.after(
            60,
            lambda: (
                _apply_appwindow_style(self.settings_window),
                _apply_window_titlebar_theme(self.settings_window, self.config.dark_theme, self._palette()),
            )
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

    def exit_app(self) -> None:
        if self._overlay_edit_active:
            self._overlay_edit_active = False
            self.overlay.finish_edit(commit=True)
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
