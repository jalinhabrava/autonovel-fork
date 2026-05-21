# Descriptor Genericity Policy & Noise Budget Heuristics

## Scope

Phase 1.3.K-a formaliza heurística conservadora para descriptores absorbidos usando metadata estructural. Incluye helper/runtime pequeño, tests unitarios nuevos y actualización de policy docs. No crea fixture replay nuevo ni toca schema, viewer, prompts, providers o write-back.

## Files Changed

- `textifai/vaerl/review_queue.py`
- `docs/operations/retention-review-policy.md`
- `tests/test_textifai_descriptor_genericity_policy.py`

## Policy Decision

- `generic_descriptor` queda suprimido por defecto.
- Solo sube a review si existe novedad semántica no trivial.
- `title_descriptor` y `role_descriptor` pueden emitir attach con evidencia mínima.
- `status_descriptor`, `relationship_descriptor`, `epithet_descriptor` pueden emitir si existe impacto semántico suficiente.

## Descriptor Taxonomy

Taxonomía implementada/soportada por metadata:

- `title_descriptor`
- `role_descriptor`
- `status_descriptor`
- `relationship_descriptor`
- `epithet_descriptor`
- `generic_descriptor`
- `appearance_descriptor`
- `age_or_demographic_descriptor`
- `unknown_descriptor`

Si no existe categoría explícita, fallback:
- `title_like` -> `title_descriptor`
- `role_like` -> `role_descriptor`
- `descriptor_like` -> `unknown_descriptor`

## Noise Budget

Heurística K-a aplicada a nivel de decisión por item:

- descriptors genéricos no escalan a `medium` sin novedad fuerte.
- relación genérica `related_to` sin facts no basta para promotion a review.
- facts múltiples + persistencia + impacto pueden desbloquear `review_enrich_existing_entity`.
- presupuesto run-level completo queda como extensión K-b.

## Runtime Behavior Change

Cambios puntuales en `review_queue.py`:

- helper `_descriptor_category(...)`
- helper `_has_relationship_descriptor_impact(...)`
- refinamiento de `_has_descriptor_enrichment_signal_value(...)`
- ajuste de `_recommended_absorbed_surface_action(...)`
- metadata de review incluye `descriptor_category`
- se elimina bloqueo demasiado agresivo para absorbed title/role surfaces antes de su clasificación específica

## Generic Descriptor Suppression

- descriptor genérico con una sola mención/fact débil sigue suprimido.
- descriptor genérico multicapítulo sin facts nuevos no escala a `medium` por defecto.
- caso tipo `el muchacho` sigue alineado con supresión conservadora.

## Descriptor Novelty Criteria

Criterios usados por helper:

- facts no triviales / múltiples
- persistencia por capítulos o menciones
- impacto relacional real
- score de candidato suficiente
- metadata estructural por categoría
- sin dependencia de strings fixture-specific

## Anti-hardcode / Language-Agnostic Guardrails

- tests estáticos mantienen que strings fixture no existen en runtime logic.
- tests funcionales comparan surfaces distintas con misma metadata y exigen misma decisión.
- runtime decide por:
  - `surface_type`
  - `semantic_value`
  - `descriptor_category`
  - `language_hint`
  - `key_facts`
  - `chapter_refs`
  - `source_mentions`
  - `relationships`
  - `candidate score/status`

## Tests Added / Updated

### Added
- `tests/test_textifai_descriptor_genericity_policy.py`
  - generic weak descriptor suppressed
  - generic multichapter without novel facts not medium by default
  - descriptor with novel facts emits enrich
  - role/title/status emits attach/enrich
  - relationship descriptor impact emits review
  - pronoun-like suppressed
  - language-agnostic equivalent surfaces match decision
  - anti-hardcode static guard

### Updated
- Ningún test existente necesitó cambio funcional en esta fase.

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
- `uv run python scripts/textifai.py replay-downstream --help` ✅

## Data Written

- Solo código/tests/docs dentro de scope.
- Replay outputs solo temporales durante tests.
- Sin escritura en `runs/**` o `vault/**`.

## Safety Constraints

- No provider calls.
- No ingestión real.
- No schema change.
- No viewer change.
- No write-back.

## Known Limitations

- Noise budget completo run-level aún no existe; K-a solo formaliza decisión por item.
- `unknown_descriptor` sigue fallback conservador.
- Novedad semántica todavía usa heurística simple, no diff semántico profundo contra canonical.

## Future Extensions

- `Phase 1.3.K-b` con fixture replay dedicado `descriptor_noise_budget`.
- budget global por run/candidate/category.
- agrupación de descriptors equivalentes y degraded extras.

## Semantic Contract Changes

- **BEHAVIOR ONLY**

## Runtime Changes

- **YES**: tuning de review_queue para genericidad descriptor y novedad semántica.

## Generated Artifacts

- Temp-only replay output en validación.

## Provider Calls

- **NO**

## Write-back

- **NO**

## Branch

- `phase-1.3-ingestion-vaerl-hardening`

## Next Suggested Phase

- `Phase 1.3.K-b — Descriptor Noise Budget Replay Fixture Contracts`
