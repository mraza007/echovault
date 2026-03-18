"""Tests for hybrid search functionality."""

import pytest
from memory.search import adjust_result_scores, merge_results


class TestMergeResults:
    """Unit tests for merge_results function."""

    def test_deduplicates_by_id(self):
        """Results with same id should be combined, not duplicated."""
        fts_results = [
            {"id": "1", "score": 10.0, "content": "test"},
            {"id": "2", "score": 5.0, "content": "other"}
        ]
        vec_results = [
            {"id": "1", "score": 0.9, "content": "test"},
            {"id": "3", "score": 0.8, "content": "another"}
        ]

        merged = merge_results(fts_results, vec_results, limit=10)

        # Should have 3 unique results
        assert len(merged) == 3
        ids = [r["id"] for r in merged]
        assert len(ids) == len(set(ids))  # No duplicates
        assert set(ids) == {"1", "2", "3"}

    def test_combines_scores_correctly(self):
        """Scores should be weighted 0.3 * fts + 0.7 * vec after normalization."""
        fts_results = [
            {"id": "1", "score": 10.0, "content": "test"}
        ]
        vec_results = [
            {"id": "1", "score": 1.0, "content": "test"}
        ]

        merged = merge_results(fts_results, vec_results,
                             fts_weight=0.3, vec_weight=0.7, limit=10)

        # FTS score normalized: 10.0 / 10.0 = 1.0
        # Vec score normalized: 1.0 / 1.0 = 1.0
        # Combined: 0.3 * 1.0 + 0.7 * 1.0 = 1.0
        assert len(merged) == 1
        assert merged[0]["id"] == "1"
        assert merged[0]["score"] == pytest.approx(1.0)

    def test_combines_scores_with_different_weights(self):
        """Test score combination with partial overlap."""
        fts_results = [
            {"id": "1", "score": 100.0, "content": "test"},
            {"id": "2", "score": 50.0, "content": "other"}
        ]
        vec_results = [
            {"id": "1", "score": 0.5, "content": "test"}
        ]

        merged = merge_results(fts_results, vec_results,
                             fts_weight=0.3, vec_weight=0.7, limit=10)

        # FTS normalized: id=1 -> 1.0, id=2 -> 0.5
        # Vec normalized: id=1 -> 1.0
        # Scores:
        #   id=1: 0.3 * 1.0 + 0.7 * 1.0 = 1.0
        #   id=2: 0.3 * 0.5 = 0.15
        assert len(merged) == 2
        assert merged[0]["id"] == "1"
        assert merged[0]["score"] == pytest.approx(1.0)
        assert merged[1]["id"] == "2"
        assert merged[1]["score"] == pytest.approx(0.15)

    def test_sorted_by_score_descending(self):
        """Results should be sorted by combined score, highest first."""
        fts_results = [
            {"id": "1", "score": 10.0, "content": "low"},
            {"id": "2", "score": 100.0, "content": "high"}
        ]
        vec_results = [
            {"id": "1", "score": 0.1, "content": "low"},
            {"id": "2", "score": 1.0, "content": "high"}
        ]

        merged = merge_results(fts_results, vec_results, limit=10)

        # Should be sorted descending by score
        assert len(merged) == 2
        assert merged[0]["id"] == "2"  # Higher combined score
        assert merged[1]["id"] == "1"  # Lower combined score
        # Verify scores are descending
        for i in range(len(merged) - 1):
            assert merged[i]["score"] >= merged[i + 1]["score"]

    def test_respects_limit(self):
        """Should return at most limit results."""
        fts_results = [
            {"id": str(i), "score": float(i), "content": f"item{i}"}
            for i in range(10)
        ]
        vec_results = []

        merged = merge_results(fts_results, vec_results, limit=5)

        assert len(merged) == 5

    def test_handles_empty_fts_results(self):
        """Should work when FTS returns no results."""
        fts_results = []
        vec_results = [
            {"id": "1", "score": 0.9, "content": "test"},
            {"id": "2", "score": 0.8, "content": "other"}
        ]

        merged = merge_results(fts_results, vec_results, limit=10)

        assert len(merged) == 2
        # Scores should be normalized and weighted
        assert merged[0]["id"] == "1"
        assert merged[0]["score"] == pytest.approx(0.7)  # 0.7 * 1.0
        assert merged[1]["id"] == "2"
        assert merged[1]["score"] == pytest.approx(0.7 * (0.8 / 0.9))

    def test_handles_empty_vec_results(self):
        """Should work when vector search returns no results."""
        fts_results = [
            {"id": "1", "score": 100.0, "content": "test"},
            {"id": "2", "score": 50.0, "content": "other"}
        ]
        vec_results = []

        merged = merge_results(fts_results, vec_results, limit=10)

        assert len(merged) == 2
        # Only FTS scores, normalized and weighted
        assert merged[0]["id"] == "1"
        assert merged[0]["score"] == pytest.approx(0.3)  # 0.3 * 1.0
        assert merged[1]["id"] == "2"
        assert merged[1]["score"] == pytest.approx(0.15)  # 0.3 * 0.5

    def test_handles_both_empty(self):
        """Should return empty list when both inputs are empty."""
        merged = merge_results([], [], limit=10)
        assert merged == []

    def test_normalizes_fts_scores_to_0_1(self):
        """FTS scores should be normalized to 0-1 range."""
        fts_results = [
            {"id": "1", "score": 1000.0, "content": "high"},
            {"id": "2", "score": 500.0, "content": "mid"},
            {"id": "3", "score": 100.0, "content": "low"}
        ]
        vec_results = []

        merged = merge_results(fts_results, vec_results,
                             fts_weight=1.0, vec_weight=0.0, limit=10)

        # Check normalized scores (with fts_weight=1.0 for easier verification)
        assert merged[0]["score"] == pytest.approx(1.0)  # 1000/1000
        assert merged[1]["score"] == pytest.approx(0.5)  # 500/1000
        assert merged[2]["score"] == pytest.approx(0.1)  # 100/1000

    def test_normalizes_vec_scores_to_0_1(self):
        """Vector scores should be normalized to 0-1 range."""
        fts_results = []
        vec_results = [
            {"id": "1", "score": 10.0, "content": "high"},
            {"id": "2", "score": 5.0, "content": "mid"},
            {"id": "3", "score": 1.0, "content": "low"}
        ]

        merged = merge_results(fts_results, vec_results,
                             fts_weight=0.0, vec_weight=1.0, limit=10)

        # Check normalized scores (with vec_weight=1.0 for easier verification)
        assert merged[0]["score"] == pytest.approx(1.0)  # 10/10
        assert merged[1]["score"] == pytest.approx(0.5)  # 5/10
        assert merged[2]["score"] == pytest.approx(0.1)  # 1/10

