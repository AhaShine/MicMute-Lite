from __future__ import annotations

import ctypes
import queue
import threading
from ctypes import wintypes
from typing import Callable

import pystray
from pystray._util import win32

from . import APP_NAME
from .assets import load_tray_image


user32 = ctypes.windll.user32
VK_SHIFT = 0x10


def _shift_pressed() -> bool:
    return bool(user32.GetAsyncKeyState(VK_SHIFT) & 0x8000)


class DarkMenuTrayIcon(pystray.Icon):
    def __init__(self, *args, command_queue: queue.Queue[tuple[str, object | None]], **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._command_queue = command_queue
        self._custom_menu_active = False

    def _run_detached(self):
        threading.Thread(target=self._run, name="MicMuteTray", daemon=True).start()

    def _on_notify(self, wparam, lparam):
        if lparam == win32.WM_LBUTTONUP:
            if self._custom_menu_active:
                return
            if _shift_pressed():
                self._command_queue.put(("show_settings", None))
            else:
                self._command_queue.put(("toggle_microphone", None))
            return

        if lparam == win32.WM_RBUTTONUP:
            point = wintypes.POINT()
            user32.GetCursorPos(ctypes.byref(point))
            self._command_queue.put(("show_tray_menu", (point.x, point.y)))

    def set_custom_menu_active(self, active: bool) -> None:
        self._custom_menu_active = active


class TrayController:
    def __init__(
        self,
        command_queue: queue.Queue[tuple[str, object | None]],
        text_provider: Callable[[str], str],
    ) -> None:
        self.command_queue = command_queue
        self._text = text_provider
        self.icon: pystray.Icon | None = None
        self.is_muted = True
        self.overlay_enabled = True
        self.mic_name = ""
        self.is_available = True

    def start(self, is_muted: bool, overlay_enabled: bool, mic_name: str, is_available: bool) -> None:
        if self.icon is not None:
            return

        self.is_muted = is_muted
        self.overlay_enabled = overlay_enabled
        self.mic_name = mic_name
        self.is_available = is_available

        menu = pystray.Menu(pystray.MenuItem(self._toggle_text, self._send_toggle_mic, default=True, visible=False))
        self.icon = DarkMenuTrayIcon(APP_NAME, self._current_image(), APP_NAME, menu, command_queue=self.command_queue)
        self.icon.run_detached()

    def update_state(self, is_muted: bool, overlay_enabled: bool, mic_name: str, is_available: bool) -> None:
        self.is_muted = is_muted
        self.overlay_enabled = overlay_enabled
        self.mic_name = mic_name
        self.is_available = is_available
        if self.icon is None:
            return
        self.icon.icon = self._current_image()
        self.icon.title = self._title_text()
        self.icon.update_menu()

    def set_language(self) -> None:
        if self.icon is None:
            return
        self.icon.title = self._title_text()
        self.icon.update_menu()

    def set_custom_menu_active(self, active: bool) -> None:
        if isinstance(self.icon, DarkMenuTrayIcon):
            self.icon.set_custom_menu_active(active)

    def stop(self) -> None:
        if self.icon is None:
            return
        self.icon.stop()
        self.icon = None

    def _current_image(self):
        if not self.is_available:
            return load_tray_image("error")
        return load_tray_image("off" if self.is_muted else "on")

    def _title_text(self) -> str:
        if not self.is_available:
            state_text = self._text("tray_state_unavailable")
        else:
            state_text = self._text("tray_state_off" if self.is_muted else "tray_state_on")
        return f"{APP_NAME}\n{self.mic_name}\n{self._text('tray_mic_label')}: {state_text}"

    def _settings_text(self, _item: pystray.MenuItem) -> str:
        return self._text("tray_settings")

    def _exit_text(self, _item: pystray.MenuItem) -> str:
        return self._text("tray_exit")

    def _send_show_settings(self, _icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        self.command_queue.put(("show_settings", None))

    def _send_toggle_mic(self, _icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        if _shift_pressed():
            self.command_queue.put(("show_settings", None))
            return
        self.command_queue.put(("toggle_microphone", None))

    def _send_exit(self, _icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        self.command_queue.put(("exit", None))

    def _toggle_text(self, _item: pystray.MenuItem) -> str:
        if not self.is_available:
            return self._text("tray_toggle_unavailable")
        return self._text("tray_toggle_off" if self.is_muted else "tray_toggle_on")
