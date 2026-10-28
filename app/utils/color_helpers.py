from PyQt6.QtGui import QPixmap, QImage, QColor
from PyQt6.QtCore import Qt

def extract_dominant_color(pixmap: QPixmap | None, default_hex: str = "#34D399") -> str:
    """
    Extracts a vibrant dominant accent color from a pixmap.
    Uses downscaled pixel sampling (16x16) for lightning-fast, CPU-light processing.
    Prefers colors with good saturation and brightness.
    """
    if not pixmap or pixmap.isNull():
        return default_hex

    try:
        # Scale down to 16x16 to analyze average color distribution quickly
        img = pixmap.toImage().scaled(16, 16, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
        if img.isNull():
            return default_hex

        best_color = None
        max_score = -1.0

        for y in range(img.height()):
            for x in range(img.width()):
                qc = img.pixelColor(x, y)
                if qc.alpha() < 50:
                    continue

                # HSL / HSV metrics
                h, s, v, _ = qc.getHsv()
                # Score colors higher if they have vibrant saturation and reasonable value
                # Penalize near-black (v < 40) and near-white (s < 30, v > 220)
                if v < 45 or (s < 25 and v > 210):
                    continue

                # Score: saturation * 1.2 + brightness
                score = (s / 255.0) * 1.4 + (v / 255.0) * 0.8
                if score > max_score:
                    max_score = score
                    best_color = qc

        if best_color and max_score > 0.5:
            # Boost brightness slightly if too dark for high contrast on black notch
            h, s, v, a = best_color.getHsv()
            v = max(180, min(255, v + 25))
            boosted = QColor.fromHsv(h, s, v, a)
            return boosted.name().upper()

        return default_hex
    except Exception as e:
        print(f"[color_helpers] Error extracting color: {e}")
        return default_hex


def get_secondary_complement(hex_color: str) -> str:
    """
    Calculates a soft complementary secondary color (offset hue by ~45 degrees)
    for the dual chromatic ambient glow inside the notch glass.
    """
    try:
        qc = QColor(hex_color)
        if not qc.isValid():
            return "#F59E0B"
        h, s, v, a = qc.getHsv()
        # Shift hue by +40 degrees for harmonious analog/chroma split
        new_h = (h + 40) % 360
        new_c = QColor.fromHsv(new_h, max(120, s - 20), v, a)
        return new_c.name().upper()
    except Exception:
        return "#F59E0B"
