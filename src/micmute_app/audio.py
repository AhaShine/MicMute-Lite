from __future__ import annotations

import ctypes
import itertools
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import comtypes
from pycaw.pycaw import AudioUtilities, DEVICE_STATE, EDataFlow

from .assets import get_builtin_sound_path, get_custom_sound_path, get_sound_path


UNAVAILABLE_MICROPHONE_NAME = "Microphone unavailable"


@dataclass(frozen=True)
class MicrophoneInfo:
    id: str
    name: str
    is_default: bool = False


@dataclass(frozen=True)
class MicrophoneState:
    id: str
    name: str
    is_muted: bool
    is_available: bool
    is_default: bool


@contextmanager
def _com_context():
    comtypes.CoInitialize()
    try:
        yield
    finally:
        try:
            comtypes.CoUninitialize()
        except OSError:
            pass


class MicrophoneService:
    def list_devices(self) -> list[MicrophoneInfo]:
        with _com_context():
            default_device = _default_capture_device()
            devices = AudioUtilities.GetAllDevices(EDataFlow.eCapture.value, DEVICE_STATE.ACTIVE.value)
            results: list[MicrophoneInfo] = []
            for device in devices:
                results.append(
                    MicrophoneInfo(
                        id=device.id,
                        name=device.FriendlyName,
                        is_default=device.id == default_device.id,
                    )
                )
            results.sort(key=lambda item: (not item.is_default, item.name.lower()))
            return results

    def get_state(self, device_id: str) -> MicrophoneState:
        with _com_context():
            default_device = _default_capture_device()
            device = self._resolve_device(device_id, default_device)
            if device is None:
                return _unavailable_state()
            return MicrophoneState(
                id=device.id,
                name=device.FriendlyName,
                is_muted=bool(device.EndpointVolume.GetMute()),
                is_available=True,
                is_default=device.id == default_device.id,
            )

    def set_muted(self, device_id: str, muted: bool) -> MicrophoneState:
        with _com_context():
            default_device = _default_capture_device()
            device = self._resolve_device(device_id, default_device)
            if device is None:
                return _unavailable_state()
            device.EndpointVolume.SetMute(bool(muted), None)
            return MicrophoneState(
                id=device.id,
                name=device.FriendlyName,
                is_muted=bool(device.EndpointVolume.GetMute()),
                is_available=True,
                is_default=device.id == default_device.id,
            )

    def toggle(self, device_id: str) -> MicrophoneState:
        state = self.get_state(device_id)
        if not state.is_available:
            return state
        return self.set_muted(device_id, not state.is_muted)

    def _resolve_device(self, device_id: str, default_device):
        if not device_id:
            return default_device
        devices = AudioUtilities.GetAllDevices(EDataFlow.eCapture.value, DEVICE_STATE.ACTIVE.value)
        for device in devices:
            if device.id == device_id:
                return device
        return default_device


def _default_capture_device():
    return AudioUtilities.CreateDevice(AudioUtilities.GetMicrophone())


def _unavailable_state() -> MicrophoneState:
    return MicrophoneState(
        id="",
        name=UNAVAILABLE_MICROPHONE_NAME,
        is_muted=True,
        is_available=False,
        is_default=True,
    )


class SoundService:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._alias_counter = itertools.count(1)
        self._active_aliases: set[str] = set()
        self._winmm = ctypes.windll.winmm
        self._winmm.mciSendStringW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_void_p]
        self._winmm.mciSendStringW.restype = ctypes.c_uint

    def play(self, sound_name: str) -> None:
        sound_path = get_sound_path(sound_name)
        if sound_path is None:
            return

        candidates = []
        custom_path = get_custom_sound_path(sound_name)
        builtin_path = get_builtin_sound_path(sound_name)
        if custom_path is not None:
            candidates.append(custom_path)
        if builtin_path is not None and builtin_path not in candidates:
            candidates.append(builtin_path)
        if not candidates:
            candidates.append(sound_path)

        for candidate in candidates:
            if candidate.exists() and self._try_play(candidate):
                return

    def _try_play(self, sound_path: Path) -> bool:
        if sound_path.suffix.lower() in {".mp3", ".wav"}:
            return self._play_mci(sound_path)
        return False

    def _play_mci(self, sound_path: Path) -> bool:
        with self._lock:
            alias = f"micmute_sound_{next(self._alias_counter)}"
            safe_path = str(sound_path).replace('"', '""')
            sound_type = "mpegvideo" if sound_path.suffix.lower() == ".mp3" else "waveaudio"
            if self._mci(f'open "{safe_path}" type {sound_type} alias {alias}') != 0:
                return False
            if self._mci(f"play {alias} from 0") != 0:
                self._mci(f"close {alias}")
                return False
            self._active_aliases.add(alias)
            threading.Thread(target=self._close_when_finished, args=(alias,), daemon=True).start()
            return True

    def _close_when_finished(self, alias: str) -> None:
        length_ms = self._sound_length(alias)
        time.sleep(max(0.2, length_ms / 1000 + 0.35))
        with self._lock:
            self._mci(f"close {alias}")
            self._active_aliases.discard(alias)

    def _sound_length(self, alias: str) -> int:
        buffer = ctypes.create_unicode_buffer(64)
        if int(self._winmm.mciSendStringW(f"status {alias} length", buffer, len(buffer), None)) != 0:
            return 1000
        try:
            return int(buffer.value)
        except ValueError:
            return 1000

    def _mci(self, command: str) -> int:
        return int(self._winmm.mciSendStringW(command, None, 0, None))
