import sys
import os
from unittest.mock import MagicMock

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QMouseEvent

from app.utils.image_cache import ImageCache
from app.core.lyrics_client import LyricsClient
from app.core.spotify_client import SpotifyClient
from app.core.state_manager import StateManager
from app.ui.notch_window import NotchWindow
from app.ui.search_tab import SearchTab, SearchItemCard

def test_search_playback():
    app = QApplication.instance()
    if not app:
        app = QApplication(["--platform", "offscreen"])

    config_path = os.path.join(BASE_DIR, "config.json")
    image_cache = ImageCache()
    lyrics_client = LyricsClient()
    spotify_client = SpotifyClient(config_path)
    state_manager = StateManager(spotify_client, lyrics_client)

    notch_win = NotchWindow(state_manager, image_cache, {})
    notch_win.show()

    search_tab = notch_win.expanded_view.search_tab

    # 1. Test search results population
    sample_tracks = [
        {
            "id": "track_1",
            "title": "Secukupnya",
            "artist": "Hindia",
            "duration_ms": 204000,
            "cover_url": "",
            "uri": "spotify:track:secukupnya"
        },
        {
            "id": "track_2",
            "title": "Evaluasi",
            "artist": "Hindia",
            "duration_ms": 215000,
            "cover_url": "",
            "uri": "spotify:track:evaluasi"
        }
    ]
    search_tab.set_results(sample_tracks)
    assert search_tab.results_list.count() == 2
    print("[PASS] Results populated in list")

    # 2. Test entire card clickability (mousePressEvent on card)
    card_1 = search_tab.results_list.itemWidget(search_tab.results_list.item(0))
    assert isinstance(card_1, SearchItemCard)

    received_signals = []
    search_tab.play_track_requested.connect(lambda uri, meta: received_signals.append((uri, meta)))

    # Simulate mouse click on the middle of the card
    click_pos = QPointF(100.0, 20.0)
    mouse_ev = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        click_pos,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier
    )
    card_1.mousePressEvent(mouse_ev)

    assert len(received_signals) == 1
    assert received_signals[0][0] == "spotify:track:secukupnya"
    assert received_signals[0][1]["title"] == "Secukupnya"
    print("[PASS] Clicking card row emitted play_track_requested with track metadata")

    # 3. Test Demo Mode play_track in StateManager
    state_manager.demo_mode = True
    state_manager.play_track("spotify:track:evaluasi", sample_tracks[1])
    assert state_manager.is_playing == True
    assert state_manager.current_track["title"] == "Evaluasi"
    assert state_manager.current_track["artist"] == "Hindia"
    print("[PASS] StateManager.play_track updates demo playback and ticker")

    # Switch tab to Search tab so widgets are active and visible
    notch_win.expand()
    notch_win.expanded_view.tabs.setCurrentIndex(2)

    # 4. Test feedback toast display
    search_tab.show_feedback(True, "Memutar di Komputer")
    assert not search_tab.status_lbl.isHidden()
    assert "Memutar di Komputer" in search_tab.status_lbl.text()

    search_tab.show_feedback(False, "Tidak ada perangkat aktif")
    assert not search_tab.status_lbl.isHidden()
    assert "Tidak ada perangkat aktif" in search_tab.status_lbl.text()
    print("[PASS] SearchTab feedback display working")

    # 5. Test Mocked SpotifyClient play_track with device and album context_uri
    spotify_mock = MagicMock()
    spotify_mock.devices.return_value = {
        "devices": [
            {"id": "dev_pc", "name": "My PC", "type": "Computer", "is_active": True}
        ]
    }
    spotify_mock.track.return_value = {"album": {"uri": "spotify:album:menari_dengan_bayangan"}}
    spotify_mock.start_playback = MagicMock()
    
    mock_client = SpotifyClient(config_path)
    mock_client.sp = spotify_mock
    mock_client.is_connected = True
    success, msg = mock_client.play_track("spotify:track:evaluasi")
    assert success == True
    spotify_mock.start_playback.assert_called_once_with(
        device_id="dev_pc",
        context_uri="spotify:album:menari_dengan_bayangan",
        offset={"uri": "spotify:track:evaluasi"}
    )
    print("[PASS] SpotifyClient.play_track successfully targets device_id with album context_uri & offset")

    print("\nAll Search Playback tests PASSED successfully!")

if __name__ == "__main__":
    test_search_playback()
