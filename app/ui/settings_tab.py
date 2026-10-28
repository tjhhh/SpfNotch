from PyQt6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QGridLayout, QLineEdit, QLabel, 
    QPushButton, QComboBox, QSlider, QStackedWidget, QApplication, QScrollArea
)
from PyQt6.QtCore import Qt, pyqtSignal


class FocusAwareLineEdit(QLineEdit):
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


class PresetCardButton(QFrame):
    """
    Custom 2x2 Preset Card matching Gambar 3 ('Liquid Dichroic Glass [RECOMMENDED]', etc.)
    Uses QFrame to avoid QPushButton layout/border inheritance artifacts.
    """
    clicked = pyqtSignal()

    def __init__(self, name: str, tag: str, parent=None):
        super().__init__(parent)
        self.setObjectName("presetCardBtn")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(40)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 10, 6)
        layout.setSpacing(6)

        self.title_lbl = QLabel(name, self)
        self.title_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.title_lbl.setStyleSheet(
            "font-size: 11.5px; font-weight: 700; color: #FFFFFF; background: transparent; border: none;"
        )
        layout.addWidget(self.title_lbl, 1)

        self.tag_lbl = QLabel(tag, self)
        self.tag_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.tag_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.tag_lbl.setStyleSheet(
            "font-size: 8.5px; font-family: 'Courier New', monospace; font-weight: 700; "
            "color: #34D399; background: rgba(52, 211, 153, 0.14); "
            "padding: 2px 6px; border-radius: 5px; border: none;"
        )
        layout.addWidget(self.tag_lbl)

        self.set_selected(False)

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(ev)

    def click(self):
        self.clicked.emit()

    def set_selected(self, selected: bool):
        if selected:
            self.setStyleSheet(
                "#presetCardBtn { "
                "background: rgba(255, 255, 255, 0.14); "
                "border: 1px solid rgba(255, 255, 255, 0.35); "
                "border-radius: 13px; "
                "}"
            )
        else:
            self.setStyleSheet(
                "#presetCardBtn { "
                "background: rgba(255, 255, 255, 0.04); "
                "border: 1px solid rgba(255, 255, 255, 0.08); "
                "border-radius: 13px; "
                "} "
                "#presetCardBtn:hover { "
                "background: rgba(255, 255, 255, 0.08); "
                "border: 1px solid rgba(255, 255, 255, 0.16); "
                "}"
            )


