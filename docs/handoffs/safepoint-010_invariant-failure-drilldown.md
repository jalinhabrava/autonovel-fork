# Invariant Failure Drilldown

## Scope
- Phase 1.1.D en viewer: ampliar sección Semantic Invariants a superficie de diagnóstico semántico.
- Trabajo read-only, observabilidad y navegación diagnóstica.
- Sin write-back, sin cambios de contratos, sin recomputar invariants.

## Files Changed
- `textifai/web_viewer/static/app.js`
- `textifai/web_viewer/static/styles.css`
- `textifai/web_viewer/project_reader.py`
- `docs/handoffs/safepoint-010_invariant-failure-drilldown.md`

## UI Changes
- Semantic Invariants ahora muestra:
  - conteos pass/fail/warn/skip/total
  - agrupación por severidad/status
  - agrupación por tipo de check (fail/warn)
  - grupos separados de failing checks y warning checks
- Cada check fallido/warn tiene detalle expandible con resumen, severidad, mensaje, contexto limitado y referencias detectadas.

## Drilldown Features Added
- Enriquecimiento read-only de checks desde `semantic_invariants_audit.json`:
  - `severity`
  - `affected_entities`
  - `affected_chapters`
  - `affected_targets`
  - `review_terms`
  - `related_artifacts`
  - `raw_context` limitado
- Detalle por check incluye “not available” cuando falta dato.

## Navigation Flows Added
- Desde drilldown de invariant:
  - `Open entity in Canon`
  - `Open entity in Graph`
  - `Open target in Graph`
  - `Open review context`
  - `Open related artifact`
- Reutiliza navegación cliente existente de Phase 1.1.C (sin rutas POST, sin mutaciones).

## Data Sources Used
- `semantic_invariants_audit.json` (checks/details existentes)
- payload de graph/canon/review ya expuesto por viewer
- artifacts ya listados por viewer

## Semantic Contract Risk Analysis
- Semantic Contract Changes: NO
- Runtime Changes: Viewer-only
- Write-back: NO
- No cambia generación de invariants ni estructura de artifacts.
- Derivaciones son de presentación/diagnóstico, sin corrección automática ni merge.

## Validation Performed
- `uv run python -m unittest -v tests.test_textifai_web_viewer`
- `uv run python scripts/textifai.py viewer --help`
- `git status --short`
- `git diff --stat`
- `node --check textifai/web_viewer/static/app.js`

## Known Limitations
- Referencias afectadas dependen de campos presentes en `details`; no todos los checks exponen entidades/capítulos/targets.
- `review_terms` usa términos detectados; no hay ID estable de review item desde invariants.
- Agrupación avanzada por entidad/artifact no incluida en esta slice.

## Future Extensions
- Match opcional a IDs estables de review item cuando backend exponga mapping explícito.
- Filtro interactivo por severidad/tipo dentro del panel de invariants.
- Enlace cruzado de invariant ↔ edge específico en graph cuando exista referencia estructurada.

## Semantic Contract Changes: NO
## Runtime Changes: Viewer-only
## Write-back: NO
## Next Suggested Slice
- Phase 1.1.E — Review Queue Prioritization Lens (ranking explainable por severidad + evidencia + ambigüedad, read-only).
