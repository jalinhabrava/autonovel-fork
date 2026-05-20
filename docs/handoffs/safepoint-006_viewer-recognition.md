# Viewer Recognition

## Current Viewer Architecture

### Entrypoints

- CLI path: `uv run python scripts/textifai.py viewer --root <root>`.
- CLI dispatch: `textifai/obsidian/cli.py` imports `run_viewer_server` and exposes `viewer`.
- Server entrypoint: `textifai/web_viewer/server.py`.
- Server function: `run_viewer_server(roots, host, port, open_browser)`.

### Routes

The viewer uses a small `ThreadingHTTPServer` and read-only HTTP GET routes:

- `GET /`: static `index.html`.
- `GET /api/projects`: list discovered projects/runs.
- `GET /api/projects/<project_id>`: full project payload.
- `GET /api/projects/<project_id>/graph`: graph payload.
- `GET /api/projects/<project_id>/canon`: canon payload.
- `GET /api/projects/<project_id>/artifacts`: artifact metadata.
- `GET /api/projects/<project_id>/note?path=...`: Markdown note payload.
- `GET /api/projects/<project_id>/artifact?path=...`: JSON/text artifact payload.

### Templates / Components

- Static HTML shell: `textifai/web_viewer/static/index.html`.
- Client UI logic: `textifai/web_viewer/static/app.js`.
- Styling: `textifai/web_viewer/static/styles.css`.
- There is no server-side template engine; UI is client-rendered with vanilla JavaScript.

Main tabs:

- Overview
- Notes
- Canon
- Review Queue
- Graph
- Artifacts

### Static Assets

- `app.js`: state management, fetch calls, tab rendering, Markdown renderer, wiki-link navigation, graph layout.
- `styles.css`: parchment-style internal UI, cards, tables, graph styling, badges, responsive layout.
- `index.html`: application shell and tab containers.

### Data Loading Flow

- `ProjectCatalog` receives configured roots.
- Discovery scans each root and direct child directories.
- A candidate becomes a project if it has `99_System/obsidian_import.json` or `99_System/review_queue.json`.
- A candidate can also be a direct `99_System` directory.
- `read_project()` assembles:
  - project metadata
  - Markdown note list
  - canon payload
  - artifact list
  - graph payload
- `read_canon()` reads `obsidian_import.json` and `review_queue.json`.
- `list_artifacts()` exposes selected `99_System` artifacts and top-level JSON files.
- `read_artifact()` reads JSON/text artifacts or directory children.
- `read_note()` reads Markdown, frontmatter, and Obsidian links.

### Graph Stack

- Backend graph builder: `build_graph()` in `textifai/web_viewer/project_reader.py`.
- Graph source: `obsidian_import.json` entities/chapters plus `review_queue.json` via canon payload.
- Node types:
  - primary entity
  - review entity
  - unresolved relationship target
  - chapter
- Edges:
  - entity relationship edges from `relationships`.
- Frontend rendering:
  - custom SVG force layout in `app.js`.
  - no D3 dependency.
  - supports pan/zoom, kind filtering, tag filtering, hide review, hide chapters, hide system.
- Graph node detail:
  - opens note if materialized Markdown exists.
  - falls back to VaERL/entity/chapter data from `obsidian_import.json` when no note exists.

### Markdown Rendering

- Markdown notes are read server-side as text.
- Frontend strips frontmatter and renders simple Markdown:
  - headings
  - bullet lists
  - paragraphs
  - wikilinks
- Wikilinks are resolved against graph node labels/slugs and note filenames.
- Rendering is intentionally lightweight, not a full Markdown engine.

### Artifact Inspection Flow

- Artifact list is driven by `VISIBLE_ARTIFACTS` plus any extra top-level `99_System/*.json`.
- Exposed artifacts include:
  - `novel_index.json`
  - `global_normalization.json`
  - `canonical_entity_map.json`
  - `resolved_entities.json`
  - `cleaned_entities.json`
  - `obsidian_import.json`
  - `chapter_extraction_audit.json`
  - `semantic_invariants_audit.json`
  - `review_queue.json`
  - `run_comparability_manifest.json`
  - `semantic_replay_audit.json`
  - `pre_vaerl_reconciliation_audit.json`
  - `primary_note_synthesis_audit.json`
  - `obsidian_relationship_reconciliation_audit.json`
- Directory artifact support currently lists file children, notably `chapter_outputs`.
- Artifact detail renders raw pretty JSON or text.

### Review Queue Visibility

