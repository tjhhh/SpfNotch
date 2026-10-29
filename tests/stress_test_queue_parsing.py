"""
Adversarial Stress Test Suite for SpotifyClient.get_queue()
Role: Empirical Challenger
Target: app/core/spotify_client.py

Tests:
1. Disconnected client fallback state.
2. Falsy and malformed root responses (None, {}, int, string, list, bool).
3. Malformed "queue" field (None, non-list, empty list, primitives).
4. Deeply nested nulls (album, artists, show, images, urls, names).
5. Unexpected types for album (string, int, float, list, bool, dict with non-string fields).
6. Unexpected types for artists (int, string, dict, list with None, list with numbers, non-string name e.g. 8888).
7. Unexpected types for images (non-list, list of primitives, dicts without 'url', non-string url e.g. 12345).
8. Primitive field nulls and invalid types (name=None, id=None, duration_ms=None).
9. High track count stress (100, 1,000 and 10,000 items) for memory leak & latency profiling.
10. Chaotic queues (50 items alternating corrupt and valid items).
11. 30 valid tracks extraction with leading corrupt items (100 items with 15 leading corrupt).
12. Spotify API exception injection (500 Error, TimeoutError, ConnectionResetError).
13. Cache mutation and state integrity (_track_album_map).
"""

import os
import sys
import time
import tracemalloc
from unittest.mock import MagicMock

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.core.spotify_client import SpotifyClient


def _create_mock_client():
    config_path = os.path.join(BASE_DIR, "config.json")
    client = SpotifyClient(config_path)
    client.sp = MagicMock()
    client.is_connected = True
    client._ensure_connected = MagicMock(return_value=True)
    return client


def test_disconnected_fallback():
    """Verify disconnected state returns 3 demo tracks and does not call sp.queue."""
    client = _create_mock_client()
    client._ensure_connected.return_value = False

    res = client.get_queue()
    assert not client.sp.queue.called, "sp.queue() was called while disconnected"
    assert isinstance(res, list), f"Expected list, got {type(res)}"
    assert len(res) == 3, f"Expected 3 demo items, got {len(res)}"
    expected_keys = {"id", "title", "artist", "duration_ms", "cover_url", "uri"}
    for item in res:
        for k in expected_keys:
            assert k in item, f"Missing key {k} in demo fallback item"
    print("  [PASS] test_disconnected_fallback")


def test_falsy_and_malformed_root_responses():
    """Verify various falsy and malformed root responses return [] without crashing."""
    falsy_roots = [
        None,
        {},
        [],
        "invalid string",
        12345,
        False,
        True,
        {"some_other_key": 42},
        {"queue": None},
        {"queue": []},
        {"queue": 100},
        {"queue": "not-a-list"},
        {"queue": False},
        {"queue": {}},
    ]

    client = _create_mock_client()
    for root in falsy_roots:
        client.sp.queue.return_value = root
        try:
            res = client.get_queue()
            assert isinstance(res, list), f"Root payload {root!r} returned non-list {type(res)}"
            assert len(res) == 0, f"Root payload {root!r} returned non-empty queue: {res}"
        except Exception as e:
            raise AssertionError(f"Payload {root!r} raised unhandled exception: {e}")

    print("  [PASS] test_falsy_and_malformed_root_responses (14 payloads)")


def test_deeply_nested_nulls():
    """Verify payload with nulls at every level parses without AttributeError/TypeError."""
    client = _create_mock_client()
    item_with_nulls = {
        "id": "null_test_1",
        "name": "Null Paradise",
        "album": None,
        "artists": None,
        "show": None,
        "images": None,
        "duration_ms": 120000,
        "uri": "spotify:track:null_1"
    }
    item_with_nested_nulls = {
        "id": "null_test_2",
        "name": "Deep Nulls",
        "album": {
            "name": None,
            "uri": None,
            "images": None
        },
        "artists": [
            {"name": None, "id": None},
            None
        ],
        "show": {
            "name": None,
            "publisher": None,
            "images": None
        },
        "images": [None, {"url": None}],
        "duration_ms": None,
        "uri": None
    }

    client.sp.queue.return_value = {"queue": [item_with_nulls, item_with_nested_nulls]}
    res = client.get_queue()

    assert len(res) == 2, f"Expected 2 parsed tracks, got {len(res)}"
    assert res[0]["title"] == "Null Paradise"
    assert res[0]["artist"] == ""
    assert res[0]["album"] == ""
    assert res[0]["cover_url"] == ""

    assert res[1]["title"] == "Deep Nulls"
    assert res[1]["artist"] == ""
    assert res[1]["album"] == ""
    assert res[1]["cover_url"] == ""
    assert res[1]["uri"] == ""
    print("  [PASS] test_deeply_nested_nulls")


