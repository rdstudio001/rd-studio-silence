"""
RD Studio Auto Silence Remover — Processing Engine
Memory-safe, high-performance silence truncation and audio generation using FFmpeg ffconcat.
Handles multi-hour recordings safely without memory bloat or UI freezes.
"""

import os
import re
import sys
import time
import uuid
import shutil
import tempfile
import subprocess
from typing import Dict, Any, List, Optional, Callable, Tuple
from .ffmpeg_wrapper import FFMPEG_PATH, format_duration
from .exporter import build_export_ffmpeg_args, get_safe_output_path
from .verifier import verify_audio_output


def build_keep_segments(
    total_duration: float,
    silence_regions: List[Dict[str, float]],
    action: str = "truncate",
    remaining_silence_sec: float = 0.20,
    max_silence_sec: Optional[float] = None
) -> List[Tuple[float, float]]:
    """
    Computes precise timeline keep intervals based on detected silence regions and configured action.
    Preserves dialogue natural timing.

    For 'truncate':
      Cuts out excess silence above remaining_silence_sec, evenly splitting
      remaining silence across preceding and succeeding speech for a natural pause.
    For 'remove':
      Removes detected silence completely.
    For 'natural':
      Preserves all natural pauses up to remaining_silence_sec, truncating longer ones.
    """
    if not silence_regions:
        return [(0.0, total_duration)] if total_duration > 0 else []

    # Sort silence regions by start time
    sorted_regions = sorted(silence_regions, key=lambda r: r["start"])
    cut_intervals: List[Tuple[float, float]] = []

    for reg in sorted_regions:
        s = max(0.0, reg["start"])
        e = min(total_duration, reg["end"])
        dur = e - s
        if dur <= 0:
            continue

        # Check maximum silence constraint
        if max_silence_sec is not None and max_silence_sec > 0 and dur > max_silence_sec:
            # Leave long pauses untouched if exceeding user-configured max
            continue

        if action == "truncate" or action == "natural":
            if dur > remaining_silence_sec:
                # Keep half remaining silence at the end of speech, half at the beginning of next speech
                half_keep = remaining_silence_sec / 2.0
                cut_start = s + half_keep
                cut_end = e - half_keep
                if cut_end > cut_start:
                    cut_intervals.append((cut_start, cut_end))
        elif action == "remove":
            cut_intervals.append((s, e))

    if not cut_intervals:
        return [(0.0, total_duration)]

    # Invert cut intervals to get keep segments
    keep_segments: List[Tuple[float, float]] = []
    current_pos = 0.0

    for cut_s, cut_e in cut_intervals:
        if cut_s > current_pos:
            # Audio segment before the cut
            dur = cut_s - current_pos
            if dur >= 0.005:  # Minimum 5ms duration to prevent tiny glitches
                keep_segments.append((round(current_pos, 4), round(cut_s, 4)))
        current_pos = max(current_pos, cut_e)

    if current_pos < total_duration:
        dur = total_duration - current_pos
        if dur >= 0.005:
            keep_segments.append((round(current_pos, 4), round(total_duration, 4)))

    return keep_segments


