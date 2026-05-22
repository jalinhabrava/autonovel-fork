# Bootstrap Prompt/Schema Hardening Minimal Contract

## Product Reading

`safepoint-050` validó una respuesta real/manual de ChatGPT contra un prompt real capturado del pipeline activo. La respuesta fue útil, pero expuso deuda real en el contrato: objetos sin sitio propio, mapa canónico vacío, relaciones rígidas y eventos densos comprimidos. Esta fase endurece el contrato mínimo antes de auditar chunking.

## Scope

- Endurecer prompt/schema de bootstrap extraction.
- Añadir compat layer mínimo para outputs v1/v2.
- Añadir tests provider-free.
- No hacer re-audit ChatGPT.
- No tocar chunking, provider real, viewer, runs ni vault.

## Files Changed

- `textifai/import_review/structured_bootstrap_v1.py`
- `tests/test_textifai_bootstrap_prompt_schema_hardening.py`
- `docs/handoffs/safepoint-051_bootstrap-prompt-schema-hardening-minimal-contract.md`

## Problems Addressed

- `empty_canonical_entity_map_in_capture`
- `chapter_schema_missing_objects_section`
- `global_prompt_entire_novel_wording_conflict`
- `relation_type_taxonomy_too_narrow`
- `event_cap_may_be_too_low_for_dense_chapters`
- `chapter_prompt_needs_empty_map_mode`
- `artifact_retention_not_first_class`

## Objects First-class

Chapter extraction prompt now includes `objects` with fields for `object_subkind`, `retention_reason`, `relationships`, `needs_review`, and review metadata. Rules state durable artifacts/tools/weapons/catalysts/keys belong in `objects`, not `concepts`.

## Empty Canonical Map Mode

Chapter prompt now includes `CANONICAL_MAP_MODE`: if canonical map is empty/incomplete, the model must extract strong local candidates, avoid canon approval, mark uncertainty, and never auto-merge or auto-promote.

## Global Normalization Wording

Global prompt now frames work as incremental global normalization over available batch evidence. It distinguishes `NOVEL_INDEX_METADATA` as structure/navigation only and prevents fact claims outside `BATCH_SCOPE`.

## Abstract Relation Model

Chapter schema now describes two-layer relation output:
- broad `relation_category`;
- free short `relation_label`;
- `evidence`, `relation_summary`, facts, review fields.

Legacy `relation_type` remains supported for compatibility.

## Event Priority Policy

Chapter schema now includes `event_importance: major|supporting|local` and prompt rules avoid a hard cap of three events in dense chapters while still discouraging micro-actions.

## Concept / Object / Event Boundaries

Prompt now defines boundaries:
- characters = durable actors;
- places = location-like settings/institutions;
- objects = artifacts/weapons/tools/catalysts/keys/persistent props;
- concepts = systems/laws/roles/doctrines/magic mechanics;
- events = durable changes/historical incidents/turning points.

## Schema Versioning / Compatibility

Normalizer now accepts:
- v1 output with no `objects`;
- v2 output with `objects`;
- legacy `relation_type`;
- v2 `relation_category` + `relation_label`.

Missing schema version defaults to `v1`; top-level or chapter-level `chapter_extraction_schema_version` is tolerated.

## Downstream Compatibility

`extract_local_entity_mentions` now includes `objects`. `chapter_relation_to_entity_relation` maps v2 relation category/label into a legacy relation type string for existing downstream flows. Existing structured bootstrap artifact test still passes.

## Tests Added / Updated

Added:
- `tests/test_textifai_bootstrap_prompt_schema_hardening.py`

Covers prompt wording, objects, empty canonical map mode, relation model, event policy, boundaries, global batch wording, v1/v2 normalizer compatibility, and no provider execution.

## Validation Performed

- `uv run python -m unittest -v tests.test_textifai_bootstrap_prompt_schema_hardening`
- `uv run python -m unittest -v tests.test_textifai_real_bootstrap_chatgpt_response_audit`
- `uv run python -m unittest -v tests.test_textifai_real_bootstrap_prompt_capture_harness`
- `uv run python -m unittest -v tests.test_textifai_structured_bootstrap_v1.StructuredBootstrapV1Tests.test_run_structured_bootstrap_v1_writes_json_artifacts`
- `uv run python scripts/textifai.py init --help`
- `uv run python scripts/textifai.py replay-downstream --help`
- `git status --short`
- `git diff --stat`

## Data Written

Only code/test/handoff files. No generated prompt captures. No novel source text.

## Safety Constraints

- No provider calls.
- No network.
- No write-back.
- No chunking implementation.
- No real `runs/**` or `vault/**` writes.

## Known Limitations

- This is contract hardening, not a new model-response re-audit.
- Downstream object rendering/mapping may need deeper work in later phase.
- Relation category/label compatibility maps to legacy strings for now.

## Future Re-audit Plan

M-b5b should capture a new real prompt with this contract, ask ChatGPT for response, and compare against `safepoint-050` baseline. Expected checks: object artifact retained in `objects`, local candidates/review state improved, relations more expressive, dense events retained with priority.

## Runtime Changes

Limited to prompt/schema wording and normalizer compatibility in `structured_bootstrap_v1.py`.

## Provider Calls

None.

## Write-back

None.

## Branch

`phase-1.3-ingestion-vaerl-hardening`

## Next Suggested Phase

Phase 1.3.M-b5b — Re-audit real captured prompt after prompt/schema hardening.
