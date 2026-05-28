# Persistent Spanish 20ch TextifAI Project Package

## Product Reading
TextifAI debe abrir proyectos persistentes author-facing, no runtimes efímeros en `/tmp`. VaERL sigue como source of truth y Markdown como substrate editable author-facing.

## Scope
Regeneración E2E 20ch con provider aprobado, package persistente local, manifest `textifai.project.json`, registry local gitignored y loader manifest-backed.

## Files Changed
- `textifai/web_viewer/project_reader.py`
- `scripts/dev/sp106_persistent_project_packager.py`
- `tests/test_textifai_project_package_contract.py`
- `tests/fixtures/textifai/project_package_contract/expected/*.json`
- `.gitignore`

## Provider Call Approval
DeepSeek provider calls aprobadas por usuario para esta fase. No secrets impresos. No raw provider outputs committeados.

## Source Manuscript Verification
Fuente verificada en `/home/david/OnT/ESP 王者の杖 .md`.

## Previous Runtime Diagnosis
8872 estaba sirviendo SP-096 mini fixture de 2 capítulos y 11 notas, insuficiente para validación de producto.

## Provider Preflight
`DEEPSEEK_API_KEY` presente. Script SP-095 reutilizado y redirigido a raíz persistente.

## 20ch E2E Regeneration
Run real ejecutado sobre 20 capítulos con DeepSeek Flash. Resultado usable pero con warnings/retry en parte de capítulos.

## Persistent Project Path
Proyecto persistente local: `/home/david/TextifAIProjects/OnT_Spanish_20ch.textifai/`

## TextifAI Project Manifest
`textifai.project.json` schema v1 con paths relativos, status, capabilities y privacy flags.

## Project Folder Structure
Raíz con `markdown/`, `vaerl/`, `graph/`, `drafts/`, `patches/`, `reports/`, `dev/`, `99_System/` de compatibilidad.

## Ingestion Output Contract
Fuente → detector de capítulos → `markdown/Chapters/*.md` → provider semantic run → VaERL/review/graph → package persistente.

## Editor Chapter Source
Editor debe listar solo `markdown/Chapters/*.md`. Se materializaron 20 capítulos desde source incluso cuando VaERL marcó retries.

## Workspace Loader / Open Project
`ProjectCatalog` ahora detecta `textifai.project.json` y registry local `.textifai_runs/registry.local.json`, y prefiere proyecto real sobre mini fixture.

## Graph / Note Payload
Graph y `/note` ya pueden cargar contra proyecto persistente con muchas más notas/nodos que SP-096. El run actual tiene warnings de retry.

## Local Registry
Registry local gitignored en `.textifai_runs/registry.local.json` con path absoluto al manifest persistente.

## Future .txtfai
Ahora: folder bundle + manifest. Futuro: `.txtfai` como folder bundle o zip package.

## Private Decision Handoff
- `docs/handoffs/private/safepoint-106_project-package-persistent-20ch/decision_handoff_private.md`

## Product Decision
`persistent_20ch_e2e_ready_with_retry_warnings`

## Recommended Next Phase
Retry focalizado chapter-scoped + SP-106B draft/patch queue sin write-back silencioso.

## What Worked
- Source real verificada.
- Provider run ejecutado.
- Package persistente creado.
- Manifest y registry integrados.
- Loader detecta proyecto real.

## What Failed
- No todos los capítulos quedaron listos semánticamente; `writer_outcome` reporta retries.
- El run VaERL materializó menos capítulos author-facing de los esperados, por eso se forzó materialización chapter-only desde source para Editor.

## Data Written
Se escribió proyecto persistente local fuera de git y reports commit-safe en `tests/fixtures/textifai/project_package_contract/expected/`.

## Privacy / Non-committed Output
No se commiteó source prose, provider outputs, package persistente, registry local ni handoff privado.

## Tests Added / Updated
Nuevo: `tests/test_textifai_project_package_contract.py`

## Validation Performed
Provider preflight, run E2E, package creation, manifest validation, loader validation y tests Python.

## Safety Constraints
No write-back desde editor. No package root changes. No secrets en logs. No outputs privados committeados.

## Known Limitations
Hay capítulos con retry pendiente. Graph counts y note counts son reales pero no equivalen a “canon perfecto”.

## Future Extensions
- `Add to VaERL`
- mini-ingestión por capítulo
- `.txtfai` zip export/import
- patch queue

## Runtime Changes
8872 debe reiniciarse contra código nuevo para descubrir registry local y preferir proyecto persistente.

## Write-back
NO.

## Branch
`phase-1.3-ingestion-vaerl-hardening`
