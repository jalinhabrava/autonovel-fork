# Review Queue Deep Visibility

## Scope

- Fase: `Phase 1.1.B — Review Queue Deep Visibility`
- Objetivo: convertir Review Queue de tabla plana a superficie read-only de inspección semántica.
- In scope:
  - `textifai/web_viewer/static/app.js`
  - `textifai/web_viewer/static/styles.css`
  - handoff de fase
- Out of scope:
  - `textifai/vaerl/**`
  - `textifai/import_review/**`
  - `textifai/obsidian/**`
  - replay / write-back / schema changes / artifact generation

## Files Changed

- `textifai/web_viewer/static/app.js`
  - summary visual de review queue
  - filtros client-side
  - sort client-side
  - item cards expandibles con evidencia/candidatos
  - links a raw artifact y graph/canon
- `textifai/web_viewer/static/styles.css`
  - estilos de summary, filtros, cards expandibles, severity badges
- `docs/handoffs/safepoint-008_review-queue-deep-visibility.md`
  - handoff de la fase

## UI Changes

- Nuevo summary arriba del tab Review Queue con:
  - total items
  - high severity
  - items with candidates
  - items with evidence
  - review type count
  - queue status
- Resumen visual adicional:
  - badges by severity
  - badges by review_type
- Filtros client-side:
  - severity
  - review_type
  - text search
- Sorting client-side:
  - severity
  - review_type
  - source
  - target
- Cada item ahora es expandible:
  - source/target claros
  - severity/type visibles
  - candidates list
  - evidence list
  - acciones de navegación a graph/canon

## Derived Read-Only Metrics

Derivadas solo desde `review_queue.json` ya cargado:

- total item count
- counts by severity
- counts by review_type
- high severity count
- candidate-backed item count
- evidence-backed item count
- filtered result count

## Data Sources Used

- `review_queue.json` ya expuesto en `state.current.canon.review_queue`
- payload actual del viewer (`graph`, `canon`) para navegación read-only

## Semantic Contract Risk Analysis

- Riesgo semántico: **bajo**
- Cambios solo de presentación/agrupación/filtering client-side
- No se reinterpreta schema más allá de labels/campos existentes
- Si falta campo:
  - se muestra vacío
  - o `not available`
- No se inventa severidad, tipo ni resolución

## Validation Performed

- `uv run python -m unittest -v tests.test_textifai_web_viewer`
- `uv run python scripts/textifai.py viewer --help`
- `git status --short`
- `git diff --stat`

## Known Limitations

- Search se aplica por texto simple, no búsqueda semántica.
- Navegación a canon abre tab canon pero no resalta entidad concreta.
- Navegación a graph depende de resolución ya existente por label/slug/note path.
- No hay grouping jerárquico completo; summary + filtros cubren caso actual.
- No hay paginación virtual para colas muy grandes.

## Future Extensions

- grouping por `review_type`
- drawer lateral persistente
- resaltado directo de entidad en canon/graph
- chips rápidos “show only high severity”
- correlación con invariants y unresolved graph targets

## Semantic Contract Changes: NO

- NO

## Runtime Changes: Viewer-only

- YES

## Write-back: NO

- NO

## Next Suggested Slice

- `Phase 1.1.C — Graph/Canon Cross-Navigation Tightening`
  - resaltar source/target en graph
  - deep-link desde review item a entity detail
  - sincronizar canon/review/graph selection state
