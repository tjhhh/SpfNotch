from PyQt6.QtWidgets import QAbstractButton
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import QPainter, QPainterPath, QColor, QPen, QBrush, QRadialGradient

class MediaPlayButton(QAbstractButton):
    """
    Hardware-grade white squircle Play/Pause button with subtle accent glow
    matching Gambar 1, 2, 3.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(44, 44)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.is_playing = False
        self.accent_color = QColor("#34D399")
        self._hovered = False
        self._pressed = False

    def set_playing(self, playing: bool):
        if self.is_playing != playing:
            self.is_playing = playing
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

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self._pressed = True
            self.update()
        super().mousePressEvent(ev)

    def mouseReleaseEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self._pressed = False
            self.update()
        super().mouseReleaseEvent(ev)

    def paintEvent(self, ev):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 1. Soft outer ambient glow around the squircle
        glow = QRadialGradient(22.0, 22.0, 22.0)
        glow_c = QColor(self.accent_color)
        glow_c.setAlpha(95 if self._hovered else 65)
        glow.setColorAt(0.45, glow_c)
        glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(glow))
        painter.drawEllipse(QRectF(0, 0, 44, 44))

        # 2. Solid white squircle (rounded-2xl / 36x36 centered at 4,4)
        if self._pressed:
            bg_color = QColor("#E2E8F0")
        elif self._hovered:
            bg_color = QColor("#F8FAFC")
        else:
            bg_color = QColor("#FFFFFF")

        painter.setBrush(QBrush(bg_color))
        painter.drawRoundedRect(QRectF(4.0, 4.0, 36.0, 36.0), 13.0, 13.0)

        # 3. Dark icon inside
        fg_color = QColor("#090A0F")
        cx, cy = 22.0, 22.0

        if self.is_playing:
            bar_w = 3.2
            bar_h = 12.0
            gap = 3.8

            x1 = cx - gap / 2.0 - bar_w
            y1 = cy - bar_h / 2.0
            path_left = QPainterPath()
            path_left.addRoundedRect(x1, y1, bar_w, bar_h, 1.0, 1.0)
            painter.fillPath(path_left, fg_color)

            x2 = cx + gap / 2.0
            y2 = cy - bar_h / 2.0
            path_right = QPainterPath()
            path_right.addRoundedRect(x2, y2, bar_w, bar_h, 1.0, 1.0)
            painter.fillPath(path_right, fg_color)
        else:
            tri_cx = cx + 1.2
            tri_w = 10.5
            tri_h = 12.5

            path = QPainterPath()
            path.moveTo(tri_cx - tri_w / 2.0, cy - tri_h / 2.0)
            path.lineTo(tri_cx + tri_w / 2.0, cy)
            path.lineTo(tri_cx - tri_w / 2.0, cy + tri_h / 2.0)
            path.closeSubpath()
            painter.fillPath(path, fg_color)

        painter.end()


class MediaNavButton(QAbstractButton):
    def __init__(self, nav_type: str = "prev", parent=None):
        super().__init__(parent)
        self.nav_type = nav_type  # "prev" or "next"
        self.setFixedSize(28, 28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hovered = False
        self._pressed = False

    def enterEvent(self, ev):
        super().enterEvent(ev)
        self._hovered = True
        self.update()

    def leaveEvent(self, ev):
        super().leaveEvent(ev)
        self._hovered = False
        self.update()

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self._pressed = True
            self.update()
        super().mousePressEvent(ev)

    def mouseReleaseEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self._pressed = False
            self.update()
        super().mouseReleaseEvent(ev)

    def paintEvent(self, ev):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self._pressed:
            painter.setBrush(QBrush(QColor(255, 255, 255, 30)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(QRectF(1, 1, 26, 26), 8.0, 8.0)
        elif self._hovered:
            painter.setBrush(QBrush(QColor(255, 255, 255, 18)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(QRectF(1, 1, 26, 26), 8.0, 8.0)

        fg_color = QColor("#FFFFFF") if self._hovered else QColor(255, 255, 255, 195)
        painter.setBrush(QBrush(fg_color))
        painter.setPen(Qt.PenStyle.NoPen)

        cx, cy = 14.0, 14.0
        bar_w = 1.8
        bar_h = 9.5
        tri_w = 7.0
        tri_h = 9.5

        if self.nav_type == "prev":
            bar_x = cx - 4.8
            bar_y = cy - bar_h / 2.0
            path_bar = QPainterPath()
            path_bar.addRoundedRect(bar_x, bar_y, bar_w, bar_h, 0.8, 0.8)
            painter.fillPath(path_bar, fg_color)

            tri_left = bar_x + bar_w + 0.8
            path_tri = QPainterPath()
            path_tri.moveTo(tri_left, cy)
            path_tri.lineTo(tri_left + tri_w, cy - tri_h / 2.0)
            path_tri.lineTo(tri_left + tri_w, cy + tri_h / 2.0)
            path_tri.closeSubpath()
            painter.fillPath(path_tri, fg_color)
        else:
            tri_right = cx + 4.8 - bar_w - 0.8
            path_tri = QPainterPath()
            path_tri.moveTo(tri_right, cy)
            path_tri.lineTo(tri_right - tri_w, cy - tri_h / 2.0)
            path_tri.lineTo(tri_right - tri_w, cy + tri_h / 2.0)
            path_tri.closeSubpath()
            painter.fillPath(path_tri, fg_color)

            bar_x = tri_right + 0.8
            bar_y = cy - bar_h / 2.0
            path_bar = QPainterPath()
            path_bar.addRoundedRect(bar_x, bar_y, bar_w, bar_h, 0.8, 0.8)
            painter.fillPath(path_bar, fg_color)

        painter.end()


class CollapseChevronButton(QAbstractButton):
    """
    Rounded square glass button with clean upward chevron '^' matching Gambar 1-3.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(30, 30)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hovered = False
        self._pressed = False

    def enterEvent(self, ev):
        super().enterEvent(ev)
        self._hovered = True
        self.update()

    def leaveEvent(self, ev):
        super().leaveEvent(ev)
        self._hovered = False
        self.update()

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self._pressed = True
            self.update()
        super().mousePressEvent(ev)

    def mouseReleaseEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self._pressed = False
            self.update()
        super().mouseReleaseEvent(ev)

    def paintEvent(self, ev):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        bg_alpha = 38 if self._pressed else (28 if self._hovered else 14)
        border_alpha = 50 if self._hovered else 28

        painter.setBrush(QBrush(QColor(255, 255, 255, bg_alpha)))
        painter.setPen(QPen(QColor(255, 255, 255, border_alpha), 1.0))
        painter.drawRoundedRect(QRectF(0.5, 0.5, 29.0, 29.0), 9.5, 9.5)

        fg_color = QColor("#FFFFFF") if self._hovered else QColor(255, 255, 255, 185)
        pen = QPen(fg_color, 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        path = QPainterPath()
        path.moveTo(QPointF(11.0, 16.5))
        path.lineTo(QPointF(15.0, 12.5))
        path.lineTo(QPointF(19.0, 16.5))
        painter.drawPath(path)

        painter.end()
