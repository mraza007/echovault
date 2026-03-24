"""Markdown rendering and session file writing for memories."""

from __future__ import annotations

import locale
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from memory.models import CATEGORY_HEADINGS, VALID_CATEGORIES, Memory

ARCHIVED_HEADING = "Archived"
MEMORY_ID_PREFIX = "<!-- memory-id:"


@dataclass
class SessionEntry:
    """Parsed memory section from a session markdown file."""

    id: Optional[str]
    title: str
    what: str
    why: Optional[str]
    impact: Optional[str]
    source: Optional[str]
    details: Optional[str]
    category: Optional[str]
    status: str = "active"
    archived_at: Optional[str] = None
    archive_reason: Optional[str] = None
    superseded_by: Optional[str] = None
    section_anchor: Optional[str] = None


@dataclass
class SessionDocument:
    """Parsed session markdown file."""

    project: str
    created: Optional[str]
    tags: list[str]
    sources: list[str]
    title: str
    entries: list[SessionEntry]


def read_markdown_text(file_path: Path) -> str:
    """Read a markdown file with encoding fallbacks."""
    encodings = ["utf-8-sig", "utf-8", locale.getpreferredencoding(False), "cp1251"]
    seen: set[str] = set()

    for encoding in encodings:
        if not encoding or encoding in seen:
            continue
        seen.add(encoding)
        try:
            return file_path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue

    return file_path.read_text(encoding="utf-8", errors="replace")


def normalize_markdown_content(content: str) -> str:
    """Normalize markdown text for line-based parsing."""
    return content.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")


def make_section_anchor(title: str, occurrence: int = 1) -> str:
    """Create a stable section anchor, suffixing repeated titles."""
    base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "memory"
    if occurrence <= 1:
        return base
    return f"{base}-{occurrence}"


def render_section(mem: Memory, details: Optional[str] = None) -> str:
    """Render a single section from a Memory."""
    return render_entry(
        SessionEntry(
            id=mem.id,
            title=mem.title,
            what=mem.what,
            why=mem.why,
            impact=mem.impact,
            source=mem.source,
            details=details,
            category=mem.category,
            status=mem.status,
            archived_at=mem.archived_at,
            archive_reason=mem.archive_reason,
            superseded_by=mem.superseded_by,
            section_anchor=mem.section_anchor,
        )
    )


def render_entry(entry: SessionEntry) -> str:
    """Render a single parsed session entry."""
    lines = [f"### {entry.title}"]
    if entry.id:
        lines.append(f"<!-- memory-id: {entry.id} -->")
    lines.append(f"**What:** {entry.what}")

    if entry.why is not None:
        lines.append(f"**Why:** {entry.why}")

    if entry.impact is not None:
        lines.append(f"**Impact:** {entry.impact}")

    if entry.source is not None:
        lines.append(f"**Source:** {entry.source}")

    if entry.status == "archived":
        if entry.category is not None:
            lines.append(f"**Category:** {entry.category}")
        if entry.archived_at is not None:
            lines.append(f"**Archived:** {entry.archived_at}")
        if entry.archive_reason is not None:
            lines.append(f"**Archive Reason:** {entry.archive_reason}")
        if entry.superseded_by is not None:
            lines.append(f"**Superseded By:** {entry.superseded_by}")

    if entry.details is not None:
        lines.append("")
        lines.append("<details>")
        lines.append(entry.details)
        lines.append("</details>")

    return "\n".join(lines)


def parse_session_file(file_path: str | Path) -> SessionDocument:
    """Parse a session markdown file into structured entries."""
    path = Path(file_path)
    content = normalize_markdown_content(read_markdown_text(path))
    frontmatter, body = _split_frontmatter(content)
    frontmatter_data = _parse_frontmatter(frontmatter)
    title = _extract_session_title(body, path)
    entries = _parse_entries(body)

    return SessionDocument(
        project=frontmatter_data.get("project", path.parent.name),
        created=frontmatter_data.get("created"),
        tags=frontmatter_data.get("tags", []),
        sources=frontmatter_data.get("sources", []),
        title=title,
        entries=entries,
    )


def write_session_document(
    file_path: str | Path,
    document: SessionDocument,
    *,
    tags: Optional[list[str]] = None,
    sources: Optional[list[str]] = None,
) -> None:
    """Write a full parsed session document back to disk."""
    path = Path(file_path)
    date_str = re.match(r"(\d{4}-\d{2}-\d{2})", path.stem)
    session_title = document.title or f"{date_str.group(1) if date_str else path.stem} Session"
    created = document.created or datetime.now(timezone.utc).isoformat()
    render_tags = sorted(tags if tags is not None else document.tags)
    render_sources = sorted(sources if sources is not None else document.sources)

    lines = ["---"]
    lines.append(f"project: {document.project}")
    lines.append(f"sources: [{', '.join(render_sources)}]")
    lines.append(f"created: {created}")
    lines.append(f"tags: [{', '.join(render_tags)}]")
    lines.append("---")
    lines.append("")
    lines.append(f"# {session_title}")
    lines.append("")

    active_entries = [entry for entry in document.entries if entry.status != "archived"]
    archived_entries = [entry for entry in document.entries if entry.status == "archived"]

    for category in VALID_CATEGORIES:
        category_entries = [entry for entry in active_entries if entry.category == category]
        if not category_entries:
            continue
        lines.append(f"## {CATEGORY_HEADINGS[category]}")
        lines.append("")
        for entry in category_entries:
            lines.append(render_entry(entry))
            lines.append("")

    uncategorized_entries = [entry for entry in active_entries if entry.category not in VALID_CATEGORIES]
    for entry in uncategorized_entries:
        lines.append(render_entry(entry))
        lines.append("")

    if archived_entries:
        lines.append(f"## {ARCHIVED_HEADING}")
        lines.append("")
        for entry in archived_entries:
            lines.append(render_entry(entry))
            lines.append("")

    content = "\n".join(lines).rstrip() + "\n"
    path.write_text(content, encoding="utf-8")


