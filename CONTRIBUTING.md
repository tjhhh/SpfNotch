# Contributing to spfnotch

Thanks for your interest! 🎉

## Dev setup

```powershell
git clone https://github.com/tjhhh/SpfNotch.git
cd SpfNotch
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
python app/main.py          # runs in Demo Mode without credentials
python app/main.py --test   # 1.2 s smoke test
```

## Project layout

```
app/
  main.py            entry point, tray icon, single-instance IPC
  core/              Spotify client, LRCLIB lyrics client, state manager
  ui/                PyQt6 widgets (notch window, pill, expanded view, tabs)
  utils/             image cache, Win32 helpers
  assets/            icon, fonts
tests/               widget / sync / performance tests
tools/               capture_screenshots.py (regenerates docs/screenshots)
```

## Guidelines

- Keep it lightweight: no heavy dependencies, no busy loops on the GUI thread
  (use `WorkerTask` / the thread pool for network calls).
- **Never** commit `config.json`, `.spotify_token_cache`, or built `.exe` files.
- Respect the [Spotify Developer Terms](https://developer.spotify.com/terms):
  no audio downloading/recording, no ad blocking, no shared client secrets,
  don't use "Spotify" as the product name.
- If you change the UI, re-run `python tools/capture_screenshots.py` and commit
  the updated screenshots.

## Releasing

1. Bump `__version__` in `app/__init__.py` and update `CHANGELOG.md`.
2. `git tag v1.x.y && git push origin v1.x.y`
3. GitHub Actions builds `spfnotch.exe` and publishes the release.
