from PyQt6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem, 
    QLabel, QPushButton, QGraphicsBlurEffect
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize, QPropertyAnimation, QEasingCurve

class LyricItemWidget(QFrame):
    """
    Single lyric row with real optical depth-of-field blur (QGraphicsBlurEffect)
    matching Gambar 1.
    """
    def __init__(self, text: str, subtext: str = "", time_str: str = "", style_mode: str = "editorial-left", parent=None):
        super().__init__(parent)
        self.setObjectName("lyricItemCard")
        self.style_mode = style_mode

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 6, 10, 6)
        self.layout.setSpacing(2)

        self.top_row = QHBoxLayout()
        self.top_row.setContentsMargins(0, 0, 0, 0)
        self.top_row.setSpacing(8)

        self.text_label = QLabel(text, self)
        self.text_label.setWordWrap(True)
        self.top_row.addWidget(self.text_label, 1)

        self.time_label = QLabel(time_str, self)
        self.time_label.setStyleSheet(
            "font-size: 10.5px; font-family: 'Courier New', monospace; "
            "color: rgba(255, 255, 255, 0.35); background: transparent; border: none;"
        )
        self.top_row.addWidget(self.time_label)

        self.layout.addLayout(self.top_row)

        self.sub_label = QLabel(subtext, self)
        self.sub_label.setStyleSheet(
            "font-size: 10.5px; font-family: 'Courier New', monospace; "
            "color: rgba(255, 255, 255, 0.45); background: transparent; border: none;"
        )
        if not subtext:
            self.sub_label.setVisible(False)
        self.layout.addWidget(self.sub_label)

        # Real optical camera blur effect for non-active lines when Depth Blur is ON
        self.blur_effect = QGraphicsBlurEffect(self)
        self.blur_effect.setBlurHints(QGraphicsBlurEffect.BlurHint.PerformanceHint)
        self.blur_effect.setBlurRadius(0.0)
        self.blur_effect.setEnabled(False)
        self.setGraphicsEffect(self.blur_effect)

    def set_active(self, is_active: bool, distance: int, depth_blur: bool, style_mode: str, accent_color: str = "#34D399"):
        self.style_mode = style_mode
        align = Qt.AlignmentFlag.AlignCenter if style_mode == "cinema-center" else Qt.AlignmentFlag.AlignLeft
        self.text_label.setAlignment(align)
        self.sub_label.setAlignment(align)
        self.time_label.setVisible(style_mode != "cinema-center")

        font_family = "'Courier New', monospace" if style_mode == "karaoke-mono" else "'Montserrat', 'Segoe UI', sans-serif"

        if is_active:
            # Active line is razor-sharp with no heavy gray border box matching Gambar 1
            self.blur_effect.setBlurRadius(0.0)
            self.blur_effect.setEnabled(False)
            self.setStyleSheet(
                "#lyricItemCard { "
                "background: transparent; "
                "border: 1px solid transparent; "
                "border-radius: 10px; "
                "}"
            )
            self.text_label.setStyleSheet(
                f"color: #FFFFFF; font-size: 15px; font-weight: 800; "
                f"font-family: {font_family}; background: transparent; border: none;"
            )
            self.sub_label.setStyleSheet(
                "font-size: 11px; font-family: 'Courier New', monospace; font-weight: 600; "
                "color: rgba(255, 255, 255, 0.58); background: transparent; border: none;"
            )
            self.time_label.setStyleSheet(
                f"font-size: 10.5px; font-family: 'Courier New', monospace; "
                f"color: {accent_color}; font-weight: bold; background: transparent; border: none;"
            )
        else:
            self.setStyleSheet(
                "#lyricItemCard { "
                "background: transparent; "
                "border: 1px solid transparent; "
                "border-radius: 10px; "
                "} "
                "#lyricItemCard:hover { "
                "background: rgba(255, 255, 255, 0.04); "
                "}"
            )
            if depth_blur:
                alpha = max(0.28, 0.78 - (distance * 0.16))
                blur_r = min(5.2, max(1.8, distance * 1.9))
                self.blur_effect.setBlurRadius(blur_r)
                self.blur_effect.setEnabled(True)
            else:
                alpha = 0.58
                self.blur_effect.setBlurRadius(0.0)
                self.blur_effect.setEnabled(False)

            color_str = f"rgba(255, 255, 255, {alpha:.2f})"
            self.text_label.setStyleSheet(
                f"color: {color_str}; font-size: 14px; font-weight: 600; "
                f"font-family: {font_family}; background: transparent; border: none;"
            )
            self.sub_label.setStyleSheet(
                f"font-size: 10.5px; font-family: 'Courier New', monospace; "
                f"color: rgba(255, 255, 255, {alpha * 0.65:.2f}); background: transparent; border: none;"
            )
            self.time_label.setStyleSheet(
                f"font-size: 10px; font-family: 'Courier New', monospace; "
                f"color: rgba(255, 255, 255, {alpha * 0.45:.2f}); background: transparent; border: none;"
            )


