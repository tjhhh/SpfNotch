import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import unittest
from unittest.mock import patch, MagicMock
from app.core.spotify_client import SpotifyClient
from PyQt6.QtWidgets import QApplication
from app.ui.settings_tab import SettingsTab

app = QApplication.instance() or QApplication(sys.argv)

class TestAccountTierBehavior(unittest.TestCase):
    def setUp(self):
        self.client = SpotifyClient("config.json")
        self.client.sp = MagicMock()
        self.client.is_connected = True
        self.client._rate_limit_until = 0.0

    def test_free_account_toggle_play_uses_local_command(self):
        self.client.user_product = "free"
        with patch("app.core.spotify_client.send_spotify_media_command", return_value=True) as mock_local:
            ok = self.client.toggle_play(current_is_playing=True)
            self.assertTrue(ok)
            mock_local.assert_called_with("play_pause")
            self.client.sp.pause_playback.assert_not_called()

    def test_free_account_next_prev_uses_local_command(self):
        self.client.user_product = "free"
        with patch("app.core.spotify_client.send_spotify_media_command", return_value=True) as mock_local:
            ok_next = self.client.next_track()
            ok_prev = self.client.previous_track()
            self.assertTrue(ok_next)
            self.assertTrue(ok_prev)
            mock_local.assert_any_call("next")
            mock_local.assert_any_call("prev")
            self.client.sp.next_track.assert_not_called()
            self.client.sp.previous_track.assert_not_called()

    def test_free_account_add_to_queue_provides_friendly_notice(self):
        self.client.user_product = "free"
        success, msg = self.client.add_to_queue("spotify:track:12345")
        self.assertFalse(success)
        self.assertIn("Spotify Free", msg)
        self.assertIn("Premium", msg)
        self.client.sp.add_to_queue.assert_not_called()

    def test_free_account_play_track_bypasses_web_api(self):
        self.client.user_product = "free"
        with patch.object(self.client, "_play_track_locally", return_value=(True, "Memutar di Spotify Desktop (Akun Free)")) as mock_local:
            success, msg = self.client.play_track("spotify:track:12345")
            self.assertTrue(success)
            self.assertIn("Akun Free", msg)
            mock_local.assert_called()
            self.client.sp.start_playback.assert_not_called()

    def test_premium_account_play_track_uses_web_api(self):
        self.client.user_product = "premium"
        self.client.last_device_id = "test_device_id"
        with patch.object(self.client, "get_best_device_id", return_value=("test_device_id", "PC")):
            success, msg = self.client.play_track("spotify:track:12345")
            self.assertTrue(success)
            self.assertIn("Web API", msg)
            self.client.sp.start_playback.assert_called_with(device_id="test_device_id", uris=["spotify:track:12345"])

    def test_premium_account_add_to_queue_uses_web_api(self):
        self.client.user_product = "premium"
        self.client.last_device_id = "test_device_id"
        success, msg = self.client.add_to_queue("spotify:track:12345")
        self.assertTrue(success)
        self.client.sp.add_to_queue.assert_called_with("spotify:track:12345", device_id="test_device_id")

    def test_settings_tab_badge_display(self):
        settings = SettingsTab()
        settings.set_connected(True, product_tier="premium")
        self.assertIn("Premium", settings.status_banner.text())
        
        settings.set_connected(True, product_tier="free")
        self.assertIn("Free", settings.status_banner.text())

if __name__ == "__main__":
    unittest.main()
