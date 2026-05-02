from flask import Flask, request, jsonify
from flask_cors import CORS
import face_recognition
import os
import base64
import numpy as np
from PIL import Image
import io
from datetime import datetime, timedelta
from pymongo import MongoClient
import pickle

# ---------------- APP SETUP ----------------
app = Flask(__name__)
CORS(app)

# ---------------- MONGODB ----------------
client = MongoClient("mongodb+srv://malay07_db_user:Malay07%40@prproject.h4mjvbl.mongodb.net/?retryWrites=true&w=majority")
db = client["main_gate_entry_exit_system"]

students_collection = db["students"]
entry_exit_collection = db["entry_exit_logs"]

# ---------------- PATHS ----------------
DATASET_PATH = "face_data"
ENCODINGS_FILE = "encodings.pkl"

# ======================================================
# LOAD OR TRAIN ENCODINGS
# ======================================================
def train_faces():
    encodings = []
    ids = []

    for roll_no in os.listdir(DATASET_PATH):
        person_dir = os.path.join(DATASET_PATH, roll_no)

        if not os.path.isdir(person_dir):
            continue

        for img in os.listdir(person_dir):
            if not img.lower().endswith((".jpg", ".jpeg", ".png")):
                continue

            img_path = os.path.join(person_dir, img)

            try:
                image = face_recognition.load_image_file(img_path)
                face_enc = face_recognition.face_encodings(image)

                if len(face_enc) == 1:
                    encodings.append(face_enc[0])
                    ids.append(roll_no)

            except Exception as e:
                print(f"Error in {img_path}: {e}")

    with open(ENCODINGS_FILE, "wb") as f:
        pickle.dump({"encodings": encodings, "ids": ids}, f)

    return encodings, ids


def load_encodings():
    if os.path.exists(ENCODINGS_FILE):
        with open(ENCODINGS_FILE, "rb") as f:
            data = pickle.load(f)
            return data["encodings"], data["ids"]
    else:
        return train_faces()


known_face_encodings, known_face_ids = load_encodings()

# ======================================================
# FACE RECOGNITION API
# ======================================================
@app.route("/api/recognize-face", methods=["POST"])
def recognize_face():
    data = request.get_json(silent=True)

    if not data or "image" not in data:
        return jsonify({"status": "ERROR", "message": "No image received"}), 400

    try:
        image_np = np.array(
            Image.open(io.BytesIO(base64.b64decode(data["image"]))).convert("RGB")
        )
    except:
        return jsonify({"status": "ERROR", "message": "Invalid image"}), 400

    face_locations = face_recognition.face_locations(image_np)

    if len(face_locations) == 0:
        return jsonify({"status": "DENIED", "message": "No face detected"})

    if len(face_locations) > 1:
        return jsonify({"status": "DENIED", "message": "Multiple faces not allowed"})

    encodings = face_recognition.face_encodings(image_np, face_locations)

    if not encodings:
        return jsonify({"status": "DENIED", "message": "Face not clear"})

    face_distances = face_recognition.face_distance(
        known_face_encodings,
        encodings[0]
    )

    best_match_index = np.argmin(face_distances)

    if face_distances[best_match_index] > 0.45:
        return jsonify({"status": "DENIED", "message": "Unknown person"})

    roll_no = known_face_ids[best_match_index]

    student = students_collection.find_one(
        {"roll_no": roll_no},
        {"_id": 0, "password": 0}
    )

    if not student:
        return jsonify({"status": "ERROR", "message": "Student not found"})

    last_log = entry_exit_collection.find_one(
        {"roll": roll_no},
        sort=[("outTime", -1)]
    )

    now = datetime.now()
    last_action_time = None

    if last_log and last_log.get("inTime") is None:
        action = "ENTRY"
        last_action_time = datetime.strptime(
            last_log["outTime"], "%Y-%m-%d %H:%M:%S"
        )
    else:
        action = "EXIT"
        if last_log and last_log.get("inTime"):
            last_action_time = datetime.strptime(
                last_log["inTime"], "%Y-%m-%d %H:%M:%S"
            )

    if last_action_time and now - last_action_time < timedelta(minutes=1):
        return jsonify({
            "status": "BLOCKED",
            "message": "Wait 1 minute before next action"
        })

    return jsonify({
        "status": "SUCCESS",
        "action": action,
        "student": student
    })


# ======================================================
# RUN LOCAL SERVER
# ======================================================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)