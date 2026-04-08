"""Tests for LLM-based compression providers."""

import pytest
from memory.compression import (
    TruncationCompressor,
    OllamaCompressor,
    OpenAICompressor,
)


class TestTruncationCompressor:
    """Tests for fallback truncation compressor."""
    
    def test_short_text_unchanged(self):
        comp = TruncationCompressor()
        text = "Short text."
        result = comp.compress(text, max_chars=100)
        assert result == text
    
    def test_truncation_with_paragraphs(self):
        comp = TruncationCompressor()
        text = "First paragraph.\n\nMiddle content.\n\nLast paragraph."
        result = comp.compress(text, max_chars=50)
        assert "First paragraph" in result
        assert "Last paragraph" in result
        assert "..." in result
    
    def test_few_paragraphs_fallback(self):
        comp = TruncationCompressor()
        text = "Only two paragraphs.\n\nSecond one here."
        result = comp.compress(text, max_chars=20)
        assert result.endswith("...")


class TestOllamaCompressor:
    """Tests for Ollama-based compression."""
    
    def test_short_text_unchanged(self):
        comp = OllamaCompressor()
        text = "Short."
        result = comp.compress(text, max_chars=100)
        assert result == text
    
    def test_fallback_on_error(self):
        # Use invalid URL to trigger fallback
        comp = OllamaCompressor(base_url="http://invalid:99999")
        long_text = "First.\n\n" + "Content. " * 100 + "\n\nLast."
        result = comp.compress(long_text, max_chars=50)
        # Should fall back to truncation
        assert "First" in result or result.endswith("...")


class TestOpenAICompressor:
    """Tests for OpenAI-based compression."""
    
    def test_short_text_unchanged(self):
        comp = OpenAICompressor(api_key="test-key")
        text = "Short."
        result = comp.compress(text, max_chars=100)
        assert result == text
    
    def test_no_api_key_fallback(self):
        comp = OpenAICompressor(api_key="")
        long_text = "First.\n\n" + "Content. " * 100 + "\n\nLast."
        result = comp.compress(long_text, max_chars=50)
        # Should fall back immediately
        assert result.endswith("...")


class TestCompressorIntegration:
    """Integration tests for compression with memory tiers."""
    
    def test_compression_in_slow_tier(self):
        import tempfile
        import os
        from memory.unified import SlowMemoryTier, MemoryEntry, MemoryTier
        
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        
        try:
            # Use truncation compressor (no LLM needed)
            compressor = TruncationCompressor()
            slow = SlowMemoryTier(db_path, compression_provider=compressor)
            
            # Create entry with long details
            entry = MemoryEntry(
                id="test-1",
                title="Test Entry",
                what="Summary",
                tier=MemoryTier.SLOW,
                timestamp=1234567890,
                details="First para.\n\n" + "Middle content. " * 50 + "\n\nLast para."
            )
            
            slow.store(entry, compress=True)
            
            # Verify compression happened
            cursor = slow.db.cursor()
            cursor.execute("SELECT summary FROM memories WHERE id = ?", ("test-1",))
            row = cursor.fetchone()
            assert row["summary"] is not None
            assert len(row["summary"]) <= 500
            
        finally:
            os.unlink(db_path)
