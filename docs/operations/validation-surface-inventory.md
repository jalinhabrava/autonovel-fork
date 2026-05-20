# Validation Surface Inventory

## Purpose

Validation must match repo zone and semantic risk.

TextifAI has multiple surfaces with different failure modes: docs, CLI routing, viewer behavior, vault materialization, VaERL semantics, bootstrap replay, prompt semantics, plugin build, legacy rails, and preserved artifacts.

A passing low-level check is not enough when a change can alter downstream semantic meaning, artifact shape, replay contracts, or persisted vault outputs.

## Validation Tiers Summary

Reference `docs/operations/validation-rules.md` for the tier policy.
Reference `docs/operations/safe-fixtures-and-baselines.md` for safe fixture and baseline strategy.

- Tier 0 docs-only
- Tier 1 CLI smoke
- Tier 2 targeted tests
- Tier 3 replay / semantic validation

## Zone-to-Validation Map

### Docs / Operations

Files:

- `docs/**`
- `docs/operations/**`
- `docs/handoffs/**`

Recommended validation:

- Tier 0
- `git status --short`
- `git diff --stat`
- manual Markdown inspection

Notes:

- No runtime claims unless actually verified.
- Docs about semantic contracts remain Tier 0 when runtime behavior is unchanged.

### Active CLI Surface

Files:

- `scripts/textifai.py`
- `textifai/cli.py`
- `textifai/obsidian/cli.py`

Recommended validation:

- Tier 1 minimum
- CLI help command
- doctor command if safe and actually wired on touched entrypoint
- targeted CLI help for touched subcommand
- targeted tests if available

Notes:

- Current discovery shows `scripts/textifai.py` supports many operational subcommands but rejects `doctor`.
- `doctor` appears implemented in `textifai/cli.py`, so entrypoint wiring must be validated before claiming it works.

### Viewer Surface

Files:

- `textifai/web_viewer/**`
- viewer-related docs

Recommended validation:

- Tier 1 or Tier 2 depending on changes
- help/start command if available
- targeted tests if available
- no assumptions about browser/manual testing unless explicitly performed

Notes:

- `viewer --help` is safe and read-only.
- `viewer` without `--help` starts server and is not docs-tier validation.

### Obsidian Import / Vault Materialization

Files:

- `textifai/obsidian/json_import.py`
- `textifai/obsidian/parser.py`
- `textifai/obsidian/setup.py`
- `textifai/obsidian/bridge_reader.py`

Recommended validation:

- Tier 2 minimum
- Tier 3 if output shape changes
- compare generated artifact shape if approved
- never write to real vault unless explicitly approved

Notes:

- Treat persisted Markdown, note filenames, import payload shape, and vault folder layout as contract-sensitive.
- Prefer safe fixtures and baseline comparisons over real vault outputs whenever possible.

### VaERL / Resolver / Invariants

Files:

- `textifai/vaerl/**`
- resolver/index/invariants/review queue related files

Recommended validation:

- Tier 2 + Tier 3
- `validate-vaerl`
- invariant validation
- artifact diff or snapshot comparison when possible

Notes:

- Review queue shape, canonical entity naming, slugs, and invariant thresholds are semantic contract surfaces.
- Prefer fixture-backed `99_System` inputs for invariant validation before touching real run artifacts.

### Bootstrap / Structured Ingestion

Files:

- `textifai/import_review/structured_bootstrap_v1.py`
- bootstrap/chapterizer/extraction/normalization/reconciliation/note synthesis files

Recommended validation:

- Tier 3 required unless explicitly waived
- replay/downstream validation
- invariant validation
- artifact diff
- expected output changes documented

Notes:

- This is highest-risk semantic surface because small logic changes can reshape many downstream artifacts.
- See `docs/operations/safe-fixtures-and-baselines.md` before choosing replay inputs or output locations.

### Prompt Engine / Templates

Files:

- `textifai/prompt_engine/**`
- `textifai/prompt_templates/**`

Recommended validation:

- Tier 2 or Tier 3 depending on whether output semantics change
- rendered prompt inspection if available
- snapshot comparison if prompt output affects extraction

Notes:

- Prompt-only edits can still be semantic contract changes if they alter extraction or resolution behavior.

### Obsidian Bridge Plugin

Files:

- `integrations/obsidian-textifai-bridge/**`

Recommended validation:

- `npm run build`
- targeted TypeScript/esbuild validation
- no plugin runtime claims unless manually tested

Notes:

- Build validates TypeScript/esbuild surface, not actual Obsidian runtime behavior.

### Legacy AutoNovel Rail

Files:

- `run_pipeline.py`
- `scripts/foundation/**`
- `scripts/drafting/**`
- `scripts/revision/**`

Recommended validation:

- only if explicitly in scope
- do not mix with active TextifAI validation
- treat as preservation rail

Notes:

- Legacy rail can require its own workflow, but it must not leak into active TextifAI semantic validation by default.

### Preservation / Generated Artifacts

Files:

