"""
Constants for the memory store package.
"""

# Security Configuration
DEFAULT_PER_USER_LIMIT = 100  # Max entries per user per category
DEFAULT_GLOBAL_LIMIT = 1000   # Max total entries per category
DEFAULT_USER_ID = "anonymous"  # Default user ID if none provided

CATEGORIES = ['emails', 'phones', 'ips', 'usernames', 'domains', 'notes']
