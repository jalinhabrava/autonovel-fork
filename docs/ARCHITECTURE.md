# TextifAI Architecture

This document describes the system as it exists today.

It is intentionally lower-level than `README.md` and more implementation-focused than `docs/TEXTIFAI_SEMANTIC_STORY_ENGINE_ROADMAP.md`.

- `README.md`: product-level entrypoint.
- `docs/TEXTIFAI_SEMANTIC_STORY_ENGINE_ROADMAP.md`: technical-product direction and phase roadmap.
- `docs/ARCHITECTURE.md`: current modules, entrypoints, artifacts, and debugging map.

## 1. Active Rails

### 1.1 Active TextifAI Rail

Preferred entrypoints:

```bash
uv run python scripts/textifai.py start
uv run python scripts/textifai.py init --vault-root <vault> --source-root <source>
uv run python scripts/textifai.py replay-downstream --input-system <run>/99_System --output-root <new-run>
uv run python scripts/textifai.py validate-vaerl --system-root <run>/99_System
```

Compatibility entrypoint:

```bash
uv run python scripts/textifai_obsidian.py inspect --vault-root <vault>
```

Main modules:

- `textifai/obsidian/cli.py`
- `textifai/obsidian/setup.py`
- `textifai/import_review/structured_bootstrap_v1.py`
- `textifai/obsidian/json_import.py`

### 1.2 Legacy AutoNovel Rail

Legacy entrypoints:

```bash
uv run python run_pipeline.py --from-scratch
uv run python scripts/pipeline/run_pipeline.py
```

Legacy modules:

- `scripts/foundation/`
- `scripts/drafting/`
- `scripts/revision/`
- `PIPELINE.md`
- `WORKFLOW.md`

These remain for historical reference and possible reuse, but they are not the active TextifAI narrative bootstrap rail.

## 2. Core Concepts

### 2.1 ECC

ECC is the editorial/context understanding layer. It interprets author input or author material into structured intent, task, or context signals.

Relevant areas:

- `textifai/author_understanding/`
- `textifai/editorial_intent/`
- `textifai/editorial/`
- `textifai/conversation/`

ECC should understand the request. It should not become the canon source.

### 2.2 VaERL

VaERL is the Vault-aware Entity Resolution Layer.

Relevant areas:

- `textifai/vaerl/`
- `textifai/import_review/entity_cluster_resolution.py`
- `textifai/import_review/entity_cleanup.py`
- `textifai/import_review/entity_reconciliation.py`
- `textifai/import_review/primary_note_synthesis.py`
- `textifai/vaerl/invariants.py`

VaERL resolves mentions, entities, aliases, slugs, relationships, review states, and semantic invariants.

## 3. Active Semantic Ingestion Pipeline

The active bootstrap/import pipeline is orchestrated by:

- `textifai/import_review/structured_bootstrap_v1.py`

Current phase order:

1. source inventory / source reading
2. primary novel document selection
3. chapter detection
4. deterministic `novel_index.json`
5. metadata-first `global_normalization_pass1.json`
6. `ambiguous_entity_queue.json`
7. selective expansion into `global_normalization_pass2.json`
8. compatibility `global_normalization.json`
9. `canonical_entity_map.json`
10. chapter extraction into `chapter_outputs/*.json`
11. entity resolution
12. entity cleanup / promotion decisions
13. pre-VaERL reconciliation
14. optional auxiliary document ingestion during replay
15. primary note synthesis
16. `obsidian_import.json` assembly
17. semantic invariants audit
18. Obsidian/vault materialization

## 4. Source And Chapter Handling

Source reader:

- `textifai/bootstrap/source_reader.py`

Chapterizer:

- `textifai/import_review/chapterizer.py`

Important chapter fields:

- `chapter_id`
- `sequence_index`
- `chapter_title_original`
- `chapter_title_canonical`
- `chapter_label_type`
- `chapter_number_in_label`
- `title_parse_signals`

`sequence_index` is physical source order. It must not be renumbered from narrative titles.

`title_parse_signals` is deterministic and language-agnostic. It supports `:` and `—` as structural separators.

