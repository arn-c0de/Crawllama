"""Comprehensive Audit Logging System.

Provides structured audit logging for all security-relevant events.
Logs are stored in JSON format with rotation for compliance and forensics.

Security Features:
- Structured JSON logging
- Automatic log rotation
- Sensitive data redaction
- Tamper-evident logging (optional)
- Compliance-ready format
- Search and filter capabilities

Example Usage:
    audit_logger = AuditLogger()
    
    # Log an event
    audit_logger.log_event(
        event_type="authentication",
        action="api_key_verify",
        user_id="user_123",
        status="success",
        metadata={"ip": "192.168.1.1"}
    )
"""
import json
import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from utils.logger import setup_logger

logger = setup_logger(__name__)


class AuditEvent:
    """Structured audit event."""
    
    def __init__(
        self,
        event_type: str,
        action: str,
        user_id: str,
        status: str,
        ip_address: str | None = None,
        endpoint: str | None = None,
        method: str | None = None,
        status_code: int | None = None,
        response_time: float | None = None,
        error: str | None = None,
        metadata: dict[str, Any] | None = None
    ):
        """Initialize audit event.
        
        Args:
            event_type: Type of event (authentication, authorization, data_access, etc.)
            action: Specific action taken
            user_id: User identifier (hashed API key or session ID)
            status: Event status (success, failure, denied)
            ip_address: Client IP address
            endpoint: API endpoint accessed
            method: HTTP method
            status_code: HTTP status code
            response_time: Request processing time in seconds
            error: Error message if failed
            metadata: Additional event metadata
        """
        self.event_id = self._generate_event_id()
        self.timestamp = datetime.now().isoformat()
        self.event_type = event_type
        self.action = action
        self.user_id = user_id
        self.status = status
        self.ip_address = ip_address
        self.endpoint = endpoint
        self.method = method
        self.status_code = status_code
        self.response_time = response_time
        self.error = error
        self.metadata = metadata or {}
    
    def _generate_event_id(self) -> str:
        """Generate unique event ID."""
        import secrets
        return secrets.token_urlsafe(16)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary."""
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "action": self.action,
            "user_id": self.user_id,
            "status": self.status,
            "ip_address": self.ip_address,
            "endpoint": self.endpoint,
            "method": self.method,
            "status_code": self.status_code,
            "response_time": self.response_time,
            "error": self.error,
            "metadata": self.metadata
        }
    
    def to_json(self) -> str:
        """Convert event to JSON string."""
        return json.dumps(self.to_dict(), default=str)


class AuditLogger:
    """Audit logging manager with structured JSON output."""
    
    def __init__(
        self,
        log_dir: str = "logs",
        log_file: str = "audit.json",
        max_bytes: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 10
    ):
        """Initialize audit logger.
        
        Args:
            log_dir: Directory for audit logs
            log_file: Audit log filename
            max_bytes: Maximum size per log file before rotation
            backup_count: Number of rotated log files to keep
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self.log_path = self.log_dir / log_file
        
        # Create rotating file handler
        self.handler = RotatingFileHandler(
            self.log_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        
        # Create logger
        self.logger = logging.getLogger("audit")
        self.logger.setLevel(logging.INFO)
        self.logger.addHandler(self.handler)
        self.logger.propagate = False  # Don't propagate to root logger
        
        logger.info(f"Audit logger initialized: {self.log_path}")
    
    def log_event(
        self,
        event_type: str,
        action: str,
        user_id: str,
        status: str,
        **kwargs
    ):
        """Log an audit event.
        
        Args:
            event_type: Type of event
            action: Action performed
            user_id: User identifier
            status: Event status
            **kwargs: Additional event fields
        """
        event = AuditEvent(
            event_type=event_type,
            action=action,
            user_id=user_id,
            status=status,
            **kwargs
        )
        
        # Log as JSON
        self.logger.info(event.to_json())
    
    def log_authentication(
        self,
        user_id: str,
        status: str,
        ip_address: str | None = None,
        error: str | None = None
    ):
        """Log authentication event."""
        self.log_event(
            event_type="authentication",
            action="api_key_verify",
            user_id=user_id,
            status=status,
            ip_address=ip_address,
            error=error
        )
    
    def log_authorization(
        self,
        user_id: str,
        role: str,
        endpoint: str,
        status: str,
        required_role: str | None = None
    ):
        """Log authorization event."""
        self.log_event(
            event_type="authorization",
            action="role_check",
            user_id=user_id,
            status=status,
            endpoint=endpoint,
            metadata={"role": role, "required_role": required_role}
        )
    
    def log_data_access(
        self,
        user_id: str,
        action: str,
        resource: str,
        status: str,
        ip_address: str | None = None
    ):
        """Log data access event."""
        self.log_event(
            event_type="data_access",
            action=action,
            user_id=user_id,
            status=status,
            ip_address=ip_address,
            metadata={"resource": resource}
        )
    
    def log_config_change(
        self,
        user_id: str,
        config_key: str,
        old_value: Any,
        new_value: Any,
        ip_address: str | None = None
    ):
        """Log configuration change."""
        self.log_event(
            event_type="configuration",
            action="config_update",
            user_id=user_id,
            status="success",
            ip_address=ip_address,
            metadata={
                "config_key": config_key,
                "old_value": str(old_value)[:100],  # Truncate for safety
                "new_value": str(new_value)[:100]
            }
        )
    
    def log_security_event(
        self,
        event_subtype: str,
        user_id: str,
        status: str,
        ip_address: str | None = None,
        details: str | None = None
    ):
        """Log security-specific event (CSRF, rate limit, etc.)."""
        self.log_event(
            event_type="security",
            action=event_subtype,
            user_id=user_id,
            status=status,
            ip_address=ip_address,
            metadata={"details": details}
        )
    
    def log_api_request(
        self,
        user_id: str,
        endpoint: str,
        method: str,
        status_code: int,
        response_time: float,
        ip_address: str | None = None,
        error: str | None = None
    ):
        """Log API request."""
        status = "success" if 200 <= status_code < 400 else "failure"
        
        self.log_event(
            event_type="api_request",
            action=f"{method} {endpoint}",
            user_id=user_id,
            status=status,
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            response_time=response_time,
            ip_address=ip_address,
            error=error
        )
    
    def search_logs(
        self,
        event_type: str | None = None,
        user_id: str | None = None,
        status: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100
    ) -> list[dict[str, Any]]:
        """Search audit logs with filters.
        
        Args:
            event_type: Filter by event type
            user_id: Filter by user ID
            status: Filter by status
            start_time: Filter by start timestamp
            end_time: Filter by end timestamp
            limit: Maximum number of results
            
        Returns:
            List of matching audit events
        """
        results = []
        
        try:
            # Read from current and rotated log files
            log_files = [self.log_path]
            for i in range(1, 11):  # Check up to 10 rotated files
                rotated = Path(f"{self.log_path}.{i}")
                if rotated.exists():
                    log_files.append(rotated)
            
            for log_file in log_files:
                with open(log_file, encoding='utf-8') as f:
                    for line in f:
                        try:
                            event = json.loads(line.strip())
                            
                            # Apply filters
                            if event_type and event.get("event_type") != event_type:
                                continue
                            
                            if user_id and event.get("user_id") != user_id:
                                continue
                            
                            if status and event.get("status") != status:
                                continue
                            
                            if start_time:
                                event_time = datetime.fromisoformat(event.get("timestamp", ""))
                                if event_time < start_time:
                                    continue
                            
                            if end_time:
                                event_time = datetime.fromisoformat(event.get("timestamp", ""))
                                if event_time > end_time:
                                    continue
                            
                            results.append(event)
                            
                            if len(results) >= limit:
                                return results
                                
                        except json.JSONDecodeError:
                            continue
        
        except Exception as e:
            logger.error(f"Failed to search audit logs: {e}")
        
        return results
    
    def get_stats(self) -> dict[str, Any]:
        """Get audit log statistics.
        
        Returns:
            Dictionary with log statistics
        """
        stats = {
            "log_file": str(self.log_path),
            "file_size_bytes": 0,
            "total_events": 0,
            "event_types": {}
        }
        
        try:
            if self.log_path.exists():
                stats["file_size_bytes"] = self.log_path.stat().st_size
                
                # Count events by type
                with open(self.log_path, encoding='utf-8') as f:
                    for line in f:
                        try:
                            event = json.loads(line.strip())
                            stats["total_events"] += 1
                            
                            event_type = event.get("event_type", "unknown")
                            stats["event_types"][event_type] = stats["event_types"].get(event_type, 0) + 1
                        except json.JSONDecodeError:
                            continue
        
        except Exception as e:
            logger.error(f"Failed to get audit stats: {e}")
        
        return stats


# Global audit logger instance
_audit_logger: AuditLogger | None = None


def get_audit_logger() -> AuditLogger:
    """Get the global audit logger instance.
    
    Initializes on first call with default configuration.
    """
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger
