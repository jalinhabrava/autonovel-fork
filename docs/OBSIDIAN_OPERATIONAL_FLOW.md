# Obsidian Operational Flow

TextifAI now distinguishes between:

- `vault markdown` as the durable project source of truth,
- the `TextifAI Bridge` plugin as the Obsidian-side metadata producer,
- the exported bridge snapshot as the interoperability layer,
- `VaERL` as the retrieval/index layer over that context,
- and author-facing consumers that must not treat all context states as equally trustworthy.

## Startup Modes

Canonical product entrypoint:

- `uv run textifai`
- `uv run textifai provider`
- `uv run textifai configure-provider`
- `uv run textifai ask --vault-root ...`
- `uv run textifai init --vault-root ...`
- `uv run textifai status --vault-root ...`
- `uv run textifai inspect --vault-root ...`

Development aliases still work:

```bash
uv run python scripts/textifai.py
```

The recommended onboarding entrypoint is now:

```bash
uv run textifai
```

It asks in English:

- whether the project starts from zero or from existing documentation,
- where the vault should live,
- where the source documentation lives if needed,
- the project title and working languages,
- whether the bridge plugin should be built now,
- and which LLM provider should back author-facing flows.

Provider onboarding supports:

- OpenAI
- remote OpenAI-compatible providers
- local OpenAI-compatible providers such as LM Studio
- Ollama through its OpenAI-compatible endpoint
- a `skip for now` mode that leaves TextifAI in non-author-facing mode

Important:

- `ask` and other author-facing semantic flows require a configured and reachable provider
- if provider readiness is red, TextifAI should fail honestly instead of inventing editorial capability with local heuristics

The short `init` command automatically chooses:

- `new_project` when no source material is provided
- `existing_material` when `--source-root` is provided
- `existing_material` in-place when `--use-vault-root-as-source` is provided

If the target folder already exists, TextifAI now follows a tolerant policy:

- missing folder: create it
- empty folder: initialize the vault there
- existing non-vault folder: convert it in place without deleting prior material
- existing folder with author documents: adopt it and stage imports there
- only block when a real filesystem or data-integrity conflict exists

### Mode A: Existing Material

Use `textifai.obsidian.prepare_obsidian_project(..., mode="existing_material")`.

What happens:

1. Create or validate the target vault.
2. Install the bridge plugin into `.obsidian/plugins/textifai-bridge` if requested.
3. Run TextifAI bootstrap staging over the source documents.
4. Leave imported material in `99_Import_Staging` with provenance and review semantics.
5. Auto-review low-risk imports and promote only the clearest artifacts to canonical folders.
6. Index the vault through VaERL on the currently available source.

Important:

- The official Obsidian Importer exists and is useful for user-driven import of Markdown and other app exports.
- TextifAI still prefers its own staged import path for automated bootstrap because it needs:
  - deterministic provenance,
  - reviewable staging,
  - and a headless path that does not depend on the Obsidian Desktop UI.

### Import Artifact Levels

Bootstrap now distinguishes between:

- `raw_fragment`
  - source segmentation unit
  - visible in manifests and coverage stats
- `candidate_artifact`
  - staged note in `99_Import_Staging`
  - provisional, reviewable, with semantic metadata
- `promoted_artifact`
  - canonical note already written into folders like `02_World/Lore` or `03_Characters/Profiles`
  - only for low-risk cases; the rest remain in staging

Important:

- staging is still the main bootstrap safety net
- promoted notes are intentionally conservative
- a staged note may be semantically useful for VaERL before it is good enough to be treated as canon

### Mode B: New Project

Use `textifai.obsidian.prepare_obsidian_project(..., mode="new_project")`.

What happens:

1. Create the canonical TextifAI vault structure.
2. Install the bridge plugin if requested.
3. Evaluate operational readiness.
4. Expose a vault ready for later author interactions and incremental project propagation.

## Validation Commands

The current Python entrypoints you should treat as authoritative are:

- `open_obsidian_source(vault_root, snapshot_path=None)`
- `validate_obsidian_snapshot(snapshot_path)`
- `evaluate_obsidian_operational_readiness(vault_root)`
- `build_vault_index(vault_path=...)`

The inspect command wraps those exact calls:

Windows example:

```bash
uv run textifai inspect --vault-root "C:\\Users\\<USER>\\Documents\\TextifAI\\OnT_Vault"
```

Linux example:

```bash
uv run textifai inspect --vault-root "$HOME/Documents/TextifAI/OnT_Vault"
```

WSL remains supported through path normalization, but it is now treated as a development environment rather than the product default.

The expected high-signal fields are:

- `readiness.operational_mode`
- `provider_readiness.provider_mode`
- `provider_readiness.provider_reachable`
- `provider_readiness.author_flows_available`
- `source_status.reliability`
- `source_note_count`
- `raw_fragment_count`
- `candidate_artifact_count`
- `promoted_artifact_count`
- `vaerl_index_entries`
- `vaerl_artifact_types`
- `manifest_summary.promotion_eligible_drafts`

For a first author-facing interaction from the CLI:

```bash
uv run textifai ask --vault-root "C:\\Users\\<USER>\\Documents\\TextifAI\\OnT_Vault"
```

That command:

1. resolves readiness,
2. queries VaERL,
3. routes the request through the conversation manager,
4. and appends a minimal trace to `99_System/textifai_ask_trace.jsonl`.

## Snapshot Refresh Expectation

After the plugin is activated inside Obsidian Desktop, snapshot refresh should no longer be a repetitive manual task.

The bridge is already configured to auto-export:

- on startup,
- after `metadataCache` resolves,
- and after markdown vault changes.

The manual palette command:

- `Export TextifAI context snapshot`

should now be treated mainly as a force-refresh or troubleshooting action, not the normal steady-state workflow.

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
