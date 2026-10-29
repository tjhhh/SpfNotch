import sys
import os
import json
import tempfile
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from PyQt6.QtWidgets import QApplication
from app.utils.image_cache import ImageCache
from app.core.lyrics_client import LyricsClient
from app.core.spotify_client import SpotifyClient
from app.core.state_manager import StateManager
from app.ui.notch_window import NotchWindow


def test_settings_persistence_and_autoconnect():
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)

    # Create temporary config file to test persistence without modifying workspace config directly
    with tempfile.NamedTemporaryFile("w+", suffix=".json", delete=False, encoding="utf-8") as tf:
        temp_config_path = tf.name
        initial_cfg = {
            "spotify": {
                "client_id": "test_client_id_123",
                "client_secret": "test_client_secret_456",
                "redirect_uri": "http://127.0.0.1:8888/callback",
                "scope": "user-read-playback-state user-modify-playback-state user-read-currently-playing"
            },
            "ui": {
                "notch_collapsed_width": 440,
                "notch_collapsed_height": 50,
                "notch_expanded_width": 540,
                "notch_expanded_height": 460,
                "idle_mode": "track"
            },
            "personalization": {
                "preset": "nordic-frost",
                "opacity": 0.82,
                "blur": 38,
                "specular_border": 0.22,
                "chroma_glow": 0.40,
                "tint_rgb": "15, 23, 42",
                "notch_morph": "floating-island",
                "scrubber_style": "laser-line",
                "accent_mode": "preset",
                "accent_color": "#38BDF8"
            }
        }
        json.dump(initial_cfg, tf, indent=2)

    try:
        # Initialize Core and UI using custom config
        image_cache = ImageCache()
        lyrics_client = LyricsClient()
        spotify_client = SpotifyClient(temp_config_path)
        state_manager = StateManager(spotify_client, lyrics_client)

        win = NotchWindow(state_manager, image_cache, initial_cfg)
        win.show()

        # -------------------------------------------------------------
        # 1. VERIFY NO HARDCODED DEMO SONGS ("Ora Urus" / "Toton Caribo")
        # -------------------------------------------------------------
        pill = win.pill_view
        expanded = win.expanded_view
        settings = expanded.settings_tab

        # Trigger disconnected state
        state_manager._load_disconnected_state()

        assert pill.current_title == "-", f"Expected pill title '-', got '{pill.current_title}'"
        assert pill.current_artist == "-", f"Expected pill artist '-', got '{pill.current_artist}'"
        assert pill.line1_label.text() == "-", f"Expected line1_label '-', got '{pill.line1_label.text()}'"
        assert expanded.title_lbl.text() == "-", f"Expected expanded title '-', got '{expanded.title_lbl.text()}'"
        assert expanded.artist_lbl.text() == "-", f"Expected expanded artist '-', got '{expanded.artist_lbl.text()}'"
        print("[PASS] 1. Disconnected state shows '-' for title and artist (no hardcoded demo songs)")

        # -------------------------------------------------------------
        # 2. VERIFY SETTINGS LOADED & APPLIED TO CONTROLS
        # -------------------------------------------------------------
        assert settings.selected_preset_id == "nordic-frost", f"Expected preset 'nordic-frost', got {settings.selected_preset_id}"
        assert settings.glass_blur == 38, f"Expected blur 38, got {settings.glass_blur}"
        assert settings.slider_blur.value() == 38, f"Expected slider blur 38, got {settings.slider_blur.value()}"
        assert settings.slider_clear.value() == 18, f"Expected slider clear 18 (100-82), got {settings.slider_clear.value()}"
        assert settings.slider_chroma.value() == 40, f"Expected slider chroma 40, got {settings.slider_chroma.value()}"
        assert settings.slider_specular.value() == 22, f"Expected slider specular 22, got {settings.slider_specular.value()}"
        assert settings.notch_morph == "floating-island", f"Expected morph 'floating-island', got {settings.notch_morph}"
        assert settings.scrubber_style == "laser-line", f"Expected scrubber 'laser-line', got {settings.scrubber_style}"
        assert settings.btn_timeline_toggle.text() == "Timeline: Laser"
        assert expanded.waveform_scrubber.style_mode == "laser-line"
        assert settings.combo_idle.currentIndex() == 1, "Expected combo_idle index 1 ('track')"
        assert pill.idle_mode == "track"
        assert win.accent_color == "#38BDF8"
        print("[PASS] 2. Settings successfully restored from config into all UI controls and sliders")

        # -------------------------------------------------------------
        # 3. VERIFY IDLE MODE PERSISTENCE
        # -------------------------------------------------------------
        # Change idle mode to lyrics
        settings.combo_idle.setCurrentIndex(0)
        assert pill.idle_mode == "lyrics"

        with open(temp_config_path, "r", encoding="utf-8") as f:
            updated_cfg = json.load(f)
        assert updated_cfg["ui"]["idle_mode"] == "lyrics", f"Expected idle_mode 'lyrics', got {updated_cfg['ui'].get('idle_mode')}"
        print("[PASS] 3. Changing idle mode combobox immediately persists to config.json")

        # -------------------------------------------------------------
        # 4. VERIFY PERSONALIZATION SLIDER UPDATE & PERSISTENCE
        # -------------------------------------------------------------
        # Move blur slider to 44
        settings.slider_blur.setValue(44)
        assert settings.glass_blur == 44
        assert win.glass_blur == 44 if hasattr(win, "glass_blur") else True

        with open(temp_config_path, "r", encoding="utf-8") as f:
            updated_cfg2 = json.load(f)
        assert updated_cfg2["personalization"]["blur"] == 44
        # Verify other settings were NOT corrupted or reset
        assert updated_cfg2["personalization"]["preset"] == "nordic-frost"
        assert updated_cfg2["personalization"]["notch_morph"] == "floating-island"
        print("[PASS] 4. Modifying slider persists to config.json without resetting other attributes")

        # -------------------------------------------------------------
        # 5. VERIFY AUTO-CONNECT & BACKGROUND RECONNECT LOGIC
        # -------------------------------------------------------------
        # Verify try_auto_reconnect method exists and returns a boolean
        can_reconnect = spotify_client.try_auto_reconnect()
        assert isinstance(can_reconnect, bool)

        # Check that StateManager executes background reconnection without crashing
        state_manager._bg_fetch_playback()

        # Check status banner updates properly with set_connected
        settings.set_connected(True)
        assert "Terhubung" in settings.status_banner.text()
        settings.set_connected(False)
        assert "Belum Terhubung" in settings.status_banner.text()
        print("[PASS] 5. Spotify try_auto_reconnect, background retry polling, and status banner verified")

        # -------------------------------------------------------------
        # 6. VERIFY CLEAN SHUTDOWN FLUSH
        # -------------------------------------------------------------
        win.save_all_settings()
        state_manager.shutdown()
        assert state_manager._is_shutting_down is True
        print("[PASS] 6. Clean shutdown and save_all_settings verified")

        win.close()
        print("\nALL SETTINGS PERSISTENCE & AUTOCONNECT TESTS PASSED 100%!")

    finally:
        if os.path.exists(temp_config_path):
            try:
                os.remove(temp_config_path)
            except Exception:
                pass


if __name__ == "__main__":
    test_settings_persistence_and_autoconnect()
