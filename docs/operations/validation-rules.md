# Validation Rules

Use the smallest validation tier that gives useful confidence for the files touched.

See `docs/operations/validation-surface-inventory.md` for the repo-zone map and command inventory.

## Tier 0 — Docs-Only

Use for documentation-only changes that do not alter executable instructions, runtime behavior, schemas, tests, source code, generated outputs, or configuration.

Commands:

```bash
git status --short
git diff --stat
```

Optional:

- manual Markdown review
- inspect created or changed docs

For docs-only changes, Tier 0 is sufficient unless docs include executable instructions needing verification.

Docs-only changes about semantic contracts remain Tier 0 if no runtime behavior changes.

## Tier 1 — CLI Smoke

Use when touching command routing, entrypoints, operational docs with executable command claims, provider setup docs, or CLI-adjacent behavior.

Commands may include:

```bash
uv run python scripts/textifai.py --help
uv run python scripts/textifai.py doctor
uv run python scripts/textifai.py <relevant-command> --help
```

Use the relevant CLI help command for the area changed.

## Tier 2 — Targeted Tests

Use when touching source code with existing adjacent tests.

Rules:

- run only tests related to touched code
- avoid broad test runs unless needed
- prefer targeted `pytest` tests over full-suite runs
- do not fix unrelated failures unless explicitly approved

## Tier 3 — Replay / Semantic Validation

Use when touching bootstrap, VaERL, resolver, importer, schemas, invariant logic, note generation, downstream replay, or semantic contract boundaries.

Examples of areas that usually require Tier 3 planning:

- `textifai/import_review/structured_bootstrap_v1.py`
- `textifai/vaerl/**`
- `textifai/obsidian/json_import.py`
- `textifai/obsidian/parser.py`
- resolver logic
- schema logic
- invariant logic
- note generation
- downstream replay

Preserve runs and vault outputs unless explicitly approved.

Any change touching semantic contracts requires an explicit validation plan before editing.

Semantic contract changes require Tier 3 unless explicitly waived.
