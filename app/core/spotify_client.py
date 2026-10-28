import os
import json
import webbrowser
import http.server
import urllib.parse
import threading
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from spotipy.exceptions import SpotifyException

class OAuthCallbackHandler(http.server.BaseHTTPRequestHandler):
    auth_code = None
    auth_error = None

    def do_GET(self):
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)

        if "code" in params:
            OAuthCallbackHandler.auth_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            html = """
            <html>
            <head><title>Otorisasi Spotify Berhasil</title></head>
            <body style="background:#121212; color:#ffffff; font-family:sans-serif; text-align:center; padding-top:60px;">
                <h1 style="color:#1DB954;">✓ Otorisasi Berhasil!</h1>
                <p>spfnotch telah terhubung. Kamu dapat menutup tab browser ini dan kembali ke aplikasi.</p>
            </body>
            </html>
            """
            self.wfile.write(html.encode("utf-8"))
        else:
            OAuthCallbackHandler.auth_error = params.get("error", ["Unknown error"])[0]
            self.send_response(400)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            html = f"""
            <html>
            <body style="background:#121212; color:#ffffff; font-family:sans-serif; text-align:center; padding-top:60px;">
                <h1 style="color:#e74c3c;">Otorisasi Dibatalkan</h1>
                <p>{OAuthCallbackHandler.auth_error}</p>
            </body>
            </html>
            """
            self.wfile.write(html.encode("utf-8"))

    def log_message(self, format, *args):
        pass  # Quiet logging

