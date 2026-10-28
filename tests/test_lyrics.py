import sys
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.core.lyrics_client import LyricsClient

def test_lrc_parsing():
    sample_lrc = """
    [00:05.12] First line of test song
    [00:12.80] Second line of test song
    [00:25.500] Third line of test song with 3-digit ms
    [01:02.10] Final chorus line
    """
    client = LyricsClient()
    lines = client._parse_lrc(sample_lrc)
    
    assert len(lines) == 4, f"Expected 4 lines, got {len(lines)}"
    assert lines[0]["time_ms"] == 5120
    assert lines[0]["text"] == "First line of test song"
    assert lines[1]["time_ms"] == 12800
    assert lines[2]["time_ms"] == 25500
    assert lines[3]["time_ms"] == 62100
    print("[PASS] test_lrc_parsing")

def test_binary_search_sync():
    timestamps = [5000, 12000, 25000, 60000]
    
    # Before first line -> should return index 0
    assert LyricsClient.find_active_index(timestamps, 2000) == 0
    # Exactly on line 1
    assert LyricsClient.find_active_index(timestamps, 5000) == 0
    # Between line 1 and 2
    assert LyricsClient.find_active_index(timestamps, 8000) == 0
    # On line 2
    assert LyricsClient.find_active_index(timestamps, 12000) == 1
    # On line 3
    assert LyricsClient.find_active_index(timestamps, 30000) == 2
    # After last line
    assert LyricsClient.find_active_index(timestamps, 90000) == 3
    print("[PASS] test_binary_search_sync")

if __name__ == "__main__":
    test_lrc_parsing()
    test_binary_search_sync()
    print("All lyrics tests passed successfully!")
