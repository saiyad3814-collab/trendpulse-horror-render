import os
import json
import uuid
import sys
import threading
import subprocess
import traceback
from flask import Flask, request, jsonify
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

app = Flask(__name__)

RENDER_TOKEN = os.environ.get("RENDER_TOKEN", "")
WORK_DIR = "/tmp/horror"
os.makedirs(WORK_DIR, exist_ok=True)

JOBS = {}

def log(*args):
    print("[render]", *args, flush=True)

def youtube_service():
    creds = Credentials(
        token=None,
        refresh_token=os.environ["YOUTUBE_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YOUTUBE_CLIENT_ID"],
        client_secret=os.environ["YOUTUBE_CLIENT_SECRET"],
        scopes=["https://www.googleapis.com/auth/youtube.upload"],
    )
    return build("youtube", "v3", credentials=creds, cache_discovery=False)

def upload_to_youtube(path, title, privacy="unlisted"):
    yt = youtube_service()
    body = {
        "snippet": {"title": title[:100], "description": "", "tags": [], "categoryId": "24"},
        "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False},
    }
    media = MediaFileUpload(path, mimetype="video/mp4", chunksize=8 * 1024 * 1024, resumable=True)
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
    resp = None
    while resp is None:
        _, resp = req.next_chunk()
    return resp["id"]

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
        log(job_id, "uploading to youtube")
        video_id = upload_to_youtube(output_path, title=episode_id.replace("_", " "))
        JOBS[job_id].update(status="done", youtube_id=video_id, link=f"https://youtu.be/{video_id}")
        log(job_id, "done", video_id)
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
    threading.Thread(target=run_job, args=(job_id, audio_path, image_path, episode_id), daemon=True).start()
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
