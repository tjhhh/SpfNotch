from PyQt6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLineEdit, QListWidget, 
    QListWidgetItem, QLabel, QPushButton, QApplication
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize, QRectF, QPointF
from PyQt6.QtGui import QPixmap, QPainter, QPen, QColor

from app.ui.queue_tab import SpotifyCoverThumbnail


class SearchIconWidget(QWidget):
    """Clean vector magnifying glass icon"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(16, 16)

    def paintEvent(self, ev):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(255, 255, 255, 115), 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QRectF(2.0, 2.0, 9.5, 9.5))
        painter.drawLine(QPointF(10.2, 10.2), QPointF(14.0, 14.0))
        painter.end()


class SearchLineEdit(QLineEdit):
    focus_activated = pyqtSignal()

    def mousePressEvent(self, ev):
        self.focus_activated.emit()
        super().mousePressEvent(ev)

    def focusInEvent(self, ev):
        self.focus_activated.emit()
        super().focusInEvent(ev)

    def keyPressEvent(self, ev):
        if ev.modifiers() == Qt.KeyboardModifier.ControlModifier and ev.key() == Qt.Key.Key_V:
            clip_text = QApplication.clipboard().text().strip()
            if clip_text:
                self.insert(clip_text)
                return
        super().keyPressEvent(ev)


class SearchItemCard(QFrame):
    """
    Sleek glass search result card.
    Uses real Spotify album cover when available, or hides the cover box if unavailable.
    """
    play_clicked = pyqtSignal()
    queue_clicked = pyqtSignal()

    def __init__(
        self,
        title: str,
        artist: str,
        duration_str: str,
        cover_url: str = "",
        cover_pixmap: QPixmap | None = None,
        accent_color: str = "#34D399",
        parent=None
    ):
        super().__init__(parent)
        self.setObjectName("searchCard")
        self.cover_url = cover_url

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(12, 7, 12, 7)
        self.layout.setSpacing(11)

        # Real Spotify cover thumbnail (hidden automatically if no Spotify cover)
        self.cover = SpotifyCoverThumbnail(size=36, radius=8.5, parent=self)
        self.cover.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.cover.set_pixmap(cover_pixmap)
        self.layout.addWidget(self.cover)

        # Title & Artist + Duration
        self.meta_col = QVBoxLayout()
        self.meta_col.setContentsMargins(0, 0, 0, 0)
        self.meta_col.setSpacing(2)

        self.title_lbl = QLabel(title, self)
        self.title_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.title_lbl.setStyleSheet(
            "font-size: 13px; font-weight: 700; color: #FFFFFF; background: transparent; border: none;"
        )

        detail_text = f"{artist} • {duration_str}" if duration_str else artist
        self.detail_lbl = QLabel(detail_text, self)
        self.detail_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.detail_lbl.setStyleSheet(
            "font-size: 11px; color: rgba(255, 255, 255, 0.55); background: transparent; border: none;"
        )

        self.meta_col.addWidget(self.title_lbl)
        self.meta_col.addWidget(self.detail_lbl)
        self.layout.addLayout(self.meta_col, 1)

        # "▶" Play Button
        self.btn_play = QPushButton("▶", self)
        self.btn_play.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_play.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_play.setFixedSize(30, 30)
        self.btn_play.setStyleSheet(
            "QPushButton { "
            "background: rgba(255, 255, 255, 0.10); "
            "border: 1px solid rgba(255, 255, 255, 0.16); "
            "border-radius: 8px; color: #FFFFFF; font-size: 11px; "
            "} "
            "QPushButton:hover { "
            "background: #FFFFFF; color: #090A0F; "
            "}"
        )
        self.btn_play.clicked.connect(lambda *_: self.play_clicked.emit())
        self.layout.addWidget(self.btn_play)

        # "+ Antrean" Button
        self.btn_queue = QPushButton("+ Antrean", self)
        self.btn_queue.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_queue.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_queue.setStyleSheet(
            "QPushButton { "
            f"background: {accent_color}1C; "
            f"border: 1px solid {accent_color}55; "
            "color: #FFFFFF; font-size: 11px; font-weight: 600; "
            "padding: 5px 11px; border-radius: 8px; "
            "} "
            "QPushButton:hover { "
            f"background: {accent_color}38; "
            f"border: 1px solid {accent_color}; "
            "}"
        )
        self.btn_queue.clicked.connect(lambda *_: self.queue_clicked.emit())
        self.layout.addWidget(self.btn_queue)

        self.setStyleSheet(
            "#searchCard { "
            "background: rgba(255, 255, 255, 0.04); "
            "border: 1px solid rgba(255, 255, 255, 0.08); "
            "border-radius: 13px; "
            "} "
            "#searchCard:hover { "
            "background: rgba(255, 255, 255, 0.09); "
            "border: 1px solid rgba(255, 255, 255, 0.18); "
            "}"
        )
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            pos = ev.pos()
            if not self.btn_queue.geometry().contains(pos) and not self.btn_play.geometry().contains(pos):
                self.play_clicked.emit()
                ev.accept()
                return
        super().mousePressEvent(ev)

    def set_accent_color(self, accent_color: str):
        self.accent_color = accent_color
        self.btn_queue.setStyleSheet(
            "QPushButton { "
            f"background: {accent_color}1C; "
            f"border: 1px solid {accent_color}55; "
            "color: #FFFFFF; font-size: 11px; font-weight: 600; "
            "padding: 5px 11px; border-radius: 8px; "
            "} "
            "QPushButton:hover { "
            f"background: {accent_color}38; "
            f"border: 1px solid {accent_color}; "
            "}"
        )

    def set_cover_pixmap(self, pix: QPixmap | None):
        self.cover.set_pixmap(pix)


class SearchTab(QWidget):
    """
    Redesigned Search Tab.
    - Glass search bar with magnifying glass icon and HASIL count pill
    - Sleek card rows with real Spotify cover art (or hidden if unavailable), play, and + Antrean buttons
    """
    search_requested = pyqtSignal(str)
    add_queue_requested = pyqtSignal(str, object)   # track uri, track dict
    play_track_requested = pyqtSignal(str, object)  # track uri, track dict
    input_focused = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.accent_color = "#34D399"
        self.image_cache = None
        self.debounce_timer = QTimer(self)
        self.debounce_timer.setSingleShot(True)
        self.debounce_timer.timeout.connect(self._trigger_search)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(4, 6, 4, 4)
        self.layout.setSpacing(6)

        # Unified Glass Search Box
        self.search_box = QFrame()
        self.search_box.setObjectName("searchBoxFrame")
        self.search_box.setStyleSheet(
            "#searchBoxFrame { "
            "background: rgba(0, 0, 0, 0.35); "
            "border: 1px solid rgba(255, 255, 255, 0.14); "
            "border-radius: 12px; "
            "}"
        )
        box_layout = QHBoxLayout(self.search_box)
        box_layout.setContentsMargins(12, 2, 10, 2)
        box_layout.setSpacing(8)

        self.search_icon = SearchIconWidget(self.search_box)
        box_layout.addWidget(self.search_icon)

        self.search_input = SearchLineEdit(self.search_box)
        self.search_input.setPlaceholderText("Ketik judul lagu, lirik, atau artis...")
        self.search_input.setStyleSheet("background: transparent; border: none; font-size: 12.5px; color: #FFFFFF; padding: 6px 0px;")
        self.search_input.textChanged.connect(self._on_text_changed)
        self.search_input.returnPressed.connect(self._on_enter_pressed)
        self.search_input.focus_activated.connect(self.input_focused.emit)
        box_layout.addWidget(self.search_input, 1)

        self.count_badge = QLabel("0 HASIL", self.search_box)
        self.count_badge.setStyleSheet(
            "background: rgba(255, 255, 255, 0.10); "
            "color: rgba(255, 255, 255, 0.65); "
            "font-size: 10px; font-family: 'Courier New', monospace; font-weight: 700; "
            "padding: 3px 8px; border-radius: 6px; border: none;"
        )
        self.count_badge.setVisible(False)
        box_layout.addWidget(self.count_badge)

        self.layout.addWidget(self.search_box)

        # Invisible btn_search for backwards compatibility
        self.btn_search = QPushButton(self)
        self.btn_search.setVisible(False)
        self.btn_search.clicked.connect(self._trigger_search)

        # Toast / Status
        self.status_lbl = QLabel("")
        self.status_lbl.setWordWrap(True)
        self.status_lbl.setStyleSheet(f"color: {self.accent_color}; font-size: 10.5px; font-weight: bold;")
        self.status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_lbl.setVisible(False)
        self.layout.addWidget(self.status_lbl)

        # Results List
        self._last_play_click_ts = 0.0
        self.results_list = QListWidget()
        self.results_list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.results_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.results_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.results_list.setSpacing(4)
        self.results_list.itemClicked.connect(self._on_list_item_clicked)
        self.layout.addWidget(self.results_list)

        # Hint
        self.hint_label = QLabel("Ketik judul lagu untuk mulai mencari")
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint_label.setStyleSheet("color: rgba(255, 255, 255, 0.45); font-size: 12px; font-style: italic;")
        self.layout.addWidget(self.hint_label)

    def set_image_cache(self, image_cache):
        self.image_cache = image_cache

    def set_accent_color(self, hex_color: str):
        self.accent_color = hex_color
        self.status_lbl.setStyleSheet(f"color: {hex_color}; font-size: 10.5px; font-weight: bold;")
        self.count_badge.setStyleSheet(
            f"font-size: 9.5px; font-family: 'Courier New', monospace; font-weight: 700; "
            f"color: {hex_color}; background: {hex_color}22; "
            "padding: 2px 7px; border-radius: 6px; border: none;"
        )
        for i in range(self.results_list.count()):
            item = self.results_list.item(i)
            widget = self.results_list.itemWidget(item)
            if hasattr(widget, "set_accent_color"):
                widget.set_accent_color(hex_color)

    def _on_enter_pressed(self):
        self.debounce_timer.stop()
        self._trigger_search()

    def _on_text_changed(self, text: str):
        self.debounce_timer.stop()
        if text.strip():
            self.debounce_timer.start(350)
        else:
            self.results_list.clear()
            self.count_badge.setVisible(False)
            self.hint_label.setText("Ketik judul lagu untuk mulai mencari")
            self.hint_label.setVisible(True)
            self.results_list.setVisible(False)

    def _trigger_search(self):
        query = self.search_input.text().strip()
        if query:
            self.hint_label.setText("Sedang mencari di Spotify...")
            self.hint_label.setVisible(True)
            self.search_requested.emit(query)

    def set_results(self, tracks: list[dict]):
        self.results_list.clear()
        if not tracks:
            self.count_badge.setText("0 HASIL")
            self.count_badge.setVisible(True)
            self.hint_label.setText("Lagu tidak ditemukan")
            self.hint_label.setVisible(True)
            self.results_list.setVisible(False)
            return

        self.count_badge.setText(f"{len(tracks)} HASIL")
        self.count_badge.setVisible(True)
        self.hint_label.setVisible(False)
        self.results_list.setVisible(True)

        for track in tracks:
            uri = track.get("uri", "")
            title = track.get("title", "Unknown")
            artist = track.get("artist", "Unknown")
            cover_url = track.get("cover_url", "")
            dur_ms = track.get("duration_ms", 0)
            mins = int((dur_ms / 1000) // 60)
            secs = int((dur_ms / 1000) % 60)
            dur_str = f"{mins}:{secs:02d}" if dur_ms > 0 else ""

            pix = None
            if cover_url and self.image_cache is not None:
                pix = self.image_cache.get_pixmap(cover_url, rounded_radius=8, size=36)

            card = SearchItemCard(
                title=title,
                artist=artist,
                duration_str=dur_str,
                cover_url=cover_url,
                cover_pixmap=pix,
                accent_color=self.accent_color,
                parent=self
            )
            card.play_clicked.connect(lambda *_, t=track: self._on_play_clicked(t))
            card.queue_clicked.connect(lambda *_, t=track: self._on_queue_clicked(t))

            list_item = QListWidgetItem()
            list_item.setData(Qt.ItemDataRole.UserRole, track)
            list_item.setSizeHint(QSize(0, 54))
            self.results_list.addItem(list_item)
            self.results_list.setItemWidget(list_item, card)

    def _on_list_item_clicked(self, item: QListWidgetItem):
        track = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(track, dict):
            self._on_play_clicked(track)

    def update_cover(self, url: str, raw_pixmap: QPixmap):
        if not url or raw_pixmap is None or raw_pixmap.isNull():
            return
        pix = raw_pixmap
        if self.image_cache is not None:
            pix = self.image_cache.process_and_cache(url, raw_pixmap, rounded_radius=8, size=36)

        for i in range(self.results_list.count()):
            item = self.results_list.item(i)
            card = self.results_list.itemWidget(item)
            if isinstance(card, SearchItemCard) and card.cover_url == url:
                card.set_cover_pixmap(pix)

    def _on_play_clicked(self, track: dict):
        import time
        now = time.time()
        if now - self._last_play_click_ts < 0.25:
            return
        self._last_play_click_ts = now
        uri = track.get("uri", "")
        title = track.get("title", "Lagu")
        self.play_track_requested.emit(uri, track)
        self.show_feedback(True, f"Memuat: {title[:20]}...", is_loading=True)

    def _on_queue_clicked(self, track: dict):
        uri = track.get("uri", "")
        title = track.get("title", "Lagu")
        self.add_queue_requested.emit(uri, track)
        self.show_feedback(True, f"Menambahkan ke antrean: {title[:16]}...", is_loading=True)

    def show_feedback(self, success: bool, message: str, is_loading: bool = False):
        if is_loading:
            color = self.accent_color
            prefix = "⏳ "
        elif success:
            color = "#1DB954"
            prefix = "▶ "
        else:
            color = "#F87171"
            prefix = "⚠ "

        self.status_lbl.setText(f"{prefix}{message}")
        self.status_lbl.setStyleSheet(f"color: {color}; font-size: 11px; font-weight: 600; padding: 2px 4px;")
        self.status_lbl.setVisible(True)

        if hasattr(self, "_feedback_timer") and self._feedback_timer.isActive():
            self._feedback_timer.stop()

        self._feedback_timer = QTimer(self)
        self._feedback_timer.setSingleShot(True)
        self._feedback_timer.timeout.connect(lambda: self.status_lbl.setVisible(False))
        self._feedback_timer.start(3500 if not is_loading else 6000)

    def _show_toast(self, msg: str):
        self.show_feedback(True, msg)
