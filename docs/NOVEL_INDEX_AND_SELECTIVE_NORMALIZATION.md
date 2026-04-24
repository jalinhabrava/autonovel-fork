# Novel Index And Selective Normalization

This document describes the incremental metadata-first layer in the active TextifAI semantic ingestion rail.

## Purpose

The pipeline avoids treating the entire novel as raw prompt context for global normalization. Instead, it builds a deterministic index, plans from metadata, and expands only selected chapter text.

The design keeps the existing boundaries intact:

- `global_normalization.json`
- `canonical_entity_map.json`
- `chapter_outputs/*.json`
- `resolved_entities.json`
- `cleaned_entities.json`
- `obsidian_import.json`

## Artifacts

`novel_index.json`

- Deterministic and LLM-free.
- Contains work metadata and one row per chapter.
- Stores `chapter_id`, `sequence_index`, title fields, `title_parse_signals`, estimated token count, content hash, and `text_path`.

`global_normalization_pass1.json`

- Deterministic metadata-only planner.
- Identifies dense chapters, ambiguity clusters, and selected chapters for expansion.
- Does not inspect full chapter text.

`ambiguous_entity_queue.json`

- JSON projection of pass 1 ambiguity clusters.
- Keeps ambiguity explicit for selective expansion and downstream diagnosis.

`global_normalization_pass2.json`

- Records the selective LLM expansion result.
- Includes selected chapter IDs, expanded chapter IDs, entity count, merge plan count, entities, and merge plan.

`selective_normalization_trace.jsonl`

- Chronological JSONL trajectory log.
- Records planner start/finish, selected/rejected chapters, ambiguity clusters, pass2 subcall start/completion/failure, merge, and finish events.
- Uses short comparable reasons such as `dense_named_entities`, `reused_explicit_number`, `repeated_prefix_segment`, `ambiguous_title_signals`, `selected_for_manual_threshold`, and `not_selected_low_signal`.

`selective_normalization_metrics.json`

- Aggregates selection counts, rejection counts, reason counts, pass2 subcall counts, and utility metrics.
- Separates completed pass2 work from observable semantic impact.
- Counts a selected chapter as contributing only when pass2 entities or merge candidates reference the chapter through `chapter_refs`.

`global_normalization.json`

- Compatibility frontier consumed by `canonical_entity_map.json`.
- Remains the stable artifact for downstream phases.

## Selection Policy

Pass 1 selects chapters from:

- chapters with high token density
- chapters participating in structural ambiguity clusters
- fallback highest-density chapters until the configured minimum is reached
- high narrative value chapters near the later part of the selected range when they have structural title signals

The planner is intentionally simple and auditable. It does not use language-specific word lists, recursive hidden calls, or opaque scoring.

`high_narrative_value` is a structured selection reason. It is intended to catch late chapters that may carry payoff, reveal, or conflict information even when they are not the densest chapters by token count. It is still metadata-only and language-agnostic.

## Observable Change Rule

Pass 2 is considered to have produced observable changes when the merged global normalization contains entity candidates or merge candidates with `chapter_refs` pointing to selected chapters.

The metrics also count:

- changed candidate entities
- alias candidates
- review candidates
- canonical candidates

These metrics are not a final quality score. They are a debugging signal for whether selective expansion produced visible normalization material or merely consumed API calls.

## Primary Stability Guardrails

Entity resolution and cleanup may annotate entities with:

- `strong_primary_candidate`
- `gender_presentation_signal`

`strong_primary_candidate` is set for proper-name entities with repeated chapter coverage. Cleanup uses it as a promotion-stability boost so recurring protagonists do not fall to review solely because the resolver still marks them as uncertain.

`gender_presentation_signal` can be `masculine`, `feminine`, `unknown`, or `mixed`. It is optional and must be treated as a soft feature, not as a hard identity rule. The resolver uses clear mismatches only to reduce alias-sharing or merge confidence when the overlap comes from descriptor-like evidence rather than the named identity itself.

## Scope

This layer prepares global normalization. It does not redesign:

- chapter splitting
- chapter extraction
- entity resolution
- entity cleanup
- Obsidian import
- VaERL materialization