def test_unexpected_album_types():
    """Verify various corrupt types for 'album' do not cause crashes."""
    client = _create_mock_client()
    corrupt_albums = [
        "String Album",
        12345,
        3.14159,
        ["album", "in", "list"],
        True,
        False,
        {},
        {"name": 9999, "uri": ["bad", "uri"], "images": "not-a-list"},
        {"name": None, "uri": None, "images": 123},
        {"non_standard_key": "some_value"}
    ]

    items = []
    for idx, alb in enumerate(corrupt_albums):
        items.append({
            "id": f"trk_alb_{idx}",
            "name": f"Track Album {idx}",
            "album": alb,
            "artists": [{"name": "Artist"}],
            "duration_ms": 180000,
            "uri": f"spotify:track:trk_alb_{idx}"
        })

    client.sp.queue.return_value = {"queue": items}
    res = client.get_queue()
    assert len(res) == len(corrupt_albums), f"Expected {len(corrupt_albums)} tracks, got {len(res)}"
    for item in res:
        assert isinstance(item["album"], str)
        assert isinstance(item["album_uri"], str)
        assert isinstance(item["cover_url"], str)

    print("  [PASS] test_unexpected_album_types (10 variations)")


def test_unexpected_artists_types():
    """Verify various corrupt types for 'artists' do not cause crashes or drop items."""
    client = _create_mock_client()
    corrupt_artists = [
        "Artist as plain string",
        12345,
        {"name": "Artist in dictionary"},
        [None, None],
        ["plain string in list", 999, 3.14],
        [{"name": None}, {"id": "123"}],
        [{"name": 8888}],  # Non-string artist name
        [],
        None,
        True,
        False
    ]

    items = []
    for idx, art in enumerate(corrupt_artists):
        items.append({
            "id": f"trk_art_{idx}",
            "name": f"Track Artist {idx}",
            "album": {"name": "Valid Album"},
            "artists": art,
            "duration_ms": 180000,
            "uri": f"spotify:track:trk_art_{idx}"
        })

    client.sp.queue.return_value = {"queue": items}
    res = client.get_queue()

    # Empirical check:
    # Any item with non-string name (e.g. 8888) should not cause an unhandled exception or dropped track
    failed_items = []
    for idx, art in enumerate(corrupt_artists):
        expected_id = f"trk_art_{idx}"
        matching = [t for t in res if t["id"] == expected_id]
        if not matching:
            failed_items.append((idx, art))

    if failed_items:
        raise AssertionError(f"Items were dropped due to artist parsing exceptions: {failed_items}")

    for item in res:
        assert isinstance(item["artist"], str), f"Artist was {type(item['artist'])}"
        assert isinstance(item["title"], str)

    print("  [PASS] test_unexpected_artists_types (11 variations)")


def test_unexpected_images_structures():
    """Verify various corrupt image structures do not crash and cover_url is always str."""
    client = _create_mock_client()
    corrupt_image_payloads = [
        {"album": {"images": "http://not-a-list.com/img.jpg"}},
        {"album": {"images": 12345}},
        {"album": {"images": None}},
        {"album": {"images": ["plain_string_url", 123, None]}},
        {"album": {"images": [{"width": 300, "height": 300}]}},  # missing 'url'
        {"album": {"images": [{"url": None}]}},
        {"album": {"images": [{"url": 12345}]}},  # non-string URL
        {"images": "direct_item_image_string"},
        {"images": [{"url": "http://valid.direct/img.jpg"}]},
        {"show": {"images": "string_show_image"}},
        {"show": {"images": [{"url": "http://valid.show/img.jpg"}]}},
        {"album": {"images": []}, "images": [], "show": {"images": []}},
    ]

    items = []
    for idx, payload in enumerate(corrupt_image_payloads):
        item = {
            "id": f"trk_img_{idx}",
            "name": f"Track Image {idx}",
            "duration_ms": 150000,
            "uri": f"spotify:track:trk_img_{idx}"
        }
        item.update(payload)
        items.append(item)

    client.sp.queue.return_value = {"queue": items}
    res = client.get_queue()
    assert len(res) == len(corrupt_image_payloads), f"Expected {len(corrupt_image_payloads)} tracks, got {len(res)}"
    for idx, item in enumerate(res):
        assert isinstance(item["cover_url"], str), (
            f"Item {idx} (payload {corrupt_image_payloads[idx]}): cover_url was {type(item['cover_url'])} ({item['cover_url']!r}), expected str"
        )

    # Check direct image and show image resolution
    assert res[8]["cover_url"] == "http://valid.direct/img.jpg"
    assert res[10]["cover_url"] == "http://valid.show/img.jpg"

    print("  [PASS] test_unexpected_images_structures (12 variations)")


