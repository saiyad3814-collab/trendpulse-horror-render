import sys
import subprocess
import imageio_ffmpeg


def render(audio_path, image_path, output_path):
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [
        ffmpeg, "-y",
        "-loop", "1", "-framerate", "1", "-i", image_path,
        "-i", audio_path,
        "-vf", "scale=1920:800:force_original_aspect_ratio=decrease,"
               "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black,format=yuv420p",
        "-c:v", "libx264", "-preset", "ultrafast", "-tune", "stillimage",
        "-r", "24",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        "-movflags", "+faststart",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stderr[-2000:], flush=True)
        sys.exit(1)
    print(f"Rendered: {output_path}", flush=True)


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python render.py <audio> <image> <output>")
        sys.exit(1)
    render(sys.argv[1], sys.argv[2], sys.argv[3])
