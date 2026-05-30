# ADR-0001: ProjectStore hybrid architecture (Markdown + SQLite + JSON snapshots)

- Status: Accepted
- Date: 2026-05-30
- Safepoint: SP-114

## Problem statement
TextifAI is moving from viewer/debug workflows to author-facing product workflows. Current runtime still relies on scattered JSON artifacts as primary operational source in multiple flows. Before full write-back features (chapter editing, ficha editing, review operations, targeted mini-ingestion), project needs stable data architecture with clear source-of-truth boundaries.

## Current pain points
- JSON artifacts duplicated across runtime phases with weak ownership.
- IDs/aliases/relations/review state fragmented and hard to query incrementally.
- No normalized operational state store for dirty flags, job states, and migration versions.
- Bundle/export direction (`.txtfai`) not clearly separated from live editing substrate.
- Team/SaaS future path unclear if local artifact model stays primary contract.

## Decision drivers
- Local-first author workflow.
- Portable project files for backup/share/export.
- Deterministic CRUD for chapters/entities/review/evidence/graph projections.
- Versioned migration path.
- Future backend portability for SaaS collaboration.

## Alternatives considered
### A. JSON-only
Pros: simple writes, transparent files.
Cons: weak relational integrity, heavy fan-out updates, poor indexing/query cost, fragile migrations.

### B. Markdown-only
Pros: best author portability.
Cons: operational state (review queues, evidence refs, aliases, dirty states) becomes brittle and parser-heavy.

### C. SQLite-only
Pros: strong operational model and queries.
Cons: poor author-facing portability and inspectability of prose/canon content.

### D. Hybrid Markdown + SQLite + JSON snapshots (chosen)
Pros: separates author substrate from operational state; supports migrations/indexes; keeps JSON for snapshots/debug/export contracts.
Cons: dual-write/consistency rules needed; explicit ownership contract required.

### E. Hosted DB only
Pros: strong collaboration/central control.
Cons: breaks local-first baseline, network dependency, operational cost and onboarding friction.

## Decision
Adopt hybrid architecture:
- Markdown/files: author-facing portable substrate (chapter body, ficha body, notes).
- SQLite per project: ProjectStore operational CRUD/index/state.
- JSON: snapshots/reports/debug/import-export artifacts; not live CRUD source.
- `.textifai/` folder: live editable project root.
- `.txtfai`: portable bundle format for export/import/backup, not live editing database.

## Ownership model
- Markdown owns narrative text and author-facing readable docs.
- SQLite owns IDs, aliases, relationships, evidence refs, source chunks, review state, dirty flags, and job/migration metadata.
- JSON owns snapshots/reports/debug fixtures and transfer payloads.

## Vector backend strategy
- Define logical `VectorIndex` contract behind ProjectStore.
- Default index/search path: SQLite FTS for lexical retrieval and baseline local relevance.
- Keep embedding/vector backend pluggable; candidates: `sqlite-vec`, `LanceDB`, `pgvector`.
- Do not hard-couple schema or API to one vector vendor in v0.

## Migration strategy
1. Introduce ProjectStore contract + SQLite schema v0 alongside existing readers.
2. Start writing operational state to SQLite while preserving Markdown ownership.
3. Generate JSON snapshots from canonical stores (Markdown + SQLite), not vice versa.
4. Add schema migrations table and versioned migration runner.
5. Incrementally route review/evidence/graph projections through ProjectStore reads.

## Local-first strategy
- Primary mode: single-user local `.textifai` project with embedded SQLite.
- No provider calls required for architecture/documentation phase.
- Offline-capable read/write for author workflows.

## SaaS/team strategy
- Most users remain individual/local-first.
- Collaborative/team mode can be online-only.
- Future managed backend: Postgres (or equivalent), mapping same logical ProjectStore contract.
- Do not attempt local SQLite multi-user collaboration in SP-114.

## `.txtfai` bundle strategy
- `.txtfai` is zip-like portable package.
- Open flow: import/extract into `.textifai` working folder.
- Work flow: edit live project folder.
- Export flow: package live folder into `.txtfai` with manifest/validation.
- Vector cache included by policy (optional/excludable), rebuildable when omitted.

## Consequences
- Clearer contract boundaries and future migration safety.
- Additional consistency checks needed between Markdown and SQLite.
- Introduces migration and schema lifecycle responsibilities.
