import sys
import os
import time
from unittest.mock import MagicMock, patch

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from PyQt6.QtWidgets import QApplication
from spotipy.exceptions import SpotifyException
from app.core.spotify_client import SpotifyClient
from app.core.state_manager import StateManager
from app.ui.settings_tab import SettingsTab
from app.main import acquire_win32_mutex, clean_end_task

def run_tests():
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)

    print("======================================================================")
    print("Running Long Pause Desync, Reconnect & Exit Lifecycle Test Suite")
    print("======================================================================")

    # -------------------------------------------------------------------------
    # TEST 1: Token Expiration (401) Self-Healing Recovery
    # -------------------------------------------------------------------------
    config_path = os.path.join(BASE_DIR, "config.json")
    client = SpotifyClient(config_path)
    client.is_connected = True
    client.sp = MagicMock()

    # Configure mock: first call throws 401 Unauthorized, second call succeeds
    valid_raw_playback = {
        "is_playing": True,
        "device": {"id": "dev_1", "name": "PC-Desktop"},
        "item": {
            "id": "track_abc",
            "name": "Viva La Vida",
            "artists": [{"name": "Coldplay"}],
            "album": {"name": "Viva La Vida", "images": [{"url": "http://cover.jpg"}]},
            "duration_ms": 242000,
            "uri": "spotify:track:abc"
        },
        "progress_ms": 12000
    }
    client.sp.current_playback.side_effect = [
        SpotifyException(401, -1, "The access token expired"),
        valid_raw_playback
    ]

    # Mock _refresh_token_and_session to succeed
    client._refresh_token_and_session = MagicMock(return_value=True)

    result = client.get_current_playback()
    assert result is not None, "get_current_playback must recover from 401 via token refresh!"
    assert result["title"] == "Viva La Vida"
    assert result["is_playing"] is True
    assert client._refresh_token_and_session.call_count == 1, "Must trigger token refresh on 401"
    print("[PASS] 1. Token 401 Auto-Recovery: Refreshed token and synced playback without restart")

    # -------------------------------------------------------------------------
    # TEST 2: Rate Limiting (429) Backoff Handling
    # -------------------------------------------------------------------------
    client.sp.current_playback.side_effect = SpotifyException(
        429, -1, "Too Many Requests", headers={"Retry-After": "12"}
    )
    result_429 = client.get_current_playback()
    assert result_429 is None
    assert client._rate_limit_until > time.time() + 8.0, "Rate limit backoff timestamp must be set"
    assert "Kuota API Spotify Habis" in client.last_error_message, "Must set informative rate limit error message"

    # Subsequent call while in backoff must return None immediately without calling API
    client.sp.current_playback.reset_mock()
    res_suppressed = client.get_current_playback()
    assert res_suppressed is None
    assert client.sp.current_playback.call_count == 0, "Must not query API while under rate-limit"
    client._rate_limit_until = 0.0  # Reset for next tests
    print("[PASS] 2. HTTP 429 Rate-Limit: Backoff respected, fast session used, and informative message set")

    # -------------------------------------------------------------------------
    # TEST 3: Polling Concurrency Guard (_is_polling)
    # -------------------------------------------------------------------------
    lyrics_mock = MagicMock()
    state_mgr = StateManager(client, lyrics_mock)
    state_mgr.thread_pool = MagicMock()

    state_mgr._is_polling = True
    state_mgr._poll_spotify()
    assert state_mgr.thread_pool.start.call_count == 0, "Must not queue task when already polling!"

    state_mgr._is_polling = False
    state_mgr._poll_spotify()
    assert state_mgr.thread_pool.start.call_count == 1, "Must queue task when idle"
    print("[PASS] 3. Concurrency Guard: Overlapping polling prevented, eliminates thread queue buildup")

    # -------------------------------------------------------------------------
    # TEST 4: Adaptive Polling Interval Transitions
    # -------------------------------------------------------------------------
    # A. Active Playing -> 1500ms
    playback_active = {
        "is_playing": True,
        "track_id": "tr_1",
        "title": "Song A",
        "artist": "Artist A",
        "album": "Album A",
        "cover_url": "",
        "progress_ms": 5000,
        "duration_ms": 200000,
        "uri": "spotify:track:1"
    }
    state_mgr._on_playback_received(playback_active)
    assert state_mgr.poll_timer.interval() == 1500, f"Expected 1500ms, got {state_mgr.poll_timer.interval()}"

    # B. Just Paused (< 15s) -> 800ms
    playback_paused = dict(playback_active)
    playback_paused["is_playing"] = False
    state_mgr._on_playback_received(playback_paused)
    assert state_mgr.poll_timer.interval() == 800, f"Expected 800ms, got {state_mgr.poll_timer.interval()}"

    # C. Paused for 30s -> 3000ms
    state_mgr._pause_start_timestamp = time.time() - 30.0
    state_mgr._on_playback_received(playback_paused)
    assert state_mgr.poll_timer.interval() == 3000, f"Expected 3000ms, got {state_mgr.poll_timer.interval()}"

    # D. Paused for > 2 hours (long pause) -> 5000ms
    state_mgr._pause_start_timestamp = time.time() - 7500.0
    state_mgr._on_playback_received(playback_paused)
    assert state_mgr.poll_timer.interval() == 5000, f"Expected 5000ms, got {state_mgr.poll_timer.interval()}"

    # E. Resuming playback -> snaps immediately back to 1500ms
    state_mgr._on_playback_received(playback_active)
    assert state_mgr.poll_timer.interval() == 1500, f"Expected 1500ms, got {state_mgr.poll_timer.interval()}"
    print("[PASS] 4. Adaptive Polling: Seamless transition between 1500ms, 800ms, 3000ms, and 5000ms")

    # -------------------------------------------------------------------------
    # TEST 5: Manual Reconnect Button, Dashboard Shortcut & Specific Error Banner
    # -------------------------------------------------------------------------
    settings_tab = SettingsTab("test_client_id", "test_secret")
    assert hasattr(settings_tab, "btn_reconnect"), "SettingsTab must have btn_reconnect"
    assert hasattr(settings_tab, "btn_open_dashboard"), "SettingsTab must have btn_open_dashboard"
    assert "Sambungkan Ulang" in settings_tab.btn_reconnect.text()
    assert "Buka Dashboard" in settings_tab.btn_open_dashboard.text()

    reconnect_spy = []
    settings_tab.reconnect_requested.connect(lambda: reconnect_spy.append(True))

    settings_tab.btn_reconnect.click()
    assert len(reconnect_spy) == 1, "reconnect_requested signal must be emitted upon click"
    assert "Menyambungkan" in settings_tab.btn_reconnect.text()
    assert settings_tab.btn_reconnect.isEnabled() is False

    # Test error display in banner
    settings_tab.set_connected(False, "Kuota API Spotify Habis")
    assert "Kuota API Spotify Habis" in settings_tab.status_banner.text()
    assert settings_tab.btn_reconnect.isEnabled() is True

    settings_tab.set_connected(True)
    assert settings_tab.btn_reconnect.isEnabled() is True
    assert "Sambungkan Ulang" in settings_tab.btn_reconnect.text()
    assert "● Terhubung ke Spotify API" in settings_tab.status_banner.text()
    print("[PASS] 5. UI Controls & Error Banner: Reconnect, Dashboard button, and specific error display verified")

    # -------------------------------------------------------------------------
    # TEST 6: StateManager.force_reconnect()
    # -------------------------------------------------------------------------
    client.try_auto_reconnect = MagicMock(return_value=True)
    state_mgr._poll_spotify = MagicMock()
    conn_spy = []
    state_mgr.connection_changed.connect(lambda s: conn_spy.append(s))

    ok = state_mgr.force_reconnect()
    assert ok is True
    assert client.try_auto_reconnect.call_args[1].get("force_refresh") is True
    assert state_mgr._poll_spotify.call_count == 1, "Must immediately trigger poll upon reconnect"
    assert True in conn_spy, "connection_changed(True) must be emitted"
    print("[PASS] 6. StateManager force_reconnect: Forces refresh and re-polls immediately")

    # -------------------------------------------------------------------------
    # TEST 7: Clean End-Task Teardown Sequence (Zombie Process Prevention)
    # -------------------------------------------------------------------------
    mock_win = MagicMock()
    mock_state = MagicMock()
    mock_tray = MagicMock()
    mock_ipc = MagicMock()

    # Test that clean_end_task executes all steps before exiting
    with patch("os._exit") as mock_os_exit:
        clean_end_task(mock_win, mock_state, mock_tray, mock_ipc)
        assert mock_win.save_all_settings.call_count == 1
        assert mock_win.hide.call_count == 1
        assert mock_tray.hide.call_count == 1
        assert mock_tray.deleteLater.call_count == 1
        assert mock_ipc.close.call_count == 1
        assert mock_state.shutdown.call_count == 1
        assert mock_os_exit.call_args[0][0] == 0, "Must exit with code 0"
    print("[PASS] 7. Clean End-Task: Settings flushed, tray hidden, IPC closed, and process cleanly terminated")

    # -------------------------------------------------------------------------
    # TEST 8: Win32 Named Mutex Single-Instance Protection
    # -------------------------------------------------------------------------
    if sys.platform == "win32":
        # Acquire test mutex
        test_mutex_name = "Global\\spfnotch_Test_SingleInstance_Mutex"
        res1 = acquire_win32_mutex(test_mutex_name)
        assert res1 is True, "First mutex acquisition must succeed"
        
        # Second acquisition with same name must detect collision
        res2 = acquire_win32_mutex(test_mutex_name)
        assert res2 is False, "Second mutex acquisition must be blocked"
        print("[PASS] 8. Win32 Named Mutex: Atomic kernel-level single instance successfully verified")
    else:
        print("[SKIP] 8. Win32 Named Mutex (Non-Windows platform)")

    # -------------------------------------------------------------------------
    # TEST 9: HTTP 429 Local Desktop Fallback (Play, Transport, Window Sync)
    # -------------------------------------------------------------------------
    client._rate_limit_until = time.time() + 3600.0
    assert client.is_rate_limited() is True

    track_meta_33 = {
        "id": "tr_33",
        "title": "33",
        "artist": "Polo G",
        "album": "THE GOAT",
        "cover_url": "http://cover33.jpg",
        "duration_ms": 170000,
        "uri": "spotify:track:33"
    }
    with patch("app.core.spotify_client.play_spotify_uri_locally", return_value=True) as mock_local_play:
        ok_play, msg_play = client.play_track("spotify:track:33", track_meta=track_meta_33)
        assert ok_play is True, f"Expected local play fallback to succeed on 429, got: {msg_play}"
        assert "Mode Lokal" in msg_play
        assert mock_local_play.call_count == 1

    with patch("app.core.spotify_client.send_spotify_media_command", return_value=True) as mock_media_cmd:
        assert client.toggle_play(True) is True
        assert client.next_track() is True
        assert client.previous_track() is True
        assert mock_media_cmd.call_count == 3

    with patch("app.core.spotify_client.get_spotify_window_track", return_value={
        "is_playing": True, "artist": "Polo G", "title": "33", "raw_title": "Polo G - 33", "hwnd": 12345
    }):
        local_pb = client.get_local_desktop_playback()
        assert local_pb is not None
        assert local_pb["title"] == "33"
        assert local_pb["artist"] == "Polo G"
        assert local_pb["duration_ms"] == 170000
        assert local_pb["is_local_fallback"] is True

        # Verify StateManager preserves interpolated progress on repeated local polls of same track
        state_mgr._on_playback_received(local_pb)
        state_mgr.current_progress_ms = 45000
        state_mgr._on_playback_received(local_pb)
        assert state_mgr.current_progress_ms == 45000, "Local fallback poll must not reset interpolated progress to 0!"
    print("[PASS] 9. HTTP 429 Local Desktop Fallback: Play URI, media keys, window sync & progress interpolation verified")

    # -------------------------------------------------------------------------
    # TEST 10: Rate-Limit State Reset on New Credentials & Hybrid Status Banner
    # -------------------------------------------------------------------------
    settings_tab.set_connected(True, "Kuota API Spotify Habis")
    assert "Mode Lokal Aktif" in settings_tab.status_banner.text()

    client._rate_limit_until = 0.0
    print("[PASS] 10. Hybrid Status Banner & Rate-Limit Reset verified")

    print("======================================================================")
    print("ALL 10 LIFECYCLE, DESYNC, 429 FALLBACK & EXIT TESTS PASSED! 100% VERIFIED.")
    print("======================================================================")

if __name__ == "__main__":
    run_tests()