- Project cards show `review_queue_count`.
- Overview shows review item count.
- Review tab shows:
  - item count
  - number of review types
  - queue status
  - item table with severity, type, source, target, candidates, and first evidence text.

### Semantic State Exposure

Already exposed:

- primary count
- review entity count
- review queue count
- invariant status from `semantic_invariants_audit.json`
- canonical entities
- review entities
- chapter summaries and IDs
- entity aliases, facts, relationships, source mentions
- unresolved relationship targets as graph nodes
- raw artifact JSON for deeper inspection

## Existing Capabilities

### What Already Works Well

- Local read-only viewer over run/vault roots.
- Zero external frontend framework or build step.
- Safe path handling for note and artifact reads.
- Clear separation between server route layer and project reader layer.
- Useful canonical graph derived from `obsidian_import.json`.
- Review entities are separated from canonical primaries.
- Graph can hide review/chapter/system-style content.
- Tag filter and kind filter help reduce graph noise.
- Artifact tab gives access to core pipeline JSON without opening folders manually.
- Graph detail fallback exposes VaERL data even without materialized Markdown notes.

### What Is Already Inspectable

- Runs/vaults that contain `99_System/obsidian_import.json` or `review_queue.json`.
- Markdown notes and frontmatter.
- Canonical primaries and review entities.
- Chapter list and chapter summaries.
- Review queue table.
- Raw visible artifacts.
- Graph relationships and unresolved relationship target placeholders.
- Entity-level aliases, key facts, relationships, source mentions, confidence when present.
- Chapter title parse signals in graph node detail.

## Observability Gaps

### Semantic State Visibility

- Overview is count-oriented, not diagnostic.
- No semantic health summary explaining what is stable vs unresolved.
- No entity-state badges in Canon table beyond implicit grouping.
- No visible confidence distribution or review-state distribution.
- No narrative-state concepts yet: knowledge boundaries, secrets, promises, emotional/authority shifts, unresolved tensions.

### Merge Visibility

- No dedicated merge/canonicalization explanation panel.
- No clear lineage from source mentions/aliases to canonical entity decision.
- No side-by-side view of canonical entity vs review candidates.
- `canonical_entity_map.json`, cleanup audits, and reconciliation audits are raw artifacts only.

### Unresolved Visibility

- Unresolved relationship targets appear as graph nodes, but there is no focused unresolved-target inspector.
- No aggregate count of unresolved relationships on overview.
- No grouping by source entity, target text, severity, or candidate availability.

### Review Queue Visibility

- Review tab is useful but flat.
- No filters by severity/type/source/target.
- No grouping or sorting controls.
- No deep detail drawer for a review item.
- No linkage from a review item to graph nodes/artifact evidence.

### Invariant Visibility

- Project cards show invariant status, but no invariant panel exists.
- `semantic_invariants_audit.json` is raw JSON only.
- No breakdown of passed/failed checks, thresholds, or actionable failure list.
- No direct mapping from invariant failure to affected entity/chapter/artifact.

### Narrative Continuity Visibility

- No timeline view.
- No chapter-to-state transition view.
- No character knowledge boundary view.
- No relationship evolution view.
- No continuity-sensitive state summary.

### Retrieval Debugging Visibility

- No retrieval preview/context package inspection.
- No evidence bundle view.
- No way to inspect why a future harness would include or exclude facts.
- No query/retrieval trace surfaces yet.

### Run Comparison Visibility

- No semantic diff panel.
- No comparison between two runs.
- `run_comparability_manifest.json` is raw artifact only.
- No artifact hash/comparability summary.

## Dangerous Areas

### Semantic Contract Risk

- `project_reader.py` derives graph/canon view from `obsidian_import.json`; changing field interpretation can alter observer assumptions even if semantic artifacts stay unchanged.
- Adding computed metrics is low-risk if read-only, but naming them as authoritative contracts should be avoided unless approved.
- Any change to `textifai/obsidian/**`, `textifai/import_review/**`, or `textifai/vaerl/**` would raise semantic contract risk and is out of scope for this recognition pass.

### Write-Back Risk

- Viewer is currently read-only; preserving this is important.
- Any action buttons that mutate review state, notes, canon, vault files, or artifacts must be excluded from Phase 1.1 unless separately approved.

### Vault Mutation Risk

- Server reads Markdown and artifacts from configured roots.
- Current safe behavior depends on read-only GET routes.
- Future features must avoid writing into real `vault/` or run outputs.

### Large Run Performance Risk

