import cv2
import easyocr
import numpy as np
import datetime
import threading
import re

from db import save_plate

reader = easyocr.Reader(['en'], gpu=False)

camera = None
camera_lock = threading.Lock()
detection_active = False
last_detected = {}
DEBOUNCE_SECONDS = 5


def preprocess_for_ocr(region):
    gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_LINEAR)
    gray = cv2.bilateralFilter(gray, 11, 17, 17)
    _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return th


def clean_plate_text(text: str) -> str:
    return re.sub(r'[^A-Z0-9]', '', text.upper())


def detect_plates(frame):
    cascade_path = cv2.data.haarcascades + "haarcascade_russian_plate_number.xml"
    cascade = cv2.CascadeClassifier(cascade_path)

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    plates = cascade.detectMultiScale(gray, 1.1, 5, minSize=(60, 20))

    results = []

    for (x, y, w, h) in plates:
        roi = frame[y:y+h, x:x+w]
        proc = preprocess_for_ocr(roi)
        ocr_out = reader.readtext(proc)

        for (_, text, conf) in ocr_out:
            cleaned = clean_plate_text(text)
            if len(cleaned) >= 4 and conf > 0.3:
                results.append((cleaned, round(conf, 3)))

                cv2.rectangle(frame, (x, y), (x+w, y+h), (0,255,0), 2)
                cv2.putText(frame, f"{cleaned} ({conf:.0%})",
                            (x, y-8), cv2.FONT_HERSHEY_SIMPLEX,
                            0.7, (0,255,0), 2)

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

        _, buffer = cv2.imencode(".jpg", annotated)
        yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" +
               buffer.tobytes() + b"\r\n")

    release_camera()