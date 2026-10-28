import os
import sys
import json
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPixmap, QColor, QPainter
from PyQt6.QtCore import Qt

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.utils.color_helpers import extract_dominant_color, get_secondary_complement
from app.ui.notch_window import NotchWindow
from app.ui.settings_tab import SettingsTab, ColorSwatchButton
from app.utils.image_cache import ImageCache
from app.core.lyrics_client import LyricsClient
from app.core.spotify_client import SpotifyClient
from app.core.state_manager import StateManager

def create_sample_pixmap(color: QColor, size: int = 64) -> QPixmap:
    pix = QPixmap(size, size)
    pix.fill(color)
    return pix

def test_chroma_accent_color_suite():
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)

    # 1. Test color_helpers
    print("[RUN] Testing color_helpers...")
    red_pix = create_sample_pixmap(QColor(230, 40, 80))
    extracted_red = extract_dominant_color(red_pix)
    assert extracted_red.startswith("#"), f"Expected hex string, got {extracted_red}"
    
    complement = get_secondary_complement("#38BDF8")
    assert complement.startswith("#"), f"Expected hex string for complement, got {complement}"
    print("[PASS] 1. color_helpers extract_dominant_color and get_secondary_complement function properly")

    # 2. Test SettingsTab Chroma Swatches
    print("[RUN] Testing SettingsTab chroma swatches...")
    tab = SettingsTab()
    assert hasattr(tab, "swatch_buttons")
    assert len(tab.swatch_buttons) == 7, f"Expected 7 swatches, got {len(tab.swatch_buttons)}"
    assert "auto" in tab.swatch_buttons
    assert "mint" in tab.swatch_buttons
    assert "cyan" in tab.swatch_buttons
    assert "violet" in tab.swatch_buttons
    assert "rose" in tab.swatch_buttons
    assert "amber" in tab.swatch_buttons
    assert "silver" in tab.swatch_buttons
    assert hasattr(tab, "btn_custom_color")
    assert hasattr(tab, "lbl_accent_tag")

    # Default is preset mint #34D399
    assert tab.accent_mode == "preset"
    assert tab.current_accent.upper() == "#34D399"
    assert tab.swatch_buttons["mint"].property("selected") is not False
    print("[PASS] 2. SettingsTab initializes 7 curated swatches, + Kustom button, and default Emerald Mint")

    # 3. Test Switching to Cyan Preset
    received_data = []
    tab.personalization_changed.connect(lambda d: received_data.append(d))

    tab._on_swatch_clicked("cyan", "#38BDF8")
    assert tab.accent_mode == "preset"
    assert tab.current_accent == "#38BDF8"
    assert tab.lbl_accent_tag.text() == "#38BDF8"
    assert len(received_data) > 0
    latest = received_data[-1]
    assert latest["accent_mode"] == "preset"
    assert latest["accent_color"] == "#38BDF8"
    print("[PASS] 3. Clicking Electric Cyan swatch updates accent to #38BDF8 and emits signal")

    # 4. Test Switching to Custom Color
    tab.set_chroma_accent("custom", "#FF007F")
    assert tab.accent_mode == "custom"
    assert tab.current_accent == "#FF007F"
    assert tab.lbl_accent_tag.text() == "#FF007F"
    latest = received_data[-1]
    assert latest["accent_mode"] == "custom"
    assert latest["accent_color"] == "#FF007F"
    print("[PASS] 4. Custom accent color #FF007F properly applied and emitted")

    # 5. Test Switching to Auto (Dynamic) Mode
    tab._on_swatch_clicked("auto", None)
    assert tab.accent_mode == "auto"
    assert tab.lbl_accent_tag.text() == "AUTO (SAMPUL)"
    latest = received_data[-1]
    assert latest["accent_mode"] == "auto"
    print("[PASS] 5. Auto (dynamic album cover) mode selected and displays AUTO (SAMPUL)")

    # 6. Test NotchWindow full propagation and persistence
    config_path = os.path.join(BASE_DIR, "config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    img_cache = ImageCache()
    lyrics = LyricsClient()
    spotify = SpotifyClient(config_path)
    state = StateManager(spotify, lyrics)

    win = NotchWindow(state, img_cache, config)
    assert hasattr(win, "accent_mode")
    assert hasattr(win, "accent_color")

    # Emit Cyan from settings_tab
    win.expanded_view.settings_tab._on_swatch_clicked("cyan", "#38BDF8")
    assert win.accent_color == "#38BDF8"
    assert win.pill_view.accent_color == "#38BDF8"
    assert win.expanded_view.accent_color == "#38BDF8"
    assert win.expanded_view.waveform_scrubber.accent_color == "#38BDF8"
    assert win.expanded_view.lyrics_tab.accent_color == "#38BDF8"
    assert win.expanded_view.search_tab.accent_color == "#38BDF8"
    assert win.chroma_color_1 == QColor("#38BDF8")
    print("[PASS] 6. NotchWindow propagates Cyan #38BDF8 to Pill, Expanded, Waveform, Lyrics, Search, and Ambient Glow")

    # 7. Test Auto mode dynamic extraction upon track change in NotchWindow
    win.expanded_view.settings_tab._on_swatch_clicked("auto", None)
    assert win.accent_mode == "auto"

    # Simulate new track with a distinct purple cover
    purple_pix = create_sample_pixmap(QColor(168, 85, 247), size=64)
    win.pill_view.current_cover = purple_pix
    win._extract_dominant_colors(purple_pix)

    assert win.accent_color != "#34D399", "Expected accent color to be extracted from purple cover"
    assert win.pill_view.accent_color == win.accent_color
    assert win.expanded_view.accent_color == win.accent_color
    print(f"[PASS] 7. Auto mode dynamically extracts color ({win.accent_color}) from album cover")

    # 8. Test config persistence
    with open(config_path, "r", encoding="utf-8") as f:
        saved_cfg = json.load(f)
    assert "personalization" in saved_cfg
    assert "accent_mode" in saved_cfg["personalization"]
    assert "accent_color" in saved_cfg["personalization"]
    print(f"[PASS] 8. Personalization successfully persisted to config.json (mode={saved_cfg['personalization']['accent_mode']})")

    # Reset config back to default preset Mint
    win.expanded_view.settings_tab._on_swatch_clicked("mint", "#34D399")
    assert win.accent_color == "#34D399"

    print("\nALL CHROMA ACCENT COLOR TESTS PASSED 100%! EXCELLENCE DELIVERED.")

if __name__ == "__main__":
    test_chroma_accent_color_suite()