class AudioProcessor:
    """
    Manages long-running audio processing jobs with live stage/progress tracking and safe cancellation.
    """

    def __init__(self, ffmpeg_path: Optional[str] = None, temp_dir: Optional[str] = None):
        self.ffmpeg_path = ffmpeg_path or FFMPEG_PATH
        self.temp_dir = temp_dir or os.path.join(tempfile.gettempdir(), "rd_studio_silence_remover")
        os.makedirs(self.temp_dir, exist_ok=True)
        self._current_process: Optional[subprocess.Popen] = None
        self._is_cancelled = False

    def cancel(self):
        """Cleanly cancels active processing job and terminates subprocess."""
        self._is_cancelled = True
        if self._current_process:
            try:
                self._current_process.terminate()
            except Exception:
                pass

    def process(
        self,
        job_id: str,
        input_path: str,
        output_path: str,
        total_duration: float,
        silence_regions: List[Dict[str, float]],
        action: str = "truncate",
        remaining_silence_sec: float = 0.20,
        max_silence_sec: Optional[float] = None,
        export_format: str = "wav",
        quality_id: Optional[str] = None,
        sample_rate: Optional[str] = "original",
        channels: Optional[int] = None,
        on_progress: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        """
        Processes audio using streaming ffconcat architecture to truncate/remove silence.

        Args:
            job_id: Unique string identifier for tracking.
            input_path: Source media file path.
            output_path: Target audio file path.
            total_duration: Original file duration in seconds.
            silence_regions: List of detected silence dicts from analyzer.
            action: 'truncate', 'remove', or 'natural'.
            remaining_silence_sec: Silence to retain when truncating.
            max_silence_sec: Optional max silence threshold.
            export_format: Output container format (wav, mp3, flac, m4a, ogg).
            quality_id: Codec profile.
            sample_rate: 'original' or specific Hz string.
            channels: Channels count (1 for mono, 2 for stereo, etc.)
            on_progress: Callback reporting stage, percent, elapsed, remaining.

        Returns:
            Dict containing processing result details, output path, duration, and metrics.
        """
        self._is_cancelled = False
        start_wall_time = time.time()

        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Input media does not exist: {input_path}")

        # Compute keep segments
        if on_progress:
            on_progress({
                "job_id": job_id,
                "stage": "Computing timeline segments...",
                "percentage": 5.0,
                "elapsed_sec": 0,
                "remaining_sec": None
            })

        keep_segments = build_keep_segments(
            total_duration=total_duration,
            silence_regions=silence_regions,
            action=action,
            remaining_silence_sec=remaining_silence_sec,
            max_silence_sec=max_silence_sec
        )

        expected_output_duration = sum(e - s for s, e in keep_segments)
        if expected_output_duration <= 0:
            expected_output_duration = total_duration

        # Generate ffconcat script in temp dir
        concat_script_path = os.path.join(self.temp_dir, f"concat_{job_id}.txt")
        temp_output_path = os.path.join(self.temp_dir, f"temp_out_{job_id}.{export_format}")

        try:
            # Escape path for FFmpeg concat demuxer
            # In ffconcat, single quotes in paths are escaped as '\'':
            abs_input = os.path.abspath(input_path).replace("\\", "/")
            escaped_input = abs_input.replace("'", "'\\''")

            with open(concat_script_path, "w", encoding="utf-8") as f:
                f.write("ffconcat version 1.0\n")
                for seg_start, seg_end in keep_segments:
                    f.write(f"file '{escaped_input}'\n")
                    f.write(f"inpoint {seg_start:.4f}\n")
                    f.write(f"outpoint {seg_end:.4f}\n")

            if on_progress:
                on_progress({
                    "job_id": job_id,
                    "stage": "Processing dialogue and truncating silence...",
                    "percentage": 10.0,
                    "elapsed_sec": time.time() - start_wall_time,
                    "remaining_sec": None
                })

            # Prepare FFmpeg command
            export_args = build_export_ffmpeg_args(
                export_format=export_format,
                quality_id=quality_id,
                sample_rate=sample_rate,
                channels=channels
            )

            # Ensure parent directory of final output exists
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

            cmd = [
                self.ffmpeg_path,
                "-hide_banner",
                "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", concat_script_path,
            ] + export_args + [
                "-progress", "pipe:1",
                output_path
            ]

            creationflags = 0x08000000 if sys.platform == "win32" else 0
            # Use stderr=subprocess.STDOUT so stdout receives both progress and log lines without pipe deadlock
            self._current_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
                creationflags=creationflags
            )

            # Monitor progress via stdout
            re_time_us = re.compile(r"out_time_us=(\d+)")
            re_time_str = re.compile(r"out_time=(\d{2}:\d{2}:\d{2}\.\d+)")
            stderr_buffer = []

            for line in self._current_process.stdout:
                if self._is_cancelled:
                    self._current_process.terminate()
                    raise InterruptedError("Processing cancelled by user.")

                stderr_buffer.append(line)
                if len(stderr_buffer) > 200:
                    stderr_buffer.pop(0)

                cur_time = None
                m_us = re_time_us.search(line)
                if m_us:
                    cur_time = float(m_us.group(1)) / 1_000_000.0
                else:
                    m_str = re_time_str.search(line)
                    if m_str:
                        # Parse HH:MM:SS
                        parts = m_str.group(1).split(":")
                        if len(parts) == 3:
                            cur_time = float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])

                if cur_time is not None and expected_output_duration > 0:
                    pct = min(95.0, 10.0 + (cur_time / expected_output_duration) * 85.0)
                    elapsed = time.time() - start_wall_time
                    speed = (cur_time / elapsed) if elapsed > 0 else 0
                    remaining = ((expected_output_duration - cur_time) / speed) if speed > 0 else None

                    if on_progress:
                        on_progress({
                            "job_id": job_id,
                            "stage": "Truncating silence & writing studio audio...",
                            "percentage": round(pct, 1),
                            "current_time": cur_time,
                            "expected_total": expected_output_duration,
                            "elapsed_sec": round(elapsed, 1),
                            "remaining_sec": round(remaining, 1) if remaining else None
                        })

            self._current_process.wait()

            if self._current_process.returncode != 0 and not self._is_cancelled:
                stderr_text = "".join(stderr_buffer)
                # Friendly error formatting
                error_hint = "The audio track could not be processed."
                if "No such file" in stderr_text:
                    error_hint = "The source file or output path was not accessible."
                elif "Invalid data found" in stderr_text:
                    error_hint = "Media file appears corrupted or uses an unreadable codec."
                elif "Permission denied" in stderr_text:
                    error_hint = "Permission denied while writing output file."

                raise RuntimeError(
                    f"FFmpeg processing failed (code {self._current_process.returncode}). {error_hint}\n"
                    f"Details: {stderr_text[-400:]}"
                )

            # Stage: Verifying output
            if on_progress:
                on_progress({
                    "job_id": job_id,
                    "stage": "Verifying studio audio integrity...",
                    "percentage": 98.0,
                    "elapsed_sec": round(time.time() - start_wall_time, 1),
                    "remaining_sec": None
                })

            is_valid, err_msg, verif_details = verify_audio_output(output_path)
            if not is_valid:
                raise RuntimeError(f"Output verification failed: {err_msg}")

            final_duration = verif_details.get("duration", expected_output_duration)
            final_size = verif_details.get("size", os.path.getsize(output_path))
            total_elapsed = time.time() - start_wall_time

            if on_progress:
                on_progress({
                    "job_id": job_id,
                    "stage": "Processing Complete",
                    "percentage": 100.0,
                    "elapsed_sec": round(total_elapsed, 1),
                    "remaining_sec": 0
                })

            return {
                "job_id": job_id,
                "status": "completed",
                "output_path": os.path.abspath(output_path),
                "output_filename": os.path.basename(output_path),
                "original_duration": total_duration,
                "original_duration_formatted": format_duration(total_duration),
                "output_duration": final_duration,
                "output_duration_formatted": format_duration(final_duration),
                "silence_removed": round(max(0.0, total_duration - final_duration), 3),
                "silence_removed_formatted": format_duration(max(0.0, total_duration - final_duration)),
                "output_size": final_size,
                "segments_kept": len(keep_segments),
                "elapsed_sec": round(total_elapsed, 2)
            }

        finally:
            self._current_process = None
            # Clean up temporary concat script
            if os.path.exists(concat_script_path):
                try:
                    os.remove(concat_script_path)
                except Exception:
                    pass
            if os.path.exists(temp_output_path):
                try:
                    os.remove(temp_output_path)
                except Exception:
                    pass
