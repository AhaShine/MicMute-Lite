from __future__ import annotations

import ctypes
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
import sys
from typing import Any
import winreg

from .hotkeys import HotkeySpec, deserialize_hotkey, serialize_hotkey


if getattr(sys, "frozen", False):
    PROJECT_ROOT = Path(sys.executable).resolve().parent
else:
    PROJECT_ROOT = Path(__file__).resolve().parents[2]

ROAMING_DIR = Path(os.getenv("APPDATA", str(Path.home() / "AppData" / "Roaming")))
APPDATA_DIR = ROAMING_DIR / "MicMute"
CONFIG_PATH = APPDATA_DIR / "config.json"
OLD_APPDATA_CONFIG_PATH = ROAMING_DIR / "MicMute Lite" / "config.json"
LEGACY_CONFIG_PATH = PROJECT_ROOT / "config.json"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE_NAME = "MicMute Lite"


def detect_default_language() -> str:
    try:
        lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        primary_language = lang_id & 0x3FF
    except (AttributeError, OSError):
        return "en"
    return "ru" if primary_language == 0x19 else "en"


def application_command(background: bool = False) -> str:
    if getattr(sys, "frozen", False):
        command = f'"{Path(sys.executable).resolve()}"'
        return f"{command} --background" if background else command
    python = Path(sys.executable).resolve()
    pythonw = python.with_name("pythonw.exe")
    if pythonw.exists():
        python = pythonw
    command = f'"{python}" "{PROJECT_ROOT / "main.py"}"'
    return f"{command} --background" if background else command


def set_autostart(enabled: bool) -> None:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, RUN_VALUE_NAME, 0, winreg.REG_SZ, application_command(background=True))
        else:
            try:
                winreg.DeleteValue(key, RUN_VALUE_NAME)
            except FileNotFoundError:
                pass


def autostart_enabled() -> bool:
    expected = application_command(background=True).strip()
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ) as key:
            value, _kind = winreg.QueryValueEx(key, RUN_VALUE_NAME)
    except FileNotFoundError:
        return False
    return str(value).strip().lower() == expected.lower()


@dataclass
class AppConfig:
    microphone_id: str = ""
    mode: str = "toggle"
    hotkey: HotkeySpec | None = None
    language: str = field(default_factory=detect_default_language)
    suppress_hotkey: bool = False
    sounds_enabled: bool = True
    autostart: bool = False
    overlay_enabled: bool = True
    overlay_position_x: float = 0.88
    overlay_position_y: float = 0.1
    overlay_scale: float = 1.0

    @classmethod
    def default(cls) -> "AppConfig":
        return cls(hotkey=None)


class ConfigStore:
    def __init__(self, path: Path = CONFIG_PATH) -> None:
        self.path = path

    def load(self) -> AppConfig:
        config = AppConfig.default()
        source_path = self.path
        for fallback_path in (OLD_APPDATA_CONFIG_PATH, LEGACY_CONFIG_PATH):
            if not source_path.exists() and fallback_path.exists():
                source_path = fallback_path
        if not source_path.exists():
            config.autostart = autostart_enabled()
            return config

        try:
            data = json.loads(source_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            config.autostart = autostart_enabled()
            return config

        config.microphone_id = str(data.get("microphone_id", config.microphone_id))
        config.mode = self._sanitize_mode(data.get("mode", config.mode))
        config.hotkey = deserialize_hotkey(data.get("hotkey")) or config.hotkey
        config.language = self._sanitize_language(data.get("language", config.language))
        config.suppress_hotkey = bool(data.get("suppress_hotkey", config.suppress_hotkey))
        config.sounds_enabled = bool(data.get("sounds_enabled", config.sounds_enabled))
        config.autostart = bool(data.get("autostart", autostart_enabled()))
        config.overlay_enabled = bool(data.get("overlay_enabled", config.overlay_enabled))
        config.overlay_position_x = self._clamp_float(data.get("overlay_position_x", config.overlay_position_x), 0.0, 1.0)
        config.overlay_position_y = self._clamp_float(data.get("overlay_position_y", config.overlay_position_y), 0.0, 1.0)
        config.overlay_scale = self._clamp_float(data.get("overlay_scale", config.overlay_scale), 0.6, 2.2)
        if source_path != self.path:
            self.save(config)
        return config

    def save(self, config: AppConfig) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = {
            "microphone_id": config.microphone_id,
            "mode": self._sanitize_mode(config.mode),
            "hotkey": serialize_hotkey(config.hotkey),
            "language": self._sanitize_language(config.language),
            "suppress_hotkey": bool(config.suppress_hotkey),
            "sounds_enabled": bool(config.sounds_enabled),
            "autostart": bool(config.autostart),
            "overlay_enabled": bool(config.overlay_enabled),
            "overlay_position_x": round(config.overlay_position_x, 3),
            "overlay_position_y": round(config.overlay_position_y, 3),
            "overlay_scale": round(config.overlay_scale, 3),
        }
        self.path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    @staticmethod
    def _sanitize_mode(value: Any) -> str:
        mode = str(value).strip().lower()
        if mode in {"toggle", "push_to_talk", "push_to_mute"}:
            return mode
        return "toggle"

    @staticmethod
    def _sanitize_language(value: Any) -> str:
        language = str(value).strip().lower()
        if language in {"ru", "en"}:
            return language
        return detect_default_language()

    @staticmethod
    def _clamp_float(value: Any, minimum: float, maximum: float) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return minimum
        return max(minimum, min(maximum, number))
