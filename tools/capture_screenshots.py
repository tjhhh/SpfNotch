"""
Generate README screenshots of spfnotch in Demo Mode (no Spotify account needed).

Usage:
    python tools/capture_screenshots.py

Output: docs/screenshots/*.png
"""
import os
import sys
import tempfile

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from PyQt6.QtCore import Qt, QTimer, QEventLoop
from PyQt6.QtWidgets import QApplication

from app.utils.image_cache import ImageCache
from app.core.lyrics_client import LyricsClient
from app.core.spotify_client import SpotifyClient
from app.core.state_manager import StateManager
from app.ui.notch_window import NotchWindow

OUT_DIR = os.path.join(BASE_DIR, "docs", "screenshots")


def wait(ms: int):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def save(widget, name: str):
    pix = widget.grab()
    path = os.path.join(OUT_DIR, name)
    pix.save(path, "PNG")
    print(f"[screenshot] {path} ({pix.width()}x{pix.height()})")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)

    # Point at a non-existent config so the app always starts in Demo Mode,
    # never touching the developer's real credentials.
    demo_cfg = os.path.join(tempfile.mkdtemp(prefix="spfnotch_demo_"), "config.json")

    spotify_client = SpotifyClient(demo_cfg)
    state_manager = StateManager(spotify_client, LyricsClient())
    win = NotchWindow(state_manager, ImageCache(), {})
    win.show()
    state_manager.start()
    wait(2500)

    # 1. Collapsed pill
    save(win, "01-pill-collapsed.png")

    # 2-5. Expanded view, every tab
    # Prevent auto-collapse (cursor is not over the notch while capturing)
    win._check_cursor_in_or_out = lambda: None
    win.leaveEvent = lambda ev: None
    win.expand()
    win.cursor_watchdog.stop()
    win.auto_collapse_timer.stop()
    wait(1200)
    ev = win.expanded_view
    tabs = [
        (0, "02-expanded-lyrics.png"),
        (1, "03-expanded-queue.png"),
        (2, "04-expanded-search.png"),
        (3, "05-expanded-personalization.png"),
    ]
    for idx, name in tabs:
        ev.switch_tab(idx)
        if idx == 2:
            ev.search_tab.search_input.setText("abadi")
            ev.search_tab.set_results(spotify_client.search_tracks("abadi"))
        wait(700)
        save(win, name)

    # 6. Spotify connection section (bottom of the Personalization tab)
    sb = ev.settings_tab.scroll_area.verticalScrollBar()
    sb.setValue(sb.maximum())
    wait(500)
    save(win, "06-spotify-connection.png")

    app.quit()


if __name__ == "__main__":
    main()
