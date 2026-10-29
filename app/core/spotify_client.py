import os
import sys
import json
import webbrowser
import http.server
import urllib.parse
import threading
import spotipy
from spotipy.oauth2 import SpotifyOAuth, SpotifyOauthError
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
        self.last_device_id: str | None = None
        self.last_device_name: str = "Spotify"
        self._last_init_attempt: float = 0.0
        self._track_album_map: dict[str, str] = {}
        
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
        except SpotifyOauthError as oe:
            print(f"[SpotifyClient] OAuth error (clearing invalid cache): {oe}")
            cache_dir = os.path.dirname(self.config_path)
            cache_path = os.path.join(cache_dir, ".spotify_token_cache")
            if os.path.exists(cache_path):
                try:
                    os.remove(cache_path)
                except Exception:
                    pass
            self.is_connected = False
            self.sp = None
            return False
        except Exception as e:
            print(f"[SpotifyClient] Init error: {e}")
            self.is_connected = False
            self.sp = None
            return False

    def try_auto_reconnect(self) -> bool:
        """Attempts to reconnect using cached credentials/tokens in a safe, non-blocking way."""
        if not self.client_id or not self.client_secret:
            return False
        if self.is_authenticating:
            return False
        if self.is_connected and self.sp:
            return True
        return self.init_spotify()

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

    def _ensure_connected(self) -> bool:
        if self.sp and self.is_connected:
            return True
        if self.is_authenticating or not self.client_id or not self.client_secret:
            return False
        import time
        now = time.time()
        if now - self._last_init_attempt < 8.0:
            return False
        self._last_init_attempt = now
        return self.init_spotify()

    def get_current_playback(self) -> dict | None:
        if not self._ensure_connected():
            return None

        try:
            playback = self.sp.current_playback()
            if not playback:
                try:
                    recent = self.sp.current_user_recently_played(limit=1)
                    if recent and recent.get("items"):
                        item = recent["items"][0].get("track")
                        if item:
                            artists = ", ".join([a["name"] for a in item.get("artists", [])])
                            images = item.get("album", {}).get("images", [])
                            cover_url = images[0]["url"] if images else ""
                            return {
                                "is_playing": False,
                                "track_id": item.get("id", ""),
                                "title": item.get("name", "-"),
                                "artist": artists or "-",
                                "album": item.get("album", {}).get("name", ""),
                                "cover_url": cover_url,
                                "progress_ms": 0,
                                "duration_ms": item.get("duration_ms", 0),
                                "uri": item.get("uri", "")
                            }
                except Exception:
                    pass
                return None

            dev = playback.get("device")
            if dev and dev.get("id"):
                self.last_device_id = dev.get("id")
                self.last_device_name = dev.get("name", "Spotify")

            if not playback.get("item"):
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

    def get_best_device_id(self) -> tuple[str | None, str]:
        """
        Finds the best active or standby Spotify Connect device.
        Returns (device_id, description_or_name).
        """
        if not self._ensure_connected():
            return None, "Spotify belum terhubung."
        try:
            res = self.sp.devices()
            devices = res.get("devices", []) if res else []
            if not devices:
                # Attempt to launch desktop Spotify client on Windows if available
                if sys.platform == "win32":
                    try:
                        os.startfile("spotify:")
                        import time
                        for _ in range(5):
                            time.sleep(0.5)
                            res_retry = self.sp.devices()
                            devices = res_retry.get("devices", []) if res_retry else []
                            if devices:
                                break
                    except Exception:
                        pass
                if not devices:
                    return None, "Tidak ada perangkat aktif. Buka Spotify di PC/HP kamu."

            # 1. Prefer currently active device
            for d in devices:
                if d.get("is_active"):
                    self.last_device_id = d.get("id")
                    self.last_device_name = d.get("name", "Perangkat Aktif")
                    return self.last_device_id, self.last_device_name

            # 2. Prefer Computer/Desktop device
            for d in devices:
                if d.get("type", "").lower() == "computer":
                    self.last_device_id = d.get("id")
                    self.last_device_name = d.get("name", "Komputer")
                    return self.last_device_id, self.last_device_name

            # 3. Fallback to first available device
            self.last_device_id = devices[0].get("id")
            self.last_device_name = devices[0].get("name", "Perangkat")
            return self.last_device_id, self.last_device_name
        except Exception as e:
            print(f"[SpotifyClient] get_best_device_id error: {e}")
            return None, f"Error perangkat: {e}"

    def toggle_play(self, current_is_playing: bool) -> bool:
        if not self.sp:
            return False
        try:
            if current_is_playing:
                self.sp.pause_playback()
            else:
                dev_id, _ = self.get_best_device_id()
                if dev_id:
                    self.sp.start_playback(device_id=dev_id)
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
        if not self._ensure_connected():
            return [
                {"id": "ini-abadi", "title": "Ini Abadi", "artist": "Perunggu", "duration_ms": 242000, "cover_url": "", "uri": "spotify:track:ini_abadi"},
                {"id": "abadi-dendi", "title": "Abadi - Indo Version", "artist": "Dendi Nata", "duration_ms": 255000, "cover_url": "", "uri": "spotify:track:abadi_dendi"},
                {"id": "bunga-abadi", "title": "Bunga Abadi", "artist": "Rio Clappy", "duration_ms": 236000, "cover_url": "", "uri": "spotify:track:bunga_abadi"}
            ]
        try:
            res = self.sp.queue()
            if not res or not isinstance(res, dict) or not res.get("queue") or not isinstance(res.get("queue"), list):
                return []
            
            queue_tracks = []
            raw_queue = res.get("queue", [])
            for item in raw_queue:
                try:
                    if not isinstance(item, dict):
                        continue

                    raw_album = item.get("album")
                    album = raw_album if isinstance(raw_album, dict) else {}
                    album_name = str(album.get("name")) if isinstance(album.get("name"), str) else ""
                    a_uri = str(album.get("uri")) if isinstance(album.get("uri"), str) else ""

                    raw_show = item.get("show")
                    show = raw_show if isinstance(raw_show, dict) else {}

                    artists = ""
                    raw_artists = item.get("artists")
                    if isinstance(raw_artists, list) and raw_artists:
                        names = [str(a["name"]) for a in raw_artists if isinstance(a, dict) and a.get("name") is not None]
                        artists = ", ".join(names)

                    if not artists:
                        if show.get("publisher"):
                            artists = str(show.get("publisher"))
                        elif show.get("name"):
                            artists = str(show.get("name"))

                    images = []
                    if isinstance(album.get("images"), list) and album["images"]:
                        images = album["images"]
                    elif isinstance(item.get("images"), list) and item["images"]:
                        images = item["images"]
                    elif isinstance(show.get("images"), list) and show["images"]:
                        images = show["images"]

                    cover_url = ""
                    if images:
                        for img in reversed(images):
                            if isinstance(img, dict) and isinstance(img.get("url"), str) and img["url"]:
                                cover_url = img["url"]
                                break
                        if not cover_url:
                            for img in images:
                                if isinstance(img, dict) and isinstance(img.get("url"), str) and img["url"]:
                                    cover_url = img["url"]
                                    break

                    raw_uri = item.get("uri")
                    t_uri = str(raw_uri) if isinstance(raw_uri, str) else ""
                    if t_uri and a_uri:
                        self._track_album_map[t_uri] = a_uri

                    raw_dur = item.get("duration_ms")
                    duration_ms = raw_dur if (isinstance(raw_dur, int) and not isinstance(raw_dur, bool)) else 0

                    raw_id = item.get("id")
                    track_id = str(raw_id) if raw_id is not None else ""

                    raw_name = item.get("name")
                    title = str(raw_name) if raw_name is not None else "Unknown"

                    queue_tracks.append({
                        "id": track_id,
                        "title": title,
                        "artist": artists,
                        "album": album_name,
                        "album_uri": a_uri,
                        "duration_ms": duration_ms,
                        "cover_url": cover_url,
                        "uri": t_uri
                    })
                    if len(queue_tracks) >= 30:
                        break
                except Exception as item_err:
                    print(f"[SpotifyClient] get_queue item error: {item_err}")
                    continue

            return queue_tracks
        except Exception as e:
            print(f"[SpotifyClient] get_queue error: {e}")
            return []

    def _resolve_uri(self, uri: str) -> str:
        """If a demo fallback URI is clicked while connected to Spotify, resolve to real Spotify track URI."""
        demo_queries = {
            "spotify:track:ini_abadi": "Ini Abadi Perunggu",
            "spotify:track:abadi_dendi": "Abadi Indo Version Dendi Nata",
            "spotify:track:abadi_collab": "Abadi Dendi Nata Hendra Kumbara",
            "spotify:track:bunga_abadi": "Bunga Abadi Rio Clappy",
            "spotify:track:ora_urus": "Ora Urus Toton Caribo",
        }
        if uri in demo_queries and self.sp:
            tracks = self.search_tracks(demo_queries[uri], limit=1)
            if tracks and tracks[0].get("uri"):
                return tracks[0]["uri"]
        return uri

    def search_tracks(self, query: str, limit: int = 10) -> list[dict]:
        if not query.strip():
            return []
        if not self._ensure_connected():
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
                t_uri = item.get("uri", "")
                a_uri = item.get("album", {}).get("uri", "")
                if t_uri and a_uri:
                    self._track_album_map[t_uri] = a_uri
                results.append({
                    "id": item.get("id", ""),
                    "title": item.get("name", "Unknown"),
                    "artist": artists,
                    "album": item.get("album", {}).get("name", ""),
                    "album_uri": a_uri,
                    "duration_ms": item.get("duration_ms", 0),
                    "cover_url": cover_url,
                    "uri": t_uri
                })
            return results
        except Exception as e:
            print(f"[SpotifyClient] search_tracks error: {e}")
            return []

    def add_to_queue(self, uri: str) -> tuple[bool, str]:
        if not self._ensure_connected() or not uri:
            return False, "Spotify belum terhubung."
        try:
            real_uri = self._resolve_uri(uri)
            dev_id, dev_name = self.get_best_device_id()
            if dev_id:
                self.sp.add_to_queue(real_uri, device_id=dev_id)
            else:
                self.sp.add_to_queue(real_uri)
            return True, "Berhasil ditambahkan ke antrean"
        except SpotifyException as se:
            if se.http_status == 403:
                return False, "Akun Spotify Free: antrean API memerlukan Spotify Premium."
            return False, "Gagal menambahkan ke antrean."
        except Exception as e:
            print(f"[SpotifyClient] add_to_queue error: {e}")
            return False, f"Gagal antrean: {e}"

    def play_track(self, uri: str, context_uri: str | None = None) -> tuple[bool, str]:
        if not self._ensure_connected() or not uri:
            return False, "Spotify belum terhubung."
        try:
            real_uri = self._resolve_uri(uri)
            dev_id, dev_name = self.get_best_device_id()
            if not dev_id:
                return False, dev_name

            album_uri = context_uri or self._track_album_map.get(real_uri, "")
            if not album_uri and real_uri.startswith("spotify:track:"):
                try:
                    tr_info = self.sp.track(real_uri)
                    if isinstance(tr_info, dict):
                        album_uri = tr_info.get("album", {}).get("uri", "")
                        if album_uri:
                            self._track_album_map[real_uri] = album_uri
                except Exception:
                    album_uri = ""

            def _do_start():
                if album_uri:
                    self.sp.start_playback(
                        device_id=dev_id,
                        context_uri=album_uri,
                        offset={"uri": real_uri}
                    )
                else:
                    self.sp.start_playback(device_id=dev_id, uris=[real_uri])

            # Explicitly pass device_id and album context_uri + offset so Spotify Desktop plays immediately
            try:
                _do_start()
            except SpotifyException as inner_se:
                if inner_se.http_status in (404, 502, 503):
                    import time
                    self.sp.transfer_playback(device_id=dev_id, force_play=False)
                    time.sleep(0.3)
                    _do_start()
                else:
                    raise inner_se

            return True, f"Memutar di {dev_name}"
        except SpotifyException as se:
            print(f"[SpotifyClient] play_track SpotifyException: {se}")
            if se.http_status == 403:
                return False, "Akun Spotify Free: kontrol putar lagu memerlukan Spotify Premium."
            elif se.http_status == 404:
                return False, "Tidak ada perangkat aktif. Buka Spotify di PC/HP kamu."
            return False, f"Spotify error: {se.msg if hasattr(se, 'msg') else 'Gagal memutar'}"
        except Exception as e:
            print(f"[SpotifyClient] play_track error: {e}")
            return False, f"Gagal memutar: {e}"