- `runs/**`
- `vault/**`
- `archive/**`
- `.textifai/**`
- `typeset/**`
- `results.tsv`
- `state.json`

Recommended validation:

- do not modify unless explicitly approved
- if approved, create backup or explicit artifact diff plan first

Notes:

- Preservation zones are not normal validation targets.
- When they must change, treat change as controlled artifact operation.

## Command Inventory

### CLI Help / Smoke

- Command: `uv run python scripts/textifai.py --help`
  - Purpose: list active operational subcommands on script entrypoint
  - Read-only or may write: read-only
  - When to use it: CLI routing changes, docs claims about script entrypoint
  - Known caveats: confirms exposed commands, not runtime correctness

- Command: `uv run python scripts/textifai.py validate-vaerl --help`
  - Purpose: inspect invariant audit CLI flags
  - Read-only or may write: read-only
  - When to use it: invariant/validation docs or CLI surface changes
  - Known caveats: running actual `validate-vaerl` writes output by default unless `--output` controlled

- Command: `uv run python scripts/textifai.py replay-downstream --help`
  - Purpose: inspect replay/downstream contract arguments
  - Read-only or may write: read-only
  - When to use it: replay CLI changes, docs, semantic validation planning
  - Known caveats: actual replay writes artifacts and must not be used as smoke by default

- Command: `uv run python scripts/textifai.py viewer --help`
  - Purpose: inspect viewer CLI options
  - Read-only or may write: read-only
  - When to use it: viewer CLI/docs changes
  - Known caveats: `viewer` without `--help` starts server

- Command: `uv run python scripts/textifai.py review-queue --help`
  - Purpose: inspect review queue CLI options
  - Read-only or may write: read-only
  - When to use it: review queue CLI/docs changes
  - Known caveats: actual command reads `review_queue.json`; safe if pointed at approved fixture only

- Command: `uv run python scripts/textifai.py doctor`
  - Purpose: expected doctor smoke on script entrypoint
  - Read-only or may write: read-only
  - When to use it: only after confirming entrypoint wiring
  - Known caveats: current inspection shows this command is rejected as unrecognized on `scripts/textifai.py`

### VaERL Validation

- Command: `uv run python scripts/textifai.py validate-vaerl --system-root <run>/99_System`
  - Purpose: run semantic invariant audit against generated system artifacts
  - Read-only or may write: may write
  - When to use it: VaERL, invariants, review queue, import contract changes
  - Known caveats: writes `semantic_invariants_audit.json` by default; use only with approved artifact plan

### Replay / Downstream

- Command: `uv run python scripts/textifai.py replay-downstream --input-system <run>/99_System --output-root <new-run>`
  - Purpose: replay downstream semantic compilation from frozen upstream artifacts
  - Read-only or may write: may write
  - When to use it: bootstrap/replay/import contract changes
  - Known caveats: writes new replay artifacts; prefer safe fixture output dirs and baseline comparisons over real runs/vaults

### Viewer

- Command: `uv run python scripts/textifai.py viewer --root runs/semantic_ingestion_e2e`
  - Purpose: start internal viewer over runs/vault roots
  - Read-only or may write: operationally read-only, but starts long-lived server
  - When to use it: explicit viewer verification only
  - Known caveats: not equivalent to browser/manual validation; avoid claiming UI behavior unless tested

### Review Queue

- Command: `uv run python scripts/textifai.py review-queue --system-root <run>/99_System --json`
  - Purpose: inspect author-actionable review queue shape
  - Read-only or may write: read-only if input artifact already exists
  - When to use it: review queue formatting/filtering/contract checks
  - Known caveats: quality depends on fixture/run chosen

### Plugin Build

- Command: `cd integrations/obsidian-textifai-bridge && npm run build`
  - Purpose: compile TypeScript plugin and verify esbuild path
  - Read-only or may write: may write build output in plugin directory
  - When to use it: plugin code changes only
  - Known caveats: build success does not prove Obsidian runtime correctness

### Tests If Discoverable

- Command: targeted `pytest` against `tests/` for touched Python modules
  - Purpose: narrow behavioral validation
  - Read-only or may write: usually read-only, but tests may create temp files
  - When to use it: source-code changes with nearby tests
  - Known caveats: no confirmed full-suite baseline documented yet

- Command: targeted legacy tests under `archive/legacy_bootstrap/tests/`
  - Purpose: validate legacy bootstrap behavior only if legacy rail explicitly in scope
  - Read-only or may write: usually read-only or temp-write
  - When to use it: legacy-only work
  - Known caveats: do not mix into active TextifAI validation by default

## Minimum Validation Rule

Before every handoff:

- `git status --short`
- `git diff --stat`
- list files changed
- state semantic contract changes YES/NO

## Unknowns

Validation gaps currently visible:

- missing CI
- no confirmed full test baseline
- no confirmed Markdown linter
- no confirmed snapshot workflow
- no confirmed safe fixture vault for write tests, unless discovered otherwise
- no confirmed working packaged `textifai` executable via `uv run textifai` in current environment
- no confirmed doctor workflow on `scripts/textifai.py` script entrypoint
