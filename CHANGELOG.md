# Changelog

All notable changes to this project are documented here.
Format based on [Keep a Changelog](https://keepachangelog.com/), versioning follows [SemVer](https://semver.org/).

## [1.1.1] - 2026-10-28

### Fixed
- **Persistent Always-On-Top Z-Order**: Notch now stays consistently on top of all desktop windows, maximized applications, borderless fullscreen apps, and Windows widgets (Win+W / Taskbar).
- **Two-Stage Topmost Elevation**: Implemented `ensure_topmost` in `win32_helpers` using both `HWND_TOPMOST (-1)` and `HWND_TOP (0)` with `SWP_NOACTIVATE` to elevate without stealing focus.
- **Extended Style Frame Flushing**: Fixed `set_no_activate` and `set_tool_window` to call `SetWindowPos` with `SWP_FRAMECHANGED` so Windows DWM never drops topmost status when modifying `GWL_EXSTYLE`.
- **Topmost Watchdog**: Added a lightweight 1s background timer and lifecycle re-elevation hooks across hover, expand, collapse, and animation events.
- **Automated Tests**: Added `tests/test_zorder_always_on_top.py` verifying Z-order dominance, focus preservation, and watchdog functionality.

## [1.1.0] - 2026-10-28

### Added
- Rebranded application identity, single-instance IPC, and assets to `spfnotch`.
- Chroma Accent Color personalization with curated palette swatches, custom HEX color picker, and dynamic album-cover color extraction.
- Automatic device discovery and context URI passing for instant Spotify desktop playback from Search and Queue tabs.

## [1.0.0] - 2026-10-28

### Added
- Dynamic-Island-style floating notch docked under the webcam (always on top, frameless).
- Collapsed pill ⇄ expanded card morphing with auto-collapse.
- Playback controls (previous / play-pause / next) and waveform scrubber seek.
- Synced lyrics from LRCLIB with 3 display styles and depth blur.
- Queue and search tabs (play now / add to queue).
- Personalization: glass presets, blur/clear/chroma/specular sliders, notch morphology, album-art accent colors.
- Bring-your-own Spotify Developer credentials with one-time OAuth login.
- Demo Mode, system tray menu, single-instance behaviour.
- Docs: README (EN/ID), LEGAL, SECURITY, CONTRIBUTING, third-party notices.
- GitHub Actions release workflow that builds `spfnotch.exe`.
