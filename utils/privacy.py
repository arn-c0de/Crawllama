"""Privacy utilities for redacting sensitive data in logs and outputs.

This module provides functions to redact or sanitize sensitive information
like coordinates, personal identifiers, and other private data before
logging or displaying to users.
"""

from typing import Tuple, Any, Dict
import re


def redact_coordinates(lat: float, lon: float, precision: int = 2) -> Tuple[str, str]:
    """Redact coordinates to lower precision for privacy.
    
    Reduces coordinate precision to prevent exact location tracking while
    still providing general location information.
    
    Args:
        lat: Latitude (decimal degrees)
        lon: Longitude (decimal degrees)
        precision: Decimal places to keep (default 2 = ~1.1km precision)
                  0 = ~111km, 1 = ~11km, 2 = ~1.1km, 3 = ~110m
    
    Returns:
        Tuple of (redacted_lat, redacted_lon) as strings with asterisk indicator
        
    Examples:
        >>> redact_coordinates(51.5074, -0.1278)
        ('51.51*', '-0.13*')
        >>> redact_coordinates(51.5074, -0.1278, precision=1)
        ('51.5*', '-0.1*')
    """
    return (f"{lat:.{precision}f}*", f"{lon:.{precision}f}*")


def redact_ip_address(ip: str, keep_prefix: bool = True) -> str:
    """Redact IP address for privacy.
    
    Args:
        ip: IP address (IPv4 or IPv6)
        keep_prefix: If True, keep first segment for general location
        
    Returns:
        Redacted IP address
        
    Examples:
        >>> redact_ip_address("192.168.1.100")
        '192.xxx.xxx.xxx'
        >>> redact_ip_address("192.168.1.100", keep_prefix=False)
        'xxx.xxx.xxx.xxx'
    """
    if ':' in ip:  # IPv6
        parts = ip.split(':')
        if keep_prefix and len(parts) > 2:
            return f"{parts[0]}:{parts[1]}:****"
        return "****:****:****"
    else:  # IPv4
        parts = ip.split('.')
        if keep_prefix and len(parts) == 4:
            return f"{parts[0]}.xxx.xxx.xxx"
        return "xxx.xxx.xxx.xxx"


def redact_email(email: str) -> str:
    """Redact email address for privacy.
    
    Args:
        email: Email address
        
    Returns:
        Redacted email (shows first char and domain)
        
    Examples:
        >>> redact_email("john.doe@example.com")
        'j***@example.com'
    """
    if '@' not in email:
        return "***@***.***"
    
    local, domain = email.split('@', 1)
    if len(local) > 1:
        return f"{local[0]}***@{domain}"
    return f"***@{domain}"


def redact_phone_number(phone: str) -> str:
    """Redact phone number for privacy.
    
    Args:
        phone: Phone number
        
    Returns:
        Redacted phone (shows country code if present)
        
    Examples:
        >>> redact_phone_number("+1-555-123-4567")
        '+1-***-***-****'
        >>> redact_phone_number("555-123-4567")
        '***-***-****'
    """
    # Keep country code if present (+XX)
    if phone.startswith('+'):
        match = re.match(r'(\+\d{1,3})', phone)
        if match:
            return f"{match.group(1)}-***-***-****"
    
    return "***-***-****"


def sanitize_for_logging(data: Any, redact_geo: bool = True) -> Any:
    """Sanitize data structure for safe logging.
    
    Recursively processes dictionaries and lists to redact sensitive fields.
    
    Args:
        data: Data to sanitize (dict, list, or primitive)
        redact_geo: If True, redact geolocation data
        
    Returns:
        Sanitized copy of data
    """
    if isinstance(data, dict):
        sanitized = {}
        for key, value in data.items():
            key_lower = key.lower()
            
            # Redact sensitive fields
            if any(sensitive in key_lower for sensitive in 
                   ['password', 'token', 'secret', 'key', 'credential', 'auth']):
                sanitized[key] = "***REDACTED***"
            elif redact_geo and key_lower in ['latitude', 'lat']:
                if isinstance(value, (int, float)):
                    sanitized[key] = f"{value:.2f}*"
                else:
                    sanitized[key] = value
            elif redact_geo and key_lower in ['longitude', 'lon', 'lng']:
                if isinstance(value, (int, float)):
                    sanitized[key] = f"{value:.2f}*"
                else:
                    sanitized[key] = value
            elif key_lower in ['email', 'e_mail']:
                if isinstance(value, str) and '@' in value:
                    sanitized[key] = redact_email(value)
                else:
                    sanitized[key] = value
            elif key_lower in ['phone', 'telephone', 'mobile']:
                if isinstance(value, str):
                    sanitized[key] = redact_phone_number(value)
                else:
                    sanitized[key] = value
            elif key_lower in ['ip', 'ip_address', 'ipaddress']:
                if isinstance(value, str):
                    sanitized[key] = redact_ip_address(value)
                else:
                    sanitized[key] = value
            else:
                # Recursively sanitize nested structures
                sanitized[key] = sanitize_for_logging(value, redact_geo)
                
        return sanitized
        
    elif isinstance(data, list):
        return [sanitize_for_logging(item, redact_geo) for item in data]
    
    else:
        # Primitive types - return as-is
        return data
