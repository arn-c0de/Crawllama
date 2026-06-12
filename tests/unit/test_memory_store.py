"""Tests for persistent memory store."""

import json
import os
import tempfile
from datetime import datetime

import pytest

from core.memory_store import MemoryStore, get_memory_store


@pytest.fixture
def temp_memory_file():
    """Create temporary memory file for testing."""
    fd, path = tempfile.mkstemp(suffix='.json')
    os.close(fd)
    yield path
    # Cleanup
    if os.path.exists(path):
        os.remove(path)


@pytest.fixture
def memory_store(temp_memory_file):
    """Create memory store instance for testing."""
    return MemoryStore(memory_file=temp_memory_file)


class TestMemoryStoreInitialization:
    """Test memory store initialization."""
    
    def test_create_new_memory_store(self, temp_memory_file):
        """Test creating new memory store."""
        store = MemoryStore(memory_file=temp_memory_file)
        assert store.data is not None
        assert 'emails' in store.data
        assert 'phones' in store.data
        assert 'ips' in store.data
        assert 'usernames' in store.data
        assert 'domains' in store.data
        assert 'notes' in store.data
        assert store.data['created_at'] is not None
    
    def test_load_existing_memory_store(self, temp_memory_file):
        """Test loading existing memory store."""
        # Create initial store
        store1 = MemoryStore(memory_file=temp_memory_file)
        store1.remember_email("test@example.com")
        
        # Load same store
        store2 = MemoryStore(memory_file=temp_memory_file)
        assert len(store2.data['emails']) == 1
        assert store2.data['emails'][0]['value'] == "test@example.com"


class TestEmailOperations:
    """Test email-related operations."""
    
    def test_remember_email(self, memory_store):
        """Test remembering an email."""
        result = memory_store.remember_email("test@example.com")
        assert result is True
        assert len(memory_store.data['emails']) == 1
        assert memory_store.data['emails'][0]['value'] == "test@example.com"
    
    def test_remember_duplicate_email(self, memory_store):
        """Test remembering duplicate email."""
        memory_store.remember_email("test@example.com")
        result = memory_store.remember_email("test@example.com")
        assert result is False
        assert len(memory_store.data['emails']) == 1
    
    def test_remember_email_with_metadata(self, memory_store):
        """Test remembering email with metadata."""
        metadata = {'source': 'osint_scan', 'confidence': 0.95}
        memory_store.remember_email("test@example.com", metadata=metadata)
        assert memory_store.data['emails'][0]['metadata'] == metadata
    
    def test_forget_email(self, memory_store):
        """Test forgetting an email."""
        memory_store.remember_email("test@example.com")
        result = memory_store.forget_email("test@example.com")
        assert result is True
        assert len(memory_store.data['emails']) == 0
    
    def test_forget_nonexistent_email(self, memory_store):
        """Test forgetting nonexistent email."""
        result = memory_store.forget_email("test@example.com")
        assert result is False
    
    def test_get_all_emails(self, memory_store):
        """Test getting all emails."""
        memory_store.remember_email("test1@example.com")
        memory_store.remember_email("test2@example.com")
        emails = memory_store.get_all_emails()
        assert len(emails) == 2
        assert any(e['value'] == "test1@example.com" for e in emails)
        assert any(e['value'] == "test2@example.com" for e in emails)


class TestPhoneOperations:
    """Test phone-related operations."""
    
    def test_remember_phone(self, memory_store):
        """Test remembering a phone."""
        result = memory_store.remember_phone("+491234567890")
        assert result is True
        assert len(memory_store.data['phones']) == 1
        assert memory_store.data['phones'][0]['value'] == "+491234567890"
    
    def test_remember_duplicate_phone(self, memory_store):
        """Test remembering duplicate phone."""
        memory_store.remember_phone("+491234567890")
        result = memory_store.remember_phone("+491234567890")
        assert result is False
        assert len(memory_store.data['phones']) == 1
    
    def test_forget_phone(self, memory_store):
        """Test forgetting a phone."""
        memory_store.remember_phone("+491234567890")
        result = memory_store.forget_phone("+491234567890")
        assert result is True
        assert len(memory_store.data['phones']) == 0
    
    def test_get_all_phones(self, memory_store):
        """Test getting all phones."""
        memory_store.remember_phone("+491234567890")
        memory_store.remember_phone("+441234567890")
        phones = memory_store.get_all_phones()
        assert len(phones) == 2


