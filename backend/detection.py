import cv2
import easyocr
import datetime
import threading
import re
import time
import numpy as np
import onnxruntime as ort

from db import save_plate

# ─── INIT ─────────────────────────────────────────────
reader = easyocr.Reader(['en'], gpu=False)

# Smart provider selection (GPU if available)
providers = ort.get_available_providers()
if "CUDAExecutionProvider" in providers:
    print("🚀 Using GPU")
    session = ort.InferenceSession("./model/best.onnx", providers=["CUDAExecutionProvider"])
else:
    print("🧠 Using CPU")
    session = ort.InferenceSession("./model/best.onnx", providers=["CPUExecutionProvider"])

input_name = session.get_inputs()[0].name

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


def preprocess_for_yolo(frame):
    img = cv2.resize(frame, (640, 640))
    img = img.astype("float32") / 255.0
    img = img.transpose(2, 0, 1)
    img = np.expand_dims(img, axis=0)
    return img


# ─── YOLO DETECTION ───────────────────────────────────
def detect_plates(frame):
    h, w, _ = frame.shape
    input_tensor = preprocess_for_yolo(frame)

    outputs = session.run(None, {input_name: input_tensor})
    preds = np.squeeze(outputs[0])

    # Normalize shape → (N,5)
    if len(preds.shape) == 2:
        if preds.shape[0] < preds.shape[1]:
            preds = preds.T

    boxes = []
    scores = []

    # Collect boxes
    for det in preds:
        if len(det) < 5:
            continue

        x, y, bw, bh, conf = det[:5]

        if conf < 0.4:
            continue

        x1 = int((x - bw / 2) * w / 640)
        y1 = int((y - bh / 2) * h / 640)
        x2 = int((x + bw / 2) * w / 640)
        y2 = int((y + bh / 2) * h / 640)

        boxes.append([x1, y1, x2 - x1, y2 - y1])
        scores.append(float(conf))

    results = []

    # ─── NMS (VERY IMPORTANT) ───
    if len(boxes) > 0:
        indices = cv2.dnn.NMSBoxes(boxes, scores, 0.4, 0.5)

        for i in indices:
            i = i[0] if isinstance(i, (list, tuple)) else i

            x, y, bw, bh = boxes[i]
            roi = frame[y:y+bh, x:x+bw]

            if roi.size == 0:
                continue

            proc = preprocess_for_ocr(roi)
            ocr_out = reader.readtext(proc)

            for (_, text, ocr_conf) in ocr_out:
                cleaned = clean_plate_text(text)

                if len(cleaned) >= 4 and ocr_conf > 0.3:
                    results.append((cleaned, round(ocr_conf, 3)))

                    cv2.rectangle(frame, (x, y), (x+bw, y+bh), (0,255,0), 2)
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
                print("❌ GStreamer failed, fallback to default camera")
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

    for _ in range(5):
        cam.read()

    print("🟢 Stream started")

    if cam is None or not cam.isOpened():
        print("❌ No camera available")
        return

    try:
        while True:
            success, frame = cam.read()

            if not success:
                continue

            frame = cv2.resize(frame, (640, 360))
            frame_count += 1

            try:
                # Run detection every 10 frames (latency control)
                if frame_count % 10 == 0:
                    annotated, results = detect_plates(frame)
                else:
                    annotated = frame
                    results = []

            except Exception as e:
                print("⚠️ Detection error:", e)
                annotated = frame
                results = []

            # debounce save
            for (plate, conf) in results:
                now = datetime.datetime.now().timestamp()
                last_time = last_detected.get(plate, 0)

                if now - last_time > DEBOUNCE_SECONDS:
                    save_plate(plate, conf)
                    last_detected[plate] = now

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