def test_primitive_field_nulls_and_types():
    """Verify that title, id, and duration_ms always conform to expected types (str, int)."""
    client = _create_mock_client()
    items = [
        {"id": None, "name": None, "duration_ms": None, "uri": None},
        {"id": 12345, "name": 67890, "duration_ms": "not_an_int", "uri": 99999},
        {"id": "t_normal", "name": "Normal Track", "duration_ms": 200000, "uri": "spotify:track:normal"}
    ]
    client.sp.queue.return_value = {"queue": items}
    res = client.get_queue()

    assert len(res) == 3
    # Check item 0
    assert isinstance(res[0]["title"], str), f"Item 0 title was {type(res[0]['title'])} ({res[0]['title']!r}), expected str"
    assert isinstance(res[0]["id"], str), f"Item 0 id was {type(res[0]['id'])}, expected str"
    assert isinstance(res[0]["duration_ms"], int), f"Item 0 duration_ms was {type(res[0]['duration_ms'])}, expected int"
    print("  [PASS] test_primitive_field_nulls_and_types")


def test_chaotic_interleaved_queue():
    """Verify a chaotic queue where odd items are valid and even items are corrupt."""
    client = _create_mock_client()
    items = []
    expected_valid_ids = []
    accepted_count = 0

    for i in range(50):
        if i % 2 == 0:
            # Corrupt payload: non-dict, missing fields, invalid types
            if i % 6 == 0:
                items.append(None)
            elif i % 6 == 2:
                items.append("completely_invalid_string_item")
            else:
                items.append({
                    "corrupt_field": [1, 2, 3],
                    "album": False,
                    "artists": "invalid"
                })
                if accepted_count < 30:
                    accepted_count += 1
        else:
            valid_id = f"valid_trk_{i}"
            items.append({
                "id": valid_id,
                "name": f"Valid Song {i}",
                "artists": [{"name": f"Artist {i}"}],
                "album": {"name": f"Album {i}", "uri": f"spotify:album:{i}"},
                "duration_ms": 200000,
                "uri": f"spotify:track:{valid_id}"
            })
            if accepted_count < 30:
                accepted_count += 1
                expected_valid_ids.append(valid_id)

    client.sp.queue.return_value = {"queue": items}
    res = client.get_queue()

    res_ids = [t["id"] for t in res if t["id"].startswith("valid_trk_")]
    assert len(res) == 30, f"Expected 30 total items returned, got {len(res)}"
    assert res_ids == expected_valid_ids, f"Expected {expected_valid_ids}, got {res_ids}"

    print(f"  [PASS] test_chaotic_interleaved_queue (50 items, {len(res)} survived, valid tracks intact)")


def test_thirty_valid_tracks_extraction_with_leading_corrupt():
    """Verify that a queue with leading corrupt items still returns 30 valid tracks if available."""
    client = _create_mock_client()
    items = []

    # 15 corrupt / non-dict items first
    for i in range(15):
        if i % 3 == 0:
            items.append(None)
        elif i % 3 == 1:
            items.append("invalid_corrupt_item_payload")
        else:
            items.append(12345)

    # 35 valid tracks next
    for i in range(35):
        items.append({
            "id": f"valid_trk_{i}",
            "name": f"Song {i}",
            "artists": [{"name": f"Artist {i}"}],
            "album": {"name": f"Album {i}"},
            "duration_ms": 200000,
            "uri": f"spotify:track:valid_{i}"
        })

    client.sp.queue.return_value = {"queue": items}
    res = client.get_queue()

    valid_returned = [t for t in res if t["id"].startswith("valid_trk_")]
    # Note: If the implementation sliced res["queue"][:30], it only examined 15 corrupt + 15 valid = 15 valid returned!
    # Even though there are 35 valid tracks available in the queue.
    if len(valid_returned) < 30:
        raise AssertionError(
            f"Premature slicing: Expected 30 valid tracks from 50 total items, got {len(valid_returned)}. "
            f"Implementation sliced raw queue [:30] before validating/filtering items."
        )

    print(f"  [PASS] test_thirty_valid_tracks_extraction_with_leading_corrupt (got {len(valid_returned)} valid tracks)")


