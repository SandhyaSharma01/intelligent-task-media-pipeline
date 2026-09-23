from flask import (
    Flask,
    request,
    jsonify,
    render_template,
    send_from_directory
)

import os
import sqlite3
import json
import re

from datetime import datetime, timedelta

from werkzeug.utils import secure_filename

from PIL import Image
from pypdf import PdfReader
from gtts import gTTS
import whisper

app = Flask(__name__)

# Dashboard Route
@app.route("/")
def home():
  return render_template("index.html")
   

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

DATABASE = os.path.join(
    BASE_DIR,
    "tasks.db"
)

UPLOAD_FOLDER = os.path.join(
    BASE_DIR,
    "uploads"
)

AUDIO_FOLDER = os.path.join(
    BASE_DIR,
    "generated_audio"
)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["AUDIO_FOLDER"] = AUDIO_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024

os.makedirs(
    UPLOAD_FOLDER,
    exist_ok=True
)

os.makedirs(
    AUDIO_FOLDER,
    exist_ok=True
)

print("Loading Whisper model...")

whisper_model = whisper.load_model("tiny")

print("Whisper model loaded successfully.")

def get_db_connection():

    conn = sqlite3.connect(DATABASE)

    conn.row_factory = sqlite3.Row

    return conn

def init_db():

    conn = get_db_connection()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS tasks (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            title TEXT NOT NULL,

            description TEXT,

            priority TEXT DEFAULT 'medium',

            status TEXT DEFAULT 'pending',

            due_date TEXT,

            due_time TEXT,

            media_filename TEXT,

            media_type TEXT,

            processing_result TEXT,

            created_at TEXT NOT NULL,

            updated_at TEXT NOT NULL

        )
    """)

    conn.commit()

    conn.close()

def get_current_time():
      return datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

def row_to_dict(row):

    if row is None:
        return None

    data = dict(row)

    if data.get("processing_result"):

        try:

            data["processing_result"] = json.loads(
                data["processing_result"]
            )

        except Exception:

            pass

    return data

def extract_priority(text):

    text = text.lower()

    high_priority_words = [
        "urgent",
        "urgently",
        "important",
        "high priority",
        "asap",
        "as soon as possible"
    ]

    low_priority_words = [
        "low priority",
        "not urgent"
    ]

    if any(
        word in text
        for word in high_priority_words
    ):
        return "high"

    if any(
        word in text
        for word in low_priority_words
    ):
        return "low"

    return "medium"

def clean_task_title(text):

    title = text.strip()

    patterns = [

        r"^(i need to)\s+",

        r"^(i have to)\s+",

        r"^(i want to)\s+",

        r"^(i should)\s+",

        r"^(please)\s+",

        r"^(remind me to)\s+",

        r"^(don't forget to)\s+",

        r"^(can you remind me to)\s+"

    ]

    for pattern in patterns:

        title = re.sub(
            pattern,
            "",
            title,
            flags=re.IGNORECASE
        )

    priority_patterns = [

        r"\bwith high priority\b",

        r"\bwith low priority\b",

        r"\bhigh priority\b",

        r"\blow priority\b",

        r"\bvery urgent\b",

        r"\burgent\b",

        r"\bas soon as possible\b",

        r"\basap\b"

    ]

    for pattern in priority_patterns:

        title = re.sub(
            pattern,
            "",
            title,
            flags=re.IGNORECASE
        )

    date_patterns = [

        r"\bday after tomorrow\b",

        r"\btomorrow\b",

        r"\btoday\b",

        r"\btonight\b",

        r"\bthis evening\b",

        r"\bthis morning\b"

    ]

    for pattern in date_patterns:

        title = re.sub(
            pattern,
            "",
            title,
            flags=re.IGNORECASE
        )

    title = re.sub(
        r"\bat\s+\d{1,2}"
        r"(?::\d{2})?"
        r"\s*(?:am|pm)\b",
        "",
        title,
        flags=re.IGNORECASE
    )

    title = re.sub(
        r"\s+",
        " ",
        title
    )

    title = title.strip(
        " .,!?;"
    )

    if not title:
        title = text.strip()

    title = (
        title[0].upper()
        + title[1:]
    )

    return title

def extract_due_date(text):
    return None

def extract_due_time(text):
    return None

def extract_task_data(text):

    priority = extract_priority(text)

    due_date = extract_due_date(text)

    due_time = extract_due_time(text)

    title = clean_task_title(text)

    return {

        "title": title,

        "description": text.strip(),

        "priority": priority,

        "status": "pending",

        "due_date": due_date,

        "due_time": due_time

    }

# Save the Task to SQLite
def save_task(task_data):

    timestamp = get_current_time()

    conn = get_db_connection()

    cursor = conn.execute("""
        INSERT INTO tasks (
            title,
            description,
            priority,
            status,
            due_date,
            due_time,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        task_data["title"],
        task_data.get("description", ""),
        task_data.get("priority", "medium"),
        task_data.get("status", "pending"),
        task_data.get("due_date"),
        task_data.get("due_time"),
        timestamp,
        timestamp
    ))

    conn.commit()

    task_id = cursor.lastrowid

    row = conn.execute(
        "SELECT * FROM tasks WHERE id = ?",
        (task_id,)
    ).fetchone()

    conn.close()

    return row_to_dict(row)

