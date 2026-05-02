from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime
from pymongo import MongoClient

# ---------------- APP SETUP ----------------
app = Flask(__name__)
CORS(app)

# ---------------- MONGODB ----------------
client = MongoClient("mongodb+srv://malay07_db_user:Malay07%40@prproject.h4mjvbl.mongodb.net/?retryWrites=true&w=majority")
db = client["main_gate_entry_exit_system"]

students_collection = db["students"]
entry_exit_collection = db["entry_exit_logs"]

# ======================================================
# HELPER FUNCTION
# ======================================================
def extract_student_phone(student):
    contact = student.get("contact")

    if isinstance(contact, dict):
        return contact.get("student")

    return contact

# ======================================================
# CONFIRM ENTRY / EXIT (ONLY THIS IN CLOUD)
# ======================================================
@app.route("/api/confirm-entry-exit", methods=["POST"])
def confirm_entry_exit():
    data = request.get_json(silent=True)

    if not data:
        return jsonify({"status": "ERROR", "message": "Invalid request"}), 400

    student = data.get("student")
    action = data.get("action")
    purpose = data.get("purpose")

    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

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
    import os
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))