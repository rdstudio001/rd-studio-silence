"""
RD Studio Auto Silence Remover — Processing History Module
Maintains a lightweight local log of completed processing jobs without duplicating audio files.
"""

import os
import json
import time
from typing import Dict, Any, List, Optional


class HistoryManager:
    """Stores metadata records of processed files."""

    def __init__(self, filepath: Optional[str] = None):
        if filepath:
            self.filepath = filepath
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.filepath = os.path.join(base_dir, "data", "history.json")
        self.records: List[Dict[str, Any]] = []
        self.load()

    def load(self):
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    self.records = json.load(f)
            except Exception:
                self.records = []

    def save(self):
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self.records, f, indent=2)
        except Exception as e:
            print(f"Error saving history: {e}")

    def add_entry(self, entry: Dict[str, Any]):
        """Adds a new processing record."""
        entry["timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S")
        self.records.insert(0, entry)
        # Cap at 200 records to keep file lightweight
        if len(self.records) > 200:
            self.records = self.records[:200]
        self.save()

    def get_all(self) -> List[Dict[str, Any]]:
        return self.records

    def clear(self):
        self.records = []
        self.save()
