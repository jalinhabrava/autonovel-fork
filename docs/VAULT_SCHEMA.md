# Vault Schema

## Goal

The vault should support one simple bootstrap loop well:

- source documents in
- chapter-level extraction
- entity merge
- canonical primaries out
- review kept separate

The vault is not meant to encode a giant semantic ontology. It should stay readable in Obsidian and useful for VaERL.

Auxiliary author documents are ingested as supporting source material, not as novel chapters. When present, their source/chunk/extraction artifacts live under `99_System/auxiliary_*`, and their reliable facts can enrich existing primaries or create future/planned primaries with `entity_origin: auxiliary_declared` or `mixed`.

## Directory Layout

```text
00_Project/
01_Voice/
02_World/
  Places/
  Magic/
  Creatures/
  Factions/
  Objects/
  History/
  Lore/
03_Characters/
  Profiles/
04_Story/
  Chapters/
  Chapter_Summaries/
05_Draft/
06_Canon/
07_Editorial/
90_Review/
99_Import_Staging/
99_System/
_Templates/
```

## Canonical Note Roles

Visible and useful roles:

- `primary`
- `chapter`
- `chapter_summary`

Hidden operational role:

- `review`

## Minimum Bootstrap Metadata

Canonical notes should carry enough metadata for Obsidian and VaERL, but no more than needed:

```yaml
---
kind: character
title: Sera
status: pending_revision
schema_version: 1.0
slug: sera
note_role: primary
entity_kind: character
canonical_subject: Serélyne Thiseriya d’Aelwen
aliases:
  - Sera
  - Serelyne
review_state: canonical
confidence: 0.92
evidence_sources:
  - /path/to/source.md
tags:
  - '#primary'
---
```

Recommended fields:

- `kind`
- `title`
- `status`
- `schema_version`
- `slug`
- `note_role`
- `entity_kind`
- `canonical_subject`
- `aliases`
- `review_state`
- `confidence`
- `evidence_sources`
- `tags`

## Hidden Material

Review and staging remain important, but must stay out of the useful graph and out of normal retrieval.

Expected tags:

- review/staging: `#review`
- chapter/chapter_summary: `#chapters`
- system: `#system`
- primary: `#primary`

Expected behavior:

- `90_Review` is for unresolved material
- `99_Import_Staging` is preserved for legacy / explicit review flows and is not the primary bootstrap rail today
- `99_System` is operational output only

## Active Bootstrap Artifact Layout

For the active TextifAI bootstrap rail, the canonical per-run artifact root is:

```text
<vault_root>/99_System/
  source_extraction_audit.json
  provider_snapshot.json
  model_plan_audit.json
  novel_index.json
  global_normalization_pass1.json
  ambiguous_entity_queue.json
  global_normalization_pass2.json
  selective_normalization_trace.jsonl
  selective_normalization_metrics.json
  llm_call_ledger.jsonl
  global_batch_plan_audit.json
  global_normalization.json
  canonical_entity_map.json
  chapter_extraction_audit.json
  chapter_outputs/
    ch_001.json
    ch_002.json
    ...
  chapters_enriched.json
  resolved_entities.json
  entity_clusters_audit.json
  entity_resolution_audit.json
  semantic_context_probe_audit.json
  semantic_context_probe_trace.jsonl
  cleaned_entities.json
  entity_cleanup_audit.json
  promotion_decisions_audit.json
  obsidian_import.json
  e2e_artifact_contract.json
  playbook_boundary_audit.json
  run_limits_audit.json
  run_comparability_manifest.json
  json_import_audit.json
  bootstrap_progress.jsonl
  api_call_traces/
```

These files are operational artifacts for the current run, not durable author-facing source material.

`novel_index.json` is the deterministic metadata index for the source novel. It stores work metadata, chapter IDs, physical order, original titles, title parsing signals, estimated token counts, content hashes, and text handles. It does not depend on an LLM.

`global_normalization_pass1.json` is a metadata-only planner. It identifies dense chapters, structural ambiguities, and selected chapter IDs for expansion.

`ambiguous_entity_queue.json` exposes the ambiguity clusters that should be considered by selective expansion and later entity resolution.

`global_normalization_pass2.json` records the selective LLM expansion result. `global_normalization.json` remains the compatibility artifact and the source for `canonical_entity_map.json`.

`selective_normalization_trace.jsonl` is a chronological JSONL trajectory log for the metadata-first planner and selective expansion. Each line contains `event_type`, `timestamp`, `run_id`, optional `chapter_id`, optional `cluster_id`, `reason`, and `metadata`.

`selective_normalization_metrics.json` aggregates trace-level utility: selected/rejected chapters, selection reason counts, pass2 subcalls, ambiguity counts, and observable-change metrics. A selected chapter is counted as contributing changes only if pass2 entities or merge candidates reference that chapter through `chapter_refs`.

`llm_call_ledger.jsonl` records every LLM call made by the active bootstrap rail. It stores phase, task, provider, model, prompt/input hashes, output hash, status, latency, and token estimates. It is the primary audit trail for checking whether two generative runs are actually comparable.

`run_limits_audit.json` records phase-level execution limits and whether a run is complete or partial. Partial artifacts are valid for debugging but not for semantic-quality comparison.

`run_comparability_manifest.json` records upstream artifact hashes (`global_normalization`, `canonical_entity_map`, `chapter_outputs`), downstream hashes (`resolved_entities`, `cleaned_entities`, `obsidian_import`), prompt hashes, and a `comparable_for_semantic_quality` flag.

`semantic_context_probe_audit.json` and `semantic_context_probe_trace.jsonl` are diagnostic, non-mutating probes over persisted entities and chapters. They surface suspicious contamination signals or merge candidates without changing `cleaned_entities.json` or `obsidian_import.json`.

Chapter extraction records two independent numbering axes:

- `sequence_index`: physical order in the source document
- `title_parse_signals`: deterministic, language-agnostic structural parsing of the title
- `chapter_label_type` and `chapter_number_in_label`: narrative structure expressed by the chapter title

`title_parse_signals` contains `has_explicit_number`, `explicit_number_value`, `has_colon`, `has_em_dash`, `primary_separator`, `prefix_segment`, and `suffix_segment`. It is structural only; semantic label classification remains in `chapter_label_type`. The current parser supports `:` and `—`; it does not treat `-`, `|`, or `·` as structural separators.

`chapter_number_in_label` only captures a number attached to the main title label. Secondary subtitle numbers such as `Parte 2` in an interlude title are not promoted to the main narrative chapter number.

## Retrieval Policy

Normal retrieval should prefer:

1. exact canonical primaries
2. nearby canonical primaries
3. chapter summaries
4. chapters

Review and staging are not normal retrieval targets.

## V1 Constraint

The current V1 should be treated as Markdown-first.

The decisive capability is not “can we ingest every format,” but “can we reliably build canonical primaries from chapter-level structured outputs and merged entities.”
