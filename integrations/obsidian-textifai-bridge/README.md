# TextifAI Obsidian Bridge

This plugin exports a structured snapshot of the current Obsidian vault so TextifAI can consume:

- note metadata from `metadataCache`
- `resolvedLinks` / `unresolvedLinks`
- aliases and frontmatter
- headings and tags
- markdown body text

Default export path:

- `.textifai/obsidian-bridge-snapshot.json`

The Python side of TextifAI will prefer this snapshot over plain vault markdown scanning when it is present.
