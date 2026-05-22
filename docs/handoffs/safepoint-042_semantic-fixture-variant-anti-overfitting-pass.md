# Semantic Fixture Variant Anti-Overfitting Pass

## Product Reading
TextifAI ya genera señales útiles alrededor de entidades en review y ya reduce señales equivalentes para evitar duplicados en la review queue. En esta fase no se agregan features visibles: se valida generalización con una variante sintética para confirmar que el comportamiento responde a metadata semántica y evidencia, no a strings concretas del fixture base. No hay merge automático, promotion automática, write-back ni mutación de canon.

## Scope
- Crear fixture variante ligera `replay_input`-only para anti-overfitting.
- Añadir tests de harness, baseline y contratos sobre la variante.
- No modificar runtime (`textifai/vaerl/review_queue.py` intacto).
- No cambiar schema ni viewer.

## Files Changed
- `tests/fixtures/textifai/semantic_edges/descriptor_noise_budget_variant/README.md`
- `tests/fixtures/textifai/semantic_edges/descriptor_noise_budget_variant/fixture_manifest.json`
- `tests/fixtures/textifai/semantic_edges/descriptor_noise_budget_variant/expected/README.md`
- `tests/fixtures/textifai/semantic_edges/descriptor_noise_budget_variant/expected/replay_drift_expectations.json`
- `tests/fixtures/textifai/semantic_edges/descriptor_noise_budget_variant/replay_input/README.md`
- `tests/fixtures/textifai/semantic_edges/descriptor_noise_budget_variant/replay_input/global_normalization.json`
- `tests/fixtures/textifai/semantic_edges/descriptor_noise_budget_variant/replay_input/chapter_outputs/ch_001.json`
- `tests/fixtures/textifai/semantic_edges/descriptor_noise_budget_variant/replay_input/chapter_outputs/ch_002.json`
- `tests/fixtures/textifai/semantic_edges/descriptor_noise_budget_variant/replay_input/chapter_outputs/ch_003.json`
- `tests/test_textifai_descriptor_noise_budget_variant_fixture_harness.py`
- `tests/test_textifai_descriptor_noise_budget_variant_replay_baseline.py`
- `tests/test_textifai_descriptor_noise_budget_variant_replay_contracts.py`

## Variant Fixture Created
Se creó `descriptor_noise_budget_variant` como fixture sintético ligero sin `source/` completo. La variante congela input replay manual y mantiene intención semántica de la policy base con nombres y surfaces distintas.

## Variant Design
- Canonical candidata en review: `Iven Ral`.
- Entidad secundaria: `Sora Niv`.
- Señales útiles esperadas:
  - `el trazador del umbral` -> `review_enrich_existing_entity`
  - `la voz del peaje` -> `review_attach_role_or_title`
  - `el amparo de Sora` -> enriquecimiento/relación
- Suppression esperada:
  - `el forastero`
  - `el centinela`
  - `ella`
  - `vendedor ausente`
- Equivalentes de rol para dedupe/degrade:
  - `la voz del peaje`
  - `el custodio del pórtico`
  - `el guarda del arco`

## Replay Input Created
Se añadió replay input manual congelado con:
- `global_normalization.json`
- `chapter_outputs/ch_001.json`
- `chapter_outputs/ch_002.json`
- `chapter_outputs/ch_003.json`

No hay provider calls ni artifacts generados persistidos fuera del fixture.

## Anti-Overfitting Criteria
PASS:
- Mismo tipo de comportamiento semántico con nombres/surfaces nuevas.
- Runtime sin literals de variante como condición.
- Tests basados en metadata/evidence/candidate state.

FAIL:
- Dependencia de strings del fixture base o variante.
- Pérdida de señales útiles solo por renombrar surfaces.
- Ruido/promoción automática inesperados.

## Behavior Preserved
Contratos de la variante conservan comportamiento de clase:
- Señales útiles siguen apareciendo.
- Suppression de pronoun/noise/genérico débil sigue estable.
- Dedupe de equivalentes evita múltiples `medium` redundantes.
- No canon mutation.

## Useful Signals
Validado en contratos replay de variante:
- `el trazador del umbral` emite `review_enrich_existing_entity` con candidate `Iven Ral`.
- `la voz del peaje` emite `review_attach_role_or_title` con candidate `Iven Ral`.
- `el amparo de Sora` emite señal compatible de enrich relacional.

## Suppression Stability
Validado:
- `el forastero`, `el centinela`, `ella`, `vendedor ausente` no se convierten en señales fuertes.

## Equivalent Descriptor Behavior
Validado:
- Equivalentes de rol para mismo candidate/categoría/acción no quedan todos `medium`.
- Permanece al menos una señal útil principal.
- Extras equivalentes se degradan a `low` o quedan suprimidos según evidencia.

## Language-Agnostic Guardrails
- Tests verifican ausencia de literals de variante en `textifai/vaerl/review_queue.py`.
- Contratos exigen decisiones por metadata (`surface_type`, `descriptor_category`, `semantic_value`, `recommended_action`, facts/relationships/evidence), no por idioma o literal específico.

## Tests Added / Updated
Nuevos:
- `tests/test_textifai_descriptor_noise_budget_variant_fixture_harness.py`
- `tests/test_textifai_descriptor_noise_budget_variant_replay_baseline.py`
- `tests/test_textifai_descriptor_noise_budget_variant_replay_contracts.py`

Actualizados:
- Ninguno (fase enfocada a variante nueva).

## Validation Performed
Ejecutado (todos OK):
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
- `uv run python -m unittest -v tests.test_textifai_review_state_candidate_descriptor_signals`
- `uv run python -m unittest -v tests.test_textifai_review_state_candidate_noise_budget_dedupe`
- `uv run python -m unittest -v tests.test_textifai_descriptor_noise_budget_variant_fixture_harness`
- `uv run python -m unittest -v tests.test_textifai_descriptor_noise_budget_variant_replay_baseline`
- `uv run python -m unittest -v tests.test_textifai_descriptor_noise_budget_variant_replay_contracts`
- `uv run python scripts/textifai.py replay-downstream --help`

## Data Written
- Fixture sintético manual bajo `tests/fixtures/textifai/semantic_edges/descriptor_noise_budget_variant/**`.
- Output de replay solo en `TemporaryDirectory` durante tests.

## Safety Constraints
- Sin provider calls (parchado para fallar si ocurre llamada).
- Sin escritura en `runs/**` ni `vault/**`.
- Sin ingestión real.
- Sin cambios de schema.

## Known Limitations
- Cobertura anti-overfitting se centra en una variante sintética en español.
- No cubre aún variante multi-idioma ni agrupación de presentación en viewer.

## Future Extensions
- Añadir variante controlada con `language_hint` distinto manteniendo misma metadata class.
- Evaluar fase de viewer/presentation grouping sobre señales ya deduplicadas.

## Semantic Contract Changes
NO

## Runtime Changes
NO

## Generated Artifacts
Manual fixture/replay input only; temp-only replay output.

## Provider Calls
NO

## Write-back
NO

## Branch
`phase-1.3-ingestion-vaerl-hardening`

## Next Suggested Phase
Phase 1.3.L-b — Review Queue Presentation Grouping (viewer-level grouping sin mutación canónica).
