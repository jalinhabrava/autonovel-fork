# Prompt Evaluation Status

Current status: `paused_pending_obsidian_bridge_reliability`

This repository currently keeps prompt/export evaluation as a **partial pipeline check**, not as definitive product-quality validation.

Why:

- prompt quality depends on the vault context actually available to VaERL,
- previous prompt evaluation rounds were running against simplified or synthetic vault fixtures,
- that is useful for testing the pipeline shape,
- but it is not yet the final operational context expected from a structured Markdown vault source compatible with Obsidian, or from a future live Obsidian bridge.

Until a fresh and valid Obsidian bridge snapshot is available, or a future live Obsidian bridge exists:

- enriched prompt inspection remains useful,
- trace/debug exports remain useful,
- but author-facing prompt/output quality should not be treated as final product validation.

Current context-source interpretation:

- `vault_reader_only`: useful for partial pipeline checks, not definitive product evaluation
- `obsidian_bridge_snapshot_fresh`: preferred bridge-backed context source
- `obsidian_bridge_snapshot_stale`: usable with caution, not ideal for prompt quality conclusions
- `obsidian_bridge_snapshot_invalid`: do not treat prompt quality conclusions as reliable

Methodological rule for now:

1. inspect the author input
2. inspect the enriched prompt payload
3. inspect support/anchoring diagnostics
4. run live provider evaluation only after confirming the context source is representative
