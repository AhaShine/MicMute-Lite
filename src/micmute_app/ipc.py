from __future__ import annotations

import socket
import threading
import time
from typing import Callable


APP_PORT = 45873
APP_HOST = "127.0.0.1"
SHOW_COMMAND = b"show-settings"


class SingleInstanceBridge:
    def __init__(self, on_show_settings: Callable[[], None]) -> None:
        self._on_show_settings = on_show_settings
        self._socket: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def start_or_signal_existing(self) -> bool:
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        exclusive_opt = getattr(socket, "SO_EXCLUSIVEADDRUSE", None)
        if exclusive_opt is not None:
            listener.setsockopt(socket.SOL_SOCKET, exclusive_opt, 1)
        try:
            listener.bind((APP_HOST, APP_PORT))
            listener.listen(5)
        except OSError:
            listener.close()
            self.signal_existing()
            return False

        self._socket = listener
        self._thread = threading.Thread(target=self._serve, name="MicMuteIpc", daemon=True)
        self._thread.start()
        return True

    def signal_existing(self) -> None:
        for _attempt in range(6):
            try:
                with socket.create_connection((APP_HOST, APP_PORT), timeout=1) as client:
                    client.sendall(SHOW_COMMAND)
                    return
            except OSError:
                time.sleep(0.12)

    def stop(self) -> None:
        self._stop.set()
        if self._socket is not None:
            try:
                self._socket.close()
            except OSError:
                pass
            self._socket = None
        if self._thread is not None:
            self._thread.join(timeout=1)
            self._thread = None

    def _serve(self) -> None:
        assert self._socket is not None
        while not self._stop.is_set():
            try:
                self._socket.settimeout(0.5)
                conn, _addr = self._socket.accept()
            except (OSError, TimeoutError):
                continue

            with conn:
                try:
                    payload = conn.recv(128)
                except OSError:
                    payload = b""
                if payload == SHOW_COMMAND:
                    self._on_show_settings()
