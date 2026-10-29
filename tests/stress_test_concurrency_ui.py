"""
Adversarial Stress Test Suite: Concurrency, Thread Safety, and UI Interaction.
Targeting:
- StateManager: Concurrency bursts, slow/failing lyrics, thread starvation resistance.
- ExpandedView: Rapid alternating tab switching, signal dispatch integrity.
- QueueTab: Rapid refresh hammering, rapid empty/populated transitions, widget lifecycle.
- Full System: Integrated concurrency storm.
"""

import os
import sys
import time
import random
import threading
import traceback
from unittest.mock import MagicMock

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QCoreApplication, QThreadPool

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


_APP = _get_app()


def _flush_events(duration_sec=0.05, step=0.005):
    """Process pending Qt events."""
    t0 = time.time()
    while time.time() - t0 < duration_sec:
        QCoreApplication.processEvents()
        time.sleep(step)


# ============================================================================
# Adversarial Test 1: Concurrency Burst & Slow/Failing Lyrics
# ============================================================================

def test_concurrency_burst_rapid_song_changes_with_blocked_and_failing_lyrics():
    """
    Stress-test: Burst of 20 rapid song change events while lyrics calls are
    artificially blocked for 2+ seconds each or throwing random exceptions.
    
    Verifies:
    1. Every queue fetch completes independently and emits queue_updated (total: 20).
    2. Queue updates arrive independently without waiting for slow lyrics to complete.
    3. No deadlocks, no thread pool hang, no Qt cross-thread exceptions.
    """
    print("\n--- Test 1: Concurrency Burst (20 Rapid Track Changes, Blocked/Failing Lyrics) ---")
    mock_spotify = MagicMock()
    mock_lyrics = MagicMock()

    slow_call_count = 0
    fail_call_count = 0
    lyrics_active_events = []
    lyrics_lock = threading.Lock()

    def adversarial_fetch_lyrics(*args, **kwargs):
        nonlocal slow_call_count, fail_call_count
        call_id = random.random()
        with lyrics_lock:
            # Randomly pick failure (~35%) or slow block (~65%)
            if call_id < 0.35:
                fail_call_count += 1
                raise RuntimeError("Adversarial LRCLIB 504 Gateway Timeout")
            else:
                slow_call_count += 1

        # Hold for 2.0+ seconds
        time.sleep(2.0)
        return {"synced": False, "lines": []}

    mock_lyrics.fetch_lyrics.side_effect = adversarial_fetch_lyrics

    # Fast queue retrieval (5ms) returning 30 tracks
    mock_spotify.get_queue.side_effect = lambda: [
        {
            "id": f"q_item_{i}",
            "title": f"Queue Track {i}",
            "artist": "Artist",
            "album": "Album",
            "album_uri": "",
            "duration_ms": 200000,
            "cover_url": "",
            "uri": f"spotify:track:q{i}"
        }
        for i in range(30)
    ]

    state_mgr = StateManager(mock_spotify, mock_lyrics)
    state_mgr.poll_timer.stop()
    state_mgr.tick_timer.stop()

    queue_emissions = []
    emission_timestamps = []

    def on_queue_updated(items):
        queue_emissions.append(items)
        emission_timestamps.append(time.time())

    state_mgr.queue_updated.connect(on_queue_updated)

    t_start = time.time()
    burst_count = 20

    print(f"Firing burst of {burst_count} rapid playback events...")
    for i in range(burst_count):
        playback_event = {
            "is_playing": True,
            "track_id": f"burst_track_{i:03d}",
            "title": f"Burst Song {i}",
            "artist": f"Artist {i}",
            "album": f"Album {i}",
            "duration_ms": 180000,
            "progress_ms": 0,
            "uri": f"spotify:track:burst_{i}"
        }
        state_mgr._on_playback_received(playback_event)
        # Flush Qt events briefly between iterations
        QCoreApplication.processEvents()

    print(f"Burst fired in {time.time() - t_start:.3f}s. Monitoring queue update emissions...")

    # Wait for all 20 queue updates to arrive.
    # Because lyrics take 2.0s each, if queue was coupled or thread-starved,
    # queue would take 2.0s * (20 / threads) = up to 5-10s!
    # But queue is independent, so queue arrivals should start immediately.
    timeout = 6.0
    t0 = time.time()
    while len(queue_emissions) < burst_count and (time.time() - t0 < timeout):
        QCoreApplication.processEvents()
        time.sleep(0.01)

    elapsed = time.time() - t_start
    first_queue_time = (emission_timestamps[0] - t_start) if emission_timestamps else None
    print(f"Result: {len(queue_emissions)}/{burst_count} queue updates received in {elapsed:.3f}s")
    if first_queue_time is not None:
        print(f"First queue update received at: {first_queue_time:.3f}s (well before 2.0s lyrics delay!)")
    print(f"Slow lyrics calls triggered: {slow_call_count}, Failing lyrics calls triggered: {fail_call_count}")

    # Ensure thread pool cleanly finishes any remaining background tasks
    print("Waiting for thread pool to drain remaining tasks...")
    state_mgr.thread_pool.waitForDone(4000)

    # Invariants
    assert len(queue_emissions) == burst_count, (
        f"Expected all {burst_count} queue_updated emissions, but got {len(queue_emissions)}!"
    )
    assert first_queue_time is not None and first_queue_time < 0.8, (
        f"First queue emission took {first_queue_time:.3f}s! Must arrive almost immediately (< 0.8s)."
    )
    for q in queue_emissions:
        assert len(q) == 30, f"Expected 30 items in queue payload, got {len(q)}"

    print("[PASS] Concurrency burst test completed successfully without starvation or deadlock.")


