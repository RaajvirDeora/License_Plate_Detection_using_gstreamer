 import sqlite3
import datetime
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "plates.db")

def init_db():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS detections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plate TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            confidence REAL DEFAULT 0
        )
    """)
    con.commit()
    con.close()


def save_plate(plate: str, confidence: float):
    now = datetime.datetime.now().isoformat(sep=" ", timespec="seconds")
    con = sqlite3.connect(DB_PATH)
    con.execute(
        "INSERT INTO detections (plate, timestamp, confidence) VALUES (?,?,?)",
        (plate, now, confidence)
    )
    con.commit()
    con.close()


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