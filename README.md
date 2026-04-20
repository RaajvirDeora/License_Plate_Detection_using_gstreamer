# PlateWatch — License Number Plate Detection System

A full-stack LNP detection app:
- **Frontend**: React + Vite (dark UI)
- **Backend**: Flask + OpenCV + EasyOCR
- **Database**: SQLite (auto-created, no setup needed)
- **Input**: Live webcam feed (MJPEG streaming)

---

## Project Structure

```
lnp_project/
├── backend/
│   ├── app.py            ← Flask API + detection logic
│   ├── requirements.txt  ← Python dependencies
│   └── plates.db         ← SQLite DB (auto-created on first run)
└── frontend/
    ├── src/
    │   ├── App.jsx
    │   ├── index.css
    │   ├── main.jsx
    │   ├── components/
    │   │   └── Navbar.jsx
    │   └── pages/
    │       ├── Dashboard.jsx
    │       ├── LiveDetection.jsx
    │       └── History.jsx
    ├── index.html
    ├── package.json
    └── vite.config.js
```

---

## Setup Instructions

### 1. Backend (Python)

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate it
# On Windows:
venv\Scripts\activate
# On Mac/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the backend server
python app.py
```

The backend starts at: **http://localhost:5000**

> First run will download the EasyOCR English model (~90 MB). This is normal.

---

### 2. Frontend (React)

Open a second terminal:

```bash
cd frontend

# Install Node dependencies
npm install

# Run dev server
npm run dev
```

The frontend starts at: **http://localhost:3000**

---

## How It Works

### Detection Pipeline

1. Flask opens the webcam using OpenCV
2. Each frame is passed through a **Haar Cascade** classifier to find plate regions
3. The region is **preprocessed** (grayscale, bilateral filter, Otsu threshold)
4. **EasyOCR** reads the text from the region
5. Text is cleaned (only A-Z, 0-9 kept)
6. If confidence > 30% and plate ≥ 4 chars → **saved to SQLite**
7. Same plate is not re-saved for 5 seconds (debounce)
8. The annotated frame is streamed as **MJPEG** to the React frontend

### API Endpoints

| Method | URL | Description |
|--------|-----|-------------|
| GET | `/api/stream` | MJPEG webcam stream with detections |
| POST | `/api/stop` | Stop the stream and release camera |
| GET | `/api/detections?limit=N` | Get latest N detections |
| DELETE | `/api/detections/<id>` | Delete a single record |
| DELETE | `/api/detections` | Clear all records |
| GET | `/api/stats` | Total, today, unique plate counts |
| GET | `/api/health` | Backend health check |

### SQLite Schema

```sql
CREATE TABLE detections (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    plate      TEXT    NOT NULL,
    timestamp  TEXT    NOT NULL,
    confidence REAL    DEFAULT 0
);
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Camera not opening | Make sure no other app is using the webcam. Try changing `cv2.VideoCapture(0)` to `(1)` in `app.py` if you have multiple cameras. |
| EasyOCR model not downloading | Check your internet connection. The model downloads on first use. |
| CORS errors in browser | Make sure backend is running on port 5000. |
| No plates detected | Ensure good lighting, hold the plate steady, plate must be at least 60×20px in frame. |

---

## Improving Detection Accuracy

The Haar cascade works but isn't perfect. For better results you can:

1. **Replace with YOLOv8** (recommended):
   ```bash
   pip install ultralytics
   ```
   Then replace the `detect_plates()` function in `app.py` with a YOLOv8 inference call.

2. **Use a pre-trained WPOD-NET** model for warped plate correction.

3. **Improve OCR** by adding plate-specific regex patterns for your country's format.
