"""Living-memory lifecycle review and health diagnostics."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from difflib import SequenceMatcher


def lifecycle_review(db, project: str | None = None) -> dict[str, list]:
    memories = db.list_memories(limit=10000, project=project, include_archived=True)
    now = datetime.now(timezone.utc)
    report: dict[str, list] = {k: [] for k in ("duplicates", "contradictions", "stale", "superseded", "completed_followups", "broad")}
    active = [m for m in memories if (m.get("status") or "active") == "active"]
    for i, left in enumerate(active):
        if left.get("valid_until"):
            try:
                if datetime.fromisoformat(left["valid_until"].replace("Z", "+00:00")) < now:
                    report["stale"].append(left["id"])
            except ValueError:
                pass
        if left.get("superseded_by"):
            report["superseded"].append({"id": left["id"], "by": left["superseded_by"]})
        try:
            structured = json.loads(left.get("structured_data") or "{}")
        except (TypeError, json.JSONDecodeError):
            structured = {}
        followups = structured.get("follow_ups", [])
        if followups and all(str(v).strip().lower().startswith(("done", "[x]", "complete")) for v in followups):
            report["completed_followups"].append(left["id"])
        if len(left.get("what", "")) > 800 or len(structured.get("steps", [])) > 20:
            report["broad"].append(left["id"])
        for right in active[i + 1:]:
            title_ratio = SequenceMatcher(None, left["title"].lower(), right["title"].lower()).ratio()
            what_ratio = SequenceMatcher(None, left["what"].lower(), right["what"].lower()).ratio()
            if title_ratio >= 0.9 and what_ratio >= 0.75:
                report["duplicates"].append([left["id"], right["id"]])
            elif title_ratio >= 0.9 and what_ratio < 0.35:
                report["contradictions"].append([left["id"], right["id"]])
    return report


def doctor(service, project: str | None = None) -> dict:
    db = service.db
    memories = db.list_memories(limit=100000, project=project, include_archived=True)
    cursor = db.conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM memory_details d LEFT JOIN memories m ON m.id=d.memory_id WHERE m.id IS NULL")
    orphaned_details = cursor.fetchone()[0]
    missing_files = sum(1 for m in memories if not os.path.exists(m["file_path"]))
    broken_related = 0
    for m in memories:
        try:
            paths = json.loads(m.get("related_files") or "[]")
        except (TypeError, json.JSONDecodeError):
            paths = []
        broken_related += sum(1 for path in paths if os.path.isabs(path) and not os.path.exists(path))
    vector_rows = 0
    if db.has_vec_table():
        cursor.execute("SELECT COUNT(*) FROM memories_vec")
        vector_rows = cursor.fetchone()[0]
    active_count = sum(1 for m in memories if (m.get("status") or "active") == "active")
    lifecycle = lifecycle_review(db, project)
    return {
        "status": "ok" if not (orphaned_details or missing_files) else "warning",
        "memories": len(memories), "active": active_count,
        "missing_markdown_files": missing_files, "orphaned_details": orphaned_details,
        "broken_absolute_related_files": broken_related,
        "vectors": {"available": db.has_vec_table(), "rows": vector_rows, "missing": max(0, len(memories) - vector_rows)},
        "embedding_dimension": db.get_embedding_dim(),
        "lifecycle_counts": {key: len(value) for key, value in lifecycle.items()},
    }