def test_high_volume_stress_and_memory():
    """Verify scaling behavior and memory efficiency with 100, 1,000 and 10,000 items."""
    client = _create_mock_client()

    for count in [100, 1000, 10000]:
        large_queue = []
        for i in range(count):
            large_queue.append({
                "id": f"track_{i}",
                "name": f"Track Title {i}",
                "artists": [{"name": f"Artist {i}", "id": f"art_{i}"}],
                "album": {
                    "name": f"Album {i}",
                    "uri": f"spotify:album:{i}",
                    "images": [
                        {"url": f"https://i.scdn.co/image/{i}_640", "height": 640, "width": 640},
                        {"url": f"https://i.scdn.co/image/{i}_300", "height": 300, "width": 300},
                        {"url": f"https://i.scdn.co/image/{i}_64", "height": 64, "width": 64}
                    ]
                },
                "duration_ms": 180000 + i,
                "uri": f"spotify:track:{i}"
            })

        client.sp.queue.return_value = {"queue": large_queue}

        tracemalloc.start()
        start_time = time.perf_counter()

        res = client.get_queue()

        duration_ms = (time.perf_counter() - start_time) * 1000
        current_mem, peak_mem = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        assert len(res) == 30, f"Expected strictly 30 tracks for count {count}, got {len(res)}"
        assert res[0]["id"] == "track_0"
        assert res[29]["id"] == "track_29"
        # Latency check: should be under 50ms since it slices [:30] before looping
        assert duration_ms < 50.0, f"Execution too slow: {duration_ms:.2f} ms for {count} items"

        print(f"  [PASS] test_high_volume_stress count={count}: time={duration_ms:.2f}ms, peak_mem={peak_mem/1024:.1f}KB, returned={len(res)}")


def test_api_exception_injection():
    """Verify that network/API exceptions raised by sp.queue() return [] without bubbling."""
    client = _create_mock_client()

    exceptions_to_test = [
        Exception("Spotify 500 Internal Server Error"),
        ConnectionResetError("Connection forcibly closed by peer"),
        TimeoutError("Connection timed out waiting for Spotify gateway"),
        KeyError("queue"),
        ValueError("Malformed JSON response from Spotify"),
        MemoryError("Simulated memory allocation failure"),
    ]

    for exc in exceptions_to_test:
        client.sp.queue.side_effect = exc
        try:
            res = client.get_queue()
            assert res == [], f"Expected empty list on {type(exc).__name__}, got {res}"
        except Exception as e:
            raise AssertionError(f"Exception {type(exc).__name__} was not handled: {e}")

    print(f"  [PASS] test_api_exception_injection ({len(exceptions_to_test)} exceptions)")


def test_track_album_map_integrity():
    """Verify that _track_album_map correctly stores URI mappings without corrupting internal state."""
    client = _create_mock_client()
    client._track_album_map.clear()

    items = [
        # Normal item with track uri and album uri
        {
            "id": "t1", "name": "Song 1", "uri": "spotify:track:t1",
            "album": {"name": "Alb 1", "uri": "spotify:album:a1"}
        },
        # Item with None URIs
        {
            "id": "t2", "name": "Song 2", "uri": None,
            "album": {"name": "Alb 2", "uri": None}
        },
        # Item with empty strings
        {
            "id": "t3", "name": "Song 3", "uri": "",
            "album": {"name": "Alb 3", "uri": ""}
        },
        # Item with non-string URIs
        {
            "id": "t4", "name": "Song 4", "uri": 12345,
            "album": {"name": "Alb 4", "uri": ["not", "a", "uri"]}
        }
    ]

    client.sp.queue.return_value = {"queue": items}
    res = client.get_queue()
    assert len(res) == 4

    # Only valid string URIs should be in _track_album_map
    assert "spotify:track:t1" in client._track_album_map
    assert client._track_album_map["spotify:track:t1"] == "spotify:album:a1"
    assert None not in client._track_album_map
    assert "" not in client._track_album_map
    assert 12345 not in client._track_album_map

    print("  [PASS] test_track_album_map_integrity")


def run_all_stress_tests():
    print("======================================================================")
    print("Starting Empirical Adversarial Stress Suite for SpotifyClient.get_queue")
    print("======================================================================")
    t0 = time.perf_counter()

    tests = [
        test_disconnected_fallback,
        test_falsy_and_malformed_root_responses,
        test_deeply_nested_nulls,
        test_unexpected_album_types,
        test_unexpected_artists_types,
        test_unexpected_images_structures,
        test_primitive_field_nulls_and_types,
        test_chaotic_interleaved_queue,
        test_thirty_valid_tracks_extraction_with_leading_corrupt,
        test_high_volume_stress_and_memory,
        test_api_exception_injection,
        test_track_album_map_integrity,
    ]

    passed = 0
    failed = 0
    failure_details = []

    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"  [FAIL] {t.__name__}: {e}")
            failure_details.append((t.__name__, str(e)))

    elapsed = (time.perf_counter() - t0) * 1000
    print("======================================================================")
    print(f"Stress Suite Results: {passed} PASSED, {failed} FAILED (Total: {len(tests)}) in {elapsed:.2f}ms")
    print("======================================================================")
    if failure_details:
        print("\nFAILURE SUMMARY:")
        for name, err in failure_details:
            print(f"- {name}: {err}")
    return failed == 0


if __name__ == "__main__":
    success = run_all_stress_tests()
    sys.exit(0 if success else 1)
