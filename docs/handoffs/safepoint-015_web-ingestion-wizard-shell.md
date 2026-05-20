# Web Ingestion Wizard Shell

## Scope
- Implementación de shell UI/API del wizard de ingestión web.
- Solo preview: sin POST, sin subprocess, sin uploads, sin ejecución de ingestión.
- Viewer-only y sin write-back.

## Files Changed
- `textifai/web_viewer/server.py`
- `textifai/web_viewer/static/app.js`
- `textifai/web_viewer/static/styles.css`
- `tests/test_textifai_web_viewer.py`
- `docs/handoffs/safepoint-015_web-ingestion-wizard-shell.md`

## API Changes
- Nuevo endpoint GET read-only:
  - `GET /api/ingestion/config`
- Payload incluye:
  - `mode: local_path_preview_only`
  - `can_execute: false`
  - `can_upload: false`
  - `default_output_root`
  - `recommended_command` metadata (args list preview style)
  - `local_only_warning`
  - `safety_notes`
  - `supported_input_mode: local_path`
  - `future_input_modes: [upload]`
  - `required_fields` definidos

## UI Changes
- Nueva sección `Ingestion Wizard` en Overview.
- Pasos visibles:
  1. Start ingestion
  2. Input mode
  3. Source material
  4. Output/run settings
  5. Command preview
  6. Safety review
  7. Execution placeholder
- Formulario local path:
  - source root
  - project title
  - run name/output slug
  - primary language
  - working languages
  - skip plugin install (default true)
- Manejo defensivo:
  - si `/api/ingestion/config` falla, muestra estado unavailable sin romper viewer.

## Command Preview Behavior
- Preview generado como lista de argumentos, no comando shell interpolado.
- Base:
  - `uv run python scripts/textifai.py init`
- Incluye:
  - `--vault-root <runs/web_ingestion/<slug>>`
  - `--source-root <source/path o placeholder>`
  - `--project-title <title o placeholder>`
  - `--primary-language` opcional
  - `--working-language` repetible
  - `--skip-plugin-install` por defecto
- Con campos vacíos muestra warnings/placeholder, pero no ejecuta nada.

## Safety Behavior
- Mensajería explícita de preview-only:
  - no subprocess
  - no execution
  - no filesystem writes
  - no uploads
  - no provider calls
- Botón de ejecución deshabilitado con texto de fase futura.

## Data Sources Used
- Config read-only de `GET /api/ingestion/config`
- Estado local frontend del formulario
- Sin lectura de `.env`, sin probes de provider, sin escritura de artifacts.

## Validation Performed
- `uv run python -m unittest -v tests.test_textifai_web_viewer`
- `uv run python scripts/textifai.py viewer --help`
- `node --check textifai/web_viewer/static/app.js`
- `git status --short`
- `git diff --stat`

## Known Limitations
- No ejecución real ni job registry todavía.
- No POST/API de jobs.
- No upload.
- Preview no valida filesystem real (solo validación superficial de campos).

## Future Extensions
- Habilitar `POST /api/ingestion/jobs` con sandbox de paths y no-overwrite estricto.
- Job registry + polling de estado/log.
- Apertura automática del resultado al completar job.

## Semantic Contract Changes: NO
## Runtime Changes: Viewer-only preview
## Write-back: NO
## Execution: NO
## Next Suggested Phase
- Phase 1.2.C — Local Path Ingestion Job MVP (POST + registry + polling + safe output policy enforcement).
