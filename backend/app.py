from flask import Flask, Response, jsonify, request
from flask_cors import CORS
import cv2
import numpy as np
import easyocr
import sqlite3
import threading
import base64
import datetime
import os
import re

app = Flask(__name__)
CORS(app)

# ─── OCR Reader (loaded once) ────────────────────────────────────────────────
reader = easyocr.Reader(['en'], gpu=False)

# ─── Camera state ─────────────────────────────────────────────────────────────
camera = None
camera_lock = threading.Lock()
detection_active = False
last_detected = {}          # plate_text -> last seen timestamp (debounce)
DEBOUNCE_SECONDS = 5        # don't re-save same plate within 5 s

# ─── Database ─────────────────────────────────────────────────────────────────
DB_PATH = os.path.join(os.path.dirname(__file__), "plates.db")

def init_db():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS detections (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            plate     TEXT    NOT NULL,
            timestamp TEXT    NOT NULL,
            confidence REAL   DEFAULT 0
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

# ─── Plate detection helpers ───────────────────────────────────────────────────
def preprocess_for_ocr(region):
    gray  = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
    gray  = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_LINEAR)
    gray  = cv2.bilateralFilter(gray, 11, 17, 17)
    _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return th

def clean_plate_text(text: str) -> str:
    text = re.sub(r'[^A-Z0-9]', '', text.upper())
    return text

def detect_plates(frame):
    """
    Returns (annotated_frame, list_of_plate_texts_with_confidence)
    Uses a Haar cascade for plate localisation + EasyOCR for reading.
    """
    cascade_path = cv2.data.haarcascades + "haarcascade_russian_plate_number.xml"
    cascade = cv2.CascadeClassifier(cascade_path)

    gray   = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    plates = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 20))

    results = []
    for (x, y, w, h) in plates:
        roi      = frame[y:y+h, x:x+w]
        proc     = preprocess_for_ocr(roi)
        ocr_out  = reader.readtext(proc)

        for (_, text, conf) in ocr_out:
            cleaned = clean_plate_text(text)
            if len(cleaned) >= 4 and conf > 0.3:
                results.append((cleaned, round(conf, 3)))
                # Draw on frame
                cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
                cv2.putText(
                    frame, f"{cleaned} ({conf:.0%})",
                    (x, y - 8), cv2.FONT_HERSHEY_SIMPLEX,
                    0.7, (0, 255, 0), 2
                )
    return frame, results


def get_camera():
    global camera
    with camera_lock:
        if camera is None or not camera.isOpened():
            camera = cv2.VideoCapture(0)
            camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        return camera


def release_camera():
    global camera
    with camera_lock:
        if camera and camera.isOpened():
            camera.release()
            camera = None


# ─── MJPEG streaming generator ────────────────────────────────────────────────
def generate_frames():
    global last_detected, detection_active
    cam = get_camera()

    while detection_active:
        success, frame = cam.read()
        if not success:
            break

        annotated, plate_results = detect_plates(frame.copy())

        for (plate, conf) in plate_results:
            now = datetime.datetime.now().timestamp()
            last_time = last_detected.get(plate, 0)
            if now - last_time > DEBOUNCE_SECONDS:
                save_plate(plate, conf)
                last_detected[plate] = now

        _, buffer = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 80])
        frame_bytes = buffer.tobytes()
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n"
            + frame_bytes
            + b"\r\n"
        )

    release_camera()


# ─── Routes ───────────────────────────────────────────────────────────────────
@app.route("/api/stream")
def stream():
    global detection_active
    detection_active = True
    return Response(
        generate_frames(),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )

@app.route("/api/stop", methods=["POST"])
def stop_stream():
    global detection_active
    detection_active = False
    return jsonify({"status": "stopped"})

@app.route("/api/detections", methods=["GET"])
def detections():
    limit = request.args.get("limit", 100, type=int)
    return jsonify(get_all_plates(limit))

@app.route("/api/detections/<int:plate_id>", methods=["DELETE"])
def delete_detection(plate_id):
    delete_plate(plate_id)
    return jsonify({"status": "deleted", "id": plate_id})

@app.route("/api/detections", methods=["DELETE"])
def clear_all():
    con = sqlite3.connect(DB_PATH)
    con.execute("DELETE FROM detections")
    con.commit()
    con.close()
    return jsonify({"status": "cleared"})

@app.route("/api/stats", methods=["GET"])
def stats():
    con = sqlite3.connect(DB_PATH)
    total   = con.execute("SELECT COUNT(*) FROM detections").fetchone()[0]
    today   = con.execute(
        "SELECT COUNT(*) FROM detections WHERE timestamp LIKE ?",
        (datetime.date.today().isoformat() + "%",)
    ).fetchone()[0]
    unique  = con.execute("SELECT COUNT(DISTINCT plate) FROM detections").fetchone()[0]
    con.close()
    return jsonify({"total": total, "today": today, "unique": unique})

@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    init_db()
    app.run(debug=True, host="0.0.0.0", port=5000, threaded=True)
