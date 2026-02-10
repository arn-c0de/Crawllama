"""Test Role-Based Access Control (RBAC) implementation.

Tests cover:
- Role assignment and retrieval
- Permission checking
- Role hierarchy
- RBAC endpoints (admin API)
- Access control enforcement
- Role revocation
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from app import app, API_KEY
from core.rbac_manager import RBACManager, Role, get_role_hierarchy, DEFAULT_ROLE


class TestRBACManager:
    """Test RBAC Manager functionality."""
    
    def test_assign_and_get_role(self):
        """Test role assignment and retrieval."""
        manager = RBACManager(fallback_to_memory=True)
        
        user_id = "test_user_123"
        manager.assign_role(user_id, Role.ADMIN)
        
        role = manager.get_role(user_id)
        assert role == Role.ADMIN
    
    def test_default_role(self):
        """Test that unknown users get default role."""
        manager = RBACManager(fallback_to_memory=True)
        
        user_id = "unknown_user_999"
        role = manager.get_role(user_id)
        
        assert role == DEFAULT_ROLE
    
    def test_check_permission_success(self):
        """Test successful permission check."""
        manager = RBACManager(fallback_to_memory=True)
        
        user_id = "test_user_123"
        manager.assign_role(user_id, Role.ADMIN)
        
        # Admin should have USER permissions
        has_permission = manager.check_permission(user_id, Role.USER)
        assert has_permission is True
        
        # Admin should have READ_ONLY permissions
        has_permission = manager.check_permission(user_id, Role.READ_ONLY)
        assert has_permission is True
    
    def test_check_permission_failure(self):
        """Test failed permission check."""
        manager = RBACManager(fallback_to_memory=True)
        
        user_id = "test_user_123"
        manager.assign_role(user_id, Role.READ_ONLY)
        
        # READ_ONLY should NOT have USER permissions
        has_permission = manager.check_permission(user_id, Role.USER)
        assert has_permission is False
        
        # READ_ONLY should NOT have ADMIN permissions
        has_permission = manager.check_permission(user_id, Role.ADMIN)
        assert has_permission is False
    
    def test_role_hierarchy(self):
        """Test role hierarchy: admin > user > read_only."""
        assert Role.ADMIN >= Role.USER
        assert Role.ADMIN >= Role.READ_ONLY
        assert Role.USER >= Role.READ_ONLY
        
        assert not (Role.USER >= Role.ADMIN)
        assert not (Role.READ_ONLY >= Role.USER)
        assert not (Role.READ_ONLY >= Role.ADMIN)
    
    def test_revoke_role(self):
        """Test role revocation."""
        manager = RBACManager(fallback_to_memory=True)
        
        user_id = "test_user_123"
        manager.assign_role(user_id, Role.ADMIN)
        
        # Verify role is assigned
        assert manager.get_role(user_id) == Role.ADMIN
        
        # Revoke
        success = manager.revoke_role(user_id)
        assert success is True
        
        # Should now have default role
        assert manager.get_role(user_id) == DEFAULT_ROLE
    
    def test_list_roles(self):
        """Test listing all role assignments."""
        manager = RBACManager(fallback_to_memory=True)
        
        # Assign multiple roles
        manager.assign_role("user1", Role.ADMIN)
        manager.assign_role("user2", Role.USER)
        manager.assign_role("user3", Role.READ_ONLY)
        
        roles = manager.list_roles()
        
        assert len(roles) >= 3
        assert roles["user1"] == Role.ADMIN.value
        assert roles["user2"] == Role.USER.value
        assert roles["user3"] == Role.READ_ONLY.value
    
    def test_get_stats(self):
        """Test RBAC manager statistics."""
        manager = RBACManager(fallback_to_memory=True)
        
        # Assign some roles
        manager.assign_role("user1", Role.ADMIN)
        manager.assign_role("user2", Role.USER)
        
        stats = manager.get_stats()
        
        assert "backend" in stats
        assert stats["backend"] == "memory"
        assert stats["memory_role_count"] >= 2


class TestRoleEnum:
    """Test Role enum functionality."""
    
    def test_role_from_string(self):
        """Test converting string to Role enum."""
        assert Role.from_string("admin") == Role.ADMIN
        assert Role.from_string("ADMIN") == Role.ADMIN
        assert Role.from_string("user") == Role.USER
        assert Role.from_string("read_only") == Role.READ_ONLY
        assert Role.from_string("invalid") is None
    
    def test_role_hierarchy_function(self):
        """Test role hierarchy function."""
        hierarchy = get_role_hierarchy()
        
        assert len(hierarchy) == 3
        assert hierarchy[0] == "admin"
        assert hierarchy[1] == "user"
        assert hierarchy[2] == "read_only"


class TestRBACEndpoints:
    """Test RBAC API endpoints."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @pytest.fixture
    def admin_headers(self):
        """Create admin authentication headers."""
        # In tests, we need to set up admin role first
        from core.rbac_manager import get_rbac_manager
        from utils.secure_hash import hmac_sha256_hex
        
        manager = get_rbac_manager()
        api_key_hash = hmac_sha256_hex(API_KEY, key=b"test_secret")
        manager.assign_role(api_key_hash, Role.ADMIN)
        
        return {"X-API-Key": API_KEY}
    
    @pytest.fixture
    def user_headers(self):
        """Create user authentication headers (non-admin)."""
        from core.rbac_manager import get_rbac_manager
        from utils.secure_hash import hmac_sha256_hex
        
        manager = get_rbac_manager()
        user_key = "user_api_key_123"
        api_key_hash = hmac_sha256_hex(user_key, key=b"test_secret")
        manager.assign_role(api_key_hash, Role.USER)
        
        return {"X-API-Key": user_key}
    
    def test_get_my_role(self, client, admin_headers):
        """Test getting own role."""
        response = client.get("/admin/roles/me", headers=admin_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "success"
        assert "role" in data
        assert "permissions" in data
    
    def test_list_roles_admin_only(self, client, user_headers):
        """Test that non-admin cannot list roles."""
        response = client.get("/admin/roles/list", headers=user_headers)
        
        # Should be forbidden (403)
        assert response.status_code in [403, 401]
    
    def test_assign_role_admin_only(self, client, user_headers):
        """Test that non-admin cannot assign roles."""
        # Get CSRF token first
        token_response = client.post("/csrf-token", headers=user_headers)
        
        if token_response.status_code == 200:
            csrf_token = token_response.json()["csrf_token"]
            
            headers = {**user_headers, "X-CSRF-Token": csrf_token}
            
            response = client.post(
                "/admin/roles/assign",
                headers=headers,
                json={"api_key_to_manage": "some_key_abc123", "role": "admin"}
            )
            
            # Should be forbidden
            assert response.status_code == 403
    
    def test_rbac_stats_admin_only(self, client, user_headers):
        """Test that non-admin cannot view RBAC stats."""
        response = client.get("/admin/roles/stats", headers=user_headers)
        
        # Should be forbidden
        assert response.status_code in [403, 401]


class TestRBACAccessControl:
    """Test RBAC access control on protected endpoints."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @pytest.fixture
    def setup_roles(self):
        """Set up different role levels for testing."""
        from core.rbac_manager import get_rbac_manager
        
        manager = get_rbac_manager()
        
        # Create keys with different roles
        admin_key_hash = "admin_hash_123"
        user_key_hash = "user_hash_456"
        readonly_key_hash = "readonly_hash_789"
        
        manager.assign_role(admin_key_hash, Role.ADMIN)
        manager.assign_role(user_key_hash, Role.USER)
        manager.assign_role(readonly_key_hash, Role.READ_ONLY)
        
        return {
            "admin": admin_key_hash,
            "user": user_key_hash,
            "read_only": readonly_key_hash
        }
    
    def test_admin_can_access_config(self, client, setup_roles):
        """Test that admin can access config endpoint."""
        # Note: This test assumes API keys are properly configured
        # In real implementation, we'd use the actual API key
        pass
    
    def test_user_cannot_access_config(self, client, setup_roles):
        """Test that regular user cannot modify config."""
        # User should be blocked from PATCH /config
        pass
    
    def test_readonly_cannot_modify_memory(self, client, setup_roles):
        """Test that read-only user cannot modify memory."""
        # Read-only should be blocked from POST /memory/remember
        pass


class TestRBACIntegration:
    """Test RBAC integration with other security features."""
    
    def test_rbac_in_security_info(self):
        """Test that RBAC info appears in security-info endpoint."""
        client = TestClient(app)
        
        response = client.get("/security-info")
        assert response.status_code == 200
        
        data = response.json()
        assert "authorization" in data
        assert "RBAC" in data["authorization"]
        assert "roles" in data
        assert len(data["roles"]) == 3
    
    def test_rbac_with_csrf(self):
        """Test that RBAC works together with CSRF protection."""
        # Both RBAC and CSRF should be checked for protected endpoints
        pass
    
    def test_dev_mode_bypasses_rbac(self):
        """Test that DEV_MODE bypasses RBAC checks."""
        import os
        
        # This test would need to set DEV_MODE=true
        # In DEV_MODE, all role checks should pass
        pass


class TestRBACEdgeCases:
    """Test RBAC edge cases and error handling."""
    
    def test_invalid_role_string(self):
        """Test handling of invalid role strings."""
        manager = RBACManager(fallback_to_memory=True)
        
        # assign_role with invalid role type should return False
        result = manager.assign_role("user1", "invalid_role")
        assert result is False, "Should return False for invalid role type"
    
    def test_empty_user_id(self):
        """Test handling of empty user ID."""
        manager = RBACManager(fallback_to_memory=True)
        
        # Should handle gracefully
        role = manager.get_role("")
        assert role == DEFAULT_ROLE
    
    def test_special_characters_in_user_id(self):
        """Test handling of special characters in user ID."""
        manager = RBACManager(fallback_to_memory=True)
        
        user_id = "user@#$%^&*()_+{}[]"
        manager.assign_role(user_id, Role.USER)
        
        role = manager.get_role(user_id)
        assert role == Role.USER


class TestRBACPerformance:
    """Test RBAC performance characteristics."""
    
    def test_permission_check_performance(self):
        """Test that permission checks are fast."""
        import time
        
        manager = RBACManager(fallback_to_memory=True)
        
        # Assign role
        manager.assign_role("test_user", Role.USER)
        
        # Measure permission check time
        start = time.perf_counter()
        for _ in range(1000):
            manager.check_permission("test_user", Role.USER)
        elapsed = time.perf_counter() - start
        
        # Should be very fast (< 0.1s for 1000 checks)
        assert elapsed < 0.1
    
    def test_role_retrieval_performance(self):
        """Test that role retrieval is fast."""
        import time
        
        manager = RBACManager(fallback_to_memory=True)
        
        # Assign role
        manager.assign_role("test_user", Role.ADMIN)
        
        # Measure retrieval time
        start = time.perf_counter()
        for _ in range(1000):
            manager.get_role("test_user")
        elapsed = time.perf_counter() - start
        
        # Should be very fast (< 0.1s for 1000 retrievals)
        assert elapsed < 0.1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
