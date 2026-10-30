from PyQt6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QGridLayout, QLineEdit, QLabel, 
    QPushButton, QComboBox, QSlider, QStackedWidget, QApplication, QScrollArea,
    QColorDialog
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


class ColorSwatchButton(QPushButton):
    """
    Circular color swatch button with active specular ring and tooltip matching Figma.
    """
    def __init__(self, swatch_id: str, name: str, hex_color: str | None = None, parent=None):
        super().__init__(parent)
        self.swatch_id = swatch_id
        self.swatch_name = name
        self.hex_color = hex_color
        self.setFixedSize(26, 26)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        if hex_color:
            self.setToolTip(f"{name} ({hex_color})")
        else:
            self.setToolTip(f"{name} - Dinamis dari sampul lagu")
        self.set_selected(False)

    def set_selected(self, selected: bool):
        if self.swatch_id == "auto":
            bg = "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #F43F5E, stop:0.33 #F59E0B, stop:0.66 #10B981, stop:1 #38BDF8)"
            if selected:
                self.setStyleSheet(
                    f"QPushButton {{ background: {bg}; border: 2.5px solid #FFFFFF; border-radius: 13px; font-size: 11px; }} "
                    f"QPushButton:hover {{ border: 2.5px solid #FFFFFF; }}"
                )
                self.setText("🌈")
            else:
                self.setStyleSheet(
                    f"QPushButton {{ background: {bg}; border: 1.5px solid rgba(255, 255, 255, 0.25); border-radius: 13px; font-size: 10px; }} "
                    f"QPushButton:hover {{ border: 2px solid rgba(255, 255, 255, 0.70); }}"
                )
                self.setText("🌈")
        else:
            c = self.hex_color or "#34D399"
            if selected:
                is_bright = c.lower() in ("#e2e8f0", "#ffffff", "#34d399", "#38bdf8", "#f59e0b")
                txt_color = "#090A0F" if is_bright else "#FFFFFF"
                self.setStyleSheet(
                    f"QPushButton {{ background: {c}; border: 2.5px solid #FFFFFF; border-radius: 13px; font-size: 11px; font-weight: bold; color: {txt_color}; }} "
                    f"QPushButton:hover {{ border: 2.5px solid #FFFFFF; }}"
                )
                self.setText("✓")
            else:
                self.setStyleSheet(
                    f"QPushButton {{ background: {c}; border: 1.5px solid rgba(255, 255, 255, 0.20); border-radius: 13px; }} "
                    f"QPushButton:hover {{ border: 2px solid rgba(255, 255, 255, 0.70); }}"
                )
                self.setText("")


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
    reconnect_requested = pyqtSignal()

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

    CHROMA_SWATCHES = [
        {"id": "auto", "name": "Auto (Sampul)", "hex": None},
        {"id": "mint", "name": "Emerald Mint", "hex": "#34D399"},
        {"id": "cyan", "name": "Electric Cyan", "hex": "#38BDF8"},
        {"id": "violet", "name": "Cyber Violet", "hex": "#A855F7"},
        {"id": "rose", "name": "Neon Rose", "hex": "#FB7185"},
        {"id": "amber", "name": "Solar Amber", "hex": "#F59E0B"},
        {"id": "silver", "name": "Ice Silver", "hex": "#E2E8F0"},
    ]

    def __init__(self, current_client_id: str = "", current_client_secret: str = "", config: dict | None = None, parent=None):
        super().__init__(parent)
        self.selected_preset_id = "default-black"
        self.glass_opacity = 0.94
        self.glass_blur = 28
        self.specular_rim = 0.18
        self.chroma_glow = 0.25
        self.tint_rgb = "9, 10, 15"
        self.notch_morph = "hardware-flush"
        self.scrubber_style = "waveform"
        self.accent_mode = "preset"
        self.current_accent = "#34D399"
        self.swatch_buttons: dict[str, ColorSwatchButton] = {}

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
        self._build_section_2_chroma_accent()
        self._build_section_3_morphology()
        self._build_section_4_spotify_settings(current_client_id, current_client_secret)

        self.scroll_area.setWidget(self.scroll_content)
        self.layout.addWidget(self.scroll_area, 1)

        if config:
            self.load_personalization_config(config)
        else:
            self._update_preset_button_styles()
            self._update_morph_button_styles()
            self._update_swatch_styles()

    def load_personalization_config(self, config: dict):
        p_cfg = config.get("personalization", {})
        ui_cfg = config.get("ui", {})

        self.selected_preset_id = p_cfg.get("preset", "default-black")
        self.glass_opacity = float(p_cfg.get("opacity", 0.94))
        self.glass_blur = int(p_cfg.get("blur", 28))
        self.specular_rim = float(p_cfg.get("specular_border", 0.18))
        self.chroma_glow = float(p_cfg.get("chroma_glow", 0.25))
        self.tint_rgb = p_cfg.get("tint_rgb", "9, 10, 15")
        self.notch_morph = p_cfg.get("notch_morph", "hardware-flush")
        self.scrubber_style = p_cfg.get("scrubber_style", "waveform")
        self.accent_mode = p_cfg.get("accent_mode", "preset")
        self.current_accent = p_cfg.get("accent_color", "#34D399")

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

        if self.scrubber_style == "laser-line":
            self.btn_timeline_toggle.setText("Timeline: Laser")
        else:
            self.btn_timeline_toggle.setText("Timeline: Waveform")

        idle_mode = ui_cfg.get("idle_mode", "lyrics")
        idx = 1 if idle_mode == "track" else 0
        self.combo_idle.blockSignals(True)
        self.combo_idle.setCurrentIndex(idx)
        self.combo_idle.blockSignals(False)

        if self.accent_mode == "auto":
            self.lbl_accent_tag.setText("AUTO (SAMPUL)")
            self.lbl_accent_tag.setStyleSheet(
                "font-size: 9px; font-family: 'Courier New', monospace; font-weight: 700; "
                "color: #38BDF8; background: rgba(56, 189, 248, 0.14); "
                "padding: 2px 7px; border-radius: 5px; border: none;"
            )
        else:
            self.lbl_accent_tag.setText(self.current_accent)
            self.lbl_accent_tag.setStyleSheet(
                f"font-size: 9.5px; font-family: 'Courier New', monospace; font-weight: 700; "
                f"color: {self.current_accent}; background: {self.current_accent}22; "
                "padding: 2px 7px; border-radius: 5px; border: none;"
            )

        self._update_preset_button_styles()
        self._update_morph_button_styles()
        self._update_swatch_styles()

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
    # SECTION 2: CHROMA ACCENT COLOR & AMBIENT GLOW (Gambar 3 / Figma)
    # =========================================================================
    def _build_section_2_chroma_accent(self):
        sec_head = QHBoxLayout()
        sec_head.setContentsMargins(0, 8, 0, 0)
        lbl_sec = QLabel("2. CHROMA ACCENT COLOR")
        lbl_sec.setStyleSheet(
            "font-size: 10px; font-family: 'Courier New', monospace; font-weight: 700; "
            "color: rgba(255, 255, 255, 0.50); letter-spacing: 0.8px;"
        )
        sec_head.addWidget(lbl_sec)
        sec_head.addStretch()

        self.lbl_accent_tag = QLabel(self.current_accent)
        self.lbl_accent_tag.setStyleSheet(
            f"font-size: 9.5px; font-family: 'Courier New', monospace; font-weight: 700; "
            f"color: {self.current_accent}; background: {self.current_accent}22; "
            "padding: 2px 7px; border-radius: 5px; border: none;"
        )
        sec_head.addWidget(self.lbl_accent_tag)
        self.content_layout.addLayout(sec_head)

        # Swatch bar frame
        swatch_card = QFrame(self.scroll_content)
        swatch_card.setObjectName("swatchGlassCard")
        swatch_card.setStyleSheet(
            "#swatchGlassCard { "
            "background: rgba(0, 0, 0, 0.28); "
            "border: 1px solid rgba(255, 255, 255, 0.08); "
            "border-radius: 14px; "
            "}"
        )
        swatch_layout = QHBoxLayout(swatch_card)
        swatch_layout.setContentsMargins(12, 8, 12, 8)
        swatch_layout.setSpacing(8)

        self.swatch_buttons = {}
        for s in self.CHROMA_SWATCHES:
            btn = ColorSwatchButton(s["id"], s["name"], s["hex"], parent=swatch_card)
            btn.clicked.connect(lambda checked=False, sid=s["id"], hex_val=s["hex"]: self._on_swatch_clicked(sid, hex_val))
            self.swatch_buttons[s["id"]] = btn
            swatch_layout.addWidget(btn)

        swatch_layout.addStretch()

        self.content_layout.addWidget(swatch_card)

    def _on_swatch_clicked(self, swatch_id: str, hex_val: str | None):
        if swatch_id == "auto":
            self.set_chroma_accent("auto", None)
        else:
            self.set_chroma_accent("preset", hex_val)

    def _open_custom_color_dialog(self):
        initial = QColor(self.current_accent if self.current_accent else "#34D399")
        color = QColorDialog.getColor(initial, self, "Pilih Warna Aksen Kustom")
        if color.isValid():
            hex_val = color.name().upper()
            self.set_chroma_accent("custom", hex_val)

    def set_chroma_accent(self, mode: str, color_hex: str | None = None):
        self.accent_mode = mode
        if mode == "auto":
            self.lbl_accent_tag.setText("AUTO (SAMPUL)")
            self.lbl_accent_tag.setStyleSheet(
                "font-size: 9px; font-family: 'Courier New', monospace; font-weight: 700; "
                "color: #38BDF8; background: rgba(56, 189, 248, 0.14); "
                "padding: 2px 7px; border-radius: 5px; border: none;"
            )
        else:
            if color_hex:
                self.current_accent = color_hex.upper()
            self.lbl_accent_tag.setText(self.current_accent)
            self.lbl_accent_tag.setStyleSheet(
                f"font-size: 9.5px; font-family: 'Courier New', monospace; font-weight: 700; "
                f"color: {self.current_accent}; background: {self.current_accent}22; "
                "padding: 2px 7px; border-radius: 5px; border: none;"
            )

        self._update_swatch_styles()
        self._emit_personalization()

    def set_initial_accent(self, mode: str, color_hex: str = "#34D399"):
        self.accent_mode = mode
        if color_hex:
            self.current_accent = color_hex.upper()
        if mode == "auto":
            self.lbl_accent_tag.setText("AUTO (SAMPUL)")
            self.lbl_accent_tag.setStyleSheet(
                "font-size: 9px; font-family: 'Courier New', monospace; font-weight: 700; "
                "color: #38BDF8; background: rgba(56, 189, 248, 0.14); "
                "padding: 2px 7px; border-radius: 5px; border: none;"
            )
        else:
            self.lbl_accent_tag.setText(self.current_accent)
            self.lbl_accent_tag.setStyleSheet(
                f"font-size: 9.5px; font-family: 'Courier New', monospace; font-weight: 700; "
                f"color: {self.current_accent}; background: {self.current_accent}22; "
                "padding: 2px 7px; border-radius: 5px; border: none;"
            )
        self._update_swatch_styles()

    def _update_swatch_styles(self):
        if not hasattr(self, "swatch_buttons"):
            return
        for sid, btn in self.swatch_buttons.items():
            if self.accent_mode == "auto":
                btn.set_selected(sid == "auto")
            elif self.accent_mode == "preset":
                btn.set_selected(sid != "auto" and btn.hex_color and btn.hex_color.upper() == self.current_accent.upper())
            else:  # custom
                btn.set_selected(False)

    # =========================================================================
    # SECTION 3: MORFOLOGI NOTCH & TIMELINE (Scroll Down)
    # =========================================================================
    def _build_section_3_morphology(self):
        sec3_head = QHBoxLayout()
        sec3_head.setContentsMargins(0, 10, 0, 0)
        lbl_sec3 = QLabel("3. MORFOLOGI NOTCH & TIMELINE")
        lbl_sec3.setStyleSheet(
            "font-size: 10px; font-family: 'Courier New', monospace; font-weight: 700; "
            "color: rgba(255, 255, 255, 0.50); letter-spacing: 0.8px;"
        )
        sec3_head.addWidget(lbl_sec3)
        sec3_head.addStretch()

        self.btn_reset_black = QPushButton("↺ Mode Hitam (Default)")
        self.btn_reset_black.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_reset_black.clicked.connect(lambda: self.apply_preset(self.PRESETS[0]))
        sec3_head.addWidget(self.btn_reset_black)
        self.content_layout.addLayout(sec3_head)

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

    # Backward compatibility alias
    _build_section_2_morphology = _build_section_3_morphology

    # =========================================================================
    # SECTION 4: PENGATURAN AKUN & SPOTIFY API (Scroll Down)
    # =========================================================================
    def _build_section_4_spotify_settings(self, current_client_id: str, current_client_secret: str):
        lbl_sec4 = QLabel("4. PENGATURAN SPOTIFY API & SISTEM")
        lbl_sec4.setStyleSheet(
            "font-size: 10px; font-family: 'Courier New', monospace; font-weight: 700; "
            "color: rgba(255, 255, 255, 0.50); letter-spacing: 0.8px; margin-top: 4px;"
        )
        self.content_layout.addWidget(lbl_sec4)

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

        # Connection status banner & reconnect button
        status_row = QHBoxLayout()
        status_row.setContentsMargins(0, 0, 0, 0)
        status_row.setSpacing(8)

        self.status_banner = QLabel("● Belum Terhubung ke Spotify API")
        self.status_banner.setStyleSheet("color: #F59E0B; font-weight: bold; font-size: 11px;")
        status_row.addWidget(self.status_banner, 1)

        self.btn_reconnect = QPushButton("🔄 Sambungkan Ulang")
        self.btn_reconnect.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_reconnect.setStyleSheet(
            "QPushButton { "
            "background: rgba(255, 255, 255, 0.08); color: #FFFFFF; font-weight: 600; "
            "padding: 4px 10px; border-radius: 8px; font-size: 11px; "
            "border: 1px solid rgba(255, 255, 255, 0.15); "
            "} "
            "QPushButton:hover { background: rgba(255, 255, 255, 0.16); border-color: rgba(255, 255, 255, 0.30); } "
            "QPushButton:pressed { background: rgba(255, 255, 255, 0.05); }"
        )
        self.btn_reconnect.clicked.connect(self._on_reconnect_clicked)
        status_row.addWidget(self.btn_reconnect)
        sp_layout.addLayout(status_row)

        # Guide text & Dashboard shortcut
        guide_row = QHBoxLayout()
        guide_row.setSpacing(6)
        self.guide = QLabel(
            "Buka <b>developer.spotify.com/dashboard</b>, set Redirect URI ke "
            "<b>http://127.0.0.1:8888/callback</b>, lalu isi Client ID & Secret:"
        )
        self.guide.setStyleSheet("color: rgba(255, 255, 255, 0.60); font-size: 10.5px;")
        self.guide.setTextFormat(Qt.TextFormat.RichText)
        self.guide.setWordWrap(True)
        guide_row.addWidget(self.guide, 1)

        self.btn_open_dashboard = QPushButton("🌐 Buka Dashboard")
        self.btn_open_dashboard.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_open_dashboard.setStyleSheet(
            "QPushButton { "
            "background: rgba(29, 185, 84, 0.15); color: #1DB954; font-weight: bold; "
            "padding: 4px 8px; border-radius: 6px; font-size: 10.5px; border: 1px solid rgba(29, 185, 84, 0.35); "
            "} "
            "QPushButton:hover { background: rgba(29, 185, 84, 0.25); border-color: #1DB954; }"
        )
        self.btn_open_dashboard.clicked.connect(self._open_dashboard)
        guide_row.addWidget(self.btn_open_dashboard)
        sp_layout.addLayout(guide_row)

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

    # Backward compatibility alias
    _build_section_3_spotify_settings = _build_section_4_spotify_settings

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
        if "accent_mode" in preset:
            self.accent_mode = preset["accent_mode"]
        if "accent_color" in preset:
            self.current_accent = preset["accent_color"]

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
        self._update_swatch_styles()
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
            "accent_mode": self.accent_mode,
            "accent_color": self.current_accent,
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

    def _open_dashboard(self):
        import webbrowser
        webbrowser.open("https://developer.spotify.com/dashboard")

    def _on_reconnect_clicked(self):
        if hasattr(self, "btn_reconnect"):
            self.btn_reconnect.setEnabled(False)
            self.btn_reconnect.setText("⏳ Menyambungkan...")
        self.reconnect_requested.emit()

    def set_connected(self, is_connected: bool, error_msg: str = "", product_tier: str = ""):
        if hasattr(self, "btn_reconnect"):
            self.btn_reconnect.setEnabled(True)
            self.btn_reconnect.setText("🔄 Sambungkan Ulang")
        if is_connected and error_msg:
            self.status_banner.setText("● Terhubung ke Spotify API (Limit 429 — Mode Lokal Aktif)")
            self.status_banner.setStyleSheet("color: #F59E0B; font-weight: bold; font-size: 10.5px;")
        elif is_connected:
            tier_str = ""
            if product_tier == "premium":
                tier_str = " (Premium)"
            elif product_tier == "free":
                tier_str = " (Free — Kontrol Lokal)"
            self.status_banner.setText(f"● Terhubung ke Spotify API{tier_str}")
            self.status_banner.setStyleSheet("color: #34D399; font-weight: bold; font-size: 11px;")
        elif error_msg:
            self.status_banner.setText(f"● {error_msg}")
            self.status_banner.setStyleSheet("color: #EF4444; font-weight: bold; font-size: 10.5px;")
        else:
            self.status_banner.setText("● Belum Terhubung ke Spotify API")
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
            self.btn_save.setEnabled(False)
            self.btn_save.setText("⏳ Membuka Browser...")
            self.credentials_saved.emit(c_id, c_secret)
        else:
            self.status_banner.setText("● Masukkan Client ID dan Secret terlebih dahulu")
            self.status_banner.setStyleSheet("color: #EF4444; font-weight: bold; font-size: 11px;")
