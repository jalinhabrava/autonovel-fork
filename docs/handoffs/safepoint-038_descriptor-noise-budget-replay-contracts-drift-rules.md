# Descriptor Noise Budget Replay Contracts & Drift Rules

## Scope

Phase 1.3.K-b2 añade contratos de replay provider-free para el fixture `descriptor_noise_budget` y actualiza drift rules con comportamiento observado. No implementa runtime budget global ni toca runtime, schema, viewer, prompts, provider o write-back.

## Files Changed

- `tests/test_textifai_descriptor_noise_budget_replay_contracts.py`
- `tests/fixtures/textifai/semantic_edges/descriptor_noise_budget/expected/replay_drift_expectations.json`
- `tests/fixtures/textifai/semantic_edges/descriptor_noise_budget/expected/README.md`

## Replay Output Observed

Replay provider-free observado en tempdir:

- `review_queue.item_count`: 2
- `descriptor_review_item_count`: 0
- `counts_by_type`:
  - `entity_retention_review`: 1
  - `review_entity`: 1
- `counts_by_severity`:
  - `medium`: 2
- Output actual no emite signals descriptor esperadas para:
  - `el cartógrafo sin memoria`
  - `el capitán del paso`
  - `el protector de Luma`
- Output actual genera:
  - `Luma Ser` como `entity_retention_review` / `review_create_primary`
  - `Ari Mar` como `review_entity` genérico

## Contract Assertions Added

Nuevo test:

- `tests/test_textifai_descriptor_noise_budget_replay_contracts.py`

Cubre:

- shape/boundary provider-free
- required entities or explicit drift
- forbidden primaries
- expected signals or explicit drift
- suppressed cases
- no-explosion / dedupe baseline
- drift expectations explicitness
- anti-hardcode runtime literals

## Required Entities

El test valida que `Ari Mar` y `Luma Ser` aparecen en output. Si no quedan primary/canonical, el comportamiento debe estar declarado como drift explícito.

## Forbidden Primary Assertions

No deben aparecer como primary fuerte:

- `él`
- `mercader distraído`
- `el viajero`
- `el caminante`

Pronoun/noise como primary se considera no negociable.

## Expected Descriptor Signals

Ideales esperados, actualmente registrados como drift porque no aparecen en replay output:

- `el cartógrafo sin memoria` -> `review_enrich_existing_entity`
- `el capitán del paso` -> `review_attach_role_or_title`
- `el protector de Luma` -> `review_enrich_existing_entity`

## Suppressed Cases

Comportamiento observado/resuelto:

- `el viajero`: no primary, no strong review item
- `el caminante`: no medium descriptor review item
- `él`: no primary, no review item
- `mercader distraído`: no primary, no review item

## Dedupe / No-Explosion Assertions

Contratos prudentes:

- `descriptor_review_items <= 6`
- si `medium_descriptor_items > 4`, debe existir drift `descriptor_queue_explosion_risk`
- output actual no tiene explosión; registrado como `descriptor_queue_no_explosion_observed`

## Drift Expectations Updated

`replay_drift_expectations.json` ahora separa:

- `manual_expectation`
- `current_observed_behavior`
- `accepted_temporary_drift`
- `resolved_current_behavior`
- `known_current_drift`
- `non_negotiable_failures`
- `future_desired_behavior`
- `language_agnostic_notes`

## Observed Current Drift

Drifts aceptados temporalmente:

- `descriptor_signal_missing_for_novel_facts`
- `role_descriptor_missing_attach_signal`
- `relationship_descriptor_missing_impact_signal`
- `descriptor_metadata_incomplete`

No se ocultó drift ni se implementó runtime budget.

## Language-Agnostic / Anti-hardcode Checks

El test comprueba que strings del fixture no aparecen como literals runtime en `textifai/vaerl/review_queue.py`:

- `Ari Mar`
- `Luma Ser`
- `el viajero`
- `el caminante`
- `el cartógrafo sin memoria`
- `el capitán del paso`
- `el protector de Luma`
- `él`
- `mercader distraído`
- `el guardián del archivo`
- `el custodio del paso`

## Tests Added / Updated

Added:

- `tests/test_textifai_descriptor_noise_budget_replay_contracts.py`

Updated:

- `tests/fixtures/textifai/semantic_edges/descriptor_noise_budget/expected/replay_drift_expectations.json`
- `tests/fixtures/textifai/semantic_edges/descriptor_noise_budget/expected/README.md`

## Validation Performed

- `uv run python -m unittest -v tests.test_textifai_fixture_harness` ✅
- `uv run python -m unittest -v tests.test_textifai_artifact_contract_snapshots` ✅
- `uv run python -m unittest -v tests.test_textifai_review_queue_retention_signals` ✅
- `uv run python -m unittest -v tests.test_textifai_retention_review_policy` ✅
- `uv run python -m unittest -v tests.test_textifai_replay_expected_drift_rules` ✅
- `uv run python -m unittest -v tests.test_textifai_semantic_edge_fixture_harness` ✅
- `uv run python -m unittest -v tests.test_textifai_semantic_edge_retention_policy` ✅
- `uv run python -m unittest -v tests.test_textifai_semantic_edge_replay_baseline` ✅
- `uv run python -m unittest -v tests.test_textifai_semantic_edge_replay_contracts` ✅
- `uv run python -m unittest -v tests.test_textifai_object_retention_signal_normalization` ✅
- `uv run python -m unittest -v tests.test_textifai_descriptor_role_review_signal_decision` ✅
- `uv run python -m unittest -v tests.test_textifai_descriptor_genericity_policy` ✅
- `uv run python -m unittest -v tests.test_textifai_descriptor_noise_budget_fixture_harness` ✅
- `uv run python -m unittest -v tests.test_textifai_descriptor_noise_budget_replay_baseline` ✅
- `uv run python -m unittest -v tests.test_textifai_descriptor_noise_budget_replay_contracts` ✅
- `uv run python scripts/textifai.py replay-downstream --help` ✅

## Data Written

- Test file y expected docs/drift JSON only.
- Replay outputs solo temporales.
- Sin writes a `runs/**` ni `vault/**`.

## Safety Constraints

- Provider patched to fail.
- Output boundary tempdir-only.
- Sin runtime changes.
- Sin schema changes.
- Sin viewer/write-back.

## Known Limitations

- Drifts de descriptor signal missing quedan aceptados temporalmente.
- No hay budget run-level real todavía.
- Contract no exige signals faltantes como hard fail hasta K-b3/runtime decision.

## Future Extensions

- K-b3 puede implementar budget run-level o ajustar replay/runtime para emitir signals descriptor esperadas.
- Endurecer missing descriptor signals de drift aceptado a failure cuando runtime esté listo.

## Semantic Contract Changes: NO

## Runtime Changes: NO

## Generated Artifacts: Temp-only replay output

## Provider Calls: NO

## Write-back: NO

## Branch

- `phase-1.3-ingestion-vaerl-hardening`

## Next Suggested Phase

- `Phase 1.3.K-b3 — Descriptor Signal Replay Alignment or Runtime Budget Decision`
