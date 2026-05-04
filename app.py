from flask import Flask, request, jsonify, send_file, render_template_string
import subprocess, os, uuid, json, base64, threading, time

app = Flask(__name__)

# ---------- Config ----------
UPLOAD_FOLDER = "/tmp/wm_uploads"
OUTPUT_FOLDER = "/tmp/wm_outputs"
MAX_CONTENT_LENGTH = 200 * 1024 * 1024  # 200 MB max upload

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

HTML = open(os.path.join(os.path.dirname(__file__), "templates", "index.html")).read()

# ---------- Auto-cleanup: delete files older than 1 hour ----------
def cleanup_loop():
    while True:
        now = time.time()
        for folder in [UPLOAD_FOLDER, OUTPUT_FOLDER]:
            for f in os.listdir(folder):
                fp = os.path.join(folder, f)
                try:
                    if os.path.isfile(fp) and now - os.path.getmtime(fp) > 3600:
                        os.remove(fp)
                except:
                    pass
        time.sleep(600)

threading.Thread(target=cleanup_loop, daemon=True).start()

# ---------- Routes ----------
@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/upload", methods=["POST"])
def upload():
    if "video" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["video"]
    if file.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    vid_id = str(uuid.uuid4())
    ext = os.path.splitext(file.filename)[1].lower() or ".mp4"
    allowed = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".flv", ".wmv"}
    if ext not in allowed:
        return jsonify({"error": f"Unsupported format: {ext}"}), 400

    path = os.path.join(UPLOAD_FOLDER, vid_id + ext)
    file.save(path)

    # Extract frame at 2s for preview
    frame_path = os.path.join(UPLOAD_FOLDER, vid_id + "_thumb.jpg")
    subprocess.run([
        "ffmpeg", "-i", path, "-ss", "00:00:02", "-vframes", "1",
        "-vf", "scale=720:-1", frame_path, "-y"
    ], capture_output=True, timeout=30)

    # Fallback: try frame at 0s if 2s fails
    if not os.path.exists(frame_path):
        subprocess.run([
            "ffmpeg", "-i", path, "-vframes", "1",
            "-vf", "scale=720:-1", frame_path, "-y"
        ], capture_output=True, timeout=30)

    # Get video dimensions
    probe = subprocess.run([
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_streams", path
    ], capture_output=True, text=True, timeout=15)

    width, height = 1280, 720
    try:
        info = json.loads(probe.stdout)
        video_stream = next((s for s in info["streams"] if s["codec_type"] == "video"), {})
        width = video_stream.get("width", 1280)
        height = video_stream.get("height", 720)
    except:
        pass

    if not os.path.exists(frame_path):
        return jsonify({"error": "Could not extract preview frame. Is the file a valid video?"}), 500

    with open(frame_path, "rb") as f:
        thumb_b64 = base64.b64encode(f.read()).decode()
    os.remove(frame_path)

    return jsonify({
        "id": vid_id,
        "ext": ext,
        "width": width,
        "height": height,
        "thumb": thumb_b64
    })

@app.route("/process", methods=["POST"])
def process():
    data = request.json
    vid_id = data.get("id", "")
    ext = data.get("ext", ".mp4")
    regions = data.get("regions", [])

    # Sanitize vid_id (UUID only)
    try:
        uuid.UUID(vid_id)
    except:
        return jsonify({"error": "Invalid video ID"}), 400

    if not regions:
        return jsonify({"error": "No regions selected"}), 400

    input_path = os.path.join(UPLOAD_FOLDER, vid_id + ext)
    output_path = os.path.join(OUTPUT_FOLDER, vid_id + "_clean.mp4")

    if not os.path.exists(input_path):
        return jsonify({"error": "Video not found. Please re-upload."}), 404

    # Build delogo filter chain
    filters = ",".join([
        f"delogo=x={int(r['x'])}:y={int(r['y'])}:w={int(r['w'])}:h={int(r['h'])}:show=0"
        for r in regions
    ])

    cmd = [
        "ffmpeg", "-i", input_path,
        "-vf", filters,
        "-c:v", "libx264", "-crf", "18", "-preset", "fast",
        "-c:a", "copy",
        output_path, "-y"
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Processing timed out (video too long?)"}), 500

    if result.returncode != 0:
        return jsonify({"error": "FFmpeg failed: " + result.stderr[-500:]}), 500

    # Delete input after processing
    try:
        os.remove(input_path)
    except:
        pass

    return jsonify({"output_id": vid_id})

@app.route("/download/<vid_id>")
def download(vid_id):
    try:
        uuid.UUID(vid_id)
    except:
        return "Invalid ID", 400

    path = os.path.join(OUTPUT_FOLDER, vid_id + "_clean.mp4")
    if not os.path.exists(path):
        return "File not found or expired", 404

    return send_file(path, as_attachment=True, download_name="clean_video.mp4")

@app.errorhandler(413)
def too_large(e):
    return jsonify({"error": "File too large. Max size is 200 MB."}), 413

if __name__ == "__main__":
    print("\n🎬 Watermark Remover running at http://localhost:5000\n")
    app.run(debug=False, port=5000)