## 5. LLM Provider Layer

Provider abstraction:

- `providers/text_provider.py`

Bootstrap model/provider selection:

- `textifai/import_review/model_router.py`
- `textifai/import_review/model_registry.py`
- `textifai/import_review/model_advisor.py`
- `textifai/import_review/provider_snapshot.py`

Important runtime environment variables:

- `AUTONOVEL_BOOTSTRAP_PROVIDER`
- `AUTONOVEL_BOOTSTRAP_MODEL`
- `TEXTIFAI_BOOTSTRAP_MAX_CHAPTERS`

Despite the historical `AUTONOVEL_*` names, these still configure the active TextifAI bootstrap provider path today.

## 6. Global Normalization

Main functions live in:

- `textifai/import_review/structured_bootstrap_v1.py`

Relevant artifacts:

- `novel_index.json`
- `global_normalization_pass1.json`
- `ambiguous_entity_queue.json`
- `global_normalization_pass2.json`
- `global_normalization.json`
- `canonical_entity_map.json`
- `selective_normalization_trace.jsonl`
- `selective_normalization_metrics.json`
- `llm_call_ledger.jsonl`

Design:

- metadata-first planning is deterministic where possible
- pass 2 expands selected chapters only
- `global_normalization.json` remains the compatibility frontier for downstream phases

## 7. Chapter Extraction

Main functions:

- `_run_chapter_extraction(...)`
- `_normalize_chapter_payload(...)`
- `_validate_chapter_extraction_payload(...)`
- `_extract_title_parse_signals(...)`

Output:

- `chapter_outputs/ch_001.json`
- `chapter_extraction_audit.json`

Debug here when:

- a chapter output is missing
- schema validation fails
- title parsing fields are missing
- generated prose violates `WORK_LANGUAGE`
- protagonist or chapter-local entity facts are absent before resolution

## 8. Entity Resolution And Cleanup

Resolution:

- `textifai/import_review/entity_cluster_resolution.py`

Cleanup:

- `textifai/import_review/entity_cleanup.py`

Reconciliation:

- `textifai/import_review/entity_reconciliation.py`

Primary note synthesis:

- `textifai/import_review/primary_note_synthesis.py`

Artifacts:

- `resolved_entities.json`
- `entity_clusters_audit.json`
- `entity_resolution_audit.json`
- `cleaned_entities.json`
- `entity_cleanup_audit.json`
- `promotion_decisions_audit.json`
- `pre_vaerl_reconciliation_audit.json`
- `primary_note_synthesis_audit.json`
- `obsidian_relationship_reconciliation_audit.json`
- `review_queue.json`
- `gender_signal_audit.json`
- `semantic_context_probe_audit.json`
- `semantic_context_probe_trace.jsonl`

Debug here when:

- a primary falls to review
- aliases contaminate another primary
- a descriptor becomes canonical over a proper name
- review queue grows with obvious duplicates
- relationships point to aliases instead of primaries
- cross-kind collisions need author review

## 9. Auxiliary Document Ingestion

Auxiliary ingestion module:

- `textifai/import_review/auxiliary_ingestion.py`

CLI usage:

```bash
uv run python scripts/textifai.py replay-downstream \
  --input-system <frozen-run>/99_System \
  --output-root <new-run> \
  --language es \
  --auxiliary-document /path/to/characters.md \
  --auxiliary-hint "/path/to/characters.md=documento de fichas de personajes presentes y futuros"
```

Artifacts:

- `auxiliary_source_index.json`
- `auxiliary_chunks/*.json`
- `auxiliary_extractions/*.json`
- `auxiliary_enrichment_audit.json`

Policy:

- auxiliary docs are not novel chapters
- author hints are recommended
- missing hints fall back to document title/filename
- clear facts can still enrich VaERL without hints
- hints improve precision and reduce graph inflation

## 10. Assembly And Vault Import

Assembly function:

- `assemble_obsidian_import(...)` in `textifai/import_review/structured_bootstrap_v1.py`

Vault importer:

- `textifai/obsidian/json_import.py`

