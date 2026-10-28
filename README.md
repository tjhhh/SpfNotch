<div align="center">

<img src="app/assets/icon.png" width="96" alt="spfnotch icon" />

# spfnotch

**A Dynamic-Island-style floating notch for Spotify on Windows.**
Now playing, synced lyrics, queue and search - right under your webcam.

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
![Platform](https://img.shields.io/badge/platform-Windows%2010%20%7C%2011-blue)
![Python](https://img.shields.io/badge/python-3.10%2B-yellow)
[![Release](https://img.shields.io/github/v/release/tjhhh/SpfNotch)](https://github.com/tjhhh/SpfNotch/releases)

**English** · [Bahasa Indonesia](README.id.md)

<img src="docs/screenshots/01-pill-collapsed.png" alt="Collapsed pill" />

</div>

> [!NOTE]
> spfnotch is an **unofficial** project and is not affiliated with or endorsed by
> Spotify AB. It uses only Spotify's official Web API. See [LEGAL.md](LEGAL.md).

---

## Table of contents

- [Features](#features)
- [Screenshots](#screenshots)
- [Requirements](#requirements)
- [Installation](#installation)
- [Connecting to Spotify](#connecting-to-spotify)
- [Usage](#usage)
- [Configuration](#configuration)
- [Building from source](#building-from-source)
- [Troubleshooting](#troubleshooting)
- [Limitations & boundaries](#limitations--boundaries)
- [Is this legal?](#is-this-legal)
- [License](#license)

## Features

- 🏝️ **Dynamic Island notch** - a frameless, always-on-top pill docked at the top
  center of your screen, right under the webcam.
- 🎞️ **Smooth morphing** - collapsed pill expands on hover/click into a full
  control card, and auto-collapses when the mouse leaves.
- ⏯️ **Playback controls** - previous, play/pause, next, and a clickable
  **waveform scrubber** to seek.
- 🎤 **Synced lyrics** (via [LRCLIB](https://lrclib.net)) - auto-scrolling,
  highlighted current line, click a line to seek. 3 styles: *Editorial Left*,
  *Center Stage*, *Studio Teleprompter*, optional depth blur.
- 📜 **Queue** - see what's playing next and jump to a track.
- 🔍 **Search** - search the Spotify catalog, play instantly or add to queue.
- 🎨 **Personalization** - glass presets (Liquid Dichroic, Crystal Clear, Sonic
  Aura, Smoked HUD), clear/blur/chroma/specular sliders, notch morphology,
  album-art-driven accent colors.
- 💤 **Idle pill mode** - show running synced lyrics or track info while collapsed.
- 🪶 **Lightweight** - ~45-55 MB RAM, ~0.1-0.3% CPU (local progress interpolation).
- 🙅 **No focus stealing** - pressing controls never interrupts your typing.
- 🧪 **Demo mode** - try the full UI before connecting an account.
- 🔒 **Private** - credentials and tokens stay on your PC. No telemetry.

## Screenshots

| Synced lyrics | Queue |
|---|---|
| ![Lyrics](docs/screenshots/02-expanded-lyrics.png) | ![Queue](docs/screenshots/03-expanded-queue.png) |
| **Search** | **Personalization** |
| ![Search](docs/screenshots/04-expanded-search.png) | ![Personalization](docs/screenshots/05-expanded-personalization.png) |
| **Spotify connection** | **Collapsed pill** |
| ![Spotify connection](docs/screenshots/06-spotify-connection.png) | ![Pill](docs/screenshots/01-pill-collapsed.png) |

<sub>Screenshots are generated in Demo Mode with `python tools/capture_screenshots.py`.</sub>

## Requirements

- Windows 10 or 11
- Spotify desktop (or any Spotify Connect device) signed in
- A **Spotify Premium** account for playback controls / queue / search-to-play
  (Spotify only allows these endpoints for Premium users; free accounts can still
  see now-playing info)
- A free Spotify Developer app (5-minute setup, see below)
- Python 3.10+ *(only if running from source)*

## Installation

### Option A - Download the .exe (recommended)

1. Go to [**Releases**](https://github.com/tjhhh/SpfNotch/releases/latest) and
   download `spfnotch.exe`.
2. Put it in its own folder (e.g. `C:\Apps\spfnotch\`) - it will create
   `config.json` next to itself.
3. Double-click `spfnotch.exe`. The notch appears at the top center of your screen.

> [!TIP]
> Windows SmartScreen may warn because the exe is not code-signed. Click
> **More info → Run anyway**, or build it yourself from source.

**Run at startup (optional):** press `Win + R`, type `shell:startup`, and put a
shortcut to `spfnotch.exe` in that folder.

### Option B - Run from source

```powershell
git clone https://github.com/tjhhh/SpfNotch.git
cd SpfNotch
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app/main.py
```

Or just double-click `start_notch.bat` (runs without a console window).

## Connecting to Spotify

spfnotch uses a **bring-your-own-credentials** model: you create your own
(free) Spotify Developer app, so your data only flows between your PC and
Spotify. This is a one-time setup.

1. Open the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
   and log in with your Spotify account.
2. Click **Create app** and fill in:

   | Field | Value |
   |---|---|
   | App name | `spfnotch` (anything you like) |
   | App description | `Personal desktop notch widget` |
   | Redirect URI | **`http://127.0.0.1:8888/callback`** - type it exactly, then click **Add** |
   | Which API/SDKs? | ✅ **Web API** |

   Accept the terms and click **Save**.
3. Open your app → **Settings** and copy the **Client ID** and
   **Client Secret** (*View client secret*).
4. *(If someone other than the app owner will use it)* go to **User Management**
   and add their name + Spotify email. Development-mode apps allow up to 5 users.
5. In spfnotch: hover the notch → **Personalisasi UI** tab → scroll to
   **3. Pengaturan Spotify API & Sistem** → paste Client ID & Secret →
   **Simpan & Hubungkan**.
6. Your browser opens Spotify's authorization page. Click **Agree**. You'll see
   *"Otorisasi Berhasil"* - close the tab. Done! 🎉

The token is cached locally in `.spotify_token_cache` and refreshed automatically,
so you only do this once.

**Permissions requested** (scopes): `user-read-playback-state`,
`user-modify-playback-state`, `user-read-currently-playing`. Nothing else - no
access to your playlists, library, email or followers.

**Disconnect:** delete `config.json` and `.spotify_token_cache`, and/or remove
the app at <https://www.spotify.com/account/apps/>.

## Usage

| Action | How |
|---|---|
| Expand | Hover over (or click) the pill |
| Collapse | Move the mouse away, or click the chevron ⌃ |
| Seek | Click/drag the waveform, or click a lyric line |
| Switch tabs | **Lirik** (lyrics) · **Antrean** (queue) · **Cari** (search) · **Personalisasi UI** |
| Tray menu | Right-click the tray icon → show, settings, quit |
| Quit | ⏻ button in the expanded view, or tray → **Keluar** |

Launching spfnotch again while it's running simply expands the existing notch
(single instance).

## Configuration

Settings live in `config.json` next to the app (see
[`config.example.json`](config.example.json)). Useful keys:

| Key | Default | Description |
|---|---|---|
| `ui.polling_interval_ms` | `2000` | How often Spotify is polled |
| `ui.auto_collapse_delay_ms` | `350` | Delay before collapsing after mouse leaves |
| `ui.idle_mode` | `lyrics` | What the collapsed pill shows |
| `personalization.*` | - | Glass preset, blur, tint, scrubber & lyric style |

> [!CAUTION]
> `config.json` contains your **Client Secret**. Never commit or share it - it is
> already in `.gitignore`.

## Building from source

```powershell
pip install -r requirements.txt -r requirements-dev.txt
pyinstaller spfnotch.spec --noconfirm
# Output: dist\spfnotch.exe
```

Pushing a tag like `v1.0.0` triggers the GitHub Actions workflow in
[`.github/workflows/release.yml`](.github/workflows/release.yml), which builds the
exe and attaches it to a GitHub Release automatically.

Smoke test: `python app/main.py --test`

## Troubleshooting

| Problem | Fix |
|---|---|
| `INVALID_CLIENT: Invalid redirect URI` | Redirect URI in the dashboard must be exactly `http://127.0.0.1:8888/callback` (not `localhost`). |
| Stuck on "Mode Demo" | Credentials wrong or authorization timed out (60 s). Re-paste and click **Simpan & Hubungkan** again. |
| `403` / "user not registered" | Add your Spotify email under **User Management** in the dashboard. App owner must have Premium. |
| Controls don't work | Requires Spotify Premium and an **active** device - start playing something in Spotify first. |
| Port 8888 in use | Close the app using it, or change `redirect_uri` in both `config.json` and the dashboard. |
| No lyrics | LRCLIB doesn't have synced lyrics for that track; the pill shows title & artist instead. |

## Limitations & boundaries

### What spfnotch will never do (by design)

- ❌ Download, record, cache or convert audio
- ❌ Block ads or unlock Premium features
- ❌ Modify, inject into, or patch the Spotify client
- ❌ Ship or share any Spotify Client ID / Secret
- ❌ Send your data anywhere except Spotify and LRCLIB (no telemetry, no own server)
- ❌ Be sold or used commercially with Spotify content

### Known limitations

| Area | Limitation |
|---|---|
| **Platform** | Windows 10/11 only (uses Win32 APIs for always-on-top & no-focus-steal). No macOS/Linux build. |
| **Spotify account** | Play/pause/skip/seek/queue/play-from-search need **Spotify Premium**. Free accounts get read-only now-playing info. |
| **Developer app** | Spotify Development Mode: app owner must have **Premium**, max **5 allow-listed users** per Client ID. Extended quota (public apps) requires a registered business with 250k+ MAU - so spfnotch stays bring-your-own-credentials. |
| **Active device** | Controls only work when a Spotify device is active (something has played recently). |
| **Latency** | State is polled every ~2 s; changes made in another app can take up to 2 s to appear. Progress between polls is interpolated locally. |
| **Lyrics** | Depends on LRCLIB coverage. Some tracks have no synced lyrics or no lyrics at all; nothing is shown in that case. |
| **Scopes** | Only playback scopes - no playlists, library, likes, podcasts management, or account info. |
| **OAuth port** | Login uses a fixed local callback on `127.0.0.1:8888` (60 s timeout). |
| **Display** | Docks to the top center of the screen it's on (primary screen by default). No drag-to-reposition. |
| **Install location** | `config.json` is written next to the exe, so the folder must be writable (avoid `C:\Program Files`). |
| **UI language** | The in-app UI is currently Indonesian only. |
| **Binary** | The `.exe` is not code-signed, so SmartScreen may warn on first run. |
| **Terms** | Spotify may change its API or Developer Terms at any time, which can break or restrict features. |

## Is this legal?

**Yes, for personal use.** spfnotch is a remote control built on Spotify's
**official public Web API** with standard OAuth. It doesn't download, record or
rip audio, doesn't block ads, doesn't unlock Premium, and doesn't modify the
Spotify client. It ships with **no** Spotify credentials - each user registers
their own developer app, as Spotify requires. Full details, grey areas (lyrics)
and privacy: **[LEGAL.md](LEGAL.md)**.

## Contributing

PRs and issues are welcome - see [CONTRIBUTING.md](CONTRIBUTING.md).
Found a security issue? See [SECURITY.md](SECURITY.md).

## License

Source code: [MIT](LICENSE) © 2026 tjhhh.
Third-party components (PyQt6 - GPL v3, Montserrat - OFL 1.1, ...):
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

<sub>Spotify is a trademark of Spotify AB. This project is not affiliated with Spotify.</sub>
