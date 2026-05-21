# Viewer Review Actions Contract

## Scope

Definir contrato viewer-facing read-only para acciones editoriales sugeridas desde `review_queue.json`, sin write-back real.

## Files Changed

- `textifai/web_viewer/static/app.js`
- `textifai/web_viewer/static/styles.css`
- `tests/test_textifai_web_viewer.py`
- `tests/test_textifai_viewer_review_actions_contract.py`
- `docs/operations/retention-review-policy.md`
- `docs/operations/viewer-review-actions-contract.md`
- `docs/handoffs/safepoint-031_viewer-review-actions-contract.md`

## Contract Document Added

Se añadió `docs/operations/viewer-review-actions-contract.md` con:

- inputs relevantes de `review_queue.json`
- action descriptors viewer-facing
- mapping desde `recommended_action`
- safety rules read-only
- language-agnostic behavior
- futuros targets de write-back solo documentados

## Action Mapping Defined

- `review_merge_or_alias` → `merge`, `mark_alias`
- `review_create_primary` → `promote`
- `review_keep_secondary` → `keep_secondary`
- `review_reject_noise` → `reject_noise`
- `review_insufficient_evidence` → inspect evidence only
- `review_attach_role_or_title` → `attach_role_or_title`
- `review_enrich_existing_entity` → `enrich_existing_entity`

`metadata.future_viewer_actions` tiene prioridad visual si existe.

## Viewer Rendering Added

El viewer ahora muestra para review items:

- recommended action
- signal tier
- candidate status
- semantic value
- surface type
- language hint
- warning `do_not_auto_merge`
- badges/buttons disabled de `future_viewer_actions`

## Read-only / Disabled Future Actions

- no POST
- no endpoint nuevo
- no write-back
- botones disabled
- copy explícita `Future action: ...`
- warnings conservadores para pronoun-like y no-clear-candidate

## Language-Agnostic Behavior

- UI basada en metadata (`surface_type`, `semantic_value`, `candidate_status`)
- no depende de strings españolas/inglesas para mapping principal
- fallback conservador si metadata es incompleta

## Tests Added / Updated

- nuevo `tests/test_textifai_viewer_review_actions_contract.py`
- actualizado `tests/test_textifai_web_viewer.py`

Cobertura:

- mapping de `recommended_action`
- render read-only de future actions
- buttons disabled
- warning `do_not_auto_merge`
- backward compatibility sin metadata nueva
- behavior agnóstico de lengua

## Validation Performed

- `uv run python -m unittest -v tests.test_textifai_web_viewer`
- `uv run python -m unittest -v tests.test_textifai_review_queue_retention_signals`
- `uv run python -m unittest -v tests.test_textifai_retention_review_policy`
- `uv run python -m unittest -v tests.test_textifai_viewer_review_actions_contract`
- `node --check textifai/web_viewer/static/app.js`
- `uv run python scripts/textifai.py replay-downstream --help`
- `git status --short`
- `git diff --stat`

Resultado: PASS en todas las suites y checks.

## Data Written

- docs versionados
- tests versionados
- static viewer rendering read-only

## Safety Constraints

- Provider Calls: NO
- Write-back: NO
- Real runs/vault writes: NO
- Review queue mutation: NO
- Canon mutation: NO

## Known Limitations

- viewer no ejecuta ninguna acción todavía
- descriptors se muestran en inglés técnico estable; localización futura pendiente
- no hay endpoint/action dispatcher aún

## Future Extensions

- tooltips más ricos por action descriptor
- panel dedicado de decision summary
- write-back contract separado para merge/promote/alias/reject

## Semantic Contract Changes

NO. Sin schema change.

## Runtime Changes

YES, viewer-only read-only rendering.

## Generated Artifacts

NO

## Provider Calls

NO

## Write-back

NO

## Branch

`phase-1.3-ingestion-vaerl-hardening`

## Next Suggested Phase

Phase 1.3.I — Viewer Review Decision UX States, todavía sin write-back persistente.
