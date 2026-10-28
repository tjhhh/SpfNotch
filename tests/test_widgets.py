import sys
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from PyQt6.QtWidgets import QApplication
from app.utils.image_cache import ImageCache
from app.core.lyrics_client import LyricsClient
from app.core.spotify_client import SpotifyClient
from app.core.state_manager import StateManager
from app.ui.notch_window import NotchWindow

def test_widget_initialization():
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)

    config_path = os.path.join(BASE_DIR, "config.json")
    image_cache = ImageCache()
    lyrics_client = LyricsClient()
    spotify_client = SpotifyClient(config_path)
    state_manager = StateManager(spotify_client, lyrics_client)

    notch_win = NotchWindow(state_manager, image_cache, {})
    
    assert notch_win.pill_view is not None
    assert notch_win.expanded_view is not None
    assert notch_win.expanded_view.lyrics_tab is not None
    assert notch_win.expanded_view.queue_tab is not None
    assert notch_win.expanded_view.search_tab is not None
    assert notch_win.expanded_view.settings_tab is not None

    notch_win.show()

    # Test expand and collapse transitions
    notch_win.expand()
    assert notch_win.is_expanded == True
    assert not notch_win.expanded_view.isHidden()

    notch_win.collapse()
    assert notch_win.is_expanded == False
    assert not notch_win.pill_view.isHidden()

    print("[PASS] test_widget_initialization")

if __name__ == "__main__":
    test_widget_initialization()
    print("Widget test suite passed successfully!")
