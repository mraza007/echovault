import json

from memory.evaluation import evaluate, sweep_thresholds
from memory.health import doctor, lifecycle_review
from memory.models import RawMemoryInput
from memory.core import MemoryService


def test_structured_living_memory_round_trip(env_home):
    svc = MemoryService(memory_home=str(env_home))
    result = svc.save(RawMemoryInput(
        title="Release playbook", what="Repeatable release procedure", category="playbook",
        triggers=["release"], steps=["bump version", "run tests"],
        verification=["memory --version"], confidence=0.9,
        commit_sha="abc123", branch="main", last_verified="2026-07-12",
    ), project="test-project")
    record = svc.db.get_memory(result["id"])
    assert json.loads(record["structured_data"])["steps"] == ["bump version", "run tests"]
    assert record["confidence"] == 0.9
    assert record["commit_sha"] == "abc123"
    assert "**Living Memory:**" in open(record["file_path"], encoding="utf-8").read()
    svc.close()


def test_context_token_budget_and_feedback(env_home):
    svc = MemoryService(memory_home=str(env_home))
    saved = svc.save(RawMemoryInput(title="Project state", what="x" * 200, category="project_state"), project="test-project")
    results, _ = svc.get_context(project="test-project", token_budget=20)
    assert len(results) == 1  # one decisive memory is allowed even if it exceeds budget
    assert svc.db.get_memory(saved["id"])["retrieved_count"] >= 1
    svc.close()


def test_evaluation_metrics(env_home):
    svc = MemoryService(memory_home=str(env_home))
    saved = svc.save(RawMemoryInput(title="JWT decision", what="Use JWT authentication"), project="test-project")
    report = evaluate(svc, [{"query": "JWT", "expected": [saved["id"]]}], project="test-project")
    assert report["recall_at_k"] == 1.0
    assert report["mrr"] == 1.0
    assert report["precision_at_k"] == 1.0
    assert report["context_tokens"] > 0
    svc.close()


def test_negative_queries_do_not_inflate_recall(env_home):
    svc = MemoryService(memory_home=str(env_home))
    saved = svc.save(RawMemoryInput(title="JWT decision", what="Use JWT authentication"), project="test-project")
    report = evaluate(svc, [
        {"query": "JWT", "expected": [saved["id"]]},
        {"query": "sourdough recipe", "expected": []},
    ], project="test-project")
    assert report["positive_queries"] == 1
    assert report["negative_queries"] == 1
    assert report["recall_at_k"] == 1.0
    assert "negative_query_false_positive_rate" in report
    svc.close()


def test_threshold_sweep_restores_configuration(env_home):
    svc = MemoryService(memory_home=str(env_home))
    saved = svc.save(RawMemoryInput(title="JWT decision", what="Use JWT authentication"), project="test-project")
    original = svc.config.context.min_vector_similarity
    report = sweep_thresholds(
        svc, [{"query": "JWT", "expected": [saved["id"]]}], project="test-project",
        relevance_values=(0.0, 0.15), vector_values=(0.0, 0.55),
    )
    assert report["recommended"] is not None
    assert len(report["candidates"]) == 4
    assert svc.config.context.min_vector_similarity == original
    svc.close()


def test_threshold_sweep_reports_when_no_safe_candidate(env_home):
    svc = MemoryService(memory_home=str(env_home))
    svc.save(RawMemoryInput(title="JWT decision", what="Use JWT authentication"), project="test-project")
    report = sweep_thresholds(
        svc,
        [
            {"query": "JWT", "expected": ["JWT decision"]},
            {"query": "sourdough recipe", "expected": []},
        ],
        project="test-project", relevance_values=(0.0,), vector_values=(0.0,),
        min_recall=1.0, max_negative_fpr=0.0,
    )
    assert report["recommended"] is None
    assert "No threshold candidate" in report["warning"]
    svc.close()


def test_lifecycle_and_doctor_are_non_mutating(env_home):
    svc = MemoryService(memory_home=str(env_home))
    svc.save(RawMemoryInput(title="Deploy steps", what="Run deploy command"), project="test-project")
    svc.save(RawMemoryInput(title="Deploy steps", what="Run deploy command"), project="test-project")
    review = lifecycle_review(svc.db, "test-project")
    assert "duplicates" in review
    report = doctor(svc, "test-project")
    assert report["memories"] >= 1
    assert "vectors" in report
    svc.close()
