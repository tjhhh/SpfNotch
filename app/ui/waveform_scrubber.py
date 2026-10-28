from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PyQt6.QtCore import Qt, pyqtSignal, QRectF
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush

WAVEFORM_BARS = [
    28, 44, 62, 38, 75, 90, 54, 42, 68, 84, 95, 70, 48, 60, 82, 100, 88, 64, 52, 76,
    92, 67, 45, 58, 86, 94, 72, 50, 38, 66, 80, 91, 74, 56, 42, 68, 85, 60, 46, 32
]

class WaveformCanvas(QWidget):
    seek_requested = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(22)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.progress_ratio = 0.0
        self.accent_color = QColor("#34D399")
        self.inactive_color = QColor(255, 255, 255, 42)
        self.style_mode = "waveform"  # "waveform" or "laser-line"
        self._dragging = False

    def set_progress(self, ratio: float):
        clamped = max(0.0, min(1.0, ratio))
        if abs(clamped - self.progress_ratio) > 0.001:
            self.progress_ratio = clamped
            self.update()

    def set_accent_color(self, hex_color: str):
        self.accent_color = QColor(hex_color)
        self.update()

    def set_style_mode(self, mode: str):
        self.style_mode = mode
        self.update()

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            ratio = ev.position().x() / max(1, self.width())
            ratio = max(0.0, min(1.0, ratio))
            self.set_progress(ratio)
            self.seek_requested.emit(ratio)

    def mouseMoveEvent(self, ev):
        if self._dragging:
            ratio = ev.position().x() / max(1, self.width())
            ratio = max(0.0, min(1.0, ratio))
            self.set_progress(ratio)
            self.seek_requested.emit(ratio)

    def mouseReleaseEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self._dragging = False

    def paintEvent(self, ev):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        if self.style_mode == "laser-line":
            # Clean laser progress rail
            rail_h = 4.0
            y = (h - rail_h) / 2.0
            # Track
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(255, 255, 255, 30)))
            painter.drawRoundedRect(QRectF(0, y, w, rail_h), 2.0, 2.0)
            # Active fill
            active_w = w * self.progress_ratio
            if active_w > 0:
                painter.setBrush(QBrush(self.accent_color))
                painter.drawRoundedRect(QRectF(0, y, active_w, rail_h), 2.0, 2.0)
                # Handle dot
                dot_r = 5.0
                painter.setBrush(QBrush(QColor("#FFFFFF")))
                painter.drawEllipse(QRectF(active_w - dot_r, (h - (dot_r * 2)) / 2.0, dot_r * 2, dot_r * 2))
            painter.end()
            return

        # Waveform Capsule Bars mode (matching Figma v6)
        num_bars = len(WAVEFORM_BARS)
        gap = 3.0
        total_gaps = (num_bars - 1) * gap
        bar_w = max(2.5, (w - total_gaps) / num_bars)

        for i, height_pct in enumerate(WAVEFORM_BARS):
            bar_ratio = i / float(num_bars)
            is_passed = bar_ratio <= self.progress_ratio

            # Height calculation
            bar_h = max(4.0, (height_pct / 100.0) * h)
            x = i * (bar_w + gap)
            y = (h - bar_h) / 2.0

            if is_passed:
                # Active played bar
                color = self.accent_color
                # Slight glow on the playhead bar
                if abs(bar_ratio - self.progress_ratio) < (1.5 / num_bars):
                    color = QColor("#A7F3D0")  # brighter highlight
            else:
                color = self.inactive_color

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(color))
            painter.drawRoundedRect(QRectF(x, y, bar_w, bar_h), bar_w / 2.0, bar_w / 2.0)

        painter.end()


class WaveformScrubber(QWidget):
    """
    Combined Scrubber with Left Timestamp, Waveform Canvas, and Right Timestamp.
    Also provides ClickableSlider-like interface for 100% test compatibility.
    """
    seek_requested = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._max_val = 1000
        self._current_val = 0
        self._block_signals = False

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(8)

        self.time_curr_lbl = QLabel("0:00")
        self.time_curr_lbl.setStyleSheet("font-size: 11px; font-family: monospace; color: rgba(255, 255, 255, 0.65); min-width: 34px;")
        self.time_curr_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.layout.addWidget(self.time_curr_lbl)

        self.canvas = WaveformCanvas(self)
        self.canvas.seek_requested.connect(self._on_canvas_seek)
        self.layout.addWidget(self.canvas, 1)

        self.time_total_lbl = QLabel("0:00")
        self.time_total_lbl.setStyleSheet("font-size: 11px; font-family: monospace; color: rgba(255, 255, 255, 0.50); min-width: 34px;")
        self.time_total_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.layout.addWidget(self.time_total_lbl)

    def _on_canvas_seek(self, ratio: float):
        if not self._block_signals:
            self._current_val = int(ratio * self._max_val)
            self.seek_requested.emit(ratio)

    def set_accent_color(self, hex_color: str):
        self.canvas.set_accent_color(hex_color)

    def set_style_mode(self, mode: str):
        self.canvas.set_style_mode(mode)

    def update_progress(self, curr_ms: int, total_ms: int, ratio: float):
        self.canvas.set_progress(ratio)
        c_sec = max(0, int(curr_ms / 1000))
        t_sec = max(0, int(total_ms / 1000))
        self.time_curr_lbl.setText(f"{c_sec // 60}:{c_sec % 60:02d}")
        self.time_total_lbl.setText(f"{t_sec // 60}:{t_sec % 60:02d}")

    # Compatibility methods with ClickableSlider / QSlider
    def setValue(self, val: int):
        self._current_val = val
        ratio = val / max(1, self._max_val)
        self.canvas.set_progress(ratio)

    def value(self) -> int:
        return self._current_val

    def setRange(self, min_val: int, max_val: int):
        self._max_val = max(1, max_val)

    def maximum(self) -> int:
        return self._max_val

    def blockSignals(self, b: bool):
        self._block_signals = b
