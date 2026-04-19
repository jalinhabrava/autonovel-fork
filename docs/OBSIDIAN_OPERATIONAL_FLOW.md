# Obsidian Operational Flow

TextifAI now distinguishes between:

- `vault markdown` as the durable project source of truth,
- the `TextifAI Bridge` plugin as the Obsidian-side metadata producer,
- the exported bridge snapshot as the interoperability layer,
- `VaERL` as the retrieval/index layer over that context,
- and author-facing consumers that must not treat all context states as equally trustworthy.

## Startup Modes

### Mode A: Existing Material

Use `textifai.obsidian.prepare_obsidian_project(..., mode="existing_material")`.

What happens:

1. Create or validate the target vault.
2. Install the bridge plugin into `.obsidian/plugins/textifai-bridge` if requested.
3. Run TextifAI bootstrap staging over the source documents.
4. Leave imported material in `99_Import_Staging` with provenance and review semantics.
5. Index the vault through VaERL on the currently available source.

Important:

- The official Obsidian Importer exists and is useful for user-driven import of Markdown and other app exports.
- TextifAI still prefers its own staged import path for automated bootstrap because it needs:
  - deterministic provenance,
  - reviewable staging,
  - and a headless path that does not depend on the Obsidian Desktop UI.

### Mode B: New Project

Use `textifai.obsidian.prepare_obsidian_project(..., mode="new_project")`.

What happens:

1. Create the canonical TextifAI vault structure.
2. Install the bridge plugin if requested.
3. Evaluate operational readiness.
4. Expose a vault ready for later author interactions and incremental project propagation.

## Operational Readiness Policy

TextifAI now evaluates the vault before treating responses as seriously grounded.

- `bootstrap_only`
  - vault missing or invalid
  - bootstrap flows allowed
  - context-sensitive authoring flows blocked

- `degraded_context`
  - vault valid, but source is only markdown reader or stale snapshot
  - VaERL can still run
  - context-sensitive flows are allowed only in degraded mode
  - prompt quality evaluation should not be treated as definitive

- `anchored_context_ready`
  - fresh, valid bridge snapshot available
  - strong grounding allowed
  - prompt evaluation can be treated as representative enough for serious review

## Interaction Rule

Every relevant semantic interaction should:

1. resolve the current operational readiness,
2. query VaERL against the preferred source,
3. build author-facing context from the same source family,
4. and only then consider any grounded response path.

This does not yet create a live Obsidian runtime channel, but it does mean TextifAI is no longer treating markdown-only and bridge-fresh contexts as equivalent.
