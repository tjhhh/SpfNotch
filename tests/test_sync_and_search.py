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

def test_v4_fixes():
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)

    config_path = os.path.join(BASE_DIR, "config.json")
    image_cache = ImageCache()
    lyrics_client = LyricsClient()
    spotify_client = SpotifyClient(config_path)
    state_manager = StateManager(spotify_client, lyrics_client)

    config = {
        "spotify": {
            "client_id": "test_saved_client_id_999",
            "client_secret": "test_saved_secret_888"
        },
        "ui": {
            "notch_collapsed_width": 320,
            "notch_expanded_width": 450
        }
    }

    notch_win = NotchWindow(state_manager, image_cache, config)
    notch_win.show()

    # 1. Verify Client ID & Secret are visible in SettingsTab fieldtexts
    settings = notch_win.expanded_view.settings_tab
    assert settings.id_input.text() == "test_saved_client_id_999", f"ID field is empty! Got: {settings.id_input.text()}"
    assert settings.secret_input.text() == "test_saved_secret_888", f"Secret field is empty! Got: {settings.secret_input.text()}"
    print("[PASS] Saved Client ID and Secret are displayed in settings fields")

    # 2. Verify Search Tab focus & input
    search = notch_win.expanded_view.search_tab
    assert search.search_input is not None
    search.search_input.setText("Coldplay")
    assert search.search_input.text() == "Coldplay"

    # Test search results display
    mock_results = [
        {"uri": "spotify:track:1", "title": "Yellow", "artist": "Coldplay", "duration_ms": 269000},
        {"uri": "spotify:track:2", "title": "Viva La Vida", "artist": "Coldplay", "duration_ms": 242000}
    ]
    search.set_results(mock_results)
    assert search.results_list.count() == 2
    print("[PASS] Search Tab input and results display working")

    # 3. Verify Instant Pause behavior
    pill = notch_win.pill_view
    pill.update_track("Yellow", "Coldplay", None, is_playing=False)
    assert "⏸" in pill.status_icon.text()
    assert "⏸" in pill.text_label.text()
    print("[PASS] Instant pause indicator reflected in pill")

    # 4. Verify Track Change clears old lyrics
    pill.update_track("Yellow", "Coldplay", None, is_playing=True)
    pill.update_lyric("Look at the stars, look how they shine for you")
    assert "Look at the stars" in pill.text_label.text()
    # Next song plays
    pill.update_track("Viva La Vida", "Coldplay", None, is_playing=True)
    assert pill.current_lyric == "", "Old song lyric was not wiped on track change!"
    print("[PASS] Track change immediately clears old song lyrics")

    print("All v4 sync, search, and pause tests passed successfully!")

if __name__ == "__main__":
    test_v4_fixes()
