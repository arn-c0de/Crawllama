"""
PII sanitization mixin for the memory store.
Provides safe logging of sensitive data like emails and phone numbers.
"""

import re

from utils.secure_hash import hmac_sha256_hex
from utils.logger import Logger

logger = Logger.get(__name__)


class SanitizationMixin:
    """Mixin providing PII sanitization and phone normalization."""

    def _sanitize_email_for_logging(self, email: str) -> str:
        """
        Sanitize email address for logging to prevent sensitive data exposure.
        Uses HMAC-SHA256 (keyed with an application secret) truncated to 8 characters
        for unique identification without exposing PII.

        Args:
            email: Email address to sanitize

        Returns:
            Hash-based identifier (e.g., "email_a1b2c3d4")
        """
        email_hash = hmac_sha256_hex(email, length=8)
        return f"email_{email_hash}"

    def _sanitize_phone_for_logging(self, phone: str) -> str:
        """
        Sanitize phone number for logging to prevent sensitive data exposure.
        Uses HMAC-SHA256 (keyed with an application secret) truncated to 8 characters
        for unique identification without exposing PII.

        Args:
            phone: Phone number to sanitize

        Returns:
            Hash-based identifier (e.g., "phone_a1b2c3d4")
        """
        phone_hash = hmac_sha256_hex(phone, length=8)
        return f"phone_{phone_hash}"

    def _normalize_phone(self, phone: str) -> str:
        """
        Normalize phone number to international format for duplicate detection.

        Args:
            phone: Phone number in any format

        Returns:
            Normalized phone number (international format if possible)
        """
        # Try using phonenumbers library if available
        try:
            import phonenumbers
            # Remove all non-digit characters except +
            cleaned = re.sub(r'[^\d+]', '', phone)

            # Try to parse with auto-detection
            try:
                parsed = phonenumbers.parse(cleaned, None)
            except Exception:
                # If no region code, try common regions
                for region in ['DE', 'US', 'GB']:
                    try:
                        parsed = phonenumbers.parse(cleaned, region)
                        if phonenumbers.is_valid_number(parsed):
                            break
                    except Exception as e:
                        logger.debug(f"Failed to parse phone number for region {region}: {e}")
                        continue
                else:
                    # Fallback: just digits
                    return re.sub(r'\D', '', phone)

            # Format to E164 (international format without spaces)
            return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        except ImportError:
            # Fallback without phonenumbers library: just remove all non-digits
            return re.sub(r'\D', '', phone)
