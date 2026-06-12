"""Domain blacklist for filtering unsafe or unwanted websites."""
import re
from typing import List, Set, Optional
from urllib.parse import urlparse
from pathlib import Path
from utils.logger import setup_logger

logger = setup_logger(__name__)


class DomainBlacklist:
    """Manage domain blacklist for URL filtering."""

    # Default blacklist categories
    DEFAULT_BLACKLIST = {
        # Malware and phishing
        "malware": [
            r".*\.tk$",
            r".*\.ml$",
            r".*\.ga$",
            r".*\.cf$",
            r".*\.gq$",
        ],
        # Spam and low-quality content
        "spam": [
            r".*casino.*",
            r".*pharma.*",
            r".*viagra.*",
            r".*lottery.*",
        ],
        # Adult content
        "adult": [],  # Can be populated if needed
        # Social media tracking pixels
        "tracking": [
            r".*\.doubleclick\.net$",
            r".*\.facebook\.com/tr",
            r".*\.google-analytics\.com$",
        ]
    }

    def __init__(
        self,
        custom_blacklist: Optional[List[str]] = None,
        blacklist_file: Optional[str] = None,
        categories: Optional[List[str]] = None
    ):
        """
        Initialize domain blacklist.

        Args:
            custom_blacklist: List of custom blacklist patterns
            blacklist_file: Path to file with blacklist patterns (None: no file, "default": use data/blacklist.txt)
            categories: Categories to enable (default: all)
        """
        self.patterns: Set[str] = set()
        self.compiled_patterns: List[re.Pattern] = []
        
        # Store file path for reloading (only if file should be used)
        if blacklist_file == "default":
            self.blacklist_file = "data/blacklist.txt"
        else:
            self.blacklist_file = blacklist_file

        # Load default categories
        if categories is None:
            categories = ["malware", "spam", "tracking"]

        for category in categories:
            if category in self.DEFAULT_BLACKLIST:
                self.patterns.update(self.DEFAULT_BLACKLIST[category])

        # Load custom blacklist
        if custom_blacklist:
            self.patterns.update(custom_blacklist)

        # Load from file (only if specified)
        if self.blacklist_file:
            self.load_from_file(self.blacklist_file)

        # Compile patterns
        self._compile_patterns()

        logger.info(f"Domain blacklist initialized with {len(self.patterns)} patterns")

    def _compile_patterns(self):
        """Compile regex patterns for efficient matching."""
        self.compiled_patterns = []
        for pattern in self.patterns:
            try:
                if not self._is_safe_pattern(pattern):
                    logger.warning(f"Skipping potentially unsafe regex pattern: {pattern}")
                    continue
                compiled = re.compile(pattern, re.IGNORECASE)
                self.compiled_patterns.append(compiled)
            except re.error as e:
                logger.warning(f"Invalid regex pattern '{pattern}': {e}")

    def _is_safe_pattern(self, pattern: str) -> bool:
        """
        Basic safety checks to reduce ReDoS risk in user-supplied regex.
        This is a heuristic, not a full regex safety validator.
        """
        if len(pattern) > 200:
            return False

        # Reject nested quantifiers like (.+)+ or (.*)* or (\w+)+
        if re.search(r"\([^)]*[*+][^)]*\)[*+]", pattern):
            return False

        # Reject backreferences (often used in expensive patterns)
        if re.search(r"\\[1-9]", pattern):
            return False

        return True

    def load_from_file(self, filepath: str):
        """
        Load blacklist patterns from file.

        Args:
            filepath: Path to blacklist file (one pattern per line)
        """
        try:
            path = Path(filepath)
            if not path.exists():
                logger.warning(f"Blacklist file not found: {filepath}")
                return

            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    # Skip empty lines and comments
                    if line and not line.startswith("#"):
                        self.patterns.add(line)

            logger.info(f"Loaded {len(self.patterns)} patterns from {filepath}")

        except Exception as e:
            logger.error(f"Failed to load blacklist file: {e}")

    def save_to_file(self, filepath: str):
        """
        Save blacklist patterns to file.

        Args:
            filepath: Path to save blacklist
        """
        try:
            path = Path(filepath)
            path.parent.mkdir(parents=True, exist_ok=True)

            with open(path, "w", encoding="utf-8") as f:
                f.write("# Domain Blacklist\n")
                f.write("# One pattern per line (supports regex)\n\n")
                for pattern in sorted(self.patterns):
                    f.write(f"{pattern}\n")

            logger.info(f"Saved {len(self.patterns)} patterns to {filepath}")

        except Exception as e:
            logger.error(f"Failed to save blacklist file: {e}")

    def add_pattern(self, pattern: str):
        """
        Add a pattern to blacklist.

        Args:
            pattern: Regex pattern to add
        """
        self.patterns.add(pattern)
        self._compile_patterns()
        logger.debug(f"Added pattern to blacklist: {pattern}")

    def remove_pattern(self, pattern: str):
        """
        Remove a pattern from blacklist.

        Args:
            pattern: Pattern to remove
        """
        self.patterns.discard(pattern)
        self._compile_patterns()
        logger.debug(f"Removed pattern from blacklist: {pattern}")

    def reload_from_file(self, filepath: str):
        """
        Reload blacklist patterns from file at runtime.

        Args:
            filepath: Path to blacklist file
        """
        old_count = len(self.patterns)
        
        # Clear existing patterns (keep only default categories)
        self.patterns.clear()
        
        # Reload default categories
        categories = ["malware", "spam", "tracking"]  # Default categories
        for category in categories:
            if category in self.DEFAULT_BLACKLIST:
                self.patterns.update(self.DEFAULT_BLACKLIST[category])
        
        # Load from file
        self.load_from_file(filepath)
        
        # Recompile patterns
        self._compile_patterns()
        
        new_count = len(self.patterns)
        logger.info(f"Blacklist reloaded: {old_count} → {new_count} patterns")

    def reload(self):
        """Reload blacklist from default file."""
        self.reload_from_file(self.blacklist_file)

    def update_from_list(self, patterns: List[str], replace: bool = False):
        """
        Update blacklist from list of patterns.

        Args:
            patterns: List of patterns to add
            replace: If True, replace existing patterns, else add to existing
        """
        if replace:
            # Keep only default patterns
            self.patterns.clear()
            categories = ["malware", "spam", "tracking"]
            for category in categories:
                if category in self.DEFAULT_BLACKLIST:
                    self.patterns.update(self.DEFAULT_BLACKLIST[category])
        
        # Add new patterns
        self.patterns.update(patterns)
        self._compile_patterns()
        
        logger.info(f"Blacklist updated with {len(patterns)} patterns (total: {len(self.patterns)})")

    def is_blacklisted(self, url: str) -> bool:
        """
        Check if URL is blacklisted.

        Args:
            url: URL to check

        Returns:
            True if URL matches any blacklist pattern
        """
        # Extract domain from URL
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            full_url = url.lower()

            # Check against all patterns
            for pattern in self.compiled_patterns:
                if pattern.search(domain) or pattern.search(full_url):
                    logger.warning("URL blocked by blacklist")  # lgtm[py/clear-text-logging-sensitive-data] - URL content not logged to avoid leaking data
                    return True

            return False

        except Exception as e:
            logger.error(f"Error checking blacklist: {e}")  # lgtm[py/clear-text-logging-sensitive-data] - URL content not logged to avoid leaking data
            return False

    def filter_urls(self, urls: List[str]) -> List[str]:
        """
        Filter list of URLs against blacklist.

        Args:
            urls: List of URLs to filter

        Returns:
            List of non-blacklisted URLs
        """
        filtered = []
        for url in urls:
            if not self.is_blacklisted(url):
                filtered.append(url)
            else:
                logger.debug(f"Filtered out blacklisted URL: {url}")

        return filtered

    def get_stats(self) -> dict:
        """
        Get blacklist statistics.

        Returns:
            Dictionary with statistics
        """
        return {
            "total_patterns": len(self.patterns),
            "categories": list(self.DEFAULT_BLACKLIST.keys())
        }


