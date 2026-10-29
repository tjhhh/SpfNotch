"""
Comprehensive E2E and Unit Test Suite for Spotify Queue Parsing, Concurrency, and UI Triggers.
Covers:
- Tier 1: Resilient Queue Parsing (R1)
- Tier 2: Asynchronous Concurrency & Isolation (R2)
- Tier 3: UI Refresh Triggers & Updates (R3)
"""

import os
import sys
import time
import threading
from unittest.mock import MagicMock

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QCoreApplication

from app.core.spotify_client import SpotifyClient
from app.core.lyrics_client import LyricsClient
from app.core.state_manager import StateManager
from app.ui.expanded_view import ExpandedView
from app.ui.queue_tab import QueueTab


def _get_app():
    app = QApplication.instance()
    if not app:
        app = QApplication(["--platform", "offscreen"])
    return app


# Ensure QApplication is initialized for offscreen test runner
_APP = _get_app()


# ============================================================================
# Tier 1: Queue Parsing Tests (R1)
# ============================================================================

def test_get_queue_calls_ensure_connected():
    """Verify _ensure_connected() is called before querying Spotify queue."""
    config_path = os.path.join(BASE_DIR, "config.json")
    client = SpotifyClient(config_path)
    client.sp = MagicMock()
    client.is_connected = True
    client.sp.queue.return_value = {"queue": []}

    client._ensure_connected = MagicMock(return_value=True)

    client.get_queue()
    assert client._ensure_connected.called, (
        "SpotifyClient.get_queue() must call self._ensure_connected() before querying queue"
    )

    # When _ensure_connected returns False, sp.queue should not be called
    client.sp.queue.reset_mock()
    client._ensure_connected.return_value = False
    res = client.get_queue()
    assert not client.sp.queue.called, (
        "SpotifyClient.get_queue() must not query sp.queue() if _ensure_connected() is False"
    )
    assert isinstance(res, list)


def test_get_queue_album_none_and_non_dict():
    """Verify queue items with album: None or non-dict album do not raise AttributeError."""
    config_path = os.path.join(BASE_DIR, "config.json")
    client = SpotifyClient(config_path)
    mock_sp = MagicMock()
    client.sp = mock_sp
    client.is_connected = True
    client._ensure_connected = MagicMock(return_value=True)

    mock_sp.queue.return_value = {
        "queue": [
            {
                "id": "trk_none_album",
                "name": "Track With None Album",
                "artists": [{"name": "Solo Artist"}],
                "album": None,
                "duration_ms": 190000,
                "uri": "spotify:track:trk_none_album"
            },
            {
                "id": "trk_str_album",
                "name": "Track With String Album",
                "artists": [{"name": "Second Artist"}],
                "album": "Single Release (Non-Dict)",
                "duration_ms": 210000,
                "uri": "spotify:track:trk_str_album"
            },
            {
                "id": "trk_int_album",
                "name": "Track With Int Album",
                "artists": [{"name": "Third Artist"}],
                "album": 12345,
                "duration_ms": 180000,
                "uri": "spotify:track:trk_int_album"
            }
        ]
    }

    res = client.get_queue()
    assert len(res) == 3, f"Expected 3 tracks parsed successfully, got {len(res)}"
    assert res[0]["title"] == "Track With None Album"
    assert res[0]["album"] == ""
    assert res[1]["title"] == "Track With String Album"
    assert res[1]["album"] == ""
    assert res[2]["title"] == "Track With Int Album"
    assert res[2]["album"] == ""


def test_get_queue_artists_none_and_empty():
    """Verify queue items with artists: None or empty list do not raise TypeError."""
    config_path = os.path.join(BASE_DIR, "config.json")
    client = SpotifyClient(config_path)
    mock_sp = MagicMock()
    client.sp = mock_sp
    client.is_connected = True
    client._ensure_connected = MagicMock(return_value=True)

    mock_sp.queue.return_value = {
        "queue": [
            {
                "id": "trk_art_none",
                "name": "Track With None Artists",
                "artists": None,
                "album": {"name": "Album One", "images": []},
                "duration_ms": 200000,
                "uri": "spotify:track:trk_art_none"
            },
            {
                "id": "trk_art_empty",
                "name": "Track With Empty Artists",
                "artists": [],
                "album": {"name": "Album Two", "images": []},
                "duration_ms": 185000,
                "uri": "spotify:track:trk_art_empty"
            }
        ]
    }

    res = client.get_queue()
    assert len(res) == 2, f"Expected 2 tracks parsed, got {len(res)}"
    assert res[0]["title"] == "Track With None Artists"
    assert res[0]["artist"] in ["", "-", "Unknown"]
    assert res[1]["title"] == "Track With Empty Artists"
    assert res[1]["artist"] in ["", "-", "Unknown"]


