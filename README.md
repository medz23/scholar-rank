# Python Exam IDE

A web-based exam platform for programming courses. Students solve Python problems in a browser-based IDE with Monaco editor, and their code is graded automatically inside sandboxed Docker containers.

## Features

- **Browser-based IDE** with Monaco editor and a built-in test terminal
- **Automatic grading** — student code runs in isolated Docker containers with memory/CPU limits
- **Two grading modes** — function-based (JSON input/output) and stdin/stdout
- **Anti-cheat** — fullscreen enforcement, tab-switching strikes (3 strikes = exam terminated), copy/paste disabled
- **Professor dashboard** — create problems, manage groups, add test cases, set global bonus, export CSV results
- **Randomized problem sets** — problems with the same `exam_order` are randomly assigned (one per set per student)

## Prerequisites

You need two things installed on your machine:

1. **Docker** — [Install Docker](https://docs.docker.com/get-docker/)
2. **Docker Compose** — included with Docker Desktop on Windows/Mac; on Linux install separately with `sudo apt install docker-compose-plugin`

Verify both are working:

```bash
docker --version
docker compose version
```

> **Note:** You do NOT need Python installed on your host machine. Everything runs inside Docker containers.

## Quick Start

### 1. Download the project

### 2. Modify the `.env` file

Then edit `.env` to set your own values if you want.

### 3. Pull the Python sandbox image

The grader runs student code inside `python:3.12-slim` containers. Pull it ahead of time so the first test run isn't slow:

```bash
docker pull python:3.12-slim
```

### 4. Start the application

```bash
docker compose up --build -d
```

This will:
- Build the web application container
- Start a PostgreSQL 16 database
- Create the database tables automatically
- Create the professor account from your `.env` credentials

### 5. Access the application

The app runs on **port 8765** by default.

**On the same machine:**

```
http://localhost:8765/pclp/login/
```

**From another device on the same network**, find your machine's IP address:

```bash
# Linux
hostname -I | awk '{print $1}'

# macOS
ipconfig getifaddr en0

# Windows (Command Prompt)
ipconfig
```

Then go to:

```
http://<YOUR_IP>:8765/pclp/login/
```

### 6. Log in as professor

Use the credentials you set in `.env` (`PROFESSOR_USERNAME` / `PROFESSOR_PASSWORD`).

## How to Use — Professor Workflow

### Creating problems

1. From the dashboard, scroll to **"Create New Problem"**
2. Fill in:
   - **Set / Q#** — the exam order number. Problems with the same number form a pool; each student gets one random problem from each pool.
   - **Title** — displayed to students
   - **Description** — supports Markdown
   - **Start Code** — the template students see in the editor
   - **Function Name** — if set, the grader calls this function directly. If left blank, the grader uses stdin/stdout mode.
   - **Weight** — how many points this problem is worth in the final grade
3. After creating a problem, expand **"Add Test Case"** to add test cases with input, expected output, point weight, and a hidden flag.

### Managing students

1. Create a **Group** (e.g., "512A") from the dashboard
2. Click into the group and **Add Student** with a username and password
3. Optionally **Assign Problem to Group** to force-assign a specific problem to all students in the group
4. Students who haven't been force-assigned will get random problems from each exam order pool when they first log in

### During the exam

- Students log in and are taken directly to their IDE
- They can run tests as many times as they want before submitting
- Submitting is final — it locks that problem and moves them to the next one
- If a student switches tabs 3 times, their exam is terminated

### After the exam

- View results per student in the group page
- Click **"Download CSV Results"** to export all scores and submitted code

## Project Structure

```
pclp-exam/
├── app/
│   ├── __init__.py          # Flask app factory, DB init, professor account creation
│   ├── models.py            # SQLAlchemy models (User, Problem, TestCase, etc.)
│   ├── routes/
│   │   ├── auth.py          # Login / logout
│   │   ├── admin.py         # Professor dashboard routes
│   │   ├── group.py         # Group management, CSV export
│   │   └── student.py       # Student IDE, code execution, submission
│   ├── services/
│   │   └── executor.py      # Docker-based code runner
│   ├── static/
│   │   ├── css/
│   │   │   ├── style.css
│   │   │   └── student.css
│   │   └── js/
│   │       ├── anticheat.js  # Tab-switch detection, copy/paste blocking
│   │       └── ide.js        # Monaco editor setup, test runner, submit logic
│   └── templates/
│       ├── admin.html
│       ├── group.html
│       ├── login.html
│       ├── student.html
│       ├── results.html
│       └── exam_complete.html
├── run.py                   # Entry point
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env                    
```

## Useful Commands

```bash
# Start the app
docker compose up --build -d

# View logs
docker compose logs -f web

# Stop the app (keeps data)
docker compose down

# Stop and DELETE all data (resets the database)
docker compose down -v

# Restart just the web container after code changes
docker compose restart web
```

## Troubleshooting

**"Cannot connect to the Docker daemon"** — Make sure Docker is running. On Linux: `sudo systemctl start docker`.

**First test run is slow** — The first time a student runs code, Docker may need to pull `python:3.12-slim` (~50 MB). Run `docker pull python:3.12-slim` ahead of time to avoid this.

**"Server busy" error when running tests** — The executor limits concurrent containers to 5. If many students run tests at the same time, some will get queued. They can retry after a few seconds. You can increase `MAX_CONCURRENT` in `executor.py` if your server can handle it.

**Port 8765 is already in use** — Change the port mapping in `docker-compose.yml` from `"8765:5000"` to something else, e.g. `"9000:5000"`.

**Database reset needed** — Run `docker compose down -v` to wipe the database volume completely, then `docker compose up --build -d` to start fresh.
