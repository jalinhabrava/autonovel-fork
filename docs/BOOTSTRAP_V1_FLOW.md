# Bootstrap V1 Flow

This document describes the active TextifAI bootstrap rail.

Canonical active entrypoints:

- `uv run python scripts/textifai.py init ...`
- `uv run python scripts/textifai_obsidian.py init ...`
- `textifai.obsidian.setup.prepare_obsidian_project()`

Canonical active pipeline module:

- `textifai/import_review/structured_bootstrap_v1.py`

Legacy AutoNovel orchestration (`run_pipeline.py`, `scripts/pipeline/run_pipeline.py`) is outside this rail.

This repository now treats bootstrap as a narrow, auditable pipeline:

1. ingest source documents
2. prefer Markdown as the primary V1 input
3. split long narrative documents into real chapters
4. build deterministic `novel_index.json`
5. run metadata-first global normalization pass 1
6. selectively expand only planned chapters in global normalization pass 2
7. build `canonical_entity_map.json`
8. run one structured LLM extraction per chapter
9. global entity cluster resolution
10. entity cleanup / promotion decisions
11. assemble `obsidian_import.json`
12. import canonical primaries, chapter notes, and chapter summaries into the vault

## Product Direction

The current V1 direction is intentionally simpler than the older staging-heavy flow.

We want:

- chapter-first extraction
- strict JSON outputs
- explicit entity merge passes
- canonical primary notes
- a review bucket for unresolved material
- separate physical chapter order from narrative chapter labels

We do not want:

- language-specific semantic heuristics as the main logic
- oversized bootstrap ontologies
- review material polluting the visible graph
- retrieval depending on weak provisional notes

## Canonical Vault Layers

Visible canonical layers:

- `02_World/Places`
- `02_World/Magic`
- `02_World/Creatures`
- `02_World/Factions`
- `02_World/Objects`
- `02_World/History`
- `02_World/Lore`
- `03_Characters/Profiles`

Story grounding layers:

- `04_Story/Chapters`
- `04_Story/Chapter_Summaries`

Hidden internal layers:

- `90_Review`
- `99_Import_Staging`
- `99_System`

## Note Roles

Minimum note roles:

- `primary`
- `chapter`
- `chapter_summary`
- `review`

Minimum review states:

- `canonical`
- `review`

## Graph And Retrieval Policy

The useful narrative graph should show canonical primaries by default.

These tags are reserved for hiding non-canonical or operational notes:

- `#system`
- `#review`
- `#chapters`

Normal retrieval should prioritize:

1. canonical primary notes
2. closely related canonical primaries
3. chapter summaries
4. chapter notes

Review and staging should only be used in explicit review flows.

## Validation Standard

Every bootstrap iteration should leave auditable artifacts when possible. These artifacts define the **semantic ingestion end-to-end** boundary up to VaERL/vault import readiness; they are not a full product E2E with a free-form user chat evaluation.

- `source_extraction_audit.json`
- `provider_snapshot.json`
- `model_plan_audit.json`
- `novel_index.json`
- `global_normalization_pass1.json`
- `ambiguous_entity_queue.json`
- `global_normalization_pass2.json`
- `selective_normalization_trace.jsonl`
- `selective_normalization_metrics.json`
- `llm_call_ledger.jsonl`
- `global_batch_plan_audit.json`
- `global_normalization.json`
- `chapter_extraction_audit.json`
- `chapter_outputs/*.json`
- `resolved_entities.json`
- `cleaned_entities.json`
- `obsidian_import.json`
- `e2e_artifact_contract.json`
- `playbook_boundary_audit.json`
- `run_limits_audit.json`
- `run_comparability_manifest.json`
- `json_import_audit.json`
- `bootstrap_progress.jsonl`

## Chapter Label Semantics

`sequence_index` is the physical order of appearance in the source document. It must not be reinterpreted from the title.

Each extracted chapter also carries:

- `title_parse_signals`: deterministic, language-agnostic title parsing signals
- `chapter_label_type`: one of `episode`, `prologue`, `epilogue`, `interlude`, `other`
- `chapter_number_in_label`: the explicit number attached to the main narrative label, or `null`

`title_parse_signals` is produced by simple structural parsing before the model sees the chapter. It records whether the title has `:` or `—`, which of those is the primary separator, the prefix/suffix around that separator, and the first explicit integer if present. It does not translate, normalize, classify, or use language-specific word lists. `-`, `|`, and `·` are not structural separators in this iteration.

The LLM uses `chapter_title_original` plus `title_parse_signals` for the minimal semantic classification into `chapter_label_type` and `chapter_number_in_label`.

For titles such as `Interludio: Ausencias que informan Parte 2`, TextifAI records `chapter_label_type = "interlude"` and `chapter_number_in_label = null`. The `Parte 2` number is treated as a secondary subtitle segment, not as the main narrative chapter number.

Product E2E starts after this point: import the novel, build the vault/VaERL, ask free-form user questions, and evaluate whether the answers are useful in real use.

## Metadata-First Global Normalization

The active bootstrap rail uses a simple metadata-first + selective expansion strategy inspired by recursive long-context processing:

