"""
Persistent Memory Store for OSINT Data
Survives session clear and provides long-term storage for important findings.

Security Features:
- Per-user entry limits to prevent DoS attacks
- Global entry limits as fallback
- User ID tracking for all entries
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path
from collections import defaultdict

from utils.logger import get_logger

logger = get_logger(__name__)


# Security Configuration
DEFAULT_PER_USER_LIMIT = 100  # Max entries per user per category
DEFAULT_GLOBAL_LIMIT = 1000   # Max total entries per category
DEFAULT_USER_ID = "anonymous"  # Default user ID if none provided


class MemoryStore:
    """
    Persistent storage for OSINT intelligence data.
    Stores emails, phones, IPs, usernames, and custom notes.
    
    Security Features:
    - Per-user quotas to prevent memory exhaustion DoS
    - Global limits as fallback protection
    - User ID tracking for audit and accountability
    """
    
    def __init__(
        self, 
        memory_file: str = "data/memory.json",
        per_user_limit: int = DEFAULT_PER_USER_LIMIT,
        global_limit: int = DEFAULT_GLOBAL_LIMIT
    ):
        """
        Initialize memory store.
        
        Args:
            memory_file: Path to persistent memory JSON file
            per_user_limit: Maximum entries per user per category (default: 100)
            global_limit: Maximum total entries per category (default: 1000)
        """
        self.memory_file = memory_file
        self.per_user_limit = per_user_limit
        self.global_limit = global_limit
        self.data = {
            'emails': [],
            'phones': [],
            'ips': [],
            'usernames': [],
            'domains': [],
            'notes': [],
            'created_at': None,
            'last_updated': None
        }
        self._load()
    
    def _load(self) -> None:
        """Load memory from disk."""
        try:
            if os.path.exists(self.memory_file) and os.path.getsize(self.memory_file) > 0:
                with open(self.memory_file, 'r', encoding='utf-8') as f:
                    loaded_data = json.load(f)
                    # Merge with default structure
                    self.data.update(loaded_data)
                logger.info(f"Loaded memory from {self.memory_file}")
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
            except (IOError, OSError, PermissionError) as save_error:
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
            
            with open(self.memory_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved memory to {self.memory_file}")
        except Exception as e:
            logger.error(f"Error saving memory: {e}")
    
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
    
    def _sanitize_email_for_logging(self, email: str) -> str:
        """
        Sanitize email address for logging to prevent sensitive data exposure.

        Args:
            email: Email address to sanitize

        Returns:
            Sanitized email (e.g., "te***@example.com")
        """
        if '@' not in email:
            return "***@***"

        username, domain = email.split('@', 1)

        # Show first 2 chars of username
        if len(username) > 2:
            sanitized = username[:2] + "***@" + domain
        else:
            sanitized = "***@" + domain

        return sanitized

    def remember_email(self, email: str, metadata: Optional[Dict] = None, user_id: str = DEFAULT_USER_ID) -> bool:
        """
        Remember an email address.

        Args:
            email: Email address to remember
            metadata: Optional metadata (source, timestamp, etc.)
            user_id: User identifier for quota tracking

        Returns:
            True if added, False if already exists or quota exceeded

        Raises:
            ValueError: If user or global quota exceeded
        """
        # Check quotas BEFORE adding
        if not self._check_user_limit('emails', user_id):
            raise ValueError(
                f"Per-user quota exceeded for emails. "
                f"Limit: {self.per_user_limit} entries per user."
            )

        if not self._check_global_limit('emails'):
            raise ValueError(
                f"Global quota exceeded for emails. "
                f"Limit: {self.global_limit} total entries."
            )

        entry = {
            'value': email.lower().strip(),
            'added_at': datetime.now().isoformat(),
            'user_id': user_id,
            'metadata': metadata or {}
        }

        # Sanitize email for logging to prevent sensitive data exposure
        sanitized_email = self._sanitize_email_for_logging(email)

        # Check if already exists
        existing_entry = next((e for e in self.data['emails'] if e['value'] == entry['value']), None)
        if existing_entry:
            # Update metadata if provided
            if metadata:
                existing_entry['metadata'].update(metadata)
                existing_entry['last_updated'] = datetime.now().isoformat()
                self._save()
                logger.info(f"Updated email metadata: {sanitized_email}")  # lgtm[py/clear-text-logging-sensitive-data]
            else:
                logger.info(f"Email {sanitized_email} already in memory")  # lgtm[py/clear-text-logging-sensitive-data]
            return False

        self.data['emails'].append(entry)
        self._save()
        logger.info(f"Remembered email: {sanitized_email} (user: {user_id})")  # lgtm[py/clear-text-logging-sensitive-data]
        return True
    
    def remember_phone(self, phone: str, metadata: Optional[Dict] = None, user_id: str = DEFAULT_USER_ID) -> bool:
        """
        Remember a phone number.
        
        Args:
            phone: Phone number to remember
            metadata: Optional metadata (country, type, etc.)
            user_id: User identifier for quota tracking
        
        Returns:
            True if added, False if already exists or quota exceeded
            
        Raises:
            ValueError: If user or global quota exceeded
        """
        if not self._check_user_limit('phones', user_id):
            raise ValueError(f"Per-user quota exceeded for phones. Limit: {self.per_user_limit}")
        
        if not self._check_global_limit('phones'):
            raise ValueError(f"Global quota exceeded for phones. Limit: {self.global_limit}")
        
        entry = {
            'value': phone.strip(),
            'added_at': datetime.now().isoformat(),
            'user_id': user_id,
            'metadata': metadata or {}
        }
        
        # Check if already exists
        if any(p['value'] == entry['value'] for p in self.data['phones']):
            logger.info(f"Phone {phone} already in memory")
            return False
        
        self.data['phones'].append(entry)
        self._save()
        logger.info(f"Remembered phone: {phone} (user: {user_id})")
        return True
    
    def remember_ip(self, ip: str, metadata: Optional[Dict] = None, user_id: str = DEFAULT_USER_ID) -> bool:
        """
        Remember an IP address.
        
        Args:
            ip: IP address to remember
            metadata: Optional metadata (location, ISP, etc.)
            user_id: User identifier for quota tracking
        
        Returns:
            True if added, False if already exists or quota exceeded
            
        Raises:
            ValueError: If user or global quota exceeded
        """
        if not self._check_user_limit('ips', user_id):
            raise ValueError(f"Per-user quota exceeded for IPs. Limit: {self.per_user_limit}")
        
        if not self._check_global_limit('ips'):
            raise ValueError(f"Global quota exceeded for IPs. Limit: {self.global_limit}")
        
        entry = {
            'value': ip.strip(),
            'added_at': datetime.now().isoformat(),
            'user_id': user_id,
            'metadata': metadata or {}
        }
        
        # Check if already exists
        if any(i['value'] == entry['value'] for i in self.data['ips']):
            logger.info(f"IP {ip} already in memory")
            return False
        
        self.data['ips'].append(entry)
        self._save()
        logger.info(f"Remembered IP: {ip} (user: {user_id})")
        return True
    
    def remember_username(self, username: str, metadata: Optional[Dict] = None, user_id: str = DEFAULT_USER_ID) -> bool:
        """
        Remember a username.
        
        Args:
            username: Username to remember
            metadata: Optional metadata (platforms, etc.)
            user_id: User identifier for quota tracking
        
        Returns:
            True if added, False if already exists or quota exceeded
            
        Raises:
            ValueError: If user or global quota exceeded
        """
        if not self._check_user_limit('usernames', user_id):
            raise ValueError(f"Per-user quota exceeded for usernames. Limit: {self.per_user_limit}")
        
        if not self._check_global_limit('usernames'):
            raise ValueError(f"Global quota exceeded for usernames. Limit: {self.global_limit}")
        
        entry = {
            'value': username.strip(),
            'added_at': datetime.now().isoformat(),
            'user_id': user_id,
            'metadata': metadata or {}
        }
        
        # Check if already exists
        if any(u['value'] == entry['value'] for u in self.data['usernames']):
            logger.info(f"Username {username} already in memory")
            return False
        
        self.data['usernames'].append(entry)
        self._save()
        logger.info(f"Remembered username: {username} (user: {user_id})")
        return True
    
    def remember_domain(self, domain: str, metadata: Optional[Dict] = None, user_id: str = DEFAULT_USER_ID) -> bool:
        """
        Remember a domain.
        
        Args:
            domain: Domain to remember
            metadata: Optional metadata
            user_id: User identifier for quota tracking
        
        Returns:
            True if added, False if already exists or quota exceeded
            
        Raises:
            ValueError: If user or global quota exceeded
        """
        if not self._check_user_limit('domains', user_id):
            raise ValueError(f"Per-user quota exceeded for domains. Limit: {self.per_user_limit}")
        
        if not self._check_global_limit('domains'):
            raise ValueError(f"Global quota exceeded for domains. Limit: {self.global_limit}")
        
        entry = {
            'value': domain.lower().strip(),
            'added_at': datetime.now().isoformat(),
            'user_id': user_id,
            'metadata': metadata or {}
        }
        
        # Check if already exists
        if any(d['value'] == entry['value'] for d in self.data['domains']):
            logger.info(f"Domain {domain} already in memory")
            return False
        
        self.data['domains'].append(entry)
        self._save()
        logger.info(f"Remembered domain: {domain} (user: {user_id})")
        return True
    
    def add_note(self, note: str, category: Optional[str] = None, user_id: str = DEFAULT_USER_ID) -> bool:
        """
        Add a custom note.
        
        Args:
            note: Note text
            category: Optional category/tag
            user_id: User identifier for quota tracking
        
        Returns:
            True on success
            
        Raises:
            ValueError: If user or global quota exceeded
        """
        if not self._check_user_limit('notes', user_id):
            raise ValueError(f"Per-user quota exceeded for notes. Limit: {self.per_user_limit}")
        
        if not self._check_global_limit('notes'):
            raise ValueError(f"Global quota exceeded for notes. Limit: {self.global_limit}")
        
        entry = {
            'text': note,
            'category': category,
            'user_id': user_id,
            'added_at': datetime.now().isoformat()
        }
        
        self.data['notes'].append(entry)
        self._save()
        logger.info(f"Added note: {note[:50]}... (user: {user_id})")
        return True
    
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
            logger.warning(f"Email {email} not found in memory for breach update")
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

        logger.info(f"Updated breach info for email: {email}")
        return True

    def forget_email(self, email: str) -> bool:
        """Remove an email from memory."""
        email = email.lower().strip()
        original_count = len(self.data['emails'])
        self.data['emails'] = [e for e in self.data['emails'] if e['value'] != email]

        if len(self.data['emails']) < original_count:
            self._save()
            logger.info(f"Forgot email: {email}")
            return True
        return False
    
    def forget_phone(self, phone: str) -> bool:
        """Remove a phone from memory."""
        phone = phone.strip()
        original_count = len(self.data['phones'])
        self.data['phones'] = [p for p in self.data['phones'] if p['value'] != phone]
        
        if len(self.data['phones']) < original_count:
            self._save()
            logger.info(f"Forgot phone: {phone}")
            return True
        return False
    
    def forget_ip(self, ip: str) -> bool:
        """Remove an IP from memory."""
        ip = ip.strip()
        original_count = len(self.data['ips'])
        self.data['ips'] = [i for i in self.data['ips'] if i['value'] != ip]
        
        if len(self.data['ips']) < original_count:
            self._save()
            logger.info(f"Forgot IP: {ip}")
            return True
        return False
    
    def forget_username(self, username: str) -> bool:
        """Remove a username from memory."""
        username = username.strip()
        original_count = len(self.data['usernames'])
        self.data['usernames'] = [u for u in self.data['usernames'] if u['value'] != username]
        
        if len(self.data['usernames']) < original_count:
            self._save()
            logger.info(f"Forgot username: {username}")
            return True
        return False
    
    def clear_all(self) -> bool:
        """Clear all memory data."""
        self.data = {
            'emails': [],
            'phones': [],
            'ips': [],
            'usernames': [],
            'domains': [],
            'notes': [],
            'created_at': self.data.get('created_at'),
            'last_updated': None
        }
        self._save()
        logger.info("Cleared all memory")
        return True
    
    def clear_category(self, category: str) -> bool:
        """
        Clear specific category.
        
        Args:
            category: 'emails', 'phones', 'ips', 'usernames', 'domains', or 'notes'
        
        Returns:
            True on success
        """
        if category in self.data and isinstance(self.data[category], list):
            self.data[category] = []
            self._save()
            logger.info(f"Cleared category: {category}")
            return True
        return False
    
    def get_all_emails(self) -> List[Dict]:
        """Get all remembered emails with breach information."""
        return self.data.get('emails', [])

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

        report = f"\n{'='*60}\n"
        report += f"EMAIL BREACH REPORT (from Memory)\n"
        report += f"{'='*60}\n"
        report += f"Email: {info['email']}\n"
        report += f"Added: {info.get('added_at', 'Unknown')}\n"

        if info.get('last_updated'):
            report += f"Updated: {info['last_updated']}\n"

        breach_summary = info.get('breach_summary')
        if not breach_summary:
            report += f"\n❓ Status: NO SCAN DATA\n"
            report += f"   Run a breach scan to check this email.\n"
        else:
            last_checked = breach_summary.get('last_checked', 'Never')
            status = breach_summary.get('status', 'UNKNOWN')

            # Status indicator
            if status == 'SAFE':
                report += f"\n✅ Status: SAFE\n"
            elif status == 'EXPOSED':
                report += f"\n🔓 Status: EXPOSED\n"
            elif status == 'COMPROMISED':
                report += f"\n🚨 Status: COMPROMISED\n"

            report += f"   Last Checked: {last_checked}\n\n"

            # Details
            for detail in breach_summary.get('details', []):
                report += f"{'='*60}\n"
                report += f"{detail['type']} - Severity: {detail['severity']}\n"
                report += f"{'='*60}\n"

                if detail['type'] == 'Data Breach':
                    report += f"Breach Count: {detail['breach_count']}\n"
                    report += f"Paste Count: {detail['paste_count']}\n"
                    if detail.get('last_breach'):
                        report += f"Last Breach: {detail['last_breach']}\n"

                    if detail.get('breaches'):
                        report += f"\nKnown Breaches:\n"
                        for i, breach in enumerate(detail['breaches'], 1):
                            if isinstance(breach, dict):
                                name = breach.get('name', 'Unknown')
                                date = breach.get('date', 'Unknown')
                                report += f"  {i}. {name} ({date})\n"
                            else:
                                report += f"  {i}. {breach}\n"

                elif detail['type'] == 'Public Leak':
                    report += f"Leak Count: {detail['leak_count']}\n"
                    if detail.get('found_in'):
                        report += f"Found in: {', '.join(detail['found_in'])}\n"

                    if detail.get('sources'):
                        report += f"\nLeak Sources:\n"
                        for i, source in enumerate(detail['sources'], 1):
                            if isinstance(source, dict):
                                src_name = source.get('source', 'Unknown')
                                src_type = source.get('type', 'unknown')
                                report += f"  {i}. {src_name} ({src_type})\n"
                            else:
                                report += f"  {i}. {source}\n"

                report += "\n"

        report += f"{'='*60}\n"
        return report
    
    def get_all_phones(self) -> List[Dict]:
        """Get all remembered phones."""
        return self.data.get('phones', [])
    
    def get_all_ips(self) -> List[Dict]:
        """Get all remembered IPs."""
        return self.data.get('ips', [])
    
    def get_all_usernames(self) -> List[Dict]:
        """Get all remembered usernames."""
        return self.data.get('usernames', [])
    
    def get_all_domains(self) -> List[Dict]:
        """Get all remembered domains."""
        return self.data.get('domains', [])
    
    def get_all_notes(self) -> List[Dict]:
        """Get all notes."""
        return self.data.get('notes', [])
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get summary statistics.
        
        Returns:
            Dictionary with counts and metadata
        """
        return {
            'emails': len(self.data.get('emails', [])),
            'phones': len(self.data.get('phones', [])),
            'ips': len(self.data.get('ips', [])),
            'usernames': len(self.data.get('usernames', [])),
            'domains': len(self.data.get('domains', [])),
            'notes': len(self.data.get('notes', [])),
            'created_at': self.data.get('created_at'),
            'last_updated': self.data.get('last_updated'),
            'total_entries': sum([
                len(self.data.get('emails', [])),
                len(self.data.get('phones', [])),
                len(self.data.get('ips', [])),
                len(self.data.get('usernames', [])),
                len(self.data.get('domains', [])),
                len(self.data.get('notes', []))
            ])
        }
    
    def search(self, query: str) -> Dict[str, List[Dict]]:
        """
        Search across all categories.
        
        Args:
            query: Search term
        
        Returns:
            Dictionary with matching entries per category
        """
        query = query.lower()
        results = {
            'emails': [],
            'phones': [],
            'ips': [],
            'usernames': [],
            'domains': [],
            'notes': []
        }
        
        for email in self.data.get('emails', []):
            if query in email['value'].lower():
                results['emails'].append(email)
        
        for phone in self.data.get('phones', []):
            if query in phone['value']:
                results['phones'].append(phone)
        
        for ip in self.data.get('ips', []):
            if query in ip['value']:
                results['ips'].append(ip)
        
        for username in self.data.get('usernames', []):
            if query in username['value'].lower():
                results['usernames'].append(username)
        
        for domain in self.data.get('domains', []):
            if query in domain['value'].lower():
                results['domains'].append(domain)
        
        for note in self.data.get('notes', []):
            if query in note['text'].lower() or (note.get('category') and query in note['category'].lower()):
                results['notes'].append(note)
        
        return results
    
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


# Global instance
_memory_store = None


def get_memory_store() -> MemoryStore:
    """Get or create global memory store instance."""
    global _memory_store
    if _memory_store is None:
        _memory_store = MemoryStore()
    return _memory_store
