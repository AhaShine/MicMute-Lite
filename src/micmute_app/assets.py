from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import sys

from PIL import Image


if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    PROJECT_ROOT = Path(sys.executable).resolve().parent
    BUNDLED_ROOT = Path(sys._MEIPASS)
else:
    PROJECT_ROOT = Path(__file__).resolve().parents[2]
    BUNDLED_ROOT = PROJECT_ROOT

ASSETS_DIR = PROJECT_ROOT / "assets"
TRAY_DIR = BUNDLED_ROOT / "assets" / "tray"
OVERLAY_DIR = BUNDLED_ROOT / "assets" / "overlay"
APP_DIR = BUNDLED_ROOT / "assets" / "app"
DEFAULT_SOUNDS_DIR = BUNDLED_ROOT / "assets" / "sounds"
CUSTOM_SOUNDS_DIR = PROJECT_ROOT / "sounds"

CUSTOM_SOUND_CANDIDATES = {
    "mute": ("off", "mute"),
    "unmute": ("on", "unmute"),
    "ptt_on": ("ptt_on",),
    "ptt_off": ("ptt_off",),
}
SOUND_EXTENSIONS = (".mp3", ".wav", ".ogg")
BUILTIN_SOUND_FILES = {
    "mute": "mute.wav",
    "unmute": "unmute.wav",
    "ptt_on": "ptt_on.wav",
    "ptt_off": "ptt_off.wav",
}


def get_custom_sound_path(name: str) -> Path | None:
    stems = CUSTOM_SOUND_CANDIDATES.get(name)
    if not stems:
        return None

    for folder in (PROJECT_ROOT, CUSTOM_SOUNDS_DIR):
        if not folder.exists():
            continue
        try:
            items = list(folder.iterdir())
        except OSError:
            continue
        for stem in stems:
            for item in items:
                if item.is_file() and item.stem.lower() == stem.lower() and item.suffix.lower() in SOUND_EXTENSIONS:
                    return item
    return None


def get_builtin_sound_path(name: str) -> Path | None:
    default_file = BUILTIN_SOUND_FILES.get(name)
    if not default_file:
        return None
    default_path = DEFAULT_SOUNDS_DIR / default_file
    if default_path.exists():
        return default_path
    return None


def get_sound_path(name: str) -> Path | None:
    return get_custom_sound_path(name) or get_builtin_sound_path(name)


def get_app_icon_path() -> Path:
    return APP_DIR / "micmute_app.ico"


@lru_cache(maxsize=8)
def load_tray_image(state: str) -> Image.Image:
    mapping = {
        "on": TRAY_DIR / "on.ico",
        "off": TRAY_DIR / "off.ico",
        "error": TRAY_DIR / "error.ico",
    }
    path = mapping.get(state, mapping["error"])
    return Image.open(path).convert("RGBA")


@lru_cache(maxsize=4)
def load_overlay_icon(muted: bool, size: int) -> Image.Image:
    path = OVERLAY_DIR / ("mute.ico" if muted else "unmute.ico")
    icon = Image.open(path).convert("RGBA")
    return icon.resize((size, size), Image.LANCZOS)


@lru_cache(maxsize=8)
def load_app_icon(size: int) -> Image.Image:
    icon = Image.open(get_app_icon_path()).convert("RGBA")
    return icon.resize((size, size), Image.LANCZOS)
