# Entity-Centric Regression Triage

## Scope
- Phase 1.1.G en viewer: priorización diagnóstica por entidad, read-only.
- Cierre de Viewer/Navigation v1 sin mutaciones ni cambios semánticos runtime.

## Files Changed
- `textifai/web_viewer/static/app.js`
- `textifai/web_viewer/static/styles.css`
- `docs/handoffs/safepoint-013_entity-centric-regression-triage.md`

## UI Changes
- Nuevo panel `Entity Triage` en Overview.
- Summary compacto con:
  - entities flagged
  - high priority
  - medium priority
  - top reasons
  - estado de comparación activa (base/candidate) si aplica.
- Lista expandible de entidades priorizadas con badges de razón y acciones de navegación.

## Triage Features Added
- Ranking por entidad usando score de **prioridad diagnóstica** (observability-only).
- Triage funciona en dos modos:
  - run actual (sin comparación)
  - candidate run enriquecido por drift (si Compare Runs está activo)
- Orden descendente por score y límite de filas para mantener claridad.

## Risk Reasons Added
- low confidence
- review pressure
- nearby review candidates
- risk signals de canonicalization visibility
- invariant reference
- canonical drift
- slug drift
- review_state changed
- alias drift
- source mention drift
- relationship count drift

## Metrics / Scores Used
- score aditivo por señales observables existentes.
- niveles de prioridad:
  - high (score >= 6)
  - medium (score >= 3)
  - low (resto)
- score se presenta explícitamente como diagnóstico, no verdad canónica.

## Data Sources Used
- canon payload (primaries/review entities)
- semantic health (invariant checks y referencias)
- review_queue navegación contextual existente
- canonicalization visibility summary ya presente
- compare runs diff summary ya presente (si activo)
- artifacts raw solo vía links read-only

## Navigation Flows Added
- desde fila triage:
  - Open in Canon
  - Open in Graph
  - Open Review Context
  - Open invariant artifact
  - Open related artifact
- reuso total de mecanismos de navegación existentes.

## Semantic Contract Risk Analysis
- Semantic Contract Changes: NO
- Runtime Changes: Viewer-only
- Write-back: NO
- No cambia resolver, canonicalization, review queue, invariants ni artifacts.

## Validation Performed
- `uv run python -m unittest -v tests.test_textifai_web_viewer`
- `uv run python scripts/textifai.py viewer --help`
- `node --check textifai/web_viewer/static/app.js`
- `git status --short`
- `git diff --stat`

## Known Limitations
- Score es heurístico y dependiente de señales disponibles.
- Matching de invariant references y drift permanece conservador por términos.
- No hay deep-link cross-run por entidad aún; se mantiene navegación segura existente.

## Future Extensions
- Filtro por reason / priority / kind.
- Export read-only de cola de triage.
- Deep-link cross-run por entidad para diff contextual.

## Semantic Contract Changes: NO
## Runtime Changes: Viewer-only
## Write-back: NO
## Next Suggested Phase
- Phase 1.2.A — Reviewer Workflow Hardening (playbook de revisión guiada, checklists por reason type, sin acciones de write-back).
