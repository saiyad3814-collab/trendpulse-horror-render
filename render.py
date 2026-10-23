import sys
import os
import requests
from moviepy.editor import ImageClip, AudioFileClip

def create_video(audio_path, image_path, output_path,https://geniuscoo.duckdns.org/webhook-test/2665411c-5442-4d4d-ad25-e2455915ab66=""):
    try:
        print(f"Loading audio from: {audio_path}")
        audio_clip = AudioFileClip(audio_path)
        
        print(f"Loading image from: {image_path}")
        image_clip = ImageClip(image_path).set_duration(audio_clip.duration)
        
        video_clip = image_clip.set_audio(audio_clip)
        
        print(f"Rendering video to: {output_path}")
        video_clip.write_videofile(
            output_path,
            fps=30,
            codec='libx264',
            audio_codec='aac',
            threads=2
        )
        print("Rendering completed successfully!")
        
        # रेंडर पूरा होने पर n8n को Webhook भेजना
        if webhook_url:
            print(f"Sending webhook callback to: {https://geniuscoo.duckdns.org/webhook-test/2665411c-5442-4d4d-ad25-e2455915ab66}")
            requests.post(webhook_url, json={
                "status": "success",
                "video_path": output_path
            })
            
    except Exception as e:
        print(f"Error during rendering: {str(e)}")
        if webhook_url:https://geniuscoo.duckdns.org/webhook-test/2665411c-5442-4d4d-ad25-e2455915ab66
            requests.post(https://geniuscoo.duckdns.org/webhook-test/2665411c-5442-4d4d-ad25-e2455915ab66, json={
                "status": "error",
                "message": str(e)
            })

if __name__ == "__main__":
    if len(sys.argv) >= 4:
        audio = sys.argv[1]
        image = sys.argv[2]
        output = sys.argv[3]
        webhook = sys.argv[4] if len(sys.argv) > 4 else ""
        create_video(audio, image, output, webhook)
    else:
        print("Usage: python render.py <audio_path> <image_path> <output_path> <webhook_url>")