def test_get_queue_podcast_episode_show_metadata():
    """Verify podcast episodes with show.publisher or show.name resolve artist correctly."""
    config_path = os.path.join(BASE_DIR, "config.json")
    client = SpotifyClient(config_path)
    mock_sp = MagicMock()
    client.sp = mock_sp
    client.is_connected = True
    client._ensure_connected = MagicMock(return_value=True)

    mock_sp.queue.return_value = {
        "queue": [
            {
                "id": "ep_publisher",
                "name": "Episode 1: Tech Talks",
                "type": "episode",
                "show": {
                    "name": "Tech Show",
                    "publisher": "Acme Media Network",
                    "images": [{"url": "http://img.publisher.jpg"}]
                },
                "duration_ms": 3600000,
                "uri": "spotify:episode:ep_publisher"
            },
            {
                "id": "ep_show_name_only",
                "name": "Episode 2: Science Hour",
                "type": "episode",
                "show": {
                    "name": "Science Hour Show",
                    "images": [{"url": "http://img.show.jpg"}]
                },
                "duration_ms": 2400000,
                "uri": "spotify:episode:ep_show_name_only"
            }
        ]
    }

    res = client.get_queue()
    assert len(res) == 2, f"Expected 2 podcast episodes parsed, got {len(res)}"
    assert res[0]["artist"] == "Acme Media Network", f"Expected 'Acme Media Network', got '{res[0]['artist']}'"
    assert res[0]["cover_url"] == "http://img.publisher.jpg"
    assert res[1]["artist"] == "Science Hour Show", f"Expected 'Science Hour Show', got '{res[1]['artist']}'"
    assert res[1]["cover_url"] == "http://img.show.jpg"


def test_get_queue_cover_image_fallbacks():
    """Verify cover image extracted from album images, item direct images, or show images."""
    config_path = os.path.join(BASE_DIR, "config.json")
    client = SpotifyClient(config_path)
    mock_sp = MagicMock()
    client.sp = mock_sp
    client.is_connected = True
    client._ensure_connected = MagicMock(return_value=True)

    mock_sp.queue.return_value = {
        "queue": [
            {
                "id": "img_album",
                "name": "Track Album Images",
                "artists": [{"name": "Artist 1"}],
                "album": {
                    "name": "Album 1",
                    "images": [{"url": "http://img/album_640.jpg"}, {"url": "http://img/album_64.jpg"}]
                },
                "duration_ms": 180000,
                "uri": "spotify:track:img_album"
            },
            {
                "id": "img_direct",
                "name": "Video Track Direct Images",
                "artists": [{"name": "Artist 2"}],
                "album": None,
                "images": [{"url": "http://img/direct_item.jpg"}],
                "duration_ms": 200000,
                "uri": "spotify:track:img_direct"
            },
            {
                "id": "img_show",
                "name": "Podcast Episode Show Images",
                "type": "episode",
                "show": {
                    "name": "Show Name",
                    "images": [{"url": "http://img/show_banner.jpg"}]
                },
                "album": None,
                "duration_ms": 1500000,
                "uri": "spotify:episode:img_show"
            }
        ]
    }

    res = client.get_queue()
    assert len(res) == 3, f"Expected 3 tracks parsed, got {len(res)}"
    assert "http://img/album" in res[0]["cover_url"], "Album image must be extracted"
    assert res[1]["cover_url"] == "http://img/direct_item.jpg", "Direct item image must be extracted when album is None"
    assert res[2]["cover_url"] == "http://img/show_banner.jpg", "Show image must be extracted for podcast episode"


def test_get_queue_per_item_error_handling():
    """Verify a corrupt or malformed item in queue does not discard subsequent valid tracks."""
    config_path = os.path.join(BASE_DIR, "config.json")
    client = SpotifyClient(config_path)
    mock_sp = MagicMock()
    client.sp = mock_sp
    client.is_connected = True
    client._ensure_connected = MagicMock(return_value=True)

    mock_sp.queue.return_value = {
        "queue": [
            {
                "id": "valid_track_1",
                "name": "First Valid Track",
                "artists": [{"name": "Artist 1"}],
                "album": {"name": "Album 1", "images": []},
                "duration_ms": 180000,
                "uri": "spotify:track:v1"
            },
            None,  # Null item
            "corrupt_string_item",  # Non-dict item
            {
                "id": "valid_track_2",
                "name": "Second Valid Track",
                "artists": [{"name": "Artist 2"}],
                "album": {"name": "Album 2", "images": []},
                "duration_ms": 220000,
                "uri": "spotify:track:v2"
            }
        ]
    }

    res = client.get_queue()
    assert len(res) == 2, f"Corrupt items should be skipped while valid tracks are kept; got {len(res)}"
    assert res[0]["title"] == "First Valid Track"
    assert res[1]["title"] == "Second Valid Track"


