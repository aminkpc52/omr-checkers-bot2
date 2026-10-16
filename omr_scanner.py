"""
omr_scanner.py
----------------
Analisis gambar borang OMR SEPENUHNYA DALAM MEMORI.
Tiada gambar ditulis ke cakera pada mana-mana ketika - fungsi di sini
menerima 'bytes' imej dan memulangkan keputusan sebagai dict Python.

Langkah:
1. Decode bait imej -> array OpenCV (dalam memori sahaja).
2. Kesan 4 ArUco marker penjuru.
3. Betulkan perspektif (warp) supaya borang menjadi rata & bersaiz piawai.
4. Untuk setiap soalan, periksa 4 gelembung (A-D), kira nisbah piksel gelap
   untuk tentukan gelembung mana yang dihitamkan.
5. Bandingkan dengan skema jawapan & kira markah.
"""

import cv2
import numpy as np

import omr_layout as layout

FILL_THRESHOLD = 0.35   # nisbah piksel gelap minimum untuk dianggap "dihitamkan"
BUBBLE_SAMPLE_HALF = int(layout.BUBBLE_RADIUS * 0.8)


class OMRScanError(Exception):
    """Ralat semasa mengimbas - contohnya marker penjuru tidak dapat dikesan."""
    pass


def _decode_image(image_bytes: bytes) -> np.ndarray:
    np_arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    if img is None:
        raise OMRScanError("Gambar tidak dapat dibaca. Sila hantar semula gambar yang jelas (JPEG/PNG).")
    return img


def _detect_markers(img: np.ndarray):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    aruco_dict = cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, layout.ARUCO_DICT_NAME))
    parameters = cv2.aruco.DetectorParameters()
    detector = cv2.aruco.ArucoDetector(aruco_dict, parameters)
    corners, ids, _ = detector.detectMarkers(gray)

    if ids is None or len(ids) < 4:
        found = 0 if ids is None else len(ids)
        raise OMRScanError(
            f"Hanya {found}/4 penanda penjuru dikesan. Pastikan ke-4 penjuru borang "
            "kelihatan jelas, tidak terpotong, dan pencahayaan mencukupi, kemudian cuba lagi."
        )

    id_to_center = {}
    for i, marker_id in enumerate(ids.flatten()):
        pts = corners[i][0]  # 4 titik penjuru marker ini
        center = pts.mean(axis=0)
        id_to_center[int(marker_id)] = center

    required = set(layout.MARKER_IDS.values())
    if not required.issubset(id_to_center.keys()):
        missing = required - id_to_center.keys()
        raise OMRScanError(f"Penanda ID {missing} tidak dikesan. Cuba ambil gambar semula dengan lebih jelas.")

    return id_to_center


def _warp_to_canonical(img: np.ndarray, id_to_center: dict) -> np.ndarray:
    src_pts = []
    dst_pts = []
    for position, marker_id in layout.MARKER_IDS.items():
        src_pts.append(id_to_center[marker_id])
        dst_pts.append(layout.marker_center(position))

    src = np.array(src_pts, dtype=np.float32)
    dst = np.array(dst_pts, dtype=np.float32)

    M = cv2.getPerspectiveTransform(src, dst)
    warped = cv2.warpPerspective(img, M, (layout.CANVAS_W, layout.CANVAS_H))
    return warped


