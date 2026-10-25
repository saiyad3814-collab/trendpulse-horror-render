import os
import json
import uuid
import threading
import subprocess
import tempfile
import traceback

from flask import Flask, request, jsonify
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

app = Flask(__name__)
JOBS = {}


def check_token():
    return request.headers.get("X-Render-Token") == os.environ.get("RENDER_TOKEN")


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
        "snippet": {"title": title[:100], "description": "", "categoryId": "24"},
        "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False},
    }
    media = MediaFileUpload(path, mimetype="video/mp4", chunksize=8 * 1024 * 1024, resumable=True)
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
    resp = None
    while resp is None:
        _, resp = req.next_chunk()
    return resp["id"]


def build_video(job_id, episode_id, shots, workdir):
    try:
        JOBS[job_id]["state"] = "running"
        clips = []
        for s in shots:
            no = int(s["shot_no"])
            img = os.path.join(workdir, f"shot_{no:02d}.jpg")
            out = os.path.join(workdir, f"clip_{no:02d}.mp4")
            subprocess.run(
                ["ffmpeg", "-y", "-loop", "1", "-i", img, "-t", str(s["duration"]),
                 "-vf", "scale=1920:1080,setsar=1", "-r", "25",
                 "-c:v", "libx264", "-preset", "veryfast", "-crf", "26", "-pix_fmt", "yuv420p", out],
                check=True,
            )
            clips.append(out)

        list_path = os.path.join(workdir, "clips.txt")
        with open(list_path, "w") as f:
            for c in clips:
                f.write(f"file '{c}'\n")

        video = os.path.join(workdir, "video.mp4")
        subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_path,
                        "-c", "copy", video], check=True)

        audio = os.path.join(workdir, "audio.mp3")
        final = os.path.join(workdir, "final.mp4")
        subprocess.run(["ffmpeg", "-y", "-i", video, "-i", audio, "-map", "0:v", "-map", "1:a",
                        "-c:v", "copy", "-c:a", "aac", "-shortest", final], check=True)

        JOBS[job_id]["state"] = "uploading"
        yt_id = upload_to_youtube(final, episode_id.replace("_", " "))
        JOBS[job_id].update({"state": "done", "youtube_id": yt_id,
                             "link": f"https://youtu.be/{yt_id}"})
    except Exception as e:
        JOBS[job_id].update({"state": "failed", "error": str(e), "trace": traceback.format_exc()[-1500:]})
    finally:
        pass


@app.route("/render", methods=["POST"])
def render():
    if not check_token():
        return jsonify({"error": "unauthorized"}), 401

    episode_id = request.form.get("episode_id", "Episode_Unknown")
    shots = json.loads(request.form.get("shots", "[]"))
    if "audio" not in request.files:
        return jsonify({"error": "audio missing"}), 400

    job_id = uuid.uuid4().hex[:12]
    workdir = tempfile.mkdtemp(prefix=f"job_{job_id}_")

    request.files["audio"].save(os.path.join(workdir, "audio.mp3"))
    for key, f in request.files.items(multi=True) if False else []:
        pass
    for key in request.files:
        if key.startswith("shot_"):
            request.files[key].save(os.path.join(workdir, f"{key}.jpg"))

    JOBS[job_id] = {"state": "queued", "episode_id": episode_id}
    threading.Thread(target=build_video, args=(job_id, episode_id, shots, workdir), daemon=True).start()
    return jsonify({"job_id": job_id, "state": "queued"}), 202


@app.route("/status/<job_id>", methods=["GET"])
def status(job_id):
    if not check_token():
        return jsonify({"error": "unauthorized"}), 401
    job = JOBS.get(job_id)
    if not job:
        return jsonify({"error": "not found"}), 404
    return jsonify(job)


@app.route("/", methods=["GET"])
def home():
    return "ok"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