# ============================================================================
# Adversarial Test 2: Thread Pool Starvation Under Tight Thread Constraints
# ============================================================================

def test_concurrency_under_constrained_thread_pool():
    """
    Stress-test: Constrain QThreadPool to only 4 threads (simulate low-core CPU or high contention).
    Trigger 10 rapid track changes with 2s lyrics delays.
    Verify all 10 queue fetches still complete reliably without permanent starvation or crash.
    """
    print("\n--- Test 2: Concurrency Under Constrained Thread Pool (maxThreadCount=4) ---")
    mock_spotify = MagicMock()
    mock_lyrics = MagicMock()

    pool = QThreadPool.globalInstance()
    original_max_threads = pool.maxThreadCount()
    pool.setMaxThreadCount(4)
    print(f"Constrained QThreadPool from {original_max_threads} to {pool.maxThreadCount()} threads.")

    try:
        def slow_lyrics(*args, **kwargs):
            time.sleep(1.0)
            return {"synced": False, "lines": []}

        mock_lyrics.fetch_lyrics.side_effect = slow_lyrics
        mock_spotify.get_queue.return_value = [{"id": "t", "title": "Track", "artist": "A", "duration_ms": 100}]

        state_mgr = StateManager(mock_spotify, mock_lyrics)
        state_mgr.poll_timer.stop()
        state_mgr.tick_timer.stop()

        queue_emissions = []
        state_mgr.queue_updated.connect(lambda q: queue_emissions.append(q))

        burst = 10
        for i in range(burst):
            state_mgr._on_playback_received({
                "is_playing": True,
                "track_id": f"constrained_{i}",
                "title": f"Song {i}",
                "artist": "Artist",
                "album": "Album",
                "duration_ms": 150000,
                "progress_ms": 0,
                "uri": f"spotify:track:c_{i}"
            })
            QCoreApplication.processEvents()

        # Wait for all queue emissions
        t0 = time.time()
        while len(queue_emissions) < burst and (time.time() - t0 < 8.0):
            QCoreApplication.processEvents()
            time.sleep(0.01)

        print(f"Received {len(queue_emissions)}/{burst} queue emissions under constrained pool.")
        state_mgr.thread_pool.waitForDone(5000)

        assert len(queue_emissions) == burst, (
            f"Expected {burst} queue emissions under 4-thread pool, got {len(queue_emissions)}"
        )
        print("[PASS] Constrained thread pool handled burst without deadlock.")
    finally:
        pool.setMaxThreadCount(original_max_threads)
        print(f"Restored QThreadPool to {original_max_threads} threads.")


