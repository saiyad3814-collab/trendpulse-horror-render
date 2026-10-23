import sys
import os
from moviepy.editor import ImageClip, AudioFileClip

def create_video(audio_path, image_path, output_path):
    try:
        print(f"Loading audio from: {audio_path}")
        audio_clip = AudioFileClip(audio_path)
        
        print(f"Loading image from: {image_path}")
        image_clip = ImageClip(image_path).set_duration(audio_clip.duration)
        
        # Audio connect to Video
        video_clip = image_clip.set_audio(audio_clip)
        
        print(f"Rendering video to: {output_path}")
        # Render Video (30 fps)
        video_clip.write_videofile(
            output_path,
            fps=30,
            codec='libx264',
            audio_codec='aac',
            threads=2
        )
        print("Rendering completed successfully!")
    except Exception as e:
        print(f"Error during rendering: {str(e)}")

if __name__ == "__main__":
    if len(sys.argv) >= 4:
        audio = sys.argv[1]
        image = sys.argv[2]
        output = sys.argv[3]
        create_video(audio, image, output)
    else:
        print("Usage: python render.py <audio_path> <image_path> <output_path>")
