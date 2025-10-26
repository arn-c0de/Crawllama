"""Tests for domain blacklist."""
import pytest
from pathlib import Path
import tempfile
from utils.domain_blacklist import DomainBlacklist, is_url_not_blacklisted, filter_safe_urls


class TestDomainBlacklist:
    """Test DomainBlacklist class."""

    def test_initialization_default(self):
        """Test default initialization."""
        blacklist = DomainBlacklist()
        assert len(blacklist.patterns) > 0
        assert len(blacklist.compiled_patterns) > 0

    def test_initialization_custom(self):
        """Test initialization with custom patterns."""
        custom = [r".*badsite\.com$", r".*spam.*"]
        blacklist = DomainBlacklist(custom_blacklist=custom)
        assert r".*badsite\.com$" in blacklist.patterns
        assert r".*spam.*" in blacklist.patterns

    def test_initialization_categories(self):
        """Test initialization with specific categories."""
        blacklist = DomainBlacklist(categories=["malware"])
        # Should only have malware patterns, not spam or tracking
        assert any("tk" in p for p in blacklist.patterns)

    def test_blacklist_malware_domains(self):
        """Test blocking of malware-associated domains."""
        blacklist = DomainBlacklist(categories=["malware"])

        assert blacklist.is_blacklisted("http://example.tk")
        assert blacklist.is_blacklisted("http://example.ml")
        assert blacklist.is_blacklisted("http://example.ga")

    def test_blacklist_spam_patterns(self):
        """Test blocking of spam patterns."""
        blacklist = DomainBlacklist(categories=["spam"])

        assert blacklist.is_blacklisted("http://online-casino-win.com")
        assert blacklist.is_blacklisted("http://buy-pharma-now.com")
        assert blacklist.is_blacklisted("http://viagra-shop.com")

    def test_blacklist_tracking(self):
        """Test blocking of tracking domains."""
        blacklist = DomainBlacklist(categories=["tracking"])

        assert blacklist.is_blacklisted("http://stats.doubleclick.net")
        assert blacklist.is_blacklisted("http://www.google-analytics.com")

    def test_safe_url(self):
        """Test that legitimate URLs are not blacklisted."""
        blacklist = DomainBlacklist()

        assert not blacklist.is_blacklisted("https://www.google.com")
        assert not blacklist.is_blacklisted("https://github.com")
        assert not blacklist.is_blacklisted("https://stackoverflow.com")
        assert not blacklist.is_blacklisted("https://www.wikipedia.org")

    def test_add_pattern(self):
        """Test adding a pattern."""
        blacklist = DomainBlacklist(categories=[])
        assert len(blacklist.patterns) == 0

        blacklist.add_pattern(r".*badsite\.com$")
        assert r".*badsite\.com$" in blacklist.patterns
        assert blacklist.is_blacklisted("http://www.badsite.com")

    def test_remove_pattern(self):
        """Test removing a pattern."""
        pattern = r".*removeme\.com$"
        blacklist = DomainBlacklist(custom_blacklist=[pattern])

        assert pattern in blacklist.patterns
        blacklist.remove_pattern(pattern)
        assert pattern not in blacklist.patterns

    def test_filter_urls(self):
        """Test filtering URL list."""
        blacklist = DomainBlacklist(categories=["malware"])

        urls = [
            "https://good.example.com",
            "https://bad.tk",
            "https://another-good.example.org",
            "https://malware.ml"
        ]

        filtered = blacklist.filter_urls(urls)
        assert len(filtered) == 2
        # Safe: Checking if URLs are in filtered list (not URL validation)
        assert "https://good.example.com" in filtered
        assert "https://another-good.example.org" in filtered
        assert "https://bad.tk" not in filtered

    def test_save_and_load_file(self):
        """Test saving and loading blacklist file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "test_blacklist.txt"

            # Create and save
            blacklist1 = DomainBlacklist(custom_blacklist=[r".*test\.com$"])
            blacklist1.save_to_file(str(filepath))

            assert filepath.exists()

            # Load
            blacklist2 = DomainBlacklist(
                categories=[],
                blacklist_file=str(filepath)
            )

            assert r".*test\.com$" in blacklist2.patterns
            assert blacklist2.is_blacklisted("http://www.test.com")

    def test_load_nonexistent_file(self):
        """Test loading from nonexistent file."""
        blacklist = DomainBlacklist(
            categories=[],
            blacklist_file="/nonexistent/path/file.txt"
        )
        # Should not crash, just log warning
        assert len(blacklist.patterns) == 0

    def test_get_stats(self):
        """Test statistics."""
        blacklist = DomainBlacklist(categories=["malware", "spam"])
        stats = blacklist.get_stats()

        assert "total_patterns" in stats
        assert stats["total_patterns"] > 0
        assert "categories" in stats
        assert "malware" in stats["categories"]


class TestGlobalFunctions:
    """Test global helper functions."""

    def test_is_url_not_blacklisted(self):
        """Test global is_url_not_blacklisted function."""
        assert is_url_not_blacklisted("https://www.google.com")
        # This might fail depending on blacklist config, adjust as needed

    def test_filter_safe_urls(self):
        """Test global filter_safe_urls function."""
        urls = [
            "https://good.com",
            "https://github.com"
        ]
        filtered = filter_safe_urls(urls)
        assert len(filtered) >= 1


class TestInvalidPatterns:
    """Test handling of invalid patterns."""

    def test_invalid_regex_pattern(self):
        """Test that invalid regex patterns are handled gracefully."""
        # Invalid regex: unclosed bracket
        blacklist = DomainBlacklist(custom_blacklist=[r"[invalid"])

        # Should not crash, just log warning
        # The invalid pattern should be in patterns but not compiled
        assert r"[invalid" in blacklist.patterns
        # But it shouldn't crash when checking URLs
        result = blacklist.is_blacklisted("https://example.com")
        assert isinstance(result, bool)
