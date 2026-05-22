# Review Queue Viewer Quick Filters & Candidate-Centric Drilldown

## Product Reading
TextifAI ya genera señales útiles, ya agrupa señales relacionadas y viewer ya muestra summaries/counters. Esta fase mejora explorabilidad: filtros rápidos y drilldown candidate-centric para priorizar decisiones editoriales sin activar write-back. Sigue siendo read-only: sin merge/promote ni edición de canon.

## Scope
- Viewer-only en frontend.
- Sin cambios en runtime semántico (`review_queue.py` intacto).
- Sin schema changes.
- Sin provider/ingestion changes.

## Files Changed
- `textifai/web_viewer/static/app.js`
- `textifai/web_viewer/static/styles.css`
- `tests/test_textifai_web_viewer.py`
- `docs/handoffs/safepoint-045_review-queue-viewer-quick-filters-candidate-drilldown.md`

## Quick Filters Added
Se añadió set inicial de quick filters locales read-only:
- All
- Requires human review
- High
- Medium
- Has related/equivalent items
- Object retention
- Legacy/ungrouped
- Future actions

## Candidate-Centric Drilldown
Se añadió panel candidate-centric con chips:
- candidates con count de grupos
- candidate seleccionado filtra grupos asociados
- marker de review state (si existe metadata)
- marker de requires review

Sin navegación profunda ni backend nuevo.

## Active Filter / Clear Filter
- Estado visible: `Active filter: ...`
- Acción `Clear filter` para volver a `All`
- Candidate selection y quick filter son filtros locales del render.

## Legacy Fallback
- `legacy/ungrouped` preservado como sección visible.
- filtro legacy muestra fallback explícito sin borrar datos antiguos.

## Existing Grouping Preserved
- principal sigue primero
- related/equivalent siguen debajo del principal
- object retention sigue separado
- no mezcla cross-candidate por filtro candidate-centric

## Read-only / No Write-back Guarantee
- No endpoints POST nuevos.
- No handlers de mutación.
- No `/api/review/actions`, `/api/review/merge`, `/api/review/promote`.
- No cambios en queue/canon/VaERL/Obsidian.

## Future Actions Presentation
- Future actions siguen como chips/badges y botones disabled.
- No acciones activas ni write-back.

## Tests Added / Updated
`tests/test_textifai_web_viewer.py` actualizado con cobertura de:
- quick filters (high/medium/requires human review/related/object/legacy/future actions)
- active filter + clear filter metadata
- candidate list con counts
- candidate-selected filtering
- guards anti-write-back y endpoints prohibidos
- compatibilidad con grouping existente y fallback legacy

## Validation Performed
- `uv run python -m unittest -v tests.test_textifai_web_viewer`
- `node --check textifai/web_viewer/static/app.js`
- `uv run python scripts/textifai.py viewer --help`
- `uv run python -m unittest -v tests.test_textifai_review_state_candidate_noise_budget_dedupe`
- `uv run python -m unittest -v tests.test_textifai_descriptor_noise_budget_variant_replay_contracts`
- `git status --short`
- `git diff --stat`

## Data Written
- Ningún artifact generado.
- Solo frontend viewer, tests y handoff.

## Safety Constraints
- Viewer-only.
- Sin runtime/schema/provider changes.
- Sin escritura en `runs/**` o `vault/**`.

## Known Limitations
- Filtros son locales de UI, no persistentes.
- No quick-filter por Low/No auto-merge/No auto-promote en esta versión.
- No routing deep-link.

## Future Extensions
- quick filters opcionales adicionales (`low`, `no_auto_merge`, `no_auto_promote`)
- persistencia de filtro activo en estado URL/local
- drilldown candidate con sub-resumen por acción

## Semantic Contract Changes
NO

## Runtime Changes
NO

## Generated Artifacts
NO

## Provider Calls
NO

## Write-back
NO

## Branch
`phase-1.3-ingestion-vaerl-hardening`

## Next Suggested Phase
Phase 1.3.L-e — Review Queue Viewer Saved Views & Lightweight Filter Presets (read-only).
