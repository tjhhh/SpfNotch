from PyQt6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem, 
    QLabel, QPushButton
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QRectF
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen, QPainterPath, QPixmap


class SpotifyCoverThumbnail(QWidget):
    """
    Renders real Spotify album art thumbnail when available.
    When no valid pixmap is available from Spotify, hides itself completely
    so no fake gradient/placeholder box is shown.
    """
    def __init__(self, size: int = 34, radius: float = 8.0, parent=None):
        super().__init__(parent)
        self.size = size
        self.radius = radius
        self.pixmap: QPixmap | None = None
        self.setFixedSize(size, size)
        self.setVisible(False)

    def set_pixmap(self, pix: QPixmap | None):
        if pix is not None and not pix.isNull():
            self.pixmap = pix
            self.setVisible(True)
            self.update()
        else:
            self.pixmap = None
            self.setVisible(False)

    def paintEvent(self, ev):
        if self.pixmap is None or self.pixmap.isNull():
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        s = float(self.size)
        r = float(self.radius)

        scaled = self.pixmap.scaled(
            self.size, self.size,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation
        )
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, s, s), r, r)
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, scaled)
        painter.setClipping(False)

        painter.setPen(QPen(QColor(255, 255, 255, 45), 1.0))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(QRectF(0.5, 0.5, s - 1.0, s - 1.0), r, r)
        painter.end()


class QueueItemCard(QFrame):
    """
    Sleek glass queue card matching Gambar 2.
    Uses real Spotify album cover when available, or hides the cover box if unavailable.
    """
    play_clicked = pyqtSignal()
    remove_clicked = pyqtSignal()

    def __init__(
        self,
        idx_str: str,
        title: str,
        artist: str,
        cover_url: str = "",
        cover_pixmap: QPixmap | None = None,
        parent=None
    ):
        super().__init__(parent)
        self.setObjectName("queueCard")
        self.cover_url = cover_url

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(14, 8, 12, 8)
        self.layout.setSpacing(12)

        # Index e.g. "01"
        self.idx_lbl = QLabel(idx_str, self)
        self.idx_lbl.setStyleSheet(
            "font-size: 11.5px; font-family: 'Courier New', monospace; font-weight: 600; "
            "color: rgba(255, 255, 255, 0.42); min-width: 20px; background: transparent; border: none;"
        )
        self.layout.addWidget(self.idx_lbl)

        # Real Spotify cover thumbnail (hidden automatically if no Spotify cover)
        self.cover = SpotifyCoverThumbnail(size=34, radius=8.5, parent=self)
        self.cover.set_pixmap(cover_pixmap)
        self.layout.addWidget(self.cover)

        # Title & Artist
        self.meta_col = QVBoxLayout()
        self.meta_col.setContentsMargins(0, 0, 0, 0)
        self.meta_col.setSpacing(2)

        self.title_lbl = QLabel(title, self)
        self.title_lbl.setStyleSheet(
            "font-size: 13px; font-weight: 700; color: #FFFFFF; background: transparent; border: none;"
        )
        self.artist_lbl = QLabel(artist, self)
        self.artist_lbl.setStyleSheet(
            "font-size: 11.5px; color: rgba(255, 255, 255, 0.55); background: transparent; border: none;"
        )

        self.meta_col.addWidget(self.title_lbl)
        self.meta_col.addWidget(self.artist_lbl)
        self.layout.addLayout(self.meta_col, 1)

        # "Putar" pill button matching Gambar 2
        self.btn_play = QPushButton("Putar", self)
        self.btn_play.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_play.setStyleSheet(
            "QPushButton { "
            "background: rgba(255, 255, 255, 0.10); "
            "border: 1px solid rgba(255, 255, 255, 0.14); "
            "color: #FFFFFF; font-size: 11px; font-weight: 600; "
            "padding: 5px 14px; border-radius: 9px; "
            "} "
            "QPushButton:hover { "
            "background: rgba(255, 255, 255, 0.20); "
            "border: 1px solid rgba(255, 255, 255, 0.28); "
            "}"
        )
        self.btn_play.clicked.connect(self.play_clicked.emit)
        self.layout.addWidget(self.btn_play)

        # "✕" remove button
        self.btn_remove = QPushButton("✕", self)
        self.btn_remove.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_remove.setFixedSize(26, 26)
        self.btn_remove.setStyleSheet(
            "QPushButton { "
            "background: transparent; color: rgba(255, 255, 255, 0.45); "
            "font-size: 11.5px; border: none; border-radius: 7px; "
            "} "
            "QPushButton:hover { "
            "background: rgba(244, 63, 94, 0.18); color: #FDA4AF; "
            "}"
        )
        self.btn_remove.clicked.connect(self.remove_clicked.emit)
        self.layout.addWidget(self.btn_remove)

        self.setStyleSheet(
            "#queueCard { "
            "background: rgba(255, 255, 255, 0.04); "
            "border: 1px solid rgba(255, 255, 255, 0.08); "
            "border-radius: 14px; "
            "} "
            "#queueCard:hover { "
            "background: rgba(255, 255, 255, 0.08); "
            "border: 1px solid rgba(255, 255, 255, 0.15); "
            "}"
        )

    def set_cover_pixmap(self, pix: QPixmap | None):
        self.cover.set_pixmap(pix)


