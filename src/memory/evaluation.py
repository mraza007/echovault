"""Offline retrieval evaluation for redacted golden-query datasets."""

from __future__ import annotations

import math
import time
from pathlib import Path
from typing import Any

import yaml


def load_golden_set(path: str) -> list[dict[str, Any]]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    cases = data.get("queries", data if isinstance(data, list) else [])
    if not isinstance(cases, list):
        raise ValueError("Golden set must be a list or contain a 'queries' list")
    return cases


def evaluate(service, cases: list[dict[str, Any]], *, limit: int = 5, project: str | None = None) -> dict:
    recalls: list[float] = []
    reciprocal_ranks: list[float] = []
    ndcgs: list[float] = []
    irrelevant = returned = tokens = total_hits = 0
    negative_queries = negative_false_positives = 0
    latencies: list[float] = []
    case_results = []
    for case in cases:
        expected = {str(v).lower() for v in case.get("expected", [])}
        started = time.perf_counter()
        results = service.search(
            str(case["query"]), limit=limit, project=case.get("project", project),
            record_feedback=False,
        )
        latency_ms = (time.perf_counter() - started) * 1000
        latencies.append(latency_ms)
        keys = [str(r["id"]).lower() for r in results]
        titles = [str(r["title"]).lower() for r in results]
        hits = [i for i, (rid, title) in enumerate(zip(keys, titles), 1) if rid in expected or title in expected]
        hit_count = len(hits)
        total_hits += hit_count
        if expected:
            recalls.append(hit_count / len(expected))
            reciprocal_ranks.append(1.0 / hits[0] if hits else 0.0)
        else:
            negative_queries += 1
            if results:
                negative_false_positives += 1
        dcg = sum(1.0 / math.log2(rank + 1) for rank in hits)
        ideal = sum(1.0 / math.log2(rank + 1) for rank in range(1, min(len(expected), limit) + 1))
        if expected:
            ndcgs.append(dcg / ideal if ideal else 0.0)
        returned += len(results)
        irrelevant += len(results) - hit_count
        tokens += sum(max(1, len(" ".join(str(r.get(k, "") or "") for k in ("title", "what", "why", "impact"))) // 4) for r in results)
        case_results.append({"query": case["query"], "hits": hit_count, "returned": len(results), "latency_ms": round(latency_ms, 2)})
    positive_count = len(recalls) or 1
    return {
        "queries": len(cases), "positive_queries": len(recalls),
        "negative_queries": negative_queries,
        "recall_at_k": sum(recalls) / positive_count,
        "mrr": sum(reciprocal_ranks) / positive_count,
        "ndcg_at_k": sum(ndcgs) / positive_count,
        "precision_at_k": total_hits / returned if returned else 1.0,
        "irrelevant_result_rate": irrelevant / returned if returned else 0.0,
        "negative_query_false_positive_rate": (
            negative_false_positives / negative_queries if negative_queries else 0.0
        ),
        "mean_latency_ms": sum(latencies) / (len(cases) or 1),
        "context_tokens": tokens, "cases": case_results,
    }


def sweep_thresholds(
    service,
    cases: list[dict[str, Any]],
    *,
    limit: int = 5,
    project: str | None = None,
    relevance_values: tuple[float, ...] = (0.0, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8),
    vector_values: tuple[float, ...] = (0.0, 0.03, 0.04, 0.05, 0.06, 0.07, 0.1),
    min_recall: float = 1.0,
    max_negative_fpr: float = 0.0,
) -> dict:
    """Evaluate a threshold grid without persisting configuration changes."""
    original_relevance = service.config.context.min_relevance
    original_vector = service.config.context.min_vector_similarity
    candidates = []
    try:
        for min_relevance in relevance_values:
            for min_vector_similarity in vector_values:
                service.config.context.min_relevance = min_relevance
                service.config.context.min_vector_similarity = min_vector_similarity
                report = evaluate(service, cases, limit=limit, project=project)
                quality = (
                    0.5 * report["recall_at_k"]
                    + 0.2 * report["ndcg_at_k"]
                    + 0.3 * (1.0 - report["irrelevant_result_rate"])
                )
                candidates.append({
                    "min_relevance": min_relevance,
                    "min_vector_similarity": min_vector_similarity,
                    "quality": round(quality, 6),
                    **{key: report[key] for key in (
                        "recall_at_k", "precision_at_k", "mrr", "ndcg_at_k",
                        "irrelevant_result_rate", "negative_query_false_positive_rate",
                        "mean_latency_ms", "context_tokens",
                    )},
                })
    finally:
        service.config.context.min_relevance = original_relevance
        service.config.context.min_vector_similarity = original_vector
    candidates.sort(key=lambda c: (
        -c["quality"], -c["recall_at_k"], c["irrelevant_result_rate"],
        -c["min_vector_similarity"], -c["min_relevance"],
    ))
    eligible = [
        candidate for candidate in candidates
        if candidate["recall_at_k"] >= min_recall
        and candidate["negative_query_false_positive_rate"] <= max_negative_fpr
    ]
    eligible.sort(key=lambda c: (
        c["irrelevant_result_rate"], -c["precision_at_k"],
        -c["min_relevance"], -c["min_vector_similarity"], -c["quality"],
    ))
    return {
        "objective": "0.5*recall + 0.2*nDCG + 0.3*(1-irrelevant_rate)",
        "minimum_recall": min_recall,
        "maximum_negative_query_false_positive_rate": max_negative_fpr,
        "recommended": eligible[0] if eligible else None,
        "warning": None if eligible else (
            "No threshold candidate satisfies both safety constraints; "
            "improve ranking or embeddings before changing defaults."
        ),
        "best_tradeoff": candidates[0] if candidates else None,
        "evaluated_candidates": len(candidates),
        "candidates": candidates[:10],
    }
