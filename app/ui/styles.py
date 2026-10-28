# Modern Dynamic Island Dark & Optical Glass Theme Styling

COLOR_BG_NOTCH = "#090A0F"
COLOR_BG_CARD = "rgba(255, 255, 255, 0.04)"
COLOR_BG_HOVER = "rgba(255, 255, 255, 0.08)"
COLOR_BORDER = "rgba(255, 255, 255, 0.10)"
COLOR_ACCENT = "#34D399"
COLOR_ACCENT_HOVER = "#10B981"
COLOR_TEXT_PRIMARY = "#FFFFFF"
COLOR_TEXT_SECONDARY = "#A0A0A0"
COLOR_TEXT_MUTED = "#666666"

NOTCH_STYLESHEET = """
QWidget {
    color: #FFFFFF;
    font-family: 'Montserrat', 'Inter', 'Segoe UI', -apple-system, sans-serif;
    font-size: 12px;
}

/* Scrollbars */
QScrollBar:vertical {
    border: none;
    background: transparent;
    width: 3px;
    margin: 2px 0px;
}
QScrollBar::handle:vertical {
    background: rgba(255, 255, 255, 0.22);
    min-height: 28px;
    border-radius: 1.5px;
}
QScrollBar::handle:vertical:hover {
    background: #34D399;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
}

/* Tab Widget Pane */
QTabWidget::pane {
    border: none;
    background: transparent;
}

/* General Buttons */
QPushButton {
    background-color: transparent;
    border: none;
    border-radius: 9px;
    color: #FFFFFF;
    padding: 4px;
}
QPushButton:hover {
    background-color: rgba(255, 255, 255, 0.10);
}
QPushButton:pressed {
    background-color: rgba(255, 255, 255, 0.18);
}

/* Paste / Utility Buttons */
QPushButton.btn-paste {
    background-color: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.15);
    color: #E2E8F0;
    border-radius: 8px;
    padding: 5px 10px;
    font-size: 10.5px;
    font-weight: 600;
}
QPushButton.btn-paste:hover {
    background-color: rgba(255, 255, 255, 0.15);
    border: 1px solid #34D399;
    color: #FFFFFF;
}

/* Exit Power Button */
QPushButton.btn-exit {
    color: #F87171;
    border-radius: 9px;
    font-size: 11px;
    font-weight: bold;
    background: rgba(248, 113, 113, 0.08);
    border: 1px solid rgba(248, 113, 113, 0.18);
}
QPushButton.btn-exit:hover {
    background-color: rgba(239, 68, 68, 0.25);
    color: #FFFFFF;
}

/* Input Fields */
QLineEdit {
    background-color: rgba(0, 0, 0, 0.35);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 10px;
    color: #FFFFFF;
    padding: 6px 12px;
    font-size: 11.5px;
    selection-background-color: #34D399;
    selection-color: #000000;
}
QLineEdit:focus {
    border: 1px solid rgba(52, 211, 153, 0.6);
    background-color: rgba(0, 0, 0, 0.45);
}

/* Sliders matching Gambar 3 (Emerald track + Circular Emerald Thumb) */
QSlider::groove:horizontal {
    height: 6px;
    background: rgba(255, 255, 255, 0.14);
    border: 1px solid rgba(255, 255, 255, 0.18);
    border-radius: 3px;
}
QSlider::sub-page:horizontal {
    background: #10B981;
    border: none;
    border-radius: 3px;
}
QSlider::add-page:horizontal {
    background: rgba(255, 255, 255, 0.12);
    border-radius: 3px;
}
QSlider::handle:horizontal {
    background: #10B981;
    border: 1px solid #34D399;
    width: 14px;
    height: 14px;
    margin-top: -5px;
    margin-bottom: -5px;
    border-radius: 7px;
}
QSlider::handle:horizontal:hover {
    background: #34D399;
    border: 1px solid #A7F3D0;
}

/* Lists (Clean transparent rows so custom cards control their own appearance) */
QListWidget {
    background: transparent;
    border: none;
    outline: none;
}
QListWidget::item {
    padding: 0px;
    margin: 2px 0px;
    border-radius: 12px;
    background: transparent;
    border: none;
}
QListWidget::item:hover {
    background: transparent;
}
QListWidget::item:selected {
    background: transparent;
}
"""
