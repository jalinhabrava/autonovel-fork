# Historical Compare Quick Actions & Run QA Checklist

## Scope
- Añadir acciones rápidas de comparación desde jobs históricos inspectables.
- Añadir checklist QA read-only por run histórica seleccionada.
- Exponer indicadores defensivos de compare readiness en snapshots del wizard.
- Mantener flujo viewer-only, sin uploads, sin cleanup, sin retry/cancel y sin cambios semánticos.

## Files Changed
- `textifai/web_viewer/ingestion_jobs.py`
- `textifai/web_viewer/static/app.js`
- `textifai/web_viewer/static/styles.css`
- `tests/test_textifai_web_viewer.py`

## API Changes
- Sin endpoints nuevos.
- Job snapshot ahora expone:
  - `can_compare`
  - `compare_unavailable_reason`
  - `comparability_manifest_available`
  - `semantic_artifacts_available`
- Estos campos son derivados defensivos desde `project_id` y `artifact_availability`.

## UI Changes
- Detalle histórico de job incluye panel `Compare readiness`.
- Detalle histórico de job incluye `Run QA checklist` read-only.
- Cards históricas muestran badge `compare yes/no`.
- Añadidos botones rápidos:
  - `Open Compare Runs`
  - `Compare with previous run`
  - `Compare with latest run`

## Compare Quick Actions
- `Set as base` y `Set as candidate` siguen asignando al Compare Runs existente.
- `Compare with previous run` busca run inspectable anterior por `created_at`.
- `Compare with latest run` busca la run inspectable más reciente distinta.
- No se ejecuta auto-compare; se prepara estado y abre/dirige al panel existente.

## Compare Readiness Indicators
- `can_compare`: requiere `project_id` y `obsidian_import.json` disponible.
- Reason si no puede comparar:
  - `project_id missing`
  - `obsidian_import.json missing`
- Manifest de comparabilidad se muestra solo como availability, sin interpretación fuerte.

## Run QA Checklist
- Checklist visual/read-only para responder qué revisar tras una ingestión.
- Items cubren:
  - result inspectable
  - artifacts clave disponibles
  - Semantic Health
  - Review Queue
  - Entity Triage
  - Canonicalization risk
  - Compare Runs
  - Graph/unresolved targets
  - raw artifacts si hay warnings

## Checklist Derivation Rules
- `available`: artifact/destino existe.
- `missing`: artifact esperado no existe.
- `recommended`: hay warnings o review queue disponible.
- `manual`: revisión humana sin estado persistente.
- `not available`: destino no existe o falta `project_id`.
- No se guarda estado y no se afirma que la revisión esté hecha.

## Navigation Flows
- Checklist permite abrir:
  - Overview / Semantic Health
  - Review Queue
  - Entity Triage
  - Canon
  - Graph
  - Artifacts
  - raw artifacts
  - Compare Runs
- Si faltan datos, botones quedan ausentes/disabled o muestran warning.

## Data Written
- Sin nuevas escrituras.
- Sigue vigente solo metadata/log del wizard bajo `runs/web_ingestion/<run_id>/`.

## Safety Constraints
- Uploads: NO.
- Destructive actions: NO.
- Retry/cancel/replay: NO.
- Semantic contract changes: NO.
- No writes en vaults ni generated artifacts fuera del output dedicado del wizard.

## Validation Performed
- `node --check textifai/web_viewer/static/app.js` ✅
- `uv run python -m unittest -v tests.test_textifai_web_viewer` ✅
- `uv run python scripts/textifai.py viewer --help` ✅
- `git status --short` ✅
- `git diff --stat` ✅

## Known Limitations
- Quick compare prepara base/candidate y abre panel; no ejecuta comparación automáticamente.
- Previous/latest target se deriva por `created_at` y runs inspectables, no por semantic manifest.
- Checklist no guarda estado de completado.
- Manifest de comparabilidad solo se muestra como disponible/no disponible.

## Future Extensions
- Botón opcional para ejecutar Compare Runs tras elegir base/candidate.
- Baseline pinning explícito para proyectos con muchas runs.
- Checklist persistible solo si se diseña un contrato de review separado.
- Interpretación más rica del comparability manifest si se estabiliza schema viewer-only.

## Semantic Contract Changes: NO

## Runtime Changes: Viewer ingestion QA UX

## Write-back: Dedicated web ingestion metadata/log only

## Uploads: NO

## Destructive Actions: NO

## Next Suggested Phase
- Phase 1.2.I — Wizard MVP Hardening Review & Phase 1.3 Planning.
