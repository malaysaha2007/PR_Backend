from flask import Flask, request, jsonify
from datetime import datetime
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

@app.route('/')
def home():
    return "Backend is running"



# ---------------- MONGODB ----------------
client = MongoClient("mongodb+srv://malay07_db_user:Malay07%40@prproject.h4mjvbl.mongodb.net/?retryWrites=true&w=majority")
db = client["main_gate_entry_exit_system"]

students_collection = db["students"]
entry_exit_collection = db["entry_exit_logs"]

# ---------------- PATHS ----------------
DATASET_PATH = "face_data"
ENCODINGS_FILE = "encodings.pkl"

known_face_encodings = []
known_face_ids = []

# ======================================================
# LOAD OR TRAIN ENCODINGS
# ======================================================
def train_faces():
    encodings = []
    ids = []

    print("Training faces...")

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

    # Save encodings
    with open(ENCODINGS_FILE, "wb") as f:
        pickle.dump({"encodings": encodings, "ids": ids}, f)

    print("Training completed and saved")

    return encodings, ids


def load_encodings():
    if not os.path.exists(ENCODINGS_FILE):
        raise Exception("encodings.pkl missing. Generate locally first.")

    with open(ENCODINGS_FILE, "rb") as f:
        data = pickle.load(f)
        print("Encodings loaded successfully")
        return data["encodings"], data["ids"]


# Load encodings
known_face_encodings, known_face_ids = load_encodings()

# ======================================================
# HELPER FUNCTION
# ======================================================
def extract_student_phone(student):
    contact = student.get("contact")

    if isinstance(contact, dict):
        return contact.get("student")

    return contact

# ======================================================
# FACE RECOGNITION API
# ======================================================
@app.route("/api/recognize-face", methods=["POST"])
def recognize_face():
    data = request.get_json(silent=True)

    if not data or "image" not in data:
        return jsonify({"status": "ERROR", "message": "No image received"}), 400

    # Decode image
    try:
        image_np = np.array(
            Image.open(io.BytesIO(base64.b64decode(data["image"]))).convert("RGB")
        )
    except:
        return jsonify({"status": "ERROR", "message": "Invalid image"}), 400

    # Check face exists
    face_locations = face_recognition.face_locations(image_np)

    if len(face_locations) == 0:
        return jsonify({"status": "DENIED", "message": "No face detected"})

    if len(face_locations) > 1:
        return jsonify({"status": "DENIED", "message": "Multiple faces not allowed"})

    # Get encoding
    encodings = face_recognition.face_encodings(image_np, face_locations)

    if not encodings:
        return jsonify({"status": "DENIED", "message": "Face not clear"})

    # Find best match
    face_distances = face_recognition.face_distance(
        known_face_encodings,
        encodings[0]
    )

    best_match_index = np.argmin(face_distances)

    if face_distances[best_match_index] > 0.45:
        return jsonify({"status": "DENIED", "message": "Unknown person"})

    roll_no = known_face_ids[best_match_index]

    # Fetch student
    student = students_collection.find_one(
        {"roll_no": roll_no},
        {"_id": 0, "password": 0}
    )

    if not student:
        return jsonify({"status": "ERROR", "message": "Student not found"})

    # ---------------- ENTRY / EXIT LOGIC ----------------
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

    response = {
        "status": "SUCCESS",
        "action": action,
        "student": student
    }

    if action == "ENTRY" and last_log:
        response["last_exit"] = {
            "purpose": last_log.get("purpose"),
            "outTime": last_log.get("outTime")
        }

    return jsonify(response)

# ======================================================
# CONFIRM ENTRY / EXIT
# ======================================================
@app.route("/api/confirm-entry-exit", methods=["POST"])
def confirm_entry_exit():
    data = request.get_json(silent=True)

    if not data:
        return jsonify({"status": "ERROR", "message": "Invalid request"}), 400

    student = data.get("student")
    action = data.get("action")
    purpose = data.get("purpose")

from datetime import datetime, timedelta

current_time = (datetime.utcnow() + timedelta(hours=5, minutes=30)) \
    .strftime("%Y-%m-%d %H:%M:%S")
    
    
    # ---------------- EXIT ----------------
    if action == "EXIT":
        student_phone = extract_student_phone(student)

        entry_exit_collection.insert_one({
            "name": student["name"],
            "roll": student["roll_no"],
            "email": student.get("email"),
            "phone": student_phone,
            "branch": student.get("branch"),
            "degree": student.get("degree"),
            "hostel": student.get("hostel"),
            "room": student.get("room"),
            "purpose": purpose,
            "outTime": current_time,
            "inTime": None
        })

        return jsonify({
            "status": "OK",
            "action": "EXIT",
            "outTime": current_time
        })

    # ---------------- ENTRY ----------------
    entry_exit_collection.update_one(
        {"roll": student["roll_no"], "inTime": None},
        {"$set": {"inTime": current_time}}
    )

    return jsonify({
        "status": "OK",
        "action": "ENTRY",
        "inTime": current_time
    })

# ======================================================
# RUN SERVER
# ======================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
    
    