@app.route("/api/tasks", methods=["GET"])
def get_tasks():

    conn = get_db_connection()

    tasks = conn.execute("""
        SELECT *
        FROM tasks
        ORDER BY id DESC
    """).fetchall()

    conn.close()

    return jsonify([
        row_to_dict(task)
        for task in tasks
    ]), 200

# Create a task
@app.route("/api/tasks", methods=["POST"])
def create_task():

    data = request.get_json(
        silent=True
    )

    if not data:

        return jsonify({
            "error": "JSON data is required"
        }), 400

    title = str(
        data.get("title", "")
    ).strip()

    if not title:

        return jsonify({
            "error": "Task title is required"
        }), 400

    task_data = {

        "title": title,

        "description": str(
            data.get(
                "description",
                ""
            )
        ).strip(),

        "priority": data.get(
            "priority",
            "medium"
        ),

        "status": data.get(
            "status",
            "pending"
        ),

        "due_date": data.get(
            "due_date"
        ),

        "due_time": data.get(
            "due_time"
        )
    }

    task = save_task(
        task_data
    )

    return jsonify({

        "message":
            "Task created successfully",

        "task":
            task

    }), 201

# Get one task
@app.route(
    "/api/tasks/<int:task_id>",
    methods=["GET"]
)
def get_single_task(task_id):

    conn = get_db_connection()

    task = conn.execute(
        """
        SELECT *
        FROM tasks
        WHERE id = ?
        """,
        (task_id,)
    ).fetchone()

    conn.close()

    if task is None:

        return jsonify({
            "error": "Task not found"
        }), 404

    return jsonify(
        row_to_dict(task)
    ), 200

# Update a task
@app.route(
    "/api/tasks/<int:task_id>",
    methods=["PUT"]
)
def update_task(task_id):

    data = request.get_json(
        silent=True
    )

    if not data:

        return jsonify({
            "error": "JSON data is required"
        }), 400

    conn = get_db_connection()

    existing = conn.execute(
        """
        SELECT *
        FROM tasks
        WHERE id = ?
        """,
        (task_id,)
    ).fetchone()

    if existing is None:

        conn.close()

        return jsonify({
            "error": "Task not found"
        }), 404

    conn.execute("""
        UPDATE tasks

        SET
            title = ?,
            description = ?,
            priority = ?,
            status = ?,
            due_date = ?,
            due_time = ?,
            updated_at = ?

        WHERE id = ?
    """, (

        data.get(
            "title",
            existing["title"]
        ),

        data.get(
            "description",
            existing["description"]
        ),

        data.get(
            "priority",
            existing["priority"]
        ),

        data.get(
            "status",
            existing["status"]
        ),

        data.get(
            "due_date",
            existing["due_date"]
        ),

        data.get(
            "due_time",
            existing["due_time"]
        ),

        get_current_time(),

        task_id
    ))

    conn.commit()

    updated = conn.execute(
        """
        SELECT *
        FROM tasks
        WHERE id = ?
        """,
        (task_id,)
    ).fetchone()

    conn.close()

    return jsonify({

        "message":
            "Task updated successfully",

        "task":
            row_to_dict(updated)

    }), 200

