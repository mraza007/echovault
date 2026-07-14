from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

VALID_CATEGORIES = (
    "decision", "pattern", "bug", "context", "learning", "playbook",
    "known_fix", "constraint", "project_state", "active_work",
)

CATEGORY_HEADINGS = {
    "decision": "Decisions",
    "pattern": "Patterns",
    "bug": "Bugs Fixed",
    "context": "Context",
    "learning": "Learnings",
    "playbook": "Playbooks",
    "known_fix": "Known Fixes",
    "constraint": "Constraints",
    "project_state": "Project State",
    "active_work": "Active Work",
}


@dataclass
class RawMemoryInput:
    """Raw input for creating a memory before processing."""

    title: str
    what: str
    why: Optional[str] = None
    impact: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    category: Optional[str] = None
    related_files: list[str] = field(default_factory=list)
    details: Optional[str] = None
    source: Optional[str] = None
    triggers: list[str] = field(default_factory=list)
    prerequisites: list[str] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)
    verification: list[str] = field(default_factory=list)
    follow_ups: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    alternatives_rejected: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    confidence: Optional[float] = None
    valid_from: Optional[str] = None
    valid_until: Optional[str] = None
    commit_sha: Optional[str] = None
    branch: Optional[str] = None
    links: list[str] = field(default_factory=list)
    last_verified: Optional[str] = None


@dataclass
class Memory:
    """A memory record with all metadata and references."""

    id: str
    title: str
    what: str
    why: Optional[str]
    impact: Optional[str]
    tags: list[str]
    category: Optional[str]
    project: str
    source: Optional[str]
    related_files: list[str]
    file_path: str
    section_anchor: str
    created_at: str
    updated_at: str
    status: str = "active"
    archived_at: Optional[str] = None
    archive_reason: Optional[str] = None
    superseded_by: Optional[str] = None
    structured_data: dict = field(default_factory=dict)
    confidence: Optional[float] = None
    valid_from: Optional[str] = None
    valid_until: Optional[str] = None
    commit_sha: Optional[str] = None
    branch: Optional[str] = None
    links: list[str] = field(default_factory=list)
    last_verified: Optional[str] = None

    @staticmethod
    def from_raw(raw: RawMemoryInput, project: str, file_path: str = "") -> Memory:
        """Create a Memory from RawMemoryInput with generated fields."""
        now = datetime.now(timezone.utc).isoformat()
        anchor = re.sub(r"[^a-z0-9]+", "-", raw.title.lower()).strip("-")
        return Memory(
            id=str(uuid.uuid4()),
            title=raw.title,
            what=raw.what,
            why=raw.why,
            impact=raw.impact,
            tags=raw.tags,
            category=raw.category,
            project=project,
            source=raw.source,
            related_files=raw.related_files,
            file_path=file_path,
            section_anchor=anchor,
            created_at=now,
            updated_at=now,
            structured_data={
                "triggers": raw.triggers, "prerequisites": raw.prerequisites,
                "steps": raw.steps, "verification": raw.verification,
                "follow_ups": raw.follow_ups, "constraints": raw.constraints,
                "alternatives_rejected": raw.alternatives_rejected,
                "open_questions": raw.open_questions,
            },
            confidence=raw.confidence, valid_from=raw.valid_from,
            valid_until=raw.valid_until, commit_sha=raw.commit_sha,
            branch=raw.branch, links=raw.links, last_verified=raw.last_verified,
        )


@dataclass
class MemoryDetail:
    """Full details/body content for a memory."""

    memory_id: str
    body: str


@dataclass
class SearchResult:
    """Search result with score and metadata."""

    id: str
    title: str
    what: str
    why: Optional[str]
    impact: Optional[str]
    category: Optional[str]
    tags: list[str]
    project: str
    source: Optional[str]
    score: float
    has_details: bool
    file_path: str
    created_at: str
