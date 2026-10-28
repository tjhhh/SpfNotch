# Third-Party Notices

spfnotch's own source code is licensed under the [MIT License](LICENSE).
It depends on, bundles, or talks to the following third-party components.

## Libraries

| Component | License | Notes |
|---|---|---|
| [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) | **GPL v3** (or Riverbank commercial) | UI toolkit. See the note below. |
| [Qt 6](https://www.qt.io/) | LGPL v3 | Bundled inside PyQt6 wheels. |
| [spotipy](https://github.com/spotipy-dev/spotipy) | MIT | Spotify Web API client. |
| [requests](https://github.com/psf/requests) | Apache 2.0 | HTTP client. |
| [PyInstaller](https://pyinstaller.org/) | GPL v2 + bootloader exception | Build tool only; the exception allows distributing the produced `.exe`. |

> **Note on PyQt6 (GPL v3).** The MIT-licensed source code in this repository
> can be used, read and modified freely. However, the **pre-built `spfnotch.exe`**
> published on GitHub Releases bundles PyQt6, so that *binary as a whole* is
> distributed under the terms of the **GNU GPL v3**. The full corresponding
> source code is this repository. If you redistribute the binary, you must do
> the same (keep it open source). This is fully compatible with MIT.

## Fonts

| Component | License |
|---|---|
| [Montserrat](https://github.com/JulietaUla/Montserrat) | SIL Open Font License 1.1 - see [`app/assets/fonts/OFL.txt`](app/assets/fonts/OFL.txt) |

## Online services (not bundled - accessed at runtime)

| Service | Terms | Used for |
|---|---|---|
| [Spotify Web API](https://developer.spotify.com/documentation/web-api) | [Spotify Developer Terms](https://developer.spotify.com/terms) & [Developer Policy](https://developer.spotify.com/policy) | Playback state, controls, queue, search, cover art. |
| [LRCLIB](https://lrclib.net/) | Free public API | Synced lyrics. Lyrics remain the copyright of their respective owners and are **not** stored in or distributed with this project. |

## Trademarks

Spotify is a trademark of Spotify AB. spfnotch is an independent,
unofficial project and is **not** affiliated with, endorsed, or sponsored by
Spotify AB. Album artwork and track metadata shown in the app are provided by
the Spotify API and belong to their respective owners.