def test_get_queue_returns_up_to_30_tracks():
    """Verify get_queue returns up to 30 tracks when 30+ items are available in queue."""
    config_path = os.path.join(BASE_DIR, "config.json")
    client = SpotifyClient(config_path)
    mock_sp = MagicMock()
    client.sp = mock_sp
    client.is_connected = True
    client._ensure_connected = MagicMock(return_value=True)

    mock_sp.queue.return_value = {
        "queue": [
            {
                "id": f"trk_{i}",
                "name": f"Track Number {i}",
                "artists": [{"name": f"Artist {i}"}],
                "album": {"name": f"Album {i}", "images": []},
                "duration_ms": 180000 + i,
                "uri": f"spotify:track:t{i}"
            }
            for i in range(1, 36)  # 35 items
        ]
    }

    res = client.get_queue()
    assert len(res) == 30, f"Expected queue limit of 30 tracks, got {len(res)}"
    assert res[0]["title"] == "Track Number 1"
    assert res[29]["title"] == "Track Number 30"


# ============================================================================
# Tier 2: Concurrency & Concurrency Isolation Tests (R2)
# ============================================================================

def test_state_manager_queue_fetching_independent_thread():
    """Verify fetch_queue runs in background worker thread and emits queue_updated."""
    _get_app()
    mock_spotify = MagicMock()
    mock_lyrics = MagicMock()
    mock_spotify.get_queue.return_value = [
        {"id": "q1", "title": "Independent Track", "artist": "Band", "duration_ms": 200000}
    ]

    state_mgr = StateManager(mock_spotify, mock_lyrics)
    state_mgr.poll_timer.stop()
    state_mgr.tick_timer.stop()

    received_queues = []
    state_mgr.queue_updated.connect(lambda q: received_queues.append(q))

    state_mgr.fetch_queue()

    # Flush events to wait for background worker
    t0 = time.time()
    while not received_queues and (time.time() - t0 < 1.0):
        QCoreApplication.processEvents()
        time.sleep(0.01)

    state_mgr.thread_pool.waitForDone(500)

    assert len(received_queues) == 1, "queue_updated signal should be emitted upon completion"
    assert received_queues[0][0]["title"] == "Independent Track"
    assert mock_lyrics.fetch_lyrics.call_count == 0, "fetch_queue must not call lyrics client"


def test_state_manager_slow_lyrics_does_not_delay_queue():
    """Verify slow lyrics fetching does NOT delay or block queue retrieval."""
    _get_app()
    mock_spotify = MagicMock()
    mock_lyrics = MagicMock()

    lyrics_started = threading.Event()
    allow_lyrics_finish = threading.Event()

    def slow_fetch_lyrics(*args, **kwargs):
        lyrics_started.set()
        allow_lyrics_finish.wait(timeout=2.0)
        return {"synced": False, "lines": []}

    mock_lyrics.fetch_lyrics.side_effect = slow_fetch_lyrics
    mock_spotify.get_queue.return_value = [
        {"id": "q_fast", "title": "Fast Queue Arrival", "artist": "Fast Artist", "duration_ms": 180000}
    ]

    state_mgr = StateManager(mock_spotify, mock_lyrics)
    state_mgr.poll_timer.stop()
    state_mgr.tick_timer.stop()

    queue_results = []
    state_mgr.queue_updated.connect(lambda q: queue_results.append(q))

    playback_event = {
        "is_playing": True,
        "track_id": "new_track_async_1",
        "title": "Song Title",
        "artist": "Artist Name",
        "album": "Album Name",
        "duration_ms": 210000,
        "progress_ms": 5000
    }

    state_mgr._on_playback_received(playback_event)

    # Queue should be delivered quickly (< 350ms) while lyrics is still blocked
    t0 = time.time()
    while not queue_results and (time.time() - t0 < 0.35):
        QCoreApplication.processEvents()
        time.sleep(0.01)

    try:
        assert len(queue_results) > 0, (
            "Queue delivery was delayed or blocked by slow lyrics! Must arrive independently."
        )
        assert allow_lyrics_finish.is_set() is False, (
            "Queue must arrive BEFORE slow lyrics finishes executing"
        )
        assert queue_results[0][0]["title"] == "Fast Queue Arrival"
    finally:
        allow_lyrics_finish.set()
        state_mgr.thread_pool.waitForDone(1000)