- `read_project()` eagerly loads notes, canon, artifacts, and graph for a selected project.
- `build_graph()` processes all entities/chapters.
- `_guess_note_path()` uses `root.rglob()` per entity/chapter candidate, which may be expensive for large vaults.
- Frontend force layout and tables may struggle with very large entity/review queues.

## Suggested Phase 1.1 Slices

### Slice A — Run Overview Dashboard

- Value: high. Turns selected run into diagnostic landing page.
- Complexity: low to medium.
- Semantic risk: low if derived read-only from existing artifacts.
- Recommended validation:
  - targeted `tests/test_textifai_web_viewer.py`
  - `uv run python scripts/textifai.py viewer --help`
  - manual inspection if browser run is approved

Possible contents:

- artifact presence matrix
- counts for chapters, primaries, review entities, review queue items
- invariant status summary
- comparability manifest presence
- warnings for missing expected artifacts

### Slice B — Invariant Status Panel

- Value: high. Makes semantic quality gates visible without raw JSON spelunking.
- Complexity: low to medium.
- Semantic risk: low if display-only.
- Recommended validation:
  - targeted tests with fixture `semantic_invariants_audit.json`
  - no replay required

Possible contents:

- pass/fail status
- counts by severity/check
- failed checks table
- link to raw artifact

### Slice C — Review Queue Panel Upgrade

- Value: high. Review queue is current author-actionable semantic state.
- Complexity: medium.
- Semantic risk: low if display-only.
- Recommended validation:
  - targeted viewer tests
  - fixture review queue display checks

Possible contents:

- severity/type filters
- grouping by review type
- detail drawer
- evidence/candidate expansion
- graph-note cross-links

### Slice D — Entity State Badges

- Value: medium-high. Makes canonical vs review vs unresolved state visible everywhere.
- Complexity: low.
- Semantic risk: low if only presentation.
- Recommended validation:
  - targeted frontend/static inspection
  - graph/canon tests if backend payload changes

Possible contents:

- canonical/review/unresolved badges
- confidence badge
- source mention count
- relationship count

### Slice E — Unresolved Relationship Inspector

- Value: high for canonicalization debugging.
- Complexity: medium.
- Semantic risk: low to medium depending on whether backend computes new summaries.
- Recommended validation:
  - targeted tests over `build_graph()` unresolved nodes
  - review queue fixture when available

Possible contents:

- unresolved target list
- source entity
- relation type
- candidate availability
- evidence snippets

### Slice F — Merge Explanation Panel

- Value: high for entity-resolution debugging.
- Complexity: medium-high.
- Semantic risk: medium because it may depend on audit artifact semantics.
- Recommended validation:
  - artifact fixture tests
  - explicit semantic-contract review if audit interpretation becomes standardized

Possible contents:

- canonical entity
- aliases/source mentions
- merged candidates
- cleanup/reconciliation audit references

### Slice G — Retrieval Preview Panel

- Value: future-facing but important for Narrative Harness.
- Complexity: high.
- Semantic risk: medium-high.
- Recommended validation:
  - defer until retrieval/context package contracts exist
  - use safe fixtures/baselines

Possible contents:

- selected entity/chapter context package
- evidence bundle preview
- inclusion/exclusion reasons

### Slice H — Semantic Diff Panel

- Value: high for replay/run comparison.
- Complexity: high.
- Semantic risk: medium.
- Recommended validation:
  - safe fixture baselines
  - explicit artifact diff strategy

Possible contents:

- run pair selection
- entity count/name/slug diff
- invariant diff
- review queue diff
- artifact comparability summary

## Recommended First Slice

Recommended first implementation slice:

### Slice B — Invariant Status Panel

Reason:

- Maximizes semantic observability with minimal semantic risk.
- Uses an existing artifact already listed by the viewer: `semantic_invariants_audit.json`.
- Avoids mutation, write-back, replay, and canon contract changes.
- Moves viewer from raw JSON inspection toward diagnostic semantic health.
- Helps answer “what is stable/unresolved and why should I trust this run?” before generation/harness work.

Suggested implementation boundary:

- Read existing `semantic_invariants_audit.json` through current project payload or a small read-only summary.
- Add an Overview or dedicated panel showing invariant pass/fail status and failure summaries.
- Link to raw artifact for full details.
- Do not alter VaERL, importer, invariant generation, replay, or vault materialization.

Recommended validation:

- Targeted unit test around project reader summary if backend payload changes.
- Browser/manual inspection only if explicitly approved.
- Tier 1 viewer CLI help check.
- Tier 0 Git scope checks.