def assign_entry_anchors(entries: list[SessionEntry]) -> None:
    """Assign stable anchors in document order."""
    counts: dict[str, int] = {}
    for entry in entries:
        base = make_section_anchor(entry.title)
        occurrence = counts.get(base, 0) + 1
        counts[base] = occurrence
        entry.section_anchor = make_section_anchor(entry.title, occurrence)


def write_session_memory(
    vault_project_dir: str,
    mem: Memory,
    date_str: str,
    details: Optional[str] = None,
) -> str:
    """Create or append to a session file."""
    file_path = Path(vault_project_dir) / f"{date_str}-session.md"
    if file_path.exists():
        document = parse_session_file(file_path)
    else:
        document = SessionDocument(
            project=mem.project,
            created=None,
            tags=[],
            sources=[],
            title=f"{date_str} Session",
            entries=[],
        )

    document.entries.append(
        SessionEntry(
            id=mem.id,
            title=mem.title,
            what=mem.what,
            why=mem.why,
            impact=mem.impact,
            source=mem.source,
            details=details,
            category=mem.category,
            status=mem.status,
            archived_at=mem.archived_at,
            archive_reason=mem.archive_reason,
            superseded_by=mem.superseded_by,
        )
    )
    assign_entry_anchors(document.entries)
    write_session_document(
        file_path,
        document,
        tags=sorted(set(document.tags + mem.tags)),
        sources=sorted(set(document.sources + ([mem.source] if mem.source else []))),
    )
    return str(file_path)


def _split_frontmatter(content: str) -> tuple[str, str]:
    """Split content into frontmatter and body."""
    normalized = normalize_markdown_content(content)
    if not normalized.startswith("---\n"):
        return "", normalized
    parts = normalized.split("---\n", 2)
    if len(parts) < 3:
        return "", normalized
    return "---\n" + parts[1] + "---", parts[2]


def _parse_frontmatter(frontmatter: str) -> dict:
    """Parse the small YAML-ish frontmatter used by session files."""
    data: dict[str, object] = {}
    if not frontmatter:
        return data
    for line in frontmatter.split("\n"):
        if ":" not in line or line == "---":
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            items = [item.strip() for item in value[1:-1].split(",") if item.strip()]
            data[key] = items
        else:
            data[key] = value
    return data


def _extract_session_title(body: str, path: Path) -> str:
    """Extract the session H1 title."""
    for line in body.split("\n"):
        if line.startswith("# "):
            return line[2:].strip()
    match = re.match(r"(\d{4}-\d{2}-\d{2})", path.stem)
    return f"{match.group(1) if match else path.stem} Session"


def _heading_to_category(heading: str) -> Optional[str]:
    for category, display in CATEGORY_HEADINGS.items():
        if display == heading:
            return category
    return None


def _parse_entries(body: str) -> list[SessionEntry]:
    """Parse section entries from a session body."""
    entries: list[SessionEntry] = []
    current_category: Optional[str] = None
    current_status = "active"
    lines = body.split("\n")
    i = 0

    while i < len(lines):
        line = lines[i]
        if line.startswith("## "):
            heading = line[3:].strip()
            if heading == ARCHIVED_HEADING:
                current_category = None
                current_status = "archived"
            else:
                current_category = _heading_to_category(heading)
                current_status = "active"
        elif line.startswith("### "):
            title = line[4:].strip()
            entry = SessionEntry(
                id=None,
                title=title,
                what="",
                why=None,
                impact=None,
                source=None,
                details=None,
                category=current_category,
                status=current_status,
            )
            details_lines: list[str] = []
            in_details = False

            i += 1
            while i < len(lines) and not lines[i].startswith("### ") and not lines[i].startswith("## "):
                stripped = lines[i].strip()
                if stripped.startswith(MEMORY_ID_PREFIX):
                    entry.id = stripped.removeprefix(MEMORY_ID_PREFIX).removesuffix("-->").strip()
                elif stripped == "<details>":
                    in_details = True
                elif stripped == "</details>":
                    in_details = False
                elif in_details:
                    details_lines.append(lines[i])
                elif stripped.startswith("**What:**"):
                    entry.what = stripped[len("**What:**"):].strip()
                elif stripped.startswith("**Why:**"):
                    entry.why = stripped[len("**Why:**"):].strip()
                elif stripped.startswith("**Impact:**"):
                    entry.impact = stripped[len("**Impact:**"):].strip()
                elif stripped.startswith("**Source:**"):
                    entry.source = stripped[len("**Source:**"):].strip()
                elif stripped.startswith("**Category:**"):
                    entry.category = stripped[len("**Category:**"):].strip() or entry.category
                elif stripped.startswith("**Archived:**"):
                    entry.archived_at = stripped[len("**Archived:**"):].strip()
                elif stripped.startswith("**Archive Reason:**"):
                    entry.archive_reason = stripped[len("**Archive Reason:**"):].strip()
                elif stripped.startswith("**Superseded By:**"):
                    entry.superseded_by = stripped[len("**Superseded By:**"):].strip()
                i += 1

            entry.details = "\n".join(details_lines).strip() or None
            entries.append(entry)
            continue
        i += 1

    assign_entry_anchors(entries)
    return entries
