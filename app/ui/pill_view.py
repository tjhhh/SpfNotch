from PyQt6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt, pyqtSignal, QRectF
from PyQt6.QtGui import QPixmap, QPainter, QColor, QBrush, QPen

from app.ui.equalizer_widget import EqualizerWidget

class PillAlbumArt(QWidget):
    """Album art with bottom-right status indicator dot matching Gambar 1"""
    def __init__(self, size=30, parent=None):
        super().__init__(parent)
        self.size = size
        self.setFixedSize(size, size)
        self.pixmap: QPixmap | None = None
        self.is_playing = False
        self.accent_color = QColor("#34D399")

    def set_pixmap(self, pix: QPixmap | None):
        self.pixmap = pix
        self.update()

    def set_playing(self, playing: bool):
        self.is_playing = playing
        self.update()

    def set_accent_color(self, hex_color: str):
        self.accent_color = QColor(hex_color)
        self.update()

    def paintEvent(self, ev):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        s = float(self.size)
        r = 8.0

        if self.pixmap and not self.pixmap.isNull():
            scaled = self.pixmap.scaled(int(s), int(s), Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            from PyQt6.QtGui import QPainterPath
            path = QPainterPath()
            path.addRoundedRect(QRectF(0, 0, s, s), r, r)
            painter.setClipPath(path)
            painter.drawPixmap(0, 0, scaled)
            painter.setClipping(False)
        else:
            painter.setPen(QPen(QColor(255, 255, 255, 45), 1.0))
            painter.setBrush(QBrush(QColor("#181B24")))
            painter.drawRoundedRect(QRectF(0.5, 0.5, s - 1, s - 1), r, r)
            painter.setPen(self.accent_color)
            painter.drawText(QRectF(0, 0, s, s), Qt.AlignmentFlag.AlignCenter, "♫")

        # Subtle specular outer border
        painter.setPen(QPen(QColor(255, 255, 255, 35), 1.0))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(QRectF(0.5, 0.5, s - 1, s - 1), r, r)

        # Status indicator dot
        dot_d = 7.0
        dot_x = s - dot_d
        dot_y = s - dot_d

        painter.setPen(QPen(QColor("#000000"), 1.2))
        dot_color = self.accent_color if self.is_playing else QColor("#6B7280")
        painter.setBrush(QBrush(dot_color))
        painter.drawEllipse(QRectF(dot_x, dot_y, dot_d, dot_d))

        painter.end()


class PillView(QWidget):
    """
    Redesigned Pill Notch (saat tidak di-hover) matching Gambar 1.
    - Album art with status indicator dot
    - LIVE pill badge
    - Dual-line text (Title/Current lyric and Upcoming lyric with ↳)
    - Animated 5-bar micro-spectrum equalizer on right + chevron
    - Ultra-thin laser playback progress line along the bottom edge
    """
    mode_toggled = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(46)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self.idle_mode = "lyrics"
        self.current_title = "-"
        self.current_artist = "-"
        self.current_cover = None
        self.is_playing = False
        self.current_lyric = ""
        self.upcoming_lyric = ""
        self.progress_ratio = 0.0
        self.accent_color = "#34D399"

        # Main horizontal layout
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(10, 3, 10, 3)
        self.main_layout.setSpacing(9)

        # 1. Left: Album Art with Status Dot
        self.art_widget = PillAlbumArt(size=30, parent=self)
        self.main_layout.addWidget(self.art_widget)

        # Alias for backward compatibility with existing tests
        self.icon_label = QLabel(self)
        self.icon_label.setVisible(False)

        # 2. Center: Dual-line text column
        self.text_col = QVBoxLayout()
        self.text_col.setContentsMargins(0, 0, 0, 0)
        self.text_col.setSpacing(1)

        # Line 1 Row: LIVE Badge + Title / Lyric
        self.line1_row = QHBoxLayout()
        self.line1_row.setContentsMargins(0, 0, 0, 0)
        self.line1_row.setSpacing(5)

        self.live_badge = QLabel("LIVE")
        self.live_badge.setStyleSheet(
            "background-color: rgba(52, 211, 153, 0.18); "
            "color: #34D399; font-size: 8.5px; font-weight: 800; "
            "padding: 1px 4px; border-radius: 4px; font-family: monospace;"
        )
        self.line1_row.addWidget(self.live_badge)

        self.line1_label = QLabel("-")
        self.line1_label.setStyleSheet("color: #FFFFFF; font-size: 11.5px; font-weight: 700;")
        self.line1_row.addWidget(self.line1_label, 1)

        self.text_col.addLayout(self.line1_row)

        # Line 2: Upcoming lyric or artist
        self.line2_label = QLabel("")
        self.line2_label.setStyleSheet("color: rgba(255, 255, 255, 0.65); font-size: 10px; font-style: italic;")
        self.text_col.addWidget(self.line2_label)

        self.main_layout.addLayout(self.text_col, 1)

        # Alias for backward compatibility with existing tests
        self.text_label = self.line1_label

        # 3. Right: Animated Equalizer + Expand Chevron
        self.right_col = QHBoxLayout()
        self.right_col.setContentsMargins(0, 0, 0, 0)
        self.right_col.setSpacing(5)

        self.equalizer = EqualizerWidget(self)
        self.right_col.addWidget(self.equalizer)

        self.dropdown_icon = QLabel("▼")
        self.dropdown_icon.setStyleSheet("color: rgba(255, 255, 255, 0.45); font-size: 8.5px;")
        self.right_col.addWidget(self.dropdown_icon)

        self.main_layout.addLayout(self.right_col)

        # Status icon alias for compatibility
        self.status_icon = QLabel("♪", self)
        self.status_icon.setVisible(False)

        self._refresh_display()

    def set_idle_mode(self, mode: str):
        self.idle_mode = mode
        self._refresh_display()

    def update_track(self, title: str, artist: str, cover_pixmap: QPixmap | None, is_playing: bool):
        if title != self.current_title:
            self.current_lyric = ""
            self.upcoming_lyric = ""

        self.current_title = title if title else "-"
        self.current_artist = artist if artist else "-"
        self.current_cover = cover_pixmap
        self.is_playing = is_playing

        self.art_widget.set_pixmap(cover_pixmap)
        self.art_widget.set_playing(is_playing)
        self.equalizer.set_playing(is_playing)

        if is_playing:
            self.status_icon.setText("▶")
        else:
            self.status_icon.setText("⏸")

        self._refresh_display()

    def update_lyric(self, current_lyric: str, upcoming_lyric: str = ""):
        cleaned_curr = current_lyric.strip() if current_lyric else ""
        cleaned_next = upcoming_lyric.strip() if upcoming_lyric else ""

        self.current_lyric = cleaned_curr
        self.upcoming_lyric = cleaned_next if cleaned_curr else ""
        self._refresh_display()

    def update_progress(self, ratio: float):
        self.progress_ratio = max(0.0, min(1.0, ratio))
        self.update()

    def set_accent_color(self, hex_color: str):
        self.accent_color = hex_color
        self.art_widget.set_accent_color(hex_color)
        self.equalizer.set_accent_color(hex_color)
        self.live_badge.setStyleSheet(
            f"background-color: {hex_color}25; "
            f"color: {hex_color}; font-size: 8.5px; font-weight: 800; "
            "padding: 1px 4px; border-radius: 4px; font-family: monospace;"
        )
        self.update()

    def _truncate(self, text: str, max_len: int) -> str:
        if len(text) > max_len:
            return text[:max_len - 3] + "..."
        return text

    def _refresh_display(self):
        if self.idle_mode == "lyrics" and self.is_playing and self.current_lyric:
            self.live_badge.setVisible(True)
            curr_text = f"♪ {self.current_lyric}"
            self.line1_label.setText(self._truncate(curr_text, 54))
            self.line2_label.setStyleSheet("color: rgba(255, 255, 255, 0.65); font-size: 10px; font-style: italic;")

            if self.upcoming_lyric:
                next_text = f"↳ {self.upcoming_lyric}"
                self.line2_label.setText(self._truncate(next_text, 58))
                self.line2_label.setVisible(True)
            elif self.current_artist:
                self.line2_label.setText(self._truncate(f"{self.current_title} • {self.current_artist}", 58))
                self.line2_label.setVisible(True)
            else:
                self.line2_label.setVisible(False)
        else:
            self.live_badge.setVisible(False)
            if self.current_title == "-" or not self.current_title:
                self.line1_label.setText("-")
            else:
                prefix = "♪ " if self.is_playing else "⏸ "
                self.line1_label.setText(self._truncate(f"{prefix}{self.current_title}", 52))

            if self.current_artist and self.current_artist != "-":
                self.line2_label.setStyleSheet("color: rgba(255, 255, 255, 0.65); font-size: 10.5px; font-style: normal;")
                self.line2_label.setText(self._truncate(self.current_artist, 56))
                self.line2_label.setVisible(True)
            elif self.current_artist == "-":
                self.line2_label.setStyleSheet("color: rgba(255, 255, 255, 0.65); font-size: 10.5px; font-style: normal;")
                self.line2_label.setText("-")
                self.line2_label.setVisible(True)
            else:
                self.line2_label.setVisible(False)

    def paintEvent(self, ev):
        super().paintEvent(ev)
        # Laser playback progress line at the bottom
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = float(self.width())
        h = float(self.height())
        bar_h = 2.0
        margin_x = 12.0
        avail_w = w - (margin_x * 2)
        y = h - bar_h

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(255, 255, 255, 22)))
        painter.drawRoundedRect(QRectF(margin_x, y, avail_w, bar_h), 1.0, 1.0)

        fill_w = avail_w * self.progress_ratio
        if fill_w > 0:
            painter.setBrush(QBrush(QColor(self.accent_color)))
            painter.drawRoundedRect(QRectF(margin_x, y, fill_w, bar_h), 1.0, 1.0)

        painter.end()
