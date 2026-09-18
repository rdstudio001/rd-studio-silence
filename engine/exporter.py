"""
RD Studio Auto Silence Remover — Audio Exporting Module
Provides studio-grade audio encoding profiles (WAV, MP3, FLAC, AAC, OPUS/OGG)
strictly preserving audio quality without unintended coloration or resampling.
"""

import os
import sys
from typing import Dict, Any, List, Optional, Tuple
from .ffmpeg_wrapper import FFMPEG_PATH


EXPORT_FORMATS = {
    "wav": {
        "name": "WAV (Uncompressed PCM)",
        "ext": "wav",
        "qualities": [
            {"id": "pcm_16", "label": "16-bit PCM (Standard CD)", "codec": "pcm_s16le"},
            {"id": "pcm_24", "label": "24-bit PCM (Studio Dubbing Master)", "codec": "pcm_s24le"},
            {"id": "pcm_32f", "label": "32-bit Float (Maximum Dynamic Range)", "codec": "pcm_f32le"},
        ],
        "default_quality": "pcm_24"
    },
    "mp3": {
        "name": "MP3 (MPEG Audio Layer III)",
        "ext": "mp3",
        "qualities": [
            {"id": "mp3_320", "label": "320 kbps (High Quality)", "codec": "libmp3lame", "bitrate": "320k"},
            {"id": "mp3_256", "label": "256 kbps (Studio Reference)", "codec": "libmp3lame", "bitrate": "256k"},
            {"id": "mp3_192", "label": "192 kbps (Standard Podcast)", "codec": "libmp3lame", "bitrate": "192k"},
            {"id": "mp3_128", "label": "128 kbps (Draft Preview)", "codec": "libmp3lame", "bitrate": "128k"},
        ],
        "default_quality": "mp3_320"
    },
    "flac": {
        "name": "FLAC (Free Lossless Audio Codec)",
        "ext": "flac",
        "qualities": [
            {"id": "flac_lossless", "label": "Lossless Studio (Level 5)", "codec": "flac", "extra": ["-compression_level", "5"]},
        ],
        "default_quality": "flac_lossless"
    },
    "m4a": {
        "name": "AAC / M4A (MPEG-4 Audio)",
        "ext": "m4a",
        "qualities": [
            {"id": "aac_320", "label": "320 kbps AAC", "codec": "aac", "bitrate": "320k"},
            {"id": "aac_256", "label": "256 kbps AAC (Standard Voice)", "codec": "aac", "bitrate": "256k"},
            {"id": "aac_192", "label": "192 kbps AAC", "codec": "aac", "bitrate": "192k"},
        ],
        "default_quality": "aac_256"
    },
    "ogg": {
        "name": "OGG / Opus (Voice Optimized)",
        "ext": "ogg",
        "qualities": [
            {"id": "opus_192", "label": "192 kbps Opus", "codec": "libopus", "bitrate": "192k"},
            {"id": "opus_128", "label": "128 kbps Opus", "codec": "libopus", "bitrate": "128k"},
        ],
        "default_quality": "opus_192"
    }
}


SAMPLE_RATES = [
    {"value": "original", "label": "Original (Preserve Source)"},
    {"value": "44100", "label": "44,100 Hz (Standard Audio / CD)"},
    {"value": "48000", "label": "48,000 Hz (Dubbing / Broadcast Video Standard)"},
    {"value": "88200", "label": "88,200 Hz (High Resolution)"},
    {"value": "96000", "label": "96,000 Hz (High Resolution Studio Master)"},
]


def get_safe_output_path(
    input_path: str,
    output_dir: Optional[str] = None,
    export_format: str = "wav",
    suffix: str = "_silence_removed",
    overwrite_existing: bool = False
) -> str:
    """
    Constructs a safe, collision-free output file path.
    Never overwrites original file.
    """
    input_dir = os.path.dirname(input_path)
    base_name = os.path.splitext(os.path.basename(input_path))[0]

    target_dir = output_dir if (output_dir and os.path.exists(output_dir)) else input_dir
    ext = export_format.lower().lstrip(".")
    if ext not in EXPORT_FORMATS:
        ext = "wav"

    filename = f"{base_name}{suffix}.{ext}"
    candidate = os.path.join(target_dir, filename)

    # Protect original
    if os.path.abspath(candidate) == os.path.abspath(input_path):
        filename = f"{base_name}_processed.{ext}"
        candidate = os.path.join(target_dir, filename)

    if not overwrite_existing and os.path.exists(candidate):
        count = 1
        while os.path.exists(candidate):
            filename = f"{base_name}{suffix}_{count}.{ext}"
            candidate = os.path.join(target_dir, filename)
            count += 1

    return candidate


def build_export_ffmpeg_args(
    export_format: str = "wav",
    quality_id: Optional[str] = None,
    sample_rate: Optional[str] = "original",
    channels: Optional[int] = None
) -> List[str]:
    """
    Builds FFmpeg encoding arguments based on chosen format and profile.
    """
    fmt = export_format.lower().lstrip(".")
    if fmt not in EXPORT_FORMATS:
        fmt = "wav"

    fmt_info = EXPORT_FORMATS[fmt]
    qualities = fmt_info["qualities"]
    chosen_q = next((q for q in qualities if q["id"] == quality_id), qualities[0])

    args = ["-vn"]  # Audio only! Never export video track.

    codec = chosen_q.get("codec")
    if codec:
        args.extend(["-c:a", codec])

    bitrate = chosen_q.get("bitrate")
    if bitrate:
        args.extend(["-b:a", bitrate])

    extra = chosen_q.get("extra")
    if extra:
        args.extend(extra)

    # Sample rate handling
    if sample_rate and sample_rate != "original":
        try:
            sr_int = int(sample_rate)
            args.extend(["-ar", str(sr_int)])
        except ValueError:
            pass

    # Channel handling
    if channels and channels in (1, 2, 6, 8):
        args.extend(["-ac", str(channels)])

    return args
