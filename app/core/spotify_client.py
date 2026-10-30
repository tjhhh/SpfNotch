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
import requests
import urllib3
from app.utils.win32_helpers import (
    get_spotify_window_track,
    send_spotify_media_command,
    play_spotify_uri_locally,
)

def _create_fast_session() -> requests.Session:
    """
    Creates a requests.Session with fail-fast, non-blocking retries.
    Crucially sets respect_retry_after_header=False and total=0 so urllib3
    does NOT sleep/block the thread for hours when Spotify returns HTTP 429.
    """
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(max_retries=urllib3.util.Retry(
        total=0,
        connect=0,
        read=0,
        status=0,
        respect_retry_after_header=False
    ))
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

class ReusableHTTPServer(http.server.HTTPServer):
    allow_reuse_address = True

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
        self.scope = "user-read-playback-state user-modify-playback-state user-read-currently-playing user-read-recently-played user-read-private"
        self.sp: spotipy.Spotify | None = None
        self.auth_manager: SpotifyOAuth | None = None
        self.is_connected = False
        self.is_authenticating = False
        self.user_product: str = "unknown"
        self.last_device_id: str | None = None
        self.last_device_name: str = "Spotify"
        self._last_init_attempt: float = 0.0
        self._track_album_map: dict[str, str] = {}
        self._rate_limit_until: float = 0.0
        self._cached_recent_track: dict | None = None
        self._last_recent_fetch: float = 0.0
        self._local_track_cache: dict[str, dict] = {}
        self._last_local_track: dict | None = None
        self.last_error_message: str = ""
        self.session: requests.Session | None = None
        
        self.load_config()
        self.init_spotify()

    def is_rate_limited(self) -> bool:
        import time
        return time.time() < self._rate_limit_until

    def _detect_user_tier(self):
        """Fetches product tier from profile ('premium', 'free', or 'unknown')."""
        if not self.sp:
            return
        try:
            profile = self.sp.current_user()
            if isinstance(profile, dict):
                prod = profile.get("product")
                if prod:
                    self.user_product = str(prod).lower().strip()
                    print(f"[SpotifyClient] Detected user tier: {self.user_product}")
        except Exception:
            pass

    def _record_rate_limit(self, se_or_err=None):
        import time
        retry_after = 10
        if hasattr(se_or_err, "headers") and se_or_err.headers and "Retry-After" in se_or_err.headers:
            try:
                retry_after = int(se_or_err.headers["Retry-After"])
            except Exception:
                retry_after = 10
        self._rate_limit_until = time.time() + retry_after
        self.last_error_message = "Kuota API Spotify Habis (Rate Limit). Buat App baru di Spotify Dashboard."
        print(f"[SpotifyClient] Rate limit 429 ({getattr(se_or_err, 'reason', '')}). Backing off for {retry_after}s.")

    def cache_track_metadata(self, track_meta: dict | None):
        if not isinstance(track_meta, dict):
            return
        title = str(track_meta.get("title", "")).strip()
        artist = str(track_meta.get("artist", "")).strip()
        uri = str(track_meta.get("uri", "")).strip()
        if title and artist:
            key = f"{artist.lower()}|{title.lower()}"
            self._local_track_cache[key] = dict(track_meta)
        if uri:
            self._local_track_cache[uri] = dict(track_meta)

    def get_local_desktop_playback(self) -> dict | None:
        """
        Reads active or paused playback directly from the local Windows Spotify Desktop app
        and enriches cover/duration via /v1/search (cached per track).
        """
        win_track = get_spotify_window_track()
        if win_track is None:
            return None

        artist = win_track.get("artist", "").strip()
        title = win_track.get("title", "").strip()
        is_playing = bool(win_track.get("is_playing", False))

        if not title:
            if self._last_local_track:
                paused = dict(self._last_local_track)
                paused["is_playing"] = False
                paused["is_local_fallback"] = True
                return paused
            return None

        cache_key = f"{artist.lower()}|{title.lower()}"
        meta = self._local_track_cache.get(cache_key)

        # Also check partial match if Spotify window lists primary artist vs multi-artist string
        if not meta:
            for k, v in self._local_track_cache.items():
                if "|" in k and k.endswith(f"|{title.lower()}") and (artist.lower() in k or k.split("|")[0] in artist.lower()):
                    meta = v
                    break

        if not meta and self.sp and not getattr(self, "_search_rate_limited", False):
            try:
                found = self.search_tracks(f"{title} {artist}".strip(), limit=3)
                if found:
                    meta = found[0]
                    self._local_track_cache[cache_key] = meta
            except Exception as e:
                if "429" in str(e):
                    self._search_rate_limited = True
                meta = None

        if not meta:
            meta = {}

        local_pb = {
            "is_playing": is_playing,
            "track_id": meta.get("id") or meta.get("track_id") or f"local:{cache_key}",
            "title": meta.get("title") or title,
            "artist": meta.get("artist") or artist or "Spotify",
            "album": meta.get("album") or win_track.get("album") or "Spotify Desktop",
            "cover_url": meta.get("cover_url", ""),
            "progress_ms": win_track.get("progress_ms", 0) or 0,
            "duration_ms": win_track.get("duration_ms", 0) or meta.get("duration_ms", 210000) or 210000,
            "uri": meta.get("uri", ""),
            "is_local_fallback": True,
        }
        self._last_local_track = local_pb
        return local_pb

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

    def save_credentials(self, client_id: str, client_secret: str, clear_cache: bool = True):
        self.client_id = client_id.strip()
        self.client_secret = client_secret.strip()
        self._rate_limit_until = 0.0
        self.last_error_message = ""
        self._cached_recent_track = None
        self.last_device_id = None
        
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

        cache_dir = os.path.dirname(self.config_path)
        cache_path = os.path.join(cache_dir, ".spotify_token_cache")
        if clear_cache and os.path.exists(cache_path):
            try:
                os.remove(cache_path)
                print("[SpotifyClient] Cleared stale .spotify_token_cache for new credentials")
            except Exception as e:
                print(f"[SpotifyClient] Error clearing cache: {e}")

        self.is_connected = False
        self.sp = None
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
                self.session = _create_fast_session()
                self.sp = spotipy.Spotify(auth_manager=self.auth_manager, requests_session=self.session)
                self.is_connected = True
                self.last_error_message = ""
                self._detect_user_tier()
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

    def _refresh_token_and_session(self) -> bool:
        """
        Forces a token refresh via SpotifyOAuth and rebuilds spotipy.Spotify.
        Returns True if session is successfully revitalized.
        """
        try:
            if not self.auth_manager:
                return self.init_spotify()
            token_info = self.auth_manager.cache_handler.get_cached_token()
            if token_info and "refresh_token" in token_info:
                new_token = self.auth_manager.refresh_access_token(token_info["refresh_token"])
                if new_token:
                    self.session = _create_fast_session()
                    self.sp = spotipy.Spotify(auth_manager=self.auth_manager, requests_session=self.session)
                    self.is_connected = True
                    self.last_error_message = ""
                    self._detect_user_tier()
                    return True
            return self.init_spotify()
        except Exception as e:
            print(f"[SpotifyClient] Token refresh failed: {e}")
            self.is_connected = False
            self.sp = None
            return False

    def try_auto_reconnect(self, force_refresh: bool = False) -> bool:
        """Attempts to reconnect using cached credentials/tokens in a safe, non-blocking way."""
        if not self.client_id or not self.client_secret:
            return False
        if self.is_authenticating:
            return False
        if not force_refresh and self.is_connected and self.sp:
            return True
        if force_refresh:
            return self._refresh_token_and_session()
        return self.init_spotify()

    def start_single_shot_auth(self, on_done_callback):
        """Runs a safe, controlled single-shot OAuth in a background thread."""
        if self.is_authenticating:
            return
        self.is_authenticating = True

        def bg_auth():
            try:
                if not self.auth_manager:
                    self.init_spotify()
                auth_url = self.auth_manager.get_authorize_url()
                webbrowser.open(auth_url)

                OAuthCallbackHandler.auth_code = None
                OAuthCallbackHandler.auth_error = None

                server = ReusableHTTPServer(("127.0.0.1", 8888), OAuthCallbackHandler)
                server.timeout = 60  # 60s timeout

                while self.is_authenticating and not OAuthCallbackHandler.auth_code and not OAuthCallbackHandler.auth_error:
                    server.handle_request()

                server.server_close()

                if OAuthCallbackHandler.auth_code:
                    token_info = self.auth_manager.get_access_token(OAuthCallbackHandler.auth_code, as_dict=True)
                    if token_info:
                        self.session = _create_fast_session()
                        self.sp = spotipy.Spotify(auth_manager=self.auth_manager, requests_session=self.session)
                        self.is_connected = True
                        self.is_authenticating = False
                        self._rate_limit_until = 0.0
                        self.last_error_message = ""
                        self._cached_recent_track = None
                        self.last_device_id = None
                        self._detect_user_tier()
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

    def _parse_playback(self, playback: dict | None) -> dict | None:
        if not playback:
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

        parsed = {
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
        self.cache_track_metadata(parsed)
        return parsed

    def get_current_playback(self) -> dict | None:
        import time
        now = time.time()
        if now < self._rate_limit_until:
            # Under active rate-limiting backoff: directly return local desktop playback
            return self.get_local_desktop_playback()

        if not self._ensure_connected():
            return None

        for attempt in range(2):
            try:
                playback = self.sp.current_playback()
                if not playback:
                    # Check local desktop playback first before recently played
                    local_pb = self.get_local_desktop_playback()
                    if local_pb and local_pb.get("title") and local_pb.get("title") != "-":
                        return local_pb

                    # Serve cached recent track or throttle recently_played to once per 60s
                    if now - self._last_recent_fetch < 60.0:
                        return self._cached_recent_track

                    self._last_recent_fetch = now
                    try:
                        recent = self.sp.current_user_recently_played(limit=1)
                        if recent and recent.get("items"):
                            item = recent["items"][0].get("track")
                            if item:
                                artists = ", ".join([a["name"] for a in item.get("artists", [])])
                                images = item.get("album", {}).get("images", [])
                                cover_url = images[0]["url"] if images else ""
                                self._cached_recent_track = {
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
                                return self._cached_recent_track
                    except Exception:
                        pass
                    return None

                # Reset cached recent track when active playback is confirmed
                self._cached_recent_track = None
                self.last_error_message = ""
                return self._parse_playback(playback)

            except SpotifyException as se:
                print(f"[SpotifyClient] SpotifyException in playback (attempt {attempt+1}): {se}")
                if se.http_status == 401 and attempt == 0:
                    print("[SpotifyClient] Token kedaluwarsa (401). Memperbarui token dan sesi...")
                    if self._refresh_token_and_session():
                        continue
                    else:
                        self.is_connected = False
                        return None
                elif se.http_status == 429:
                    self._record_rate_limit(se)
                    return self.get_local_desktop_playback()
                elif se.http_status == 401:
                    self.is_connected = False
                return None
            except Exception as e:
                print(f"[SpotifyClient] General error in playback: {e}")
                return None

        return None

    def get_best_device_id(self) -> tuple[str | None, str]:
        """
        Finds the best active or standby Spotify Connect device.
        Returns (device_id, description_or_name).
        """
        if not self._ensure_connected():
            return None, "Spotify belum terhubung."
        if self.last_device_id:
            return self.last_device_id, self.last_device_name
        if self.is_rate_limited():
            return None, "Kuota API Spotify Developer sedang habis (429 Rate Limit). Gunakan akun developer lain atau tunggu reset kuota."
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
        except SpotifyException as se:
            print(f"[SpotifyClient] get_best_device_id SpotifyException: {se}")
            if se.http_status == 429:
                self._record_rate_limit(se)
                return None, "Kuota API Spotify Developer sedang habis (429 Rate Limit). Gunakan akun developer lain atau tunggu reset kuota."
            return None, f"Error perangkat: {se}"
        except Exception as e:
            err_str = str(e)
            print(f"[SpotifyClient] get_best_device_id error: {err_str}")
            if "QUOTA_EXCEEDED" in err_str or "429" in err_str:
                self._record_rate_limit(e)
                return None, "Kuota API Spotify Developer sedang habis (429 Rate Limit). Gunakan akun developer lain atau tunggu reset kuota."
            return None, f"Error perangkat: {e}"

    def toggle_play(self, current_is_playing: bool) -> bool:
        if self.user_product == "free" or self.is_rate_limited():
            return send_spotify_media_command("play_pause")
        if not self.sp:
            return False
        try:
            if current_is_playing:
                self.sp.pause_playback()
            else:
                dev_id = self.last_device_id
                if not dev_id:
                    dev_id, _ = self.get_best_device_id()
                if dev_id:
                    self.sp.start_playback(device_id=dev_id)
                else:
                    self.sp.start_playback()
            return True
        except SpotifyException as se:
            print(f"[SpotifyClient] toggle_play SpotifyException: {se}")
            if se.http_status == 429:
                self._record_rate_limit(se)
            if se.http_status in (429, 403, 404):
                return send_spotify_media_command("play_pause")
            return False
        except Exception as e:
            print(f"[SpotifyClient] toggle_play error: {e}")
            if "429" in str(e) or "QUOTA_EXCEEDED" in str(e):
                self._record_rate_limit(e)
                return send_spotify_media_command("play_pause")
            return False

    def next_track(self) -> bool:
        if self.user_product == "free" or self.is_rate_limited():
            return send_spotify_media_command("next")
        if not self.sp:
            return False
        try:
            self.sp.next_track()
            return True
        except SpotifyException as se:
            print(f"[SpotifyClient] next_track SpotifyException: {se}")
            if se.http_status == 429:
                self._record_rate_limit(se)
            if se.http_status in (429, 403, 404):
                return send_spotify_media_command("next")
            return False
        except Exception as e:
            print(f"[SpotifyClient] next_track error: {e}")
            if "429" in str(e) or "QUOTA_EXCEEDED" in str(e):
                self._record_rate_limit(e)
                return send_spotify_media_command("next")
            return False

    def previous_track(self) -> bool:
        if self.user_product == "free" or self.is_rate_limited():
            return send_spotify_media_command("prev")
        if not self.sp:
            return False
        try:
            self.sp.previous_track()
            return True
        except SpotifyException as se:
            print(f"[SpotifyClient] previous_track SpotifyException: {se}")
            if se.http_status == 429:
                self._record_rate_limit(se)
            if se.http_status in (429, 403, 404):
                return send_spotify_media_command("prev")
            return False
        except Exception as e:
            print(f"[SpotifyClient] previous_track error: {e}")
            if "429" in str(e) or "QUOTA_EXCEEDED" in str(e):
                self._record_rate_limit(e)
                return send_spotify_media_command("prev")
            return False

    def seek(self, position_ms: int) -> bool:
        if not self.sp or self.is_rate_limited():
            return False
        try:
            self.sp.seek_track(position_ms)
            return True
        except SpotifyException as se:
            if se.http_status == 429:
                self._record_rate_limit(se)
            print(f"[SpotifyClient] seek error: {se}")
            return False
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
        except SpotifyException as se:
            if se.http_status == 429:
                self._record_rate_limit(se)
            print(f"[SpotifyClient] get_queue error: {se}")
            return []
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
                track_dict = {
                    "id": item.get("id", ""),
                    "title": item.get("name", "Unknown"),
                    "artist": artists,
                    "album": item.get("album", {}).get("name", ""),
                    "album_uri": a_uri,
                    "duration_ms": item.get("duration_ms", 0),
                    "cover_url": cover_url,
                    "uri": t_uri
                }
                self.cache_track_metadata(track_dict)
                results.append(track_dict)
            return results
        except Exception as e:
            print(f"[SpotifyClient] search_tracks error: {e}")
            return []

    def add_to_queue(self, uri: str) -> tuple[bool, str]:
        if not self._ensure_connected() or not uri:
            return False, "Spotify belum terhubung."
        if self.user_product == "free":
            return False, "Akun Spotify Free: antrean API memerlukan Spotify Premium. Gunakan tombol ▶ untuk langsung memutar."
        if self.is_rate_limited():
            return False, "Kuota API Spotify Developer sedang habis (429 Rate Limit)."
        try:
            real_uri = self._resolve_uri(uri)
            dev_id = self.last_device_id
            if not dev_id:
                dev_id, _ = self.get_best_device_id()
            if dev_id:
                self.sp.add_to_queue(real_uri, device_id=dev_id)
            else:
                self.sp.add_to_queue(real_uri)
            return True, "Berhasil ditambahkan ke antrean"
        except SpotifyException as se:
            if se.http_status == 403:
                return False, "Akun Spotify Free: antrean API memerlukan Spotify Premium."
            elif se.http_status == 429:
                self._record_rate_limit(se)
                return False, "Kuota API Spotify Developer sedang habis (429 Rate Limit)."
            return False, "Gagal menambahkan ke antrean."
        except Exception as e:
            err_str = str(e)
            print(f"[SpotifyClient] add_to_queue error: {err_str}")
            if "QUOTA_EXCEEDED" in err_str or "429" in err_str:
                self._record_rate_limit(e)
                return False, "Kuota API Spotify Developer sedang habis (429 Rate Limit)."
            return False, f"Gagal antrean: {e}"

    def _play_track_locally(self, real_uri: str, track_meta: dict | None = None) -> tuple[bool, str] | None:
        """Attempts to play the track URI via the local Windows Spotify Desktop app."""
        if play_spotify_uri_locally(real_uri):
            meta = track_meta or self._local_track_cache.get(real_uri, {})
            if isinstance(meta, dict) and meta.get("title"):
                self._last_local_track = {
                    "is_playing": True,
                    "track_id": meta.get("id") or meta.get("track_id") or real_uri,
                    "title": meta.get("title", "Unknown"),
                    "artist": meta.get("artist", "Spotify"),
                    "album": meta.get("album", "Spotify Desktop"),
                    "cover_url": meta.get("cover_url", ""),
                    "progress_ms": 0,
                    "duration_ms": meta.get("duration_ms", 210000) or 210000,
                    "uri": real_uri,
                    "is_local_fallback": True,
                }
            return True, "Memutar di Spotify Desktop (Mode Lokal)"
        return None

    def play_track(self, uri: str, context_uri: str | None = None, track_meta: dict | None = None) -> tuple[bool, str]:
        if not self._ensure_connected() or not uri:
            return False, "Spotify belum terhubung."
        if track_meta:
            self.cache_track_metadata(track_meta)
        try:
            real_uri = self._resolve_uri(uri)

            # 1. Rate-limited or Free tier account: use fast local desktop control directly (avoids 429 / 403)
            if self.user_product == "free" or self.is_rate_limited():
                local_res = self._play_track_locally(real_uri, track_meta)
                if local_res:
                    return local_res
                if self.is_rate_limited():
                    return False, "Kuota API Spotify Developer sedang habis (429 Rate Limit). Gunakan akun developer lain atau tunggu reset kuota."
                return False, "Akun Free: Membuka lagu di Spotify Desktop."

            # 2. Premium / Unknown: Attempt direct Spotify Web API first if client and device exist
            dev_id, dev_name = self.get_best_device_id()
            if dev_id and self.sp:
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

                try:
                    _do_start()
                    self._rate_limit_until = 0.0
                    self.last_error_message = ""
                    return True, f"Memutar di {dev_name} (Web API)"
                except SpotifyException as inner_se:
                    if inner_se.http_status in (404, 502, 503):
                        import time
                        self.sp.transfer_playback(device_id=dev_id, force_play=False)
                        time.sleep(0.3)
                        _do_start()
                        self._rate_limit_until = 0.0
                        self.last_error_message = ""
                        return True, f"Memutar di {dev_name} (Web API)"
                    elif inner_se.http_status == 429:
                        self._record_rate_limit(inner_se)
                    elif inner_se.http_status == 403:
                        pass
                    else:
                        raise inner_se

            # 2. Fallback to Local Desktop Mode if Web API is 429 or device unavailable
            local_res = self._play_track_locally(real_uri, track_meta)
            if local_res:
                return local_res
            return False, dev_name or "Gagal memutar lagu via Web API maupun lokal."
        except SpotifyException as se:
            print(f"[SpotifyClient] play_track SpotifyException: {se}")
            if se.http_status == 429:
                self._record_rate_limit(se)
            local_res = self._play_track_locally(uri, track_meta)
            if local_res:
                return local_res
            if se.http_status == 403:
                return False, "Akun Spotify Free: kontrol putar Web API memerlukan Spotify Premium."
            elif se.http_status == 404:
                return False, "Tidak ada perangkat aktif. Buka Spotify di PC/HP kamu."
            elif se.http_status == 429:
                return False, "Kuota API Spotify Developer sedang habis (429 Rate Limit). Tunggu reset atau gunakan akun lain."
            return False, f"Spotify error: {se.msg if hasattr(se, 'msg') else 'Gagal memutar'}"
        except Exception as e:
            err_str = str(e)
            print(f"[SpotifyClient] play_track error: {err_str}")
            if "QUOTA_EXCEEDED" in err_str or "429" in err_str:
                self._record_rate_limit(e)
                local_res = self._play_track_locally(uri, track_meta)
                if local_res:
                    return local_res
                return False, "Kuota API Spotify Developer sedang habis (429 Rate Limit). Gunakan akun developer lain atau tunggu reset kuota."
            return False, f"Gagal memutar: {e}"