class LyricsTab(QWidget):
    """
    Redesigned Lyrics Tab matching Gambar 1.
    - View mode toolbar: Editorial Left, Center Stage, Studio Teleprompter
    - Depth Blur: ON / OFF toggle with real QGraphicsBlurEffect
    - Smooth animated vertical scrolling (QPropertyAnimation)
    """
    seek_time_requested = pyqtSignal(int)  # time in ms

    def __init__(self, parent=None):
        super().__init__(parent)
        self.active_idx = -1
        self.user_scrolled = False
        self.lyric_style = "editorial-left"  # 'editorial-left' | 'cinema-center' | 'karaoke-mono'
        self.depth_blur = True
        self.accent_color = "#34D399"
        self.raw_lines = []
        self.current_title = ""
        self.current_artist = ""

        self.resume_timer = QTimer(self)
        self.resume_timer.setSingleShot(True)
        self.resume_timer.timeout.connect(self._resume_auto_scroll)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(6, 6, 6, 4)
        self.layout.setSpacing(6)

        # 1. Sub-controls Bar (Style Pills + Depth Blur Toggle) matching Gambar 1
        self.sub_bar = QHBoxLayout()
        self.sub_bar.setContentsMargins(2, 0, 2, 2)
        self.sub_bar.setSpacing(6)

        self.btn_editorial = QPushButton("Editorial Left")
        self.btn_editorial.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_editorial.setMinimumWidth(106)
        self.btn_editorial.clicked.connect(lambda: self.set_lyric_style("editorial-left"))
        self.sub_bar.addWidget(self.btn_editorial)

        self.btn_center = QPushButton("Center Stage")
        self.btn_center.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_center.setMinimumWidth(96)
        self.btn_center.clicked.connect(lambda: self.set_lyric_style("cinema-center"))
        self.sub_bar.addWidget(self.btn_center)

        self.btn_teleprompter = QPushButton("Studio Teleprompter")
        self.btn_teleprompter.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_teleprompter.setMinimumWidth(142)
        self.btn_teleprompter.clicked.connect(lambda: self.set_lyric_style("karaoke-mono"))
        self.sub_bar.addWidget(self.btn_teleprompter)

        self.sub_bar.addStretch()

        self.btn_depth = QPushButton("Depth Blur: ON")
        self.btn_depth.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_depth.setMinimumWidth(108)
        self.btn_depth.clicked.connect(self._toggle_depth_blur)
        self.sub_bar.addWidget(self.btn_depth)

        self.layout.addLayout(self.sub_bar)

        # 2. Lyrics List Widget
        self.list_widget = QListWidget()
        self.list_widget.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.list_widget.setSpacing(2)
        self.list_widget.verticalScrollBar().sliderPressed.connect(self._on_user_scroll_start)
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        self.layout.addWidget(self.list_widget)

        # Smooth scroll animation on vertical scrollbar
        self.scroll_anim = QPropertyAnimation(self.list_widget.verticalScrollBar(), b"value", self)
        self.scroll_anim.setDuration(280)
        self.scroll_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        # Empty State Label (displays Title & Author when no lyrics exist)
        self.empty_label = QLabel("")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setTextFormat(Qt.TextFormat.RichText)
        self.empty_label.setWordWrap(True)
        self.empty_label.setStyleSheet("color: #FFFFFF; background: transparent; border: none;")
        self.layout.addWidget(self.empty_label, 1)

        self._update_toolbar_styles()

    def set_track_metadata(self, title: str, artist: str):
        self.current_title = title or ""
        self.current_artist = artist or ""
        if not self.raw_lines:
            self._update_empty_track_display()

    def _update_empty_track_display(self):
        if self.current_title:
            html = (
                f"<div style='text-align:center;'>"
                f"<div style='font-size:16px; font-weight:800; color:#FFFFFF; margin-bottom:4px;'>{self.current_title}</div>"
                f"<div style='font-size:12.5px; font-weight:500; color:rgba(255,255,255,0.60);'>{self.current_artist}</div>"
                f"</div>"
            )
            self.empty_label.setText(html)
        else:
            self.empty_label.setText(
                "<div style='font-size:13px; color:rgba(255,255,255,0.45);'>Belum ada lagu yang diputar</div>"
            )

    def set_accent_color(self, hex_color: str):
        self.accent_color = hex_color
        self._update_toolbar_styles()
        self._refresh_all_items()

    def set_lyric_style(self, style_mode: str):
        self.lyric_style = style_mode
        self._update_toolbar_styles()
        self._refresh_all_items()

    def _toggle_depth_blur(self):
        self.depth_blur = not self.depth_blur
        self._update_toolbar_styles()
        self._refresh_all_items()

    def _update_toolbar_styles(self):
        active_css = (
            "background: rgba(255, 255, 255, 0.12); "
            "border: 1px solid rgba(255, 255, 255, 0.32); "
            "color: #FFFFFF; font-size: 10.5px; font-weight: 700; "
            "padding: 3px 10px; border-radius: 6px; font-family: 'Courier New', monospace;"
        )
        inactive_css = (
            "background: transparent; "
            "border: 1px solid transparent; "
            "color: rgba(255, 255, 255, 0.48); font-size: 10.5px; font-weight: 500; "
            "padding: 3px 10px; border-radius: 6px; font-family: 'Courier New', monospace;"
        )

        self.btn_editorial.setStyleSheet(active_css if self.lyric_style == "editorial-left" else inactive_css)
        self.btn_center.setStyleSheet(active_css if self.lyric_style == "cinema-center" else inactive_css)
        self.btn_teleprompter.setStyleSheet(active_css if self.lyric_style == "karaoke-mono" else inactive_css)

        if self.depth_blur:
            self.btn_depth.setText("Depth Blur: ON")
            self.btn_depth.setStyleSheet(
                f"background: {self.accent_color}1A; "
                f"border: 1px solid {self.accent_color}66; "
                f"color: {self.accent_color}; font-size: 10.5px; font-weight: 700; "
                "padding: 3px 10px; border-radius: 6px; font-family: 'Courier New', monospace;"
            )
        else:
            self.btn_depth.setText("Depth Blur: OFF")
            self.btn_depth.setStyleSheet(
                "background: rgba(255, 255, 255, 0.05); "
                "border: 1px solid rgba(255, 255, 255, 0.15); "
                "color: rgba(255, 255, 255, 0.45); font-size: 10.5px; "
                "padding: 3px 10px; border-radius: 6px; font-family: 'Courier New', monospace;"
            )

    def set_lyrics(self, lyrics_data: dict):
        self.list_widget.clear()
        self.active_idx = -1
        self.user_scrolled = False
        self.raw_lines = lyrics_data.get("lines", [])

        if not self.raw_lines:
            self._update_empty_track_display()
            self.empty_label.setVisible(True)
            self.list_widget.setVisible(False)
            return

        self.empty_label.setVisible(False)
        self.list_widget.setVisible(True)

        for line in self.raw_lines:
            text = line.get("text", "")
            subtext = line.get("subtext", "")
            t_ms = line.get("time_ms", 0)
            t_sec = int(t_ms / 1000)
            time_str = f"{t_sec // 60}:{t_sec % 60:02d}"

            item_widget = LyricItemWidget(text, subtext, time_str, self.lyric_style, parent=self)

            list_item = QListWidgetItem()
            list_item.setData(Qt.ItemDataRole.UserRole, t_ms)
            list_item.setSizeHint(QSize(0, 52 if subtext else 40))
            self.list_widget.addItem(list_item)
            self.list_widget.setItemWidget(list_item, item_widget)

        self._refresh_all_items()

    def _smooth_scroll_to_item(self, item: QListWidgetItem):
        if not item:
            return
        rect = self.list_widget.visualItemRect(item)
        viewport_h = self.list_widget.viewport().height()
        if viewport_h <= 0:
            self.list_widget.scrollToItem(item, QListWidget.ScrollHint.PositionAtCenter)
            return

        sb = self.list_widget.verticalScrollBar()
        current_val = sb.value()
        target_val = current_val + rect.center().y() - (viewport_h // 2)
        target_val = max(sb.minimum(), min(sb.maximum(), target_val))

        self.scroll_anim.stop()
        self.scroll_anim.setStartValue(current_val)
        self.scroll_anim.setEndValue(target_val)
        self.scroll_anim.start()

    def set_active_line(self, index: int):
        count = self.list_widget.count()
        if count == 0 or index < 0 or index >= count:
            return

        if self.active_idx == index:
            return

        self.active_idx = index
        self._refresh_all_items()

        if not self.user_scrolled:
            target_item = self.list_widget.item(index)
            if target_item:
                self._smooth_scroll_to_item(target_item)

    def _refresh_all_items(self):
        count = self.list_widget.count()
        for i in range(count):
            item = self.list_widget.item(i)
            widget = self.list_widget.itemWidget(item)
            if isinstance(widget, LyricItemWidget):
                is_active = (i == self.active_idx)
                dist = abs(i - self.active_idx) if self.active_idx >= 0 else 1
                widget.set_active(is_active, dist, self.depth_blur, self.lyric_style, self.accent_color)

    def _on_item_clicked(self, item: QListWidgetItem):
        t_ms = item.data(Qt.ItemDataRole.UserRole)
        if t_ms is not None:
            self.seek_time_requested.emit(int(t_ms))

    def _on_user_scroll_start(self):
        self.user_scrolled = True
        self.resume_timer.start(3500)

    def _resume_auto_scroll(self):
        self.user_scrolled = False
        if 0 <= self.active_idx < self.list_widget.count():
            item = self.list_widget.item(self.active_idx)
            self._smooth_scroll_to_item(item)
