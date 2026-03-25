"""Open a memory in $EDITOR (vim) for editing."""

from __future__ import annotations

import os
import subprocess
import tempfile
from typing import Optional

import yaml


_TEMPLATE = """\
# Save and quit (:wq) to update. Quit without saving (:q!) to cancel.
# Lines starting with # are ignored.

title: {title}
project: {project}
category: {category}
tags: [{tags}]
source: {source}
what: {what}
why: {why}
impact: {impact}
details: |
{details}
"""


def _indent(text: str, prefix: str = "  ") -> str:
    if not text:
        return prefix
    return "\n".join(f"{prefix}{line}" for line in text.splitlines())


def _memory_to_yaml(record: Optional[dict], project: str = "") -> str:
    if record is None:
        record = {}
    tags_raw = record.get("tags", [])
    if isinstance(tags_raw, str):
        try:
            import json

            tags_raw = json.loads(tags_raw)
        except Exception:
            tags_raw = [t.strip() for t in tags_raw.split(",") if t.strip()]
    tags_str = ", ".join(str(t) for t in tags_raw)
    details = record.get("details", "") or ""

    return _TEMPLATE.format(
        title=record.get("title", ""),
        project=record.get("project", project),
        category=record.get("category", ""),
        tags=tags_str,
        source=record.get("source", ""),
        what=record.get("what", ""),
        why=record.get("why", ""),
        impact=record.get("impact", ""),
        details=_indent(details),
    )


def _parse_yaml(content: str) -> Optional[dict]:
    lines = [line for line in content.splitlines() if not line.strip().startswith("#")]
    cleaned = "\n".join(lines)
    try:
        data = yaml.safe_load(cleaned)
    except yaml.YAMLError:
        return None
    if not isinstance(data, dict):
        return None
    title = (data.get("title") or "").strip()
    what = (data.get("what") or "").strip()
    if not title or not what:
        return None
    tags = data.get("tags", [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    return {
        "title": title,
        "project": (data.get("project") or "").strip(),
        "category": (data.get("category") or "").strip() or None,
        "tags": tags or [],
        "source": (data.get("source") or "").strip() or None,
        "what": what,
        "why": (data.get("why") or "").strip() or None,
        "impact": (data.get("impact") or "").strip() or None,
        "details": (data.get("details") or "").strip() or None,
    }


def edit_memory(
    record: Optional[dict] = None,
    project: str = "",
) -> Optional[dict]:
    """Open a memory in $EDITOR. Returns parsed dict or None if cancelled."""
    content = _memory_to_yaml(record, project=project)
    editor = os.environ.get("EDITOR", "vim")

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".yaml",
        prefix="echovault-",
        delete=False,
    ) as f:
        f.write(content)
        tmp_path = f.name

    try:
        result = subprocess.run([editor, tmp_path])  # noqa: S603
        if result.returncode != 0:
            return None
        with open(tmp_path) as f:
            edited = f.read()
        if edited.strip() == content.strip():
            return None
        return _parse_yaml(edited)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
