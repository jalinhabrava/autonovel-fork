# Historical Run Triage & Artifact Entry Surface

## Scope
- Convertir cada job histórico/restaurado del wizard en punto de entrada hacia inspección semántica.
- Añadir señales de disponibilidad de artifacts semánticos al snapshot del job.
- Añadir atajos desde historial hacia Overview, Semantic Health, Review Queue, Canon, Graph, Artifacts, raw artifacts, Compare Runs y Entity Triage.
- Mantener la fase como navegación/UX read-only, sin uploads ni acciones destructivas.

## Files Changed
- `textifai/web_viewer/ingestion_jobs.py`
- `textifai/web_viewer/static/app.js`
- `tests/test_textifai_web_viewer.py`

## API Changes
- No se añadieron endpoints nuevos.
- Snapshot de jobs ahora expone `artifact_availability` derivado defensivamente desde `99_System`:
  - `obsidian_import.json`
  - `review_queue.json`
  - `semantic_invariants_audit.json`
  - `run_comparability_manifest.json`
- `web_ingestion_job.json` también persiste `artifact_availability`.

## UI Changes
- Detalle de job histórico ahora muestra separación explícita entre:
  - job log de ejecución del wizard
  - semantic artifacts de la ingestion
- Se añadieron acciones rápidas:
  - `Open Overview`
  - `Open Semantic Health`
  - `Open Review Queue`
  - `Open Canon`
  - `Open Graph`
  - `Open Artifacts`
  - `Open Entity Triage`
  - `Use as base`
  - `Use as candidate`
- Se añadieron botones de raw artifact con disabled defensivo si artifact falta.

## Historical Run Triage
- Las cards históricas muestran señales run-card:
  - status
  - restored/stale/inspectable badges
  - result status
  - review queue availability
  - timestamps y duration
  - output root
  - warning principal
- Para run abierta/seleccionada, se muestra mini-summary de calidad con datos del project payload actual:
  - health status
  - primary count
  - review entity count
  - review queue count
  - invariant status
  - triage rows

## Artifact Entry Shortcuts
- Atajos raw disponibles desde detalle de job:
  - `obsidian_import.json`
  - `review_queue.json`
  - `semantic_invariants_audit.json`
  - `run_comparability_manifest.json`
- Si artifact no existe, botón queda disabled.
- No se inventa disponibilidad.

## Result Opening Behavior
- Abrir resultado desde historial:
  - refresca projects
  - selecciona project por `project_id`
  - navega a tab solicitado
  - muestra notice contextual
- Si falta `project_id`, se muestra error/warning sin crash.

## Compare/Triage Integration
- `Use as base` y `Use as candidate` asignan el `project_id` al estado existing de Compare Runs.
- `Open Entity Triage` abre Overview sobre el proyecto histórico seleccionado.
- No se recalcula scoring ni se cambia semántica.

## Log vs Artifact Separation
- UI deja explícito que `web_ingestion_job.log` es log de ejecución.
- Semantic artifacts se muestran como outputs separados.
- `View log` sigue recuperando log con tail defensivo.

## Data Written
- Sin nuevas escrituras funcionales.
- Persistencia existente de metadata/log del wizard continúa bajo `runs/web_ingestion/<run_id>/`.

## Safety Constraints
- Uploads: NO.
- Destructive actions: NO.
- Delete/cleanup/retry/cancel: NO.
- No replay.
- No cambios en VaERL, canonicalization, review queue generation ni artifact schemas.

## Validation Performed
- `uv run python -m unittest -v tests.test_textifai_web_viewer` ✅
- `uv run python scripts/textifai.py viewer --help` ✅
- `node --check textifai/web_viewer/static/app.js` ✅
- `git status --short` ✅
- `git diff --stat` ✅

## Known Limitations
- Mini-summary de calidad solo aparece cuando el project payload ya está cargado/seleccionado.
- No hay eager loading de todos los project payloads históricos por performance.
- Artifact shortcuts dependen de `artifact_availability` derivado desde filesystem local.
- Compare integration solo asigna base/candidate; usuario aún ejecuta comparación en panel existente.

## Future Extensions
- Lazy-load de summary semántico por card expandida.
- Deep links más finos hacia anchors internos de Semantic Health/Entity Triage.
- Run-to-run compare quick action si base y candidate ya están seleccionados.
- Historical run triage score viewer-only basado en health/review/invariant fields existentes.

## Semantic Contract Changes: NO

## Runtime Changes: Viewer ingestion history/navigation UX

## Write-back: Dedicated web ingestion metadata/log only

## Uploads: NO

## Destructive Actions: NO

## Next Suggested Phase
- Phase 1.2.H — Historical Compare Quick Actions & Run QA Checklist.
