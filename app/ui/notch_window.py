import sys
import os
import json
from PyQt6.QtWidgets import QWidget, QApplication, QVBoxLayout
from PyQt6.QtCore import Qt, QRect, QRectF, QPropertyAnimation, QSequentialAnimationGroup, QEasingCurve, QTimer, pyqtProperty, pyqtSignal
from PyQt6.QtGui import QPainter, QPainterPath, QColor, QPen, QBrush, QCursor, QFontDatabase, QIcon, QRadialGradient, QPixmap

from app.ui.pill_view import PillView
from app.ui.expanded_view import ExpandedView
from app.ui.styles import NOTCH_STYLESHEET
from app.utils.win32_helpers import set_no_activate, set_tool_window, activate_window_focus, ensure_topmost
from app.utils.color_helpers import extract_dominant_color, get_secondary_complement
from app.core.state_manager import WorkerTask

class NotchWindow(QWidget):
    search_results_ready = pyqtSignal(list)
    auth_done_signal = pyqtSignal(bool, str)

    def __init__(self, state_manager, image_cache, config: dict):
        super().__init__()
        self.state_mgr = state_manager
        self.img_cache = image_cache
        self.config = config

        # Load Montserrat font
        self._load_custom_fonts()

        # Dimensions & Configurations
        ui_cfg = config.get("ui", {})
        self.col_w = ui_cfg.get("notch_collapsed_width", 440)
        self.col_h = ui_cfg.get("notch_collapsed_height", 50)
        self.exp_w = ui_cfg.get("notch_expanded_width", 540)
        self.exp_h = ui_cfg.get("notch_expanded_height", 460)
        self.anim_dur = ui_cfg.get("animation_duration_ms", 240)
        self.collapse_delay = ui_cfg.get("auto_collapse_delay_ms", 350)
        self.default_idle_mode = ui_cfg.get("idle_mode", "lyrics")

        # Personalization & Glass Settings (Mode Hitam default)
        personal_cfg = config.get("personalization", {})
        self.glass_opacity = personal_cfg.get("opacity", 0.94)
        self.tint_rgb = personal_cfg.get("tint_rgb", "9, 10, 15")
        self.specular_rim = personal_cfg.get("specular_border", 0.18)
        self.chroma_glow = personal_cfg.get("chroma_glow", 0.25)
        self.notch_morph = personal_cfg.get("notch_morph", "hardware-flush")
        self.accent_mode = personal_cfg.get("accent_mode", "preset")
        self.accent_color = personal_cfg.get("accent_color", "#34D399")
        self.chroma_color_1 = QColor(self.accent_color)
        self.chroma_color_2 = QColor(get_secondary_complement(self.accent_color))

        self.is_expanded = False
        self._current_rect = QRect(0, 0, self.col_w, self.col_h)

        # Window Flags & Icon
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setStyleSheet(NOTCH_STYLESHEET)

        base_res_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        for rel in [os.path.join("app", "assets", "icon.png"), os.path.join("assets", "icon.png")]:
            ic_path = os.path.join(base_res_dir, rel)
            if os.path.exists(ic_path):
                self.setWindowIcon(QIcon(ic_path))
                break

        # Views
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self.pill_view = PillView(self)
        self.pill_view.set_idle_mode(self.default_idle_mode)

        spot_cfg = config.get("spotify", {})
        c_id = spot_cfg.get("client_id", "")
        c_secret = spot_cfg.get("client_secret", "")
        self.expanded_view = ExpandedView(c_id, c_secret, self)
        self.expanded_view.setFixedSize(self.exp_w, self.exp_h)
        self.expanded_view.setVisible(False)

        # Share ImageCache with QueueTab and SearchTab for real Spotify album covers
        self.expanded_view.queue_tab.set_image_cache(self.img_cache)
        self.expanded_view.search_tab.set_image_cache(self.img_cache)

        # Initialize and apply configuration across views
        self.expanded_view.apply_initial_config(config)
        self.pill_view.set_accent_color(self.accent_color)
        tier = getattr(self.state_mgr.spotify, "user_product", "")
        self.expanded_view.settings_tab.set_connected(self.state_mgr.spotify.is_connected, product_tier=tier)

        self.main_layout.addWidget(self.pill_view)
        self.main_layout.addWidget(self.expanded_view)

        # Timers
        self.auto_collapse_timer = QTimer(self)
        self.auto_collapse_timer.setSingleShot(True)
        self.auto_collapse_timer.timeout.connect(self.collapse)

        self.cursor_watchdog = QTimer(self)
        self.cursor_watchdog.setInterval(80)
        self.cursor_watchdog.timeout.connect(self._check_cursor_in_or_out)

        # Persistent Z-Order Watchdog: enforces Notch stays above all windows & widgets
        self.zorder_watchdog = QTimer(self)
        self.zorder_watchdog.setInterval(1000)
        self.zorder_watchdog.timeout.connect(self._maintain_topmost_zorder)
        self.zorder_watchdog.start()

        # Animations
        self.anim = QPropertyAnimation(self, b"animatedGeometry")
        self.anim.setDuration(self.anim_dur)
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.jiggle_group: QSequentialAnimationGroup | None = None
        self.startup_group: QSequentialAnimationGroup | None = None

        # Connect signals
        self._init_signals()

        # Initial positioning
        self._reposition_to_top_center(self.col_w, self.col_h)

    def _load_custom_fonts(self):
        """Loads bundled Montserrat fonts into QFontDatabase"""
        if getattr(sys, 'frozen', False):
            base_dir = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
            fonts_dir = os.path.join(base_dir, "app", "assets", "fonts")
            if not os.path.exists(fonts_dir):
                fonts_dir = os.path.join(base_dir, "assets", "fonts")
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            fonts_dir = os.path.join(base_dir, "assets", "fonts")

        for font_file in ["Montserrat.ttf", "Montserrat-Regular.ttf"]:
            full_path = os.path.join(fonts_dir, font_file)
            if os.path.exists(full_path):
                QFontDatabase.addApplicationFont(full_path)

    def _maintain_topmost_zorder(self):
        """Enforces true topmost z-order over all desktop applications and widgets."""
        if not self.isVisible():
            return
        ensure_topmost(int(self.winId()))
        self.raise_()

    def changeEvent(self, ev):
        super().changeEvent(ev)
        if self.isVisible():
            ensure_topmost(int(self.winId()))
            self.raise_()

    def showEvent(self, ev):
        super().showEvent(ev)
        hwnd = int(self.winId())
        set_no_activate(hwnd, enable=True)
        set_tool_window(hwnd)
        ensure_topmost(hwnd)
        self.raise_()
        QTimer.singleShot(50, self.run_startup_animation)

    def run_startup_animation(self):
        """Smooth jiggle drop animation when app first opens"""
        geo = self._get_target_screen_geometry()
        x = geo.x() + (geo.width() - self.col_w) // 2

        hidden_rect = QRect(x, geo.y() - self.col_h, self.col_w, self.col_h)
        overshoot_rect = QRect(x, geo.y() + 6, self.col_w, self.col_h)
        final_rect = QRect(x, geo.y(), self.col_w, self.col_h)

        self.setGeometry(hidden_rect)

        self.startup_group = QSequentialAnimationGroup(self)
        
        anim1 = QPropertyAnimation(self, b"animatedGeometry")
        anim1.setDuration(170)
        anim1.setStartValue(hidden_rect)
        anim1.setEndValue(overshoot_rect)
        anim1.setEasingCurve(QEasingCurve.Type.OutQuad)
        self.startup_group.addAnimation(anim1)

        anim2 = QPropertyAnimation(self, b"animatedGeometry")
        anim2.setDuration(140)
        anim2.setStartValue(overshoot_rect)
        anim2.setEndValue(final_rect)
        anim2.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.startup_group.addAnimation(anim2)

        def on_startup_finished():
            ensure_topmost(int(self.winId()))
            self.raise_()

        self.startup_group.finished.connect(on_startup_finished)
        self.startup_group.start()

    def _get_target_screen_geometry(self) -> QRect:
        screen = self.screen() or QApplication.primaryScreen()
        if screen:
            return screen.geometry()
        return QRect(0, 0, 1920, 1080)

    def _reposition_to_top_center(self, width: int, height: int):
        geo = self._get_target_screen_geometry()
        x = geo.x() + (geo.width() - width) // 2
        y = geo.y()
        self.setGeometry(x, y, width, height)
        self._current_rect = QRect(x, y, width, height)

    def get_animated_geom(self) -> QRect:
        return self._current_rect

    def set_animated_geom(self, rect: QRect):
        self._current_rect = rect
        self.setGeometry(rect)
        self.update()

    animatedGeometry = pyqtProperty(QRect, get_animated_geom, set_animated_geom)

    def _init_signals(self):
        # State manager events
        self.state_mgr.playback_state_changed.connect(self._on_playback_state)
        self.state_mgr.progress_updated.connect(self._on_progress_updated)
        self.state_mgr.lyrics_loaded.connect(self.expanded_view.lyrics_tab.set_lyrics)
        self.state_mgr.active_lyric_changed.connect(self._on_lyric_changed)
        self.state_mgr.queue_updated.connect(self.expanded_view.queue_tab.set_queue)
        self.state_mgr.connection_changed.connect(self._on_connection_changed)

        # Settings & Personalization
        self.expanded_view.settings_tab.idle_mode_changed.connect(self._on_idle_mode_changed)
        self.expanded_view.settings_tab.personalization_changed.connect(self._on_personalization_changed)

        # Input focus activation
        self.expanded_view.settings_tab.input_focused.connect(self._on_input_focused)
        self.expanded_view.search_tab.input_focused.connect(self._on_input_focused)

        # Image cache
        self.img_cache.image_loaded.connect(self._on_image_loaded)

        # View actions
        self.expanded_view.play_pause_clicked.connect(self.state_mgr.toggle_play)
        self.expanded_view.next_clicked.connect(self.state_mgr.next_track)
        self.expanded_view.prev_clicked.connect(self.state_mgr.previous_track)
        self.expanded_view.seek_clicked.connect(self.state_mgr.seek)
        self.expanded_view.collapse_clicked.connect(self.collapse)
        self.expanded_view.exit_clicked.connect(self._on_exit_requested)
        self.expanded_view.reconnect_requested.connect(self._on_reconnect_requested)

        # Queue tab actions
        self.expanded_view.queue_tab.refresh_requested.connect(self.state_mgr.fetch_queue)
        self.expanded_view.queue_tab.play_track_requested.connect(self._on_play_track)

        # Search tab actions
        self.expanded_view.search_tab.search_requested.connect(self._on_search)
        self.expanded_view.search_tab.play_track_requested.connect(self._on_play_track)
        self.expanded_view.search_tab.add_queue_requested.connect(self._on_add_queue)
        self.search_results_ready.connect(self.expanded_view.search_tab.set_results)
        self.state_mgr.track_play_result.connect(self.expanded_view.search_tab.show_feedback)

        # Settings tab credentials
        self.expanded_view.settings_tab.credentials_saved.connect(self._on_credentials_saved)
        self.auth_done_signal.connect(self._on_auth_finished)

    def _on_personalization_changed(self, data: dict):
        self.glass_opacity = data.get("opacity", self.glass_opacity)
        self.tint_rgb = data.get("tint_rgb", self.tint_rgb)
        self.specular_rim = data.get("specular_border", self.specular_rim)
        self.chroma_glow = data.get("chroma_glow", self.chroma_glow)
        self.notch_morph = data.get("notch_morph", self.notch_morph)

        if "accent_mode" in data:
            self.accent_mode = data["accent_mode"]

        if self.accent_mode in ("preset", "custom") and "accent_color" in data:
            self.accent_color = data["accent_color"]
            self.chroma_color_1 = QColor(self.accent_color)
            self.chroma_color_2 = QColor(get_secondary_complement(self.accent_color))
            self.pill_view.set_accent_color(self.accent_color)
            self.expanded_view.set_accent_color(self.accent_color)
        elif self.accent_mode == "auto":
            curr_pix = self.pill_view.current_cover
            if curr_pix and not curr_pix.isNull():
                self.accent_color = extract_dominant_color(curr_pix)
            else:
                self.accent_color = "#34D399"
            self.chroma_color_1 = QColor(self.accent_color)
            self.chroma_color_2 = QColor(get_secondary_complement(self.accent_color))
            self.pill_view.set_accent_color(self.accent_color)
            self.expanded_view.set_accent_color(self.accent_color)

        self._save_personalization_to_config()
        self.update()

    def _save_personalization_to_config(self):
        try:
            cfg_path = getattr(self.state_mgr.spotify, "config_path", None)
            if not cfg_path or not os.path.exists(cfg_path):
                base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                cfg_path = os.path.join(base_dir, "config.json")

            if os.path.exists(cfg_path):
                with open(cfg_path, "r", encoding="utf-8") as f:
                    cfg_data = json.load(f)
            else:
                cfg_data = {}

            if "personalization" not in cfg_data:
                cfg_data["personalization"] = {}

            p = cfg_data["personalization"]
            p["preset"] = self.expanded_view.settings_tab.selected_preset_id
            p["opacity"] = self.glass_opacity
            p["blur"] = self.expanded_view.settings_tab.glass_blur
            p["specular_border"] = self.specular_rim
            p["chroma_glow"] = self.chroma_glow
            p["tint_rgb"] = self.tint_rgb
            p["notch_morph"] = self.notch_morph
            p["scrubber_style"] = self.expanded_view.settings_tab.scrubber_style
            p["accent_mode"] = self.accent_mode
            p["accent_color"] = self.accent_color

            with open(cfg_path, "w", encoding="utf-8") as f:
                json.dump(cfg_data, f, indent=2)
        except Exception as e:
            print(f"[NotchWindow] Error saving personalization: {e}")

    def _on_idle_mode_changed(self, mode: str):
        self.pill_view.set_idle_mode(mode)
        self._save_idle_mode_to_config(mode)

    def _save_idle_mode_to_config(self, mode: str):
        try:
            cfg_path = getattr(self.state_mgr.spotify, "config_path", None)
            if not cfg_path or not os.path.exists(cfg_path):
                base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                cfg_path = os.path.join(base_dir, "config.json")

            if os.path.exists(cfg_path):
                with open(cfg_path, "r", encoding="utf-8") as f:
                    cfg_data = json.load(f)
            else:
                cfg_data = {}

            if "ui" not in cfg_data:
                cfg_data["ui"] = {}

            cfg_data["ui"]["idle_mode"] = mode

            with open(cfg_path, "w", encoding="utf-8") as f:
                json.dump(cfg_data, f, indent=2)
        except Exception as e:
            print(f"[NotchWindow] Error saving idle mode: {e}")

    def save_all_settings(self):
        """Ensures all current settings are flushed to disk."""
        self._save_personalization_to_config()
        if hasattr(self, "expanded_view") and hasattr(self.expanded_view, "settings_tab"):
            current_idle = self.expanded_view.settings_tab.combo_idle.currentData() or "lyrics"
            self._save_idle_mode_to_config(current_idle)

    def _on_connection_changed(self, is_connected: bool):
        err = getattr(self.state_mgr.spotify, "last_error_message", "")
        tier = getattr(self.state_mgr.spotify, "user_product", "")
        self.expanded_view.settings_tab.set_connected(is_connected, err, product_tier=tier)

    def _on_reconnect_requested(self):
        if hasattr(self, "state_mgr"):
            success = self.state_mgr.force_reconnect()
            err = getattr(self.state_mgr.spotify, "last_error_message", "")
            tier = getattr(self.state_mgr.spotify, "user_product", "")
            self.expanded_view.settings_tab.set_connected(success, err, product_tier=tier)

    def _on_exit_requested(self):
        self.hide()
        if hasattr(self, "exit_requested_callback") and callable(self.exit_requested_callback):
            self.exit_requested_callback()
            return
        self.save_all_settings()
        if hasattr(self, "state_mgr"):
            self.state_mgr.shutdown()
        try:
            from PyQt6.QtCore import QThreadPool
            QThreadPool.globalInstance().clear()
        except Exception:
            pass
        QApplication.quit()
        import os
        os._exit(0)

    def closeEvent(self, event):
        self.save_all_settings()
        super().closeEvent(event)

    def _on_play_track(self, uri: str, track_meta: dict | None = None):
        self.state_mgr.play_track(uri, track_meta)

    def _on_add_queue(self, uri: str, track_meta: dict | None = None):
        self.state_mgr.add_to_queue(uri, track_meta)

    def _on_input_focused(self):
        hwnd = int(self.winId())
        activate_window_focus(hwnd)

    def _on_lyric_changed(self, idx: int, text: str, next_text: str = ""):
        self.expanded_view.lyrics_tab.set_active_line(idx)
        self.pill_view.update_lyric(text, next_text)

    def _on_credentials_saved(self, client_id: str, client_secret: str):
        self.state_mgr.poll_timer.stop()
        self.expanded_view.settings_tab.btn_save.setEnabled(False)
        self.expanded_view.settings_tab.btn_save.setText("⏳ Membuka Browser...")

        def on_auth_done(success: bool, msg: str):
            self.auth_done_signal.emit(success, msg)

        # Cleanly save credentials and invalidate old token cache
        self.state_mgr.spotify.save_credentials(client_id, client_secret, clear_cache=True)
        self.expanded_view.settings_tab.set_credentials(client_id, client_secret)

        # Always launch single-shot auth so browser opens directly for user authorization
        self.state_mgr.spotify.start_single_shot_auth(on_auth_done)

    def _on_auth_finished(self, success: bool, msg: str):
        self.expanded_view.settings_tab.btn_save.setEnabled(True)
        self.expanded_view.settings_tab.btn_save.setText("Simpan & Hubungkan")
        err = getattr(self.state_mgr.spotify, "last_error_message", "") if not success else ""
        tier = getattr(self.state_mgr.spotify, "user_product", "")
        self.expanded_view.settings_tab.set_connected(success, err or (msg if not success else ""), product_tier=tier)
        if success:
            self.state_mgr.demo_mode = False
            self.state_mgr.poll_timer.start(1500)
            self.state_mgr._poll_spotify()

    def _on_search(self, query: str):
        self._search_seq = getattr(self, "_search_seq", 0) + 1
        req_seq = self._search_seq
        def bg_search():
            tracks = self.state_mgr.spotify.search_tracks(query)
            if getattr(self, "_search_seq", 0) == req_seq:
                self.search_results_ready.emit(tracks)
        self.state_mgr.thread_pool.start(WorkerTask(bg_search))

    def _extract_dominant_colors(self, pixmap: QPixmap | None):
        """Extracts dominant colors from the album cover or applies user-selected accent"""
        if self.accent_mode == "auto":
            dom_hex = extract_dominant_color(pixmap)
            self.accent_color = dom_hex
            self.chroma_color_1 = QColor(self.accent_color)
            self.chroma_color_2 = QColor(get_secondary_complement(self.accent_color))
            self.pill_view.set_accent_color(self.accent_color)
            self.expanded_view.set_accent_color(self.accent_color)
        else:
            self.chroma_color_1 = QColor(self.accent_color)
            self.chroma_color_2 = QColor(get_secondary_complement(self.accent_color))
        self.update()

    def _on_playback_state(self, track: dict):
        title = track.get("title", "")
        artist = track.get("artist", "")
        is_playing = track.get("is_playing", False)
        cover_url = track.get("cover_url", "")

        pix = self.img_cache.get_pixmap(cover_url, rounded_radius=12, size=56)
        self._extract_dominant_colors(pix)
        self.pill_view.update_track(title, artist, pix, is_playing)
        self.expanded_view.update_track(title, artist, pix, is_playing)

    def _on_image_loaded(self, url: str, raw_pixmap: QPixmap):
        # 1. Update main playback header & pill if url matches current track
        if self.state_mgr.current_track and self.state_mgr.current_track.get("cover_url") == url:
            processed = self.img_cache.process_and_cache(url, raw_pixmap, rounded_radius=12, size=56)
            self._extract_dominant_colors(processed)
            title = self.state_mgr.current_track.get("title", "")
            artist = self.state_mgr.current_track.get("artist", "")
            is_playing = self.state_mgr.current_track.get("is_playing", False)
            self.pill_view.update_track(title, artist, processed, is_playing)
            self.expanded_view.update_track(title, artist, processed, is_playing)

        # 2. Update QueueTab & SearchTab cards if any track uses this Spotify cover URL
        self.expanded_view.queue_tab.update_cover(url, raw_pixmap)
        self.expanded_view.search_tab.update_cover(url, raw_pixmap)

    def _on_progress_updated(self, curr_ms: int, total_ms: int, ratio: float):
        self.expanded_view.update_progress(curr_ms, total_ms, ratio)
        self.pill_view.update_progress(ratio)

    # Hover and Expansion Control
    def enterEvent(self, ev):
        super().enterEvent(ev)
        ensure_topmost(int(self.winId()))
        self.raise_()
        self.auto_collapse_timer.stop()
        if not self.is_expanded:
            self.expand()

    def leaveEvent(self, ev):
        super().leaveEvent(ev)
        if self.is_expanded and not self._is_any_input_focused():
            self.auto_collapse_timer.start(self.collapse_delay)

    def _is_any_input_focused(self) -> bool:
        return (
            self.expanded_view.search_tab.search_input.hasFocus() or
            self.expanded_view.settings_tab.id_input.hasFocus() or
            self.expanded_view.settings_tab.secret_input.hasFocus()
        )

    def _check_cursor_in_or_out(self):
        if not self.is_expanded:
            self.cursor_watchdog.stop()
            return

        if self._is_any_input_focused():
            return

        pos = QCursor.pos()
        margin_rect = self.geometry().adjusted(-10, -5, 10, 15)
        if not margin_rect.contains(pos):
            if not self.auto_collapse_timer.isActive():
                self.auto_collapse_timer.start(self.collapse_delay)
        else:
            if self.auto_collapse_timer.isActive():
                self.auto_collapse_timer.stop()

    def expand(self):
        if self.is_expanded:
            return
        self.is_expanded = True
        ensure_topmost(int(self.winId()))
        self.raise_()
        self.auto_collapse_timer.stop()
        self.cursor_watchdog.start()

        if self.jiggle_group and self.jiggle_group.state() == QSequentialAnimationGroup.State.Running:
            self.jiggle_group.stop()

        geo = self._get_target_screen_geometry()
        start_rect = self.geometry()
        
        target_x = geo.x() + (geo.width() - self.exp_w) // 2
        target_rect = QRect(target_x, geo.y(), self.exp_w, self.exp_h)

        self.pill_view.setVisible(False)
        self.expanded_view.setVisible(True)

        self.anim.stop()
        self.anim.setDuration(self.anim_dur)
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.anim.setStartValue(start_rect)
        self.anim.setEndValue(target_rect)
        self.anim.start()

    def collapse(self):
        if not self.is_expanded:
            return
        self.is_expanded = False
        self.auto_collapse_timer.stop()
        self.cursor_watchdog.stop()

        hwnd = int(self.winId())
        set_no_activate(hwnd, enable=True)
        ensure_topmost(hwnd)
        self.raise_()

        geo = self._get_target_screen_geometry()
        start_rect = self.geometry()
        target_x = geo.x() + (geo.width() - self.col_w) // 2
        target_rect = QRect(target_x, geo.y(), self.col_w, self.col_h)

        self.expanded_view.setVisible(False)
        self.pill_view.setVisible(True)

        self.anim.stop()
        self.anim.setDuration(190)
        self.anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        self.anim.setStartValue(start_rect)
        self.anim.setEndValue(target_rect)

        def on_collapse_finished():
            ensure_topmost(int(self.winId()))
            self.raise_()
            self._run_collapse_jiggle(target_x, geo.y())

        try:
            self.anim.finished.disconnect()
        except TypeError:
            pass
        self.anim.finished.connect(on_collapse_finished)
        self.anim.start()

    def _run_collapse_jiggle(self, x: int, y: int):
        if self.is_expanded:
            return

        try:
            self.anim.finished.disconnect()
        except TypeError:
            pass

        base_rect = QRect(x, y, self.col_w, self.col_h)
        stretch_rect = QRect(x + 3, y, self.col_w - 6, self.col_h + 6)

        self.jiggle_group = QSequentialAnimationGroup(self)

        anim_stretch = QPropertyAnimation(self, b"animatedGeometry")
        anim_stretch.setDuration(80)
        anim_stretch.setStartValue(base_rect)
        anim_stretch.setEndValue(stretch_rect)
        anim_stretch.setEasingCurve(QEasingCurve.Type.OutQuad)
        self.jiggle_group.addAnimation(anim_stretch)

        anim_return = QPropertyAnimation(self, b"animatedGeometry")
        anim_return.setDuration(120)
        anim_return.setStartValue(stretch_rect)
        anim_return.setEndValue(base_rect)
        anim_return.setEasingCurve(QEasingCurve.Type.OutBounce)
        self.jiggle_group.addAnimation(anim_return)

        def on_jiggle_finished():
            ensure_topmost(int(self.winId()))
            self.raise_()

        self.jiggle_group.finished.connect(on_jiggle_finished)
        self.jiggle_group.start()

    def paintEvent(self, ev):
        """
        Draws the Dynamic Glass Notch Surface matching Gambar 1-3.
        - Supports Mode Hitam (Default Obsidian) or Customizable Glass
        - Ambient Chromatic Bleed glow using dominant colors from Spotify cover
        - 1px Specular Rim highlight
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = float(self.width())
        h = float(self.height())
        radius = 26.0 if self.is_expanded else 22.0

        path = QPainterPath()
        if self.notch_morph == "floating-island":
            path.addRoundedRect(QRectF(0, 0, w, h), radius, radius)
        elif self.notch_morph == "sharp-hud":
            path.addRoundedRect(QRectF(0, 0, w, h), 16.0, 16.0)
        else:
            # Hardware Flush (flat against top screen bezel, bottom corners rounded)
            path.moveTo(0, 0)
            path.lineTo(w, 0)
            path.lineTo(w, h - radius)
            path.quadTo(w, h, w - radius, h)
            path.lineTo(radius, h)
            path.quadTo(0, h, 0, h - radius)
            path.closeSubpath()

        # Parse Tint RGB and Opacity (keeps deep optical glass contrast on Windows desktop)
        try:
            rgb_parts = [int(p.strip()) for p in self.tint_rgb.split(",")]
            r, g, b = rgb_parts[0], rgb_parts[1], rgb_parts[2]
        except Exception:
            r, g, b = 9, 10, 15

        # Map glass_opacity [0.12 .. 1.0] to deep optical alpha [205 .. 252] so text and cards stay high-contrast
        alpha = max(195, min(253, int(190 + (self.glass_opacity * 62))))
        bg_color = QColor(r, g, b, alpha)
        painter.fillPath(path, bg_color)

        # Ambient Chromatic Glow (dynamic album cover accent bleed matching Gambar 1-3)
        if self.chroma_glow > 0.05:
            # Top-left primary accent ambient orb
            glow_grad1 = QRadialGradient(w * 0.16, 15.0, w * 0.58)
            c1 = QColor(self.chroma_color_1)
            c1.setAlpha(min(180, int(self.chroma_glow * 115)))
            glow_grad1.setColorAt(0.0, c1)
            c1_mid = QColor(self.chroma_color_1)
            c1_mid.setAlpha(min(140, int(self.chroma_glow * 45)))
            glow_grad1.setColorAt(0.60, c1_mid)
            glow_grad1.setColorAt(1.0, QColor(0, 0, 0, 0))
            painter.fillPath(path, QBrush(glow_grad1))

            # Bottom-right secondary complement ambient orb
            glow_grad2 = QRadialGradient(w * 0.85, h * 0.85, w * 0.55)
            c2 = QColor(self.chroma_color_2)
            c2.setAlpha(min(150, int(self.chroma_glow * 80)))
            glow_grad2.setColorAt(0.0, c2)
            glow_grad2.setColorAt(1.0, QColor(0, 0, 0, 0))
            painter.fillPath(path, QBrush(glow_grad2))

        # Specular 1px Inner Rim Highlight
        rim_alpha = max(10, min(255, int(self.specular_rim * 255)))
        pen = QPen(QColor(255, 255, 255, rim_alpha), 1.0)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

        painter.end()
