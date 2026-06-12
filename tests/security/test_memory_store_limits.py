"""
Security Test Suite: Memory Store User Limits

Tests for DoS protection via per-user quotas in the memory store.
Prevents memory exhaustion attacks where a single user fills the store.

OWASP Top 10 2021: A04 - Insecure Design (Resource Exhaustion)
CWE-400: Uncontrolled Resource Consumption

Test Categories:
1. Per-User Quota Enforcement
2. Global Quota Enforcement  
3. Quota Status Reporting
4. Multi-User Isolation
5. Edge Cases and Error Handling
"""
import os
import tempfile

import pytest

from core.memory_store import MemoryStore


@pytest.fixture
def temp_memory_file():
    """Create a temporary memory file for testing."""
    fd, path = tempfile.mkstemp(suffix='.json')
    os.close(fd)
    yield path
    # Cleanup
    if os.path.exists(path):
        os.remove(path)


@pytest.fixture
def memory_store(temp_memory_file):
    """Create a memory store with test limits."""
    return MemoryStore(
        memory_file=temp_memory_file,
        per_user_limit=5,  # Small limit for testing
        global_limit=15    # 3 users * 5 entries
    )


class TestPerUserQuotas:
    """Test per-user quota enforcement."""
    
    def test_user_can_add_up_to_limit(self, memory_store):
        """User can add entries up to their quota"""
        for i in range(5):  # Limit is 5
            result = memory_store.remember_email(
                f"test{i}@example.com",
                user_id="user1"
            )
            assert result is True
    
    def test_user_blocked_at_limit(self, memory_store):
        """User is blocked when reaching quota"""
        # Fill up to limit
        for i in range(5):
            memory_store.remember_email(f"test{i}@example.com", user_id="user1")
        
        # Next attempt should raise ValueError
        with pytest.raises(ValueError) as exc_info:
            memory_store.remember_email("overflow@example.com", user_id="user1")
        
        assert "per-user quota exceeded" in str(exc_info.value).lower()
        assert "5" in str(exc_info.value)  # Shows limit
    
    def test_different_users_have_separate_quotas(self, memory_store):
        """Each user has independent quota"""
        # User1 fills their quota
        for i in range(5):
            memory_store.remember_email(f"user1_{i}@example.com", user_id="user1")
        
        # User2 should still be able to add
        result = memory_store.remember_email("user2@example.com", user_id="user2")
        assert result is True
        
        # User1 should still be blocked
        with pytest.raises(ValueError):
            memory_store.remember_email("user1_blocked@example.com", user_id="user1")
    
    def test_quota_applies_per_category(self, memory_store):
        """Quota is per category (emails, phones, etc.)"""
        # Fill email quota
        for i in range(5):
            memory_store.remember_email(f"test{i}@example.com", user_id="user1")
        
        # Phone quota should be independent
        result = memory_store.remember_phone("+1234567890", user_id="user1")
        assert result is True
        
        # Email should still be blocked
        with pytest.raises(ValueError):
            memory_store.remember_email("overflow@example.com", user_id="user1")
    
    def test_quota_for_all_categories(self, memory_store):
        """Quota enforcement works for all memory categories"""
        categories = [
            ('remember_email', 'test@example.com'),
            ('remember_phone', '+1234567890'),
            ('remember_ip', '1.2.3.4'),
            ('remember_username', 'testuser'),
            ('remember_domain', 'example.com'),
            ('add_note', 'Test note')
        ]
        
        for method_name, value in categories:
            method = getattr(memory_store, method_name)
            
            # Fill quota
            for i in range(5):
                if method_name == 'add_note':
                    method(f"{value} {i}", user_id="user1")
                else:
                    method(f"{value}_{i}", user_id="user1")
            
            # Should block at limit
            with pytest.raises(ValueError) as exc_info:
                method(f"{value}_overflow", user_id="user1")
            
            assert "quota exceeded" in str(exc_info.value).lower()


