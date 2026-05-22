# Review-State Candidate Noise Budget & Equivalent Descriptor Dedupe

## Product Reading

TextifAI ya puede generar señales útiles alrededor de entidades en review. Riesgo siguiente: varias señales parecidas pueden representar misma decisión editorial. Esta fase conserva señal principal útil y reduce duplicados equivalentes. No implica merge automático, promotion automática, mutación de canon ni write-back.

## Scope

- runtime mínimo en `textifai/vaerl/review_queue.py`
- tests replay/unit para dedupe/degrade de equivalentes
- drift expectations y docs de política
- sin schema change, viewer, provider, write-back ni canonicalization broad changes

## Files Changed

- `textifai/vaerl/review_queue.py`
- `tests/test_textifai_review_state_candidate_noise_budget_dedupe.py`
- `tests/test_textifai_review_state_candidate_descriptor_signals.py`
- `tests/test_textifai_descriptor_noise_budget_replay_contracts.py`
- `tests/test_textifai_descriptor_signal_replay_alignment_diagnostics.py`
- `tests/test_textifai_descriptor_genericity_policy.py`
- `tests/fixtures/textifai/semantic_edges/descriptor_noise_budget/expected/replay_drift_expectations.json`
- `tests/fixtures/textifai/semantic_edges/descriptor_noise_budget/expected/README.md`
- `docs/operations/retention-review-policy.md`

## Semantic Decision

Equivalencia primaria se evalúa por `(candidate, descriptor_category, recommended_action)` con escape hatch por evidence diferencial. Mantener una signal principal medium. Extras equivalentes pasan a low. Signals realmente distintas sobreviven.

## Runtime Behavior Change

Se añadió post-procesado sobre review items ya emitidos:

- identifica descriptor items equivalentes;
- mantiene item principal con mayor peso estructural;
- degrada equivalentes cercanas a `low`;
- conserva items con facts o relationships diferenciales.

## Equivalent Descriptor Policy

Equivalentes:

- mismo candidate principal;
- misma `descriptor_category`;
- misma acción editorial;
- mismo valor semántico compatible;
- sin facts o relationships claramente diferenciales.

Escape hatch:

- relationship target/type distinto -> mantener;
- facts diferenciales fuertes -> mantener;
- acción distinta -> mantener;
- categoría distinta -> mantener.

## Noise Budget

- máximo 1 `medium` por `(candidate, descriptor_category, recommended_action)` salvo evidence diferencial;
- extras equivalentes -> `low` con metadata de degradación;
- no suppression agresiva por defecto;
- no afecta categorías/acciones distintas.

## Useful Signals Preserved

Se mantienen:

- `el cartógrafo sin memoria` -> `review_enrich_existing_entity` `medium`
- `el capitán del paso` -> `review_attach_role_or_title` `medium`
- `el protector de Luma` -> `review_enrich_existing_entity` `medium`

## Dedupe / Degrade Behavior

En replay actual:

- `el capitán del paso` queda señal principal `medium`
- `el guardián del archivo` -> `low`
- `el custodio del paso` -> `low`
- metadata secundaria incluye `degraded_due_to_equivalent_signal`, `equivalent_signal_group`, `primary_equivalent_surface`

## Suppression Regression

Siguen suprimidos o sin strong signal:

- `el viajero`
- `el caminante`
- `él`
- `mercader distraído`

## No Canon Mutation Guarantee

- `Ari Mar` sigue `review_entity`
- no auto-promotion
- no auto-merge
- no write-back
- no schema change
- no VaERL/Obsidian mutation

## Anti-hardcode / Language-Agnostic Guardrails

- runtime no usa strings de fixture como condición
- tests unitarios verifican equivalencia con surfaces inglesas distintas
- runtime decide por metadata, facts, relationships y candidate state

## Drift Expectations Updated

Resueltos/registrados:

- `equivalent_descriptor_signals_should_not_all_remain_medium`
- `review_state_candidate_descriptor_no_explosion_observed`
- `distinct_descriptor_signals_should_survive_when_facts_differ`

Sigue drift parcial:

- `descriptor_metadata_incomplete` para item genérico `review_entity`

## Tests Added / Updated

- Nuevo `tests/test_textifai_review_state_candidate_noise_budget_dedupe.py`
- Actualizado `tests/test_textifai_review_state_candidate_descriptor_signals.py`
- Actualizado `tests/test_textifai_descriptor_noise_budget_replay_contracts.py`
- Actualizado `tests/test_textifai_descriptor_signal_replay_alignment_diagnostics.py`
- Actualizado `tests/test_textifai_descriptor_genericity_policy.py`

## Validation Performed

PASSED:

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
- `uv run python scripts/textifai.py replay-downstream --help`

## Data Written

Solo archivos versionados. Replay output solo en `TemporaryDirectory`.

## Safety Constraints

- No provider calls
- No ingestion real
- No writes a `runs/**` ni `vault/**`
- No schema change
- No write-back

## Known Limitations

- Política aún degrada, no agrupa visualmente.
- Heurística de facts diferenciales es conservadora; futuras mejoras pueden refinar similitud semántica.
- `descriptor_metadata_incomplete` parcial sigue abierto para item genérico review_entity.

## Future Extensions

- grouping viewer-facing en vez de solo degrade runtime
- suppression segura de redundancia total
- budget más fino por chapter cluster o relationship bundle

## Semantic Contract Changes

BEHAVIOR ONLY: review queue ahora degrada señales descriptor equivalentes sin cambiar schema.

## Runtime Changes

YES: `review_queue.py` dedupe/degrade para señales descriptor equivalentes.

## Generated Artifacts

Temp-only replay output.

## Provider Calls

NO.

## Write-back

NO.

## Branch

`phase-1.3-ingestion-vaerl-hardening`

## Next Suggested Phase

`Phase 1.3.K-b3d — Equivalent Descriptor Grouping Metadata / Viewer Presentation Contract`