# Global blacklist instance
blacklist = DomainBlacklist(
    categories=["malware", "spam", "tracking"]
)


def is_url_not_blacklisted(url: str) -> bool:
    """
    Check if URL is NOT blacklisted (i.e., safe to access from blacklist perspective).
    
    NOTE: This only checks the blacklist patterns. For full URL validation
    (schema, private IPs, whitelisting), use utils.validators.is_safe_url() instead.

    Args:
        url: URL to check

    Returns:
        True if URL is NOT blacklisted (safe from blacklist perspective)
    """
    return not blacklist.is_blacklisted(url)


# DEPRECATED: Use is_url_not_blacklisted() for clarity
def is_safe_url(url: str) -> bool:
    """
    DEPRECATED: Use is_url_not_blacklisted() for clarity, or validators.is_safe_url() for full validation.
    
    Check if URL is safe to access (not blacklisted).

    Args:
        url: URL to check

    Returns:
        True if URL is safe (not blacklisted)
    """
    import warnings
    warnings.warn(
        "domain_blacklist.is_safe_url() is deprecated. "
        "Use is_url_not_blacklisted() for blacklist checks or "
        "validators.is_safe_url() for full URL validation.",
        DeprecationWarning,
        stacklevel=2
    )
    return is_url_not_blacklisted(url)


def filter_safe_urls(urls: List[str]) -> List[str]:
    """
    Filter list of URLs to only safe ones.

    Args:
        urls: List of URLs

    Returns:
        List of safe URLs
    """
    return blacklist.filter_urls(urls)


def add_custom_pattern(pattern: str):
    """
    Add custom pattern to global blacklist.

    Args:
        pattern: Regex pattern
    """
    blacklist.add_pattern(pattern)


def load_custom_blacklist(filepath: str):
    """
    Load custom blacklist from file.

    Args:
        filepath: Path to blacklist file
    """
    blacklist.load_from_file(filepath)
