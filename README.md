# MicMute Lite

MicMute Lite is a small Windows tray utility for muting and unmuting a microphone with keyboard or mouse hotkeys.

## What it does

- lives in the system tray instead of keeping a large main window open
- supports `toggle`, `push-to-talk`, and `push-to-mute`
- accepts keyboard keys and mouse buttons, including `Mouse4` and `Mouse5`
- plays built-in mute and unmute sounds
- can use custom `on/off` sound files placed next to the executable
- shows a movable and resizable on-screen overlay with microphone state
- keeps theme, language, hotkey, device, and overlay settings between launches

## Quick start

Run:

```bat
run.bat
```

After launch the app stays in the tray.

- `Left click`: toggle microphone
- `Shift + left click`: open Settings
- `Right click`: open tray menu

## Build

Build a standalone exe:

```bat
build.bat
```

The result is usually written to:

```text
dist\MicMuteLite.exe
```

If the old exe is still running, the script writes a new file to:

```text
dist\MicMuteLite_new.exe
```

## Custom sounds

If one of these files is placed next to `MicMuteLite.exe`, the app will try to use it first:

- `on.mp3` or `on.wav`
- `off.mp3` or `off.wav`

If playback fails, MicMute Lite falls back to the built-in sounds.

## Project layout

```text
src/micmute_app/   application code
assets/            tray icons, overlay icons, bundled sounds, app icon
sounds/            optional custom sounds for local runs
main.py            launcher entry point
run.bat            local run helper
build.bat          PyInstaller build helper
```

## Credits

This project was originally shaped around ideas and behavior from:

- [Anc813/MicMute](https://github.com/Anc813/MicMute)
- [SaifAqqad/AHK_MicMute](https://github.com/SaifAqqad/AHK_MicMute)
