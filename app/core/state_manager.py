import time
from PyQt6.QtCore import QObject, QTimer, pyqtSignal, QThreadPool, QRunnable
from app.core.spotify_client import SpotifyClient
from app.core.lyrics_client import LyricsClient

class WorkerTask(QRunnable):
    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            self.fn(*self.args, **self.kwargs)
        except RuntimeError as re:
            if "wrapped C/C++ object" not in str(re):
                print(f"[WorkerTask] RuntimeError: {re}")
        except Exception as e:
            print(f"[WorkerTask] Error: {e}")

class StateManager(QObject):
    playback_state_changed = pyqtSignal(dict)       # track info
    progress_updated = pyqtSignal(int, int, float)   # current_ms, total_ms, ratio
    lyrics_loaded = pyqtSignal(dict)                # lyrics dict
    active_lyric_changed = pyqtSignal(int, str, str)     # line_index, current_text, upcoming_text
    queue_updated = pyqtSignal(list)                # list of queue items
    connection_changed = pyqtSignal(bool)           # is connected
    track_play_result = pyqtSignal(bool, str)       # success, message

    # Internal thread-safe queued signals from background workers to main thread
    _playback_received = pyqtSignal(object)
    _lyrics_received = pyqtSignal(dict)
    _queue_received = pyqtSignal(list)
    _revert_play_state = pyqtSignal(bool)
    _revert_to_track = pyqtSignal(object, bool)
    _play_result_received = pyqtSignal(bool, str)

    def __init__(self, spotify_client: SpotifyClient, lyrics_client: LyricsClient):
        super().__init__()
        self.spotify = spotify_client
        self.lyrics = lyrics_client
        self.thread_pool = QThreadPool.globalInstance()

        # Connect internal signals to main thread slots
        self._playback_received.connect(self._on_playback_received)
        self._lyrics_received.connect(self._on_lyrics_received)
        self._queue_received.connect(self._on_queue_received)
        self._revert_play_state.connect(self._on_revert_play_state)
        self._revert_to_track.connect(self._on_revert_to_track)
        self._play_result_received.connect(self._on_play_result_received)

        # State tracking
        self.current_track: dict | None = None
        self.current_lyrics: dict | None = None
        self.active_lyric_idx: int = -1
        self.current_progress_ms: int = 0
        self.duration_ms: int = 0
        self.is_playing: bool = False
        self.last_poll_timestamp: float = time.time()
        self.last_tick_timestamp: float = time.time()
        self.demo_mode: bool = False
        self._play_lock_until: float = 0.0
        self._pending_track_uri: str = ""
        self._last_reconnect_attempt: float = 0.0
        self._is_shutting_down: bool = False
        self._is_polling: bool = False
        self._pause_start_timestamp: float = 0.0

        # Polling Timer (Checks Spotify adaptively: 1.5s playing, 1.0s quick pause, 3.0s-5.0s idle)
        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self._poll_spotify)
        self.poll_timer.start(1500)

        # High precision interpolation timer (Runs only when playing on main thread)
        self.tick_timer = QTimer(self)
        self.tick_timer.timeout.connect(self._interpolate_tick)
        self.tick_interval_ms = 40  # ~25 FPS, extremely low CPU (< 0.2%)

    def start(self):
        self._poll_spotify()

    def _poll_spotify(self):
        if getattr(self, "_is_shutting_down", False):
            return
        if getattr(self, "_is_polling", False):
            return
        self._is_polling = True
        worker = WorkerTask(self._bg_fetch_playback)
        self.thread_pool.start(worker)

    def _bg_fetch_playback(self):
        try:
            if getattr(self, "_is_shutting_down", False):
                return

            if getattr(self.spotify, "is_authenticating", False):
                return

            if not self.spotify.is_connected:
                # Try background auto-reconnect if credentials exist
                if self.spotify.client_id and self.spotify.client_secret:
                    now = time.time()
                    if now - self._last_reconnect_attempt > 4.0:
                        self._last_reconnect_attempt = now
                        if self.spotify.try_auto_reconnect():
                            self.connection_changed.emit(True)

                if not self.spotify.is_connected:
                    self._playback_received.emit(None)
                    return

            playback = self.spotify.get_current_playback()
            if playback is None and hasattr(self.spotify, "get_local_desktop_playback"):
                playback = self.spotify.get_local_desktop_playback()
            self._playback_received.emit(playback)
        except Exception as e:
            print(f"[StateManager] bg_fetch_playback error: {e}")
        finally:
            self._is_polling = False

    def force_reconnect(self) -> bool:
        """Forces an immediate token refresh and connection synchronization."""
        self._last_reconnect_attempt = 0.0
        self.spotify._rate_limit_until = 0.0
        success = self.spotify.try_auto_reconnect(force_refresh=True)
        self.connection_changed.emit(success)
        self._is_polling = False
        self._poll_spotify()
        return success

    def _on_playback_received(self, playback: dict | None):
        """Executes safely on the MAIN GUI THREAD via Qt QueuedConnection"""
        if getattr(self, "_is_shutting_down", False):
            return

        if not self.spotify.is_connected:
            if not self.current_track or self.current_track.get("title") != "-":
                self._load_disconnected_state()
            if self.poll_timer.interval() != 5000:
                self.poll_timer.setInterval(5000)
            return

        self.demo_mode = False
        now = time.time()
        in_play_lock = now < self._play_lock_until

        if not playback:
            if in_play_lock:
                return
            if self.is_playing:
                self.is_playing = False
                self.tick_timer.stop()
                if self.current_track:
                    self.current_track["is_playing"] = False
                    self.playback_state_changed.emit(self.current_track)
            elif not self.current_track or self.current_track.get("title") == "-":
                # Spotify is connected, but idle with no active playback
                standby_track = {
                    "is_playing": False,
                    "track_id": "",
                    "title": "-",
                    "artist": "-",
                    "album": "Spotify Standby",
                    "cover_url": "",
                    "progress_ms": 0,
                    "duration_ms": 0,
                    "uri": ""
                }
                self.current_track = standby_track
                self.playback_state_changed.emit(standby_track)
            self.connection_changed.emit(True)
            if self.poll_timer.interval() != 5000:
                self.poll_timer.setInterval(5000)
            return

        if in_play_lock and self._pending_track_uri and playback.get("uri") != self._pending_track_uri:
            # Ignore stale poll response while Spotify is transitioning to the newly requested track
            return

        if self._pending_track_uri and playback.get("uri") == self._pending_track_uri:
            self._play_lock_until = 0.0
            self._pending_track_uri = ""

        self.connection_changed.emit(True)
        prev_track_id = self.current_track.get("track_id") if self.current_track else None
        new_track_id = playback.get("track_id")
        server_progress = playback.get("progress_ms", 0)
        is_playing = playback.get("is_playing", False)
        is_local = bool(playback.get("is_local_fallback", False))
        was_paused = not self.is_playing

        self.current_track = playback
        self.duration_ms = max(1, playback.get("duration_ms", 1))
        self.is_playing = is_playing

        # Pause / Play handling executed strictly on the main thread
        if not is_playing:
            if self.tick_timer.isActive():
                self.tick_timer.stop()
            if server_progress > 0 or new_track_id != prev_track_id:
                self.current_progress_ms = server_progress
            
            # Adaptive pause backoff:
            if was_paused and self._pause_start_timestamp > 0.0:
                pause_duration = now - self._pause_start_timestamp
                if pause_duration < 15.0:
                    desired_interval = 800  # Responsive 800ms to catch quick unpause
                elif pause_duration < 120.0:
                    desired_interval = 3000  # Relaxed 3s to conserve API quota
                else:
                    desired_interval = 5000  # Long pause backoff 5s
            else:
                self._pause_start_timestamp = now
                desired_interval = 800

            if self.poll_timer.interval() != desired_interval:
                self.poll_timer.setInterval(desired_interval)
        else:
            self._pause_start_timestamp = 0.0
            if self.poll_timer.interval() != 1500:
                self.poll_timer.setInterval(1500)
            
            self.last_tick_timestamp = time.time()
            if not self.tick_timer.isActive():
                self.tick_timer.start(self.tick_interval_ms)

            # Snap progress immediately if resuming from pause or changing song
            if new_track_id != prev_track_id or was_paused:
                self.current_progress_ms = server_progress
                self.active_lyric_idx = -1  # Force immediate lyric evaluation upon song change
            else:
                # Soft clock drift correction (avoids rubber-banding / jitter)
                if server_progress > 0 or not is_local:
                    drift = abs(server_progress - self.current_progress_ms)
                    if drift > 800:
                        self.current_progress_ms = server_progress
                    else:
                        self.current_progress_ms += int((server_progress - self.current_progress_ms) * 0.3)

        self.playback_state_changed.emit(playback)
        self._emit_progress()
        if self.is_playing:
            self._check_lyrics_sync()

        # If track changed, immediately wipe old lyrics and fetch new ones
        if new_track_id != prev_track_id:
            self.current_lyrics = None
            self.active_lyric_idx = -1
            self.active_lyric_changed.emit(-1, "", "")
            self._fetch_lyrics_and_queue(playback)

    def _load_disconnected_state(self):
        """Clean disconnected state showing '-' when not connected to Spotify"""
        self.demo_mode = False
        disc_track = {
            "is_playing": False,
            "track_id": "",
            "title": "-",
            "artist": "-",
            "album": "-",
            "cover_url": "",
            "progress_ms": 0,
            "duration_ms": 0,
            "uri": ""
        }
        self.current_track = disc_track
        self.current_progress_ms = 0
        self.duration_ms = 0
        self.is_playing = False
        if self.tick_timer.isActive():
            self.tick_timer.stop()
        self.connection_changed.emit(False)
        self.playback_state_changed.emit(disc_track)
        self.current_lyrics = None
        self.active_lyric_idx = -1
        self.lyrics_loaded.emit({"synced": False, "lines": [], "timestamps": [], "raw": ""})
        self.active_lyric_changed.emit(-1, "", "")
        self.queue_updated.emit([])

    def _load_demo_track(self):
        """Fallback pointing to disconnected state with '-' placeholder"""
        self._load_disconnected_state()

    def shutdown(self):
        self._is_shutting_down = True
        if hasattr(self, "poll_timer"):
            self.poll_timer.stop()
        if hasattr(self, "tick_timer"):
            self.tick_timer.stop()
        if hasattr(self, "thread_pool"):
            try:
                self.thread_pool.clear()
            except Exception:
                pass

    def _interpolate_tick(self):
        """Interpolates playback progress between API polls for 60fps smooth progress"""
        if not self.is_playing:
            return

        now = time.time()
        delta_ms = int((now - self.last_tick_timestamp) * 1000)
        self.last_tick_timestamp = now

        if delta_ms > 0:
            self.current_progress_ms = min(self.current_progress_ms + delta_ms, self.duration_ms)
            self._emit_progress()
            self._check_lyrics_sync()

    def _emit_progress(self):
        ratio = max(0.0, min(1.0, self.current_progress_ms / max(1, self.duration_ms)))
        self.progress_updated.emit(self.current_progress_ms, self.duration_ms, ratio)

    def _check_lyrics_sync(self):
        if not self.current_lyrics or not self.current_lyrics.get("synced"):
            return

        timestamps = self.current_lyrics.get("timestamps", [])
        if not timestamps:
            return

        # Anticipation offset +150ms for human-ear vocal sync
        sync_time_ms = self.current_progress_ms + 150
        idx = LyricsClient.find_active_index(timestamps, sync_time_ms)
        if idx != self.active_lyric_idx:
            self.active_lyric_idx = idx
            lines = self.current_lyrics.get("lines", [])
            text = lines[idx]["text"] if 0 <= idx < len(lines) else ""
            next_text = lines[idx + 1]["text"] if 0 <= idx + 1 < len(lines) else ""
            self.active_lyric_changed.emit(idx, text, next_text)

    def _fetch_lyrics_worker(self, track_info: dict):
        self.active_lyric_idx = -1
        req_track_id = track_info.get("track_id", "")
        
        def bg_work():
            lyrics_data = self.lyrics.fetch_lyrics(
                track_name=track_info.get("title", ""),
                artist_name=track_info.get("artist", ""),
                album_name=track_info.get("album", ""),
                duration_sec=int(track_info.get("duration_ms", 0) / 1000)
            )
            if lyrics_data is not None:
                lyrics_data = dict(lyrics_data)
                lyrics_data["_track_id"] = req_track_id
                self._lyrics_received.emit(lyrics_data)

        self.thread_pool.start(WorkerTask(bg_work))

    def _fetch_lyrics_and_queue(self, track_info: dict):
        self._fetch_lyrics_worker(track_info)
        self.fetch_queue()

    def _on_lyrics_received(self, lyrics_data: dict):
        """Runs safely on the MAIN GUI THREAD"""
        req_id = lyrics_data.get("_track_id")
        curr_id = self.current_track.get("track_id") if self.current_track else None
        if req_id and curr_id and req_id != curr_id:
            return  # Ignore stale lyrics from previous track

        self.current_lyrics = lyrics_data
        self.lyrics_loaded.emit(lyrics_data)
        self.active_lyric_idx = -1

        if not lyrics_data.get("lines"):
            # No lyrics available -> clear lyric so PillView shows Title & Author only
            self.active_lyric_changed.emit(-1, "", "")
        else:
            self._check_lyrics_sync()

    def _on_queue_received(self, queue_items: list):
        """Runs safely on the MAIN GUI THREAD"""
        self.queue_updated.emit(queue_items)

    def _on_revert_play_state(self, target_state: bool):
        """Runs safely on the MAIN GUI THREAD if Spotify API call failed"""
        self.is_playing = target_state
        if self.is_playing:
            self.last_tick_timestamp = time.time()
            if not self.tick_timer.isActive():
                self.tick_timer.start(self.tick_interval_ms)
        else:
            self.tick_timer.stop()
        if self.current_track:
            self.current_track["is_playing"] = self.is_playing
            self.playback_state_changed.emit(self.current_track)

    def _on_revert_to_track(self, old_track: dict | None, old_playing: bool):
        """Runs safely on MAIN GUI THREAD to restore track metadata if remote play failed"""
        self.current_track = old_track
        self.is_playing = old_playing
        if self.is_playing:
            self.last_tick_timestamp = time.time()
            if not self.tick_timer.isActive():
                self.tick_timer.start(self.tick_interval_ms)
        else:
            self.tick_timer.stop()
        if self.current_track:
            self.current_track["is_playing"] = self.is_playing
            self.playback_state_changed.emit(self.current_track)

    def _on_play_result_received(self, success: bool, message: str):
        """Emits play result status to UI on the main thread"""
        self.track_play_result.emit(success, message)

    def play_track(self, uri: str, track_meta: dict | None = None):
        """
        Plays a track by URI with optimistic UI update and multi-mode support (Spotify or Demo).
        """
        if not uri:
            return

        # 1. Demo Mode or Offline Mode
        if self.demo_mode or not self.spotify.is_connected:
            title = track_meta.get("title", "Lagu Demo") if track_meta else "Lagu Demo"
            artist = track_meta.get("artist", "") if track_meta else ""
            cover_url = track_meta.get("cover_url", "") if track_meta else ""
            dur_ms = track_meta.get("duration_ms", 210000) if track_meta else 210000

            new_track = {
                "is_playing": True,
                "track_id": track_meta.get("id", uri) if track_meta else uri,
                "title": title,
                "artist": artist,
                "album": "Single",
                "cover_url": cover_url,
                "progress_ms": 0,
                "duration_ms": dur_ms,
                "uri": uri
            }
            self.current_track = new_track
            self.current_progress_ms = 0
            self.duration_ms = dur_ms
            self.is_playing = True
            self.last_tick_timestamp = time.time()
            if not self.tick_timer.isActive():
                self.tick_timer.start(self.tick_interval_ms)
            self.playback_state_changed.emit(new_track)
            self._fetch_lyrics_and_queue(new_track)
            self.track_play_result.emit(True, f"Memutar (Demo): {title[:20]}")
            return

        # 2. Spotify Connected Mode (Optimistic UI Update + Background API Call)
        self.demo_mode = False
        old_track = self.current_track.copy() if self.current_track else None
        old_playing = self.is_playing
        self._play_lock_until = time.time() + 2.8
        self._pending_track_uri = uri

        if track_meta:
            if hasattr(self.spotify, "cache_track_metadata"):
                self.spotify.cache_track_metadata(track_meta)
            optimistic_track = {
                "is_playing": True,
                "track_id": track_meta.get("id", uri),
                "title": track_meta.get("title", "Memuat..."),
                "artist": track_meta.get("artist", ""),
                "album": track_meta.get("album", ""),
                "cover_url": track_meta.get("cover_url", ""),
                "progress_ms": 0,
                "duration_ms": track_meta.get("duration_ms", 0),
                "uri": uri
            }
            self.current_track = optimistic_track
            self.current_progress_ms = 0
            self.duration_ms = max(1, optimistic_track["duration_ms"])
            self.is_playing = True
            self.last_tick_timestamp = time.time()
            if not self.tick_timer.isActive():
                self.tick_timer.start(self.tick_interval_ms)
            self.playback_state_changed.emit(optimistic_track)
            self._emit_progress()
            self.current_lyrics = None
            self.active_lyric_idx = -1
            self.active_lyric_changed.emit(-1, "", "")
            self._fetch_lyrics_and_queue(optimistic_track)

        album_uri = track_meta.get("album_uri", "") if isinstance(track_meta, dict) else ""

        def bg_worker():
            success, message = self.spotify.play_track(uri, context_uri=album_uri)
            self._play_result_received.emit(success, message)
            if success:
                if not (hasattr(self.spotify, "is_rate_limited") and self.spotify.is_rate_limited()):
                    time.sleep(0.6)
                    self._bg_fetch_playback()
            else:
                self._play_lock_until = 0.0
                self._pending_track_uri = ""
                if old_track:
                    self._revert_to_track.emit(old_track, old_playing)

        self.thread_pool.start(WorkerTask(bg_worker))

    def add_to_queue(self, uri: str, track_meta: dict | None = None):
        if self.demo_mode or not self.spotify.is_connected:
            self.track_play_result.emit(True, "Ditambahkan ke antrean (Demo)")
            return

        def bg_worker():
            success, msg = self.spotify.add_to_queue(uri)
            self._play_result_received.emit(success, msg)
            if success:
                time.sleep(0.4)
                self.fetch_queue()

        self.thread_pool.start(WorkerTask(bg_worker))

    def fetch_queue(self):
        def bg_work():
            queue_items = self.spotify.get_queue()
            self._queue_received.emit(queue_items)
        self.thread_pool.start(WorkerTask(bg_work))

    # Control Actions
    def toggle_play(self):
        if self.demo_mode:
            self.is_playing = not self.is_playing
            if self.is_playing:
                self.last_tick_timestamp = time.time()
                self.tick_timer.start(self.tick_interval_ms)
            else:
                self.tick_timer.stop()
            if self.current_track:
                self.current_track["is_playing"] = self.is_playing
                self.playback_state_changed.emit(self.current_track)
            return

        target_state = self.is_playing  # True if was playing, False if was paused
        self.is_playing = not target_state
        if self.is_playing:
            self.last_tick_timestamp = time.time()
            if not self.tick_timer.isActive():
                self.tick_timer.start(self.tick_interval_ms)
            self.active_lyric_idx = -1
            self._check_lyrics_sync()
        else:
            self.tick_timer.stop()

        if self.current_track:
            self.current_track["is_playing"] = self.is_playing
            self.playback_state_changed.emit(self.current_track)

        def bg_toggle():
            success = self.spotify.toggle_play(target_state)
            if not success:
                self._revert_play_state.emit(target_state)
            else:
                time.sleep(0.4)
                self._bg_fetch_playback()

        self.thread_pool.start(WorkerTask(bg_toggle))

    def next_track(self):
        if self.demo_mode:
            self.current_progress_ms = 0
            self._emit_progress()
            return
        self.thread_pool.start(WorkerTask(self._bg_next))

    def _bg_next(self):
        self.spotify.next_track()
        time.sleep(0.3)
        self._bg_fetch_playback()

    def previous_track(self):
        if self.demo_mode:
            self.current_progress_ms = 0
            self._emit_progress()
            return
        self.thread_pool.start(WorkerTask(self._bg_prev))

    def _bg_prev(self):
        self.spotify.previous_track()
        time.sleep(0.3)
        self._bg_fetch_playback()

    def seek(self, ratio: float):
        target_ms = int(ratio * self.duration_ms)
        self.current_progress_ms = target_ms
        self._emit_progress()
        self._check_lyrics_sync()
        if not self.demo_mode:
            self.thread_pool.start(WorkerTask(lambda: self.spotify.seek(target_ms)))
