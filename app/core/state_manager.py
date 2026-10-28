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
        except Exception as e:
            print(f"[WorkerTask] Error: {e}")

class StateManager(QObject):
    playback_state_changed = pyqtSignal(dict)       # track info
    progress_updated = pyqtSignal(int, int, float)   # current_ms, total_ms, ratio
    lyrics_loaded = pyqtSignal(dict)                # lyrics dict
    active_lyric_changed = pyqtSignal(int, str, str)     # line_index, current_text, upcoming_text
    queue_updated = pyqtSignal(list)                # list of queue items
    connection_changed = pyqtSignal(bool)           # is connected

    # Internal thread-safe queued signals from background workers to main thread
    _playback_received = pyqtSignal(object)
    _lyrics_received = pyqtSignal(dict)
    _queue_received = pyqtSignal(list)
    _revert_play_state = pyqtSignal(bool)

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

        # Polling Timer (Checks Spotify every 1.5s while playing, 800ms while paused for instant resume)
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
        worker = WorkerTask(self._bg_fetch_playback)
        self.thread_pool.start(worker)

    def _bg_fetch_playback(self):
        if getattr(self.spotify, "is_authenticating", False):
            return

        if not self.spotify.is_connected:
            self._playback_received.emit(None)
            return

        try:
            playback = self.spotify.get_current_playback()
            self._playback_received.emit(playback)
        except Exception as e:
            print(f"[StateManager] bg_fetch_playback error: {e}")

    def _on_playback_received(self, playback: dict | None):
        """Executes safely on the MAIN GUI THREAD via Qt QueuedConnection"""
        if not self.spotify.is_connected:
            if not self.current_track:
                self._load_demo_track()
            return

        if not playback:
            if self.is_playing:
                self.is_playing = False
                self.tick_timer.stop()
                if self.current_track:
                    self.current_track["is_playing"] = False
                    self.playback_state_changed.emit(self.current_track)
            self.connection_changed.emit(True)
            return

        self.connection_changed.emit(True)
        prev_track_id = self.current_track.get("track_id") if self.current_track else None
        new_track_id = playback.get("track_id")
        server_progress = playback.get("progress_ms", 0)
        is_playing = playback.get("is_playing", False)
        was_paused = not self.is_playing

        self.current_track = playback
        self.duration_ms = playback.get("duration_ms", 1)
        self.is_playing = is_playing

        # Pause / Play handling executed strictly on the main thread
        if not is_playing:
            if self.tick_timer.isActive():
                self.tick_timer.stop()
            self.current_progress_ms = server_progress
            if self.poll_timer.interval() != 800:
                self.poll_timer.setInterval(800)  # Responsive 800ms poll to catch unpause quickly
        else:
            if self.poll_timer.interval() != 1500:
                self.poll_timer.setInterval(1500)
            
            self.last_tick_timestamp = time.time()
            if not self.tick_timer.isActive():
                self.tick_timer.start(self.tick_interval_ms)

            # Snap progress immediately if resuming from pause or changing song
            if was_paused or new_track_id != prev_track_id:
                self.current_progress_ms = server_progress
                self.active_lyric_idx = -1  # Force immediate lyric evaluation upon resume
            else:
                # Soft clock drift correction (avoids rubber-banding / jitter)
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

    def _load_demo_track(self):
        """Mock demo data matching Figma Redesign so user can see the exact UI immediately"""
        self.demo_mode = True
        demo_track = {
            "is_playing": True,
            "track_id": "ora-urus",
            "title": "Ora Urus",
            "artist": "Toton Caribo, Wizz Baker, Justy Aldrin, Jacson Zeran",
            "album": "East Bounce Session",
            "cover_url": "",
            "progress_ms": 154000,
            "duration_ms": 278000,
            "uri": "spotify:track:ora_urus"
        }
        self.current_track = demo_track
        self.current_progress_ms = 154000
        self.duration_ms = 278000
        self.is_playing = True
        self.last_tick_timestamp = time.time()
        self.tick_timer.start(self.tick_interval_ms)
        self.connection_changed.emit(False)
        self.playback_state_changed.emit(demo_track)

        # Mock demo lyrics from Figma Redesign
        demo_lyrics = {
            "synced": True,
            "lines": [
                {"time_ms": 138000, "text": "Sio ado, ko bikin pusing kepala tiap malam", "subtext": "Verse 2 • Toton Caribo"},
                {"time_ms": 144000, "text": "Janji manis tinggal cerita di ujung jalan", "subtext": "Pre-Chorus"},
                {"time_ms": 149000, "text": "Kalau begitu, sekarang hidup ni ko yang urus", "subtext": "Hidup ni ko yang urus, sa cape, ora urus"},
                {"time_ms": 154000, "text": "Hidup ni ko yang urus, sa cape, ora urus", "subtext": "Hook Utama • Beat Drop"},
                {"time_ms": 159000, "text": "Ba-ba-baby, oh, ba-ba-ba-ba-ba-baby", "subtext": "Chant Part I"},
                {"time_ms": 164000, "text": "Oh, ba-ba-baby, oh, ba-ba-ba-ba-ba-baby", "subtext": "Chant Part II"},
                {"time_ms": 169000, "text": "Ba-ba-baby, oh, ba-ba-ba-ba-ba-baby", "subtext": "Chorus Peak"},
                {"time_ms": 175000, "text": "Sa sudah malas tahu, terserah ko mau kemana", "subtext": "Outro Groove"},
                {"time_ms": 182000, "text": "Biar waktu yang bicara, sa jalan lurus saja", "subtext": "Fade Out"}
            ],
            "timestamps": [138000, 144000, 149000, 154000, 159000, 164000, 169000, 175000, 182000],
            "raw": ""
        }
        self.current_lyrics = demo_lyrics
        self.lyrics_loaded.emit(demo_lyrics)

        # Initial queue in demo mode
        demo_queue = [
            {"id": "ini-abadi", "title": "Ini Abadi", "artist": "Perunggu", "duration_ms": 242000, "cover_url": "", "uri": "spotify:track:ini_abadi"},
            {"id": "abadi-dendi", "title": "Abadi - Indo Version", "artist": "Dendi Nata", "duration_ms": 255000, "cover_url": "", "uri": "spotify:track:abadi_dendi"},
            {"id": "bunga-abadi", "title": "Bunga Abadi", "artist": "Rio Clappy", "duration_ms": 236000, "cover_url": "", "uri": "spotify:track:bunga_abadi"}
        ]
        self.queue_updated.emit(demo_queue)

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

    def _fetch_lyrics_and_queue(self, track_info: dict):
        self.active_lyric_idx = -1
        req_track_id = track_info.get("track_id", "")
        
        def bg_work():
            # 1. Fetch Lyrics in worker thread
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

            # 2. Fetch Queue in worker thread
            queue_items = self.spotify.get_queue()
            self._queue_received.emit(queue_items)

        self.thread_pool.start(WorkerTask(bg_work))

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
