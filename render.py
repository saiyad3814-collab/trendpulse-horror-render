import sys
from moviepy.editor import ImageClip, AudioFileClip


def render(audio_path, image_path, output_path):
    audio = AudioFileClip(audio_path)
    video = ImageClip(image_path).set_duration(audio.duration).set_audio(audio)
    video.write_videofile(
        output_path, fps=24, codec="libx264", audio_codec="aac",
        threads=2, preset="ultrafast", logger=None,
    )
    video.close()
    audio.close()


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python render.py <audio> <image> <output>")
        sys.exit(1)
    render(sys.argv[1], sys.argv[2], sys.argv[3])