class TestIPOperations:
    """Test IP-related operations."""
    
    def test_remember_ip(self, memory_store):
        """Test remembering an IP."""
        result = memory_store.remember_ip("192.168.1.1")
        assert result is True
        assert len(memory_store.data['ips']) == 1
        assert memory_store.data['ips'][0]['value'] == "192.168.1.1"
    
    def test_remember_duplicate_ip(self, memory_store):
        """Test remembering duplicate IP."""
        memory_store.remember_ip("192.168.1.1")
        result = memory_store.remember_ip("192.168.1.1")
        assert result is False
        assert len(memory_store.data['ips']) == 1
    
    def test_forget_ip(self, memory_store):
        """Test forgetting an IP."""
        memory_store.remember_ip("192.168.1.1")
        result = memory_store.forget_ip("192.168.1.1")
        assert result is True
        assert len(memory_store.data['ips']) == 0
    
    def test_get_all_ips(self, memory_store):
        """Test getting all IPs."""
        memory_store.remember_ip("192.168.1.1")
        memory_store.remember_ip("8.8.8.8")
        ips = memory_store.get_all_ips()
        assert len(ips) == 2


class TestUsernameOperations:
    """Test username-related operations."""
    
    def test_remember_username(self, memory_store):
        """Test remembering a username."""
        result = memory_store.remember_username("johndoe")
        assert result is True
        assert len(memory_store.data['usernames']) == 1
        assert memory_store.data['usernames'][0]['value'] == "johndoe"
    
    def test_remember_duplicate_username(self, memory_store):
        """Test remembering duplicate username."""
        memory_store.remember_username("johndoe")
        result = memory_store.remember_username("johndoe")
        assert result is False
        assert len(memory_store.data['usernames']) == 1
    
    def test_forget_username(self, memory_store):
        """Test forgetting a username."""
        memory_store.remember_username("johndoe")
        result = memory_store.forget_username("johndoe")
        assert result is True
        assert len(memory_store.data['usernames']) == 0
    
    def test_get_all_usernames(self, memory_store):
        """Test getting all usernames."""
        memory_store.remember_username("johndoe")
        memory_store.remember_username("janedoe")
        usernames = memory_store.get_all_usernames()
        assert len(usernames) == 2


class TestDomainOperations:
    """Test domain-related operations."""
    
    def test_remember_domain(self, memory_store):
        """Test remembering a domain."""
        result = memory_store.remember_domain("example.com")
        assert result is True
        assert len(memory_store.data['domains']) == 1
        assert memory_store.data['domains'][0]['value'] == "example.com"
    
    def test_remember_duplicate_domain(self, memory_store):
        """Test remembering duplicate domain."""
        memory_store.remember_domain("example.com")
        result = memory_store.remember_domain("example.com")
        assert result is False
        assert len(memory_store.data['domains']) == 1
    
    def test_get_all_domains(self, memory_store):
        """Test getting all domains."""
        memory_store.remember_domain("example.com")
        memory_store.remember_domain("test.com")
        domains = memory_store.get_all_domains()
        assert len(domains) == 2


