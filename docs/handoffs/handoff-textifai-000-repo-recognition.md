# handoff-textifai-000-repo-recognition

## Repo

- Path: `/home/david/projects/autonovel-fork`
- Branch: `main`
- HEAD: `4e88118 feat(viewer): add graph tag filtering and VaERL detail fallback`
- Git status summary: clean at recognition time; `git status --short` returned no modified or untracked files.
- Recent safepoints: none detected with `git log --oneline --grep='^safepoint-[0-9]\{3\}' -n 30`.
- Recent tags: none observed during recognition.

## Scope

- Recognition only.
- No code changes performed.
- No config changes performed.
- No dependency installation performed.
- No CodeGraph initialization performed.
- No destructive commands performed.

## Architecture Map

### Main Folders

- `textifai/`: active TextifAI product runtime and semantic story engine logic.
- `textifai/import_review/`: structured bootstrap, extraction, normalization, entity resolution, cleanup, reconciliation, primary note synthesis, replay, and import assembly.
- `textifai/vaerl/`: VaERL contracts, indexes, matching, resolver support, review queue, relation helpers, and semantic invariants.
- `textifai/obsidian/`: Obsidian setup, parsing, reading, JSON import, bridge snapshot reading, readiness checks, and operational CLI.
- `textifai/prompt_engine/`: prompt contracts, context building, rendering, template loading, model adaptation, and exports.
- `textifai/prompt_templates/`: author-facing prompt templates.
- `textifai/author_understanding/`, `textifai/editorial_intent/`, `textifai/conversation/`, `textifai/editorial/`: ECC and author-facing understanding/execution surfaces.
- `textifai/web_viewer/`: internal local viewer for runs and vaults.
- `scripts/`: active entrypoint wrappers plus legacy foundation/drafting/revision scripts.
- `integrations/obsidian-textifai-bridge/`: Obsidian bridge plugin with TypeScript build.
- `runs/`: generated semantic ingestion and replay artifacts.
- `vault/`: vault-related package and local vault state.
- `archive/`: legacy bootstrap reference material.
- `docs/`: product, architecture, roadmap, schema, flow, audit, and operational documentation.
- `tests/`: Python test suite.

### Key Files

- `README.md`: product entrypoint and conceptual overview.
- `docs/TEXTIFAI_SEMANTIC_STORY_ENGINE_ROADMAP.md`: living technical-product roadmap.
- `docs/ARCHITECTURE.md`: current implementation architecture.
- `docs/BOOTSTRAP_V1_FLOW.md`: active semantic ingestion and bootstrap flow.
- `docs/VAULT_SCHEMA.md`: vault layout and artifact schema notes.
- `docs/e2e_semantic_diagnosis_rules.md`: diagnostic playbook for semantic ingestion runs.
- `scripts/textifai.py`: canonical active TextifAI script entrypoint.
- `textifai/cli.py`: package CLI entrypoint for product runtime.
- `textifai/obsidian/cli.py`: operational CLI for start/init/status/inspect/validate/replay/review/viewer/provider/ask flows.
- `textifai/import_review/structured_bootstrap_v1.py`: central semantic ingestion orchestration; high-risk monolith.
- `textifai/obsidian/json_import.py`: Obsidian import materialization logic.
- `textifai/vaerl/invariants.py`: semantic invariant audit logic.

### Data Flow Hypothesis

1. Source material is discovered and read.
2. Primary novel document is selected.
3. Chapters are detected and indexed.
4. Deterministic `novel_index.json` is produced.
5. Global normalization artifacts are generated.
6. Chapter-level extraction artifacts are produced.
7. Entity resolution, cleanup, and reconciliation build VaERL-oriented semantic state.
8. Auxiliary documents may enrich downstream replay.
9. Primary notes and Obsidian import payloads are synthesized.
10. `obsidian_import.json` and related `99_System` artifacts become observable boundaries.
11. Semantic invariants audit the result.
12. Obsidian/vault materialization and viewer/review tools project over those artifacts.

## Current Capabilities

### Implemented

- Markdown novel ingestion.
- Chapter detection.
- Deterministic structural indexing.
- Semantic extraction and normalization.
- Entity resolution into canonical primaries and review candidates.
- Entity cleanup and reconciliation.
- Obsidian-style vault import/materialization.
- Downstream replay from frozen artifacts.
- Auxiliary document ingestion during replay.
- Phase 1 semantic invariant audits.
- Review queue inspection.
- Internal local viewer for runs/vaults.
- Provider readiness/configuration flows.
- Basic author-facing query path.

### Partial

- VaERL core is marked `in progress` in the roadmap.
- Codex View is marked `in progress` in the roadmap.
- Internal viewer is a tactical acceleration layer, also `in progress` in the roadmap.
- Author-facing interaction exists but does not imply mature free chat or durable correction loop.

### Unknown

- Current full-suite test health was not checked during recognition.
- Runtime provider connectivity was not checked.
- Semantic quality of latest replay artifacts was not revalidated.
- Obsidian plugin runtime behavior was not manually tested.
- CodeGraph index was not initialized, so no CodeGraph symbol map was available.

