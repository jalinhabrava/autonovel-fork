# Job Restart Resilience & Lightweight Persistence

## Scope
- Añadir persistencia ligera de metadata por job del Web Ingestion Wizard.
- Rehidratar jobs previos al reiniciar viewer.
- Recuperar logs persistidos para jobs restaurados.
- Mantener apertura de resultado y detección inspectable tras restart.

## Files Changed
- `textifai/web_viewer/ingestion_jobs.py`
- `textifai/web_viewer/server.py`
- `textifai/web_viewer/static/app.js`
- `textifai/web_viewer/static/styles.css`
- `tests/test_textifai_web_viewer.py`

## Persistence Format
- Archivo por job: `runs/web_ingestion/<run_id>/web_ingestion_job.json`
- Campos persistidos:
  - `job_id`
  - `status`
  - `created_at`
  - `started_at`
  - `finished_at`
  - `duration_seconds`
  - `exit_code`
  - `project_title`
  - `source_root`
  - `output_root`
  - `safe_output_root`
  - `command_preview`
  - `result_detected`
  - `result_status`
  - `result_warnings`
  - `inspectable_artifacts_available`
  - `review_queue_available`
  - `project_id`
  - `error`
  - `run_name`
  - `log_path_relative`
- No se persiste log completo dentro del JSON.
- Persistencia atómica simple con archivo temporal + replace.

## API Changes
- `GET /api/ingestion/jobs` ahora incluye jobs restaurados desde disco.
- `GET /api/ingestion/jobs/<job_id>` expone `restored_from_disk`, `log_path_relative`, señales revalidadas y snapshot persistente.
- `GET /api/ingestion/jobs/<job_id>/log` hace fallback a `web_ingestion_job.log` si no hay log en memoria.
- `GET /api/ingestion/jobs/<job_id>/log?max_chars=...` acepta límite defensivo de tail.

## UI Changes
- `Recent jobs` ahora mezcla jobs en memoria + restaurados.
- Badge `restored` visible en detalle y lista.
- `View log` fuerza recuperación de log persistido para jobs rehidratados.
- Estado de job muestra `log_source`, warnings de log y warnings de restart/result detection.

## Rehydration Behavior
- Al arrancar registry se escanean `runs/web_ingestion/*/web_ingestion_job.json`.
- Jobs válidos se cargan read-only sin relanzar subprocess.
- Si metadata dice `queued` o `running`:
  - se marca `failed`
  - se añade warning: `server restarted while job was active; status cannot be trusted`
- Se evita duplicado por `job_id` y `output_root`.

## Result Detection Behavior
- Tras rehidratar se recalcula estado desde filesystem actual.
- `99_System/obsidian_import.json` => `result_detected` / inspectable.
- `99_System/review_queue.json` => `review_queue_available`.
- Si faltan artifacts, se reemplaza confianza previa por warnings actuales.
- `project_id` se vuelve a derivar desde `output_root` cuando el resultado es abrible por viewer.

## Log Recovery Behavior
- Si el job no tiene log en memoria:
  - se intenta leer `web_ingestion_job.log` dentro de su output root.
  - se devuelve tail truncado/redacted.
  - `log_source` indica `persisted`.
- Si falta log:
  - `log_source: missing`
  - warning claro en respuesta/UI.

## Data Written
- Solo dentro de `runs/web_ingestion/<run_id>/`:
  - `web_ingestion_job.json`
  - `web_ingestion_job.log`
- Sin escrituras en raíz repo, `vault/`, `.textifai/`, `.codegraph/`, `.superpowers/`.

## Safety Constraints
- No restart/re-run automático de jobs.
- No recuperación de subprocess activo.
- No borrado de outputs, logs o metadata.
- No cambios semánticos en ingestion/VaERL/replay/contracts.
- Redacción básica aplicada a errores/logs persistidos o recuperados.

## Validation Performed
- `uv run python -m unittest -v tests.test_textifai_web_viewer` ✅
- `uv run python scripts/textifai.py viewer --help` ✅
- `node --check textifai/web_viewer/static/app.js` ✅
- `git status --short` ✅
- `git diff --stat` ✅

## Known Limitations
- Registry sigue sin persistencia completa de estado vivo; solo metadata ligera por job.
- Jobs activos interrumpidos se degradan a `failed` con warning; no hay recovery real.
- Redacción de logs sigue básica.
- No hay limpieza/rotación de metadata antigua.
- Runs previas sin `web_ingestion_job.json` no se descubren como historial del wizard.

## Future Extensions
- Persistencia ligera indexada para ordenar/filtrar historial grande.
- Cleanup/retention policy opcional para metadata y logs del wizard.
- Recovery dashboard específico para jobs interrumpidos.
- Enlaces profundos a tabs concretos del resultado restaurado.

## Semantic Contract Changes: NO

## Runtime Changes: Viewer ingestion persistence

## Write-back: Dedicated web ingestion job metadata/log only

## Uploads: NO

## Next Suggested Phase
- Phase 1.2.F — Wizard Recovery UX & Historical Run Management.
