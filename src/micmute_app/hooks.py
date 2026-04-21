from __future__ import annotations

import ctypes
import threading
from ctypes import wintypes
from typing import Callable

from .hotkeys import HotkeySpec, format_hotkey_label, keyboard_display_name, modifier_name_from_vk, mouse_display_name, normalized_modifiers


user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

WH_KEYBOARD_LL = 13
WH_MOUSE_LL = 14
HC_ACTION = 0

WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
WM_MBUTTONDOWN = 0x0207
WM_MBUTTONUP = 0x0208
WM_XBUTTONDOWN = 0x020B
WM_XBUTTONUP = 0x020C
WM_QUIT = 0x0012
XBUTTON1 = 1
XBUTTON2 = 2

ULONG_PTR = wintypes.WPARAM
LRESULT = ctypes.c_longlong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_long


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class POINT(ctypes.Structure):
    _fields_ = [
        ("x", wintypes.LONG),
        ("y", wintypes.LONG),
    ]


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("pt", POINT),
        ("mouseData", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", POINT),
    ]


LowLevelProc = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)

user32.SetWindowsHookExW.argtypes = [ctypes.c_int, LowLevelProc, wintypes.HINSTANCE, wintypes.DWORD]
user32.SetWindowsHookExW.restype = wintypes.HANDLE
user32.CallNextHookEx.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
user32.CallNextHookEx.restype = LRESULT
user32.UnhookWindowsHookEx.argtypes = [wintypes.HANDLE]
user32.UnhookWindowsHookEx.restype = wintypes.BOOL
user32.GetMessageW.argtypes = [ctypes.POINTER(MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
user32.GetMessageW.restype = wintypes.BOOL
user32.TranslateMessage.argtypes = [ctypes.POINTER(MSG)]
user32.TranslateMessage.restype = wintypes.BOOL
user32.DispatchMessageW.argtypes = [ctypes.POINTER(MSG)]
user32.DispatchMessageW.restype = LRESULT
user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.PostThreadMessageW.restype = wintypes.BOOL
kernel32.GetCurrentThreadId.restype = wintypes.DWORD


class GlobalHookManager:
    def __init__(self, event_callback: Callable[[str, HotkeySpec | None], None]) -> None:
        self._event_callback = event_callback
        self._thread: threading.Thread | None = None
        self._thread_id = 0
        self._ready = threading.Event()
        self._lock = threading.RLock()
        self._keyboard_hook = None
        self._mouse_hook = None
        self._keyboard_proc = LowLevelProc(self._keyboard_callback)
        self._mouse_proc = LowLevelProc(self._mouse_callback)
        self._hotkey: HotkeySpec | None = None
        self._suppress_hotkey = True
        self._pressed_modifiers: set[str] = set()
        self._active = False
        self._active_main: tuple[str, int] | None = None
        self._active_modifiers: tuple[str, ...] = ()
        self._capture_enabled = False

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run_loop, name="MicMuteHooks", daemon=True)
        self._thread.start()
        self._ready.wait(timeout=5)

    def stop(self) -> None:
        if not self._thread_id:
            return
        user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
        if self._thread:
            self._thread.join(timeout=2)
        self._thread = None
        self._thread_id = 0

    def set_hotkey(self, hotkey: HotkeySpec | None, suppress_hotkey: bool) -> None:
        with self._lock:
            self._hotkey = hotkey
            self._suppress_hotkey = suppress_hotkey
            self._active = False
            self._active_main = None
            self._active_modifiers = ()

    def begin_capture(self) -> None:
        with self._lock:
            self._capture_enabled = True

    def cancel_capture(self) -> None:
        with self._lock:
            self._capture_enabled = False

    def _run_loop(self) -> None:
        self._thread_id = kernel32.GetCurrentThreadId()
        self._keyboard_hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._keyboard_proc, 0, 0)
        self._mouse_hook = user32.SetWindowsHookExW(WH_MOUSE_LL, self._mouse_proc, 0, 0)
        self._ready.set()

        message = MSG()
        while user32.GetMessageW(ctypes.byref(message), 0, 0, 0) != 0:
            user32.TranslateMessage(ctypes.byref(message))
            user32.DispatchMessageW(ctypes.byref(message))

        if self._keyboard_hook:
            user32.UnhookWindowsHookEx(self._keyboard_hook)
            self._keyboard_hook = None
        if self._mouse_hook:
            user32.UnhookWindowsHookEx(self._mouse_hook)
            self._mouse_hook = None

    def _keyboard_callback(self, code: int, wparam: int, lparam: int) -> int:
        if code != HC_ACTION:
            return user32.CallNextHookEx(self._keyboard_hook, code, wparam, lparam)

        info = ctypes.cast(lparam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
        handled = False
        if wparam in (WM_KEYDOWN, WM_SYSKEYDOWN):
            handled = self._handle_keyboard_event(info, True)
        elif wparam in (WM_KEYUP, WM_SYSKEYUP):
            handled = self._handle_keyboard_event(info, False)

        if handled:
            return 1
        return user32.CallNextHookEx(self._keyboard_hook, code, wparam, lparam)

    def _mouse_callback(self, code: int, wparam: int, lparam: int) -> int:
        if code != HC_ACTION:
            return user32.CallNextHookEx(self._mouse_hook, code, wparam, lparam)

        info = ctypes.cast(lparam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
        handled = self._handle_mouse_event(wparam, info)
        if handled:
            return 1
        return user32.CallNextHookEx(self._mouse_hook, code, wparam, lparam)

    def _handle_keyboard_event(self, info: KBDLLHOOKSTRUCT, is_down: bool) -> bool:
        vk_code = int(info.vkCode)
        modifier = modifier_name_from_vk(vk_code)

        with self._lock:
            if modifier:
                if is_down:
                    self._pressed_modifiers.add(modifier)
                else:
                    self._pressed_modifiers.discard(modifier)
                    if self._active and modifier in self._active_modifiers:
                        self._finish_active_hotkey()
                return False

            if is_down and self._capture_enabled:
                modifiers = normalized_modifiers(self._pressed_modifiers)
                display = keyboard_display_name(vk_code, int(info.scanCode), bool(info.flags & 0x01))
                self._capture_enabled = False
                self._emit(
                    "capture",
                    HotkeySpec(kind="keyboard", code=vk_code, modifiers=modifiers, display=display),
                )
                return True

            return self._process_hotkey_event("keyboard", vk_code, is_down)

    def _handle_mouse_event(self, message: int, info: MSLLHOOKSTRUCT) -> bool:
        button_code: int | None = None
        is_down = False
        is_up = False

        if message == WM_LBUTTONDOWN:
            button_code, is_down = 1, True
        elif message == WM_LBUTTONUP:
            button_code, is_up = 1, True
        elif message == WM_RBUTTONDOWN:
            button_code, is_down = 2, True
        elif message == WM_RBUTTONUP:
            button_code, is_up = 2, True
        elif message == WM_MBUTTONDOWN:
            button_code, is_down = 3, True
        elif message == WM_MBUTTONUP:
            button_code, is_up = 3, True
        elif message == WM_XBUTTONDOWN:
            xbutton = (info.mouseData >> 16) & 0xFFFF
            button_code, is_down = (4 if xbutton == XBUTTON1 else 5), True
        elif message == WM_XBUTTONUP:
            xbutton = (info.mouseData >> 16) & 0xFFFF
            button_code, is_up = (4 if xbutton == XBUTTON1 else 5), True

        if button_code is None:
            return False

        with self._lock:
            if is_down and self._capture_enabled:
                modifiers = normalized_modifiers(self._pressed_modifiers)
                self._capture_enabled = False
                self._emit(
                    "capture",
                    HotkeySpec(kind="mouse", code=button_code, modifiers=modifiers, display=mouse_display_name(button_code)),
                )
                return True

            if is_down:
                return self._process_hotkey_event("mouse", button_code, True)
            if is_up:
                return self._process_hotkey_event("mouse", button_code, False)
            return False

    def _process_hotkey_event(self, kind: str, code: int, is_down: bool) -> bool:
        current_hotkey = self._hotkey
        if current_hotkey is None:
            return False

        current_modifiers = normalized_modifiers(self._pressed_modifiers)
        suppress = self._suppress_hotkey
        main_identity = (kind, code)

        if is_down:
            if self._active and self._active_main == main_identity:
                return suppress

            if current_hotkey.kind == kind and current_hotkey.code == code and current_hotkey.modifiers == current_modifiers:
                self._active = True
                self._active_main = main_identity
                self._active_modifiers = current_hotkey.modifiers
                self._emit("hotkey_down", current_hotkey)
                return suppress
            return False

        if self._active and self._active_main == main_identity:
            self._finish_active_hotkey()
            return suppress
        return False

    def _finish_active_hotkey(self) -> None:
        hotkey = self._hotkey
        self._active = False
        self._active_main = None
        self._active_modifiers = ()
        self._emit("hotkey_up", hotkey)

    def _emit(self, event_name: str, hotkey: HotkeySpec | None) -> None:
        self._event_callback(event_name, hotkey)
