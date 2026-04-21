from __future__ import annotations

import ctypes
from dataclasses import dataclass
from typing import Any


user32 = ctypes.windll.user32
user32.GetKeyNameTextW.argtypes = [ctypes.c_long, ctypes.c_wchar_p, ctypes.c_int]
user32.GetKeyNameTextW.restype = ctypes.c_int

MODIFIER_ORDER = ("Ctrl", "Alt", "Shift", "Win")
MOUSE_NAMES = {
    1: "MouseLeft",
    2: "MouseRight",
    3: "MouseMiddle",
    4: "Mouse4",
    5: "Mouse5",
}
VK_NAME_OVERRIDES = {
    0x08: "Backspace",
    0x09: "Tab",
    0x0D: "Enter",
    0x1B: "Esc",
    0x20: "Space",
    0x21: "Page Up",
    0x22: "Page Down",
    0x23: "End",
    0x24: "Home",
    0x25: "Left",
    0x26: "Up",
    0x27: "Right",
    0x28: "Down",
    0x2D: "Insert",
    0x2E: "Delete",
    0x5B: "Win",
    0x5C: "Win",
    0x90: "Num Lock",
    0x91: "Scroll Lock",
    0xA0: "Shift",
    0xA1: "Shift",
    0xA2: "Ctrl",
    0xA3: "Ctrl",
    0xA4: "Alt",
    0xA5: "Alt",
}
MODIFIER_VKS = {
    0xA0: "Shift",
    0xA1: "Shift",
    0xA2: "Ctrl",
    0xA3: "Ctrl",
    0xA4: "Alt",
    0xA5: "Alt",
    0x5B: "Win",
    0x5C: "Win",
}


@dataclass(frozen=True)
class HotkeySpec:
    kind: str
    code: int
    modifiers: tuple[str, ...]
    display: str

    @property
    def label(self) -> str:
        if not self.display:
            return "Не назначено"
        return format_hotkey_label(self.display, self.modifiers)


def modifier_name_from_vk(vk_code: int) -> str | None:
    return MODIFIER_VKS.get(vk_code)


def normalized_modifiers(modifiers: list[str] | tuple[str, ...] | set[str]) -> tuple[str, ...]:
    values = {modifier for modifier in modifiers if modifier in MODIFIER_ORDER}
    return tuple(modifier for modifier in MODIFIER_ORDER if modifier in values)


def format_hotkey_label(main_display: str, modifiers: list[str] | tuple[str, ...]) -> str:
    if not main_display:
        return "Не назначено"
    ordered = list(normalized_modifiers(tuple(modifiers)))
    ordered.append(main_display)
    return " + ".join(ordered)


def keyboard_display_name(vk_code: int, scan_code: int = 0, extended: bool = False) -> str:
    override = VK_NAME_OVERRIDES.get(vk_code)
    if override:
        return override

    lparam = scan_code << 16
    if extended:
        lparam |= 1 << 24

    buffer = ctypes.create_unicode_buffer(64)
    result = user32.GetKeyNameTextW(lparam, buffer, len(buffer))
    if result:
        value = buffer.value.strip()
        if len(value) == 1:
            return value.upper()
        return value.title()

    if 0x70 <= vk_code <= 0x87:
        return f"F{vk_code - 0x6F}"
    if 0x30 <= vk_code <= 0x39 or 0x41 <= vk_code <= 0x5A:
        return chr(vk_code)
    return f"VK {vk_code}"


def mouse_display_name(code: int) -> str:
    return MOUSE_NAMES.get(code, f"Mouse{code}")


def serialize_hotkey(spec: HotkeySpec | None) -> dict[str, Any] | None:
    if spec is None:
        return None
    return {
        "kind": spec.kind,
        "code": spec.code,
        "modifiers": list(spec.modifiers),
        "display": spec.display,
    }


def deserialize_hotkey(data: dict[str, Any] | None) -> HotkeySpec | None:
    if not data:
        return None
    kind = str(data.get("kind", "keyboard"))
    code = int(data.get("code", 0))
    display = str(data.get("display", "")).strip()
    modifiers = normalized_modifiers(tuple(data.get("modifiers", [])))
    if kind not in {"keyboard", "mouse"} or code <= 0:
        return None
    if not display:
        display = keyboard_display_name(code) if kind == "keyboard" else mouse_display_name(code)
    return HotkeySpec(kind=kind, code=code, modifiers=modifiers, display=display)
