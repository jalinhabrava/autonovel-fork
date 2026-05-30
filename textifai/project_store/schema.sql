PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS project_meta (
  project_id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  language TEXT,
  schema_version INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS files (
  file_id INTEGER PRIMARY KEY,
  path TEXT NOT NULL UNIQUE,
  kind TEXT NOT NULL,
  checksum TEXT,
  char_count INTEGER,
  last_seen_at TEXT
);

CREATE TABLE IF NOT EXISTS chapters (
  chapter_id TEXT PRIMARY KEY,
  ordinal INTEGER NOT NULL,
  unit_type TEXT,
  title TEXT,
  display_title TEXT,
  markdown_path TEXT NOT NULL,
  content_hash TEXT,
  char_count INTEGER,
  source_start INTEGER,
  source_end INTEGER,
  status TEXT,
  dirty INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS entities (
  entity_id TEXT PRIMARY KEY,
  canonical_name TEXT NOT NULL,
  kind TEXT,
  ficha_markdown_path TEXT,
  summary TEXT
);

CREATE TABLE IF NOT EXISTS entity_aliases (
  alias_id INTEGER PRIMARY KEY,
  entity_id TEXT NOT NULL,
  alias TEXT NOT NULL,
  alias_type TEXT,
  confidence REAL,
  UNIQUE(entity_id, alias),
  FOREIGN KEY(entity_id) REFERENCES entities(entity_id)
);

CREATE TABLE IF NOT EXISTS relationships (
  relationship_id TEXT PRIMARY KEY,
  src_entity_id TEXT NOT NULL,
  dst_entity_id TEXT NOT NULL,
  relation_type TEXT NOT NULL,
  state TEXT,
  FOREIGN KEY(src_entity_id) REFERENCES entities(entity_id),
  FOREIGN KEY(dst_entity_id) REFERENCES entities(entity_id)
);

CREATE TABLE IF NOT EXISTS evidence_items (
  evidence_id TEXT PRIMARY KEY,
  source_ref TEXT,
  chapter_id TEXT,
  excerpt TEXT,
  confidence REAL
);

CREATE TABLE IF NOT EXISTS source_chunks (
  chunk_id TEXT PRIMARY KEY,
  chapter_id TEXT,
  char_start INTEGER,
  char_end INTEGER,
  text_hash TEXT
);

CREATE TABLE IF NOT EXISTS review_items (
  review_item_id TEXT PRIMARY KEY,
  item_type TEXT NOT NULL,
  target_id TEXT,
  status TEXT NOT NULL,
  priority INTEGER,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS review_decisions (
  decision_id TEXT PRIMARY KEY,
  review_item_id TEXT NOT NULL,
  decision TEXT NOT NULL,
  rationale TEXT,
  actor TEXT,
  decided_at TEXT NOT NULL,
  FOREIGN KEY(review_item_id) REFERENCES review_items(review_item_id)
);

CREATE TABLE IF NOT EXISTS graph_nodes (
  node_id TEXT PRIMARY KEY,
  entity_id TEXT,
  label TEXT,
  kind TEXT,
  degree INTEGER
);

CREATE TABLE IF NOT EXISTS graph_edges (
  edge_id TEXT PRIMARY KEY,
  src_node_id TEXT NOT NULL,
  dst_node_id TEXT NOT NULL,
  relation_type TEXT,
  weight REAL
);

CREATE TABLE IF NOT EXISTS dirty_states (
  resource_type TEXT NOT NULL,
  resource_id TEXT NOT NULL,
  dirty_reason TEXT,
  updated_at TEXT NOT NULL,
  PRIMARY KEY(resource_type, resource_id)
);

CREATE TABLE IF NOT EXISTS jobs (
  job_id TEXT PRIMARY KEY,
  job_type TEXT NOT NULL,
  status TEXT NOT NULL,
  started_at TEXT,
  finished_at TEXT,
  error TEXT
);

CREATE TABLE IF NOT EXISTS migrations (
  migration_id TEXT PRIMARY KEY,
  applied_at TEXT NOT NULL,
  checksum TEXT
);

CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT,
  updated_at TEXT
);