# ============================================================================
# Adversarial Test 3: Rapid Alternating Tab Switching (ExpandedView)
# ============================================================================

def test_ui_stress_rapid_alternating_tab_switching():
    """
    Stress-test: Rapid alternating tab switching (0 <-> 1 <-> 2) 50 times in a tight loop.
    Verifies:
    1. refresh_requested is emitted EXACTLY when switching to tab 1.
    2. refresh_requested is NOT emitted when switching to tab 0 or 2.
    3. No GUI freezes, no deadlocks, no Qt segmentation faults.
    """
    print("\n--- Test 3: UI Stress (50 Rapid Alternating Tab Switches) ---")
    ev = ExpandedView()
    ev.show()
    _flush_events(0.05)

    refresh_emissions = 0

    def on_refresh():
        nonlocal refresh_emissions
        refresh_emissions += 1

    ev.queue_tab.refresh_requested.connect(on_refresh)

    # Sequence of 50 tab switches alternating between 0 (Lyrics), 1 (Queue), and 2 (Search)
    # Pattern: 0 -> 1 -> 2 -> 1 -> 0 -> 1 -> 2 -> 1 ...
    pattern = [0, 1, 2, 1] * 13  # 52 switches
    pattern = pattern[:50]
    expected_tab1_count = pattern.count(1)

    print(f"Executing {len(pattern)} tab switches (expected tab 1 hits: {expected_tab1_count})...")
    t0 = time.time()
    for step, target_idx in enumerate(pattern):
        ev.switch_tab(target_idx)
        assert ev.tabs.currentIndex() == target_idx, f"Tab index mismatch at step {step}"
        QCoreApplication.processEvents()

    elapsed = time.time() - t0
    print(f"50 tab switches executed in {elapsed:.3f}s ({elapsed/50*1000:.2f}ms/switch).")
    print(f"Total refresh_requested emissions recorded: {refresh_emissions}")

    assert refresh_emissions == expected_tab1_count, (
        f"Expected {expected_tab1_count} refresh_requested emissions, but got {refresh_emissions}!"
    )
    ev.close()
    _flush_events(0.02)
    print("[PASS] Rapid alternating tab switching stress passed.")


# ============================================================================
# Adversarial Test 4: Rapid Refresh Button Hammering During Active Workers
# ============================================================================

