# CodeGraph Usage

## Purpose

CodeGraph is used for repo navigation, symbol discovery, impact mapping, and safer planning before touching critical TextifAI areas.

It helps reduce blind edits in high-risk modules by giving fast visibility into symbols, file structure, and likely impact paths.

## When to Use

Use CodeGraph before changes involving:

- `textifai/import_review/structured_bootstrap_v1.py`
- `textifai/vaerl/**`
- `textifai/obsidian/**`
- `textifai/prompt_engine/**`
- `textifai/author_understanding/**`
- CLI entrypoints
- semantic contract changes
- cross-module refactors

## Rules

- CodeGraph is advisory, not a substitute for reading files.
- Do not rely only on CodeGraph for semantic behavior.
- Always inspect target files directly before editing.
- For semantic contract changes, still follow `docs/operations/semantic-contracts.md`.
- For validation, still follow `docs/operations/validation-surface-inventory.md`.

## Safe Commands

Commands discovered and validated in this repo:

- `codegraph status`
  - Purpose: check initialization/index health and stats.
  - Safety: read-only.
  - Caveat: can show "up to date" even with zero indexed files if only initialized.

- `codegraph init`
  - Purpose: create local `.codegraph/` metadata and database skeleton.
  - Safety: writes local tooling state in `.codegraph/`.
  - Caveat: does not build symbol map by itself.

- `codegraph index`
  - Purpose: build symbol map/index for repository navigation.
  - Safety: writes local index data in `.codegraph/codegraph.db`.
  - Caveat: generated DB can become large; treat as local tooling state.

- `codegraph sync`
  - Purpose: refresh index incrementally after file changes.
  - Safety: writes local index updates.
  - Caveat: use after significant code churn before relying on query/context output.

- `codegraph query <search>`
  - Purpose: search symbols by name/kind.
  - Safety: read-only.
  - Caveat: index quality depends on latest `index`/`sync`.

- `codegraph files`
  - Purpose: inspect indexed file tree and metadata.
  - Safety: read-only.
  - Caveat: only indexed files appear.

- `codegraph context <task>`
  - Purpose: generate focused context bundle for a task.
  - Safety: read-only.
  - Caveat: context is heuristic and must be verified against source files.

- `codegraph affected [files...]`
  - Purpose: suggest affected tests/files from changed sources.
  - Safety: read-only.
  - Caveat: depends on graph completeness; not a replacement for human review.

## Storage Policy

Observed `.codegraph/` files after initialization and indexing:

- `.codegraph/config.json`
- `.codegraph/codegraph.db`
- `.codegraph/.gitignore`

Observed policy marker:

- `.codegraph/.gitignore` explicitly states CodeGraph data files are local to each machine and should not be committed.

Current recommendation:

- Treat `.codegraph/` as local generated tooling state.
- Do not include `.codegraph/codegraph.db` in safepoint commits.
- Keep CodeGraph usage operational, not part of semantic artifact outputs.

Repository note:

- Root `git status` currently shows `.codegraph/` as untracked directory.
- Recommend future review of top-level `.gitignore` entry for `.codegraph/` to avoid accidental staging.
- Do not change ignore policy automatically unless explicitly approved.
