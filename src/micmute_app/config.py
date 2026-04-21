from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Any

from .hotkeys import HotkeySpec, deserialize_hotkey, serialize_hotkey


if getattr(sys, "frozen", False):
    PROJECT_ROOT = Path(sys.executable).resolve().parent
else:
    PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "config.json"


@dataclass
class AppConfig:
    microphone_id: str = ""
    mode: str = "toggle"
    hotkey: HotkeySpec | None = None
    language: str = "ru"
    dark_theme: bool = True
    suppress_hotkey: bool = True
    sounds_enabled: bool = True
    overlay_enabled: bool = True
    overlay_position_x: float = 0.88
    overlay_position_y: float = 0.1
    overlay_scale: float = 1.0
    start_minimized: bool = False

    @classmethod
    def default(cls) -> "AppConfig":
        return cls(hotkey=None)


class ConfigStore:
    def __init__(self, path: Path = CONFIG_PATH) -> None:
        self.path = path

    def load(self) -> AppConfig:
        config = AppConfig.default()
        if not self.path.exists():
            return config

        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return config

        config.microphone_id = str(data.get("microphone_id", config.microphone_id))
        config.mode = self._sanitize_mode(data.get("mode", config.mode))
        config.hotkey = deserialize_hotkey(data.get("hotkey")) or config.hotkey
        config.language = self._sanitize_language(data.get("language", config.language))
        config.dark_theme = bool(data.get("dark_theme", config.dark_theme))
        config.suppress_hotkey = bool(data.get("suppress_hotkey", config.suppress_hotkey))
        config.sounds_enabled = bool(data.get("sounds_enabled", config.sounds_enabled))
        config.overlay_enabled = bool(data.get("overlay_enabled", config.overlay_enabled))
        config.overlay_position_x = self._clamp_float(data.get("overlay_position_x", config.overlay_position_x), 0.0, 1.0)
        config.overlay_position_y = self._clamp_float(data.get("overlay_position_y", config.overlay_position_y), 0.0, 1.0)
        config.overlay_scale = self._clamp_float(data.get("overlay_scale", config.overlay_scale), 0.6, 2.2)
        config.start_minimized = bool(data.get("start_minimized", config.start_minimized))
        return config

    def save(self, config: AppConfig) -> None:
        payload: dict[str, Any] = {
            "microphone_id": config.microphone_id,
            "mode": self._sanitize_mode(config.mode),
            "hotkey": serialize_hotkey(config.hotkey),
            "language": self._sanitize_language(config.language),
            "dark_theme": bool(config.dark_theme),
            "suppress_hotkey": bool(config.suppress_hotkey),
            "sounds_enabled": bool(config.sounds_enabled),
            "overlay_enabled": bool(config.overlay_enabled),
            "overlay_position_x": round(config.overlay_position_x, 3),
            "overlay_position_y": round(config.overlay_position_y, 3),
            "overlay_scale": round(config.overlay_scale, 3),
            "start_minimized": bool(config.start_minimized),
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
        return "ru"

    @staticmethod
    def _clamp_float(value: Any, minimum: float, maximum: float) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return minimum
        return max(minimum, min(maximum, number))