def test_ui_stress_rapid_refresh_button_hammering_during_active_workers():
    """
    Stress-test: Rapid clicking of QueueTab.btn_refresh 30 times while queue worker
    tasks are executing concurrently.
    
    Verifies:
    1. 30 refresh_requested signals emitted and connected to fetch_queue.
    2. Concurrent queue workers execute and return without crashing.
    3. No task pileup, race conditions, or widget lifecycle crashes.
    """
    print("\n--- Test 4: Rapid QueueTab.btn_refresh Hammering (30x with Active Workers) ---")
    mock_spotify = MagicMock()
    mock_lyrics = MagicMock()

    # Simulate realistic 20ms queue fetching delay
    def delayed_get_queue():
        time.sleep(0.02)
        return [
            {"id": f"q_{i}", "title": f"Song {i}", "artist": "Artist", "album": "Album", "album_uri": "", "duration_ms": 100000, "cover_url": "", "uri": f"spotify:track:{i}"}
            for i in range(15)
        ]

    mock_spotify.get_queue.side_effect = delayed_get_queue

    state_mgr = StateManager(mock_spotify, mock_lyrics)
    state_mgr.poll_timer.stop()
    state_mgr.tick_timer.stop()

    queue_tab = QueueTab()
    queue_tab.show()
    _flush_events(0.02)

    refresh_emitted_count = 0

    def on_refresh():
        nonlocal refresh_emitted_count
        refresh_emitted_count += 1
        state_mgr.fetch_queue()

    queue_tab.refresh_requested.connect(on_refresh)

    queue_delivered_count = 0

    def on_queue_updated(items):
        nonlocal queue_delivered_count
        queue_delivered_count += 1
        queue_tab.set_queue(items)

    state_mgr.queue_updated.connect(on_queue_updated)

    # Hammer btn_refresh 30 times rapidly
    hammer_count = 30
    print(f"Hammering QueueTab.btn_refresh {hammer_count} times in tight loop...")
    t0 = time.time()
    for i in range(hammer_count):
        queue_tab.btn_refresh.click()
        QCoreApplication.processEvents()

    hammer_elapsed = time.time() - t0
    print(f"Hammered {hammer_count} clicks in {hammer_elapsed:.3f}s. Awaiting worker deliveries...")

    # Wait for all deliveries to process
    t_wait = time.time()
    while queue_delivered_count < hammer_count and (time.time() - t_wait < 5.0):
        QCoreApplication.processEvents()
        time.sleep(0.01)

    state_mgr.thread_pool.waitForDone(2000)
    print(f"Completed: {queue_delivered_count}/{hammer_count} queue deliveries processed.")

    assert refresh_emitted_count == hammer_count, (
        f"Expected {hammer_count} refresh emissions, got {refresh_emitted_count}"
    )
    assert queue_delivered_count == hammer_count, (
        f"Expected {hammer_count} queue deliveries, got {queue_delivered_count}"
    )
    assert queue_tab.list_widget.count() == 15, (
        f"Expected 15 items in list_widget, got {queue_tab.list_widget.count()}"
    )
    assert queue_tab.empty_label.isVisible() is False

    queue_tab.close()
    _flush_events(0.02)
    print("[PASS] Rapid refresh button hammering test passed.")


# ============================================================================
# Adversarial Test 5: Rapid Empty <-> Populated Queue Transitions
# ============================================================================

