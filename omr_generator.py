"""
omr_generator.py
------------------
Menjana borang OMR (20 soalan, pilihan A-D, dengan medan Nama & Kelas)
sebagai imej PNG dalam memori (tiada fail ditulis ke cakera). Termasuk
4 ArUco marker di penjuru untuk membolehkan omr_scanner.py membetulkan
perspektif gambar yang diambil menggunakan kamera telefon.
"""

import io
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

import omr_layout as layout


def _get_font(size: int):
    """Cuba dapatkan font TrueType; jatuh balik kepada font lalai PIL jika tiada."""
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "arial.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _draw_aruco_marker(canvas: Image.Image, marker_id: int, position: str):
    aruco_dict = cv2.aruco.getPredefinedDictionary(
        getattr(cv2.aruco, layout.ARUCO_DICT_NAME)
    )
    marker_img = cv2.aruco.generateImageMarker(
        aruco_dict, marker_id, layout.MARKER_PIXEL_SIZE
    )
    marker_pil = Image.fromarray(marker_img).convert("L")

    cx, cy = layout.marker_center(position)
    top_left_x = int(cx - layout.MARKER_PIXEL_SIZE / 2)
    top_left_y = int(cy - layout.MARKER_PIXEL_SIZE / 2)
    canvas.paste(marker_pil, (top_left_x, top_left_y))


def generate_omr_sheet(exam_title: str = "OMR ANSWER SHEET") -> bytes:
    """
    Jana borang OMR dan kembalikan bait imej PNG (dalam memori, bukan fail).
    """
    canvas = Image.new("RGB", (layout.CANVAS_W, layout.CANVAS_H), "white")
    draw = ImageDraw.Draw(canvas)

    title_font = _get_font(34)
    label_font = _get_font(20)
    small_font = _get_font(16)
    q_font = _get_font(18)

    # ---- Header ----
    draw.text((layout.CANVAS_W // 2, 50), exam_title, font=title_font, fill="black", anchor="mm")

    # Medan Nama & Kelas (x dijaga antara 130-870 supaya tidak bertindih dengan
    # marker ArUco di penjuru, yang menduduki x:[30,110] dan x:[890,970]).
    draw.text((130, 100), "Nama:", font=label_font, fill="black")
    draw.line([(210, 122), (560, 122)], fill="black", width=2)

    draw.text((590, 100), "Kelas:", font=label_font, fill="black")
    draw.line([(660, 122), (870, 122)], fill="black", width=2)

    draw.text((60, 160), "Arahan: Hitamkan gelembung jawapan dengan penuh menggunakan pen/pensel gelap.",
               font=small_font, fill="black")

    # ---- 4 ArUco marker penjuru (untuk pembetulan perspektif) ----
    for position, marker_id in layout.MARKER_IDS.items():
        _draw_aruco_marker(canvas, marker_id, position)

    # ---- Gelembung jawapan ----
    positions = layout.bubble_positions()
    for q in range(1, layout.TOTAL_QUESTIONS + 1):
        label_x, label_y = layout.question_label_position(q)
        draw.text((label_x, label_y), f"{q}.", font=q_font, fill="black", anchor="lm")

        for opt, (x, y) in positions[q].items():
            r = layout.BUBBLE_RADIUS
            draw.ellipse([x - r, y - r, x + r, y + r], outline="black", width=2)
            draw.text((x, y), opt, font=small_font, fill="black", anchor="mm")

    # ---- Footer ----
    footer_font = _get_font(14)
    draw.text(
        (layout.CANVAS_W // 2, layout.CANVAS_H - 22),
        "Jangan lipat borang. Pastikan ke-4 penanda penjuru jelas semasa bergambar.",
        font=footer_font, fill="black", anchor="mm"
    )

    buffer = io.BytesIO()
    canvas.save(buffer, format="PNG")
    return buffer.getvalue()