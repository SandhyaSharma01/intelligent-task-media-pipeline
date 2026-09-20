from flask import Flask, request, jsonify, render_template
import os
import sqlite3
from PIL import Image
from pypdf import PdfReader

app = Flask(__name__)

def get_db_connection():
    conn = sqlite3.connect("tasks.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()

    conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                priority TEXT,
                status TEXT, 
                media_filename TEXT,
                media_type TEXT, 
                processing_result TEXT
                )
""")

    conn.commit()
    conn.close()
 
UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

tasks=[]

#---HOME---
@app.route("/")
def home():
    return render_template("index.html")

#---GET ALL TASKS---
@app.route("/tasks", methods=["GET"])
def get_tasks():
    conn = get_db_connection()

    tasks = conn.execute(
        "SELECT * FROM tasks"
    ).fetchall()

    conn.close()

    return jsonify([dict(task) for task in tasks])

#---CREATE TASKS---
@app.route("/tasks", methods = ["POST"])
def create_task():
    data = request.get_json()
    conn = get_db_connection()
    
    cursor = conn.execute("""
               INSERT INTO tasks (title, description, priority, status)
               VALUES(?, ?, ?, ?)
""", (
    data["title"],
    data["description"],
    data["priority"],
    "PENDING"
)
)

    conn.commit()
    task_id = cursor.lastrowid
    conn.close()

    return jsonify({
        "id" : task_id,
        "title" : data["title"],
        "description" : data["description"],
        "priority" : data["priority"],
        "status" : "PENDING"
    }),201

#---UPDATE TASK---
@app.route("/tasks/<int:task_id>", methods=["PUT"])
def update_task(task_id):
    data = request.get_json()

    conn = get_db_connection()

    task = conn.execute(
        "SELECT * FROM tasks WHERE id = ?",
        (task_id,)
    ).fetchone()

    if task is None:
        conn.close()
        return jsonify({
            "error": "Task not found"
        }), 404

    conn.execute("""
        UPDATE tasks
        SET title = ?,
            description = ?,
            priority = ?,
            status = ?
        WHERE id = ?
    """, (
        data.get("title", task["title"]),
        data.get("description", task["description"]),
        data.get("priority", task["priority"]),
        data.get("status", task["status"]),
        task_id
    ))

    conn.commit()

    updated_task = conn.execute(
        "SELECT * FROM tasks WHERE id = ?",
        (task_id,)
    ).fetchone()

    conn.close()

    return jsonify(dict(updated_task)),200
    

#---DELETE TASK---
@app.route("/tasks/<int:task_id>", methods=["DELETE"])
def delete_task(task_id):
    conn = get_db_connection()

    task = conn.execute(
        "SELECT * FROM tasks WHERE id = ?",
        (task_id,)
    ).fetchone()

    if task is None:
        conn.close()
        return jsonify({
            "error": "Task not found"
        }), 404

    conn.execute(
        "DELETE FROM tasks WHERE id = ?",
        (task_id,)
    )

    conn.commit()
    conn.close()

    return jsonify({
        "message": "Task deleted successfully",
        "task_id": task_id
    }),200

def get_media_type(filename):
    extension = os.path.splitext(filename)[1].lower()

    if extension in[".jpg", ".jpeg", ".png", ".gif"]:
        return "image"

    elif extension == ".pdf":
        return "pdf"

    elif extension in[".txt", ".csv"]:
        return "text"

    else:
        return "unknown"

def process_media(filename, media_type):

    if media_type == "text":
        with open(filename,"r") as file:
            content = file.read()
        return{
            "message" : "Text processed successfully",
            "characters" : len(content),
            "words" : len(content.split())
        }

    elif media_type == "image":
        image = Image.open(filename)
        width, height = image.size
        return {
        "message" : "Image processed successfully",
        "width" : width,
        "height" : height
        }
    elif media_type == "pdf":
        pdf = PdfReader(filename)
        page_count = len(pdf.pages)
        text = ""
        for page in pdf.image:
            text += page.extract_text() or ""
        return{
         "message" : "PDF processed successfully",
         "pages" : page_count,
         "text" : text
        }

    else:
        return "Unkown media type"
    

@app.route("/tasks/<int:task_id>/upload", methods=["POST"])
def upload_media(task_id):
    # 1. Find the task in the SQL database
    conn = get_db_connection()

    task = conn.execute(
        "SELECT * FROM tasks WHERE id = ?",
        (task_id,)
    ).fetchone()

    if task is None:
        conn.close()
        return jsonify({
            "error": "Task not found"
        }), 404

    # 2. Check whether a file was sent
    if "file" not in request.files:
        conn.close()
        return jsonify({
            "error": "No file provided"
        }), 400

    file = request.files["file"]

    # 3. Check whether a file was selected
    if file.filename == "":
        conn.close()
        return jsonify({
            "error": "No file selected"
        }), 400

    # 4. Create the file path
    file_path = os.path.join(
        app.config["UPLOAD_FOLDER"],
        file.filename
    )

    # 5. Save the file
    file.save(file_path)

    # 6. Find the type of media
    media_type = get_media_type(file.filename)

    # 7. Process the file
    processing_result = process_media(
        file_path,
        media_type
    )

    # 8. Save the uploaded-file information in the task
    conn.execute("""
        UPDATE tasks
        SET media_filename = ?,
            media_type = ?,
            processing_result = ?
        WHERE id = ?
    """, (
        file.filename,
        media_type,
        str(processing_result),
        task_id
    ))

    conn.commit()
    conn.close()

    # 9. Return the result
    return jsonify({
        "message": "File uploaded successfully",
        "task_id": task_id,
        "filename": file.filename,
        "media_type": media_type,
        "processing": processing_result
    }), 201


if __name__ == "__main__":
    init_db()
    app.run(debug=True)