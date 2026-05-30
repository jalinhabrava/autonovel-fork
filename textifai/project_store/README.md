# TextifAI ProjectStore Contract (SP-114)

Status: interface contract + architecture stub (no runtime migration in this safepoint)

## Minimal interface
- `open_project(path)`
- `create_project(path)`
- `validate_project()`
- `get_chapters()`
- `get_chapter(chapter_id)`
- `save_chapter_draft(...)`
- `mark_chapter_dirty(...)`
- `get_entity(entity_id)`
- `update_entity_ficha(...)`
- `get_review_queue()`
- `record_review_decision(...)`
- `get_evidence(evidence_id)`
- `get_graph_projection()`
- `export_json_snapshots()`
- `export_txtfai(path)`
- `import_txtfai(path)`
- `rebuild_indexes()`
- `migrate_schema()`

## Storage split
- Markdown/files: narrative and author-facing ficha bodies.
- SQLite: operational CRUD/index/state.
- JSON snapshots: reports/debug/export fixtures; not primary CRUD.

## Future backends
- Local default: SQLite.
- Team/SaaS future: Postgres/managed backend via same logical contract.
- Vector backend behind pluggable `VectorIndex` adapter.
