"""Markdown rendering and session file writing for memories."""

import locale
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from memory.models import CATEGORY_HEADINGS, VALID_CATEGORIES, Memory


def _read_session_text(file_path: Path) -> str:
    """Read an existing session file with encoding fallbacks."""
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


def render_section(mem: Memory, details: Optional[str] = None) -> str:
    """Render a single H3 section from a Memory.

    Args:
        mem: The Memory object to render
        details: Optional full detail text to include in collapsible section

    Returns:
        Formatted markdown section as string
    """
    lines = [f"### {mem.title}"]
    lines.append(f"**What:** {mem.what}")

    if mem.why is not None:
        lines.append(f"**Why:** {mem.why}")

    if mem.impact is not None:
        lines.append(f"**Impact:** {mem.impact}")

    if mem.source is not None:
        lines.append(f"**Source:** {mem.source}")

    if details is not None:
        lines.append("")
        lines.append("<details>")
        lines.append(details)
        lines.append("</details>")

    return "\n".join(lines)


def write_session_memory(
    vault_project_dir: str,
    mem: Memory,
    date_str: str,
    details: Optional[str] = None,
) -> str:
    """Create or append to a session file.

    Args:
        vault_project_dir: Directory path for the vault project
        mem: The Memory to write
        date_str: Date string for the session file (e.g., "2026-01-22")
        details: Optional full detail text to include in collapsible section

    Returns:
        Path to the session file
    """
    file_path = Path(vault_project_dir) / f"{date_str}-session.md"
    section_content = render_section(mem, details)

    if not file_path.exists():
        # Create new file
        content = _create_new_session_file(mem, date_str, section_content)
        file_path.write_text(content, encoding="utf-8")
    else:
        # Append to existing file
        content = _read_session_text(file_path)
        updated_content = _append_to_session_file(content, mem, section_content)
        file_path.write_text(updated_content, encoding="utf-8")

    return str(file_path)


def _create_new_session_file(mem: Memory, date_str: str, section_content: str) -> str:
    """Create a new session file with frontmatter and initial content."""
    now = datetime.now(timezone.utc).isoformat()
    sources = [mem.source] if mem.source else []
    tags = sorted(mem.tags)

    lines = ["---"]
    lines.append(f"project: {mem.project}")
    lines.append(f"sources: [{', '.join(sources)}]")
    lines.append(f"created: {now}")
    lines.append(f"tags: [{', '.join(tags)}]")
    lines.append("---")
    lines.append("")
    lines.append(f"# {date_str} Session")
    lines.append("")

    if mem.category:
        category_heading = CATEGORY_HEADINGS[mem.category]
        lines.append(f"## {category_heading}")
        lines.append("")

    lines.append(section_content)

    return "\n".join(lines) + "\n"


def _append_to_session_file(content: str, mem: Memory, section_content: str) -> str:
    """Append memory to existing session file, updating frontmatter and structure."""
    # Split frontmatter and body
    frontmatter, body = _split_frontmatter(content)

    # Update frontmatter
    updated_frontmatter = _update_frontmatter(frontmatter, mem)

    # Update body with new section
    updated_body = _insert_section_in_body(body, mem, section_content)

    return updated_frontmatter + "\n" + updated_body


def _split_frontmatter(content: str) -> tuple[str, str]:
    """Split content into frontmatter and body."""
    parts = content.split("---\n", 2)
    if len(parts) >= 3:
        frontmatter = "---\n" + parts[1] + "---"
        body = parts[2]
    else:
        frontmatter = ""
        body = content

    return frontmatter, body


def _update_frontmatter(frontmatter: str, mem: Memory) -> str:
    """Update frontmatter with new tags and sources."""
    lines = frontmatter.split("\n")
    updated_lines = []

    existing_tags = []
    existing_sources = []

    for line in lines:
        if line.startswith("tags:"):
            # Extract existing tags
            match = re.search(r"\[(.*?)\]", line)
            if match:
                tags_str = match.group(1)
                if tags_str.strip():
                    existing_tags = [t.strip() for t in tags_str.split(",")]
        elif line.startswith("sources:"):
            # Extract existing sources
            match = re.search(r"\[(.*?)\]", line)
            if match:
                sources_str = match.group(1)
                if sources_str.strip():
                    existing_sources = [s.strip() for s in sources_str.split(",")]

    # Merge and deduplicate tags
    all_tags = sorted(set(existing_tags + mem.tags))

    # Merge sources
    new_source = mem.source if mem.source else None
    all_sources = existing_sources.copy()
    if new_source and new_source not in all_sources:
        all_sources.append(new_source)

    # Rebuild frontmatter
    for line in lines:
        if line.startswith("tags:"):
            updated_lines.append(f"tags: [{', '.join(all_tags)}]")
        elif line.startswith("sources:"):
            updated_lines.append(f"sources: [{', '.join(all_sources)}]")
        else:
            updated_lines.append(line)

    return "\n".join(updated_lines)


def _insert_section_in_body(body: str, mem: Memory, section_content: str) -> str:
    """Insert section in body at correct position based on category."""
    if not mem.category:
        # No category, just append at end
        return body.rstrip() + "\n\n" + section_content + "\n"

    category_heading = CATEGORY_HEADINGS[mem.category]

    # Check if category heading already exists
    if f"## {category_heading}" in body:
        # Append under existing heading
        return _append_under_existing_category(body, category_heading, section_content)
    else:
        # Insert new category heading in correct order
        return _insert_new_category(body, mem.category, category_heading, section_content)


def _append_under_existing_category(
    body: str, category_heading: str, section_content: str
) -> str:
    """Append section under existing category heading."""
    lines = body.split("\n")
    result_lines = []
    i = 0

    while i < len(lines):
        line = lines[i]
        result_lines.append(line)

        # Found the target category heading
        if line == f"## {category_heading}":
            # Skip blank lines after heading
            i += 1
            while i < len(lines) and lines[i].strip() == "":
                result_lines.append(lines[i])
                i += 1

            # Collect all H3 sections under this category
            while i < len(lines) and not lines[i].startswith("## "):
                result_lines.append(lines[i])
                i += 1

            # Insert new section before next H2 or end
            result_lines.append("")
            result_lines.append(section_content)
            continue

        i += 1

    return "\n".join(result_lines) + "\n"


def _insert_new_category(
    body: str, category: str, category_heading: str, section_content: str
) -> str:
    """Insert new category heading at correct position."""
    # Get category order
    category_order = list(VALID_CATEGORIES)
    target_index = category_order.index(category)

    lines = body.split("\n")
    insert_position = len(lines)

    # Find where to insert based on category order
    for i, line in enumerate(lines):
        if line.startswith("## "):
            # Extract category from heading
            heading_text = line[3:].strip()
            for cat in category_order:
                if CATEGORY_HEADINGS[cat] == heading_text:
                    cat_index = category_order.index(cat)
                    if cat_index > target_index:
                        # Found a category that should come after ours
                        insert_position = i
                        break
            if insert_position < len(lines):
                break

    # Insert new category section
    new_lines = (
        lines[:insert_position]
        + [f"## {category_heading}", "", section_content, ""]
        + lines[insert_position:]
    )

    return "\n".join(new_lines).rstrip() + "\n"