# Delete a task
@app.route(
    "/api/tasks/<int:task_id>",
    methods=["DELETE"]
)
def delete_task(task_id):

    conn = get_db_connection()

    existing = conn.execute(
        """
        SELECT *
        FROM tasks
        WHERE id = ?
        """,
        (task_id,)
    ).fetchone()

    if existing is None:

        conn.close()

        return jsonify({
            "error": "Task not found"
        }), 404

    conn.execute(
        """
        DELETE FROM tasks
        WHERE id = ?
        """,
        (task_id,)
    )

    conn.commit()

    conn.close()

    return jsonify({

        "message":
            "Task deleted successfully",

        "task_id":
            task_id

    }), 200

# Text -> Task
@app.route("/api/text-to-task", methods=["POST"])
def text_to_task():

    data = request.get_json(
        silent=True
    )

    if not data:

        return jsonify({
            "error": "JSON data is required"
        }), 400

    text = str(
        data.get("text", "")
    ).strip()

    if not text:

        return jsonify({
            "error": "Text cannot be empty"
        }), 400

    # Convert natural language
    # into structured task information
    extracted = extract_task_data(
        text
    )

    # Save the structured task
    # into SQLite
    task = save_task(
        extracted
    )

    return jsonify({

        "message":
            "Task created from text successfully",

        "extracted":
            extracted,

        "task":
            task

    }), 201

# Voice -> Task
@app.route("/api/audio-to-task", methods=["POST"])
def audio_to_task():

    if "audio" not in request.files:
        return jsonify({
            "error": "Audio file is required"
        }), 400

    audio_file = request.files["audio"]

    if not audio_file.filename:
        return jsonify({
            "error": "No audio file selected"
        }), 400

    filename = secure_filename(
        audio_file.filename
    )

    audio_path = os.path.join(
        UPLOAD_FOLDER,
        filename
    )

    audio_file.save(audio_path)

    try:

        # 1. Convert speech to text
        result = whisper_model.transcribe(
            audio_path
        )

        text = result.get(
            "text",
            ""
        ).strip()

        if not text:
            return jsonify({
                "error": "No speech detected"
            }), 400

        # 2. Convert the spoken text
        #    into structured task information
        extracted = extract_task_data(
            text
        )

        # 3. Save task in SQLite
        task = save_task(
            extracted
        )

        # 4. Store information about
        #    the original audio file
        conn = get_db_connection()

        conn.execute("""
            UPDATE tasks

            SET
                media_filename = ?,
                media_type = ?,
                updated_at = ?

            WHERE id = ?
        """, (
            filename,
            "audio",
            get_current_time(),
            task["id"]
        ))

        conn.commit()

        final_task = conn.execute(
            """
            SELECT *
            FROM tasks
            WHERE id = ?
            """,
            (task["id"],)
        ).fetchone()

        conn.close()

        return jsonify({

            "message":
                "Voice task created successfully",

            "transcription":
                text,

            "task":
                row_to_dict(final_task)

        }), 201

    except Exception as error:

        return jsonify({
            "error": str(error)
        }), 500

# Audio -> Text
@app.route("/api/audio-to-text", methods=["POST"])
def audio_to_text():

    # Check whether an audio file was uploaded
    if "audio" not in request.files:

        return jsonify({
            "error": "Audio file is required"
        }), 400

    audio_file = request.files["audio"]

    # Check whether the user actually selected a file
    if not audio_file.filename:

        return jsonify({
            "error": "No audio file selected"
        }), 400

    # Make the filename safe
    filename = secure_filename(
        audio_file.filename
    )

    # Create the complete file path
    audio_path = os.path.join(
        UPLOAD_FOLDER,
        filename
    )

    # Save the uploaded audio
    audio_file.save(
        audio_path
    )

    try:

        # Send the audio to Whisper
        result = whisper_model.transcribe(
            audio_path
        )

        # Extract the transcribed text
        text = result.get(
            "text",
            ""
        ).strip()

        # Make sure Whisper actually detected speech
        if not text:

            return jsonify({
                "error": "No speech detected"
            }), 400

        return jsonify({

            "message":
                "Audio converted to text successfully",

            "filename":
                filename,

            "text":
                text

        }), 200

    except Exception as error:

        return jsonify({

            "error":
                str(error)

        }), 500

