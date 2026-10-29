from PyQt6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QTabWidget
)
from PyQt6.QtCore import Qt, pyqtSignal, QRectF
from PyQt6.QtGui import QPixmap, QPainter, QColor, QBrush, QPen, QPainterPath

from app.ui.lyrics_tab import LyricsTab
from app.ui.queue_tab import QueueTab
from app.ui.search_tab import SearchTab
from app.ui.settings_tab import SettingsTab
from app.ui.custom_buttons import MediaPlayButton, MediaNavButton, CollapseChevronButton
from app.ui.waveform_scrubber import WaveformScrubber


class ExpandedCoverArt(QWidget):
    """52x52 rounded cover art with subtle border matching Gambar 1-3"""
    def __init__(self, size=52, parent=None):
        super().__init__(parent)
        self.size = size
        self.setFixedSize(size, size)
        self.pixmap: QPixmap | None = None
        self.accent_color = QColor("#34D399")

    def set_pixmap(self, pix: QPixmap | None):
        self.pixmap = pix
        self.update()

    def set_accent_color(self, hex_color: str):
        self.accent_color = QColor(hex_color)
        self.update()

    def paintEvent(self, ev):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        s = self.size
        r = 13.0

        if self.pixmap and not self.pixmap.isNull():
            scaled = self.pixmap.scaled(s, s, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            path = QPainterPath()
            path.addRoundedRect(QRectF(0, 0, s, s), r, r)
            painter.setClipPath(path)
            painter.drawPixmap(0, 0, scaled)
            painter.setClipping(False)
        else:
            from PyQt6.QtGui import QRadialGradient, QFont
            # Elegant dark vinyl squircle with subtle radial depth
            bg_grad = QRadialGradient(s * 0.5, s * 0.5, s * 0.7)
            bg_grad.setColorAt(0.0, QColor("#222736"))
            bg_grad.setColorAt(0.7, QColor("#141721"))
            bg_grad.setColorAt(1.0, QColor("#0C0E14"))

            path = QPainterPath()
            path.addRoundedRect(QRectF(0, 0, s, s), r, r)
            painter.setClipPath(path)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(bg_grad))
            painter.drawRoundedRect(QRectF(0, 0, s, s), r, r)

            # Subtle concentric vinyl record groove rings
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(255, 255, 255, 14), 1.0))
            for rad in [s * 0.38, s * 0.28, s * 0.18]:
                painter.drawEllipse(QRectF(s * 0.5 - rad, s * 0.5 - rad, rad * 2, rad * 2))

            # Centered musical note ♫ in glowing accent color
            painter.setPen(self.accent_color)
            f = QFont("Segoe UI Symbol", int(s * 0.36))
            f.setBold(True)
            painter.setFont(f)
            painter.drawText(QRectF(0, 0, s, s), Qt.AlignmentFlag.AlignCenter, "♫")
            painter.setClipping(False)

        painter.setPen(QPen(QColor(255, 255, 255, 55), 1.0))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(QRectF(0.5, 0.5, s - 1, s - 1), r, r)
        painter.end()

AlbumCoverWidget = ExpandedCoverArt


