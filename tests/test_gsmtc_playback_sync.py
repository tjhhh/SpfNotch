import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import unittest
from unittest.mock import patch, MagicMock
from app.utils.win32_helpers import (
    get_spotify_window_track,
    send_spotify_media_command,
    play_spotify_uri_locally,
)
from app.core.spotify_client import SpotifyClient

class TestGSMTCPlaybackSync(unittest.TestCase):
    def test_gsmtc_paused_track_recovery_with_timeline(self):
        # When window title is just "Spotify" (paused or playing)
        with patch("app.utils.win32_helpers.find_spotify_hwnd", return_value=(12345, "Spotify")), \
             patch("app.utils.win32_helpers.get_windows_media_session", return_value={
                 "app_id": "Spotify",
                 "is_playing": True,
                 "title": "Introvert",
                 "artist": "Stand Here Alone",
                 "album": "Introvert",
                 "progress_ms": 75000,
                 "duration_ms": 188000,
             }):
            res = get_spotify_window_track()
            self.assertIsNotNone(res)
            self.assertTrue(res["is_playing"])
            self.assertEqual(res["title"], "Introvert")
            self.assertEqual(res["artist"], "Stand Here Alone")
            self.assertEqual(res["progress_ms"], 75000)
            self.assertEqual(res["duration_ms"], 188000)

    def test_spotify_client_local_desktop_playback_preserves_timeline(self):
        client = SpotifyClient("config.json")
        client.sp = MagicMock()
        client.is_connected = True

        mock_search_result = [{
            "id": "3rrwI8sRQN9WIl8Ummp6fG",
            "title": "Introvert",
            "artist": "Stand Here Alone",
            "album": "Introvert",
            "cover_url": "https://i.scdn.co/image/introvert.jpg",
            "duration_ms": 192052,
            "uri": "spotify:track:3rrwI8sRQN9WIl8Ummp6fG"
        }]

        with patch("app.core.spotify_client.get_spotify_window_track", return_value={
            "is_playing": True,
            "artist": "Stand Here Alone",
            "title": "Introvert",
            "album": "Introvert",
            "progress_ms": 75000,
            "duration_ms": 188000,
        }), patch.object(client, "search_tracks", return_value=mock_search_result):
            playback = client.get_local_desktop_playback()
            self.assertIsNotNone(playback)
            self.assertTrue(playback["is_playing"])
            self.assertEqual(playback["title"], "Introvert")
            self.assertEqual(playback["artist"], "Stand Here Alone")
            self.assertEqual(playback["progress_ms"], 75000)
            self.assertEqual(playback["duration_ms"], 188000)
            self.assertTrue(playback["is_local_fallback"])

    def test_get_current_playback_falls_back_under_429(self):
        client = SpotifyClient("config.json")
        client._rate_limit_until = 9999999999  # Force 429
        expected = {
            "is_playing": True,
            "title": "33x",
            "artist": "Perunggu",
            "progress_ms": 10000,
            "duration_ms": 434000,
            "is_local_fallback": True
        }
        with patch.object(client, "get_local_desktop_playback", return_value=expected):
            pb = client.get_current_playback()
            self.assertEqual(pb, expected)

    def test_send_spotify_media_command_calls_gsmtc(self):
        with patch("app.utils.win32_helpers.send_windows_media_action", return_value=True) as mock_action:
            ok = send_spotify_media_command("play_pause")
            self.assertTrue(ok)
            mock_action.assert_called_with("toggle")

    def test_play_spotify_uri_locally_triggers_gsmtc_play(self):
        with patch("subprocess.run") as mock_subproc, \
             patch("app.utils.win32_helpers.send_windows_media_action", return_value=True) as mock_action, \
             patch("app.utils.win32_helpers.get_spotify_window_track", side_effect=[
                 {"is_playing": False},  # first check (just cued)
                 {"is_playing": True},   # after send_windows_media_action("play")
             ]):
            ok = play_spotify_uri_locally("spotify:track:3rrwI8sRQN9WIl8Ummp6fG")
            self.assertTrue(ok)
            self.assertTrue(mock_subproc.called)
            args = mock_subproc.call_args[0][0]
            self.assertIn("play_uri", args)
            self.assertIn("spotify:track:3rrwI8sRQN9WIl8Ummp6fG", args)

if __name__ == "__main__":
    unittest.main()