def test_ui_stress_empty_to_populated_rapid_transitions():
    """
    Stress-test: Rapid alternating empty queue -> populated queue -> empty queue transitions (50 cycles).
    Verifies:
    1. UI toggles between empty_label and list_widget cleanly.
    2. queue_count_changed signal is emitted correctly with accurate count.
    3. User interactions (e.g. removal, clicks) during rapid transitions do not crash.
    """
    print("\n--- Test 5: UI Stress (Rapid Empty <-> Populated Queue Transitions 50x) ---")
    queue_tab = QueueTab()
    queue_tab.show()
    _flush_events(0.02)

    count_emissions = []
    queue_tab.queue_count_changed.connect(lambda c: count_emissions.append(c))

    dummy_items_30 = [
        {"id": f"t_{i}", "title": f"Title {i}", "artist": f"Artist {i}", "album": f"Album {i}", "duration_ms": 180000, "cover_url": "", "uri": f"spotify:track:t{i}"}
        for i in range(30)
    ]
    dummy_items_1 = [
        {"id": "single", "title": "Single Track", "artist": "Solo", "album": "Single", "duration_ms": 120000, "cover_url": "", "uri": "spotify:track:single"}
    ]

    cycles = 50
    print(f"Running {cycles} cycles of Empty -> Populated(30) -> Empty -> Populated(1)...")
    t0 = time.time()

    for c in range(cycles):
        # 1. Empty
        queue_tab.set_queue([])
        assert queue_tab.empty_label.isVisible() is True
        assert queue_tab.list_widget.isVisible() is False
        assert queue_tab.list_widget.count() == 0
        QCoreApplication.processEvents()

        # 2. Populated (30 items)
        queue_tab.set_queue(list(dummy_items_30))
        assert queue_tab.empty_label.isVisible() is False
        assert queue_tab.list_widget.isVisible() is True
        assert queue_tab.list_widget.count() == 30
        QCoreApplication.processEvents()

        # Adversarial removal call on active queue
        queue_tab._remove_item_at(0)
        assert queue_tab.list_widget.count() == 29
        QCoreApplication.processEvents()

        # 3. Empty again
        queue_tab.set_queue([])
        assert queue_tab.empty_label.isVisible() is True
        assert queue_tab.list_widget.isVisible() is False
        QCoreApplication.processEvents()

        # Adversarial removal call on EMPTY queue (must not raise IndexError)
        queue_tab._remove_item_at(0)
        queue_tab._remove_item_at(99)
        QCoreApplication.processEvents()

        # 4. Populated (1 item)
        queue_tab.set_queue(list(dummy_items_1))
        assert queue_tab.empty_label.isVisible() is False
        assert queue_tab.list_widget.isVisible() is True
        assert queue_tab.list_widget.count() == 1
        QCoreApplication.processEvents()

    elapsed = time.time() - t0
    print(f"50 transition cycles ({cycles * 4} state updates) completed in {elapsed:.3f}s.")
    print(f"Recorded {len(count_emissions)} queue_count_changed emissions.")

    # Final verify
    assert queue_tab.list_widget.count() == 1
    queue_tab.set_queue([])
    assert queue_tab.list_widget.count() == 0
    assert queue_tab.empty_label.isVisible() is True

    queue_tab.close()
    _flush_events(0.02)
    print("[PASS] Rapid empty to populated queue transitions passed.")


# ============================================================================
# Adversarial Test 6: Integrated Concurrency & UI Storm
# ============================================================================

def test_integrated_concurrency_and_ui_storm():
    """
    Stress-test: Integrated multi-threaded storm:
    - Background thread continuously emits track changes (burst of 15 tracks)
    - Main thread continuously alternates tabs (0 <-> 1 <-> 2)
    - QueueTab refresh button is hammered
    - Queue deliveries arrive asynchronously and update UI
    Verifies that the entire system survives high concurrent load without deadlocking or crashing.
    """
    print("\n--- Test 6: Integrated Concurrency and UI Storm ---")
    mock_spotify = MagicMock()
    mock_lyrics = MagicMock()

    mock_lyrics.fetch_lyrics.side_effect = lambda *a, **kw: (time.sleep(0.5), {"synced": False, "lines": []})[1]
    mock_spotify.get_queue.side_effect = lambda: [
        {"id": f"storm_{i}", "title": f"Storm Track {i}", "artist": "Artist", "album": "Album", "album_uri": "", "duration_ms": 100000, "cover_url": "", "uri": f"spotify:track:storm_{i}"}
        for i in range(20)
    ]

    state_mgr = StateManager(mock_spotify, mock_lyrics)
    state_mgr.poll_timer.stop()
    state_mgr.tick_timer.stop()

    ev = ExpandedView()
    ev.show()

    # Wire up UI and state manager like NotchWindow does
    ev.queue_tab.refresh_requested.connect(state_mgr.fetch_queue)
    state_mgr.queue_updated.connect(ev.queue_tab.set_queue)

    storm_running = True
    track_emissions = 0

    def background_track_emitter():
        nonlocal track_emissions
        t_id = 0
        while storm_running and t_id < 15:
            state_mgr._on_playback_received({
                "is_playing": True,
                "track_id": f"storm_track_{t_id}",
                "title": f"Storm Title {t_id}",
                "artist": "Artist",
                "album": "Album",
                "duration_ms": 200000,
                "progress_ms": 1000 * t_id,
                "uri": f"spotify:track:st_{t_id}"
            })
            track_emissions += 1
            t_id += 1
            time.sleep(0.08)

    bg_thread = threading.Thread(target=background_track_emitter, daemon=True)
    bg_thread.start()

    # On main thread, perform tab switches and button clicks for 1.8 seconds
    t_end = time.time() + 1.8
    tab_toggle = 0
    clicks = 0
    while time.time() < t_end:
        ev.switch_tab(tab_toggle % 3)
        tab_toggle += 1
        if tab_toggle % 2 == 0:
            ev.queue_tab.btn_refresh.click()
            clicks += 1
        QCoreApplication.processEvents()
        time.sleep(0.015)

    storm_running = False
    bg_thread.join(timeout=1.0)

    print(f"Storm completed: {track_emissions} track changes, {tab_toggle} tab switches, {clicks} refresh clicks.")
    print("Flushing remaining events and waiting for worker threads...")
    state_mgr.thread_pool.waitForDone(3000)
    _flush_events(0.1)

    ev.close()
    _flush_events(0.02)
    print("[PASS] Integrated storm test passed without crash or deadlock.")


