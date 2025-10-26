"""
Persistent Memory Store for OSINT Data
Survives session clear and provides long-term storage for important findings.
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path

from utils.logger import get_logger

logger = get_logger(__name__)


class MemoryStore:
    """
    Persistent storage for OSINT intelligence data.
    Stores emails, phones, IPs, usernames, and custom notes.
    """
    
    def __init__(self, memory_file: str = "data/memory.json"):
        """
        Initialize memory store.
        
        Args:
            memory_file: Path to persistent memory JSON file
        """
        self.memory_file = memory_file
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
            except:
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
    
    def remember_email(self, email: str, metadata: Optional[Dict] = None) -> bool:
        """
        Remember an email address.
        
        Args:
            email: Email address to remember
            metadata: Optional metadata (source, timestamp, etc.)
        
        Returns:
            True if added, False if already exists
        """
        entry = {
            'value': email.lower().strip(),
            'added_at': datetime.now().isoformat(),
            'metadata': metadata or {}
        }
        
        # Check if already exists
        if any(e['value'] == entry['value'] for e in self.data['emails']):
            logger.info(f"Email {email} already in memory")
            return False
        
        self.data['emails'].append(entry)
        self._save()
        logger.info(f"Remembered email: {email}")
        return True
    
    def remember_phone(self, phone: str, metadata: Optional[Dict] = None) -> bool:
        """
        Remember a phone number.
        
        Args:
            phone: Phone number to remember
            metadata: Optional metadata (country, type, etc.)
        
        Returns:
            True if added, False if already exists
        """
        entry = {
            'value': phone.strip(),
            'added_at': datetime.now().isoformat(),
            'metadata': metadata or {}
        }
        
        # Check if already exists
        if any(p['value'] == entry['value'] for p in self.data['phones']):
            logger.info(f"Phone {phone} already in memory")
            return False
        
        self.data['phones'].append(entry)
        self._save()
        logger.info(f"Remembered phone: {phone}")
        return True
    
    def remember_ip(self, ip: str, metadata: Optional[Dict] = None) -> bool:
        """
        Remember an IP address.
        
        Args:
            ip: IP address to remember
            metadata: Optional metadata (location, ISP, etc.)
        
        Returns:
            True if added, False if already exists
        """
        entry = {
            'value': ip.strip(),
            'added_at': datetime.now().isoformat(),
            'metadata': metadata or {}
        }
        
        # Check if already exists
        if any(i['value'] == entry['value'] for i in self.data['ips']):
            logger.info(f"IP {ip} already in memory")
            return False
        
        self.data['ips'].append(entry)
        self._save()
        logger.info(f"Remembered IP: {ip}")
        return True
    
    def remember_username(self, username: str, metadata: Optional[Dict] = None) -> bool:
        """
        Remember a username.
        
        Args:
            username: Username to remember
            metadata: Optional metadata (platforms, etc.)
        
        Returns:
            True if added, False if already exists
        """
        entry = {
            'value': username.strip(),
            'added_at': datetime.now().isoformat(),
            'metadata': metadata or {}
        }
        
        # Check if already exists
        if any(u['value'] == entry['value'] for u in self.data['usernames']):
            logger.info(f"Username {username} already in memory")
            return False
        
        self.data['usernames'].append(entry)
        self._save()
        logger.info(f"Remembered username: {username}")
        return True
    
    def remember_domain(self, domain: str, metadata: Optional[Dict] = None) -> bool:
        """
        Remember a domain.
        
        Args:
            domain: Domain to remember
            metadata: Optional metadata
        
        Returns:
            True if added, False if already exists
        """
        entry = {
            'value': domain.lower().strip(),
            'added_at': datetime.now().isoformat(),
            'metadata': metadata or {}
        }
        
        # Check if already exists
        if any(d['value'] == entry['value'] for d in self.data['domains']):
            logger.info(f"Domain {domain} already in memory")
            return False
        
        self.data['domains'].append(entry)
        self._save()
        logger.info(f"Remembered domain: {domain}")
        return True
    
    def add_note(self, note: str, category: Optional[str] = None) -> bool:
        """
        Add a custom note.
        
        Args:
            note: Note text
            category: Optional category/tag
        
        Returns:
            True on success
        """
        entry = {
            'text': note,
            'category': category,
            'added_at': datetime.now().isoformat()
        }
        
        self.data['notes'].append(entry)
        self._save()
        logger.info(f"Added note: {note[:50]}...")
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
        """Get all remembered emails."""
        return self.data.get('emails', [])
    
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