class TestTieredSearch:
    """Unit tests for tiered_search function."""

    def test_tiered_search_skips_embedding_when_fts_sufficient(self):
        """Test that tiered search returns FTS results without calling embed."""
        from unittest.mock import MagicMock
        from memory.search import tiered_search

        db = MagicMock()
        db.fts_search.return_value = [
            {"id": "1", "title": "Auth fix", "score": 5.0},
            {"id": "2", "title": "Auth setup", "score": 4.0},
            {"id": "3", "title": "Auth config", "score": 3.0},
        ]

        embed_provider = MagicMock()

        results = tiered_search(db, embed_provider, "auth", limit=3)

        assert len(results) == 3
        # Embedding provider should NOT have been called
        embed_provider.embed.assert_not_called()

    def test_tiered_search_calls_embedding_when_fts_sparse(self):
        """Test that tiered search falls back to hybrid when FTS returns few results."""
        from unittest.mock import MagicMock
        from memory.search import tiered_search

        db = MagicMock()
        db.fts_search.return_value = [
            {"id": "1", "title": "Result", "score": 1.0},
        ]
        db.vector_search.return_value = [
            {"id": "2", "title": "Semantic match", "score": 0.9},
        ]

        embed_provider = MagicMock()
        embed_provider.embed.return_value = [0.1] * 768

        results = tiered_search(db, embed_provider, "vague query", limit=5)

        # Should have called embedding since FTS was sparse
        embed_provider.embed.assert_called_once()
        assert len(results) >= 1

    def test_tiered_search_calls_embedding_when_fts_is_only_noise(self):
        """Weak lexical tail should not suppress semantic search."""
        from unittest.mock import MagicMock
        from memory.search import tiered_search

        db = MagicMock()
        db.fts_search.return_value = [
            {"id": "1", "title": "Bare lexical hit", "score": 10.0},
            {"id": "2", "title": "Stopword noise", "score": 1.4},
            {"id": "3", "title": "More stopword noise", "score": 1.0},
        ]
        db.vector_search.return_value = [
            {"id": "4", "title": "Semantic match", "score": 0.9},
        ]

        embed_provider = MagicMock()
        embed_provider.embed.return_value = [0.1] * 768

        results = tiered_search(db, embed_provider, "natural language question", limit=5)

        embed_provider.embed.assert_called_once()
        assert len(results) >= 1

    def test_tiered_search_prefers_semantic_top_hit_when_single_lexical_result_conflicts(self):
        """A lone lexical hit should not dominate a stronger semantic result."""
        from unittest.mock import MagicMock
        from memory.search import tiered_search

        db = MagicMock()
        db.fts_search.return_value = [
            {"id": "lexical", "title": "Keyword overlap", "score": 6.0},
        ]
        db.vector_search.return_value = [
            {"id": "semantic", "title": "Best semantic match", "score": 0.95},
            {"id": "lexical", "title": "Keyword overlap", "score": 0.20},
        ]

        embed_provider = MagicMock()
        embed_provider.embed.return_value = [0.1] * 768

        results = tiered_search(db, embed_provider, "paraphrased idea", limit=5)

        assert results[0]["id"] == "semantic"

    def test_tiered_search_fts_only_when_no_embed_provider(self):
        """Test that tiered search works with no embedding provider."""
        from unittest.mock import MagicMock
        from memory.search import tiered_search

        db = MagicMock()
        db.fts_search.return_value = [
            {"id": "1", "title": "Result", "score": 5.0},
        ]

        results = tiered_search(db, None, "query", limit=5)

        assert len(results) == 1
        # Score should be normalized
        assert results[0]["score"] == 1.0

    def test_tiered_search_falls_back_on_embed_exception(self):
        """Test that tiered search falls back to FTS on embedding error."""
        from unittest.mock import MagicMock
        from memory.search import tiered_search

        db = MagicMock()
        db.fts_search.return_value = [
            {"id": "1", "title": "Result", "score": 3.0},
        ]

        embed_provider = MagicMock()
        embed_provider.embed.side_effect = RuntimeError("API down")

        results = tiered_search(db, embed_provider, "query", limit=5)

        # Should still return FTS results despite embed failure
        assert len(results) == 1


    def test_preserves_result_metadata(self):
        """Should preserve all fields from original results."""
        fts_results = [
            {
                "id": "1",
                "score": 10.0,
                "content": "test content",
                "project": "myproject",
                "source": "mysource",
                "timestamp": "2024-01-01"
            }
        ]
        vec_results = []

        merged = merge_results(fts_results, vec_results, limit=10)

        assert len(merged) == 1
        result = merged[0]
        assert result["id"] == "1"
        assert result["content"] == "test content"
        assert result["project"] == "myproject"
        assert result["source"] == "mysource"
        assert result["timestamp"] == "2024-01-01"
        assert "score" in result  # Score is updated


class TestAdjustResultScores:
    """Unit tests for low-signal diagnostic down-ranking."""

    def test_downranks_probe_results_for_normal_queries(self):
        """Diagnostic probe memories should not dominate user-facing retrieval."""
        results = [
            {"id": "probe", "title": "Temporary probe memory", "category": "test", "tags": "[]", "score": 1.0},
            {"id": "real", "title": "Production auth fix", "category": "bug", "tags": '["auth"]', "score": 0.8},
        ]

        ranked = adjust_result_scores(results, "auth issue")

        assert ranked[0]["id"] == "real"
        assert ranked[1]["id"] == "probe"

    def test_preserves_probe_results_when_query_explicitly_requests_diagnostics(self):
        """Do not hide diagnostic memories when the user explicitly asks for them."""
        results = [
            {"id": "probe", "title": "Temporary probe memory", "category": "test", "tags": "[]", "score": 1.0},
            {"id": "real", "title": "Production auth fix", "category": "bug", "tags": '["auth"]', "score": 0.8},
        ]

        ranked = adjust_result_scores(results, "diagnostic probe memory")

        assert ranked[0]["id"] == "probe"
