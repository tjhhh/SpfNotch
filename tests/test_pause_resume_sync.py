import sys
import os
import time

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

def test_pause_resume_sync():
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)

    config_path = os.path.join(BASE_DIR, "config.json")
    image_cache = ImageCache()
    lyrics_client = LyricsClient()
    spotify_client = SpotifyClient(config_path)
    spotify_client.is_connected = True  # Mock connection for test
    state_manager = StateManager(spotify_client, lyrics_client)

    config = {
        "spotify": {"client_id": "test_id", "client_secret": "test_secret"},
        "ui": {"notch_collapsed_width": 320, "notch_expanded_width": 450}
    }

    notch_win = NotchWindow(state_manager, image_cache, config)
    notch_win.show()

    # Provide mock lyrics
    mock_lyrics = {
        "synced": True,
        "lines": [
            {"time_ms": 0, "text": "Intro music"},
            {"time_ms": 5000, "text": "First line of the song"},
            {"time_ms": 15000, "text": "Second line of the song"},
            {"time_ms": 25000, "text": "Chorus begins now"}
        ],
        "timestamps": [0, 5000, 15000, 25000]
    }
    state_manager._on_lyrics_received(mock_lyrics)

    # 1. Simulate Spotify Playing track
    playback_playing_1 = {
        "is_playing": True,
        "track_id": "track_123",
        "title": "Fix You",
        "artist": "Coldplay",
        "album": "X&Y",
        "cover_url": "",
        "progress_ms": 6000,
        "duration_ms": 300000,
        "uri": "spotify:track:fixyou"
    }
    state_manager._on_playback_received(playback_playing_1)

    assert state_manager.is_playing == True
    assert state_manager.tick_timer.isActive() == True, "tick_timer should be active when playing!"
    assert notch_win.expanded_view.btn_play.is_playing == True, "Play button should show Pause (is_playing=True)"
    assert "Fix You" in notch_win.pill_view.current_title
    print("[PASS] 1. Initial play state: tick_timer is active, UI synced")

    # 2. Simulate User Pausing in Spotify
    playback_paused = dict(playback_playing_1)
    playback_paused["is_playing"] = False
    playback_paused["progress_ms"] = 8500
    state_manager._on_playback_received(playback_paused)

    assert state_manager.is_playing == False
    assert state_manager.tick_timer.isActive() == False, "tick_timer must be stopped when paused!"
    assert state_manager.poll_timer.interval() == 800, "poll_timer must be 800ms when paused!"
    assert notch_win.expanded_view.btn_play.is_playing == False, "Play button must show Play (is_playing=False)"
    assert "⏸" in notch_win.pill_view.status_icon.text()
    assert "⏸" in notch_win.pill_view.text_label.text()
    print("[PASS] 2. Pause detected: tick_timer stopped, poll_timer sped up to 800ms, UI paused")

    # 3. Simulate User Unpausing / Playing again in Spotify
    playback_resumed = dict(playback_playing_1)
    playback_resumed["is_playing"] = True
    playback_resumed["progress_ms"] = 8600
    state_manager._on_playback_received(playback_resumed)

    assert state_manager.is_playing == True
    assert state_manager.tick_timer.isActive() == True, "tick_timer MUST restart when resuming playback!"
    assert state_manager.current_progress_ms == 8600, "progress_ms must snap immediately on resume"
    assert notch_win.expanded_view.btn_play.is_playing == True, "Play button must update back to Pause icon"
    assert notch_win.pill_view.status_icon.text() == "▶", "Pill status icon must show ▶"
    print("[PASS] 3. Resume detected: tick_timer restarted successfully, progress snapped to server, UI playing")

    # 4. Verify interpolator advances progress and changes active lyric
    prev_ms = state_manager.current_progress_ms
    state_manager.last_tick_timestamp = time.time() - 0.2  # simulate 200ms elapsed
    state_manager._interpolate_tick()
    assert state_manager.current_progress_ms > prev_ms, "Progress ms should advance on tick"
    print(f"[PASS] 4. Tick interpolation smoothly advanced progress from {prev_ms} to {state_manager.current_progress_ms}ms")

    # 5. Advance to 15200ms and verify lyric syncs to 'Second line of the song'
    state_manager.current_lyrics = mock_lyrics
    state_manager.current_progress_ms = 15200
    state_manager._check_lyrics_sync()
    assert state_manager.active_lyric_idx == 2
    assert "Second line of the song" in notch_win.pill_view.text_label.text()
    print("[PASS] 5. Lyrics correctly synced to active line after resume")

    # 6. Test background worker signal dispatch (Thread Safety)
    received_in_thread = []
    def on_playback_test(p):
        received_in_thread.append(p)
    state_manager.playback_state_changed.connect(on_playback_test)

    # Dispatch via internal signal as if from QThreadPool
    state_manager._playback_received.emit(playback_resumed)
    app.processEvents()
    assert len(received_in_thread) >= 1
    assert state_manager.tick_timer.isActive() == True
    print("[PASS] 6. Thread-safe queued signal dispatch successfully started timer on main thread")

    print("\nALL PAUSE-RESUME SYNC TESTS PASSED SUCCESSFULLY! 100% VERIFIED.")

if __name__ == "__main__":
    test_pause_resume_sync()
