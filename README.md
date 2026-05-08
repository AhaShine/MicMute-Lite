# MicMute Lite

MicMute Lite is a compact Windows tray app for controlling microphone mute state with keyboard or mouse hotkeys.

It is built for Windows 10 and Windows 11, with a small settings window, tray controls, optional on-screen overlay, and custom on/off sounds.

## Features

- Tray-first workflow: left click toggles the microphone, right click opens the menu, `Shift + left click` opens settings.
- Hotkey modes: `toggle`, `push-to-talk`, and `push-to-mute`.
- Keyboard and mouse bindings, including side mouse buttons (`Mouse4`, `Mouse5`).
- Optional overlay with movable/resizable microphone state indicator.
- Built-in on/off sounds plus custom `on.mp3`, `off.mp3`, `on.wav`, or `off.wav` next to the exe.
- Autostart through the current user's Windows Run key.
- Single-instance behavior: launching the exe again focuses the existing settings window.
- Safety guardian: if the main app process dies while the mic is muted, a helper process tries to unmute it.

## Windows Compatibility

The app uses Windows Core Audio through `pycaw`, low-level keyboard/mouse hooks through WinAPI, and Tk for the settings UI. It has compatibility fallbacks for:

- Windows 11 and modern Windows 10 dark title bars.
- Older Windows 10 dark-titlebar attributes.
- Per-monitor DPI awareness, with fallbacks for older Windows builds.
- Normal process exit, tray exit, and typical Task Manager "End task" behavior.

One hard limitation: if every MicMute Lite process is force-killed, including the guardian helper or the whole process tree, no remaining code can unmute the microphone. Covering that case would require installing a separate Windows service or scheduled watchdog.

## Quick Start

Run from source:

```bat
run.bat
```

Build a standalone exe:

```bat
build.bat
```

The build output is:

```text
dist\MicMuteLite.exe
```

If the old exe is still running, the build script writes:

```text
dist\MicMuteLite_new.exe
```

## Settings Storage

Settings are stored in:

```text
%APPDATA%\MicMute\config.json
```

Old local `config.json` files and the previous `%APPDATA%\MicMute Lite\config.json` location are migrated automatically.

## Custom Sounds

Place any of these files next to `MicMuteLite.exe`:

```text
on.mp3
off.mp3
on.wav
off.wav
```

The app uses custom files first. If a custom file is missing or cannot be played, it falls back to bundled sounds.

## Project Layout

```text
src/micmute_app/   application source code
assets/            app icon, tray icons, overlay icons, bundled sounds
sounds/            optional custom sounds for local runs
main.py            launcher entry point
run.bat            local run helper
build.bat          PyInstaller build helper
```

## Credits

This project was shaped around ideas and behavior from:

- [Anc813/MicMute](https://github.com/Anc813/MicMute)
- [SaifAqqad/AHK_MicMute](https://github.com/SaifAqqad/AHK_MicMute)