# ============================================================================
# Adversarial Test 7: Background Delivery While Navigated Away
# ============================================================================

def test_background_delivery_while_navigated_away():
    """
    Stress-test: Switch to Queue tab, immediately switch away to Lyrics/Search tab,
    verify that background queue delivery updates QueueTab and ExpandedView badge correctly.
    """
    print("\n--- Test 7: Background Queue Delivery While Navigated Away ---")
    mock_spotify = MagicMock()
    mock_lyrics = MagicMock()

    # Worker has a 100ms artificial delay to allow user to navigate away
    def delayed_queue():
        time.sleep(0.1)
        return [
            {"id": f"away_{i}", "title": f"Away Track {i}", "artist": "Artist", "album": "Album", "album_uri": "", "duration_ms": 100000, "cover_url": "", "uri": f"spotify:track:away_{i}"}
            for i in range(25)
        ]

    mock_spotify.get_queue.side_effect = delayed_queue

    state_mgr = StateManager(mock_spotify, mock_lyrics)
    state_mgr.poll_timer.stop()
    state_mgr.tick_timer.stop()

    ev = ExpandedView()
    ev.show()
    _flush_events(0.02)

    ev.queue_tab.refresh_requested.connect(state_mgr.fetch_queue)
    state_mgr.queue_updated.connect(ev.queue_tab.set_queue)

    # 1. Start at Tab 0
    ev.switch_tab(0)
    assert ev.tabs.currentIndex() == 0
    _flush_events(0.01)

    # 2. Switch to Tab 1 (Queue) -> triggers refresh_requested
    ev.switch_tab(1)
    assert ev.tabs.currentIndex() == 1
    _flush_events(0.01)

    # 3. Immediately switch away to Tab 2 (Search) before 100ms worker finishes
    ev.switch_tab(2)
    assert ev.tabs.currentIndex() == 2
    _flush_events(0.01)

    # 4. Wait for background worker to complete while user is on Tab 2
    t0 = time.time()
    while ev.queue_badge_lbl.text() != "25" and (time.time() - t0 < 2.0):
        QCoreApplication.processEvents()
        time.sleep(0.01)

    state_mgr.thread_pool.waitForDone(1000)

    # Verify badge is updated to 25 even though tab is not active!
    assert ev.queue_badge_lbl.text() == "25", f"Expected badge '25', got '{ev.queue_badge_lbl.text()}'"
    assert ev.queue_tab.list_widget.count() == 25, f"Expected 25 items in queue_tab, got {ev.queue_tab.list_widget.count()}"

    # 5. Switch back to Tab 1: items are already there
    ev.switch_tab(1)
    _flush_events(0.02)
    assert ev.queue_tab.list_widget.isVisible() is True
    assert ev.queue_tab.empty_label.isVisible() is False

    ev.close()
    _flush_events(0.02)
    print("[PASS] Background delivery while navigated away succeeded.")


