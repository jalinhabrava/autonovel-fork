# Obsidian Bridge Status

Current state:

- `textifai/obsidian/reader.py` provides a structured reader for vault Markdown compatible with Obsidian.
- `integrations/obsidian-textifai-bridge/` adds the first real plugin-side bridge layer:
  - exports metadata from `Vault.getMarkdownFiles()`
  - reads note content with `Vault.cachedRead()`
  - includes `MetadataCache.getFileCache()`
  - includes `resolvedLinks` and `unresolvedLinks`
  - reacts to `metadataCache.resolved`, `metadataCache.changed`, and vault create/rename/delete events
  - exports a versioned snapshot contract with vault identity, installation identity, export sequence, capabilities, completeness flags, and timestamps
  - writes the snapshot atomically through temp-file + rename
  - exposes enough metadata for TextifAI to distinguish fresh / stale / invalid bridge state

Important:

- this is stronger than plain vault Markdown compatibility,
- but it is still not a full live sync platform integration,
- TextifAI currently consumes the exported snapshot file when present and otherwise falls back to vault Markdown scanning.

This means the current bridge is:

- `bridge-backed snapshot interoperability`: yes
- `live bidirectional Obsidian integration`: not yet

Snapshot validity policy in TextifAI:

- `snapshot válido`
  - schema soportado
  - timestamp parseable
  - export completo
  - identidad de vault e instalación presentes en schema `2.0`
  - notas parseables y `note_count` consistente

- `snapshot usable but stale`
  - snapshot válido pero viejo según la política de freshness
  - o snapshot `1.0` cargado en modo de compatibilidad hacia atrás
  - usable con cautela, no ideal para conclusiones fuertes sobre prompt quality

- `snapshot unusable`
  - JSON corrupto
  - schema no soportado
  - export incompleto
  - contrato mínimo roto
  - en ese caso TextifAI cae a `vault_reader_only` si el fallback está permitido

MetadataCache currently used by the plugin:

- `getFileCache(file)`
- `resolvedLinks`
- `unresolvedLinks`
- `links`
- `embeds`
- `frontmatterLinks`
- `tags`
- `headings`
- `sections`

Stable and useful for TextifAI:

- resolved links
- unresolved links
- headings
- tags
- frontmatter and aliases
- link/embeds/frontmatter link cache

Still limited for full product closure:

- no direct long-lived Python <-> Obsidian runtime channel
- no incremental transport beyond repeated snapshot export
- no authoritative “live session” coupling between TextifAI runtime and Obsidian app state