class NavPillButton(QFrame):
    """
    Custom tab selector pill button that properly sizes its label and optional badge
    ('3' or 'LAB') and dynamically switches badge colors between active/inactive states
    matching Gambar 1, 2, 3.
    """
    clicked = pyqtSignal()

    def __init__(self, label_text: str, badge_text: str | None = None, parent=None):
        super().__init__(parent)
        self.setObjectName("navPillBtn")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.is_active = False
        self.accent_color = "#34D399"

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(12, 6, 12, 6)
        self.layout.setSpacing(6)

        self.text_lbl = QLabel(label_text, self)
        self.text_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.layout.addWidget(self.text_lbl)

        self.badge_lbl: QLabel | None = None
        if badge_text is not None:
            self.badge_lbl = QLabel(badge_text, self)
            self.badge_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            self.badge_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.layout.addWidget(self.badge_lbl)

        self.set_active(False, self.accent_color)

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(ev)

    def click(self):
        self.clicked.emit()

    def set_badge_text(self, text: str):
        if self.badge_lbl is not None:
            self.badge_lbl.setText(text)

    def set_active(self, active: bool, accent_color: str = "#34D399"):
        self.is_active = active
        self.accent_color = accent_color

        if active:
            self.setStyleSheet(
                "#navPillBtn { "
                "background: rgba(255, 255, 255, 0.14); "
                "border: 1px solid rgba(255, 255, 255, 0.22); "
                "border-radius: 9px; "
                "}"
            )
            self.text_lbl.setStyleSheet(
                "color: #FFFFFF; font-size: 12px; font-weight: 700; "
                "background: transparent; border: none;"
            )
            if self.badge_lbl is not None:
                self.badge_lbl.setStyleSheet(
                    f"background: {accent_color}33; "
                    f"color: {accent_color}; "
                    "font-size: 9.5px; font-family: 'Courier New', monospace; font-weight: 700; "
                    "padding: 1px 6px; border-radius: 6px; border: none;"
                )
        else:
            self.setStyleSheet(
                "#navPillBtn { "
                "background: transparent; "
                "border: 1px solid transparent; "
                "border-radius: 9px; "
                "} "
                "#navPillBtn:hover { "
                "background: rgba(255, 255, 255, 0.06); "
                "}"
            )
            self.text_lbl.setStyleSheet(
                "color: rgba(255, 255, 255, 0.55); font-size: 12px; font-weight: 500; "
                "background: transparent; border: none;"
            )
            if self.badge_lbl is not None:
                self.badge_lbl.setStyleSheet(
                    "background: rgba(255, 255, 255, 0.08); "
                    "color: rgba(255, 255, 255, 0.58); "
                    "font-size: 9.5px; font-family: 'Courier New', monospace; font-weight: 600; "
                    "padding: 1px 6px; border-radius: 6px; border: none;"
                )


class QuickGlassButton(QPushButton):
    """
    Right-hand pill button '[ ● 58% Clear ]' with green indicator dot and glass border
    matching Gambar 1, 2, 3.
    """
    def __init__(self, text: str = "● 58% Clear", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.accent_color = QColor("#34D399")
        self._clear_pct = 58
        self._hovered = False
        self.setFixedHeight(32)
        self.setMinimumWidth(100)
        self.setText(text)

    def setText(self, text: str):
        super().setText(text)
        # Extract percentage if present
        cleaned = text.replace("●", "").strip()
        self._display_text = cleaned
        self.update()

    def set_accent_color(self, hex_color: str):
        self.accent_color = QColor(hex_color)
        self.update()

    def enterEvent(self, ev):
        super().enterEvent(ev)
        self._hovered = True
        self.update()

    def leaveEvent(self, ev):
        super().leaveEvent(ev)
        self._hovered = False
        self.update()

    def paintEvent(self, ev):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = float(self.width())
        h = float(self.height())

        bg_alpha = 26 if self._hovered else 15
        painter.setBrush(QBrush(QColor(255, 255, 255, bg_alpha)))
        painter.setPen(QPen(QColor(255, 255, 255, 42), 1.0))
        painter.drawRoundedRect(QRectF(0.5, 0.5, w - 1.0, h - 1.0), 11.0, 11.0)

        # Green dot on left
        dot_r = 4.0
        dot_x = 12.0
        dot_y = (h / 2.0) - dot_r
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(self.accent_color))
        painter.drawEllipse(QRectF(dot_x, dot_y, dot_r * 2.0, dot_r * 2.0))

        # Monospace label text
        from PyQt6.QtGui import QFont
        font = QFont("Courier New", 9)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor(255, 255, 255, 225))
        text_rect = QRectF(dot_x + dot_r * 2.0 + 6.0, 0, w - (dot_x + dot_r * 2.0 + 14.0), h)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, getattr(self, "_display_text", "58% Clear"))
        painter.end()

