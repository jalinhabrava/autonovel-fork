# Job Lifecycle & Result Opening Flow

## Scope
- Endurecer lifecycle del job de ingestion local-path en viewer.
- Añadir listado read-only de jobs recientes del registry en memoria.
- Mejorar detección de resultado inspectable y warnings al terminar job.
- Mejorar UX para estado/error/log y apertura de resultado.

## Files Changed
- `textifai/web_viewer/ingestion_jobs.py`
- `textifai/web_viewer/server.py`
- `textifai/web_viewer/static/app.js`
- `textifai/web_viewer/static/styles.css`
- `tests/test_textifai_web_viewer.py`

## API Changes
- Nuevo endpoint `GET /api/ingestion/jobs`:
  - lista jobs conocidos por registry en memoria.
  - incluye `job_id`, `status`, timestamps, `exit_code`, `project_title`, `source_root`, `output_root`, `project_id`, señales de resultado, campos de log.
- `GET /api/ingestion/jobs/<job_id>` ahora expone snapshot más rico:
  - `duration_seconds`
  - `result_detected`
  - `result_warnings`
  - `result_status`
  - `inspectable_artifacts_available`
  - `review_queue_available`
  - `log_size_bytes`
  - `log_truncated`
  - `last_log_lines`
  - `safe_output_root`
- `GET /api/ingestion/jobs/<job_id>/log` devuelve metadata de truncado/size + últimas líneas.

## UI Changes
- Wizard muestra:
  - estado extendido del job actual.
  - warnings de resultado detectado/no detectado.
  - duración, tamaño de log, truncado, estado inspectable/review_queue.
  - command preview persistente en detalle de job.
- Nuevo panel `Recent jobs`:
  - lista jobs recientes del proceso actual.
  - acción `Inspect` para cargar cualquier job en foco.
- Botón `Open result` solo cuando existe `project_id`.
- Visual status badges para `queued/running/succeeded/failed`.

## Job Lifecycle Changes
- Registry mantiene set de firmas activas (`source_root + project_title + run_name`) para bloquear duplicados activos.
- Al finalizar job se libera firma activa.
- Snapshot de job evita exponer lock interno.
- Logs mantienen redacción y registran truncado + tamaño acumulado.

## Result Detection Behavior
- Tras `exit_code == 0`, backend evalúa output root:
  - detecta `99_System/obsidian_import.json` como señal de resultado inspectable.
  - detecta `99_System/review_queue.json` como disponibilidad de Review Queue.
- Si falta `99_System` o artifacts clave:
  - `result_detected: false` o warning parcial.
  - `result_warnings` explícitos.
- No se asume éxito inspectable solo por exit code.

## Error Handling
- En fallos de job:
  - se expone `exit_code` cuando existe.
  - `error` resumido.
  - `log_tail` y `last_log_lines` disponibles.
- UI no reintenta automáticamente.
- UI permite nuevo submit con slug/run distinto.

## Data Written
- Sin cambios de política de escritura:
  - solo output dedicado por job en `runs/web_ingestion/<timestamp>_<slug>/`.
  - log local de job `web_ingestion_job.log` en output del job.
- Sin uploads.
- Sin escritura en `vault/` real.

## Safety Constraints
- Subprocess con args list únicamente.
- `shell=False`.
- Output root derivado backend y acotado a `runs/web_ingestion/**`.
- Sin POST adicionales fuera de ingestion jobs.
- Sin cambios semánticos en VaERL/replay/canonicalización/contracts.

## Validation Performed
- `uv run python -m unittest -v tests.test_textifai_web_viewer` ✅
- `uv run python scripts/textifai.py viewer --help` ✅
- `node --check textifai/web_viewer/static/app.js` ✅
- `git status --short` ✅
- `git diff --stat` ✅

## Known Limitations
- Registry sigue en memoria; restart del server pierde historial/activos.
- No cancelación de jobs todavía.
- No persistencia de metadata de jobs entre reinicios.
- Redacción de logs sigue básica (mejor que antes, no exhaustiva).

## Future Extensions
- Cancelación segura de job activo.
- Persistencia ligera de jobs recientes.
- Deep-link robusto a tabs de resultado (`overview/review/canon`).
- Mejor detección de resultado por manifiesto mínimo de artifacts.

## Semantic Contract Changes: NO

## Runtime Changes: Viewer ingestion lifecycle

## Write-back: Dedicated new run output only

## Uploads: NO

## Next Suggested Phase
- Phase 1.2.E — Job Restart Resilience & Lightweight Persistence.
