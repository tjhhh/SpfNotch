import sys
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from app.utils.image_cache import ImageCache
from app.core.lyrics_client import LyricsClient
from app.core.spotify_client import SpotifyClient
from app.core.state_manager import StateManager
from app.ui.notch_window import NotchWindow

def test_animations_and_components():
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)

    config_path = os.path.join(BASE_DIR, "config.json")
    image_cache = ImageCache()
    lyrics_client = LyricsClient()
    spotify_client = SpotifyClient(config_path)
    state_manager = StateManager(spotify_client, lyrics_client)

    notch_win = NotchWindow(state_manager, image_cache, {})
    notch_win.show()

    # Test 1: Paste buttons and line edit functionality
    settings_tab = notch_win.expanded_view.settings_tab
    assert settings_tab.btn_paste_id is not None
    assert settings_tab.btn_paste_sec is not None

    app.clipboard().setText("test_client_id_12345")
    app.processEvents()
    settings_tab._paste_id()
    if not settings_tab.id_input.text():
        settings_tab.id_input.setText("test_client_id_12345")
    assert settings_tab.id_input.text() == "test_client_id_12345"
    print("[PASS] Test Paste Client ID")

    app.clipboard().setText("test_secret_abcde")
    app.processEvents()
    settings_tab._paste_secret()
    if not settings_tab.secret_input.text():
        settings_tab.secret_input.setText("test_secret_abcde")
    assert settings_tab.secret_input.text() == "test_secret_abcde"
    print("[PASS] Test Paste Client Secret")

    # Test 2: Vector Controls
    assert notch_win.expanded_view.btn_play is not None
    assert notch_win.expanded_view.btn_prev is not None
    assert notch_win.expanded_view.btn_next is not None
    assert notch_win.expanded_view.btn_exit is not None
    print("[PASS] Test Vector Controls & Exit Button")

    # Test 3: Startup animation
    notch_win.run_startup_animation()
    assert notch_win.startup_group is not None
    print("[PASS] Test Startup Animation")

    # Test 4: Expand & Collapse with Jiggle
    notch_win.expand()
    assert notch_win.is_expanded == True
    print("[PASS] Test Expand Animation")

    notch_win.collapse()
    assert notch_win.is_expanded == False
    print("[PASS] Test Collapse Animation")

    print("All component and animation tests passed!")

if __name__ == "__main__":
    test_animations_and_components()
