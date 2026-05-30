# TextifAI SQLite Schema v0

Status: Draft for SP-114 (architecture + light prototype)

## Table contracts

### `project_meta`
- Purpose: project identity/version metadata.
- Key fields: `project_id`, `title`, `language`, `schema_version`, `created_at`, `updated_at`.
- Ownership: SQLite.
- Relation: mirrors manifest core fields; Markdown-independent.
- Migration notes: bump `schema_version` with `migrations` records.

### `files`
- Purpose: file index and checksums for Markdown/JSON payloads.
- Key fields: `path`, `kind`, `checksum`, `last_seen_at`.
- Ownership: SQLite index of filesystem assets.
- Relation: points to Markdown/JSON locations; does not own file body.
- Migration notes: additive columns for hash/version algorithms.

### `chapters`
- Purpose: chapter operational metadata.
- Key fields: `chapter_id`, `ordinal`, `title`, `markdown_path`, `status`, `dirty`.
- Ownership: SQLite metadata; Markdown owns chapter body.
- Relation: binds chapter IDs to markdown files.
- Migration notes: preserve stable `chapter_id` across path renames.

### `entities`
- Purpose: canonical entity registry.
- Key fields: `entity_id`, `canonical_name`, `kind`, `ficha_markdown_path`, `summary`.
- Ownership: split; SQLite metadata, Markdown owns ficha body.
- Relation: links to canon markdown and graph/review state.
- Migration notes: entity IDs immutable.

### `entity_aliases`
- Purpose: alias resolution per entity.
- Key fields: `alias_id`, `entity_id`, `alias`, `alias_type`, `confidence`.
- Ownership: SQLite.
- Relation: derived from extraction/review decisions; can emit JSON snapshots.
- Migration notes: unique `(entity_id, alias)` constraint retained.

### `relationships`
- Purpose: typed edges between entities.
- Key fields: `relationship_id`, `src_entity_id`, `dst_entity_id`, `relation_type`, `state`.
- Ownership: SQLite.
- Relation: graph projection source plus Markdown references.
- Migration notes: edge IDs stable; allow soft-deprecate state.

### `evidence_items`
- Purpose: evidence references tied to entities/relations/review items.
- Key fields: `evidence_id`, `source_ref`, `chapter_id`, `excerpt`, `confidence`.
- Ownership: SQLite.
- Relation: references source chunks/markdown offsets; JSON exports for audits.
- Migration notes: keep source locator fields backward compatible.

### `source_chunks`
- Purpose: normalized chunk catalog for source/chapter text spans.
- Key fields: `chunk_id`, `chapter_id`, `char_start`, `char_end`, `text_hash`.
- Ownership: SQLite index; source text remains file-based.
- Relation: supports evidence links and retrieval.
- Migration notes: chunk IDs can be regenerated with deterministic hash policy.

### `review_items`
- Purpose: pending/reviewable items queue.
- Key fields: `review_item_id`, `item_type`, `target_id`, `status`, `priority`, `created_at`.
- Ownership: SQLite.
- Relation: replaces JSON-only live queue; JSON snapshot still emitted.
- Migration notes: map legacy queue IDs where possible.

### `review_decisions`
- Purpose: immutable audit trail for review outcomes.
- Key fields: `decision_id`, `review_item_id`, `decision`, `rationale`, `actor`, `decided_at`.
- Ownership: SQLite.
- Relation: feeds snapshot reports.
- Migration notes: append-only.

### `graph_nodes`
- Purpose: persisted graph projection nodes.
- Key fields: `node_id`, `entity_id`, `label`, `kind`, `degree`.
- Ownership: SQLite projection cache.
- Relation: derived from entities/relationships; exportable JSON graph.
- Migration notes: rebuildable cache table.

### `graph_edges`
- Purpose: persisted graph projection edges.
- Key fields: `edge_id`, `src_node_id`, `dst_node_id`, `relation_type`, `weight`.
- Ownership: SQLite projection cache.
- Relation: derived from `relationships`.
- Migration notes: rebuildable cache table.

### `dirty_states`
- Purpose: per-resource dirty/reindex flags.
- Key fields: `resource_type`, `resource_id`, `dirty_reason`, `updated_at`.
- Ownership: SQLite.
- Relation: drives rebuild/index jobs.
- Migration notes: may split by pipeline later.

### `jobs`
- Purpose: run/job lifecycle records.
- Key fields: `job_id`, `job_type`, `status`, `started_at`, `finished_at`, `error`.
- Ownership: SQLite.
- Relation: supersedes fragmented runtime JSON status for live state.
- Migration notes: keep status enum extendable.

### `migrations`
- Purpose: schema migration ledger.
- Key fields: `migration_id`, `applied_at`, `checksum`.
- Ownership: SQLite.
- Relation: independent from Markdown/JSON.
- Migration notes: strictly append-only.

### `settings`
- Purpose: project-scoped configuration key/value.
- Key fields: `key`, `value`, `updated_at`.
- Ownership: SQLite.
- Relation: optional overrides for runtime/index/export behaviors.
- Migration notes: validate reserved key namespace.