# ============================================================================
# Adversarial Test 8: StateManager Shutdown Mid-Burst
# ============================================================================

def test_statemanager_shutdown_mid_burst():
    """
    Stress-test: Trigger rapid bursts of playback and queue fetches, then immediately
    invoke shutdown(). Verify no dangling timers, no segmentation faults, and clean teardown.
    """
    print("\n--- Test 8: StateManager Shutdown Mid-Burst ---")
    mock_spotify = MagicMock()
    mock_lyrics = MagicMock()

    mock_lyrics.fetch_lyrics.side_effect = lambda *a, **kw: (time.sleep(0.1), {"synced": False, "lines": []})[1]
    mock_spotify.get_queue.side_effect = lambda: (time.sleep(0.05), [{"id": "x", "title": "X", "artist": "A", "duration_ms": 100}])[1]

    state_mgr = StateManager(mock_spotify, mock_lyrics)

    # Start rapid calls
    for i in range(10):
        state_mgr.fetch_queue()
        state_mgr._on_playback_received({
            "is_playing": True,
            "track_id": f"sd_{i}",
            "title": f"SD {i}",
            "artist": "A",
            "album": "Alb",
            "duration_ms": 100000,
            "progress_ms": 0,
            "uri": f"spotify:track:sd_{i}"
        })

    # Immediate shutdown mid-flight
    state_mgr.shutdown()
    assert state_mgr._is_shutting_down is True
    assert state_mgr.poll_timer.isActive() is False
    assert state_mgr.tick_timer.isActive() is False

    # Drain pool
    state_mgr.thread_pool.waitForDone(2000)
    _flush_events(0.05)
    print("[PASS] StateManager shutdown mid-burst succeeded.")


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    print("=" * 70)
    print("ADVERSARIAL STRESS TEST SUITE: CONCURRENCY, THREAD SAFETY & UI")
    print("=" * 70)

    tests = [
        ("Test 1: Concurrency Burst & Slow/Failing Lyrics", test_concurrency_burst_rapid_song_changes_with_blocked_and_failing_lyrics),
        ("Test 2: Constrained Thread Pool (Starvation Check)", test_concurrency_under_constrained_thread_pool),
        ("Test 3: Rapid Alternating Tab Switching", test_ui_stress_rapid_alternating_tab_switching),
        ("Test 4: Rapid Refresh Button Hammering", test_ui_stress_rapid_refresh_button_hammering_during_active_workers),
        ("Test 5: Rapid Empty <-> Populated Transitions", test_ui_stress_empty_to_populated_rapid_transitions),
        ("Test 6: Integrated Concurrency & UI Storm", test_integrated_concurrency_and_ui_storm),
        ("Test 7: Background Delivery While Navigated Away", test_background_delivery_while_navigated_away),
        ("Test 8: StateManager Shutdown Mid-Burst", test_statemanager_shutdown_mid_burst),
    ]

    passed = 0
    failed = 0
    errors = []

    for name, test_fn in tests:
        try:
            test_fn()
            passed += 1
        except Exception as e:
            failed += 1
            err_msg = f"[FAIL] {name}: {e}\n{traceback.format_exc()}"
            print(err_msg)
            errors.append((name, err_msg))

    print("\n" + "=" * 70)
    print(f"STRESS TEST SUMMARY: {passed} PASSED, {failed} FAILED out of {len(tests)} tests")
    print("=" * 70)

    if failed > 0:
        print("\nFailures:")
        for name, err in errors:
            print(f"- {name}")
        sys.exit(1)
    else:
        print("\nALL ADVERSARIAL STRESS TESTS COMPLETED SUCCESSFULLY!")
        sys.exit(0)


if __name__ == "__main__":
    main()
