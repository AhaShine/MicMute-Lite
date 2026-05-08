from __future__ import annotations

import ctypes
import os
from pathlib import Path
import subprocess
import sys
import time
from ctypes import wintypes

from .audio import MicrophoneService


SYNCHRONIZE = 0x00100000
INFINITE = 0xFFFFFFFF
DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_NO_WINDOW = 0x08000000
SW_HIDE = 0
UNMUTE_ATTEMPTS = 12
UNMUTE_RETRY_SECONDS = 0.25

kernel32 = ctypes.windll.kernel32
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
kernel32.WaitForSingleObject.restype = wintypes.DWORD
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL
kernel32.LocalFree.argtypes = [ctypes.c_void_p]
kernel32.LocalFree.restype = ctypes.c_void_p

shell32 = ctypes.windll.shell32
shell32.ShellExecuteW.argtypes = [
    wintypes.HWND,
    ctypes.c_wchar_p,
    ctypes.c_wchar_p,
    ctypes.c_wchar_p,
    ctypes.c_wchar_p,
    ctypes.c_int,
]
shell32.ShellExecuteW.restype = wintypes.HINSTANCE
shell32.CommandLineToArgvW.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_int)]
shell32.CommandLineToArgvW.restype = ctypes.POINTER(ctypes.c_wchar_p)


def start_guardian(device_id: str) -> bool:
    """Start a tiny companion process that unmutes the selected mic if this process dies."""
    executable, arguments = _guardian_command(os.getpid(), device_id)
    return _launch_hidden(executable, arguments) or _launch_detached(executable, arguments)


def guardian_main(parent_pid: int, device_id: str) -> int:
    _wait_for_process_exit(parent_pid)
    _unmute_with_retries(device_id)
    return 0


def _guardian_command(parent_pid: int, device_id: str) -> tuple[str, str]:
    args = ["--guardian", str(parent_pid), "--guardian-device-id", device_id]
    if getattr(sys, "frozen", False):
        return str(Path(sys.executable).resolve()), subprocess.list2cmdline(args)

    root = Path(__file__).resolve().parents[2]
    python = _pythonw_or_current()
    return str(python), subprocess.list2cmdline([str(root / "main.py"), *args])


def _pythonw_or_current() -> Path:
    python = Path(sys.executable).resolve()
    pythonw = python.with_name("pythonw.exe")
    return pythonw if pythonw.exists() else python


def _launch_hidden(executable: str, arguments: str) -> bool:
    try:
        return int(shell32.ShellExecuteW(None, "open", executable, arguments, None, SW_HIDE)) > 32
    except OSError:
        return False


def _launch_detached(executable: str, arguments: str) -> bool:
    command = [executable, *_split_windows_args(arguments)]
    creationflags = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW
    try:
        subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            creationflags=creationflags,
        )
        return True
    except OSError:
        return False


def _split_windows_args(arguments: str) -> list[str]:
    argc = ctypes.c_int(0)
    argv = shell32.CommandLineToArgvW(arguments, ctypes.byref(argc))
    if not argv:
        return [arguments] if arguments else []
    try:
        return [argv[index] for index in range(argc.value)]
    finally:
        kernel32.LocalFree(argv)


def _wait_for_process_exit(pid: int) -> None:
    handle = kernel32.OpenProcess(SYNCHRONIZE, False, wintypes.DWORD(pid))
    if not handle:
        return
    try:
        kernel32.WaitForSingleObject(handle, INFINITE)
    finally:
        kernel32.CloseHandle(handle)


def _unmute_with_retries(device_id: str) -> None:
    service = MicrophoneService()
    for _attempt in range(UNMUTE_ATTEMPTS):
        try:
            state = service.get_state(device_id)
            if not state.is_available or not state.is_muted:
                return
            after = service.set_muted(device_id, False)
            if after.is_available and not after.is_muted:
                return
        except Exception:
            pass
        time.sleep(UNMUTE_RETRY_SECONDS)
