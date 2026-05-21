# Retention Review Policy & Signal Tiers

## Scope

Refinar política de review signals de retención/identidad para priorización, metadata accionable y comportamiento agnóstico de lengua, sin write-back ni cambios de schema.

## Files Changed

- `textifai/vaerl/review_queue.py`
- `tests/test_textifai_replay_expected_drift_rules.py`
- `tests/test_textifai_review_queue_retention_signals.py`
- `tests/test_textifai_retention_review_policy.py`
- `tests/fixtures/textifai/minimal_novel/expected/replay_drift_expectations.json`
- `docs/operations/retention-review-policy.md`

## Policy Document Added

Se añadió `docs/operations/retention-review-policy.md` para fijar:

- propósito editorial de señales de retención
- principios de no auto-promotion y no auto-merge
- acciones recomendadas
- tiers `high|medium|low|suppressed`
- policy de candidate guessing
- diseño language-agnostic
- acciones futuras del viewer sin write-back

## Recommended Actions Defined

- `review_merge_or_alias`
- `review_create_primary`
- `review_keep_secondary`
- `review_reject_noise`
- `review_insufficient_evidence`
- `review_attach_role_or_title`
- `review_enrich_existing_entity`

## Signal Tiers Defined

Runtime y tests ahora reconocen:

- `high`
- `medium`
- `low`
- `suppressed`

`suppressed` evita crear item; otros tiers se traducen a severities compatibles con schema actual.

## Language-Agnostic Design

- La decisión principal ya no depende solo de strings concretas.
- Se acepta `surface_type` y `language_hint` en retention context.
- Pronombres pueden marcarse estructuralmente como `pronoun_like`.
- Descriptor/title/role se tratan por señal estructural, no por idioma fijo.
- Sigue existiendo fallback conservador con pequeña lista pronoun-like para compatibilidad.

## Runtime Behavior Changes

`review_queue.py` ahora añade metadata backward-compatible a `entity_retention_review`:

- `signal_tier`
- `candidate_status`
- `language_hint`
- `surface_type`
- `semantic_value`
- `future_viewer_actions`

También ajusta:

- selección de severidad desde tier
- supresión de pronombres/ruido efímero
- decisión más explícita para descriptor/title/role vs object durable omitido

## Review Item Metadata

Cada signal retenido mantiene:

- `recommended_action`
- `do_not_auto_merge`
- `decision_reason`
- `chapter_refs`
- `no_clear_existing_primary`
- `retention_review_required`

Y añade metadata nueva compatible con viewer futuro sin cambiar `schema_version`.

## Tests Added / Updated

- Actualizado `tests/test_textifai_replay_expected_drift_rules.py`
  - exige metadata de tier/status/semantic value para `brújula de plata`
- Actualizado `tests/test_textifai_review_queue_retention_signals.py`
  - verifica `signal_tier`, `candidate_status`, `surface_type`, `semantic_value`, `future_viewer_actions`
- Añadido `tests/test_textifai_retention_review_policy.py`
  - objeto persistente omitido sin candidato
  - title/descriptor en español e inglés con `surface_type`
  - pronouns suprimidos
  - mención efímera suprimida

## Replay Fixture Behavior

Con replay provider-free del fixture `minimal_novel`:

- `brújula de plata` sigue sin auto-promoción a primary
- debe generar `entity_retention_review`
- review item ahora carga tier/status/action metadata
- menciones episódicas prohibidas siguen sin primary ni señal fuerte

## Validation Performed

- `uv run python -m unittest -v tests.test_textifai_fixture_harness`
- `uv run python -m unittest -v tests.test_textifai_artifact_contract_snapshots`
- `uv run python -m unittest -v tests.test_textifai_replay_baseline_harness`
- `uv run python -m unittest -v tests.test_textifai_replay_output_contract_assertions`
- `uv run python -m unittest -v tests.test_textifai_replay_expected_drift_rules`
- `uv run python -m unittest -v tests.test_textifai_review_queue_retention_signals`
- `uv run python -m unittest -v tests.test_textifai_retention_review_policy`
- `uv run python scripts/textifai.py replay-downstream --help`
- `git status --short`
- `git diff --stat`

Resultado: PASS en todas las suites y help command.

## Data Written

- Docs versionados.
- Tests versionados.
- Temp-only replay output durante tests.
- Sin escritura en `runs/**`, `vault/**` ni `.textifai/**`.

## Safety Constraints

- Provider calls: NO
- Write-back: NO
- Schema version change: NO
- Real runs/vault writes: NO
- Auto-merge: NO
- Auto-promotion: NO

## Known Limitations

- `pronoun_like` sigue teniendo fallback léxico pequeño para compatibilidad; no sustituye detector multilengua real.
- `signal_tier` usa heurística ligera; futura fase puede refinar scoring.
- `review_enrich_existing_entity` queda documentado pero no tiene caso runtime fuerte en fixture actual.

## Future Extensions

- refinar detector extensible de `surface_type`
- separar candidate scoring y tier policy en helper más explícito
- preparar viewer actions reales sin write-back automático
- decidir política final de object retention vs keep-secondary vs create-primary

## Semantic Contract Changes

BEHAVIOR ONLY. Metadata nueva backward-compatible en review queue; `schema_version` no cambia.

## Runtime Changes

YES. Cambia generación/metadata de `review_queue` para señales de retención.

## Generated Artifacts

Temp-only replay output.

## Provider Calls

NO

## Write-back

NO

## Branch

`phase-1.3-ingestion-vaerl-hardening`

## Next Suggested Phase

Phase 1.3.H — Viewer Review Actions Contract, para fijar shape/UI contract de acciones editoriales sugeridas sin write-back definitivo.
