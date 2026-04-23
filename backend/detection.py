import cv2
import easyocr
import datetime
import threading
import re
import time

from db import save_plate

# ─── INIT ─────────────────────────────────────────────
reader = easyocr.Reader(['en'], gpu=False)

CASCADE_PATH = "/home/raajvir/Desktop/License_Plate_Detection_using_gstreamer/backend/opencv/data/haarcascades/haarcascade_russian_plate_number.xml"
cascade = cv2.CascadeClassifier(CASCADE_PATH)

if cascade.empty():
    print("❌ Cascade not loaded")
else:
    print("✅ Cascade loaded")

camera = None
camera_lock = threading.Lock()
last_detected = {}
DEBOUNCE_SECONDS = 5
frame_count = 0

# ─── GSTREAMER PIPELINE ───────────────────────────────
GSTREAMER_PIPELINE = (
    "v4l2src device=/dev/video0 ! "
    "video/x-raw,format=YUY2,width=640,height=480,framerate=30/1 ! "
    "videoconvert ! "
    "appsink drop=true max-buffers=1 sync=false"
)

# ─── HELPERS ──────────────────────────────────────────
def preprocess_for_ocr(region):
    gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=2, fy=2)
    gray = cv2.bilateralFilter(gray, 11, 17, 17)
    _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return th


def clean_plate_text(text):
    return re.sub(r'[^A-Z0-9]', '', text.upper())


# ─── DETECTION ────────────────────────────────────────
def detect_plates(frame):
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
                cv2.putText(frame, cleaned,
                            (x, y-8),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.7, (0,255,0), 2)

    return frame, results


# ─── CAMERA ───────────────────────────────────────────
def get_camera():
    global camera

    with camera_lock:
        if camera is None or not camera.isOpened():
            print("🎥 Starting camera...")

            camera = cv2.VideoCapture(GSTREAMER_PIPELINE, cv2.CAP_GSTREAMER)

            if not camera.isOpened():
                print("❌ GStreamer failed, falling back to default camera")
                camera = cv2.VideoCapture(0)

            if camera.isOpened():
                print("✅ Camera started")

        return camera


def release_camera():
    global camera

    with camera_lock:
        if camera and camera.isOpened():
            print("🛑 Releasing camera")
            camera.release()
            camera = None


# ─── STREAM ───────────────────────────────────────────
def generate_frames():
    global frame_count, last_detected

    cam = get_camera()
        # warm-up camera
    for _ in range(5):
        cam.read()

    print("🟢 Stream started")

    if cam is None or not cam.isOpened():
        print("❌ No camera available")
        return

    print("🟢 Stream started")

    try:
        while True:
            success, frame = cam.read()

            if not success:
                print("⚠️ Frame read failed")
                continue

            frame = cv2.resize(frame, (640, 360))
            frame_count += 1

            # Run OCR every 5 frames
            if frame_count % 5 == 0:
                annotated, results = detect_plates(frame)
            else:
                annotated = frame
                results = []

            # Save results
            for (plate, conf) in results:
                now = datetime.datetime.now().timestamp()
                last_time = last_detected.get(plate, 0)

                if now - last_time > DEBOUNCE_SECONDS:
                    save_plate(plate, conf)
                    last_detected[plate] = now

            # Prevent browser freeze
            annotated[0, 0, 0] = (annotated[0, 0, 0] + 1) % 255

            ret, buffer = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 60])
            if not ret:
                continue

            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n"
                b"Content-Length: " + str(len(buffer)).encode() + b"\r\n\r\n" +
                buffer.tobytes() +
                b"\r\n"
            )

            time.sleep(0.03)

    except GeneratorExit:
        print("⚠️ Client disconnected")

    finally:
        release_camera()
        print("🛑 Camera released")