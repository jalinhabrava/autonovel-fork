# Canonical Author Graph + Review Hydration + Ingestion Progress

## Product Reading
TextifAI is a first-party author platform. VaERL is the semantic source of truth, Markdown is the editable author-facing substrate, and React/Tailwind is the main product surface. The Author Workspace must consume only finalized, canonical, author-facing projection artifacts.

## Scope
SP-108B fixes canonical projection regression without provider calls, retry, full rerun, package changes, editor write-back, or raw source exposure.

## Files Changed
- `textifai/import_review/markdown_graph_index.py`
- `textifai/web_viewer/project_reader.py`
- `textifai/web_viewer/react_shell/src/App.tsx`
- `textifai/web_viewer/react_shell/src/api.ts`
- `textifai/web_viewer/react_shell/src/graph/GraphDataAdapter.ts`
- `textifai/web_viewer/react_shell/src/graph/GraphToolbar.tsx`
- `scripts/dev/sp108b_canonical_projection_refresh.py`
- `tests/test_textifai_canonical_projection_regression.py`
- `tests/fixtures/textifai/canonical_projection_regression/expected/*.json`

## SP107 Context
SP-107 produced a Pro-first 20 chapter project with zero technical retries and semantic review warnings. The visible graph regressed because product graph projection could include internal package artifacts.

## Root Cause
`build_markdown_graph_index(project.root)` scanned too broadly. Product graph generation needed to prefer `project.root/markdown/` and exclude `dev/`, `runs/`, `99_System/`, provider outputs, hidden dirs, and duplicated legacy vault/viewer folders.

## Author Graph Projection
SP-108B adds `build_author_graph()` and generates `graph/author_graph.json` with schema `textifai.author_graph`. The projection keeps canonical entities and chapters, consolidates aliases as metadata, removes pronouns, and routes unresolved/internal candidates away from author graph.

## Graph Source / Project Reader
`project_reader.build_graph()` now prioritizes `graph/author_graph.json`. Legacy graph generation remains fallback only and marks metadata with `graph_mode=legacy`.

## Internal Candidate / Pronoun Filtering
The author graph excludes `review/local_candidate`, `Reviewlocal_Candidate` paths, local candidates, raw dev/run nodes, and pronoun labels such as `yo`, `ella`, `él`, `el`, and `la` unless future phases resolve them explicitly.

## Review Hydration
Raw `vaerl/review_queue.json` items hydrate into `ReviewDecisionItem` payloads with title, subtitle, human reason, severity, suggested action, evidence refs, local state, and technical details.

## Dynamic Review Summary
The backend exposes deterministic summary counts for possible merges, probable aliases, uncertain relationships, insufficient evidence, pronoun/POV, unconfirmed local candidates, deferred items, and local unapplied decisions.

## Graph UX Filters
Graph filters now support multi-select kind filters. The duplicate `Mostrar todo` behavior is replaced by `Restablecer filtros`.

## Node Inspector Hydration
Graph nodes include author-facing metadata for summary, aliases, note path, degree, review count, evidence count, tags, backlinks, and outgoing links where available.

## Ingestion Progress Contract
SP-108B writes `reports/run_status.json` for the SP-107 run with author-facing pipeline steps, final status `completed_with_editorial_review`, and `safe_to_open_workspace=true`. Internal paths stay Dev/debug-only.

## Private Decision Handoff
Private details live at `docs/handoffs/private/safepoint-108b_canonical-projection-review-progress/decision_handoff_private.md` and must not be staged.

## Product Decision
Assessment: `canonical_author_graph_ready_review_hydrated`.

## Recommended Next Phase
Implement local review actions and VaERL patch/write-back mechanics for accept/reject/merge decisions.

## What Worked
- Author graph generated deterministically from clean Markdown projection.
- Project reader serves canonical author graph first.
- Review queue cards hydrate without generic placeholders.
- Ingestion screen can render finalized progress steps.

## What Failed
- No semantic merge/write-back is implemented yet.
- Existing TypeScript typecheck has dependency/type environment issues outside this patch.

## Data Written
- Private project: `graph/author_graph.json` and `reports/run_status.json`.
- Commit-safe reports: `tests/fixtures/textifai/canonical_projection_regression/expected/*.json`.

## Privacy / Non-committed Output
Private project package, provider outputs, source prose, registry, and private handoff remain unstaged and uncommitted.

## Tests Added / Updated
- Added `tests/test_textifai_canonical_projection_regression.py`.
- Added canonical projection regression expected reports.

## Validation Performed
- `uv run python scripts/dev/sp108b_canonical_projection_refresh.py`
- `uv run python -m unittest -v tests.test_textifai_canonical_projection_regression`

## Safety Constraints
No provider calls, no full rerun, no retry, no editor write-back, no source prose in commit-safe artifacts, no raw provider outputs in commit-safe artifacts.

## Known Limitations
Author graph is deterministic cleanup/projection over existing SP-107 artifacts. It does not improve underlying semantic extraction quality.

## Future Extensions
- Review decision local state persistence.
- VaERL patch queue and safe write-back.
- Canonical merge policy for author-approved decisions.
- Live runner events via `run_events.jsonl` and `heartbeat.json`.

## Runtime Changes
Runtime graph API now prefers `graph/author_graph.json`. Runtime project detail includes `run_status`.

## Write-back
No editor write-back. No VaERL write-back from review actions.

## Branch
`phase-1.3-ingestion-vaerl-hardening`
