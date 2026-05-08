from __future__ import annotations

import argparse

from .audio import MicrophoneService
from .guardian import guardian_main
from .ui import MicMuteApp


def main() -> int:
    parser = argparse.ArgumentParser(description="MicMute Lite")
    parser.add_argument("--self-test", action="store_true", help="Check microphone access without opening the UI.")
    parser.add_argument("--background", action="store_true", help="Start minimized to tray, used by Windows autostart.")
    parser.add_argument("--guardian", type=int, default=0, help=argparse.SUPPRESS)
    parser.add_argument("--guardian-device-id", default="", help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.guardian:
        return guardian_main(args.guardian, args.guardian_device_id)

    if args.self_test:
        service = MicrophoneService()
        devices = service.list_devices()
        state = service.get_state("")
        print("Detected microphones:")
        for device in devices:
            marker = "*" if device.is_default else " "
            print(f"{marker} {device.name} :: {device.id}")
        print()
        print(f"Current state: {'muted' if state.is_muted else 'live'}")
        print(f"Selected name: {state.name}")
        return 0

    app = MicMuteApp(start_hidden=args.background)
    if getattr(app, "should_exit_immediately", False):
        return 0
    app.run()
    return 0
