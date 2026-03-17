# Local EchoVault Fork Notes

This local fork exists to preserve semantic-search tuning for the `memory` CLI used by Codex.

## Why this fork exists

The stock `echovault` package was patched locally to improve project-scoped semantic retrieval:

- filter noisy stopwords from FTS queries
- convert vector distance into a bounded positive similarity score
- over-fetch vector candidates when project/source filters are active
- reduce the ranking impact of low-signal diagnostic and temporary probe memories
- let the semantic top result outrank a single conflicting lexical hit in sparse-search cases

These changes are implemented in:

- `src/memory/db.py`
- `src/memory/search.py`

## Expected install mode

Install from this repo in editable mode so future `pipx` upgrades from PyPI or GitHub do not overwrite the tuned search behavior:

```bash
pipx install --force --editable /Volumes/Flash500Gb/MAC/.codex-local/echovault-fork
```

## Maintenance

- Keep the branch local unless you decide to publish your own fork.
- If you pull upstream changes later, re-run semantic retrieval tests before trusting the merge.
- The active memory config still lives outside the repo at `~/.memory/config.yaml`.
