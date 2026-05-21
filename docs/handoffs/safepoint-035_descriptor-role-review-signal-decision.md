# Descriptor / Role Review Signal Decision

## Scope

Phase 1.3.J-b implementa señal editorial conservadora para surfaces absorbidas (`title_like` / `role_like` / `descriptor_like`) con evidencia suficiente y candidato canonical claro, sin tocar schema, viewer, prompts, providers ni write-back.

## Files Changed

- `textifai/vaerl/review_queue.py`
- `tests/test_textifai_semantic_edge_replay_contracts.py`
- `tests/test_textifai_descriptor_role_review_signal_decision.py` (nuevo)
- `tests/fixtures/textifai/semantic_edges/identity_alias_role/expected/replay_drift_expectations.json`
- `tests/fixtures/textifai/semantic_edges/identity_alias_role/expected/README.md`
- `docs/operations/retention-review-policy.md`

## Semantic Decision

- No generar review para todo alias absorbido.
- Sí generar review cuando surface absorbida aporta valor semántico editorial (title/role/descriptor) con evidencia estructural.
- Descriptor genérico con evidencia débil se mantiene suprimido para evitar ruido.

## Anti-hardcode / Language-Agnostic Guardrails

- Inspección read-only ejecutada sobre strings fixture y drift ids:
  - `la princesa`, `la heredera silenciosa`, `el muchacho`, `Sera Valen`, `Ren Tal`
  - `title_surface_alias_without_review_signal`, `descriptor_surface_alias_without_enrichment_signal`, `ren_descriptor_alias_without_review_signal`
- Resultado: no aparecen como condiciones runtime en `textifai/vaerl/review_queue.py`.
- Nueva prueba `test_fixture_strings_are_not_runtime_conditions` verifica que esas strings no estén hardcodeadas en runtime.
- Lógica runtime usa metadata: `surface_type`, `semantic_value`, `language_hint`, `candidate score`, `key_facts`, `chapter_refs`, `source_mentions`, `candidate_status`.

## Runtime Behavior Change

Se añadió `absorbed semantic surface signaling` en `build_review_queue`:

- Nuevo paso `_absorbed_semantic_surface_items(...)`.
- Fuente de candidatos: `retention_context.global_entities` + `retention_context.resolved_entities`.
- Solo surfaces absorbidas que ya resuelven contra primaries (`_resolve_key`) y no son pronoun/noise.
- Emisión conservadora:
  - `title_like` / `role_like` con evidencia mínima -> `review_attach_role_or_title`
  - `descriptor_like` con evidencia de enriquecimiento no trivial -> `review_enrich_existing_entity`
  - descriptor genérico débil -> no item.

## Descriptor / Role Signal Behavior

- `la princesa` -> señal explícita `entity_retention_review` + `review_attach_role_or_title`.
- `la heredera silenciosa` -> señal explícita `entity_retention_review` + `review_enrich_existing_entity`.
- Metadata incluida: `signal_tier`, `candidate_status`, `surface_type`, `semantic_value`, `language_hint`, `do_not_auto_merge`, `decision_reason`, `future_viewer_actions`, `chapter_refs`.

## Suppression Policy

- `el muchacho` permanece suprimido como descriptor genérico absorbido (sin señal fuerte).
- `ella` y `guardia somnoliento` continúan suprimidos.
- No auto-merge y no auto-promotion en todos los paths nuevos.

## Object Retention Regression

Sin regresión de `safepoint-034`:

- `llave de cristal` mantiene `entity_retention_review` moderno.
- Se preserva metadata de retención y frontera provider-free/tempdir.

## Drift Expectations Updated

`replay_drift_expectations.json` actualizado:

- Resueltos y movidos a `resolved_current_behavior`:
  - `title_surface_absorbed_without_review_signal`
  - `descriptor_surface_absorbed_without_enrichment_signal`
- Se mantiene drift explícito:
  - `generic_descriptor_absorbed_without_review_signal`
  - metadata de caso: `surface_text`, `candidate`, `fixture_case`, `observed_behavior`, `decision`, `reason`.
- `non_negotiable_failures` amplía garantías:
  - `auto-merge occurs`
  - `auto-promotion occurs`
  - además de primaries prohibidos y frontera tempdir/provider.

## Tests Added / Updated

### Added
- `tests/test_textifai_descriptor_role_review_signal_decision.py`
  - title absorbed -> attach role/title
  - descriptor absorbed con facts -> enrich existing entity
  - descriptor genérico débil -> suppressed
  - anti-hardcode runtime strings

### Updated
- `tests/test_textifai_semantic_edge_replay_contracts.py`
  - exige señales explícitas para `la princesa` y `la heredera silenciosa`
  - valida drift taxonómico `generic_descriptor_absorbed_without_review_signal`
  - valida resolved drift ids de title/descriptor

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
- `uv run python scripts/textifai.py replay-downstream --help` ✅

## Data Written

- Solo archivos de código/tests/docs/fixture expectations en scope.
- Replay outputs solo en `TemporaryDirectory` durante tests.
- Sin escritura en `runs/**` ni `vault/**`.

## Safety Constraints

- Provider calls: deshabilitadas/parchadas en tests provider-free.
- Sin ingestión real.
- Sin cambios de schema.
- Sin cambios de viewer.
- Sin write-back.

## Known Limitations

- `generic_descriptor_absorbed_without_review_signal` permanece abierto por diseño para evitar ruido.
- Heurística descriptor enrichment es conservadora (`facts/chapter refs/confidence`) y puede requerir ajuste en futuros fixtures.

## Future Extensions

- Añadir tiering más fino para descriptor genérico multi-capítulo.
- Separar subclases de descriptor (`status_like`, `epithet_like`, etc.) sin hardcode por idioma.
- Conectar señales a acciones viewer cuando exista write-back seguro.

## Semantic Contract Changes

- **BEHAVIOR ONLY** (sin cambio de `schema_version`).

## Runtime Changes

- **YES**: generación de review_queue para surfaces absorbed descriptor/title/role y metadata asociada.

## Generated Artifacts

- Temp-only replay output en validación.

## Provider Calls

- **NO**

## Write-back

- **NO**

## Branch

- `phase-1.3-ingestion-vaerl-hardening`

## Next Suggested Phase

- `Phase 1.3.K — Descriptor Genericity Tuning & Signal Noise Budget`.
