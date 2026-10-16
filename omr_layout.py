"""
omr_layout.py
--------------
Koordinat "kanonik" borang OMR. Fail ini dikongsi oleh omr_generator.py
(untuk melukis borang) dan omr_scanner.py (untuk membaca borang).

PENTING: Jangan tukar nilai di sini tanpa jana semula borang baharu -
borang lama yang telah dicetak tidak akan sepadan dengan koordinat baharu.
"""

# Saiz kanvas "diselaraskan" (canonical) selepas pembetulan perspektif.
# Semua borang yang dijana dan semua imej yang diimbas akan dipetakan
# kepada saiz ini supaya koordinat gelembung sentiasa konsisten.
CANVAS_W = 1000
CANVAS_H = 1400

# ArUco marker (DICT_4X4_50) diletakkan di 4 penjuru untuk pembetulan
# perspektif (perspective correction) apabila gambar diambil menggunakan
# kamera telefon (tidak rata / senget).
ARUCO_DICT_NAME = "DICT_4X4_50"
MARKER_PIXEL_SIZE = 80   # saiz marker semasa dilukis pada borang (piksel)
MARKER_MARGIN = 30       # jarak marker dari tepi kanvas

MARKER_IDS = {
    "TL": 0,  # top-left
    "TR": 1,  # top-right
    "BL": 2,  # bottom-left
    "BR": 3,  # bottom-right
}


def marker_center(position: str):
    """Pusat piksel bagi setiap marker selepas warp, dalam sistem CANVAS_W x CANVAS_H."""
    half = MARKER_PIXEL_SIZE / 2
    if position == "TL":
        return (MARKER_MARGIN + half, MARKER_MARGIN + half)
    if position == "TR":
        return (CANVAS_W - MARKER_MARGIN - half, MARKER_MARGIN + half)
    if position == "BL":
        return (MARKER_MARGIN + half, CANVAS_H - MARKER_MARGIN - half)
    if position == "BR":
        return (CANVAS_W - MARKER_MARGIN - half, CANVAS_H - MARKER_MARGIN - half)
    raise ValueError(f"Posisi marker tidak sah: {position}")


# ---- Susun atur soalan / gelembung jawapan ----
TOTAL_QUESTIONS = 20
OPTIONS = ["A", "B", "C", "D"]

# 2 lajur (Q1-10 di kiri, Q11-20 di kanan), 10 baris setiap lajur.
QUESTIONS_PER_COLUMN = 10
COLUMN_X_START = [140, 580]     # x permulaan label soalan bagi setiap lajur
ROW_Y_START = 260               # y bagi soalan pertama
ROW_HEIGHT = 100                # jarak menegak antara baris

BUBBLE_RADIUS = 14
BUBBLE_GAP = 55                 # jarak mendatar antara pusat gelembung
FIRST_BUBBLE_OFFSET_X = 90      # jarak gelembung 'A' dari label soalan


def bubble_positions():
    """
    Kembalikan dict:
        { nombor_soalan (1..20): { 'A': (x, y), 'B': (x, y), 'C': (x, y), 'D': (x, y) } }
    """
    positions = {}
    for q in range(1, TOTAL_QUESTIONS + 1):
        col = 0 if q <= QUESTIONS_PER_COLUMN else 1
        row = (q - 1) % QUESTIONS_PER_COLUMN
        base_x = COLUMN_X_START[col]
        base_y = ROW_Y_START + row * ROW_HEIGHT

        opts = {}
        for i, opt in enumerate(OPTIONS):
            x = base_x + FIRST_BUBBLE_OFFSET_X + i * BUBBLE_GAP
            y = base_y
            opts[opt] = (x, y)
        positions[q] = opts
    return positions


def question_label_position(q: int):
    """Posisi (x, y) untuk label 'Q1', 'Q2', dst."""
    col = 0 if q <= QUESTIONS_PER_COLUMN else 1
    row = (q - 1) % QUESTIONS_PER_COLUMN
    base_x = COLUMN_X_START[col]
    base_y = ROW_Y_START + row * ROW_HEIGHT
    return (base_x, base_y)