"""
class_manager.py
-------------------
Menguruskan KELAS (bukan gambar) bagi setiap chat Telegram. Setiap kelas ada:
  - skema jawapan sendiri
  - rekod "submissions" (jawapan yang dikesan bagi setiap gambar yang telah
    disemak untuk kelas itu) - digunakan untuk jana analisis A/B/C/D penuh

Disimpan dalam satu fail JSON kecil (class_store.json) supaya data tidak
hilang bila bot dimulakan semula.

PENTING: Hanya JAWAPAN YANG DIKESAN (huruf A/B/C/D/BLANK/MULTIPLE) disimpan
di sini untuk tujuan statistik - bukan gambar itu sendiri. Gambar sentiasa
diproses dalam memori sahaja (lihat bot.py / omr_scanner.py) dan tidak
pernah ditulis ke cakera.
"""

import json
import os
import uuid
from threading import Lock

import omr_layout as layout

STORE_PATH = os.path.join(os.path.dirname(__file__), "class_store.json")
_lock = Lock()

VALID_OPTIONS = set(layout.OPTIONS)  # {"A", "B", "C", "D"}
TOTAL_QUESTIONS = layout.TOTAL_QUESTIONS


def _load_store() -> dict:
    if not os.path.exists(STORE_PATH):
        return {}
    with open(STORE_PATH, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def _save_store(store: dict):
    with open(STORE_PATH, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Pengurusan kelas
# ---------------------------------------------------------------------------

def list_classes(chat_id: int):
    """Pulangkan senarai (class_id, nama_kelas) bagi chat ini, disusun mengikut nama."""
    with _lock:
        store = _load_store()
        chat_classes = store.get(str(chat_id), {})
        items = [(cid, data.get("name", cid)) for cid, data in chat_classes.items()]
        return sorted(items, key=lambda item: item[1].lower())


def class_name_exists(chat_id: int, name: str) -> bool:
    name_lower = name.strip().lower()
    return any(existing.lower() == name_lower for _, existing in list_classes(chat_id))


def add_class(chat_id: int, name: str) -> str:
    """Cipta kelas baharu, pulangkan class_id uniknya."""
    name = name.strip()
    if not name:
        raise ValueError("Nama kelas tidak boleh kosong.")
    if len(name) > 40:
        raise ValueError("Nama kelas terlalu panjang (maksimum 40 aksara).")
    if class_name_exists(chat_id, name):
        raise ValueError(f"Kelas '{name}' sudah wujud.")

    class_id = uuid.uuid4().hex[:8]
    with _lock:
        store = _load_store()
        chat_classes = store.setdefault(str(chat_id), {})
        chat_classes[class_id] = {"name": name, "scheme": None, "submissions": []}
        _save_store(store)
    return class_id


def delete_class(chat_id: int, class_id: str):
    with _lock:
        store = _load_store()
        chat_classes = store.get(str(chat_id), {})
        chat_classes.pop(class_id, None)
        _save_store(store)


def delete_all_classes(chat_id: int):
    """Padam SEMUA kelas (skema + rekod analisis) bagi chat ini. Tidak boleh diundur."""
    with _lock:
        store = _load_store()
        store.pop(str(chat_id), None)
        _save_store(store)


def get_class(chat_id: int, class_id: str) -> dict | None:
    with _lock:
        store = _load_store()
        return store.get(str(chat_id), {}).get(class_id)


def get_class_name(chat_id: int, class_id: str) -> str | None:
    data = get_class(chat_id, class_id)
    return data.get("name") if data else None


# ---------------------------------------------------------------------------
# Skema jawapan (per kelas)
# ---------------------------------------------------------------------------

def get_scheme(chat_id: int, class_id: str) -> dict | None:
    data = get_class(chat_id, class_id)
    if not data or not data.get("scheme"):
        return None
    return {int(k): v for k, v in data["scheme"].items()}


def set_scheme_from_string(chat_id: int, class_id: str, answer_string: str) -> dict:
    cleaned = answer_string.strip().upper().replace(" ", "")
    if len(cleaned) != TOTAL_QUESTIONS:
        raise ValueError(
            f"Skema mesti mengandungi tepat {TOTAL_QUESTIONS} huruf (contoh: ABCDABCDABCDABCDABCD). "
            f"Anda berikan {len(cleaned)} huruf."
        )
    invalid = [c for c in cleaned if c not in VALID_OPTIONS]
    if invalid:
        raise ValueError(
            f"Huruf tidak sah dijumpai: {set(invalid)}. Hanya {'/'.join(sorted(VALID_OPTIONS))} dibenarkan."
        )

    scheme = {i + 1: cleaned[i] for i in range(TOTAL_QUESTIONS)}
    with _lock:
        store = _load_store()
        chat_classes = store.setdefault(str(chat_id), {})
        if class_id not in chat_classes:
            raise ValueError("Kelas tidak dijumpai.")
        chat_classes[class_id]["scheme"] = {str(k): v for k, v in scheme.items()}
        _save_store(store)
    return scheme


def format_scheme(scheme: dict) -> str:
    lines = [f"{q}.{scheme.get(q, '-')}" for q in range(1, TOTAL_QUESTIONS + 1)]
    rows = ["  ".join(lines[i:i + 5]) for i in range(0, len(lines), 5)]
    return "\n".join(rows)


# ---------------------------------------------------------------------------
# Rekod submission & analisis A/B/C/D
# ---------------------------------------------------------------------------

def add_submission(chat_id: int, class_id: str, detected_answers: dict) -> int:
    """
    detected_answers: { nombor_soalan (int): 'A'/'B'/'C'/'D'/'BLANK'/'MULTIPLE' }
    Rekod satu set jawapan yang dikesan daripada satu gambar yang telah disemak.
    Pulangkan jumlah submission terkini bagi kelas ini (selepas ditambah).
    """
    with _lock:
        store = _load_store()
        chat_classes = store.setdefault(str(chat_id), {})
        if class_id not in chat_classes:
            raise ValueError("Kelas tidak dijumpai.")
        entry = {str(k): v for k, v in detected_answers.items()}
        chat_classes[class_id].setdefault("submissions", []).append(entry)
        _save_store(store)
        return len(chat_classes[class_id]["submissions"])


def get_analysis(chat_id: int, class_id: str) -> dict:
    """
    Pulangkan:
    {
        "total_submissions": int,
        "per_question": { q: {"A": n, "B": n, "C": n, "D": n, "BLANK": n, "MULTIPLE": n} }
    }
    """
    data = get_class(chat_id, class_id)
    submissions = data.get("submissions", []) if data else []

    categories = list(layout.OPTIONS) + ["BLANK", "MULTIPLE"]
    per_question = {q: {c: 0 for c in categories} for q in range(1, TOTAL_QUESTIONS + 1)}

    for sub in submissions:
        for q_str, ans in sub.items():
            q = int(q_str)
            if q in per_question and ans in per_question[q]:
                per_question[q][ans] += 1

    return {"total_submissions": len(submissions), "per_question": per_question}


def format_analysis(class_name: str, analysis: dict) -> str:
    total = analysis["total_submissions"]
    per_question = analysis["per_question"]

    lines = [f"📊 Analisis Penuh - Kelas {class_name}", f"Jumlah gambar disemak: {total}", ""]

    if total == 0:
        lines.append("Belum ada gambar disemak untuk kelas ini lagi. Guna 'Semak Jawapan' dahulu.")
        return "\n".join(lines)

    for q in range(1, TOTAL_QUESTIONS + 1):
        counts = per_question[q]
        parts = [f"{opt}={counts[opt]}" for opt in layout.OPTIONS]
        extra = []
        if counts["BLANK"]:
            extra.append(f"Kosong={counts['BLANK']}")
        if counts["MULTIPLE"]:
            extra.append(f"Berganda={counts['MULTIPLE']}")
        line = f"Soalan {q}: " + " ".join(parts)
        if extra:
            line += "  |  " + " ".join(extra)
        lines.append(line)

    return "\n".join(lines)