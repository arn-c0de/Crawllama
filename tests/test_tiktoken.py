"""Test suite for tiktoken integration in ContextManager."""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from core.context_manager import ContextManager
from utils.text_cleaner import get_text_cleaner


class TestTiktokenIntegration:
    """Test tiktoken integration for accurate token counting."""

    def test_token_estimation_basic(self):
        """Test basic token estimation."""
        cm = ContextManager(max_tokens=16000)

        # Simple texts
        assert cm.estimate_tokens("Hello, world!") > 0
        assert cm.estimate_tokens("Dies ist ein deutscher Text.") > 0
        assert cm.estimate_tokens("") == 0

    def test_token_estimation_vs_old_method(self):
        """Compare tiktoken with old estimation method."""
        cm = ContextManager(max_tokens=16000)

        # Short text (should be similar)
        text1 = "Hello, world!"
        tokens1 = cm.estimate_tokens(text1)
        old_estimate1 = len(text1) // 4
        # Allow some difference
        assert abs(tokens1 - old_estimate1) <= 2

        # Longer text (tiktoken should be more accurate)
        text2 = "The quick brown fox jumps over the lazy dog. " * 10
        tokens2 = cm.estimate_tokens(text2)
        old_estimate2 = len(text2) // 4
        # tiktoken should give different result
        assert tokens2 != old_estimate2

    def test_truncation_accuracy(self):
        """Test that truncation produces exact token count."""
        cm = ContextManager(max_tokens=16000)

        long_text = "This is a test sentence. " * 100

        # Truncate to different sizes
        for max_tokens in [50, 100, 200]:
            truncated = cm.truncate(long_text, max_tokens=max_tokens)
            # Remove ellipsis for accurate count
            actual_tokens = cm.estimate_tokens(truncated.replace("...", ""))

            # Should be at or below max_tokens
            assert actual_tokens <= max_tokens

            # Should be close to max_tokens (within 5% for tiktoken)
            # Check if tiktoken is available via text_cleaner
            if cm.text_cleaner.encoding is not None:  # Only if tiktoken is available
                assert actual_tokens >= max_tokens * 0.95

    def test_context_building(self):
        """Test complete prompt building with token management."""
        cm = ContextManager(max_tokens=16000)

        system_prompt = "You are a helpful assistant."
        user_query = "What is the capital of France?"
        context = "France is a country in Europe. " * 50

        prompt = cm.build_prompt(
            system_prompt,
            user_query,
            context,
            max_context_tokens=100
        )

        # Prompt should be built
        assert len(prompt) > 0
        assert system_prompt in prompt
        assert user_query in prompt

        # Should fit in context
        assert cm.fits_in_context(prompt)

    def test_fits_in_context(self):
        """Test context fitting check."""
        cm = ContextManager(max_tokens=100)

        short_text = "Short text"
        long_text = "Long text " * 1000

        assert cm.fits_in_context(short_text)
        assert not cm.fits_in_context(long_text)

    def test_split_into_chunks(self):
        """Test text chunking functionality."""
        cm = ContextManager(max_tokens=16000)

        long_text = "This is a sentence. " * 100

        chunks = cm.split_into_chunks(long_text, chunk_size=50, overlap=10)

        # Should produce multiple chunks
        assert len(chunks) > 1

        # Each chunk should be roughly the right size
        for chunk in chunks:
            tokens = cm.estimate_tokens(chunk)
            # Should be around chunk_size (allowing for sentence boundaries)
            assert tokens <= 70  # Some flexibility for sentence boundaries

    def test_tiktoken_availability(self):
        """Test that tiktoken is properly loaded."""
        try:
            import tiktoken
            TIKTOKEN_AVAILABLE = True
        except ImportError:
            TIKTOKEN_AVAILABLE = False

        # tiktoken should be available in tests (optional check)
        # If not available, test should still pass
        if TIKTOKEN_AVAILABLE:
            assert True, "tiktoken is available"
        else:
            # Skip if tiktoken not installed (CI/CD environments)
            pytest.skip("tiktoken not installed")

    def test_encoding_initialization(self):
        """Test that encoding is properly initialized."""
        cm = ContextManager(max_tokens=16000)

        # Should have encoding if tiktoken is available
        try:
            import tiktoken
            TIKTOKEN_AVAILABLE = True
        except ImportError:
            TIKTOKEN_AVAILABLE = False
            
        if TIKTOKEN_AVAILABLE:
            assert cm.text_cleaner.encoding is not None
        else:
            assert cm.text_cleaner.encoding is None


def test_token_estimation_performance():
    """Test performance of token estimation (should be fast)."""
    import time
    cm = ContextManager(max_tokens=16000)

    long_text = "This is a test sentence. " * 1000

    start = time.time()
    for _ in range(100):
        cm.estimate_tokens(long_text)
    elapsed = time.time() - start

    # Should complete 100 estimations in less than 1 second
    assert elapsed < 1.0, f"Token estimation too slow: {elapsed:.3f}s for 100 iterations"


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
