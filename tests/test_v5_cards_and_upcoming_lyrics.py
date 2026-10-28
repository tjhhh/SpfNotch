import sys
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QSize
from app.utils.image_cache import ImageCache
from app.core.lyrics_client import LyricsClient
from app.core.spotify_client import SpotifyClient
from app.core.state_manager import StateManager
from app.ui.notch_window import NotchWindow
from app.ui.pill_view import PillView
from app.ui.search_tab import SearchTab
from app.ui.queue_tab import QueueTab

def test_v5_enhancements():
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)

    config_path = os.path.join(BASE_DIR, "config.json")
    image_cache = ImageCache()
    lyrics_client = LyricsClient()
    spotify_client = SpotifyClient(config_path)
    spotify_client.is_connected = True
    state_manager = StateManager(spotify_client, lyrics_client)

    config = {
        "ui": {
            "notch_collapsed_width": 390,
            "notch_collapsed_height": 46,
            "notch_expanded_width": 460,
            "notch_expanded_height": 400
        }
    }

    notch_win = NotchWindow(state_manager, image_cache, config)
    notch_win.show()

    # 1. Test SearchTab card height
    search_tab = notch_win.expanded_view.search_tab
    mock_search = [
        {"uri": "spotify:track:1", "title": "Ini Abadi", "artist": "Perunggu", "duration_ms": 230000},
        {"uri": "spotify:track:2", "title": "Pompeii", "artist": "Bastille", "duration_ms": 214000}
    ]
    search_tab.set_results(mock_search)
    assert search_tab.results_list.count() == 2
    item1 = search_tab.results_list.item(0)
    assert item1.sizeHint().height() >= 50, f"Search card height must be >= 50px, got {item1.sizeHint().height()}"
    print(f"[PASS] 1. SearchTab card height is {item1.sizeHint().height()}px (generous vertical room)")

    # 2. Test QueueTab card height
    queue_tab = notch_win.expanded_view.queue_tab
    mock_queue = [
        {"id": "q1", "title": "Sampai Akhir Waktu", "artist": "Yovie & Nuno", "duration_ms": 240000},
        {"id": "q2", "title": "Abadi - Indo Version", "artist": "Dendi Nata", "duration_ms": 210000}
    ]
    queue_tab.set_queue(mock_queue)
    assert queue_tab.list_widget.count() == 2
    qitem1 = queue_tab.list_widget.item(0)
    assert qitem1.sizeHint().height() >= 50, f"Queue card height must be >= 50px, got {qitem1.sizeHint().height()}"
    print(f"[PASS] 2. QueueTab card height is {qitem1.sizeHint().height()}px (no clipped text)")

    # 3. Test PillView two-line layout & upcoming lyrics
    pill = notch_win.pill_view
    assert pill.height() == 46, f"Pill height must be 46px, got {pill.height()}"

    # Song playing without lyrics yet
    pill.update_track("Ini Abadi", "Perunggu", None, is_playing=True)
    assert "Ini Abadi" in pill.line1_label.text()
    assert "Perunggu" in pill.line2_label.text()
    print("[PASS] 3a. Pill view shows Title (line 1) & Artist (line 2) during track mode")

    # Song playing with active and upcoming lyrics
    pill.update_lyric("Katakanlah kita kan abadi", "Walau dunia berganti rupa")
    assert "♪ Katakanlah kita kan abadi" in pill.line1_label.text()
    assert "↳ Walau dunia berganti rupa" in pill.line2_label.text()
    assert pill.line2_label.isVisible() == True
    print("[PASS] 3b. Pill view shows Current Lyric (line 1) & Upcoming Lyric (line 2)")

    # 4. Test StateManager emits upcoming lyrics
    mock_lyrics = {
        "synced": True,
        "lines": [
            {"time_ms": 0, "text": "Baris Pertama"},
            {"time_ms": 5000, "text": "Baris Kedua yang Sedang Dinyanyikan"},
            {"time_ms": 12000, "text": "Baris Ketiga Upcoming Berikutnya"}
        ],
        "timestamps": [0, 5000, 12000]
    }
    state_manager.current_lyrics = mock_lyrics
    state_manager.current_progress_ms = 5200

    emitted_lyrics = []
    def on_lyric(idx, curr, upcom):
        emitted_lyrics.append((idx, curr, upcom))
    state_manager.active_lyric_changed.connect(on_lyric)

    state_manager._check_lyrics_sync()
    assert len(emitted_lyrics) >= 1
    idx, curr, upcom = emitted_lyrics[-1]
    assert idx == 1
    assert curr == "Baris Kedua yang Sedang Dinyanyikan"
    assert upcom == "Baris Ketiga Upcoming Berikutnya"
    print(f"[PASS] 4. StateManager successfully computed and emitted upcoming lyric: '{upcom}'")

    # 5. Long lyric line truncation in PillView
    super_long = "Ini adalah baris lirik yang sangat panjang sekali melebihi batas karakter normal pada notch"
    pill.update_lyric(super_long, "Lirik selanjutnya")
    assert pill.line1_label.text().endswith("...")
    assert len(pill.line1_label.text()) <= 55
    print("[PASS] 5. Long lyrics gracefully truncated with ellipsis without overflowing")

    # 6. Paused mode fallback
    pill.update_track("Ini Abadi", "Perunggu", None, is_playing=False)
    assert "⏸" in pill.line1_label.text()
    assert "Perunggu" in pill.line2_label.text()
    print("[PASS] 6. Paused state displays Pause Title on line 1, Artist on line 2")

    print("\nALL V5 ENHANCEMENT TESTS PASSED 100%!")

if __name__ == "__main__":
    test_v5_enhancements()
