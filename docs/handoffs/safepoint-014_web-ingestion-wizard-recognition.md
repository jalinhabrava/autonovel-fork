# Web Ingestion Wizard Recognition

## Scope
- Reconocimiento y diseño seguro del MVP de Web Ingestion Wizard.
- Sin implementación de rutas POST, uploads, subprocess, jobs ni escritura de runs/vaults.
- Docs-only.

## Current Ingestion Entrypoints
- Entrypoint CLI activo:
  - `uv run python scripts/textifai.py init ...`
  - delega a `textifai.obsidian.cli` → `prepare_obsidian_project()` en `textifai/obsidian/setup.py`
- Comando `init` acepta hoy:
  - `--vault-root`
  - `--project-title`
  - `--source-root`
  - `--use-vault-root-as-source`
  - `--primary-language`
  - `--working-language` (repetible)
  - `--build-bridge-plugin`
  - `--skip-plugin-install`
  - `--plugin-repo-root`
  - `--importer-preference`
- Modo operativo actual:
  - `new_project` si no hay `source-root`
  - `existing_material` si hay `source-root` o `--use-vault-root-as-source`
- `--skip-plugin-install`:
  - evita instalar/copiar el bridge plugin en `.obsidian/plugins/...`
  - reduce side effects y dependencia de Node/npm para un wizard MVP
- Escrituras/outputs detectados:
  - inicializa/valida vault target
  - puede escribir `99_System/bootstrap_progress.jsonl`
  - puede escribir `99_System/source_extraction_audit.json`
  - si bootstrap estructurado corre, genera artifacts de semantic ingestion/import dentro del vault target
  - puede copiar/instalar bridge plugin en `.obsidian/plugins/<plugin_id>`
- Fallos posibles:
  - path inválido o no normalizable
  - vault destino no inicializable o no válido
  - provider/model no configurados para bootstrap estructurado
  - fallo de extracción/import bootstrap
  - fallo npm/build/install del plugin
  - conflictos al usar carpeta existente como destino/source

## Current Viewer Discovery Flow
- Viewer actual se arranca con:
  - `uv run python scripts/textifai.py viewer --root <path> [--root <path> ...]`
- Descubrimiento actual:
  - `ProjectCatalog` recorre roots configurados
  - inspecciona root y sus subdirectorios inmediatos
  - acepta candidatos con `99_System/` o candidatos que sean ellos mismos `99_System/`
- Datos que lista por proyecto:
  - `project_id`, `name`, `root`, `system_root`, `kind`
  - counts de chapters/entities/primaries/review
  - `review_queue_count`
  - `invariants_status`
- Refresh actual:
  - botón `Refresh projects` llama a `GET /api/projects`
- Apertura de resultado:
  - UI selecciona `project_id` y carga `GET /api/projects/<id>`
- Detección de nueva run:
  - hoy bastaría con que el wizard escriba en un root ya observado por viewer y luego refresque lista
  - no hay watcher ni push server-side; todo es polling/refresh explícito

## MVP Options
### Option A — Local path wizard
- Usuario indica:
  - source path local
  - project title
  - output root / run name / vault target
- Pros:
  - menor complejidad
  - sin uploads ni lifecycle temporal
  - se alinea con CLI actual
  - más fácil controlar paths y no-overwrite
  - mejor para entorno local-first del viewer actual
- Contras:
  - UX menos “web nativa”
  - depende de que usuario conozca paths locales válidos
  - permisos/path normalization deben manejarse bien

### Option B — Upload files wizard
- Usuario sube archivos desde navegador
- Pros:
  - UX más amigable para no técnicos
  - elimina entrada manual de paths
- Contras:
  - storage temporal
  - límites de tamaño
  - encoding/formato/zip lifecycle
  - cleanup de temporales
  - mayor superficie de seguridad
  - más trabajo antes de tener safety model sólido

### Option C — Hybrid
- MVP inicial con local path wizard
- upload real más adelante
- Pros:
  - entrega temprana segura
  - mantiene evolución futura abierta
  - reduce riesgo operacional inicial
- Contras:
  - UX inicial menos pulida
  - habrá que explicar claramente “local-only”

## Recommended MVP
- Recomendación: **Option C — Hybrid**
- Implementar primero wizard local-path, sin upload.
- Razón:
  - encaja con CLI y viewer actual
  - minimiza superficie de seguridad
  - permite definir command preview, output policy y job model antes de aceptar bytes arbitrarios desde navegador

## Safe Output Policy
- Usar root dedicado, propuesto:
  - `runs/web_ingestion/<timestamp_slug>/`
- Reglas:
  - no overwrite nunca
  - `run_id` único con timestamp + slug sanitizado
  - `project_title` visible pero no usado solo como path bruto
  - path final siempre normalizado y derivado por backend
  - logs separados dentro de run target o subdir controlado
  - no escribir en `vault/` real salvo aprobación explícita futura
  - no aceptar outputs fuera de roots aprobados sin confirmación fuerte
  - persistir metadata mínima del job visible en UI

## Execution Model Proposal
- Modelo recomendado:
  - subprocess asíncrono
  - registry de jobs en memoria
  - polling HTTP para estado y log
- Estado de job:
  - `queued`
  - `running`
  - `succeeded`
  - `failed`
- Captura:
  - stdout/stderr a buffer + archivo de log controlado
- Protección:
  - evitar doble submit accidental con lock simple por target path
  - no correr dos jobs con mismo output target
- Reinicio server:
  - en MVP shell no ejecutar nada aún
  - en job MVP futuro documentar que registry en memoria pierde jobs activos tras restart, salvo recuperación básica por log file

## API Proposal
- Propuesta futura, no implementada:
  - `GET /api/ingestion/config`
  - `POST /api/ingestion/jobs`
  - `GET /api/ingestion/jobs/<job_id>`
  - `GET /api/ingestion/jobs/<job_id>/log`
  - opcional `GET /api/ingestion/jobs`
- `GET /api/ingestion/config` debería exponer:
  - allowed roots
  - default output root
  - local-only warning
  - CLI capability summary
  - whether provider readiness probe passes
- `POST /api/ingestion/jobs` debería aceptar args estructurados, no command string

## UI Flow Proposal
1. Start ingestion
2. Choose input mode
3. Source material
4. Output/run settings
5. Review command / safety confirmation
6. Run
7. Progress
8. Open result

## Safety Constraints
- no shell string interpolation
- subprocess with args list only
- path normalization obligatoria
- no overwrite
- no secrets en logs
- no `.env` exposure
- no arbitrary command execution
- rutas POST solo para wizard futuro
- no canon write-back
- upload futuro con límites de tamaño y lifecycle explícito
- warning claro: herramienta local-only
- no escritura fuera de roots aprobados

## Validation Strategy
- fases futuras:
  - unit tests de path sanitization
  - tests de command builder
  - tests de job registry/status transitions
  - tests API viewer wizard GET/POST
  - test manual con tiny synthetic fixture cuando exista fixture harness
  - no ejecutar OnT/run real por defecto

## Recommended First Implementation Slice
- Recomendación: **Phase 1.2.B — Web Ingestion Wizard Shell**
- Scope sugerido:
  - UI shell del wizard
  - `GET /api/ingestion/config` read-only
  - command preview builder sin ejecución
  - safety warnings visibles
  - no POST, no subprocess, no writes
- Justificación:
  - menor riesgo
  - valida IA/UX/fields
  - fija contrato de seguridad antes de permitir ejecución real

## Semantic Contract Changes: NO
## Runtime Changes: NO
## Write-back: NO
## Next Suggested Phase
- Phase 1.2.B — Web Ingestion Wizard Shell
