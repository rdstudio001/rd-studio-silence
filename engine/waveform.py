"""
RD Studio Auto Silence Remover — Waveform Peak Generation Module
Extracts downsampled min/max peaks for multi-hour audio without memory bloat.
Ensures 60 FPS rendering on UI canvas regardless of file duration.
"""

import os
import sys
import subprocess
import numpy as np
from typing import Dict, Any, List, Optional
from .ffmpeg_wrapper import FFMPEG_PATH


def generate_waveform_peaks(
    filepath: str,
    target_peaks: int = 2000,
    ffmpeg_path: Optional[str] = None
) -> List[float]:
    """
    Extracts downsampled peak amplitudes using FFmpeg streaming PCM.
    Produces a normalized list of float peak values between 0.0 and 1.0.

    Args:
        filepath: Media file path.
        target_peaks: Number of visual peak bars to generate (e.g. 2000).
        ffmpeg_path: Custom ffmpeg path if needed.

    Returns:
        List of normalized float peaks in range [0.0, 1.0].
    """
    if not os.path.exists(filepath):
        return [0.0] * 100

    ff = ffmpeg_path or FFMPEG_PATH

    # Downsample audio stream to mono 400Hz raw 16-bit PCM
    cmd = [
        ff,
        "-hide_banner",
        "-nostats",
        "-i", filepath,
        "-ac", "1",
        "-filter:a", "aresample=400",
        "-f", "s16le",
        "-"
    ]

    creationflags = 0x08000000 if sys.platform == "win32" else 0
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=True,
            creationflags=creationflags
        )
        data = np.frombuffer(proc.stdout, dtype=np.int16)
    except Exception:
        # Fallback to zero peaks if file cannot be read
        return [0.0] * 100

    total_samples = len(data)
    if total_samples == 0:
        return [0.0] * 100

    # Compute absolute amplitude
    abs_data = np.abs(data.astype(np.float32))

    # Divide into target_peaks chunks and find max in each chunk
    chunk_size = max(1, total_samples // target_peaks)
    num_chunks = min(target_peaks, total_samples // chunk_size)

    truncated_len = num_chunks * chunk_size
    reshaped = abs_data[:truncated_len].reshape(num_chunks, chunk_size)
    peaks = reshaped.max(axis=1)

    # Normalize peaks to [0.0, 1.0] with smooth headroom
    max_val = float(peaks.max()) if len(peaks) > 0 else 0.0
    if max_val > 0:
        normalized = (peaks / max_val).tolist()
    else:
        normalized = [0.0] * num_chunks

    # Round to 3 decimal places for compactness
    return [round(p, 3) for p in normalized]
