"""Hybrid search combining FTS5 keyword search and semantic vector search."""

import re
from typing import Optional

from memory.db import MemoryDB
from memory.embeddings.base import EmbeddingProvider


_LOW_SIGNAL_MARKERS = {
    "diagnostic",
    "diagnostics",
    "probe",
    "temporary",
    "test",
    "validation",
}


def _tokenize(text: str) -> set[str]:
    return {token for token in re.findall(r"\w+", text.lower(), flags=re.UNICODE)}


def _lexical_coverage(result: dict, query: str) -> float:
    """Return the fraction of meaningful query terms present in a result."""
    query_terms = {
        token for token in _tokenize(query)
        if len(token) > 1 and token not in {
            "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
            "in", "is", "it", "of", "on", "or", "that", "the", "this", "to", "with",
        }
    }
    if not query_terms:
        return 1.0
    haystack = _tokenize(" ".join(str(result.get(field, "") or "") for field in (
        "title", "what", "why", "impact", "tags", "category",
    )))
    return len(query_terms & haystack) / len(query_terms)


def adjust_result_scores(results: list[dict], query: str) -> list[dict]:
    """Down-rank low-signal housekeeping memories unless the query asks for them.

    Temporary probes and diagnostics are useful for agent maintenance, but they
    should not dominate normal user-facing retrieval.
    """
    query_terms = _tokenize(query)
    wants_low_signal = bool(query_terms & _LOW_SIGNAL_MARKERS)
    adjusted: list[dict] = []

    for result in results:
        item = dict(result)
        score = float(item.get("score", 0.0))

        if not wants_low_signal:
            haystack = " ".join(
                str(item.get(field, "")).lower() for field in ("title", "category", "tags")
            )
            if any(marker in haystack for marker in {"temporary", "probe", "diagnostic", "diagnostics"}):
                score *= 0.55
            elif any(marker in haystack for marker in {"test", "validation"}):
                score *= 0.75

        item["score"] = score
        adjusted.append(item)

    return sorted(adjusted, key=lambda x: x["score"], reverse=True)


def merge_results(
    fts_results: list[dict],
    vec_results: list[dict],
    fts_weight: float = 0.3,
    vec_weight: float = 0.7,
    limit: int = 5,
) -> list[dict]:
    """Merge FTS5 and vector search results with weighted scoring.

    Args:
        fts_results: Results from FTS5 keyword search with 'id' and 'score' fields
        vec_results: Results from vector search with 'id' and 'score' fields
        fts_weight: Weight for FTS5 scores (default 0.3)
        vec_weight: Weight for vector scores (default 0.7)
        limit: Maximum number of results to return

    Returns:
        Merged and re-ranked results, sorted by combined score descending
    """
    # Normalize FTS scores to 0-1
    fts_results = [dict(r) for r in fts_results]
    vec_results = [dict(r) for r in vec_results]
    raw_fts = {r["id"]: float(r.get("score", 0.0)) for r in fts_results}
    raw_vec = {r["id"]: float(r.get("score", 0.0)) for r in vec_results}
    if fts_results:
        max_fts = max(r["score"] for r in fts_results) or 1.0
        for r in fts_results:
            r["score"] = r["score"] / max_fts if max_fts > 0 else 0.0

    # Normalize vec scores to 0-1
    if vec_results:
        max_vec = max(r["score"] for r in vec_results) or 1.0
        for r in vec_results:
            r["score"] = r["score"] / max_vec if max_vec > 0 else 0.0

    # Combine with weighted scoring, dedup by id
    scores: dict[str, dict] = {}
    for r in fts_results:
        rid = r["id"]
        scores[rid] = dict(r)
        scores[rid]["score"] = fts_weight * r["score"]
    for r in vec_results:
        rid = r["id"]
        if rid in scores:
            scores[rid]["score"] += vec_weight * r["score"]
        else:
            scores[rid] = dict(r)
            scores[rid]["score"] = vec_weight * r["score"]

    ranked = sorted(scores.values(), key=lambda x: x["score"], reverse=True)
    for item in ranked:
        item["score_explain"] = {
            "mode": "hybrid",
            "fts_raw": round(raw_fts.get(item["id"], 0.0), 6),
            "vector_similarity": round(raw_vec.get(item["id"], 0.0), 6),
            "fts_weight": fts_weight,
            "vector_weight": vec_weight,
            "combined": round(float(item["score"]), 6),
        }
    return ranked[:limit]


