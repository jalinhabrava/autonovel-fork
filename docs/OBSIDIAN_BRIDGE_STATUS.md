# Obsidian Bridge Status

Current state:

- `textifai/obsidian/reader.py` provides a structured reader for vault Markdown compatible with Obsidian.
- `integrations/obsidian-textifai-bridge/` adds the first real plugin-side bridge layer:
  - exports metadata from `Vault.getMarkdownFiles()`
  - reads note content with `Vault.cachedRead()`
  - includes `MetadataCache.getFileCache()`
  - includes `resolvedLinks` and `unresolvedLinks`
  - reacts to `metadataCache.resolved`, `metadataCache.changed`, and vault rename/delete events

Important:

- this is stronger than plain vault Markdown compatibility,
- but it is still not a full live sync platform integration,
- TextifAI currently consumes the exported snapshot file when present and otherwise falls back to vault Markdown scanning.

This means the current bridge is:

- `bridge-backed snapshot interoperability`: yes
- `live bidirectional Obsidian integration`: not yet
