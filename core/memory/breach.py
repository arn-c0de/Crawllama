"""
Breach intelligence mixin for the memory store.
Handles breach/vulnerability data for email addresses.
"""

from datetime import datetime
from typing import Dict, Optional

from utils.logger import Logger

logger = Logger.get(__name__)


class BreachIntelMixin:
    """Mixin providing breach intelligence operations."""

    def update_email_breach_info(self, email: str, breach_info: Dict, vuln_info: Dict = None) -> bool:
        """
        Update breach/vulnerability information for an email.

        Args:
            email: Email address to update
            breach_info: Breach data from HIBP or similar
            vuln_info: Vulnerability data from leak checks

        Returns:
            True if updated, False if email not found
        """
        email = email.lower().strip()
        entry = next((e for e in self.data['emails'] if e['value'] == email), None)

        if not entry:
            sanitized_email = self._sanitize_email_for_logging(email)
            logger.warning(f"Email {sanitized_email} not found in memory for breach update")
            return False

        # Initialize breach_data if not exists
        if 'breach_data' not in entry['metadata']:
            entry['metadata']['breach_data'] = {}

        # Update breach information
        entry['metadata']['breach_data']['last_checked'] = datetime.now().isoformat()

        if breach_info:
            entry['metadata']['breach_data']['hibp'] = {
                'pwned': breach_info.get('pwned', False),
                'breach_count': breach_info.get('breach_count', 0),
                'paste_count': breach_info.get('paste_count', 0),
                'severity': breach_info.get('severity', 'none'),
                'last_breach': breach_info.get('last_breach'),
                'breaches': breach_info.get('breaches', [])[:5]  # Store only first 5
            }

        if vuln_info:
            entry['metadata']['breach_data']['vulnerability'] = {
                'vulnerable': vuln_info.get('vulnerable', False),
                'leak_count': vuln_info.get('leak_count', 0),
                'severity': vuln_info.get('severity', 'none'),
                'found_in': vuln_info.get('found_in', []),
                'breach_sources': vuln_info.get('breach_sources', [])[:10]  # Store first 10
            }

        entry['last_updated'] = datetime.now().isoformat()
        self._save()

        sanitized_email = self._sanitize_email_for_logging(email)
        logger.info(f"Updated breach info for email: {sanitized_email}")
        return True

    def get_email_with_breach_info(self, email: str) -> Optional[Dict]:
        """
        Get email entry with formatted breach information.

        Args:
            email: Email address to retrieve

        Returns:
            Dictionary with email and breach data, or None if not found
        """
        email = email.lower().strip()
        entry = next((e for e in self.data['emails'] if e['value'] == email), None)

        if not entry:
            return None

        # Format breach data for display
        result = {
            'email': entry['value'],
            'added_at': entry.get('added_at'),
            'last_updated': entry.get('last_updated'),
            'metadata': entry.get('metadata', {}),
            'breach_summary': None
        }

        breach_data = entry.get('metadata', {}).get('breach_data', {})
        if breach_data:
            summary = {
                'last_checked': breach_data.get('last_checked'),
                'status': 'SAFE',
                'details': []
            }

            # HIBP data
            hibp = breach_data.get('hibp', {})
            if hibp and hibp.get('pwned'):
                summary['status'] = 'COMPROMISED'
                summary['details'].append({
                    'type': 'Data Breach',
                    'severity': hibp.get('severity', 'unknown').upper(),
                    'breach_count': hibp.get('breach_count', 0),
                    'paste_count': hibp.get('paste_count', 0),
                    'last_breach': hibp.get('last_breach'),
                    'breaches': hibp.get('breaches', [])
                })

            # Vulnerability data
            vuln = breach_data.get('vulnerability', {})
            if vuln and vuln.get('vulnerable'):
                if summary['status'] == 'SAFE':
                    summary['status'] = 'EXPOSED'
                summary['details'].append({
                    'type': 'Public Leak',
                    'severity': vuln.get('severity', 'unknown').upper(),
                    'leak_count': vuln.get('leak_count', 0),
                    'found_in': vuln.get('found_in', []),
                    'sources': vuln.get('breach_sources', [])
                })

            result['breach_summary'] = summary

        return result

    def format_email_breach_report(self, email: str) -> str:
        """
        Generate formatted breach report for an email.

        Args:
            email: Email address

        Returns:
            Formatted report string
        """
        info = self.get_email_with_breach_info(email)

        if not info:
            return f"Email {email} not found in memory."

        divider = '=' * 60
        report = f"\n{divider}\n"
        report += "EMAIL BREACH REPORT (from Memory)\n"
        report += f"{divider}\n"
        report += f"Email: {info['email']}\n"
        report += f"Added: {info.get('added_at', 'Unknown')}\n"

        if info.get('last_updated'):
            report += f"Updated: {info['last_updated']}\n"

        breach_summary = info.get('breach_summary')
        if not breach_summary:
            report += "\n❓ Status: NO SCAN DATA\n"
            report += "   Run a breach scan to check this email.\n"
        else:
            report += self._format_breach_summary(breach_summary)

        report += f"{divider}\n"
        return report

    def _format_breach_summary(self, breach_summary: dict) -> str:
        """Format the status line and detail sections of a breach summary."""
        status_lines = {
            'SAFE': "\n✅ Status: SAFE\n",
            'EXPOSED': "\n🔓 Status: EXPOSED\n",
            'COMPROMISED': "\n🚨 Status: COMPROMISED\n",
        }
        status = breach_summary.get('status', 'UNKNOWN')
        last_checked = breach_summary.get('last_checked', 'Never')

        text = status_lines.get(status, "")
        text += f"   Last Checked: {last_checked}\n\n"

        divider = '=' * 60
        for detail in breach_summary.get('details', []):
            text += f"{divider}\n"
            text += f"{detail['type']} - Severity: {detail['severity']}\n"
            text += f"{divider}\n"

            if detail['type'] == 'Data Breach':
                text += self._format_data_breach_detail(detail)
            elif detail['type'] == 'Public Leak':
                text += self._format_public_leak_detail(detail)

            text += "\n"
        return text

    @staticmethod
    def _format_data_breach_detail(detail: dict) -> str:
        """Format a single data-breach detail section."""
        text = f"Breach Count: {detail['breach_count']}\n"
        text += f"Paste Count: {detail['paste_count']}\n"
        if detail.get('last_breach'):
            text += f"Last Breach: {detail['last_breach']}\n"

        if detail.get('breaches'):
            text += "\nKnown Breaches:\n"
            for i, breach in enumerate(detail['breaches'], 1):
                if isinstance(breach, dict):
                    name = breach.get('name', 'Unknown')
                    date = breach.get('date', 'Unknown')
                    text += f"  {i}. {name} ({date})\n"
                else:
                    text += f"  {i}. {breach}\n"
        return text

    @staticmethod
    def _format_public_leak_detail(detail: dict) -> str:
        """Format a single public-leak detail section."""
        text = f"Leak Count: {detail['leak_count']}\n"
        if detail.get('found_in'):
            text += f"Found in: {', '.join(detail['found_in'])}\n"

        if detail.get('sources'):
            text += "\nLeak Sources:\n"
            for i, source in enumerate(detail['sources'], 1):
                if isinstance(source, dict):
                    src_name = source.get('source', 'Unknown')
                    src_type = source.get('type', 'unknown')
                    text += f"  {i}. {src_name} ({src_type})\n"
                else:
                    text += f"  {i}. {source}\n"
        return text
