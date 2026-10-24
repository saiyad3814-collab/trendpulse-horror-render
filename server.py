import os
import json
import uuid
import sys
import threading
import subprocess
import traceback
from flask import Flask, request, jsonify
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

app = Flask(__name__)

EPISODES_FOLDER_ID = "1taTM5hPagqEDeXH3dc54sEnk9UW1zqi7"
RENDER_TOKEN = os.environ.get("RENDER_TOKEN", "")
WORK_DIR = "/tmp/horror"
os.makedirs(WORK_DIR, exist_ok=True)

JOBS = {}


def log(*args):
    print("[render]", *args, flush=True)


def drive_service():
    info = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
    creds = Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/drive"]
    )
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def run_job(job_id, audio_path, image_path, episode_id):
    JOBS[job_id]["status"] = "running"
    try:
        output_path = os.path.join(WORK_DIR, f"{episode_id}.mp4")
        log(job_id, "rendering", episode_id)
        result = subprocess.run(
            [sys.executable, "render.py", audio_path, image_path, output_path],
            capture_output=True, text=True,
        )
        log(job_id, "render exit code", result.returncode)
        if result.stderr:
            log(job_id, "render stderr", result.stderr[-1500:])
        if result.returncode != 0 or not os.path.exists(output_path):
            raise RuntimeError((result.stderr or result.stdout or "render failed")[-1500:])

        log(job_id, "uploading to drive")
        service = drive_service()
        media = MediaFileUpload(output_path, mimetype="video/mp4", resumable=True)
        uploaded = service.files().create(
            body={"name": f"{episode_id}.mp4", "parents": [EPISODES_FOLDER_ID]},
            media_body=media,
            fields="id,webViewLink",
        ).execute()

        JOBS[job_id].update(
            status="done",
            drive_file_id=uploaded["id"],
            link=uploaded.get("webViewLink"),
        )
        log(job_id, "done", uploaded["id"])
    except Exception as e:
        log(job_id, "failed", traceback.format_exc())
        JOBS[job_id].update(status="failed", message=str(e)[:1500])


def authorized():
    return not RENDER_TOKEN or request.headers.get("X-Render-Token") == RENDER_TOKEN


@app.route("/render", methods=["POST"])
def start_render():
    if not authorized():
        return jsonify({"status": "error", "message": "unauthorized"}), 401

    episode_id = request.form.get("episode_id") or "episode"
    audio = request.files.get("audio")
    image = request.files.get("image")
    if not audio or not image:
        return jsonify({"status": "error", "message": "audio and image files required"}), 400

    job_id = uuid.uuid4().hex[:8]
    audio_path = os.path.join(WORK_DIR, f"{job_id}_audio.mp3")
    image_path = os.path.join(WORK_DIR, f"{job_id}_image.jpg")
    audio.save(audio_path)
    image.save(image_path)

    JOBS[job_id] = {"status": "queued", "episode_id": episode_id}
    log(job_id, "accepted", episode_id)
    threading.Thread(
        target=run_job,
        args=(job_id, audio_path, image_path, episode_id),
        daemon=True,
    ).start()
    return jsonify({"status": "accepted", "job_id": job_id, "episode_id": episode_id}), 202


@app.route("/status/<job_id>", methods=["GET"])
def status(job_id):
    if not authorized():
        return jsonify({"status": "error", "message": "unauthorized"}), 401
    job = JOBS.get(job_id)
    if not job:
        return jsonify({"status": "not_found"}), 404
    return jsonify(job)


@app.route("/", methods=["GET"])
def home():
    return "Server is up and running!"
