# Intelligent Task & Media Processing Pipeline

 - A Flask-based project that combines task management with basic media processing.

## Features

- Task Management
- Create tasks
- View all tasks
- Update tasks
-  Delete tasks
- Set task priority
- Set task status
- Add due date

### Text Processing
 - Convert text input into structured task information
 - Create a task from natural-language text

### Voice Processing
 - Convert audio to text using Whisper
 - Create tasks from voice input
 - Convert text into speech using gTTS

### Media Processing
 - Upload and process images
 - Upload and process PDF files
 - Upload and process text files
 - Process audio files

## Technologies Used

- Python
 - Flask
 - SQLite
 - HTML
 - CSS
 - JavaScript
 - OpenAI Whisper
 - gTTS
 - Pillow
 - pypdf

## Project Structure

```text
intelligent-task-media-pipeline/
│
├── app.py
├── requirements.txt
├── README.md
│
├── templates/
│   └── index.html
│
└── .gitignore
```

## Installation
```bash
 - git clone https://github.com/SandhyaSharma01/intelligent-task-media-pipeline
 - cd intelligent-task-media-pipeline
 - pip install -r requirements.txt
 - python app.py
```
## API Endpoints
 - GET /api/tasks - Get all tasks
 - POST /api/tasks - Create a task
 - PUT /api/tasks/<task_id> - Update a task
 - Delete /api/tasks/<task_id> -Delete a task

### Future Improvements
 - Add users authentication
 - Improve natural-language task extraction
 - Add more media-processing features
 - Improve input validation
 - Add more automated testing
 - Improve error handling
 - Add task search and filtering
 - Deploy the application online

### Author
 - Sandhya Sharma
  




