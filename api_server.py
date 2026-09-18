"""
RD Studio Auto Silence Remover — API & Web Server
Provides high-performance REST APIs, audio streaming with Range support,
native file picker integration, and serves the dark studio UI.
"""

import os
import sys
import json
import time
import uuid
import shutil
import mimetypes
import threading
from typing import Dict, Any, Optional

import bottle
from bottle import Bottle, request, response, static_file, abort

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from engine.ffmpeg_wrapper import FFMPEG_PATH, FFPROBE_PATH, get_media_info, format_duration
from engine.analyzer import SilenceAnalyzer
from engine.processor import AudioProcessor
from engine.waveform import generate_waveform_peaks
from engine.presets import PresetManager, DEFAULT_PRESET_ID
from engine.exporter import EXPORT_FORMATS, SAMPLE_RATES, get_safe_output_path
from engine.settings import SettingsManager
from engine.history import HistoryManager
from engine.batch import BatchManager

app = Bottle()

# Global managers
settings_mgr = SettingsManager()
preset_mgr = PresetManager()
history_mgr = HistoryManager()
batch_mgr = BatchManager(history_manager=history_mgr)

# Active single job state
active_job = {
    "job_id": None,
    "status": "idle",  # idle, analyzing, processing, completed, failed, cancelled
    "stage": "",
    "percentage": 0.0,
    "elapsed_sec": 0.0,
    "remaining_sec": None,
    "result": None,
    "error": None
}
active_processor: Optional[AudioProcessor] = None
active_analyzer: Optional[SilenceAnalyzer] = None
job_lock = threading.Lock()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UI_DIR = os.path.join(BASE_DIR, "ui")
UPLOADS_DIR = os.path.join(BASE_DIR, "data", "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)


# --- CORS / Utility Helpers ---
@app.hook('after_request')
def enable_cors():
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'PUT, GET, POST, DELETE, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Authorization, Content-Type, Accept, Origin'


@app.route('/api/<:re:.*>', method='OPTIONS')
def api_options():
    return {}


# --- Static UI Serving ---
@app.route('/')
def serve_index():
    return static_file("index.html", root=UI_DIR)


@app.route('/<filepath:path>')
def serve_static(filepath):
    return static_file(filepath, root=UI_DIR)


# --- API Endpoints ---

@app.route('/api/status', method='GET')
def get_status():
    return {
        "app_name": "RD Studio Auto Silence Remover",
        "version": "1.0.0",
        "owner": "Shahneel Khan",
        "studio": "RD Studio",
        "website": "https://rdstudio.online",
        "ffmpeg_ready": os.path.exists(FFMPEG_PATH),
        "export_formats": EXPORT_FORMATS,
        "sample_rates": SAMPLE_RATES,
    }


@app.route('/api/dialog/browse', method='POST')
def open_native_file_dialog():
    """Opens native Windows file picker dialog."""
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        
        filetypes = [
            ("Supported Media", "*.wav;*.mp3;*.m4a;*.aac;*.flac;*.ogg;*.opus;*.aiff;*.mp4;*.mkv;*.mov;*.webm;*.avi"),
            ("Audio Files", "*.wav;*.mp3;*.m4a;*.aac;*.flac;*.ogg;*.opus;*.aiff"),
            ("Video Files", "*.mp4;*.mkv;*.mov;*.webm;*.avi"),
            ("All Files", "*.*")
        ]
        
        selected_file = filedialog.askopenfilename(
            title="RD Studio — Select Audio or Video File",
            filetypes=filetypes
        )
        root.destroy()
        
        if not selected_file:
            return {"cancelled": True}

        info = get_media_info(selected_file)
        return {"cancelled": False, "media_info": info}
    except Exception as e:
        response.status = 400
        return {"error": str(e)}


@app.route('/api/dialog/browse_folder', method='POST')
def open_folder_dialog():
    """Opens native Windows folder picker dialog."""
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        folder = filedialog.askdirectory(title="Select RD Studio Export Directory")
        root.destroy()
        return {"cancelled": not bool(folder), "directory": folder}
    except Exception as e:
        response.status = 400
        return {"error": str(e)}


@app.route('/api/file/probe', method='POST')
def probe_file():
    data = request.json or {}
    filepath = data.get("filepath")
    if not filepath:
        response.status = 400
        return {"error": "No filepath provided."}
    try:
        info = get_media_info(filepath)
        return {"media_info": info}
    except Exception as e:
        response.status = 400
        return {"error": str(e)}


@app.route('/api/file/upload', method='POST')
def upload_file():
    """Handles file drag & drop upload from browser/mobile."""
    upload = request.files.get('file')
    if not upload:
        response.status = 400
        return {"error": "No file uploaded."}

    ext = os.path.splitext(upload.filename)[1]
    safe_name = f"upload_{int(time.time())}_{upload.filename}"
    save_path = os.path.join(UPLOADS_DIR, safe_name)
    upload.save(save_path, overwrite=True)

    try:
        info = get_media_info(save_path)
        return {"media_info": info}
    except Exception as e:
        if os.path.exists(save_path):
            os.remove(save_path)
        response.status = 400
        return {"error": str(e)}


@app.route('/api/file/waveform', method='POST')
def get_waveform():
    data = request.json or {}
    filepath = data.get("filepath")
    target_peaks = int(data.get("target_peaks", 2000))
    if not filepath:
        response.status = 400
        return {"error": "Filepath required."}
    try:
        peaks = generate_waveform_peaks(filepath, target_peaks=target_peaks)
        return {"peaks": peaks, "peak_count": len(peaks)}
    except Exception as e:
        response.status = 400
        return {"error": str(e)}


@app.route('/api/silence/analyze', method='POST')
def analyze_silence():
    global active_analyzer
    data = request.json or {}
    filepath = data.get("filepath")
    total_duration = float(data.get("duration", 0.0))
    threshold_db = float(data.get("threshold_db", -20.0))
    min_silence_sec = float(data.get("min_silence_sec", 0.07))
    max_silence_sec = data.get("max_silence_sec")
    if max_silence_sec is not None and str(max_silence_sec).strip():
        max_silence_sec = float(max_silence_sec)
    else:
        max_silence_sec = None
    action = data.get("action", "truncate")
    remaining_silence_sec = float(data.get("remaining_silence_sec", 0.20))

    if not filepath or not os.path.exists(filepath):
        response.status = 400
        return {"error": "Filepath not found."}

    try:
        active_analyzer = SilenceAnalyzer()
        res = active_analyzer.analyze(
            filepath=filepath,
            total_duration=total_duration,
            threshold_db=threshold_db,
            min_silence_sec=min_silence_sec,
            max_silence_sec=max_silence_sec,
            action=action,
            remaining_silence_sec=remaining_silence_sec
        )
        return {"analysis": res}
    except Exception as e:
        response.status = 400
        return {"error": str(e)}
    finally:
        active_analyzer = None


@app.route('/api/silence/process', method='POST')
def process_silence():
    global active_job, active_processor
    data = request.json or {}
    filepath = data.get("filepath")
    total_duration = float(data.get("duration", 0.0))
    silence_regions = data.get("silence_regions", [])
    action = data.get("action", "truncate")
    remaining_silence_sec = float(data.get("remaining_silence_sec", 0.20))
    max_silence_sec = data.get("max_silence_sec")
    if max_silence_sec is not None and str(max_silence_sec).strip():
        max_silence_sec = float(max_silence_sec)
    else:
        max_silence_sec = None

    export_format = data.get("export_format", "wav")
    quality_id = data.get("quality_id")
    sample_rate = data.get("sample_rate", "original")
    channels = data.get("channels")
    output_dir = data.get("output_dir") or settings_mgr.get("export_dir")

    if not filepath or not os.path.exists(filepath):
        response.status = 400
        return {"error": "Invalid media file path."}

    with job_lock:
        if active_job["status"] == "processing":
            response.status = 409
            return {"error": "A processing job is already running."}

        job_id = str(uuid.uuid4())[:8]
        safe_output = get_safe_output_path(
            input_path=filepath,
            output_dir=output_dir,
            export_format=export_format,
            suffix="_silence_removed"
        )

        active_job.update({
            "job_id": job_id,
            "status": "processing",
            "stage": "Initializing job...",
            "percentage": 0.0,
            "elapsed_sec": 0.0,
            "remaining_sec": None,
            "result": None,
            "error": None
        })

    def run_worker():
        global active_processor
        try:
            active_processor = AudioProcessor(temp_dir=settings_mgr.get("temp_dir"))

            def prog_callback(p):
                with job_lock:
                    active_job["stage"] = p.get("stage", "Processing audio...")
                    active_job["percentage"] = p.get("percentage", 0.0)
                    active_job["elapsed_sec"] = p.get("elapsed_sec", 0.0)
                    active_job["remaining_sec"] = p.get("remaining_sec")

            result = active_processor.process(
                job_id=job_id,
                input_path=filepath,
                output_path=safe_output,
                total_duration=total_duration,
                silence_regions=silence_regions,
                action=action,
                remaining_silence_sec=remaining_silence_sec,
                max_silence_sec=max_silence_sec,
                export_format=export_format,
                quality_id=quality_id,
                sample_rate=sample_rate,
                channels=channels,
                on_progress=prog_callback
            )

            with job_lock:
                active_job["status"] = "completed"
                active_job["stage"] = "Processing Complete"
                active_job["percentage"] = 100.0
                active_job["result"] = result

            # Record in history
            history_mgr.add_entry({
                "filename": os.path.basename(filepath),
                "preset": data.get("preset_name", "RD Studio"),
                "original_duration": result["original_duration_formatted"],
                "output_duration": result["output_duration_formatted"],
                "silence_removed": result["silence_removed_formatted"],
                "output_path": result["output_path"],
                "status": "Completed"
            })

        except InterruptedError:
            with job_lock:
                active_job["status"] = "cancelled"
                active_job["stage"] = "Cancelled by user"
        except Exception as ex:
            with job_lock:
                active_job["status"] = "failed"
                active_job["stage"] = "Failed"
                active_job["error"] = str(ex)
        finally:
            active_processor = None

    t = threading.Thread(target=run_worker, daemon=True)
    t.start()

    return {"status": "started", "job_id": job_id, "output_path": safe_output}


@app.route('/api/silence/progress', method='GET')
def get_progress():
    with job_lock:
        return dict(active_job)


@app.route('/api/silence/cancel', method='POST')
def cancel_active():
    global active_processor, active_analyzer
    with job_lock:
        if active_processor:
            active_processor.cancel()
        if active_analyzer:
            active_analyzer.cancel()
        active_job["status"] = "cancelled"
        active_job["stage"] = "Cancelled"
    return {"status": "cancelling"}


# --- Presets Endpoints ---
@app.route('/api/presets', method='GET')
def get_presets():
    return {"presets": preset_mgr.get_all()}


@app.route('/api/presets', method='POST')
def save_preset():
    data = request.json or {}
    try:
        saved = preset_mgr.create_or_update_custom(
            name=data.get("name", "Custom Preset"),
            threshold_db=float(data.get("threshold_db", -20.0)),
            min_silence_sec=float(data.get("min_silence_sec", 0.07)),
            action=data.get("action", "truncate"),
            remaining_silence_sec=float(data.get("remaining_silence_sec", 0.20)),
            max_silence_sec=float(data.get("max_silence_sec")) if data.get("max_silence_sec") else None,
            preset_id=data.get("id")
        )
        return {"preset": saved}
    except Exception as e:
        response.status = 400
        return {"error": str(e)}


@app.route('/api/presets/<preset_id>', method='DELETE')
def delete_preset(preset_id):
    try:
        ok = preset_mgr.delete_preset(preset_id)
        if not ok:
            response.status = 404
            return {"error": "Preset not found."}
        return {"success": True}
    except Exception as e:
        response.status = 400
        return {"error": str(e)}


# --- Settings & History Endpoints ---
@app.route('/api/settings', method='GET')
def get_settings():
    return {"settings": settings_mgr.settings}


@app.route('/api/settings', method='POST')
def update_settings():
    data = request.json or {}
    updated = settings_mgr.update_all(data)
    return {"settings": updated}


@app.route('/api/history', method='GET')
def get_history():
    return {"history": history_mgr.get_all()}


@app.route('/api/history/clear', method='POST')
def clear_history():
    history_mgr.clear()
    return {"success": True}


# --- Batch Processing Endpoints ---
@app.route('/api/batch/items', method='GET')
def get_batch_items():
    return {"items": batch_mgr.get_items(), "is_running": batch_mgr._is_running}


@app.route('/api/batch/add', method='POST')
def add_to_batch():
    data = request.json or {}
    filepath = data.get("filepath")
    if not filepath or not os.path.exists(filepath):
        response.status = 400
        return {"error": "Invalid filepath."}
    try:
        item = batch_mgr.add_file(filepath)
        return {"item": item, "total_items": len(batch_mgr.get_items())}
    except Exception as e:
        response.status = 400
        return {"error": str(e)}


@app.route('/api/batch/remove', method='POST')
def remove_from_batch():
    data = request.json or {}
    item_id = data.get("id")
    ok = batch_mgr.remove_item(item_id)
    return {"success": ok}


@app.route('/api/batch/clear', method='POST')
def clear_batch():
    batch_mgr.clear()
    return {"success": True}


@app.route('/api/batch/process_all', method='POST')
def process_all_batch():
    data = request.json or {}
    settings = data.get("settings", {})
    output_dir = data.get("output_dir") or settings_mgr.get("export_dir")

    if batch_mgr._is_running:
        response.status = 409
        return {"error": "Batch processing already in progress."}

    threading.Thread(
        target=batch_mgr.process_all,
        kwargs={"settings": settings, "output_dir": output_dir},
        daemon=True
    ).start()

    return {"status": "started"}


@app.route('/api/batch/cancel', method='POST')
def cancel_batch():
    batch_mgr.cancel()
    return {"status": "cancelling"}


# --- Audio Streaming with Range Support ---
@app.route('/api/stream/audio')
def stream_audio():
    """
    Streams audio file to browser/preview player with HTTP Range header support.
    Allows instant scrubbing forward and backward in audio player.
    """
    filepath = request.query.get('file')
    if not filepath or not os.path.exists(filepath):
        abort(404, "Audio file not found.")

    file_size = os.path.getsize(filepath)
    mime_type, _ = mimetypes.guess_type(filepath)
    mime_type = mime_type or "audio/wav"

    range_header = request.headers.get('Range')
    if not range_header:
        response.content_type = mime_type
        response.headers['Content-Length'] = str(file_size)
        response.headers['Accept-Ranges'] = 'bytes'
        return open(filepath, 'rb')

    # Handle Range header
    ranges = range_header.replace('bytes=', '').split('-')
    start = int(ranges[0]) if ranges[0] else 0
    end = int(ranges[1]) if len(ranges) > 1 and ranges[1] else file_size - 1

    if start >= file_size or end >= file_size or start > end:
        response.status = 416
        response.headers['Content-Range'] = f'bytes */{file_size}'
        return ""

    content_length = end - start + 1
    response.status = 206
    response.content_type = mime_type
    response.headers['Content-Range'] = f'bytes {start}-{end}/{file_size}'
    response.headers['Content-Length'] = str(content_length)
    response.headers['Accept-Ranges'] = 'bytes'

    def file_chunk_generator(fp, offset, length, chunk_size=65536):
        with open(fp, 'rb') as f:
            f.seek(offset)
            remaining = length
            while remaining > 0:
                read_amount = min(chunk_size, remaining)
                chunk = f.read(read_amount)
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    return file_chunk_generator(filepath, start, content_length)


@app.route('/api/download')
def download_audio_file():
    """Forces browser or mobile phone to download the processed audio file directly."""
    filepath = request.query.get('file')
    if not filepath or not os.path.exists(filepath):
        abort(404, "Audio file not found.")

    filename = os.path.basename(filepath)
    dirname = os.path.dirname(os.path.abspath(filepath))
    return static_file(filename, root=dirname, download=filename)


def run_server(host="127.0.0.1", port=8080):
    """Starts the bottle web server."""
    bottle.run(app, host=host, port=port, quiet=True)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    host = sys.argv[2] if len(sys.argv) > 2 else "127.0.0.1"
    print(f"Starting RD Studio Auto Silence Remover Server on http://{host}:{port}")
    run_server(host=host, port=port)
