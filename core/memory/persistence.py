"""
Persistence mixin for the memory store.
Handles loading from and saving to disk.
"""

import json
import os
from datetime import datetime

from utils.logger import Logger

logger = Logger.get(__name__)


class PersistenceMixin:
    """Mixin providing disk persistence for memory data."""

    @staticmethod
    def _default_data():
        """Return the default empty data structure."""
        return {
            'emails': [],
            'phones': [],
            'ips': [],
            'usernames': [],
            'domains': [],
            'notes': [],
            'created_at': None,
            'last_updated': None
        }

    def _load(self) -> None:
        """Load memory from disk."""
        try:
            if os.path.exists(self.memory_file) and os.path.getsize(self.memory_file) > 0:
                with open(self.memory_file, encoding='utf-8') as f:
                    loaded_data = json.load(f)
                    # Merge with default structure
                    self.data.update(loaded_data)
                logger.debug(f"Loaded memory from {self.memory_file}")
            else:
                # First time initialization or empty file
                self.data['created_at'] = datetime.now().isoformat()
                self._save()
                logger.info(f"Created new memory store at {self.memory_file}")
        except Exception as e:
            logger.error(f"Error loading memory: {e}")
            # Initialize with defaults if loading fails
            self.data['created_at'] = datetime.now().isoformat()
            try:
                self._save()
            except (OSError, PermissionError) as save_error:
                logger.warning(f"Could not save memory: {save_error}")
                pass  # If we can't save, at least we have data in memory

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