## Scripts / Commands

### Dev

- Root Python development appears to use `uv`.
- Active CLI examples:
  - `uv run python scripts/textifai.py start`
  - `uv run python scripts/textifai.py init --vault-root <vault> --source-root <source>`
  - `uv run python scripts/textifai.py status`
  - `uv run python scripts/textifai.py inspect --vault-root <vault>`
  - `uv run python scripts/textifai.py ask --vault-root <vault> --text <question>`
  - `uv run python scripts/textifai.py provider`
  - `uv run python scripts/textifai.py configure-provider`
  - `uv run python scripts/textifai.py chat`
  - `uv run python scripts/textifai.py doctor`

### Build

- Obsidian bridge plugin:
  - `cd integrations/obsidian-textifai-bridge && npm run build`
- Root Python project has no package-manager build script detected in `pyproject.toml`.

### Test

- Tests exist under `tests/` and `archive/legacy_bootstrap/tests/`.
- No root `pytest` config or script was confirmed during recognition.
- Future test runs should be targeted by touched area.

### Lint

- No root lint script was detected in `pyproject.toml`.
- No lint command was run during recognition.

### Other Useful Commands

- Validate VaERL artifacts:
  - `uv run python scripts/textifai.py validate-vaerl --system-root <run>/99_System`
- Review queue:
  - `uv run python scripts/textifai.py review-queue --system-root <run>/99_System`
- Replay downstream semantic compilation:
  - `uv run python scripts/textifai.py replay-downstream --input-system <run>/99_System --output-root <new-run>`
- Internal viewer:
  - `uv run python scripts/textifai.py viewer --root runs/semantic_ingestion_e2e`
- Legacy AutoNovel rail:
  - `uv run python run_pipeline.py --from-scratch`
  - `uv run python run_pipeline.py --phase foundation`
  - `uv run python run_pipeline.py --phase drafting`
  - `uv run python run_pipeline.py --phase revision`
  - `uv run python run_pipeline.py --phase export`

## Risks / Preservation Notes

### Modified Files

- No modified files were present at recognition time.

### Untracked Files

- No untracked files were present at recognition time.

### Generated Files

- `runs/` is large and contains semantic ingestion/replay artifacts. It must be preserved unless explicitly requested.
- `vault/` may contain durable vault or project state. It must be preserved unless explicitly requested.
- `typeset/` may contain generated publishing outputs. It must be preserved unless explicitly requested.
- `.textifai/` is local TextifAI state. It must be preserved unless explicitly requested.

### Secrets / Configs

- `.env` exists and is ignored. Never commit it.
- Provider keys referenced by code/docs include `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `FAL_KEY`, and `ELEVENLABS_API_KEY`.
- Runtime/provider configuration should be handled carefully and not normalized blindly.

### Large Data

- `runs/` was approximately `83M` during recognition.
- `runs/semantic_ingestion_e2e/` contains many named replay and ONT experiment directories.
- These artifacts likely carry comparability value and should not be cleaned without explicit approval.

### Sensitive Technical Areas

- `textifai/import_review/structured_bootstrap_v1.py` is a large central orchestrator and should require explicit approval before edits.
- `textifai/vaerl/**` carries semantic contract risk.
- `textifai/obsidian/json_import.py` and `textifai/obsidian/parser.py` affect persisted Markdown/vault behavior.
- CLI changes can alter operational workflows even if semantic code is untouched.
- Legacy AutoNovel scripts should not be mixed with active TextifAI changes.

## Proposed Iteration Workflow

1. Diagnosis: read-only inspection, active rail confirmation, risk map, and current `git status --short`.
2. Plan: propose exact scope, files, validation tier, expected safepoint number, and out-of-scope areas.
3. Approval Gate: wait for user approval before editing unless approval was already explicit.
4. Execution: change only approved files; avoid opportunistic refactors.
5. Verification: run smallest useful validation tier for touched area.
6. Review: inspect `git status --short` and `git diff --stat`; ensure only intended files changed.
7. Handoff: create matching handoff for any safepoint iteration.
8. Safepoint: commit with `safepoint-XXX short description` only when approved; stage only intentional files.
9. Push/Tag: only when requested or required by current repo operating rules and not blocked by user instruction.

## Suggested Next Phase

Phase 0.1 — Operationalization.

Recommended small safe scope:

- Create `docs/ACTIVE_RAIL.md` to define active TextifAI rail vs legacy AutoNovel rail.
- Create `docs/operations/repo-zones.md` to classify critical core, docs, tooling, and preservation zones.
- Create `docs/operations/safepoint-convention.md` to make safepoint and handoff expectations explicit.
- Create `docs/operations/handoff-template.md` to standardize future handoffs.
- Create `docs/operations/validation-rules.md` to define lightweight validation tiers.
- Save this recognition as `docs/handoffs/handoff-textifai-000-repo-recognition.md`.

This phase avoids runtime/source code and reduces risk before touching TextifAI semantic behavior.
