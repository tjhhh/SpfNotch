from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPainter, QColor
import random

class EqualizerWidget(QWidget):
    """
    Micro-spectrum 5-bar equalizer matching Gambar 1 and Figma v6 design.
    Vibrant mint/cyan green bars with smooth live animation.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(22, 16)
        self.is_playing = False
        self.accent_color = QColor("#34D399")

        # Initial bar heights ratio (0.2 to 1.0)
        self.target_heights = [0.45, 0.9, 0.65, 1.0, 0.5]
        self.current_heights = [0.45, 0.9, 0.65, 1.0, 0.5]

        # Timer for animating bars
        self.timer = QTimer(self)
        self.timer.setInterval(110)
        self.timer.timeout.connect(self._animate_step)

    def set_playing(self, playing: bool):
        if self.is_playing != playing:
            self.is_playing = playing
            if playing:
                self.timer.start()
            else:
                self.timer.stop()
                self.current_heights = [0.2, 0.25, 0.2, 0.25, 0.2]
                self.update()

    def set_accent_color(self, color_hex: str):
        self.accent_color = QColor(color_hex)
        self.update()

    def _animate_step(self):
        if not self.is_playing:
            return
        # Smooth organic variation
        for i in range(5):
            self.current_heights[i] = random.uniform(0.25, 1.0)
        self.update()

    def paintEvent(self, ev):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        num_bars = 5
        bar_w = 2.4
        gap = (w - (num_bars * bar_w)) / (num_bars - 1)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self.accent_color)

        for i in range(num_bars):
            ratio = self.current_heights[i] if self.is_playing else 0.2
            bar_h = max(3.0, h * ratio)
            x = i * (bar_w + gap)
            y = h - bar_h
            painter.drawRoundedRect(int(x), int(y), int(bar_w), int(bar_h), 1.2, 1.2)

        painter.end()
