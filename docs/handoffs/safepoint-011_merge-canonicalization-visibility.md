# Merge & Canonicalization Visibility

## Scope
- Phase 1.1.E en viewer: visibilidad read-only de canonicalización, merges y reconciliación.
- Sin write-back, sin mutaciones, sin cambios de contratos semánticos.
- Solo observabilidad, drilldown y navegación diagnóstica.

## Files Changed
- `textifai/web_viewer/project_reader.py`
- `textifai/web_viewer/static/app.js`
- `textifai/web_viewer/static/styles.css`
- `docs/handoffs/safepoint-011_merge-canonicalization-visibility.md`

## UI Changes
- Nuevo bloque **Canonicalization Visibility** en vista Canon (panel dedicado por entidad seleccionada).
- Integración del mismo bloque en Graph node detail para entidades.
- Tabla Canon ahora incluye botón `Inspect` además de `View in graph`.
- Nuevos badges/métricas visuales para aliases, source mentions, chapter refs, review pressure y señales de riesgo.
- Nuevos bloques de audit en formato defensivo (expandible) con contexto limitado.

## Canonicalization Visibility Added
- Para cada entidad:
  - canonical name, preferred slug, kind/subkind, review_state, confidence
  - aliases, source_mentions, chapter_refs
  - relationship_count, key_fact_count
  - review_pressure_count y nearby_review_entity_count detectables
- Señales observability-only:
  - many aliases
  - many source mentions
  - low confidence
  - review_state no canonical
  - nearby review entities
  - review pressure
  - unresolved relationship hints

## Merge/Audit Visibility Added
- Enriquecimiento read-only en backend (`project_reader`) por entidad usando artifacts existentes:
  - `resolved_entities.json`
  - `cleaned_entities.json`
  - `entity_clusters_audit.json`
  - `entity_resolution_audit.json`
  - `entity_cleanup_audit.json`
  - `promotion_decisions_audit.json`
  - `pre_vaerl_reconciliation_audit.json`
  - `obsidian_relationship_reconciliation_audit.json`
  - `review_queue.json`
  - `semantic_invariants_audit.json`
- Secciones audit renderizadas en panel:
  - resolution/cluster/promotion
  - resolved vs cleaned snapshots
  - cleanup summary
  - pre-VaERL reconciliation samples
  - relationship reconciliation samples
  - unresolved relationship hints

## Risk Signals Added
- Signals no canónicas y solo diagnósticas.
- No recomputan canonicalización ni corrigen entidades.
- Si falta estructura o artifact, muestra `not available`.

## Navigation Flows Added
- Desde panel de canonicalización:
  - `Open in Graph`
  - `Open Review Context`
  - `Open <artifact>.json` para raw audit relevante
- Reutiliza flujos previos:
  - Canon → Graph
  - Graph → Canon
  - Review Queue ↔ Graph/Canon
  - Invariant drilldown ↔ Graph/Canon/Review

## Data Sources Used
- Canon/graph/review payload existente del viewer.
- Artifacts existentes en `99_System` listados arriba.
- Sin creación de artifacts nuevos.

## Semantic Contract Risk Analysis
- Semantic Contract Changes: NO
- Runtime Changes: Viewer-only
- Write-back: NO
- No cambia resolver/canonicalization/reconciliation runtime.
- Matching es defensivo y no agresivo; evita inferir identidad dudosa.

## Validation Performed
- `uv run python -m unittest -v tests.test_textifai_web_viewer`
- `uv run python scripts/textifai.py viewer --help`
- `node --check textifai/web_viewer/static/app.js`
- `git status --short`
- `git diff --stat`

## Known Limitations
- Algunos artifacts pueden no existir por run; panel cae a `not available`.
- Mapeo review-context usa términos/slug/aliases presentes, no IDs semánticos globales.
- Extractos audit son limitados para mantener claridad y evitar dumps masivos.

## Future Extensions
- Correlación opcional por IDs estables de review item/entity cuando estén disponibles.
- Filtros internos por nivel de riesgo y tipo de señal en panel.
- Vistas comparativas entre runs para drift de canonicalización.

## Semantic Contract Changes: NO
## Runtime Changes: Viewer-only
## Write-back: NO
## Next Suggested Slice
- Phase 1.1.F — Canon Drift & Cross-Run Diff Visibility (comparar estabilidad de entidades y decisiones de canonicalización entre runs, read-only).