Main output:

- `obsidian_import.json`
- materialized Markdown vault
- `json_import_audit.json`

Important linking policy:

- `preferred_slug` is the internal link target
- Markdown wikilinks should use slug targets
- `canonical_name` is display/canon naming
- empty placeholder notes should not be generated

## 11. Semantic Invariants

Invariant module:

- `textifai/vaerl/invariants.py`

CLI:

```bash
uv run python scripts/textifai.py validate-vaerl \
  --system-root <run>/99_System \
  --vault-root <materialized-vault> \
  --required-primary Ren \
  --required-primary Sera \
  --max-unlinked-primary-mentions 0
```

Artifact:

- `semantic_invariants_audit.json`

Current checks:

- `obsidian_import.json` exists
- chapter integrity is complete
- required primaries exist
- primary/review counts are within configured gates
- `preferred_slug` is present and unique within the same entity kind
- cross-kind same-name collisions are surfaced as `ontological_name_collisions`
- exact duplicate canonicals are rejected
- near-duplicates are warnings
- relationship targets should resolve to a primary through canonical name, slug, alias, or source mention
- primary summaries/facts that mention another primary without a graph relationship are surfaced as `unlinked_primary_mentions`
- primary entities with no facts, refs, or relationships are surfaced as `suspicious_orphan_primaries`
- descriptor/pronoun canonicals are surfaced when a stronger specific alias is available
- `obsidian_relationship_reconciliation_audit.json` records late links added after chapter-derived relationship enrichment
- `review_queue.json` converts unresolved or uncertain semantic state into author-actionable work items
- semantic prose respects work language
- required Phase 1 artifacts exist
- auxiliary extraction has no errors
- optional vault placeholders/wikilinks checks pass

`ontological_name_collisions` are warnings, not hard failures. They cover cases such as "Báculo" as object/concept/person/title, or "La Corona" as institution/title/person.

## 12. E2E Diagnostic Boundaries

Current semantic ingestion boundaries:

1. `novel_index`
2. `global_normalization_pass1`
3. `ambiguous_entity_queue`
4. `global_normalization_pass2`
5. `global_normalization`
6. `chapter_extraction`
7. `entity_resolution`
8. `entity_cleanup`
9. `obsidian_import`

See:

- `docs/e2e_semantic_diagnosis_rules.md`
- `docs/BOOTSTRAP_V1_FLOW.md`

## 13. Replay And Comparability

Replay command:

```bash
uv run python scripts/textifai.py replay-downstream \
  --input-system runs/semantic_ingestion_e2e/replay_fixtures/ont_20chapters_language_fix_v6/99_System \
  --output-root runs/semantic_ingestion_e2e/replay_entity_resolution_v1 \
  --language es
```

Replay freezes:

- `global_normalization.json`
- `chapter_outputs/`
- `chapter_extraction_audit.json`

Replay regenerates:

- `resolved_entities.json`
- `cleaned_entities.json`
- `obsidian_import.json`
- downstream audits

Use replay when iterating on VaERL quality without paying for novel extraction again.

## 14. Where To Debug

| Problem | First place to inspect |
| --- | --- |
| Chapter missing | `chapter_extraction_audit.json` |
| Bad chapter title structure | `chapter_outputs/*.json` |
| Prose in wrong language | boundary artifact where prose first appears |
| Primary missing | `resolved_entities.json`, then `cleaned_entities.json` |
| Descriptor primary | `promotion_decisions_audit.json` |
| Alias contamination | `entity_clusters_audit.json`, `semantic_context_probe_audit.json` |
| Relationship points to alias | `pre_vaerl_reconciliation_audit.json` |
| Aux doc failed | `auxiliary_enrichment_audit.json` and `auxiliary_extractions/*.error.json` |
| Broken wikilink | `semantic_invariants_audit.json`, then `obsidian_import.json` |
| Ontological collision | `semantic_invariants_audit.json` |

## 15. Historical Notes

The repository still includes legacy AutoNovel files. They should be treated as historical or reusable material, not as the active TextifAI orchestration path.