def test_state_manager_lyrics_failure_does_not_prevent_queue():
    """Verify an exception or failure in lyrics fetching does not block or prevent queue retrieval."""
    _get_app()
    mock_spotify = MagicMock()
    mock_lyrics = MagicMock()

    mock_lyrics.fetch_lyrics.side_effect = RuntimeError("LRCLIB 504 Gateway Timeout")
    mock_spotify.get_queue.return_value = [
        {"id": "q_resilient", "title": "Resilient Track", "artist": "Resilient Artist", "duration_ms": 190000}
    ]

    state_mgr = StateManager(mock_spotify, mock_lyrics)
    state_mgr.poll_timer.stop()
    state_mgr.tick_timer.stop()

    queue_results = []
    state_mgr.queue_updated.connect(lambda q: queue_results.append(q))

    playback_event = {
        "is_playing": True,
        "track_id": "new_track_resilience_2",
        "title": "Failing Lyrics Song",
        "artist": "Failing Artist",
        "album": "Album",
        "duration_ms": 220000,
        "progress_ms": 2000
    }

    state_mgr._on_playback_received(playback_event)

    t0 = time.time()
    while not queue_results and (time.time() - t0 < 0.5):
        QCoreApplication.processEvents()
        time.sleep(0.01)

    state_mgr.thread_pool.waitForDone(500)

    assert len(queue_results) > 0, (
        "Queue was not delivered when lyrics client threw an unhandled exception!"
    )
    assert queue_results[0][0]["title"] == "Resilient Track"


def test_state_manager_queue_fetch_triggers():
    """Verify queue fetching is triggered on track change, initial connected playback, and on demand."""
    _get_app()
    mock_spotify = MagicMock()
    mock_lyrics = MagicMock()
    mock_lyrics.fetch_lyrics.return_value = None
    mock_spotify.get_queue.return_value = [{"id": "q1", "title": "T1"}]

    state_mgr = StateManager(mock_spotify, mock_lyrics)
    state_mgr.poll_timer.stop()
    state_mgr.tick_timer.stop()

    # 1. Trigger on demand: fetch_queue()
    mock_spotify.get_queue.reset_mock()
    state_mgr.fetch_queue()
    state_mgr.thread_pool.waitForDone(500)
    assert mock_spotify.get_queue.call_count >= 1, "fetch_queue() must trigger spotify.get_queue()"

    # 2. Trigger on initial connected playback (from disconnected / empty)
    state_mgr.current_track = None
    mock_spotify.get_queue.reset_mock()
    init_playback = {
        "is_playing": True,
        "track_id": "track_initial_connect",
        "title": "First Song",
        "artist": "Artist Init",
        "album": "Album Init",
        "duration_ms": 200000,
        "progress_ms": 0
    }
    state_mgr._on_playback_received(init_playback)
    state_mgr.thread_pool.waitForDone(500)
    assert mock_spotify.get_queue.call_count >= 1, (
        "Initial connected playback must trigger queue retrieval"
    )

    # 3. Trigger on song change
    mock_spotify.get_queue.reset_mock()
    changed_playback = {
        "is_playing": True,
        "track_id": "track_changed_second",
        "title": "Second Song",
        "artist": "Artist 2",
        "album": "Album 2",
        "duration_ms": 210000,
        "progress_ms": 0
    }
    state_mgr._on_playback_received(changed_playback)
    state_mgr.thread_pool.waitForDone(500)
    assert mock_spotify.get_queue.call_count >= 1, (
        "Song change must trigger queue retrieval"
    )


# ============================================================================
# Tier 3: UI Trigger Tests (R3)
# ============================================================================

def test_expanded_view_switch_tab_emits_refresh():
    """Verify switch_tab(1) in ExpandedView emits queue_tab.refresh_requested."""
    _get_app()
    view = ExpandedView()
    emitted_count = []
    view.queue_tab.refresh_requested.connect(lambda: emitted_count.append(True))

    # Switch to tab index 1 (Antrean)
    view.switch_tab(1)
    assert len(emitted_count) >= 1, (
        "ExpandedView.switch_tab(1) must emit self.queue_tab.refresh_requested"
    )

    # Switch to other tabs (0: Lirik, 2: Cari) should NOT trigger queue refresh
    emitted_count.clear()
    view.switch_tab(0)
    assert len(emitted_count) == 0, "Switching to tab 0 (Lirik) must not emit refresh_requested"

    view.switch_tab(2)
    assert len(emitted_count) == 0, "Switching to tab 2 (Cari) must not emit refresh_requested"