def _binarize(warped: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    return binary


def _fill_ratio(binary_img: np.ndarray, x: int, y: int) -> float:
    h, w = binary_img.shape
    x0, x1 = max(0, x - BUBBLE_SAMPLE_HALF), min(w, x + BUBBLE_SAMPLE_HALF)
    y0, y1 = max(0, y - BUBBLE_SAMPLE_HALF), min(h, y + BUBBLE_SAMPLE_HALF)
    roi = binary_img[y0:y1, x0:x1]
    if roi.size == 0:
        return 0.0
    return float(np.count_nonzero(roi)) / float(roi.size)


def _read_answers_detailed(binary_img: np.ndarray) -> dict:
    """
    Kembalikan { nombor_soalan: {"final": 'A'/.../'BLANK'/'MULTIPLE', "filled": ['A', ...]} }
    'filled' menyimpan SEMUA gelembung yang dikesan gelap (berguna untuk penandaan
    visual apabila kes 'MULTIPLE').
    """
    positions = layout.bubble_positions()
    detailed = {}

    for q, opts in positions.items():
        ratios = {opt: _fill_ratio(binary_img, int(x), int(y)) for opt, (x, y) in opts.items()}
        filled = [opt for opt, r in ratios.items() if r >= FILL_THRESHOLD]

        if len(filled) == 0:
            final = "BLANK"
        elif len(filled) == 1:
            final = filled[0]
        else:
            final = "MULTIPLE"

        detailed[q] = {"final": final, "filled": filled}

    return detailed


def _score_from_detailed(detailed: dict, scheme: dict) -> dict:
    correct, wrong, blank, multiple = [], [], [], []
    total = 0

    for q in range(1, layout.TOTAL_QUESTIONS + 1):
        detected_ans = detailed.get(q, {"final": "BLANK"})["final"]
        correct_ans = scheme.get(q)

        if detected_ans == "BLANK":
            blank.append(q)
        elif detected_ans == "MULTIPLE":
            multiple.append(q)
        elif correct_ans and detected_ans == correct_ans:
            correct.append(q)
            total += 1
        else:
            wrong.append(q)

    return {
        "total": total,
        "max_score": len(scheme),
        "answers": {q: d["final"] for q, d in detailed.items()},
        "correct": correct,
        "wrong": wrong,
        "blank": blank,
        "multiple": multiple,
    }


# ---- Warna penandaan (BGR - format OpenCV, bukan RGB) ----
COLOR_GREEN = (0, 200, 0)     # jawapan betul
COLOR_RED = (0, 0, 230)       # jawapan salah
COLOR_YELLOW = (0, 210, 255)  # kosong / jawapan berganda (kurang jelas)
MARK_THICKNESS = 3
MARK_RADIUS = layout.BUBBLE_RADIUS + 6


def _annotate(warped_img: np.ndarray, detailed: dict, scheme: dict) -> np.ndarray:
    """Lukis bulatan warna pada gambar borang yang telah diselaraskan (warped, berwarna)."""
    annotated = warped_img.copy()
    positions = layout.bubble_positions()

    for q in range(1, layout.TOTAL_QUESTIONS + 1):
        info = detailed.get(q, {"final": "BLANK", "filled": []})
        final = info["final"]
        filled = info["filled"]
        correct_ans = scheme.get(q)
        opts = positions[q]

        if final not in ("BLANK", "MULTIPLE"):
            # Satu gelembung sahaja ditanda - hijau jika betul, merah jika salah.
            color = COLOR_GREEN if (correct_ans and final == correct_ans) else COLOR_RED
            x, y = opts[final]
            cv2.circle(annotated, (int(x), int(y)), MARK_RADIUS, color, MARK_THICKNESS)

        elif final == "MULTIPLE":
            # Lebih daripada satu gelembung ditanda - semuanya kuning (tidak jelas).
            for opt in filled:
                x, y = opts[opt]
                cv2.circle(annotated, (int(x), int(y)), MARK_RADIUS, COLOR_YELLOW, MARK_THICKNESS)

        else:  # BLANK - tiada gelembung ditanda
            xs = [pt[0] for pt in opts.values()]
            y = opts["A"][1]
            x0 = int(min(xs) - MARK_RADIUS)
            x1 = int(max(xs) + MARK_RADIUS)
            y0 = int(y - MARK_RADIUS)
            y1 = int(y + MARK_RADIUS)
            cv2.rectangle(annotated, (x0, y0), (x1, y1), COLOR_YELLOW, MARK_THICKNESS)

    return annotated


def scan_and_score(image_bytes: bytes, scheme: dict) -> dict:
    """
    scheme: { nombor_soalan (int, 1-20): 'A'/'B'/'C'/'D' }

    Pulangkan:
    {
        "total": int, "max_score": int,
        "answers": { q: jawapan_dikesan },
        "correct": [q, ...], "wrong": [q, ...],
        "blank": [q, ...], "multiple": [q, ...],
    }
    """
    img = _decode_image(image_bytes)
    id_to_center = _detect_markers(img)
    warped = _warp_to_canonical(img, id_to_center)
    binary_img = _binarize(warped)
    detailed = _read_answers_detailed(binary_img)
    return _score_from_detailed(detailed, scheme)


def scan_score_and_annotate(image_bytes: bytes, scheme: dict):
    """
    Sama seperti scan_and_score(), tetapi turut menjana gambar bertanda
    (hijau = betul, merah = salah, kuning = kosong/jawapan berganda) SEBAGAI
    BAIT PNG DALAM MEMORI - tiada fail ditulis ke cakera.

    Pulangkan: (result_dict, annotated_png_bytes)
    """
    img = _decode_image(image_bytes)
    id_to_center = _detect_markers(img)
    warped = _warp_to_canonical(img, id_to_center)
    binary_img = _binarize(warped)
    detailed = _read_answers_detailed(binary_img)
    result = _score_from_detailed(detailed, scheme)

    annotated = _annotate(warped, detailed, scheme)
    success, buf = cv2.imencode(".png", annotated)
    if not success:
        raise OMRScanError("Gagal menjana gambar bertanda.")

    return result, buf.tobytes()
