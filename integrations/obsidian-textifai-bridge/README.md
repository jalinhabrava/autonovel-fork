# TextifAI Obsidian Bridge

This plugin exports a structured Obsidian snapshot that TextifAI can consume as a higher-fidelity context source than plain vault markdown scanning.

## What it exports

- markdown note body via `Vault.cachedRead()`
- `MetadataCache.getFileCache()`
- `resolvedLinks` / `unresolvedLinks`
- headings
- sections
- tags
- wikilinks
- embeds
- frontmatter links
- aliases and `project_confirmed_aliases`
- note path canonicalization
- vault identity and installation identity
- export sequence and timestamp

## Why it exists

TextifAI can already read vault markdown directly, but that path does not give it the same metadata layer that Obsidian itself maintains in memory.

The bridge closes part of that gap by exporting a snapshot that is:

- deterministic enough for tests
- richer than plain markdown scanning
- robust enough to drive VaERL and author-facing context retrieval

## Output path

Default:

- `.textifai/obsidian-bridge-snapshot.json`

TextifAI also checks:

- `99_System/obsidian_bridge_snapshot.json`

## Install in Obsidian Desktop

1. Build the plugin:

```bash
npm install
npm run build
```

2. Copy these files into your vault plugin directory:

- `manifest.json`
- `main.js`
- `styles.css` if added later

Target folder:

- `<your-vault>/.obsidian/plugins/textifai-bridge/`

3. In Obsidian:

- open `Settings`
- go to `Community plugins`
- enable `TextifAI Bridge`

4. Run the command:

- `Export TextifAI context snapshot`

## Export behavior

- the plugin auto-exports on startup when enabled
- it also listens to `metadataCache.on("resolved")`
- and to markdown create/rename/delete / metadata-changed events
- exports are debounced
- writes use a temp file + rename strategy to avoid half-written snapshots

## Limits

This is stronger than plain markdown reading, but it is still snapshot interoperability, not a fully live bidirectional runtime bridge.

TextifAI currently treats this as:

- preferred over vault markdown scanning
- still distinct from a future fully live Obsidian transport layer