def test_queue_tab_btn_refresh_visible_and_emits():
    """Verify QueueTab.btn_refresh exists, is visible (not hidden), and emits refresh_requested."""
    _get_app()
    tab = QueueTab()
    assert hasattr(tab, "btn_refresh"), "QueueTab must have btn_refresh attribute"
    assert not tab.btn_refresh.isHidden(), (
        "QueueTab.btn_refresh must be visible (isHidden() is False) for manual user action"
    )

    refresh_emitted = []
    tab.refresh_requested.connect(lambda: refresh_emitted.append(True))

    tab.btn_refresh.click()
    assert len(refresh_emitted) == 1, (
        "Clicking QueueTab.btn_refresh must emit refresh_requested"
    )


def test_queue_ui_badge_and_list_update_on_delivery():
    """Verify queue count badge and list widget update accurately when queue items are delivered."""
    _get_app()
    view = ExpandedView()
    mock_items = [
        {"id": "q1", "title": "Song 1", "artist": "Artist 1", "duration_ms": 180000, "cover_url": "", "uri": "spotify:track:1"},
        {"id": "q2", "title": "Song 2", "artist": "Artist 2", "duration_ms": 190000, "cover_url": "", "uri": "spotify:track:2"},
        {"id": "q3", "title": "Song 3", "artist": "Artist 3", "duration_ms": 200000, "cover_url": "", "uri": "spotify:track:3"},
    ]

    # Deliver 3 tracks
    view.queue_tab.set_queue(mock_items)

    assert view.queue_tab.list_widget.count() == 3, (
        f"Expected 3 items in QueueTab list_widget, got {view.queue_tab.list_widget.count()}"
    )
    assert not view.queue_tab.list_widget.isHidden(), "list_widget should be visible when queue has items"
    assert hasattr(view, "queue_badge_lbl"), "ExpandedView must have queue_badge_lbl"
    assert view.queue_badge_lbl.text() == "3", (
        f"Queue badge text expected '3', got '{view.queue_badge_lbl.text()}'"
    )

    # Deliver empty queue
    view.queue_tab.set_queue([])
    assert view.queue_tab.list_widget.count() == 0, "Queue list should be empty"
    assert not view.queue_tab.empty_label.isHidden(), "Empty label should be visible (not hidden) when queue is empty"
    assert view.queue_tab.list_widget.isHidden(), "List widget should be hidden when queue is empty"
    assert view.queue_badge_lbl.text() == "0", (
        f"Queue badge text expected '0', got '{view.queue_badge_lbl.text()}'"
    )


# ============================================================================
# Main Execution Runner
# ============================================================================

ALL_TESTS = [
    # Tier 1
    test_get_queue_calls_ensure_connected,
    test_get_queue_album_none_and_non_dict,
    test_get_queue_artists_none_and_empty,
    test_get_queue_podcast_episode_show_metadata,
    test_get_queue_cover_image_fallbacks,
    test_get_queue_per_item_error_handling,
    test_get_queue_returns_up_to_30_tracks,
    # Tier 2
    test_state_manager_queue_fetching_independent_thread,
    test_state_manager_slow_lyrics_does_not_delay_queue,
    test_state_manager_lyrics_failure_does_not_prevent_queue,
    test_state_manager_queue_fetch_triggers,
    # Tier 3
    test_expanded_view_switch_tab_emits_refresh,
    test_queue_tab_btn_refresh_visible_and_emits,
    test_queue_ui_badge_and_list_update_on_delivery,
]


def run_all_tests():
    print("=" * 70)
    print("Running Queue Parsing, Concurrency, and UI Triggers Test Suite")
    print("=" * 70)

    passed = 0
    failed = 0
    failures = []

    for test_fn in ALL_TESTS:
        test_name = test_fn.__name__
        try:
            test_fn()
            print(f"[PASS] {test_name}")
            passed += 1
        except Exception as e:
            print(f"[FAIL] {test_name}: {e}")
            failed += 1
            failures.append((test_name, str(e)))

    print("=" * 70)
    print(f"Summary: {passed} PASSED, {failed} FAILED out of {len(ALL_TESTS)} tests")
    print("=" * 70)

    if failures:
        print("\nFailed Tests Details:")
        for idx, (name, err) in enumerate(failures, 1):
            print(f"  {idx}. {name}")
            print(f"     Reason: {err}")

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