AlbumCoverWidget = ExpandedCoverArt


class ExpandedView(QWidget):
    """
    Redesigned App Notch matching Gambar 1, 2, 3.
    - Header: Cover 52x52, Title, Artist, 24-BIT FLAC quality badge
    - Transport cluster: Prev, Squircle Play/Pause with glow, Next, Collapse chevron ^
    - Capsule Waveform Scrubber with timestamps
    - Modern Pill Tab Bar: Lirik, Antrean (3), Cari, Personalisasi UI (LAB) + ● 58% Clear
    """
    play_pause_clicked = pyqtSignal()
    next_clicked = pyqtSignal()
    prev_clicked = pyqtSignal()
    seek_clicked = pyqtSignal(float)
    collapse_clicked = pyqtSignal()
    exit_clicked = pyqtSignal()

    def __init__(self, current_client_id: str = "", current_client_secret: str = "", parent=None):
        super().__init__(parent)
        self.accent_color = "#34D399"
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(16, 12, 16, 12)
        self.layout.setSpacing(10)

        # =====================================================================
        # 1. TOP HEADER: Cover + Title + Vector Controls + Collapse
        # =====================================================================
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(12)

        # Album Art
        self.cover_widget = ExpandedCoverArt(size=52, parent=self)
        header_layout.addWidget(self.cover_widget)

        # Label alias for backward compatibility with existing tests
        self.cover_label = QLabel(self)
        self.cover_label.setVisible(False)

        # Track Metadata
        meta_col = QVBoxLayout()
        meta_col.setContentsMargins(0, 1, 0, 1)
        meta_col.setSpacing(2)

        self.title_lbl = QLabel("-")
        self.title_lbl.setStyleSheet("font-size: 16px; font-weight: 800; color: #FFFFFF; letter-spacing: -0.3px;")
        
        self.artist_lbl = QLabel("-")
        self.artist_lbl.setStyleSheet("font-size: 12px; color: rgba(255, 255, 255, 0.65);")

        self.quality_lbl = QLabel("24-BIT / 96KHZ FLAC")
        self.quality_lbl.setStyleSheet(
            "font-size: 9.5px; font-family: 'Courier New', monospace; font-weight: 600; "
            "color: rgba(255, 255, 255, 0.45); letter-spacing: 0.5px;"
        )

        meta_col.addWidget(self.title_lbl)
        meta_col.addWidget(self.artist_lbl)
        meta_col.addWidget(self.quality_lbl)
        header_layout.addLayout(meta_col, 1)

        # Transport Cluster (Prev, Play Squircle, Next, Divider, Collapse ^)
        ctrl_layout = QHBoxLayout()
        ctrl_layout.setSpacing(6)

        self.btn_prev = MediaNavButton("prev")
        self.btn_prev.setToolTip("Lagu Sebelumnya")
        self.btn_prev.clicked.connect(self.prev_clicked.emit)
        ctrl_layout.addWidget(self.btn_prev)

        self.btn_play = MediaPlayButton()
        self.btn_play.setToolTip("Putar / Jeda")
        self.btn_play.clicked.connect(self.play_pause_clicked.emit)
        ctrl_layout.addWidget(self.btn_play)

        self.btn_next = MediaNavButton("next")
        self.btn_next.setToolTip("Lagu Berikutnya")
        self.btn_next.clicked.connect(self.next_clicked.emit)
        ctrl_layout.addWidget(self.btn_next)

        # Subtle vertical divider line matching Gambar 1-3
        divider = QLabel()
        divider.setFixedSize(1, 20)
        divider.setStyleSheet("background: rgba(255, 255, 255, 0.12);")
        ctrl_layout.addWidget(divider)

        # Collapse Button ^
        self.btn_collapse = CollapseChevronButton(self)
        self.btn_collapse.setToolTip("Ciutkan ke Pill Notch")
        self.btn_collapse.clicked.connect(self.collapse_clicked.emit)
        ctrl_layout.addWidget(self.btn_collapse)

        # Power Exit Button ⏻
        self.btn_exit = QPushButton("⏻", self)
        self.btn_exit.setProperty("class", "btn-exit")
        self.btn_exit.setToolTip("Keluar & Matikan Notch")
        self.btn_exit.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_exit.setFixedSize(30, 30)
        self.btn_exit.clicked.connect(self.exit_clicked.emit)
        ctrl_layout.addWidget(self.btn_exit)

        header_layout.addLayout(ctrl_layout)
        self.layout.addWidget(header_widget)

        # =====================================================================
        # 2. WAVEFORM SCRUBBER / TIMELINE
        # =====================================================================
        self.waveform_scrubber = WaveformScrubber(self)
        self.waveform_scrubber.seek_requested.connect(self.seek_clicked.emit)
        self.layout.addWidget(self.waveform_scrubber)

        # Slider alias for 100% backward compatibility with tests
        self.slider = self.waveform_scrubber
        self.curr_time_lbl = self.waveform_scrubber.time_curr_lbl
        self.total_time_lbl = self.waveform_scrubber.time_total_lbl

        # =====================================================================
        # 3. MODERN PILL NAVIGATION BAR (Gambar 1, 2, 3)
        # =====================================================================
        nav_container = QWidget()
        nav_layout = QHBoxLayout(nav_container)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(8)

        self.pills_box = QFrame()
        self.pills_box.setObjectName("pillsBox")
        self.pills_box.setStyleSheet(
            "#pillsBox { "
            "background: rgba(0, 0, 0, 0.32); "
            "border: 1px solid rgba(255, 255, 255, 0.08); "
            "border-radius: 13px; "
            "}"
        )
        pills_layout = QHBoxLayout(self.pills_box)
        pills_layout.setContentsMargins(4, 4, 4, 4)
        pills_layout.setSpacing(4)

        self.nav_buttons: list[NavPillButton] = []
        self.nav_labels: list[QLabel] = []
        tabs_meta = [
            ("Lirik", None),
            ("Antrean", "3"),
            ("Cari", None),
            ("Personalisasi UI", "LAB"),
        ]

        for idx, (label, tag) in enumerate(tabs_meta):
            btn = NavPillButton(label, tag, parent=self.pills_box)
            self.nav_labels.append(btn.text_lbl)
            if label == "Antrean" and btn.badge_lbl is not None:
                self.queue_badge_lbl = btn.badge_lbl

            btn.clicked.connect(lambda i=idx: self.switch_tab(i))
            pills_layout.addWidget(btn)
            self.nav_buttons.append(btn)

        nav_layout.addWidget(self.pills_box)
        nav_layout.addStretch()

        # Quick Glass Transparency status pill on top right: [ ● 58% Clear ]
        self.btn_quick_glass = QuickGlassButton("● 58% Clear", self)
        self.btn_quick_glass.setToolTip("Ubah cepat intensitas efek kaca tembus pandang")
        self.btn_quick_glass.clicked.connect(self._toggle_quick_glass)
        nav_layout.addWidget(self.btn_quick_glass)

        self.layout.addWidget(nav_container)

        # Subtle 1px horizontal separator line below tab bar
        sep = QLabel()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: rgba(255, 255, 255, 0.08);")
        self.layout.addWidget(sep)

        # =====================================================================
        # 4. TAB WIDGET (Lirik, Antrean, Cari, Settings)
        # =====================================================================
        self.tabs = QTabWidget()
        self.tabs.tabBar().setVisible(False)
        
        self.lyrics_tab = LyricsTab()
        self.queue_tab = QueueTab()
        self.search_tab = SearchTab()
        self.settings_tab = SettingsTab(current_client_id, current_client_secret)
        self.settings_tab.exit_requested.connect(self.exit_clicked.emit)

        self.tabs.addTab(self.lyrics_tab, "Lirik")
        self.tabs.addTab(self.queue_tab, "Antrean")
        self.tabs.addTab(self.search_tab, "Cari")
        self.tabs.addTab(self.settings_tab, "Personalisasi UI")

        self.layout.addWidget(self.tabs, 1)

        # Connect sub-tab updates
        self.queue_tab.queue_count_changed.connect(self._on_queue_count_changed)
        self.lyrics_tab.seek_time_requested.connect(self._on_lyric_seek)
        self.settings_tab.personalization_changed.connect(self._on_personalization_update)

        self.switch_tab(0)

    def switch_tab(self, index: int):
        self.tabs.setCurrentIndex(index)
        for i, btn in enumerate(self.nav_buttons):
            btn.set_active(i == index, self.accent_color)
        if index == 1 and hasattr(self, "queue_tab"):
            self.queue_tab.refresh_requested.emit()

    def _on_queue_count_changed(self, count: int):
        if hasattr(self, "queue_badge_lbl"):
            self.queue_badge_lbl.setText(str(count))

    def _on_lyric_seek(self, time_ms: int):
        duration_ms = self.waveform_scrubber.maximum()
        if duration_ms > 0:
            ratio = max(0.0, min(1.0, time_ms / float(duration_ms)))
            self.seek_clicked.emit(ratio)

    def _on_personalization_update(self, data: dict):
        if "scrubber_style" in data:
            self.waveform_scrubber.set_style_mode(data["scrubber_style"])
        if "opacity" in data:
            clear_pct = int(round((1.0 - data["opacity"]) * 100))
            self.btn_quick_glass.setText(f"● {clear_pct}% Clear")

    def _toggle_quick_glass(self):
        curr_op = self.settings_tab.glass_opacity
        if curr_op > 0.5:
            self.settings_tab.slider_clear.setValue(58)
            self.btn_quick_glass.setText("● 58% Clear")
        else:
            self.settings_tab.slider_clear.setValue(6)
            self.btn_quick_glass.setText("● 6% Clear")

    def set_accent_color(self, hex_color: str):
        self.accent_color = hex_color
        self.cover_widget.set_accent_color(hex_color)
        self.btn_play.set_accent_color(hex_color)
        self.btn_quick_glass.set_accent_color(hex_color)
        self.waveform_scrubber.set_accent_color(hex_color)
        self.lyrics_tab.set_accent_color(hex_color)
        self.search_tab.set_accent_color(hex_color)
        self.switch_tab(self.tabs.currentIndex())

    def apply_initial_config(self, config: dict):
        if hasattr(self, "settings_tab"):
            self.settings_tab.load_personalization_config(config)
        p_cfg = config.get("personalization", {})
        scrubber_style = p_cfg.get("scrubber_style", "waveform")
        self.waveform_scrubber.set_style_mode(scrubber_style)
        
        opacity = float(p_cfg.get("opacity", 0.94))
        clear_pct = int(round((1.0 - opacity) * 100))
        self.btn_quick_glass.setText(f"● {clear_pct}% Clear")
        
        accent_color = p_cfg.get("accent_color", "#34D399")
        self.set_accent_color(accent_color)

    def update_track(self, title: str, artist: str, cover_pixmap: QPixmap | None, is_playing: bool):
        self.title_lbl.setText(title if title else "-")
        self.artist_lbl.setText(artist if artist else "-")
        self.cover_widget.set_pixmap(cover_pixmap)
        self.btn_play.set_playing(is_playing)
        self.lyrics_tab.set_track_metadata(title, artist)

    def update_progress(self, curr_ms: int, total_ms: int, ratio: float):
        self.waveform_scrubber.setRange(0, total_ms if total_ms > 0 else 1000)
        self.waveform_scrubber.update_progress(curr_ms, total_ms, ratio)