def tiered_search(
    db: MemoryDB,
    embedding_provider: Optional[EmbeddingProvider],
    query: str,
    limit: int = 5,
    min_fts_results: int = 3,
    project: Optional[str] = None,
    source: Optional[str] = None,
    include_archived: bool = False,
    min_relevance: float = 0.0,
    min_vector_similarity: float = 0.0,
) -> list[dict]:
    """FTS-first tiered search that only calls embed when FTS results are sparse.

    Avoids embedding API latency (5-20s) for most searches by checking
    FTS results first and only falling back to hybrid search when needed.

    Args:
        db: Memory database instance
        embedding_provider: Embedding provider for query vectorization, or None for FTS-only
        query: Search query string
        limit: Maximum number of results to return
        min_fts_results: Minimum FTS results before skipping embedding (default 3)
        project: Optional project filter
        source: Optional source filter

    Returns:
        Search results sorted by score descending
    """
    fts_results = db.fts_search(
        query,
        limit=limit * 2,
        project=project,
        source=source,
        include_archived=include_archived,
    )

    # Normalize FTS scores to 0-1
    if fts_results:
        max_score = max(r["score"] for r in fts_results) or 1.0
        for r in fts_results:
            r["score"] = r["score"] / max_score if max_score > 0 else 0.0

    # Only skip embeddings when we have several strong lexical matches.
    # Raw result count alone is too noisy for natural-language queries because
    # weak OR matches can inflate FTS results without being genuinely relevant.
    strong_fts_results = [r for r in fts_results if r["score"] >= 0.15]
    top_lexical_coverage = _lexical_coverage(fts_results[0], query) if fts_results else 0.0
    if len(strong_fts_results) >= min_fts_results and top_lexical_coverage >= 0.5:
        ranked = adjust_result_scores(fts_results, query)
        for item in ranked:
            item["score_explain"] = {
                "mode": "fts", "normalized": round(float(item["score"]), 6),
                "query_term_coverage": round(_lexical_coverage(item, query), 6),
            }
        return [r for r in ranked if r["score"] >= min_relevance][:limit]

    # If no embedding provider, return FTS-only
    if embedding_provider is None:
        return [r for r in adjust_result_scores(fts_results, query) if r["score"] >= min_relevance][:limit]

    # FTS results are sparse — fall back to hybrid (embed + vector search + merge)
    try:
        query_vec = embedding_provider.search(query)
        vec_results = db.vector_search(
            query_vec,
            limit=limit * 2,
            project=project,
            source=source,
            include_archived=include_archived,
        )
        vec_results = [
            r for r in vec_results
            if float(r.get("score", 0.0)) >= min_vector_similarity
        ]
        # When lexical evidence is sparse and disagrees with the top semantic hit,
        # trust vectors more heavily. A single strong keyword match can otherwise
        # overwhelm the actual best semantic result.
        fts_weight = 0.3
        vec_weight = 0.7
        if (
            len(strong_fts_results) == 1
            and vec_results
            and strong_fts_results[0]["id"] != vec_results[0]["id"]
        ):
            fts_weight = 0.05
            vec_weight = 0.95

        # FTS scores already normalized (max=1.0); merge_results re-normalizes
        # which is a no-op on 0-1 scores.
        ranked = adjust_result_scores(
            merge_results(
                fts_results,
                vec_results,
                fts_weight=fts_weight,
                vec_weight=vec_weight,
                limit=limit * 2,
            ),
            query,
        )
        return [r for r in ranked if r["score"] >= min_relevance][:limit]
    except Exception:
        # On any embedding/vector error, return whatever FTS found
        return [r for r in adjust_result_scores(fts_results, query) if r["score"] >= min_relevance][:limit]


def hybrid_search(
    db: MemoryDB,
    embedding_provider: Optional[EmbeddingProvider],
    query: str,
    limit: int = 5,
    project: Optional[str] = None,
    source: Optional[str] = None,
    include_archived: bool = False,
    min_relevance: float = 0.0,
    min_vector_similarity: float = 0.0,
) -> list[dict]:
    """Run FTS5 and optionally vector search, merge results.

    When embedding_provider is None, runs FTS-only search.

    Args:
        db: Memory database instance
        embedding_provider: Embedding provider for query vectorization, or None for FTS-only
        query: Search query string
        limit: Maximum number of results to return
        project: Optional project filter
        source: Optional source filter

    Returns:
        Merged and re-ranked search results
    """
    fts_results = db.fts_search(
        query,
        limit=limit * 2,
        project=project,
        source=source,
        include_archived=include_archived,
    )

    if embedding_provider is None:
        # FTS-only mode: normalize scores and return directly
        if fts_results:
            max_score = max(r["score"] for r in fts_results) or 1.0
            for r in fts_results:
                r["score"] = r["score"] / max_score if max_score > 0 else 0.0
        return [r for r in adjust_result_scores(fts_results, query) if r["score"] >= min_relevance][:limit]

    query_vec = embedding_provider.search(query)
    vec_results = db.vector_search(
        query_vec,
        limit=limit * 2,
        project=project,
        source=source,
        include_archived=include_archived,
    )
    vec_results = [r for r in vec_results if float(r.get("score", 0.0)) >= min_vector_similarity]
    ranked = adjust_result_scores(
        merge_results(fts_results, vec_results, limit=limit * 2), query
    )
    return [r for r in ranked if r["score"] >= min_relevance][:limit]