- `novel_index.json` is deterministic and LLM-free.
- `global_normalization_pass1.json` plans dense or ambiguous chapters from metadata only.
- `ambiguous_entity_queue.json` makes ambiguity explicit instead of hiding it in prose.
- `global_normalization_pass2.json` records the selected chapters expanded with the LLM.
- `selective_normalization_trace.jsonl` records chronological planner/pass2 trajectory events.
- `selective_normalization_metrics.json` summarizes selection counts, pass2 completion, and observable utility.
- `global_normalization.json` remains the stable downstream frontier consumed by `canonical_entity_map.json`.

This is intentionally not a recursive framework. The source text remains an external indexed object, pass 1 plans from metadata, and pass 2 expands only the selected chapter texts.

Observable pass2 utility is counted conservatively: a selected chapter contributes only when pass2 global entities or merge candidates reference that chapter ID through `chapter_refs`. This distinguishes completed subcalls from subcalls with no visible normalization impact.

## Reproducibility Artifacts

TextifAI treats long-context ingestion as an auditable execution, not just a sequence of prompts. Runs persist:

- `llm_call_ledger.jsonl`: one JSON line per LLM call with phase, task, provider, model, prompt/input hash, output hash, status, latency, and token estimates.
- `run_limits_audit.json`: phase limits and whether the run is `complete` or `partial`; partial runs are valid for debugging but not semantic-quality comparison.
- `run_comparability_manifest.json`: upstream and downstream artifact hashes plus prompt hashes, so replay runs can be compared only when their frozen inputs match.
- `semantic_invariants_audit.json`: Phase 1 VaERL quality gates over chapter integrity, required primaries, slug uniqueness within kind, cross-kind ontological collisions, duplicate names, language consistency, auxiliary extraction integrity, and optional vault wikilinks/placeholders.
- `semantic_context_probe_audit.json` and `semantic_context_probe_trace.jsonl`: diagnostic probes over persisted VaERL artifacts. These are non-mutating and exist to surface contamination or merge candidates.

Downstream replay reuses frozen upstream artifacts and regenerates only entity resolution, cleanup, assembly, and import artifacts:

```bash
uv run python scripts/textifai.py replay-downstream \
  --input-system runs/semantic_ingestion_e2e/replay_fixtures/ont_20chapters_language_fix_v6/99_System \
  --output-root runs/semantic_ingestion_e2e/replay_entity_resolution_v1 \
  --language es
```

`replay-semantic` remains available as a compatibility alias for the same downstream replay behavior.

Run Phase 1 invariants manually against any generated run:

```bash
uv run python scripts/textifai.py validate-vaerl \
  --system-root runs/semantic_ingestion_e2e/replay_entity_resolution_v19_aux_hints/99_System \
  --vault-root runs/semantic_ingestion_e2e/replay_entity_resolution_v19_aux_hints_vault \
  --required-primary Ren \
  --required-primary Sera \
  --language es
```

Replay can also ingest auxiliary author documents without rerunning the frozen novel extraction. Auxiliary documents use a separate rail:

- `auxiliary_source_index.json`: document inventory with path, title fallback, optional author hint status, hashes, and size metadata.
- `auxiliary_chunks/*.json`: deterministic chunks built from markdown headings or paragraph windows.
- `auxiliary_extractions/*.json`: LLM extraction per auxiliary chunk.
- `auxiliary_enrichment_audit.json`: created/enriched entities, planned relationships, unresolved endpoints, and extraction errors.

Author hints are optional. If the author leaves the hint blank, the document title/filename is used as fallback context, but clear facts in the content can still enrich or create primary entities.

```bash
AUTONOVEL_BOOTSTRAP_PROVIDER=openai AUTONOVEL_BOOTSTRAP_MODEL=gpt-4.1-mini \
  uv run python scripts/textifai.py replay-downstream \
  --input-system runs/semantic_ingestion_e2e/replay_fixtures/ont_20chapters_language_fix_v6/99_System \
  --output-root runs/semantic_ingestion_e2e/replay_entity_resolution_aux \
  --language es \
  --auxiliary-document /path/to/characters.md \
  --auxiliary-hint "/path/to/characters.md=documento de fichas de personajes presentes y futuros"
```

## Local Semantic Ingestion Runs

Use `runs/semantic_ingestion_e2e/<run-name>/` for local persisted runs that exercise the playbook boundaries without committing generated vault content.

Example:

```bash
TEXTIFAI_BOOTSTRAP_MAX_CHAPTERS=20 AUTONOVEL_BOOTSTRAP_PROVIDER=openai AUTONOVEL_BOOTSTRAP_MODEL=auto \
  uv run python scripts/textifai.py init \
  --vault-root runs/semantic_ingestion_e2e/ont_20chapters \
  --source-root /path/to/source \
  --project-title "Semantic Ingest 20 Chapters" \
  --skip-plugin-install
```

## Current Honest Constraint

The repository already supports chapter-first bootstrap structure, but retrieval and higher-level interpretation still have to coexist with:

- durable vault markdown as the long-term source of truth
- bridge snapshots for strong grounding
- legacy staging/review modules that remain available but are no longer the primary bootstrap rail