class SettingsTab(QWidget):
    """
    Redesigned Personalisasi UI + Pengaturan Tab matching Gambar 3.
    - Starts directly with '1. MATERIAL & OPTICAL GLASS PRESET', 2x2 Preset Cards,
      and 2x2 Glass Sliders Card (matching Gambar 3 pixel-for-pixel at top of scroll).
    - Scrolling down reveals '2. MORFOLOGI NOTCH & TIMELINE' and '3. AKUN & SPOTIFY API'.
    """
    credentials_saved = pyqtSignal(str, str)     # client_id, client_secret
    idle_mode_changed = pyqtSignal(str)          # "lyrics" or "track"
    input_focused = pyqtSignal()
    personalization_changed = pyqtSignal(dict)   # glass and ui parameters
    exit_requested = pyqtSignal()

    PRESETS = [
        {
            "id": "default-black",
            "name": "Mode Hitam (Default)",
            "tag": "BLACK OBSIDIAN",
            "opacity": 0.94,
            "blur": 28,
            "specular": 0.18,
            "chroma": 0.25,
            "tint": "9, 10, 15",
            "morph": "hardware-flush",
            "scrubber": "waveform"
        },
        {
            "id": "liquid-prism",
            "name": "Liquid Dichroic Glass",
            "tag": "RECOMMENDED",
            "opacity": 0.42,
            "blur": 28,
            "specular": 0.24,
            "chroma": 0.48,
            "tint": "12, 15, 22",
            "morph": "hardware-flush",
            "scrubber": "waveform"
        },
        {
            "id": "frosted-quartz",
            "name": "Crystal Tembus Ekstrem",
            "tag": "ULTRA CLEAR",
            "opacity": 0.22,
            "blur": 16,
            "specular": 0.34,
            "chroma": 0.30,
            "tint": "24, 28, 38",
            "morph": "hardware-flush",
            "scrubber": "waveform"
        },
        {
            "id": "chroma-bleed",
            "name": "Sonic Aura Mesh",
            "tag": "SYNAESTHETIC",
            "opacity": 0.52,
            "blur": 36,
            "specular": 0.20,
            "chroma": 0.85,
            "tint": "10, 10, 16",
            "morph": "hardware-flush",
            "scrubber": "waveform"
        },
        {
            "id": "te-field-metal",
            "name": "Teenage Eng. Smoked",
            "tag": "HARDWARE HUD",
            "opacity": 0.68,
            "blur": 20,
            "specular": 0.18,
            "chroma": 0.15,
            "tint": "14, 15, 18",
            "morph": "sharp-hud",
            "scrubber": "waveform"
        }
    ]

    def __init__(self, current_client_id: str = "", current_client_secret: str = "", parent=None):
        super().__init__(parent)
        self.selected_preset_id = "default-black"
        self.glass_opacity = 0.94
        self.glass_blur = 28
        self.specular_rim = 0.18
        self.chroma_glow = 0.25
        self.tint_rgb = "9, 10, 15"
        self.notch_morph = "hardware-flush"
        self.scrubber_style = "waveform"

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(4, 4, 4, 2)
        self.layout.setSpacing(0)

        # Hidden subtab buttons & stacked alias for 100% backward test compatibility
        self.btn_sub_personal = QPushButton("Personalisasi UI", self)
        self.btn_sub_personal.setVisible(False)
        self.btn_sub_personal.clicked.connect(lambda: self._switch_subtab(0))

        self.btn_sub_spotify = QPushButton("Akun & Spotify API", self)
        self.btn_sub_spotify.setVisible(False)
        self.btn_sub_spotify.clicked.connect(lambda: self._switch_subtab(1))

        self.stacked = QStackedWidget(self)
        self.stacked.setVisible(False)
        self.stacked.addWidget(QWidget())
        self.stacked.addWidget(QWidget())

        # Smooth borderless Scroll Area so top view matches Gambar 3 exactly
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        self.scroll_content = QWidget()
        self.scroll_content.setStyleSheet("background: transparent;")
        self.content_layout = QVBoxLayout(self.scroll_content)
        self.content_layout.setContentsMargins(4, 4, 8, 10)
        self.content_layout.setSpacing(11)

        self._build_section_1_glass_presets()
        self._build_section_2_morphology()
        self._build_section_3_spotify_settings(current_client_id, current_client_secret)

        self.scroll_area.setWidget(self.scroll_content)
        self.layout.addWidget(self.scroll_area, 1)

        self._update_preset_button_styles()
        self._update_morph_button_styles()

    def _switch_subtab(self, index: int):
        self.stacked.setCurrentIndex(index)
        sb = self.scroll_area.verticalScrollBar()
        if index == 0:
            sb.setValue(0)
        else:
            sb.setValue(sb.maximum())

    # =========================================================================
    # SECTION 1: MATERIAL & OPTICAL GLASS PRESET + 2x2 SLIDERS (Gambar 3)
    # =========================================================================
    def _build_section_1_glass_presets(self):
        lbl_sec1 = QLabel("1. MATERIAL & OPTICAL GLASS PRESET")
        lbl_sec1.setStyleSheet(
            "font-size: 10px; font-family: 'Courier New', monospace; font-weight: 700; "
            "color: rgba(255, 255, 255, 0.50); letter-spacing: 0.8px;"
        )
        self.content_layout.addWidget(lbl_sec1)

        # 2x2 Grid of Presets matching Gambar 3
        self.preset_grid = QGridLayout()
        self.preset_grid.setContentsMargins(0, 0, 0, 0)
        self.preset_grid.setHorizontalSpacing(8)
        self.preset_grid.setVerticalSpacing(7)
        self.preset_buttons: dict[str, PresetCardButton] = {}

        grid_presets = [self.PRESETS[1], self.PRESETS[2], self.PRESETS[3], self.PRESETS[4]]
        for i, p in enumerate(grid_presets):
            card_btn = PresetCardButton(p["name"], p["tag"], parent=self.scroll_content)
            row = i // 2
            col = i % 2
            card_btn.clicked.connect(lambda preset=p: self.apply_preset(preset))
            self.preset_buttons[p["id"]] = card_btn
            self.preset_grid.addWidget(card_btn, row, col)

        self.content_layout.addLayout(self.preset_grid)

        # 2x2 Sliders Card matching Gambar 3
        self.sliders_card = QFrame(self.scroll_content)
        self.sliders_card.setObjectName("slidersGlassCard")
        self.sliders_card.setStyleSheet(
            "#slidersGlassCard { "
            "background: rgba(0, 0, 0, 0.28); "
            "border: 1px solid rgba(255, 255, 255, 0.08); "
            "border-radius: 14px; "
            "}"
        )
        sliders_layout = QGridLayout(self.sliders_card)
        sliders_layout.setContentsMargins(14, 11, 14, 12)
        sliders_layout.setHorizontalSpacing(14)
        sliders_layout.setVerticalSpacing(7)

        # Slider 1: Efek Tembus (Clear)
        self.lbl_clear_val = QLabel("6%")
        self.lbl_clear_val.setStyleSheet(
            "font-size: 11px; font-family: 'Courier New', monospace; color: #34D399; font-weight: bold;"
        )
        s1_head = QHBoxLayout()
        s1_title = QLabel("Efek Tembus (Clear)")
        s1_title.setStyleSheet("font-size: 11px; color: rgba(255, 255, 255, 0.72);")
        s1_head.addWidget(s1_title)
        s1_head.addStretch()
        s1_head.addWidget(self.lbl_clear_val)
        sliders_layout.addLayout(s1_head, 0, 0)

        self.slider_clear = QSlider(Qt.Orientation.Horizontal)
        self.slider_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        self.slider_clear.setRange(0, 88)
        self.slider_clear.setValue(6)
        self.slider_clear.valueChanged.connect(self._on_clear_changed)
        sliders_layout.addWidget(self.slider_clear, 1, 0)

        # Slider 2: Refraksi Blur
        self.lbl_blur_val = QLabel("28px")
        self.lbl_blur_val.setStyleSheet(
            "font-size: 11px; font-family: 'Courier New', monospace; color: #34D399; font-weight: bold;"
        )
        s2_head = QHBoxLayout()
        s2_title = QLabel("Refraksi Blur")
        s2_title.setStyleSheet("font-size: 11px; color: rgba(255, 255, 255, 0.72);")
        s2_head.addWidget(s2_title)
        s2_head.addStretch()
        s2_head.addWidget(self.lbl_blur_val)
        sliders_layout.addLayout(s2_head, 0, 1)

        self.slider_blur = QSlider(Qt.Orientation.Horizontal)
        self.slider_blur.setCursor(Qt.CursorShape.PointingHandCursor)
        self.slider_blur.setRange(6, 48)
        self.slider_blur.setValue(28)
        self.slider_blur.valueChanged.connect(self._on_blur_changed)
        sliders_layout.addWidget(self.slider_blur, 1, 1)

        # Slider 3: Chroma Bleed Cover
        self.lbl_chroma_val = QLabel("25%")
        self.lbl_chroma_val.setStyleSheet(
            "font-size: 11px; font-family: 'Courier New', monospace; color: #34D399; font-weight: bold;"
        )
        s3_head = QHBoxLayout()
        s3_title = QLabel("Chroma Bleed Cover")
        s3_title.setStyleSheet("font-size: 11px; color: rgba(255, 255, 255, 0.72);")
        s3_head.addWidget(s3_title)
        s3_head.addStretch()
        s3_head.addWidget(self.lbl_chroma_val)
        sliders_layout.addLayout(s3_head, 2, 0)

        self.slider_chroma = QSlider(Qt.Orientation.Horizontal)
        self.slider_chroma.setCursor(Qt.CursorShape.PointingHandCursor)
        self.slider_chroma.setRange(0, 100)
        self.slider_chroma.setValue(25)
        self.slider_chroma.valueChanged.connect(self._on_chroma_changed)
        sliders_layout.addWidget(self.slider_chroma, 3, 0)

        # Slider 4: Specular Rim 1px
        self.lbl_specular_val = QLabel("18%")
        self.lbl_specular_val.setStyleSheet(
            "font-size: 11px; font-family: 'Courier New', monospace; color: #34D399; font-weight: bold;"
        )
        s4_head = QHBoxLayout()
        s4_title = QLabel("Specular Rim 1px")
        s4_title.setStyleSheet("font-size: 11px; color: rgba(255, 255, 255, 0.72);")
        s4_head.addWidget(s4_title)
        s4_head.addStretch()
        s4_head.addWidget(self.lbl_specular_val)
        sliders_layout.addLayout(s4_head, 2, 1)

        self.slider_specular = QSlider(Qt.Orientation.Horizontal)
        self.slider_specular.setCursor(Qt.CursorShape.PointingHandCursor)
        self.slider_specular.setRange(5, 50)
        self.slider_specular.setValue(18)
        self.slider_specular.valueChanged.connect(self._on_specular_changed)
        sliders_layout.addWidget(self.slider_specular, 3, 1)

        self.content_layout.addWidget(self.sliders_card)

    # =========================================================================
    # SECTION 2: MORFOLOGI NOTCH & TIMELINE (Scroll Down)
    # =========================================================================
    def _build_section_2_morphology(self):
        sec2_head = QHBoxLayout()
        sec2_head.setContentsMargins(0, 12, 0, 0)
        lbl_sec2 = QLabel("2. MORFOLOGI NOTCH & TIMELINE")
        lbl_sec2.setStyleSheet(
            "font-size: 10px; font-family: 'Courier New', monospace; font-weight: 700; "
            "color: rgba(255, 255, 255, 0.50); letter-spacing: 0.8px;"
        )
        sec2_head.addWidget(lbl_sec2)
        sec2_head.addStretch()

        self.btn_reset_black = QPushButton("↺ Mode Hitam (Default)")
        self.btn_reset_black.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_reset_black.clicked.connect(lambda: self.apply_preset(self.PRESETS[0]))
        sec2_head.addWidget(self.btn_reset_black)
        self.content_layout.addLayout(sec2_head)

        morph_row = QHBoxLayout()
        morph_row.setSpacing(6)

        self.btn_morph_bezel = QPushButton("Bezel Ears")
        self.btn_morph_bezel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_morph_bezel.clicked.connect(lambda: self.set_morphology("hardware-flush"))
        morph_row.addWidget(self.btn_morph_bezel)

        self.btn_morph_float = QPushButton("Floating Capsule")
        self.btn_morph_float.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_morph_float.clicked.connect(lambda: self.set_morphology("floating-island"))
        morph_row.addWidget(self.btn_morph_float)

        self.btn_morph_sharp = QPushButton("Sharp HUD")
        self.btn_morph_sharp.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_morph_sharp.clicked.connect(lambda: self.set_morphology("sharp-hud"))
        morph_row.addWidget(self.btn_morph_sharp)

        morph_row.addStretch()

        self.btn_timeline_toggle = QPushButton("Timeline: Waveform")
        self.btn_timeline_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_timeline_toggle.setStyleSheet(
            "background: rgba(255, 255, 255, 0.06); "
            "border: 1px solid rgba(255, 255, 255, 0.15); "
            "color: #FFFFFF; font-size: 10.5px; font-family: 'Courier New', monospace; "
            "padding: 4px 10px; border-radius: 8px;"
        )
        self.btn_timeline_toggle.clicked.connect(self._toggle_timeline_style)
        morph_row.addWidget(self.btn_timeline_toggle)

        self.content_layout.addLayout(morph_row)

    # =========================================================================
    # SECTION 3: PENGATURAN AKUN & SPOTIFY API (Scroll Down)
    # =========================================================================
    def _build_section_3_spotify_settings(self, current_client_id: str, current_client_secret: str):
        lbl_sec3 = QLabel("3. PENGATURAN SPOTIFY API & SISTEM")
        lbl_sec3.setStyleSheet(
            "font-size: 10px; font-family: 'Courier New', monospace; font-weight: 700; "
            "color: rgba(255, 255, 255, 0.50); letter-spacing: 0.8px; margin-top: 4px;"
        )
        self.content_layout.addWidget(lbl_sec3)

        spotify_card = QFrame(self.scroll_content)
        spotify_card.setObjectName("spotifySettingsCard")
        spotify_card.setStyleSheet(
            "#spotifySettingsCard { "
            "background: rgba(0, 0, 0, 0.28); "
            "border: 1px solid rgba(255, 255, 255, 0.08); "
            "border-radius: 14px; "
            "}"
        )
        sp_layout = QVBoxLayout(spotify_card)
        sp_layout.setContentsMargins(12, 10, 12, 10)
        sp_layout.setSpacing(7)

        # Connection status banner
        self.status_banner = QLabel("● Belum Terhubung ke Spotify API")
        self.status_banner.setStyleSheet("color: #F59E0B; font-weight: bold; font-size: 11px;")
        sp_layout.addWidget(self.status_banner)

        # Guide text
        self.guide = QLabel(
            "Buka <b>developer.spotify.com/dashboard</b>, set Redirect URI ke "
            "<b>http://127.0.0.1:8888/callback</b>, lalu isi Client ID & Secret:"
        )
        self.guide.setStyleSheet("color: rgba(255, 255, 255, 0.60); font-size: 10.5px;")
        self.guide.setTextFormat(Qt.TextFormat.RichText)
        self.guide.setWordWrap(True)
        sp_layout.addWidget(self.guide)

        # Row 1: Client ID + Paste
        id_layout = QHBoxLayout()
        id_layout.setSpacing(6)
        self.id_input = FocusAwareLineEdit()
        self.id_input.setPlaceholderText("Spotify Client ID")
        self.id_input.setText(current_client_id)
        self.id_input.focus_activated.connect(self.input_focused.emit)
        id_layout.addWidget(self.id_input, 1)

        self.btn_paste_id = QPushButton("📋 Tempel")
        self.btn_paste_id.setProperty("class", "btn-paste")
        self.btn_paste_id.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_paste_id.clicked.connect(self._paste_id)
        id_layout.addWidget(self.btn_paste_id)
        sp_layout.addLayout(id_layout)

        # Row 2: Client Secret + Paste
        sec_layout = QHBoxLayout()
        sec_layout.setSpacing(6)
        self.secret_input = FocusAwareLineEdit()
        self.secret_input.setPlaceholderText("Spotify Client Secret")
        self.secret_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.secret_input.setText(current_client_secret)
        self.secret_input.focus_activated.connect(self.input_focused.emit)
        sec_layout.addWidget(self.secret_input, 1)

        self.btn_paste_sec = QPushButton("📋 Tempel")
        self.btn_paste_sec.setProperty("class", "btn-paste")
        self.btn_paste_sec.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_paste_sec.clicked.connect(self._paste_secret)
        sec_layout.addWidget(self.btn_paste_sec)
        sp_layout.addLayout(sec_layout)

        # Save & Connect Button
        self.btn_save = QPushButton("Simpan & Hubungkan")
        self.btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save.setStyleSheet(
            "QPushButton { "
            "background-color: #10B981; color: #090A0F; font-weight: 800; "
            "padding: 7px; border-radius: 9px; font-size: 11.5px; "
            "} "
            "QPushButton:hover { background-color: #34D399; }"
        )
        self.btn_save.clicked.connect(self._on_save_clicked)
        sp_layout.addWidget(self.btn_save)

        # Bottom row: Idle Mode + Exit Notch Button
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(8)

        idle_lbl = QLabel("Mode Pill:")
        idle_lbl.setStyleSheet("color: rgba(255, 255, 255, 0.70); font-size: 11px; font-weight: 600;")
        bottom_row.addWidget(idle_lbl)

        self.combo_idle = QComboBox()
        self.combo_idle.addItem("🎵 Lirik Berjalan (Synced)", "lyrics")
        self.combo_idle.addItem("💿 Judul Lagu & Artis", "track")
        self.combo_idle.setStyleSheet("""
            QComboBox {
                background: rgba(0, 0, 0, 0.35);
                color: #FFFFFF;
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 8px;
                padding: 4px 10px;
                font-size: 11px;
            }
            QComboBox QAbstractItemView {
                background: #141721;
                color: #FFFFFF;
                selection-background-color: #34D399;
                selection-color: #000000;
            }
        """)
        self.combo_idle.currentIndexChanged.connect(self._on_idle_mode_changed)
        bottom_row.addWidget(self.combo_idle, 1)

        self.btn_quit_app = QPushButton("⏻ Keluar")
        self.btn_quit_app.setProperty("class", "btn-exit")
        self.btn_quit_app.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_quit_app.setStyleSheet(
            "QPushButton { "
            "background: rgba(244, 63, 94, 0.12); "
            "border: 1px solid rgba(244, 63, 94, 0.30); "
            "color: #FDA4AF; font-size: 10.5px; font-weight: 700; "
            "padding: 4px 10px; border-radius: 8px; "
            "} "
            "QPushButton:hover { background: rgba(244, 63, 94, 0.28); color: #FFFFFF; }"
        )
        self.btn_quit_app.clicked.connect(self.exit_requested.emit)
        bottom_row.addWidget(self.btn_quit_app)

        sp_layout.addLayout(bottom_row)
        self.content_layout.addWidget(spotify_card)

    def apply_preset(self, preset: dict):
        self.selected_preset_id = preset["id"]
        self.glass_opacity = round(float(preset["opacity"]), 2)
        self.glass_blur = preset["blur"]
        self.specular_rim = round(float(preset["specular"]), 2)
        self.chroma_glow = round(float(preset["chroma"]), 2)
        self.tint_rgb = preset.get("tint", "9, 10, 15")
        if "morph" in preset:
            self.notch_morph = preset["morph"]
        if "scrubber" in preset:
            self.scrubber_style = preset["scrubber"]

        clear_pct = int(round((1.0 - self.glass_opacity) * 100))
        self.slider_clear.blockSignals(True)
        self.slider_clear.setValue(clear_pct)
        self.slider_clear.blockSignals(False)
        self.lbl_clear_val.setText(f"{clear_pct}%")

        self.slider_blur.blockSignals(True)
        self.slider_blur.setValue(int(self.glass_blur))
        self.slider_blur.blockSignals(False)
        self.lbl_blur_val.setText(f"{int(self.glass_blur)}px")

        chroma_pct = int(round(self.chroma_glow * 100))
        self.slider_chroma.blockSignals(True)
        self.slider_chroma.setValue(chroma_pct)
        self.slider_chroma.blockSignals(False)
        self.lbl_chroma_val.setText(f"{chroma_pct}%")

        specular_pct = int(round(self.specular_rim * 100))
        self.slider_specular.blockSignals(True)
        self.slider_specular.setValue(specular_pct)
        self.slider_specular.blockSignals(False)
        self.lbl_specular_val.setText(f"{specular_pct}%")

        self._update_preset_button_styles()
        self._update_morph_button_styles()
        self._emit_personalization()

    def set_morphology(self, morph_mode: str):
        self.notch_morph = morph_mode
        self._update_morph_button_styles()
        self._emit_personalization()

    def _toggle_timeline_style(self):
        if self.scrubber_style == "waveform":
            self.scrubber_style = "laser-line"
            self.btn_timeline_toggle.setText("Timeline: Laser")
        else:
            self.scrubber_style = "waveform"
            self.btn_timeline_toggle.setText("Timeline: Waveform")
        self._emit_personalization()

    def _on_clear_changed(self, val: int):
        self.lbl_clear_val.setText(f"{val}%")
        self.glass_opacity = max(0.12, min(1.0, 1.0 - (val / 100.0)))
        self._emit_personalization()

    def _on_blur_changed(self, val: int):
        self.lbl_blur_val.setText(f"{val}px")
        self.glass_blur = val
        self._emit_personalization()

    def _on_chroma_changed(self, val: int):
        self.lbl_chroma_val.setText(f"{val}%")
        self.chroma_glow = val / 100.0
        self._emit_personalization()

    def _on_specular_changed(self, val: int):
        self.lbl_specular_val.setText(f"{val}%")
        self.specular_rim = val / 100.0
        self._emit_personalization()

    def _emit_personalization(self):
        data = {
            "preset": self.selected_preset_id,
            "opacity": self.glass_opacity,
            "blur": self.glass_blur,
            "specular_border": self.specular_rim,
            "chroma_glow": self.chroma_glow,
            "tint_rgb": self.tint_rgb,
            "notch_morph": self.notch_morph,
            "scrubber_style": self.scrubber_style,
        }
        self.personalization_changed.emit(data)

    def _update_preset_button_styles(self):
        for pid, btn in self.preset_buttons.items():
            btn.set_selected(pid == self.selected_preset_id)

        if hasattr(self, "btn_reset_black"):
            if self.selected_preset_id == "default-black":
                self.btn_reset_black.setStyleSheet(
                    "background: rgba(255, 255, 255, 0.14); border: 1px solid rgba(255, 255, 255, 0.30); "
                    "color: #FFFFFF; font-size: 9.5px; font-family: 'Courier New', monospace; padding: 2px 8px; border-radius: 6px;"
                )
            else:
                self.btn_reset_black.setStyleSheet(
                    "background: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.10); "
                    "color: rgba(255, 255, 255, 0.50); font-size: 9.5px; font-family: 'Courier New', monospace; padding: 2px 8px; border-radius: 6px;"
                )

    def _update_morph_button_styles(self):
        active_css = (
            "background: rgba(255, 255, 255, 0.14); "
            "border: 1px solid rgba(255, 255, 255, 0.30); "
            "color: #FFFFFF; font-size: 10.5px; font-family: 'Courier New', monospace; "
            "padding: 4px 10px; border-radius: 8px;"
        )
        inactive_css = (
            "background: transparent; "
            "border: 1px solid rgba(255, 255, 255, 0.10); "
            "color: rgba(255, 255, 255, 0.50); font-size: 10.5px; font-family: 'Courier New', monospace; "
            "padding: 4px 10px; border-radius: 8px;"
        )
        self.btn_morph_bezel.setStyleSheet(active_css if self.notch_morph == "hardware-flush" else inactive_css)
        self.btn_morph_float.setStyleSheet(active_css if self.notch_morph == "floating-island" else inactive_css)
        if hasattr(self, "btn_morph_sharp"):
            self.btn_morph_sharp.setStyleSheet(active_css if self.notch_morph == "sharp-hud" else inactive_css)

    def _paste_id(self):
        text = QApplication.clipboard().text().strip()
        if text:
            self.id_input.setText(text)

    def _paste_secret(self):
        text = QApplication.clipboard().text().strip()
        if text:
            self.secret_input.setText(text)

    def _on_idle_mode_changed(self, idx: int):
        mode = self.combo_idle.currentData()
        self.idle_mode_changed.emit(mode)

    def set_connected(self, is_connected: bool):
        if is_connected:
            self.status_banner.setText("● Terhubung ke Spotify API")
            self.status_banner.setStyleSheet("color: #34D399; font-weight: bold; font-size: 11px;")
        else:
            self.status_banner.setText("● Belum Terhubung (Mode Demo)")
            self.status_banner.setStyleSheet("color: #F59E0B; font-weight: bold; font-size: 11px;")

    def set_credentials(self, client_id: str, client_secret: str):
        if client_id:
            self.id_input.setText(client_id)
        if client_secret:
            self.secret_input.setText(client_secret)

    def _on_save_clicked(self):
        c_id = self.id_input.text().strip()
        c_secret = self.secret_input.text().strip()
        if c_id and c_secret:
            self.credentials_saved.emit(c_id, c_secret)
