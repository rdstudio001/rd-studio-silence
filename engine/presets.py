"""
RD Studio Auto Silence Remover — Presets Management System
Handles factory dubbing presets, custom user presets, validation, and JSON persistence.
"""

import os
import json
from typing import Dict, Any, List, Optional


DEFAULT_PRESET_ID = "rd_studio_dialogue_cut"

FACTORY_PRESETS: List[Dict[str, Any]] = [
    {
        "id": "rd_studio_dialogue_cut",
        "name": "RD Studio — Dialogue Silence Cut",
        "description": "Optimized starting point for professional Urdu, Hindi & Asian drama/anime dubbing.",
        "threshold_db": -20.0,
        "min_silence_sec": 0.07,
        "max_silence_sec": None,
        "action": "truncate",
        "remaining_silence_sec": 0.20,
        "is_builtin": True
    },
    {
        "id": "natural_dialogue",
        "name": "Natural Dialogue",
        "description": "Less aggressive cut preserving natural conversational breathing and relaxed pauses.",
        "threshold_db": -24.0,
        "min_silence_sec": 0.15,
        "max_silence_sec": None,
        "action": "truncate",
        "remaining_silence_sec": 0.30,
        "is_builtin": True
    },
    {
        "id": "standard_dubbing",
        "name": "Standard Dubbing",
        "description": "Balanced dialogue processing for fast-paced TV serials and voice-over workflows.",
        "threshold_db": -20.0,
        "min_silence_sec": 0.08,
        "max_silence_sec": None,
        "action": "truncate",
        "remaining_silence_sec": 0.18,
        "is_builtin": True
    },
    {
        "id": "aggressive_silence_cut",
        "name": "Aggressive Silence Cut",
        "description": "Rapid pacing with minimal gaps, ideal for fast promos, game dubs, and trailers.",
        "threshold_db": -18.0,
        "min_silence_sec": 0.05,
        "max_silence_sec": None,
        "action": "truncate",
        "remaining_silence_sec": 0.10,
        "is_builtin": True
    }
]


class PresetManager:
    """Manages preset loading, saving, deletion, and validation."""

    def __init__(self, storage_path: Optional[str] = None):
        if storage_path:
            self.storage_path = storage_path
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            data_dir = os.path.join(base_dir, "data")
            os.makedirs(data_dir, exist_ok=True)
            self.storage_path = os.path.join(data_dir, "presets.json")

        self.presets: List[Dict[str, Any]] = []
        self.load_presets()

    def load_presets(self):
        """Loads presets from file, combining factory presets with user presets."""
        user_presets = []
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        user_presets = [p for p in data if not p.get("is_builtin")]
            except Exception:
                user_presets = []

        # Merge factory and user presets
        self.presets = [dict(p) for p in FACTORY_PRESETS] + user_presets

    def save_presets(self):
        """Saves only user-defined presets to disk."""
        user_presets = [p for p in self.presets if not p.get("is_builtin")]
        try:
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(user_presets, f, indent=2)
        except Exception as e:
            print(f"Failed to save presets: {e}")

    def get_all(self) -> List[Dict[str, Any]]:
        """Returns all available presets."""
        return self.presets

    def get_by_id(self, preset_id: str) -> Optional[Dict[str, Any]]:
        """Finds preset by ID, falling back to default preset if not found."""
        for p in self.presets:
            if p["id"] == preset_id:
                return dict(p)
        # Fallback to default
        return dict(FACTORY_PRESETS[0])

    def create_or_update_custom(
        self,
        name: str,
        threshold_db: float,
        min_silence_sec: float,
        action: str,
        remaining_silence_sec: float,
        max_silence_sec: Optional[float] = None,
        preset_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Creates or updates a custom preset."""
        import re

        clean_name = name.strip()
        if not clean_name:
            clean_name = "Custom Preset"

        if not preset_id:
            slug = re.sub(r'[^a-zA-Z0-9_]', '_', clean_name.lower())[:20]
            preset_id = f"custom_{slug}_{os.urandom(3).hex()}"

        # Prevent overwriting built-in presets
        for bp in FACTORY_PRESETS:
            if bp["id"] == preset_id:
                preset_id = f"custom_{preset_id}_{os.urandom(3).hex()}"
                break

        preset_data = {
            "id": preset_id,
            "name": clean_name,
            "description": "User-defined custom dialogue preset.",
            "threshold_db": round(float(threshold_db), 2),
            "min_silence_sec": round(float(min_silence_sec), 3),
            "max_silence_sec": round(float(max_silence_sec), 3) if max_silence_sec else None,
            "action": action,
            "remaining_silence_sec": round(float(remaining_silence_sec), 3),
            "is_builtin": False
        }

        # Check if already exists in list
        updated = False
        for i, p in enumerate(self.presets):
            if p["id"] == preset_id and not p.get("is_builtin"):
                self.presets[i] = preset_data
                updated = True
                break

        if not updated:
            self.presets.append(preset_data)

        self.save_presets()
        return preset_data

    def delete_preset(self, preset_id: str) -> bool:
        """Deletes custom preset. Built-in presets cannot be deleted."""
        for p in self.presets:
            if p["id"] == preset_id:
                if p.get("is_builtin"):
                    raise ValueError("Built-in RD Studio factory presets cannot be deleted.")
                self.presets = [x for x in self.presets if x["id"] != preset_id]
                self.save_presets()
                return True
        return False
