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
import cloudinary
import cloudinary.uploader

cloudinary.config(
    cloud_name="dbrjgcpkz",
    api_key="179582722719283",
    api_secret="hjyQQlHCtNXjO-kaXAfaE5XSD_I"
)

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

    # Face detection
    face_locations = face_recognition.face_locations(image_np)

    if len(face_locations) == 0:
        return jsonify({"status": "DENIED", "message": "No face detected"})

    if len(face_locations) > 1:
        return jsonify({"status": "DENIED", "message": "Multiple faces not allowed"})

    encodings = face_recognition.face_encodings(image_np, face_locations)

    if not encodings:
        return jsonify({"status": "DENIED", "message": "Face not clear"})
    
    

        # ---------------- MATCH FACE USING DB ----------------
    students = list(students_collection.find({}, {"_id": 0}))

    best_match = None
    min_distance = 1.0

    for s in students:
        db_encoding = np.array(s.get("encoding", []))

        if len(db_encoding) == 0:
            continue

        dist = face_recognition.face_distance([db_encoding], encodings[0])[0]

        if dist < min_distance:
            min_distance = dist
            best_match = s

    # Check match
    if not best_match or min_distance > 0.45:
        return jsonify({"status": "DENIED", "message": "Unknown person"})

    roll_no = best_match["roll_no"]
    student = best_match

   

    if not student:
        return jsonify({"status": "ERROR", "message": "Student not found"})

    # ---------------- ENTRY / EXIT LOGIC ----------------
    last_log = entry_exit_collection.find_one(
        {"roll": roll_no},
        sort=[("_id", -1)]   # ✅ FIX: latest record
    )

    # ✅ IST current time
    now = datetime.utcnow() + timedelta(hours=5, minutes=30)

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

    # ✅ cooldown check
    if last_action_time and (now - last_action_time).total_seconds() < 60:
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

    current_time = (datetime.utcnow() + timedelta(hours=5, minutes=30)) \
        .strftime("%Y-%m-%d %H:%M:%S")

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
# ADD STUDENT (CLOUDINARY + MONGODB)
# ======================================================
@app.route("/api/add-student", methods=["POST"])
def add_student():
    data = request.get_json()

    name = data.get("name")
    roll_no = data.get("roll_no")
    image_base64 = data.get("image")

    if not name or not roll_no or not image_base64:
        return jsonify({"status": "ERROR", "message": "Missing data"}), 400

    try:
        # Decode image
        image_bytes = base64.b64decode(image_base64)

        # Upload to Cloudinary
        upload_result = cloudinary.uploader.upload(
            io.BytesIO(image_bytes),
            folder="students",
            public_id=roll_no
        )

        image_url = upload_result["secure_url"]

        # Convert image → numpy
        image_np = np.array(
            Image.open(io.BytesIO(image_bytes)).convert("RGB")
        )

        # Generate encoding
        encodings = face_recognition.face_encodings(image_np)

        if len(encodings) != 1:
            return jsonify({
                "status": "ERROR",
                "message": "Face not clear or multiple faces"
            })

        # Save in MongoDB (YOUR STRUCTURE)
        students_collection.insert_one({
            "name": name,
            "roll_no": roll_no,
            "branch": data.get("branch"),
            "degree": data.get("degree"),
            "hostel": data.get("hostel"),
            "room": data.get("room"),

            "contact": {
                "student": data.get("student_phone"),
                "parent": data.get("parent_phone")
            },

            "email": data.get("email"),
            "password": roll_no,

            # ✅ NEW
            "image_url": image_url,
            "encoding": encodings[0].tolist(),

            # ✅ REQUIRED FORMAT
            "created_at": datetime.now().strftime("%Y-%M-%D %H:%M:%S"),

        })

        return jsonify({
            "status": "SUCCESS",
            "message": "Student added successfully"
        })

    except Exception as e:
        return jsonify({"status": "ERROR", "message": str(e)})
    
    
    

# ======================================================
# RUN SERVER
# ======================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)