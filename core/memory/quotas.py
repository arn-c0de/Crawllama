"""
Quota management mixin for the memory store.
Enforces per-user and global entry limits.
"""

from typing import Dict

from utils.logger import get_logger

logger = get_logger(__name__)


class QuotaMixin:
    """Mixin providing quota checks for memory categories."""

    def _check_user_limit(self, category: str, user_id: str) -> bool:
        """
        Check if user has reached their quota for a category.

        Args:
            category: Memory category (emails, phones, etc.)
            user_id: User identifier

        Returns:
            True if user is within limits, False if quota exceeded
        """
        user_entries = [
            entry for entry in self.data.get(category, [])
            if entry.get('user_id') == user_id
        ]

        if len(user_entries) >= self.per_user_limit:
            logger.warning(
                f"User {user_id} reached per-user limit for {category}: "
                f"{len(user_entries)}/{self.per_user_limit}"
            )
            return False

        return True

    def _check_global_limit(self, category: str) -> bool:
        """
        Check if global quota for a category is reached.

        Args:
            category: Memory category

        Returns:
            True if within limits, False if quota exceeded
        """
        total_entries = len(self.data.get(category, []))

        if total_entries >= self.global_limit:
            logger.warning(
                f"Global limit reached for {category}: "
                f"{total_entries}/{self.global_limit}"
            )
            return False

        return True

    def get_user_quota_status(self, user_id: str) -> Dict[str, Dict[str, int]]:
        """
        Get quota status for a specific user.

        Args:
            user_id: User identifier

        Returns:
            Dictionary with usage and limits per category
        """
        status = {}
        categories = ['emails', 'phones', 'ips', 'usernames', 'domains', 'notes']

        for category in categories:
            user_entries = [
                entry for entry in self.data.get(category, [])
                if entry.get('user_id') == user_id
            ]
            status[category] = {
                'used': len(user_entries),
                'limit': self.per_user_limit,
                'remaining': max(0, self.per_user_limit - len(user_entries)),
                'percentage': int((len(user_entries) / self.per_user_limit) * 100)
            }

        return status
