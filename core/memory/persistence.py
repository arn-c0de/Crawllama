"""
Persistence mixin for the memory store.
Handles loading from and saving to disk.
"""

import json
import os
from datetime import datetime

from utils.logger import Logger

from .constants import CATEGORIES

logger = Logger.get(__name__)


class PersistenceMixin:
    """Mixin providing disk persistence for memory data."""

    @staticmethod
    def _default_data():
        """Return the default empty data structure."""
        data: dict = {category: [] for category in CATEGORIES}
        data['created_at'] = None
        data['last_updated'] = None
        return data

    def _load(self) -> None:
        """Load memory from disk.

        A corrupt or unreadable file is moved aside (``*.corrupt``) instead of
        being overwritten with empty defaults, so stored intel is never lost.
        """
        if not os.path.exists(self.memory_file) or os.path.getsize(self.memory_file) == 0:
            # First time initialization or empty file
            self.data['created_at'] = datetime.now().isoformat()
            self._try_save()
            logger.info(f"Created new memory store at {self.memory_file}")
            return

        try:
            with open(self.memory_file, encoding='utf-8') as f:
                loaded_data = json.load(f)
            if not isinstance(loaded_data, dict):
                raise ValueError("memory file does not contain a JSON object")
        except Exception as e:
            logger.error(f"Error loading memory: {e}")
            self._quarantine_corrupt_file()
            self.data['created_at'] = datetime.now().isoformat()
            self._try_save()
            return

        # Merge with default structure, ignoring malformed categories
        for key, value in loaded_data.items():
            if key in CATEGORIES and not isinstance(value, list):
                logger.warning(f"Ignoring malformed memory category '{key}'")
                continue
            self.data[key] = value
        logger.debug(f"Loaded memory from {self.memory_file}")

    def _quarantine_corrupt_file(self) -> None:
        """Move an unreadable memory file aside so it can be recovered manually."""
        backup = f"{self.memory_file}.corrupt"
        try:
            os.replace(self.memory_file, backup)
            logger.warning(f"Corrupt memory file moved to {backup}")
        except OSError as e:
            logger.warning(f"Could not back up corrupt memory file: {e}")

    def _try_save(self) -> None:
        """Save, tolerating an unwritable location (data stays in memory)."""
        try:
            self._save()
        except OSError as save_error:
            logger.warning(f"Could not save memory: {save_error}")

    def _save(self) -> None:
        """Save memory to disk."""
        try:
            # Ensure directory exists
            dir_path = os.path.dirname(self.memory_file)
            if dir_path:  # Only create if there's a directory component
                os.makedirs(dir_path, exist_ok=True)

            # Update timestamp
            self.data['last_updated'] = datetime.now().isoformat()

            # Write to a temp file and rename: a crash mid-write cannot
            # truncate/corrupt the existing memory file.
            tmp_file = f"{self.memory_file}.tmp"
            with open(tmp_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
            os.replace(tmp_file, self.memory_file)
            logger.debug(f"Saved memory to {self.memory_file}")
        except Exception as e:
            logger.error(f"Error saving memory: {e}")
