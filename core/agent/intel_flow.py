"""Memory intel storage and memory-store context formatting for SearchAgent.

Extracted from agent.py as a delegation collaborator (same pattern as
ToolsFlow / OSINTFlow / ResultFlow / ContextBuilder): SearchAgent holds a
MemoryIntelFlow(self) and forwards the entry points (_auto_store_intel,
_get_memory_store_context). Methods reach back into the agent via self.agent.
"""
import logging
import re
from datetime import datetime
from typing import Any

from core.agent.constants import EMAIL_PATTERN
from core.memory_store import get_memory_store

logger = logging.getLogger("crawllama")

# Words signalling "store data from the previous answer" rather than from
# the query itself ("merke dir alle emails", "remember those")
CONTEXT_REFERENCE_KEYWORDS = [
    'alle', 'diese', 'dieses', 'das', 'die', 'those', 'that', 'them', 'all', 'the'
]
# Reference words like "email"/"phone" without an actual value also indicate
# the user wants to store something from the previous answer.
INTEL_REFERENCE_WORDS = ['email', 'phone', 'nummer', 'adresse', 'address']

# Phone number extraction patterns. The context variant additionally allows
# "/" as separator in local numbers (e.g. "04321/99 00 000").
CONTEXT_PHONE_PATTERNS = [
    r'\+\d{1,3}[\s.-]?\d{1,4}[\s.-]?\d{3,4}[\s.-]?\d{3,5}(?:[-]?\d{1,4})?',  # International: +49 40 822.268-0
    r'\d{3,5}[\s/.-]\d{3,4}[\s/.-]?\d{3,5}(?:[-]?\d{1,4})?',  # Local: 040 822268-0 or 04321/99 00 000
    r'\(\d{3,5}\)[\s.-]?\d{3,4}[\s.-]?\d{3,5}',  # (040) 822268-0
]
QUERY_PHONE_PATTERNS = [
    r'\+\d{1,3}[\s.-]?\d{1,4}[\s.-]?\d{3,4}[\s.-]?\d{3,5}(?:[-]?\d{1,4})?',  # International: +49 40 822.268-0
    r'\d{3,5}[\s.-]\d{3,4}[\s.-]?\d{3,5}(?:[-]?\d{1,4})?',  # Local: 040 822268-0
    r'\(\d{3,5}\)[\s.-]?\d{3,4}[\s.-]?\d{3,5}',  # (040) 822268-0
]

NOTE_URL_PATTERN = re.compile(r'https?://[^\s<>"\']+')
PHONE_DIGIT_FILTER = re.compile(r'[^\d]')
LOOSE_PHONE_PATTERN = re.compile(r'\+?\d[\d\s.-]{6,}')
MIN_PHONE_DIGITS = 6


