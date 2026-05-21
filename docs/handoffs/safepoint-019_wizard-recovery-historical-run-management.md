# Wizard Recovery UX & Historical Run Management

## Scope
- Mejorar UX del historial del Web Ingestion Wizard usando metadata persistida en `safepoint-018`.
- Añadir filtros, ordenación y summary client-side para jobs históricos/restaurados.
- Hacer más visible estado restored/stale/inspectable/log-source.
- Mantener todo read-only y no destructivo para historial.

## Files Changed
- `textifai/web_viewer/ingestion_jobs.py`
- `textifai/web_viewer/server.py`
- `textifai/web_viewer/static/app.js`
- `textifai/web_viewer/static/styles.css`
- `tests/test_textifai_web_viewer.py`

## API Changes
- `GET /api/ingestion/jobs` ahora devuelve:
  - `jobs`
  - `summary`
- `summary` incluye:
  - `job_count`
  - `restored_count`
  - `active_count`
  - `inspectable_count`
  - `failed_count`
  - `ignored_output_dirs_without_metadata`
  - `approx_log_bytes`
- Se mantiene read-only.
- No se añaden endpoints destructivos ni upload.

## UI Changes
- `Recent jobs` evoluciona hacia superficie `Ingestion History` más útil.
- Añadidos filtros client-side:
  - status
  - restored only
  - inspectable only
  - failed/stale only
  - text search
- Añadida ordenación:
  - newest first
  - oldest first
  - status
  - project title
- Summary compacto de historial.
- Placeholder disabled: `Retention cleanup is not implemented yet`.

## Historical Job Management
- Jobs en memoria + restaurados se muestran juntos.
- Orden por fecha y filtros solo frontend.
- Cada fila muestra:
  - `project_title`
  - `run_name`
  - `status`
  - restored badge
  - stale badge si aplica
  - inspectable/not-inspectable badge
  - `created_at`
  - `finished_at`
  - `duration`
  - `output_root`
  - warning principal si existe
- Carpetas `runs/web_ingestion/*` sin metadata se ignoran defensivamente y se reportan como count.

## Recovery UX
- Mensajes más claros para jobs restaurados:
  - restored badge
  - warning de restart cuando estado previo era activo
  - warning si resultado no es inspeccionable
- Detalle del job mantiene trazabilidad del restart.

## Result Opening Behavior
- `Open result` desde historial si `project_id` existe.
- Al abrir resultado:
  - refresca lista de projects
  - selecciona proyecto
  - vuelve a `overview`
- Si no existe `project_id`, UI informa que refresh/inspección manual puede ser necesaria.

## Log Recovery UX
- Detalle muestra `log_source` (`memory` / `persisted` / `missing`).
- `View log` pide tail con `max_chars` defensivo.
- `log_warning` visible si falta log persistido.
- Estado truncado/tamaño sigue visible.

## Data Written
- Sin nuevas categorías de escritura.
- Solo metadata/log del wizard en `runs/web_ingestion/<run_id>/`.

## Safety Constraints
- Uploads: NO.
- Destructive actions: NO.
- No delete/cleanup real.
- No cambios semánticos.
- No modificación de outputs históricos fuera de metadata/log propios del wizard.

## Validation Performed
- `uv run python -m unittest -v tests.test_textifai_web_viewer` ✅
- `uv run python scripts/textifai.py viewer --help` ✅
- `node --check textifai/web_viewer/static/app.js` ✅
- `git status --short` ✅
- `git diff --stat` ✅

## Known Limitations
- Filtros/ordenación son solo frontend; no hay paginación backend.
- No hay cleanup real ni retención todavía.
- Runs antiguas sin metadata siguen fuera del historial, salvo count ignorado.
- `stale` sigue representado como `failed + warning`, no estado backend separado.

## Future Extensions
- Estado `stale` explícito si merece contrato viewer-only propio.
- Paginación/virtualización si historial crece mucho.
- Retención/cleanup no destructivo con dry-run antes de acciones reales.
- Enlaces más profundos a tabs concretos del resultado histórico.

## Semantic Contract Changes: NO

## Runtime Changes: Viewer ingestion history UX

## Write-back: Dedicated web ingestion metadata/log only

## Uploads: NO

## Destructive Actions: NO

## Next Suggested Phase
- Phase 1.2.G — Historical Run Triage & Artifact Entry Surface.