class TestNoteOperations:
    """Test note-related operations."""
    
    def test_add_note(self, memory_store):
        """Test adding a note."""
        result = memory_store.add_note("Important finding", category="investigation")
        assert result is True
        assert len(memory_store.data['notes']) == 1
        assert memory_store.data['notes'][0]['text'] == "Important finding"
        assert memory_store.data['notes'][0]['category'] == "investigation"
    
    def test_add_note_without_category(self, memory_store):
        """Test adding note without category."""
        result = memory_store.add_note("Simple note")
        assert result is True
        assert memory_store.data['notes'][0]['category'] is None
    
    def test_get_all_notes(self, memory_store):
        """Test getting all notes."""
        memory_store.add_note("Note 1")
        memory_store.add_note("Note 2")
        notes = memory_store.get_all_notes()
        assert len(notes) == 2


class TestClearOperations:
    """Test clear operations."""
    
    def test_clear_category(self, memory_store):
        """Test clearing specific category."""
        memory_store.remember_email("test@example.com")
        memory_store.remember_phone("+491234567890")
        
        result = memory_store.clear_category('emails')
        assert result is True
        assert len(memory_store.data['emails']) == 0
        assert len(memory_store.data['phones']) == 1
    
    def test_clear_all(self, memory_store):
        """Test clearing all data."""
        memory_store.remember_email("test@example.com")
        memory_store.remember_phone("+491234567890")
        memory_store.remember_ip("192.168.1.1")
        
        result = memory_store.clear_all()
        assert result is True
        assert len(memory_store.data['emails']) == 0
        assert len(memory_store.data['phones']) == 0
        assert len(memory_store.data['ips']) == 0


class TestSearchOperations:
    """Test search operations."""
    
    def test_search_emails(self, memory_store):
        """Test searching emails."""
        memory_store.remember_email("john@example.com")
        memory_store.remember_email("jane@test.com")
        
        results = memory_store.search("john")
        assert len(results['emails']) == 1
        assert results['emails'][0]['value'] == "john@example.com"
    
    def test_search_multiple_categories(self, memory_store):
        """Test searching across categories."""
        memory_store.remember_email("test@example.com")
        memory_store.remember_username("testuser")
        memory_store.add_note("Test note")
        
        results = memory_store.search("test")
        assert len(results['emails']) == 1
        assert len(results['usernames']) == 1
        assert len(results['notes']) == 1
    
    def test_search_no_results(self, memory_store):
        """Test search with no results."""
        memory_store.remember_email("test@example.com")
        
        results = memory_store.search("nonexistent")
        assert len(results['emails']) == 0
        assert len(results['phones']) == 0


class TestSummary:
    """Test summary operations."""
    
    def test_get_summary_empty(self, memory_store):
        """Test summary with empty store."""
        summary = memory_store.get_summary()
        assert summary['emails'] == 0
        assert summary['phones'] == 0
        assert summary['ips'] == 0
        assert summary['usernames'] == 0
        assert summary['domains'] == 0
        assert summary['notes'] == 0
        assert summary['total_entries'] == 0
    
    def test_get_summary_with_data(self, memory_store):
        """Test summary with data."""
        memory_store.remember_email("test@example.com")
        memory_store.remember_phone("+491234567890")
        memory_store.remember_ip("192.168.1.1")
        memory_store.remember_username("johndoe")
        memory_store.add_note("Note 1")
        
        summary = memory_store.get_summary()
        assert summary['emails'] == 1
        assert summary['phones'] == 1
        assert summary['ips'] == 1
        assert summary['usernames'] == 1
        assert summary['notes'] == 1
        assert summary['total_entries'] == 5


