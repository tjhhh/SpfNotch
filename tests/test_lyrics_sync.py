import sys
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from PyQt6.QtWidgets import QApplication
from app.ui.pill_view import PillView
from app.core.lyrics_client import LyricsClient

def test_pill_lyrics_sync():
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)

    pill = PillView()
    pill.set_idle_mode("lyrics")
    
    # 1. Update track info (Song starts playing)
    pill.update_track("Rindu Aku Rindu Kamu", "Maman Fvndy", None, is_playing=True)
    assert "Rindu Aku Rindu Kamu" in pill.text_label.text()
    print("[PASS] Initial track title display")

    # 2. Lyric line arrives from sync engine
    pill.update_lyric("Ketika tiba-tiba ombak di laut pasang")
    assert pill.text_label.text() == "♪ Ketika tiba-tiba ombak di laut pasang", f"Got: {pill.text_label.text()}"
    print("[PASS] Lyric displayed in pill view")

    # 3. 2-second background poll occurs -> Lyric must NOT be overwritten!
    pill.update_track("Rindu Aku Rindu Kamu", "Maman Fvndy", None, is_playing=True)
    assert pill.text_label.text() == "♪ Ketika tiba-tiba ombak di laut pasang", f"Overwritten! Got: {pill.text_label.text()}"
    print("[PASS] Lyric preserved across background polls")

    # 4. Next lyric line arrives
    pill.update_lyric("Cinta kita berdua juga pasang, Sayang")
    assert pill.text_label.text() == "♪ Cinta kita berdua juga pasang, Sayang", f"Got: {pill.text_label.text()}"
    print("[PASS] Next lyric updated smoothly")

    # 5. Song is paused -> gracefully falls back to title
    pill.update_track("Rindu Aku Rindu Kamu", "Maman Fvndy", None, is_playing=False)
    assert "⏸" in pill.status_icon.text()
    print("[PASS] Paused state handled correctly")

    # 6. Song with no lyrics (or cleared lyrics) -> displays ONLY Title and Author (no stale lyric, no LIVE badge)
    pill.update_track("Karena Su Sayang", "Maman Fvndy, Abil Ska 86, Nikisuka", None, is_playing=True)
    pill.update_lyric("", "")
    assert pill.live_badge.isHidden() is True, "LIVE badge must be hidden when no lyrics exist"
    assert pill.line1_label.text() == "♪ Karena Su Sayang", f"Expected title on line 1, got: {pill.line1_label.text()}"
    assert "Maman Fvndy" in pill.line2_label.text(), f"Expected author on line 2, got: {pill.line2_label.text()}"
    print("[PASS] No-lyrics state shows Title and Author only")

    # 7. LyricsClient rejects unrelated search results (e.g. Japanese song matching '86' in artist name)
    client = LyricsClient()
    fake_jp_item = {"trackName": "夜の空を飾る綺麗な花", "artistName": "SawanoHiroyuki[nZk]:86", "duration": 210}
    assert client._is_matching_result(fake_jp_item, "Karena Su Sayang", "Maman Fvndy, Abil Ska 86, Nikisuka", 210) is False
    valid_item = {"trackName": "Karena Su Sayang", "artistName": "Maman Fvndy", "duration": 205}
    assert client._is_matching_result(valid_item, "Karena Su Sayang", "Maman Fvndy, Abil Ska 86, Nikisuka", 210) is True
    print("[PASS] LyricsClient strictly validates title & artist and rejects false-positive lyrics")

    print("All pill lyrics sync tests passed successfully!")

if __name__ == "__main__":
    test_pill_lyrics_sync()