class QueueTab(QWidget):
    """
    Redesigned Queue Tab matching Gambar 2.
    - Glass cards with 01, 02, 03 index, real Spotify cover (or hidden if unavailable),
      Putar pill button, and ✕ button.
    """
    refresh_requested = pyqtSignal()
    play_track_requested = pyqtSignal(str)   # track uri
    queue_count_changed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.queue_items_data = []
        self.image_cache = None

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(2, 4, 2, 4)
        self.layout.setSpacing(6)

        # Invisible refresh trigger button for compatibility
        self.btn_refresh = QPushButton(self)
        self.btn_refresh.setVisible(False)
        self.btn_refresh.clicked.connect(self.refresh_requested.emit)

        # List Widget
        self.list_widget = QListWidget()
        self.list_widget.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.list_widget.setSpacing(4)
        self.layout.addWidget(self.list_widget)

        # Empty state
        self.empty_label = QLabel("Tidak ada lagu di antrean.")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setStyleSheet("color: rgba(255, 255, 255, 0.45); font-size: 12px; font-style: italic;")
        self.layout.addWidget(self.empty_label)

    def set_image_cache(self, image_cache):
        self.image_cache = image_cache

    def set_queue(self, queue_items: list[dict]):
        self.list_widget.clear()
        self.queue_items_data = queue_items or []
        self.queue_count_changed.emit(len(self.queue_items_data))

        if not self.queue_items_data:
            self.empty_label.setVisible(True)
            self.list_widget.setVisible(False)
            return

        self.empty_label.setVisible(False)
        self.list_widget.setVisible(True)

        for i, item in enumerate(self.queue_items_data):
            title = item.get("title", "Unknown")
            artist = item.get("artist", "Unknown")
            uri = item.get("uri", "")
            cover_url = item.get("cover_url", "")

            pix = None
            if cover_url and self.image_cache is not None:
                pix = self.image_cache.get_pixmap(cover_url, rounded_radius=8, size=36)

            idx_str = f"{i + 1:02d}"
            card = QueueItemCard(
                idx_str=idx_str,
                title=title,
                artist=artist,
                cover_url=cover_url,
                cover_pixmap=pix,
                parent=self
            )
            card.play_clicked.connect(lambda u=uri: self.play_track_requested.emit(u))
            card.remove_clicked.connect(lambda idx=i: self._remove_item_at(idx))

            list_item = QListWidgetItem()
            list_item.setSizeHint(QSize(0, 56))
            self.list_widget.addItem(list_item)
            self.list_widget.setItemWidget(list_item, card)

    def update_cover(self, url: str, raw_pixmap: QPixmap):
        if not url or raw_pixmap is None or raw_pixmap.isNull():
            return
        pix = raw_pixmap
        if self.image_cache is not None:
            pix = self.image_cache.process_and_cache(url, raw_pixmap, rounded_radius=8, size=36)

        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            card = self.list_widget.itemWidget(item)
            if isinstance(card, QueueItemCard) and card.cover_url == url:
                card.set_cover_pixmap(pix)

    def _remove_item_at(self, idx: int):
        if 0 <= idx < len(self.queue_items_data):
            self.queue_items_data.pop(idx)
            self.set_queue(self.queue_items_data)
