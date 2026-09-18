"""
RD Studio Auto Silence Remover — FFmpeg Wrapper Module
Handles binary resolution, metadata extraction, validation, and safe subprocess execution.
"""

import os
import sys
import json
import shutil
import subprocess
from typing import Dict, Any, Optional, List

# Ensure static-ffmpeg paths are registered if available
try:
    import static_ffmpeg
    static_ffmpeg.add_paths()
except Exception:
    pass


def find_binary(binary_name: str) -> str:
    """
    Locates ffmpeg or ffprobe executable from static_ffmpeg, PATH, or local directory.
    """
    # Check PATH first (which static_ffmpeg adds to)
    path = shutil.which(binary_name)
    if path and os.path.exists(path):
        return path

    # Check python lib static_ffmpeg directory directly on Windows
    site_packages = os.path.dirname(os.path.dirname(sys.executable))
    possible_dirs = [
        os.path.join(sys.prefix, "Lib", "site-packages", "static_ffmpeg", "bin", "win32"),
        os.path.join(os.path.expanduser("~"), "AppData", "Local", "Programs", "Python", "Python312", "Lib", "site-packages", "static_ffmpeg", "bin", "win32"),
        os.path.join(os.path.dirname(__file__), "..", "bin"),
    ]
    exe_name = f"{binary_name}.exe" if sys.platform == "win32" else binary_name
    for d in possible_dirs:
        candidate = os.path.join(d, exe_name)
        if os.path.exists(candidate):
            return candidate

    raise FileNotFoundError(f"Could not find required binary: '{binary_name}'. Please ensure FFmpeg is installed.")


FFMPEG_PATH = find_binary("ffmpeg")
FFPROBE_PATH = find_binary("ffprobe")


def format_duration(seconds: float) -> str:
    """Format seconds into HH:MM:SS.ms"""
    if seconds is None or seconds < 0:
        return "00:00:00"
    total_sec = int(seconds)
    ms = int((seconds - total_sec) * 1000)
    hours = total_sec // 3600
    minutes = (total_sec % 3600) // 60
    secs = total_sec % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}.{ms // 100:01d}"


def format_filesize(size_bytes: int) -> str:
    """Format bytes into readable string (KB, MB, GB)"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def get_media_info(filepath: str) -> Dict[str, Any]:
    """
    Probes media file using ffprobe and extracts comprehensive audio and container metadata.
    Validates that audio stream exists.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: '{filepath}'")

    file_size = os.path.getsize(filepath)
    filename = os.path.basename(filepath)
    ext = os.path.splitext(filepath)[1].lower().lstrip(".")

    cmd = [
        FFPROBE_PATH,
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        filepath
    ]

    try:
        creationflags = 0x08000000 if sys.platform == "win32" else 0
        res = subprocess.run(cmd, capture_output=True, text=True, check=True, creationflags=creationflags)
        data = json.loads(res.stdout)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"FFprobe could not read media file '{filename}'. Possible corruption or unsupported format.")
    except Exception as e:
        raise RuntimeError(f"Failed to probe '{filename}': {str(e)}")

    format_info = data.get("format", {})
    streams = data.get("streams", [])

    audio_stream = None
    video_stream = None

    for s in streams:
        codec_type = s.get("codec_type")
        if codec_type == "audio" and audio_stream is None:
            audio_stream = s
        elif codec_type == "video" and video_stream is None:
            video_stream = s

    is_video = video_stream is not None

    if audio_stream is None:
        if is_video:
            raise ValueError(f"No audio stream found in video '{filename}'. RD Studio requires an audio track.")
        else:
            raise ValueError(f"No audio stream detected in file '{filename}'.")

    # Determine duration
    duration_str = audio_stream.get("duration") or format_info.get("duration")
    try:
        duration = float(duration_str) if duration_str else 0.0
    except (ValueError, TypeError):
        duration = 0.0

    # Audio details
    codec_name = audio_stream.get("codec_name", "unknown")
    sample_rate = int(audio_stream.get("sample_rate", 44100))
    channels = int(audio_stream.get("channels", 2))
    channel_layout = audio_stream.get("channel_layout", "stereo" if channels == 2 else "mono" if channels == 1 else f"{channels} channels")

    # Bit depth determination
    bits_per_sample = audio_stream.get("bits_per_sample") or audio_stream.get("bits_per_raw_sample")
    sample_fmt = audio_stream.get("sample_fmt", "")
    if bits_per_sample and int(bits_per_sample) > 0:
        bit_depth = f"{bits_per_sample}-bit"
    elif "s16" in sample_fmt:
        bit_depth = "16-bit"
    elif "s24" in sample_fmt:
        bit_depth = "24-bit"
    elif "s32" in sample_fmt:
        bit_depth = "32-bit"
    elif "flt" in sample_fmt:
        bit_depth = "32-bit Float"
    elif "dbl" in sample_fmt:
        bit_depth = "64-bit Float"
    else:
        bit_depth = "N/A"

    return {
        "filepath": os.path.abspath(filepath),
        "filename": filename,
        "extension": ext,
        "filesize": file_size,
        "filesize_formatted": format_filesize(file_size),
        "duration": duration,
        "duration_formatted": format_duration(duration),
        "sample_rate": sample_rate,
        "channels": channels,
        "channel_layout": channel_layout,
        "audio_codec": codec_name.upper(),
        "bit_depth": bit_depth,
        "is_video": is_video,
        "video_codec": video_stream.get("codec_name", "").upper() if video_stream else None,
    }
