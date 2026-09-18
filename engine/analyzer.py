"""
RD Studio Auto Silence Remover — Silence Detection & Analysis Module
Accurately detects silent regions using FFmpeg silencedetect, computes exact metrics,
and predicts post-processed duration without memory duplication.
"""

import os
import re
import sys
import subprocess
from typing import Dict, Any, List, Optional, Callable
from .ffmpeg_wrapper import FFMPEG_PATH, format_duration


class SilenceAnalyzer:
    """
    Analyzes audio amplitude/energy to detect silent sections based on threshold and duration.
    """

    def __init__(self, ffmpeg_path: Optional[str] = None):
        self.ffmpeg_path = ffmpeg_path or FFMPEG_PATH
        self._is_cancelled = False
        self._current_process: Optional[subprocess.Popen] = None

    def cancel(self):
        """Signals cancellation and terminates running FFmpeg process."""
        self._is_cancelled = True
        if self._current_process:
            try:
                self._current_process.terminate()
            except Exception:
                pass

    def analyze(
        self,
        filepath: str,
        total_duration: float,
        threshold_db: float = -20.0,
        min_silence_sec: float = 0.07,
        max_silence_sec: Optional[float] = None,
        action: str = "truncate",
        remaining_silence_sec: float = 0.20,
        on_progress: Optional[Callable[[float, float], None]] = None,
    ) -> Dict[str, Any]:
        """
        Runs FFmpeg silencedetect filter and parses silent regions in real-time.

        Args:
            filepath: Path to audio or video media file.
            total_duration: Total duration of file in seconds.
            threshold_db: Amplitude threshold in dB (e.g. -20.0).
            min_silence_sec: Minimum duration in seconds to qualify as silence.
            max_silence_sec: Optional maximum silence duration.
            action: 'truncate', 'remove', or 'natural'.
            remaining_silence_sec: Remaining silence duration to keep when truncating.
            on_progress: Callback(percent: float, current_time: float)

        Returns:
            Dict containing detected silence regions, counts, durations, and predictions.
        """
        self._is_cancelled = False

        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Media file not found: {filepath}")

        # Input validation
        if threshold_db > 0:
            threshold_db = 0.0
        if threshold_db < -100.0:
            threshold_db = -100.0
        if min_silence_sec < 0.001:
            min_silence_sec = 0.001
        if remaining_silence_sec < 0:
            remaining_silence_sec = 0.0

        filter_arg = f"silencedetect=noise={threshold_db:.2f}dB:d={min_silence_sec:.4f}"

        cmd = [
            self.ffmpeg_path,
            "-hide_banner",
            "-nostats",
            "-i", filepath,
            "-af", filter_arg,
            "-f", "null",
            "-"
        ]

        creationflags = 0x08000000 if sys.platform == "win32" else 0
        self._current_process = subprocess.Popen(
            cmd,
            stderr=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            text=True,
            bufsize=1,
            universal_newlines=True,
            creationflags=creationflags
        )

        detected_regions: List[Dict[str, float]] = []
        current_start: Optional[float] = None

        # Regex patterns for silencedetect output
        re_start = re.compile(r"silence_start:\s*([0-9\.\-]+)")
        re_end = re.compile(r"silence_end:\s*([0-9\.\-]+)\s*\|\s*silence_duration:\s*([0-9\.\-]+)")

        try:
            for line in self._current_process.stderr:
                if self._is_cancelled:
                    self._current_process.terminate()
                    raise InterruptedError("Analysis cancelled by user.")

                if "silence_start:" in line:
                    m = re_start.search(line)
                    if m:
                        try:
                            val = float(m.group(1))
                            current_start = max(0.0, val)
                            if on_progress and total_duration > 0:
                                pct = min(99.0, (current_start / total_duration) * 100.0)
                                on_progress(pct, current_start)
                        except ValueError:
                            pass

                elif "silence_end:" in line:
                    m = re_end.search(line)
                    if m:
                        try:
                            end_val = float(m.group(1))
                            dur_val = float(m.group(2))
                            start_val = current_start if current_start is not None else max(0.0, end_val - dur_val)

                            # Clamp within total duration
                            if total_duration > 0:
                                end_val = min(total_duration, end_val)

                            if end_val > start_val:
                                detected_regions.append({
                                    "start": round(start_val, 4),
                                    "end": round(end_val, 4),
                                    "duration": round(dur_val, 4)
                                })
                            current_start = None

                            if on_progress and total_duration > 0:
                                pct = min(99.0, (end_val / total_duration) * 100.0)
                                on_progress(pct, end_val)
                        except ValueError:
                            pass

            self._current_process.wait()

            # Handle case where file ends while in silence
            if current_start is not None and total_duration > current_start:
                final_dur = total_duration - current_start
                if final_dur >= min_silence_sec:
                    detected_regions.append({
                        "start": round(current_start, 4),
                        "end": round(total_duration, 4),
                        "duration": round(final_dur, 4)
                    })

        finally:
            self._current_process = None

        if on_progress:
            on_progress(100.0, total_duration)

        # Calculate statistics based on selected action and settings
        total_silence_duration = 0.0
        total_reduction = 0.0

        for reg in detected_regions:
            dur = reg["duration"]
            total_silence_duration += dur

            # Check max silence constraint if configured
            if max_silence_sec is not None and max_silence_sec > 0 and dur > max_silence_sec:
                # Long silence region exceeds user threshold; leave natural or cap
                continue

            if action == "truncate":
                if dur > remaining_silence_sec:
                    total_reduction += (dur - remaining_silence_sec)
            elif action == "remove":
                total_reduction += dur
            elif action == "natural":
                # Keep natural silence: only remove excess beyond remaining_silence
                if dur > remaining_silence_sec:
                    total_reduction += (dur - remaining_silence_sec)

        estimated_output = max(0.0, total_duration - total_reduction)

        return {
            "regions_count": len(detected_regions),
            "regions": detected_regions,
            "total_silence_duration": round(total_silence_duration, 3),
            "total_silence_formatted": format_duration(total_silence_duration),
            "estimated_reduction": round(total_reduction, 3),
            "estimated_reduction_formatted": format_duration(total_reduction),
            "estimated_output_duration": round(estimated_output, 3),
            "estimated_output_formatted": format_duration(estimated_output),
            "original_duration": round(total_duration, 3),
            "original_duration_formatted": format_duration(total_duration),
            "threshold_db": threshold_db,
            "min_silence_sec": min_silence_sec,
            "max_silence_sec": max_silence_sec,
            "remaining_silence_sec": remaining_silence_sec,
            "action": action,
        }
