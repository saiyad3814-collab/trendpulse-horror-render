import os
import io
import json
import uuid
import sys
import threading
import subprocess
import requests
from flask import Flask, request, jsonify
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload

app = Flask(__name__)

EPISODES_FOLDER_ID = "1taTM5hPagqEDeXH3dc54sEnk9UW1zqi7"
RENDER_TOKEN = os.environ.get("RENDER_TOKEN", "")
WORK_DIR = "/tmp/horror"
os.makedirs(WORK_DIR, exist_ok=True)


def drive_service():
    info = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
    creds = Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/drive"]
    )
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def download(service, file_id, dest):
    req = service.files().get_media(fileId=file_id)
    with io.FileIO(dest, "wb") as fh:
        dl = MediaIoBaseDownload(fh, req)
        done = False
        while not done:
            _, done = dl.next_chunk()
    return dest


def run_job(job_id, audio_file_id, image_file_id, episode_id, callback_url):
    def notify(payload):
        try:
            requests.post(callback_url, json=payload, timeout=30)
        except Exception as e:
            print("callback failed:", e, flush=True)

    try:
        service = drive_service()
        audio_path = download(service, audio_file_id, os.path.join(WORK_DIR, f"{job_id}.mp3"))
        image_path = download(service, image_file_id, os.path.join(WORK_DIR, f"{job_id}.png"))
        output_path = os.path.join(WORK_DIR, f"{episode_id}.mp4")

        result = subprocess.run(
            [sys.executable, "render.py", audio_path, image_path, output_path],
            capture_output=True, text=True,
        )
        if result.returncode != 0 or not os.path.exists(output_path):
            raise RuntimeError((result.stderr or result.stdout)[-1500:])

        media = MediaFileUpload(output_path, mimetype="video/mp4", resumable=True)
        uploaded = service.files().create(
            body={"name": f"{episode_id}.mp4", "parents": [EPISODES_FOLDER_ID]},
            media_body=media,
            fields="id,webViewLink",
        ).execute()

        notify({
            "status": "success",
            "episode_id": episode_id,
            "drive_file_id": uploaded["id"],
            "link": uploaded.get("webViewLink"),
        })
    except Exception as e:
        notify({"status": "error", "episode_id": episode_id, "message": str(e)[:1500]})


@app.route("/render", methods=["POST"])
def start_render():
    if RENDER_TOKEN and request.headers.get("X-Render-Token") != RENDER_TOKEN:
        return jsonify({"status": "error", "message": "unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    required = ["audio_file_id", "image_file_id", "episode_id", "callback_url"]
    missing = [k for k in required if not data.get(k)]
    if missing:
        return jsonify({"status": "error", "message": f"missing: {missing}"}), 400

    job_id = uuid.uuid4().hex[:8]
    threading.Thread(
        target=run_job,
        args=(job_id, data["audio_file_id"], data["image_file_id"],
              data["episode_id"], data["callback_url"]),
        daemon=True,
    ).start()
    return jsonify({"status": "accepted", "job_id": job_id,
                    "episode_id": data["episode_id"]}), 202


@app.route("/", methods=["GET"])
def home():
    return "Server is up and running!"