class TestExportImport:
    """Test export/import operations."""
    
    def test_export_to_json(self, memory_store, temp_memory_file):
        """Test exporting memory to JSON."""
        memory_store.remember_email("test@example.com")
        memory_store.remember_phone("+491234567890")
        
        export_path = temp_memory_file + ".export"
        result = memory_store.export_to_json(export_path)
        assert result is True
        assert os.path.exists(export_path)
        
        # Verify exported data
        with open(export_path) as f:
            data = json.load(f)
            assert len(data['emails']) == 1
            assert len(data['phones']) == 1
        
        os.remove(export_path)
    
    def test_import_from_json_merge(self, memory_store, temp_memory_file):
        """Test importing memory with merge."""
        memory_store.remember_email("existing@example.com")
        
        # Create import file
        import_data = {
            'emails': [{'value': 'new@example.com', 'added_at': datetime.now().isoformat(), 'metadata': {}}],
            'phones': [{'value': '+491234567890', 'added_at': datetime.now().isoformat(), 'metadata': {}}]
        }
        import_path = temp_memory_file + ".import"
        with open(import_path, 'w') as f:
            json.dump(import_data, f)
        
        result = memory_store.import_from_json(import_path, merge=True)
        assert result is True
        assert len(memory_store.data['emails']) == 2  # Merged
        assert len(memory_store.data['phones']) == 1
        
        os.remove(import_path)
    
    def test_import_from_json_replace(self, memory_store, temp_memory_file):
        """Test importing memory with replace."""
        memory_store.remember_email("existing@example.com")
        
        # Create import file
        import_data = {
            'emails': [{'value': 'new@example.com', 'added_at': datetime.now().isoformat(), 'metadata': {}}],
            'phones': [],
            'ips': [],
            'usernames': [],
            'domains': [],
            'notes': []
        }
        import_path = temp_memory_file + ".import"
        with open(import_path, 'w') as f:
            json.dump(import_data, f)
        
        result = memory_store.import_from_json(import_path, merge=False)
        assert result is True
        assert len(memory_store.data['emails']) == 1  # Replaced
        assert memory_store.data['emails'][0]['value'] == 'new@example.com'
        
        os.remove(import_path)


class TestPersistence:
    """Test data persistence."""
    
    def test_data_persists_across_instances(self, temp_memory_file):
        """Test that data persists across instances."""
        # First instance
        store1 = MemoryStore(memory_file=temp_memory_file)
        store1.remember_email("test@example.com")
        store1.remember_phone("+491234567890")
        
        # Second instance
        store2 = MemoryStore(memory_file=temp_memory_file)
        assert len(store2.data['emails']) == 1
        assert len(store2.data['phones']) == 1
        assert store2.data['emails'][0]['value'] == "test@example.com"
        assert store2.data['phones'][0]['value'] == "+491234567890"
    
    def test_metadata_includes_timestamps(self, memory_store):
        """Test that entries include timestamps."""
        memory_store.remember_email("test@example.com")
        
        email_entry = memory_store.data['emails'][0]
        assert 'added_at' in email_entry
        assert email_entry['added_at'] is not None
        
        # Verify it's a valid ISO format timestamp
        datetime.fromisoformat(email_entry['added_at'])


class TestGlobalInstance:
    """Test global memory store instance."""
    
    def test_get_memory_store_singleton(self):
        """Test that get_memory_store returns singleton."""
        store1 = get_memory_store()
        store2 = get_memory_store()
        assert store1 is store2


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_remember_email_case_insensitive(self, memory_store):
        """Test email case insensitivity."""
        memory_store.remember_email("Test@EXAMPLE.com")
        assert memory_store.data['emails'][0]['value'] == "test@example.com"
    
    def test_remember_domain_case_insensitive(self, memory_store):
        """Test domain case insensitivity."""
        memory_store.remember_domain("EXAMPLE.COM")
        assert memory_store.data['domains'][0]['value'] == "example.com"
    
    def test_remember_empty_value(self, memory_store):
        """Empty values are rejected by input validation (anti memory-poisoning)."""
        with pytest.raises(ValueError):
            memory_store.remember_email("")
        assert len(memory_store.data['emails']) == 0
    
    def test_search_case_insensitive(self, memory_store):
        """Test case-insensitive search."""
        memory_store.remember_email("Test@Example.com")
        
        results = memory_store.search("TEST")
        assert len(results['emails']) == 1
    
    def test_clear_nonexistent_category(self, memory_store):
        """Test clearing nonexistent category."""
        result = memory_store.clear_category('nonexistent')
        assert result is False
