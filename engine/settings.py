"""
RD Studio Auto Silence Remover — Application Settings Module
Handles persistent configuration (export folder, temp directory, defaults).
"""

import os
import json
from typing import Dict, Any


class SettingsManager:
    """Manages application settings stored in data/settings.json."""

    def __init__(self, filepath: str = None):
        if filepath:
            self.filepath = filepath
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.filepath = os.path.join(base_dir, "data", "settings.json")

        self.defaults = {
            "export_dir": os.path.join(os.path.expanduser("~"), "Music", "RD_Studio_Exports"),
            "temp_dir": os.path.join(os.path.expanduser("~"), "AppData", "Local", "Temp", "rd_studio_silence_remover"),
            "default_preset": "rd_studio_dialogue_cut",
            "default_export_format": "wav",
            "default_quality": "pcm_24",
            "default_sample_rate": "original",
            "auto_clean_temp": True,
            "confirm_overwrite": True,
            "theme": "dark_studio",
        }
        self.settings = dict(self.defaults)
        self.load()

    def load(self):
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    self.settings.update(saved)
            except Exception:
                pass

    def save(self):
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=2)
        except Exception as e:
            print(f"Error saving settings: {e}")

    def get(self, key: str, default=None):
        return self.settings.get(key, default)

    def set(self, key: str, value: Any):
        self.settings[key] = value
        self.save()

    def update_all(self, new_data: Dict[str, Any]):
        self.settings.update(new_data)
        self.save()
        return self.settings