class MemoryIntelFlow:
    """Store OSINT intel into the memory store and format it back into context."""

    def __init__(self, agent):
        self.agent = agent

    def _auto_store_intel(self, query: str) -> None:
        """
        Automatically extract and store emails, phones, URLs from query.

        Args:
            query: User query containing intel to store
        """
        try:
            memory = get_memory_store()
            query_lower = query.lower()
            stored_count = 0

            # Check if user wants to store URLs as notes
            store_urls_as_notes = 'notes' in query_lower or 'notiz' in query_lower

            if self._wants_store_from_context(query) and self.agent.session.conversation_history:
                last_response = self.agent.session.conversation_history[-1].get('response', '')
                stored_count += self._store_intel_from_text(
                    memory,
                    last_response,
                    source='context',
                    phone_patterns=CONTEXT_PHONE_PATTERNS,
                    store_urls_as_notes=store_urls_as_notes,
                )

            # Extract directly from query
            stored_count += self._store_intel_from_text(
                memory,
                query,
                source='user_query',
                phone_patterns=QUERY_PHONE_PATTERNS,
            )

            if stored_count > 0:
                logger.info(f"✅ Auto-stored {stored_count} intelligence items from query")
            else:
                logger.debug("No intelligence items found to store")

        except Exception as e:
            logger.error(f"Failed to auto-store intel: {e}", exc_info=True)

    @staticmethod
    def _wants_store_from_context(query: str) -> bool:
        """Check if the user wants to store intel from the previous answer."""
        query_lower = query.lower()

        # Reference words like "alle", "diese", "those" point at previous output
        if any(keyword in query_lower for keyword in CONTEXT_REFERENCE_KEYWORDS):
            return True

        # "merke die email" / "remember the phone" without an actual value also
        # indicates the user wants to store from context
        has_reference_words = any(word in query_lower for word in INTEL_REFERENCE_WORDS)
        has_actual_value = bool(EMAIL_PATTERN.findall(query)) or bool(LOOSE_PHONE_PATTERN.findall(query))
        return has_reference_words and not has_actual_value

    def _store_intel_from_text(
        self,
        memory,
        text: str,
        source: str,
        phone_patterns: list[str],
        store_urls_as_notes: bool = False,
    ) -> int:
        """Extract and store URLs, emails, and phones from a text. Returns the count."""
        stored_count = 0

        if store_urls_as_notes:
            stored_count += self._store_urls_as_notes(memory, text, source)

        for email in EMAIL_PATTERN.findall(text):
            metadata = {'source': source, 'timestamp': datetime.now().isoformat()}
            if memory.remember_email(email, metadata=metadata):
                # Email is already sanitized in memory.remember_email() logging
                stored_count += 1

        stored_count += self._store_phones(memory, text, phone_patterns, source)
        return stored_count

    @staticmethod
    def _store_urls_as_notes(memory, text: str, source: str) -> int:
        """Store all URLs found in the text as notes. Returns the count."""
        stored_count = 0
        for url in NOTE_URL_PATTERN.findall(text):
            metadata = {'source': source, 'timestamp': datetime.now().isoformat()}
            if memory.add_note(f"URL: {url}", metadata=metadata):
                logger.info("Auto-stored URL as note")  # lgtm[py/clear-text-logging-sensitive-data] - URL omitted to avoid logging content
                stored_count += 1
        return stored_count

    @staticmethod
    def _store_phones(memory, text: str, phone_patterns: list[str], source: str) -> int:
        """Store phone numbers matching any of the patterns. Returns the count."""
        stored_count = 0
        for pattern in phone_patterns:
            for phone in re.findall(pattern, text):
                # Only store if it looks like a real phone (at least 6 digits)
                digits_only = PHONE_DIGIT_FILTER.sub('', phone)
                if len(digits_only) < MIN_PHONE_DIGITS:
                    continue
                metadata = {'source': source, 'timestamp': datetime.now().isoformat()}
                if memory.remember_phone(phone.strip(), metadata=metadata):
                    # Phone is already sanitized in memory.remember_phone() logging
                    stored_count += 1
        return stored_count

    def _get_memory_store_context(self) -> str:
        """
        Get formatted context from Memory Store.

        Returns:
            Formatted string with all stored intelligence
        """
        try:
            memory = get_memory_store()
            summary = memory.get_summary()

            if summary['total_entries'] == 0:
                return "💾 Memory Store: No entries saved."

            context_parts = ["💾 Stored Information (Memory Store):"]
            context_parts.extend(self._format_memory_emails(memory, summary))
            context_parts.extend(self._format_memory_category(memory, summary, 'phones', '📱 Phone numbers'))
            context_parts.extend(self._format_memory_category(memory, summary, 'ips', '🌐 IP addresses'))
            context_parts.extend(self._format_memory_category(memory, summary, 'usernames', '👤 Usernames'))
            context_parts.extend(self._format_memory_category(memory, summary, 'domains', '🔗 Domains'))
            context_parts.extend(self._format_memory_notes(memory, summary))

            return "\n".join(context_parts)

        except Exception as e:
            logger.error(f"Failed to get memory store context: {e}", exc_info=True)
            return "💾 Memory Store: Error retrieving data."

    def _format_memory_emails(self, memory, summary: dict[str, Any]) -> list[str]:
        """Format the email section including breach status (max 10 entries)."""
        if summary['emails'] == 0:
            return []

        lines = [f"\n📧 Email addresses ({summary['emails']}):"]
        for item in memory.data.get('emails', [])[:10]:  # Max 10
            lines.append(self._format_email_entry(item))
        if summary['emails'] > 10:
            lines.append(f"  ... and {summary['emails'] - 10} more")
        return lines

    @staticmethod
    def _format_email_entry(item: dict[str, Any]) -> str:
        """Format one stored email with its breach status, if available."""
        email_display = f"  • {item['value']}"

        breach_data = item.get('metadata', {}).get('breach_data', {})
        if not breach_data:
            return email_display

        hibp = breach_data.get('hibp', {})
        if not (hibp and hibp.get('pwned')):
            return email_display + " ✅ CLEAN"

        breach_count = hibp.get('breach_count', 0)
        severity = hibp.get('severity', 'unknown').upper()
        email_display += f" ⚠️ COMPROMISED ({breach_count} breaches, {severity})"

        breaches = hibp.get('breaches', [])
        if breaches:
            breach_names = [b.get('Name') or b.get('name') or b.get('Title', 'Unknown')
                          for b in breaches[:3]]
            email_display += f"\n      Breaches: {', '.join(breach_names)}"
            if len(breaches) > 3:
                email_display += f" (+{len(breaches)-3} more)"

        return email_display

    @staticmethod
    def _format_memory_category(
        memory,
        summary: dict[str, Any],
        key: str,
        header: str,
        max_items: int = 10,
    ) -> list[str]:
        """Format a simple value-list memory category (phones, ips, ...)."""
        count = summary[key]
        if count == 0:
            return []

        lines = [f"\n{header} ({count}):"]
        for item in memory.data.get(key, [])[:max_items]:
            lines.append(f"  • {item['value']}")
        if count > max_items:
            lines.append(f"  ... and {count - max_items} more")
        return lines

    @staticmethod
    def _format_memory_notes(memory, summary: dict[str, Any]) -> list[str]:
        """Format the notes section (max 5 entries, truncated content)."""
        if summary['notes'] == 0:
            return []

        lines = [f"\n📝 Notes ({summary['notes']}):"]
        for item in memory.data.get('notes', [])[:5]:
            lines.append(f"  • {item['content'][:100]}...")
        if summary['notes'] > 5:
            lines.append(f"  ... and {summary['notes'] - 5} more")
        return lines
