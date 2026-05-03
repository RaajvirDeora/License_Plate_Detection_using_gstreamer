import sqlite3
import datetime
import os
import re

DB_PATH = os.path.join(os.path.dirname(__file__), "plates.db")

# ─────────────────────────────────────────────
# NORMALIZATION (VERY IMPORTANT)
# ─────────────────────────────────────────────
def normalize_plate(text: str) -> str:
    if not text:
        return ""

    text = text.upper()
    text = re.sub(r'[^A-Z0-9]', '', text)  # remove spaces/symbols

    # Common OCR corrections
    text = text.replace('O', '0')
    text = text.replace('I', '1')
    text = text.replace('Z', '2')

    return text


# ─────────────────────────────────────────────
# RELAXED VALIDATION
# ─────────────────────────────────────────────
_PLATE_RE = re.compile(r'^[A-Z]{2}[0-9]{1,2}[A-Z]{1,3}[0-9]{3,4}$')

def is_valid_indian_plate(text: str) -> bool:
    return bool(_PLATE_RE.match(text))


# ─────────────────────────────────────────────
# OPTIONAL SCORING SYSTEM (BETTER THAN HARD FILTER)
# ─────────────────────────────────────────────
def plate_score(text: str) -> float:
    score = 0.0

    if re.match(r'^[A-Z]{2}', text):
        score += 0.3  # state code

    if re.search(r'[0-9]{1,2}', text):
        score += 0.2  # district code

    if re.search(r'[A-Z]{1,3}', text):
        score += 0.2  # series

    if re.search(r'[0-9]{3,4}$', text):
        score += 0.3  # number

    return score


# ─────────────────────────────────────────────
# DB INIT
# ─────────────────────────────────────────────
def init_db():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS detections (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            plate      TEXT    NOT NULL UNIQUE,
            timestamp  TEXT    NOT NULL,
            confidence REAL    DEFAULT 0,
            hit_count  INTEGER DEFAULT 1
        )
    """)

    con.commit()
    con.close()


# ─────────────────────────────────────────────
# SAVE PLATE (CORE LOGIC)
# ─────────────────────────────────────────────
def save_plate(raw_plate: str, confidence: float):
    """
    Insert or update plate.
    Uses normalization + relaxed validation + scoring.
    """

    plate = normalize_plate(raw_plate)

    if not plate:
        return

    # Scoring filter (adjust threshold if needed)
    score = plate_score(plate)

    if score < 0.6:
        print(f"❌ Rejected (low score {score:.2f}): {raw_plate} -> {plate}")
        return

    # Optional strict check (keep relaxed)
    if not is_valid_indian_plate(plate):
        print(f"⚠️ Weak format but accepted: {plate}")

    now = datetime.datetime.now().isoformat(sep=" ", timespec="seconds")

    con = sqlite3.connect(DB_PATH)

    try:
        con.execute(
            "INSERT INTO detections (plate, timestamp, confidence, hit_count) VALUES (?,?,?,1)",
            (plate, now, confidence)
        )
        con.commit()

    except sqlite3.IntegrityError:
        con.execute(
            """UPDATE detections
               SET timestamp  = ?,
                   confidence = MAX(confidence, ?),
                   hit_count  = hit_count + 1
               WHERE plate = ?""",
            (now, confidence, plate)
        )
        con.commit()

    finally:
        con.close()


# ─────────────────────────────────────────────
# FETCH DATA
# ─────────────────────────────────────────────
def get_all_plates(limit: int = 100):
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row

    rows = con.execute(
        "SELECT * FROM detections ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()

    con.close()
    return [dict(r) for r in rows]


def delete_plate(plate_id: int):
    con = sqlite3.connect(DB_PATH)
    con.execute("DELETE FROM detections WHERE id=?", (plate_id,))
    con.commit()
    con.close()


def search_plate(query: str):
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row

    query = normalize_plate(query)

    rows = con.execute(
        "SELECT * FROM detections WHERE plate LIKE ? ORDER BY timestamp DESC",
        (f"%{query}%",)
    ).fetchall()

    con.close()
    return [dict(r) for r in rows]