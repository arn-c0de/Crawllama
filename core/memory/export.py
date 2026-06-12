"""
Export/import mixin for the memory store.
Handles JSON export, snapshot generation, and JSON import.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import TextIO

from utils.logger import get_logger

logger = get_logger(__name__)

SNAPSHOT_DIVIDER = "═══════════════════════════════════════════════════════════"


class ExportImportMixin:
    """Mixin providing export and import operations."""

    def export_to_json(self, filepath: str) -> bool:
        """
        Export memory to a JSON file.

        Args:
            filepath: Export destination

        Returns:
            True on success
        """
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
            logger.info(f"Exported memory to {filepath}")
            return True
        except Exception as e:
            logger.error(f"Error exporting memory: {e}")
            return False

    def export_memory_snapshot(self, export_dir: str = "data/exports") -> dict:
        """
        Export current memory state to a timestamped file with both JSON and readable formats.

        Args:
            export_dir: Directory for exports (default: data/exports)

        Returns:
            Dictionary with export details (filepath, timestamp, counts)
        """
        try:
            # Create export directory if it doesn't exist
            export_path = Path(export_dir)
            export_path.mkdir(parents=True, exist_ok=True)

            # Generate timestamp-based filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            json_file = export_path / f"memory_export_{timestamp}.json"
            txt_file = export_path / f"memory_export_{timestamp}.txt"

            # Export JSON (complete data)
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)

            # Export human-readable text
            with open(txt_file, 'w', encoding='utf-8') as f:
                stats = self._write_snapshot_header_and_summary(f)
                self._write_snapshot_emails(f)
                self._write_snapshot_phones(f)
                self._write_snapshot_ips(f)
                self._write_snapshot_usernames(f)
                self._write_snapshot_domains(f)
                self._write_snapshot_notes(f)

            logger.info(f"Memory snapshot exported to {export_dir}/memory_export_{timestamp}.*")
            return {
                'success': True,
                'json_file': str(json_file),
                'txt_file': str(txt_file),
                'timestamp': timestamp,
                'total_entries': stats['total_entries'],
                'categories': {
                    'emails': stats['emails'],
                    'phones': stats['phones'],
                    'ips': stats['ips'],
                    'usernames': stats['usernames'],
                    'domains': stats['domains'],
                    'notes': stats['notes']
                }
            }

        except Exception as e:
            logger.error(f"Error creating memory snapshot: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }

    def _write_snapshot_header_and_summary(self, f: TextIO) -> dict:
        """Write the snapshot header and summary block; return the summary stats."""
        f.write(f"{SNAPSHOT_DIVIDER}\n")
        f.write(f"  CrawlLama Memory Export - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"{SNAPSHOT_DIVIDER}\n\n")

        # Summary — BUG FIX: was self.get_stats(), now self.get_summary()
        stats = self.get_summary()
        f.write("SUMMARY:\n")
        f.write(f"  Total Entries: {stats['total_entries']}\n")
        f.write(f"  Emails: {stats['emails']}\n")
        f.write(f"  Phones: {stats['phones']}\n")
        f.write(f"  IPs: {stats['ips']}\n")
        f.write(f"  Usernames: {stats['usernames']}\n")
        f.write(f"  Domains: {stats['domains']}\n")
        f.write(f"  Notes: {stats['notes']}\n\n")
        return stats

    def _write_snapshot_emails(self, f: TextIO) -> None:
        """Write email entries (with breach info) to the snapshot."""
        if not self.data.get('emails'):
            return

        f.write("═══ EMAILS ═══\n\n")
        for email in self.data['emails']:
            f.write(f"📧 {email['value']}\n")
            f.write(f"   Added: {email.get('added_at', 'N/A')}\n")
            f.write(f"   User: {email.get('user_id', 'default')}\n")
            self._write_snapshot_breach_info(f, email)
            f.write("\n")

    def _write_snapshot_breach_info(self, f: TextIO, email: dict) -> None:
        """Write breach data for a single email entry, if available."""
        breach_data = email.get('metadata', {}).get('breach_data', {})
        if not breach_data:
            return

        hibp = breach_data.get('hibp', {})
        vuln = breach_data.get('vulnerability', {})

        if hibp and hibp.get('pwned'):
            f.write(f"   ⚠️  BREACH STATUS: COMPROMISED\n")
            f.write(f"       Breaches: {hibp.get('breach_count', 0)}\n")
            f.write(f"       Pastes: {hibp.get('paste_count', 0)}\n")

        if vuln and vuln.get('vulnerable'):
            f.write(f"   🔓 VULNERABILITY: EXPOSED\n")
            f.write(f"       Leak Count: {vuln.get('leak_count', 0)}\n")
            f.write(f"       Sources: {', '.join(vuln.get('found_in', [])[:3])}\n")

    def _write_snapshot_phones(self, f: TextIO) -> None:
        """Write phone number entries to the snapshot."""
        if not self.data.get('phones'):
            return

        f.write("═══ PHONE NUMBERS ═══\n\n")
        for phone in self.data['phones']:
            f.write(f"📱 {phone['value']}\n")
            f.write(f"   Added: {phone.get('added_at', 'N/A')}\n")
            metadata = phone.get('metadata', {})
            if metadata.get('country'):
                f.write(f"   Country: {metadata['country']}\n")
            if metadata.get('carrier'):
                f.write(f"   Carrier: {metadata['carrier']}\n")
            f.write("\n")

    def _write_snapshot_ips(self, f: TextIO) -> None:
        """Write IP address entries to the snapshot."""
        if not self.data.get('ips'):
            return

        f.write("═══ IP ADDRESSES ═══\n\n")
        for ip in self.data['ips']:
            f.write(f"🌐 {ip['value']}\n")
            f.write(f"   Added: {ip.get('added_at', 'N/A')}\n")
            metadata = ip.get('metadata', {})
            if metadata.get('location'):
                f.write(f"   Location: {metadata['location']}\n")
            f.write("\n")

    def _write_snapshot_usernames(self, f: TextIO) -> None:
        """Write username entries to the snapshot."""
        if not self.data.get('usernames'):
            return

        f.write("═══ USERNAMES ═══\n\n")
        for username in self.data['usernames']:
            f.write(f"👤 {username['value']}\n")
            f.write(f"   Added: {username.get('added_at', 'N/A')}\n")
            metadata = username.get('metadata', {})
            if metadata.get('platforms'):
                f.write(f"   Platforms: {', '.join(metadata['platforms'][:5])}\n")
            f.write("\n")

    def _write_snapshot_domains(self, f: TextIO) -> None:
        """Write domain entries to the snapshot."""
        if not self.data.get('domains'):
            return

        f.write("═══ DOMAINS ═══\n\n")
        for domain in self.data['domains']:
            f.write(f"🔗 {domain['value']}\n")
            f.write(f"   Added: {domain.get('added_at', 'N/A')}\n")
            f.write("\n")

    def _write_snapshot_notes(self, f: TextIO) -> None:
        """Write note entries to the snapshot."""
        if not self.data.get('notes'):
            return

        f.write("═══ NOTES ═══\n\n")
        for note in self.data['notes']:
            f.write(f"📝 {note['text'][:100]}{'...' if len(note['text']) > 100 else ''}\n")
            f.write(f"   Added: {note.get('added_at', 'N/A')}\n")
            if note.get('category'):
                f.write(f"   Category: {note['category']}\n")
            f.write("\n")

    def import_from_json(self, filepath: str, merge: bool = True) -> bool:
        """
        Import memory from a JSON file.

        Args:
            filepath: Import source
            merge: If True, merge with existing data; if False, replace

        Returns:
            True on success
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                imported_data = json.load(f)

            if merge:
                # Merge data
                for category in ['emails', 'phones', 'ips', 'usernames', 'domains', 'notes']:
                    if category in imported_data:
                        existing_values = {item['value'] for item in self.data.get(category, []) if 'value' in item}
                        for item in imported_data[category]:
                            if 'value' in item and item['value'] not in existing_values:
                                self.data.setdefault(category, []).append(item)
                            elif 'text' in item:  # Notes don't have 'value'
                                self.data.setdefault(category, []).append(item)
            else:
                # Replace data
                self.data = imported_data

            self._save()
            logger.info(f"Imported memory from {filepath}")
            return True
        except Exception as e:
            logger.error(f"Error importing memory: {e}")
            return False
