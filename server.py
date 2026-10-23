from flask import Flask, request, jsonify
import subprocess
import os

app = Flask(__name__)

@app.route('/render', methods=['POST'])
def run_render():
    data = request.get_json(silent=True) or {}
    audio_path = data.get('audio_path', '/tmp/audio.mp3')
    image_path = data.get('image_path', '/tmp/image.png')
    webhook_url = data.get('webhook_url', 'https://geniuscoo.duckdns.org/webhook-test/2665411c-5442-4d4d-ad25-e2455915ab66')
    
    output_dir = "/opt/render/project/src/episodes"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "horror_episode_60m.mp4")
    
    render_script = "render.py"
    cmd = ["python", render_script, str(audio_path), str(image_path), str(output_path), str(webhook_url)]
    
    try:
        subprocess.Popen(cmd)
        return jsonify({
            "status": "success",
            "message": "Rendering started in background",
            "video_path": output_path
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/', methods=['GET'])
def home():
    return "Server is up and running!"

if __name__ == '__main__':
    app.run()
