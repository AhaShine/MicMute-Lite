from __future__ import annotations

import ctypes
from ctypes import wintypes


def enable_dpi_awareness() -> None:
    """Keep Tk windows and overlay sizing consistent on Windows 10 and 11."""
    try:
        user32 = ctypes.windll.user32
        if hasattr(user32, "SetProcessDpiAwarenessContext"):
            user32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
            user32.SetProcessDpiAwarenessContext.restype = wintypes.BOOL
            # PER_MONITOR_AWARE_V2 is available on modern Windows 10 builds and Windows 11.
            if user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
                return
    except (AttributeError, OSError, ValueError):
        pass

    try:
        shcore = ctypes.windll.shcore
        shcore.SetProcessDpiAwareness.argtypes = [ctypes.c_int]
        shcore.SetProcessDpiAwareness.restype = ctypes.c_long
        if shcore.SetProcessDpiAwareness(2) == 0:
            return
    except (AttributeError, OSError, ValueError):
        pass

    try:
        ctypes.windll.user32.SetProcessDPIAware.argtypes = []
        ctypes.windll.user32.SetProcessDPIAware.restype = wintypes.BOOL
        ctypes.windll.user32.SetProcessDPIAware()
    except (AttributeError, OSError, ValueError):
        pass
