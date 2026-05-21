# Object Retention Signal Normalization

## Scope

Normalizar objetos durables que caían como `review_entity` genérico para que emitan señal moderna de retención en `review_queue`, sin cambiar schema ni tocar descriptor/title/role policy.

## Files Changed

- `textifai/vaerl/review_queue.py`
- `tests/test_textifai_semantic_edge_replay_contracts.py`
- `tests/test_textifai_object_retention_signal_normalization.py`
- `tests/fixtures/textifai/semantic_edges/identity_alias_role/expected/replay_drift_expectations.json`
- `tests/fixtures/textifai/semantic_edges/identity_alias_role/expected/README.md`
- `docs/handoffs/safepoint-034_object-retention-signal-normalization.md`

## Semantic Decision

- No auto-promotion.
- No auto-merge.
- Sí señal moderna y accionable para objetos durables no retenidos como primary.
- Esta fase no aborda drifts de descriptor/title/role.

## Runtime Behavior Change

En `_review_entity_items(...)`, cuando una review entity cumple perfil de objeto durable sin strong merge candidate, se normaliza a item `entity_retention_review` con metadata moderna.

## Object Retention Normalization

Normalización aplicada de forma conservadora cuando:

- `entity_kind == object`
- hay retención/evidencia suficiente (`_has_retention_weight`)
- no es candidato ephemeral/noise
- no existe strong merge candidate (`score < 0.85`)

Salida normalizada incluye:

- `review_type: entity_retention_review`
- `suggested_action: review_create_primary` o `review_keep_secondary`
- `signal_tier: medium`
- `candidate_status`
- `surface_type: object_like`
- `semantic_value: persistent_object`
- `do_not_auto_merge: true`
- `future_viewer_actions: [promote, keep_secondary, reject_noise]`
- `retention_review_required: true`

## Review Queue Metadata

Se mantiene compatibilidad backward:

- `schema_version` sin cambio
- fields viewer-compatible existentes intactos
- items no-target de esta fase siguen su comportamiento previo

## Drift Expectations Updated

`replay_drift_expectations.json` actualizado para mover el drift de objeto persistente a comportamiento resuelto actual y mantener explícitos los drifts descriptor/title/role.

## No Aggressive Promotion Guarantee

- `llave de cristal` sigue sin promoción automática a primary.
- la normalización cambia señal de review/metadata, no canon.

## Deferred Descriptor / Role Drifts

Se mantienen como drift conocido y diferido:

- `title_surface_alias_without_review_signal`
- `descriptor_surface_alias_without_enrichment_signal`
- `ren_descriptor_alias_without_review_signal`

## Tests Added / Updated

- Nuevo: `tests/test_textifai_object_retention_signal_normalization.py`
- Actualizado: `tests/test_textifai_semantic_edge_replay_contracts.py`

Cobertura añadida:

- normalización de `llave de cristal` a `entity_retention_review` moderno
- metadata mínima obligatoria
- no broad reclassification de descriptor/title/role en esta fase

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
- `uv run python scripts/textifai.py replay-downstream --help`
- `git status --short`
- `git diff --stat`

Resultado: PASS en todas las suites y checks.

## Data Written

- no artifacts reales generados
- solo fixtures/tests/docs versionados
- replay outputs solo en `TemporaryDirectory` durante tests

## Safety Constraints

- provider calls: NO
- write-back: NO
- schema changes: NO
- runtime broad rewrite: NO
- real runs/vault writes: NO

## Known Limitations

- descriptor/title/role signals siguen diferidos
- objeto durable con strong candidate queda fuera de esta normalización conservadora

## Future Extensions

- Phase siguiente para decisión explícita de descriptor/title/role absorbed signals.
- posible calibración de thresholds de candidate strength si aparecen falsos positivos.

## Semantic Contract Changes

BEHAVIOR ONLY (sin cambio de schema).

## Runtime Changes

YES, normalización de generación/metadata de review_queue para objetos durables review.

## Generated Artifacts

Temp-only replay output.

## Provider Calls

NO

## Write-back

NO

## Branch

`phase-1.3-ingestion-vaerl-hardening`

## Next Suggested Phase

Phase 1.3.J-b — Descriptor / Role Review Signal Decision.