class SpotifyClient:
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.client_id = ""
        self.client_secret = ""
        self.redirect_uri = "http://127.0.0.1:8888/callback"
        self.scope = "user-read-playback-state user-modify-playback-state user-read-currently-playing"
        self.sp: spotipy.Spotify | None = None
        self.auth_manager: SpotifyOAuth | None = None
        self.is_connected = False
        self.is_authenticating = False
        
        self.load_config()
        self.init_spotify()

    def load_config(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    spot_cfg = cfg.get("spotify", {})
                    self.client_id = spot_cfg.get("client_id", "").strip()
                    self.client_secret = spot_cfg.get("client_secret", "").strip()
                    self.redirect_uri = spot_cfg.get("redirect_uri", "http://127.0.0.1:8888/callback")
                    self.scope = spot_cfg.get("scope", self.scope)
            except Exception as e:
                print(f"[SpotifyClient] Error loading config: {e}")

    def save_credentials(self, client_id: str, client_secret: str):
        self.client_id = client_id.strip()
        self.client_secret = client_secret.strip()
        
        cfg = {}
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
            except Exception:
                cfg = {}
        
        if "spotify" not in cfg:
            cfg["spotify"] = {}
        cfg["spotify"]["client_id"] = self.client_id
        cfg["spotify"]["client_secret"] = self.client_secret
        cfg["spotify"]["redirect_uri"] = self.redirect_uri
        cfg["spotify"]["scope"] = self.scope

        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)

        return self.init_spotify()

    def init_spotify(self) -> bool:
        if not self.client_id or not self.client_secret:
            self.is_connected = False
            self.sp = None
            return False

        try:
            cache_dir = os.path.dirname(self.config_path)
            cache_path = os.path.join(cache_dir, ".spotify_token_cache")
            
            # open_browser=False prevents spontaneous browser tab loops!
            self.auth_manager = SpotifyOAuth(
                client_id=self.client_id,
                client_secret=self.client_secret,
                redirect_uri=self.redirect_uri,
                scope=self.scope,
                cache_path=cache_path,
                open_browser=False
            )

            # Check if cached token is already valid
            token_info = self.auth_manager.cache_handler.get_cached_token()
            valid_token = self.auth_manager.validate_token(token_info)

            if valid_token:
                self.sp = spotipy.Spotify(auth_manager=self.auth_manager)
                self.is_connected = True
                return True
            else:
                self.is_connected = False
                self.sp = None
                return False
        except Exception as e:
            print(f"[SpotifyClient] Init error: {e}")
            self.is_connected = False
            self.sp = None
            return False

    def start_single_shot_auth(self, on_done_callback):
        """Runs a safe, controlled single-shot OAuth in a background thread."""
        if self.is_authenticating:
            return
        self.is_authenticating = True

        def bg_auth():
            try:
                auth_url = self.auth_manager.get_authorize_url()
                webbrowser.open(auth_url)

                OAuthCallbackHandler.auth_code = None
                OAuthCallbackHandler.auth_error = None

                server = http.server.HTTPServer(("127.0.0.1", 8888), OAuthCallbackHandler)
                server.timeout = 60  # 60s timeout

                while self.is_authenticating and not OAuthCallbackHandler.auth_code and not OAuthCallbackHandler.auth_error:
                    server.handle_request()

                server.server_close()

                if OAuthCallbackHandler.auth_code:
                    token_info = self.auth_manager.get_access_token(OAuthCallbackHandler.auth_code, as_dict=True)
                    if token_info:
                        self.sp = spotipy.Spotify(auth_manager=self.auth_manager)
                        self.is_connected = True
                        self.is_authenticating = False
                        on_done_callback(True, "Terhubung ke Spotify API")
                        return

                self.is_connected = False
                self.is_authenticating = False
                on_done_callback(False, OAuthCallbackHandler.auth_error or "Otorisasi timeout / dibatalkan")
            except Exception as e:
                self.is_connected = False
                self.is_authenticating = False
                on_done_callback(False, f"Error: {e}")

        threading.Thread(target=bg_auth, daemon=True).start()

    def get_current_playback(self) -> dict | None:
        if not self.sp or not self.is_connected:
            return None

        try:
            playback = self.sp.current_playback()
            if not playback or not playback.get("item"):
                return None

            item = playback["item"]
            artists = ", ".join([a["name"] for a in item.get("artists", [])])
            images = item.get("album", {}).get("images", [])
            cover_url = images[0]["url"] if images else ""

            return {
                "is_playing": playback.get("is_playing", False),
                "track_id": item.get("id", ""),
                "title": item.get("name", "Unknown Title"),
                "artist": artists or "Unknown Artist",
                "album": item.get("album", {}).get("name", ""),
                "cover_url": cover_url,
                "progress_ms": playback.get("progress_ms", 0),
                "duration_ms": item.get("duration_ms", 0),
                "uri": item.get("uri", "")
            }
        except SpotifyException as se:
            print(f"[SpotifyClient] SpotifyException in playback: {se}")
            return None
        except Exception as e:
            print(f"[SpotifyClient] General error in playback: {e}")
            return None

    def toggle_play(self, current_is_playing: bool) -> bool:
        if not self.sp:
            return False
        try:
            if current_is_playing:
                self.sp.pause_playback()
            else:
                self.sp.start_playback()
            return True
        except Exception as e:
            print(f"[SpotifyClient] toggle_play error: {e}")
            return False

    def next_track(self) -> bool:
        if not self.sp:
            return False
        try:
            self.sp.next_track()
            return True
        except Exception as e:
            print(f"[SpotifyClient] next_track error: {e}")
            return False

    def previous_track(self) -> bool:
        if not self.sp:
            return False
        try:
            self.sp.previous_track()
            return True
        except Exception as e:
            print(f"[SpotifyClient] previous_track error: {e}")
            return False

    def seek(self, position_ms: int) -> bool:
        if not self.sp:
            return False
        try:
            self.sp.seek_track(position_ms)
            return True
        except Exception as e:
            print(f"[SpotifyClient] seek error: {e}")
            return False

    def get_queue(self) -> list[dict]:
        if not self.sp:
            return [
                {"id": "ini-abadi", "title": "Ini Abadi", "artist": "Perunggu", "duration_ms": 242000, "cover_url": "", "uri": "spotify:track:ini_abadi"},
                {"id": "abadi-dendi", "title": "Abadi - Indo Version", "artist": "Dendi Nata", "duration_ms": 255000, "cover_url": "", "uri": "spotify:track:abadi_dendi"},
                {"id": "bunga-abadi", "title": "Bunga Abadi", "artist": "Rio Clappy", "duration_ms": 236000, "cover_url": "", "uri": "spotify:track:bunga_abadi"}
            ]
        try:
            res = self.sp.queue()
            if not res or not res.get("queue"):
                return []
            
            queue_tracks = []
            for item in res["queue"][:15]:
                artists = ", ".join([a["name"] for a in item.get("artists", [])])
                images = item.get("album", {}).get("images", [])
                cover_url = images[-1]["url"] if images else ""
                queue_tracks.append({
                    "id": item.get("id", ""),
                    "title": item.get("name", "Unknown"),
                    "artist": artists,
                    "duration_ms": item.get("duration_ms", 0),
                    "cover_url": cover_url,
                    "uri": item.get("uri", "")
                })
            return queue_tracks
        except Exception as e:
            print(f"[SpotifyClient] get_queue error: {e}")
            return []

    def search_tracks(self, query: str, limit: int = 10) -> list[dict]:
        if not query.strip():
            return []
        if not self.sp:
            # Demo fallback catalog matching Figma Redesign
            catalog = [
                {"id": "ini-abadi", "title": "Ini Abadi", "artist": "Perunggu", "duration_ms": 242000, "cover_url": "", "uri": "spotify:track:ini_abadi"},
                {"id": "abadi-dendi", "title": "Abadi - Indo Version", "artist": "Dendi Nata", "duration_ms": 255000, "cover_url": "", "uri": "spotify:track:abadi_dendi"},
                {"id": "abadi-collab", "title": "Abadi", "artist": "Dendi Nata, Hendra Kumbara", "duration_ms": 249000, "cover_url": "", "uri": "spotify:track:abadi_collab"},
                {"id": "bunga-abadi", "title": "Bunga Abadi", "artist": "Rio Clappy", "duration_ms": 236000, "cover_url": "", "uri": "spotify:track:bunga_abadi"}
            ]
            q_lower = query.strip().lower()
            filtered = [t for t in catalog if q_lower in t["title"].lower() or q_lower in t["artist"].lower()]
            return filtered if filtered else catalog[:limit]
        try:
            res = self.sp.search(q=query, type="track", limit=limit)
            items = res.get("tracks", {}).get("items", [])
            results = []
            for item in items:
                artists = ", ".join([a["name"] for a in item.get("artists", [])])
                images = item.get("album", {}).get("images", [])
                cover_url = images[-1]["url"] if images else ""
                results.append({
                    "id": item.get("id", ""),
                    "title": item.get("name", "Unknown"),
                    "artist": artists,
                    "duration_ms": item.get("duration_ms", 0),
                    "cover_url": cover_url,
                    "uri": item.get("uri", "")
                })
            return results
        except Exception as e:
            print(f"[SpotifyClient] search_tracks error: {e}")
            return []

    def add_to_queue(self, uri: str) -> bool:
        if not self.sp or not uri:
            return False
        try:
            self.sp.add_to_queue(uri)
            return True
        except Exception as e:
            print(f"[SpotifyClient] add_to_queue error: {e}")
            return False

    def play_track(self, uri: str) -> bool:
        if not self.sp or not uri:
            return False
        try:
            self.sp.start_playback(uris=[uri])
            return True
        except Exception as e:
            print(f"[SpotifyClient] play_track error: {e}")
            return False
