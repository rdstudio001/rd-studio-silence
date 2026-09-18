"""
RD Studio Auto Silence Remover — Output Verification Module
Verifies that generated audio meets studio quality, is non-empty, and decodable by FFprobe.
"""

import os
import subprocess
from typing import Dict, Any, Tuple
from .ffmpeg_wrapper import FFPROBE_PATH


def verify_audio_output(filepath: str, min_expected_duration: float = 0.05) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Verifies that the output audio file was successfully generated and is valid.

    Checks:
    1. File exists
    2. File size > 0
    3. FFprobe can decode container and read streams
    4. At least one audio stream is present
    5. Duration is valid and greater than min_expected_duration

    Returns:
        (is_valid: bool, error_message: str, details: Dict)
    """
    if not os.path.exists(filepath):
        return False, f"Output file does not exist at '{filepath}'", {}

    size = os.path.getsize(filepath)
    if size == 0:
        return False, f"Output file is empty (0 bytes): '{filepath}'", {}

    cmd = [
        FFPROBE_PATH,
        "-v", "error",
        "-show_entries", "format=duration,size,bit_rate:stream=codec_name,channels,sample_rate",
        "-of", "json",
        filepath
    ]

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        import json
        info = json.loads(res.stdout)
    except Exception as e:
        return False, f"Output file could not be decoded by FFprobe: {str(e)}", {}

    streams = info.get("streams", [])
    if not streams:
        return False, "Output file contains no audio streams.", {}

    audio_stream = streams[0]
    format_info = info.get("format", {})
    dur_str = format_info.get("duration") or audio_stream.get("duration")

    try:
        duration = float(dur_str) if dur_str else 0.0
    except (ValueError, TypeError):
        duration = 0.0

    if duration < min_expected_duration:
        return False, f"Output duration ({duration:.2f}s) is unexpectedly short or invalid.", {
            "duration": duration,
            "size": size,
            "stream": audio_stream
        }

    return True, "", {
        "duration": duration,
        "size": size,
        "codec": audio_stream.get("codec_name"),
        "channels": audio_stream.get("channels"),
        "sample_rate": audio_stream.get("sample_rate")
    }
