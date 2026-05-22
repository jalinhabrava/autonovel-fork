# Descriptor Signal Replay Alignment Diagnostics

## Product Reading

Problema actual no es exceso de alertas. Problema actual es pérdida de alertas narrativas útiles. Fixture `descriptor_noise_budget` muestra que TextifAI absorbe descriptores relevantes dentro de `Ari Mar`, pero no los convierte en señales editoriales accionables. Esta fase deja fallo localizado y medible. No abre ruido. No permite auto-merge. No permite auto-promotion.

## Scope

Diagnóstico replay provider-free para `descriptor_noise_budget`. Tests y drift explícito. Sin cambios runtime. Sin schema. Sin viewer. Sin write-back.

## Files Changed

- `tests/test_textifai_descriptor_signal_replay_alignment_diagnostics.py`
- `tests/fixtures/textifai/semantic_edges/descriptor_noise_budget/expected/replay_drift_expectations.json`
- `tests/fixtures/textifai/semantic_edges/descriptor_noise_budget/expected/README.md`

## Diagnostic Questions Answered

- `Ari Mar` existe, pero queda en `review_entity`, no primary usable.
- Descriptores relevantes sí llegan al replay input.
- Descriptores relevantes sobreviven como aliases/source mentions absorbidos.
- `review_queue.json` no emite items descriptor dedicados.
- Drift de señales faltantes queda explícito.
- Suppression de ruido sigue estable.

## Candidate State Diagnosis

- `Ari Mar` aparece top-level con `review_state=review`.
- `note_role=review`.
- `strong_primary_candidate=false`.
- `review_reason_code=weak_or_descriptive_naming`.
- `semantic_invariants_audit.json` reporta `primary_count=0`, `review_count=1`.
- `promotion_decisions_audit.json` deja decisión `review`.

Diagnóstico: estado de candidato probablemente bloquea signal descriptor útil.

## Descriptor Surface Propagation

Surfaces relevantes:

- `el cartógrafo sin memoria`
- `el capitán del paso`
- `el protector de Luma`

Hallazgo:

- están en replay input;
- quedan absorbidas en aliases/source mentions de `Ari Mar`;
- no generan `review_queue` item dedicado;
- no desaparecen por completo;
- pérdida ocurre en transición hacia review signal, no en input.

## Metadata Presence

Input conserva metadata estructural:

- `surface_type`
- `semantic_value`
- `descriptor_category`
- `language_hint`
- `key_facts`
- `chapter_refs`
- `source_mentions`
- `canonical_candidate`

Output actual:

- `review_entity` de `Ari Mar` no trae bundle moderno descriptor;
- faltan `surface_type`, `semantic_value`, `descriptor_category`, `future_viewer_actions`, `do_not_auto_merge`.

## Missing Signal Drift

Se mantiene drift explícito para:

- `descriptor_signal_missing_for_novel_facts`
- `role_descriptor_missing_attach_signal`
- `relationship_descriptor_missing_impact_signal`
- `candidate_state_blocks_descriptor_signal`
- `descriptor_surface_metadata_not_retained`

## Suppression Regression

Sigue correcto:

- `el viajero`
- `el caminante`
- `él`
- `mercader distraído`

No aparecen como primary fuerte ni como signals descriptor fuertes.

## Anti-hardcode / Language-Agnostic Guardrails

- test estático verifica que literals de fixture no aparecen en `textifai/vaerl/review_queue.py`;
- drift IDs no aparecen en runtime;
- diagnóstico depende de metadata y estado observado, no de reglas con strings del fixture.

## Tests Added / Updated

- Nuevo: `tests/test_textifai_descriptor_signal_replay_alignment_diagnostics.py`
- Actualizado: `tests/fixtures/textifai/semantic_edges/descriptor_noise_budget/expected/replay_drift_expectations.json`
- Actualizado: `tests/fixtures/textifai/semantic_edges/descriptor_noise_budget/expected/README.md`

## Validation Performed

- `uv run python -m unittest -v tests.test_textifai_fixture_harness`
- `uv run python -m unittest -v tests.test_textifai_artifact_contract_snapshots`
- `uv run python -m unittest -v tests.test_textifai_review_queue_retention_signals`
- `uv run python -m unittest -v tests.test_textifai_retention_review_policy`
- `uv run python -m unittest -v tests.test_textifai_replay_expected_drift_rules`
- `uv run python -m unittest -v tests.test_textifai_semantic_edge_fixture_harness`
- `uv run python -m unittest -v tests.test_textifai_semantic_edge_retention_policy`
- `uv run python -m unittest -v tests.test_textifai_semantic_edge_replay_baseline`
- `uv run python -m unittest -v tests.test_textifai_semantic_edge_replay_contracts`
- `uv run python -m unittest -v tests.test_textifai_object_retention_signal_normalization`
- `uv run python -m unittest -v tests.test_textifai_descriptor_role_review_signal_decision`
- `uv run python -m unittest -v tests.test_textifai_descriptor_genericity_policy`
- `uv run python -m unittest -v tests.test_textifai_descriptor_noise_budget_fixture_harness`
- `uv run python -m unittest -v tests.test_textifai_descriptor_noise_budget_replay_baseline`
- `uv run python -m unittest -v tests.test_textifai_descriptor_noise_budget_replay_contracts`
- `uv run python -m unittest -v tests.test_textifai_descriptor_signal_replay_alignment_diagnostics`
- `uv run python scripts/textifai.py replay-downstream --help`

## Data Written

Solo archivos versionados de tests/docs. Replay output generado solo en `TemporaryDirectory`.

## Safety Constraints

- Runtime changes: NO
- Semantic contract changes: NO
- Provider calls: NO
- Write-back: NO
- Generated artifacts: Temp-only replay output

## Known Limitations

- No prueba todavía cambio runtime.
- No confirma ruta exacta interna que descarta signal descriptor.
- No resuelve si bloqueo está en candidate-state acceptance o en metadata propagation final; deja ambos visibles.

## Future Extensions

- fase siguiente debe probar alineación mínima runtime para permitir signals descriptor con evidencia fuerte aun si candidate sigue en `review_entity`;
- mantener suppression actual para genéricos/pronombres/ruido.

## Semantic Contract Changes: NO

## Runtime Changes: NO

## Generated Artifacts: Temp-only replay output

## Provider Calls: NO

## Write-back: NO

## Branch

`phase-1.3-ingestion-vaerl-hardening`

## Next Suggested Phase

`Phase 1.3.K-b3b — Descriptor Signal Runtime Alignment for Review-State Candidates`
