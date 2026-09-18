"""
RD Studio Auto Silence Remover — Batch Processing Queue Module
Handles multi-file workflows (e.g. full dubbing series / episodes).
Isolates errors per file so failures don't disrupt the overall batch.
"""

import os
import time
import uuid
import threading
from typing import Dict, Any, List, Optional, Callable
from .ffmpeg_wrapper import get_media_info
from .analyzer import SilenceAnalyzer
from .processor import AudioProcessor
from .exporter import get_safe_output_path
from .history import HistoryManager


class BatchManager:
    """Manages queue of media files to be analyzed and processed in batch."""

    def __init__(self, history_manager: Optional[HistoryManager] = None):
        self.history = history_manager or HistoryManager()
        self.items: List[Dict[str, Any]] = []
        self._lock = threading.Lock()
        self._is_running = False
        self._is_cancelled = False
        self._current_processor: Optional[AudioProcessor] = None
        self._current_analyzer: Optional[SilenceAnalyzer] = None

    def add_file(self, filepath: str) -> Dict[str, Any]:
        """Probes and adds a file to the batch queue."""
        with self._lock:
            # Check if file already in queue
            for it in self.items:
                if it["filepath"] == os.path.abspath(filepath):
                    return it

            info = get_media_info(filepath)
            item = {
                "id": str(uuid.uuid4())[:8],
                "filepath": info["filepath"],
                "filename": info["filename"],
                "filesize_formatted": info["filesize_formatted"],
                "duration": info["duration"],
                "duration_formatted": info["duration_formatted"],
                "audio_codec": info["audio_codec"],
                "sample_rate": info["sample_rate"],
                "channels": info["channels"],
                "is_video": info["is_video"],
                "status": "waiting",  # waiting, analyzing, processing, completed, failed, cancelled
                "stage": "Queued",
                "progress": 0.0,
                "error_message": None,
                "analysis_result": None,
                "output_path": None,
                "output_duration_formatted": None,
            }
            self.items.append(item)
            return item

    def remove_item(self, item_id: str) -> bool:
        with self._lock:
            for i, it in enumerate(self.items):
                if it["id"] == item_id:
                    if it["status"] in ("analyzing", "processing"):
                        return False  # Cannot remove currently running item
                    self.items.pop(i)
                    return True
        return False

    def clear(self):
        with self._lock:
            if not self._is_running:
                self.items = []

    def get_items(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [dict(it) for it in self.items]

    def cancel(self):
        """Cancels running batch."""
        self._is_cancelled = True
        if self._current_processor:
            self._current_processor.cancel()
        if self._current_analyzer:
            self._current_analyzer.cancel()

    def process_all(
        self,
        settings: Dict[str, Any],
        output_dir: Optional[str] = None,
        on_batch_update: Optional[Callable[[List[Dict[str, Any]]], None]] = None,
    ):
        """
        Executes batch processing on a background thread.
        Iterates through waiting or failed items.
        """
        self._is_running = True
        self._is_cancelled = False

        try:
            for item in self.items:
                if self._is_cancelled:
                    item["status"] = "cancelled"
                    item["stage"] = "Cancelled by user"
                    continue

                if item["status"] in ("completed",):
                    continue

                # 1. Analysis Stage
                item["status"] = "analyzing"
                item["stage"] = "Analyzing audio energy & silence..."
                item["progress"] = 10.0
                if on_batch_update:
                    on_batch_update(self.get_items())

                try:
                    self._current_analyzer = SilenceAnalyzer()
                    analysis = self._current_analyzer.analyze(
                        filepath=item["filepath"],
                        total_duration=item["duration"],
                        threshold_db=settings.get("threshold_db", -20.0),
                        min_silence_sec=settings.get("min_silence_sec", 0.07),
                        max_silence_sec=settings.get("max_silence_sec"),
                        action=settings.get("action", "truncate"),
                        remaining_silence_sec=settings.get("remaining_silence_sec", 0.20),
                        on_progress=lambda p, cur: None
                    )
                    item["analysis_result"] = analysis

                    if self._is_cancelled:
                        item["status"] = "cancelled"
                        item["stage"] = "Cancelled by user"
                        break

                    # 2. Processing Stage
                    item["status"] = "processing"
                    item["stage"] = "Truncating silence..."
                    item["progress"] = 25.0
                    if on_batch_update:
                        on_batch_update(self.get_items())

                    out_format = settings.get("export_format", "wav")
                    safe_output = get_safe_output_path(
                        input_path=item["filepath"],
                        output_dir=output_dir,
                        export_format=out_format,
                        suffix="_silence_removed"
                    )

                    self._current_processor = AudioProcessor()

                    def progress_cb(prog_dict):
                        item["progress"] = prog_dict.get("percentage", 25.0)
                        item["stage"] = prog_dict.get("stage", "Processing audio...")
                        if on_batch_update:
                            on_batch_update(self.get_items())

                    result = self._current_processor.process(
                        job_id=item["id"],
                        input_path=item["filepath"],
                        output_path=safe_output,
                        total_duration=item["duration"],
                        silence_regions=analysis["regions"],
                        action=settings.get("action", "truncate"),
                        remaining_silence_sec=settings.get("remaining_silence_sec", 0.20),
                        max_silence_sec=settings.get("max_silence_sec"),
                        export_format=out_format,
                        quality_id=settings.get("quality_id"),
                        sample_rate=settings.get("sample_rate", "original"),
                        channels=settings.get("channels"),
                        on_progress=progress_cb
                    )

                    item["status"] = "completed"
                    item["stage"] = "Completed"
                    item["progress"] = 100.0
                    item["output_path"] = result["output_path"]
                    item["output_duration_formatted"] = result["output_duration_formatted"]

                    # Log to history
                    self.history.add_entry({
                        "filename": item["filename"],
                        "preset": settings.get("preset_name", "RD Studio"),
                        "original_duration": item["duration_formatted"],
                        "output_duration": result["output_duration_formatted"],
                        "silence_removed": result["silence_removed_formatted"],
                        "output_path": result["output_path"],
                        "status": "Completed"
                    })

                except InterruptedError:
                    item["status"] = "cancelled"
                    item["stage"] = "Cancelled"
                except Exception as ex:
                    item["status"] = "failed"
                    item["stage"] = "Failed"
                    item["error_message"] = str(ex)

                if on_batch_update:
                    on_batch_update(self.get_items())

        finally:
            self._is_running = False
            self._current_processor = None
            self._current_analyzer = None
            if on_batch_update:
                on_batch_update(self.get_items())