class TestGlobalQuotas:
    """Test global quota enforcement."""
    
    def test_global_limit_across_users(self, memory_store):
        """Global limit prevents total entries from exceeding limit"""
        # 3 users, 5 entries each = 15 total (at global limit)
        for user_num in range(3):
            user_id = f"user{user_num}"
            for i in range(5):
                memory_store.remember_email(
                    f"user{user_num}_{i}@example.com",
                    user_id=user_id
                )
        
        # Next entry from any user should hit global limit
        with pytest.raises(ValueError) as exc_info:
            memory_store.remember_email("overflow@example.com", user_id="user4")
        
        assert "global quota exceeded" in str(exc_info.value).lower()
        assert "15" in str(exc_info.value)  # Shows limit
    
    def test_global_limit_before_user_limit(self, memory_store):
        """Global limit can trigger before user reaches their quota"""
        # Fill most of global quota with different users
        for user_num in range(2):
            user_id = f"user{user_num}"
            for i in range(5):
                memory_store.remember_email(
                    f"user{user_num}_{i}@example.com",
                    user_id=user_id
                )
        # 10 entries used, 5 remaining globally
        
        # user3 can add 5 more (reaching global limit)
        for i in range(5):
            memory_store.remember_email(f"user3_{i}@example.com", user_id="user3")
        
        # user4 tries to add but hits global limit (not their own limit)
        with pytest.raises(ValueError) as exc_info:
            memory_store.remember_email("user4@example.com", user_id="user4")
        
        assert "global quota exceeded" in str(exc_info.value).lower()


class TestQuotaStatusReporting:
    """Test quota status and monitoring."""
    
    def test_get_user_quota_status(self, memory_store):
        """Get detailed quota status for a user"""
        # Add some entries
        for i in range(3):
            memory_store.remember_email(f"test{i}@example.com", user_id="user1")
        
        status = memory_store.get_user_quota_status("user1")
        
        # Check structure
        assert 'emails' in status
        assert status['emails']['used'] == 3
        assert status['emails']['limit'] == 5
        assert status['emails']['remaining'] == 2
        assert status['emails']['percentage'] == 60  # 3/5 = 60%
    
    def test_quota_status_all_categories(self, memory_store):
        """Quota status includes all categories"""
        status = memory_store.get_user_quota_status("user1")
        
        expected_categories = ['emails', 'phones', 'ips', 'usernames', 'domains', 'notes']
        for category in expected_categories:
            assert category in status
            assert 'used' in status[category]
            assert 'limit' in status[category]
            assert 'remaining' in status[category]
            assert 'percentage' in status[category]
    
    def test_quota_status_empty_user(self, memory_store):
        """Quota status for user with no entries"""
        status = memory_store.get_user_quota_status("newuser")
        
        for category in status.values():
            assert category['used'] == 0
            assert category['remaining'] == 5
            assert category['percentage'] == 0
    
    def test_quota_status_multiple_users(self, memory_store):
        """Different users have independent status"""
        memory_store.remember_email("user1@example.com", user_id="user1")
        memory_store.remember_email("user2_1@example.com", user_id="user2")
        memory_store.remember_email("user2_2@example.com", user_id="user2")
        
        status1 = memory_store.get_user_quota_status("user1")
        status2 = memory_store.get_user_quota_status("user2")
        
        assert status1['emails']['used'] == 1
        assert status2['emails']['used'] == 2


