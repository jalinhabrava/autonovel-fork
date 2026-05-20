# Local Path Ingestion Job MVP

## Scope
- Implementar primer MVP ejecutable del Ingestion Wizard con `local path` únicamente.
- Añadir endpoints GET/POST read-only/controlados para crear jobs, consultar estado y leer log.
- Mantener ejecución acotada a `runs/web_ingestion/**` con política de output derivada por backend.

## Files Changed
- `textifai/web_viewer/ingestion_jobs.py`: registry en memoria, validación, sanitización, build de comando y redacción básica de logs.
- `textifai/web_viewer/server.py`: endpoints de config, creación de jobs, estado y log; wiring del registry.
- `textifai/web_viewer/project_reader.py`: refresh defensivo de catálogo para detectar runs recién creadas.
- `textifai/web_viewer/static/app.js`: wizard ejecutable, submit, polling, estado, log tail y apertura/refresco de resultado.
- `textifai/web_viewer/static/styles.css`: estilos del estado del job y acciones del wizard.
- `tests/test_textifai_web_viewer.py`: cobertura de config segura, builder de comando, sanitización y rechazo de paths inválidos/overwrite.

## API Changes
- `GET /api/ingestion/config`
  - Ahora expone `can_execute: true`, `execution_mode: local_path_job`, warnings y notas de seguridad.
- `POST /api/ingestion/jobs`
  - Valida payload JSON de `local path`, deriva `output_root`, crea job en memoria y responde `202` con snapshot.
- `GET /api/ingestion/jobs/<job_id>`
  - Devuelve estado, timestamps, `output_root`, `project_id`, `command_preview`, error y `log_tail`.
- `GET /api/ingestion/jobs/<job_id>/log`
  - Devuelve log redacted y acotado del job.

## UI Changes
- `Ingestion Wizard` deja de ser solo preview.
- Botón `Submit ingestion job` habilitado cuando campos mínimos son válidos y `can_execute` está activo.
- Panel de estado con `job_id`, estado, timestamps, `output_root`, `project_id`, `exit_code`, error y `log_tail`.
- Acciones para `Refresh projects` y `Open result` cuando el proyecto resultante es detectable.

## Job Registry Behavior
- Registry en memoria por proceso de viewer.
- Cada job corre en thread background.
- Estados soportados: `queued`, `running`, `succeeded`, `failed`.
- `stdout` + `stderr` combinados, redacted y guardados como tail en memoria.
- Log persistido también en `web_ingestion_job.log` dentro del output del job.
- Si el server reinicia, jobs activos o historial en memoria se pierden.

## Command Building
- Comando construido solo como lista de args.
- Base:
  - `uv run python scripts/textifai.py init`
- Flags incluidos:
  - `--vault-root <derived_output_root>`
  - `--source-root <source_root>`
  - `--project-title <project_title>`
  - `--skip-plugin-install` por defecto
  - `--primary-language <value>` si existe
  - `--working-language <value>` repetible si existe
- No usa interpolación shell.
- No usa `shell=True`.

## Safe Output Policy
- `output_root` siempre derivado por backend.
- Root fijo: `runs/web_ingestion/`.
- Formato: `<timestamp>_<sanitized_slug>`.
- Rechazo si target existe.
- No se acepta output path arbitrario desde frontend.
- `source_root` debe existir y resolverse antes de lanzar job.
- No se escribe en `vault/` real ni fuera de `runs/web_ingestion/**`.

## Validation / Safety Checks
- Rechazo de `source_root` vacío.
- Rechazo de `source_root` inexistente o no-directorio.
- Rechazo de `run_name` no sanitizable.
- Rechazo de overwrite de target existente.
- Command preview y ejecución usan args list, no string shell.
- Logs pasan por redacción básica defensiva de tokens/patrones comunes.

## Data Written
- Solo en ejecuciones reales iniciadas por usuario.
- Directorio nuevo dedicado: `runs/web_ingestion/<timestamp>_<slug>/`.
- Log del job: `runs/web_ingestion/<timestamp>_<slug>/web_ingestion_job.log`.
- No uploads.
- No escritura en `vault/` real.
- No modificación de artifacts previos existentes.

## Data Sources Used
- Configuración local del viewer.
- Catálogo de proyectos/runs ya descubierto por `project_reader`.
- Payload del wizard enviado por frontend.
- Output y log del subprocess de `scripts/textifai.py init`.

## Validation Performed
- `uv run python -m unittest -v tests.test_textifai_web_viewer`
- `uv run python scripts/textifai.py viewer --help`
- `node --check textifai/web_viewer/static/app.js`
- `git status --short`
- `git diff --stat`

## Known Limitations
- Registry en memoria: reinicio de server pierde estado e historial de jobs.
- No cancelación de jobs en este MVP.
- Redacción de logs es básica; puede no cubrir todos los formatos de secretos.
- `project_id` depende de discovery actual por path, no de un ID global persistente.
- El target reservado queda marcado durante vida del proceso aunque job falle temprano.

## Future Extensions
- Cancelación segura de jobs.
- Persistencia ligera del registry.
- Validación de paths más rica y límites configurables.
- Mejor redacción de logs y truncado configurable.
- Upload mode separado y sandboxeado.
- Apertura profunda directa a tabs/paneles del resultado.

## Semantic Contract Changes: NO

## Runtime Changes: Viewer ingestion execution

## Write-back: Dedicated new run output only

## Uploads: NO

## Next Suggested Phase
- Phase 1.2.D — Job Lifecycle Hardening & Result Opening Flow.