# Text -> Audio
@app.route("/api/text-to-audio", methods=["POST"])
def text_to_audio():

    data = request.get_json(
        silent=True
    )

    if not data:
        return jsonify({
            "error": "JSON data is required"
        }), 400

    text = str(
        data.get("text", "")
    ).strip()

    if not text:
        return jsonify({
            "error": "Text cannot be empty"
        }), 400

    try:

        filename = (
            f"speech_"
            f"{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            f".mp3"
        )

        audio_path = os.path.join(
            AUDIO_FOLDER,
            filename
        )

        # Convert text into speech
        speech = gTTS(
            text=text,
            lang="en",
            slow=False
        )

        # Save the generated audio
        speech.save(audio_path)

        return jsonify({

            "message":
                "Text converted to audio successfully",

            "text":
                text,

            "filename":
                filename,

            "audio_url":
                f"/generated-audio/{filename}"

        }), 201

    except Exception as error:

        return jsonify({

            "error":
                str(error)

        }), 500

@app.route(
    "/generated-audio/<filename>",
    methods=["GET"]
)
def generated_audio(filename):

    return send_from_directory(
        AUDIO_FOLDER,
        filename
    )

# Detect the media type
def get_media_type(filename):

    extension = os.path.splitext(
        filename
    )[1].lower()

    if extension in [
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".webp"
    ]:
        return "image"

    if extension == ".pdf":
        return "pdf"

    if extension in [
        ".txt",
        ".csv"
    ]:
        return "text"

    if extension in [
        ".mp3",
        ".wav",
        ".m4a",
        ".ogg",
        ".webm"
    ]:
        return "audio"

    return "unknown"

# Process the upload file
def process_media(
    file_path,
    media_type
):

    if media_type == "image":

        image = Image.open(
            file_path
        )

        width, height = image.size

        return {
            "type": "image",
            "message":
                "Image processed successfully",
            "width": width,
            "height": height,
            "format": image.format
        }


    if media_type == "pdf":

        pdf = PdfReader(
            file_path
        )

        page_count = len(
            pdf.pages
        )

        extracted_text = ""

        for page in pdf.pages:

            extracted_text += (
                page.extract_text()
                or ""
            )

        return {
            "type": "pdf",
            "message":
                "PDF processed successfully",
            "pages": page_count,
            "text": extracted_text
        }


    if media_type == "text":

        with open(
            file_path,
            "r",
            encoding="utf-8",
            errors="ignore"
        ) as file:

            content = file.read()

        return {
            "type": "text",
            "message":
                "Text file processed successfully",
            "characters":
                len(content),
            "words":
                len(content.split()),
            "text":
                content
        }


    if media_type == "audio":

        result = whisper_model.transcribe(
            file_path
        )

        return {
            "type": "audio",
            "message":
                "Audio processed successfully",
            "text":
                result.get("text", "").strip()
        }


    return {
        "type": "unknown",
        "message":
            "Unsupported media type"
}

   # Media Processing
@app.route("/api/media-processing", methods=["POST"])
def media_processing():

    if "file" not in request.files:
        return jsonify({
            "error": "Media file is required"
        }), 400

    media_file = request.files["file"]

    if not media_file.filename:
        return jsonify({
            "error": "No media file selected"
        }), 400

    filename = secure_filename(
        media_file.filename
    )

    file_path = os.path.join(
        UPLOAD_FOLDER,
        filename
    )

    media_file.save(file_path)

    try:

        media_type = get_media_type(
            filename
        )

        if media_type == "unknown":
            return jsonify({
                "error": "Unsupported media type"
            }), 400

        result = process_media(
            file_path,
            media_type
        )

        return jsonify({
            "message": "Media processed successfully",
            "filename": filename,
            "result": result
        }), 200

    except Exception as error:

        return jsonify({
            "error": str(error)
        }), 500

if __name__ == "__main__":

    init_db()

    app.run(
        debug=True,
        host="127.0.0.1",
        port=5000
    )

