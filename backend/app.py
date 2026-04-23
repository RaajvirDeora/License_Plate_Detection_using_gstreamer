from flask import Flask, Response, jsonify, request
from flask_cors import CORS

from db import *
from detection import generate_frames, detection_active

import detection

app = Flask(__name__)
CORS(app)


@app.route("/api/stream")
def stream():
    detection.detection_active = True
    return Response(generate_frames(),
        mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/api/stop", methods=["POST"])
def stop_stream():
    detection.detection_active = False
    return jsonify({"status": "stopped"})


@app.route("/api/detections", methods=["GET"])
def detections():
    limit = request.args.get("limit", 100, type=int)
    return jsonify(get_all_plates(limit))


@app.route("/api/detections/<int:plate_id>", methods=["DELETE"])
def delete_detection(plate_id):
    delete_plate(plate_id)
    return jsonify({"status": "deleted"})


@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    init_db()
    app.run(debug=True)