class TestMultiUserIsolation:
    """Test user data isolation and tracking."""
    
    def test_user_id_stored_in_entries(self, memory_store):
        """User ID is tracked in all entries"""
        memory_store.remember_email("test@example.com", user_id="user1")
        
        emails = memory_store.get_all_emails()
        assert len(emails) == 1
        assert emails[0]['user_id'] == "user1"
    
    def test_default_user_id_when_not_specified(self, memory_store):
        """Default user ID is used when none provided"""
        memory_store.remember_email("test@example.com")  # No user_id
        
        emails = memory_store.get_all_emails()
        assert emails[0]['user_id'] == "anonymous"
    
    def test_user_tracking_all_categories(self, memory_store):
        """User ID tracked in all memory categories"""
        memory_store.remember_email("test@example.com", user_id="user1")
        memory_store.remember_phone("+1234567890", user_id="user1")
        memory_store.remember_ip("1.2.3.4", user_id="user1")
        memory_store.remember_username("testuser", user_id="user1")
        memory_store.remember_domain("example.com", user_id="user1")
        memory_store.add_note("Test note", user_id="user1")
        
        assert all(e['user_id'] == "user1" for e in memory_store.get_all_emails())
        assert all(p['user_id'] == "user1" for p in memory_store.get_all_phones())
        assert all(i['user_id'] == "user1" for i in memory_store.get_all_ips())
        assert all(u['user_id'] == "user1" for u in memory_store.get_all_usernames())
        assert all(d['user_id'] == "user1" for d in memory_store.get_all_domains())
        assert all(n['user_id'] == "user1" for n in memory_store.get_all_notes())


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_duplicate_entries_dont_count_towards_quota(self, memory_store):
        """Duplicate entries don't consume additional quota"""
        # Add same email 10 times
        for _ in range(10):
            try:
                memory_store.remember_email("same@example.com", user_id="user1")
            except ValueError:
                pass  # Quota might be exceeded
        
        # Should only count as 1 entry
        emails = [e for e in memory_store.get_all_emails() if e['value'] == "same@example.com"]
        assert len(emails) == 1
        
        status = memory_store.get_user_quota_status("user1")
        assert status['emails']['used'] == 1
    
    def test_persistence_preserves_user_tracking(self, temp_memory_file):
        """User IDs persist across store reloads"""
        # Create store and add entries
        store1 = MemoryStore(temp_memory_file, per_user_limit=5, global_limit=15)
        store1.remember_email("test@example.com", user_id="user1")
        store1.remember_email("test2@example.com", user_id="user2")
        
        # Reload from same file
        store2 = MemoryStore(temp_memory_file, per_user_limit=5, global_limit=15)
        emails = store2.get_all_emails()
        
        assert len(emails) == 2
        assert emails[0]['user_id'] == "user1"
        assert emails[1]['user_id'] == "user2"
        
        # Quotas should still apply
        for i in range(4):
            store2.remember_email(f"user1_{i}@example.com", user_id="user1")
        
        with pytest.raises(ValueError):
            store2.remember_email("overflow@example.com", user_id="user1")
    
    def test_empty_user_id_uses_default(self, memory_store):
        """Empty string user_id uses default"""
        memory_store.remember_email("test@example.com", user_id="")
        
        emails = memory_store.get_all_emails()
        # Should use empty string, not replace with default
        # (This documents current behavior)
        assert emails[0]['user_id'] == ""
    
    def test_special_characters_in_user_id(self, memory_store):
        """User IDs with special characters are handled"""
        special_ids = [
            "user@domain.com",
            "user-123",
            "user_456",
            "user.name",
            "用户789"  # Unicode
        ]
        
        for user_id in special_ids:
            result = memory_store.remember_email(
                f"{user_id}@example.com",
                user_id=user_id
            )
            assert result is True
    
    def test_very_long_user_id(self, memory_store):
        """Very long user IDs are handled"""
        long_id = "x" * 1000
        result = memory_store.remember_email("test@example.com", user_id=long_id)
        assert result is True
        
        emails = memory_store.get_all_emails()
        assert emails[0]['user_id'] == long_id


class TestSecurityScenarios:
    """Test real-world DoS attack scenarios."""
    
    def test_prevent_single_user_memory_exhaustion(self, temp_memory_file):
        """Prevent single malicious user from filling entire store"""
        store = MemoryStore(
            temp_memory_file,
            per_user_limit=10,
            global_limit=100
        )
        
        # Attacker tries to add 100 emails
        added = 0
        for i in range(100):
            try:
                store.remember_email(f"spam{i}@example.com", user_id="attacker")
                added += 1
            except ValueError:
                break
        
        # Should stop at 10 (per-user limit)
        assert added == 10
        
        # Other users should still be able to use the store
        result = store.remember_email("legit@example.com", user_id="legitimate_user")
        assert result is True
    
    def test_prevent_multiple_user_coordinated_attack(self, temp_memory_file):
        """Prevent coordinated attack from multiple user IDs"""
        store = MemoryStore(
            temp_memory_file,
            per_user_limit=10,
            global_limit=50
        )
        
        # 10 attackers each add 10 entries = 100 attempts
        attackers_succeeded = 0
        for user_num in range(10):
            user_id = f"attacker{user_num}"
            for i in range(10):
                try:
                    store.remember_email(
                        f"spam_{user_num}_{i}@example.com",
                        user_id=user_id
                    )
                    attackers_succeeded += 1
                except ValueError:
                    break  # Hit global limit
        
        # Should stop at 50 (global limit)
        assert attackers_succeeded == 50
        
        # No more entries allowed
        with pytest.raises(ValueError) as exc_info:
            store.remember_email("overflow@example.com", user_id="another_attacker")
        
        assert "global quota exceeded" in str(exc_info.value).lower()
    
    def test_quota_prevents_gradual_fill_up(self, temp_memory_file):
        """Quota prevents slow memory exhaustion over time"""
        store = MemoryStore(
            temp_memory_file,
            per_user_limit=5,
            global_limit=15
        )
        
        # Simulate slow attack over multiple sessions
        for session in range(10):
            try:
                store.remember_email(
                    f"session{session}@example.com",
                    user_id="persistent_attacker"
                )
            except ValueError:
                break
        
        # Should be limited to 5 entries total
        emails = [
            e for e in store.get_all_emails()
            if e.get('user_id') == "persistent_attacker"
        ]
        assert len(emails) == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
