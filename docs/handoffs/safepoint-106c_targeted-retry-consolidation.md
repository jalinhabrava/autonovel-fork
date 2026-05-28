# Targeted Retry Consolidation

## Product Reading
TextifAI es una plataforma first-party para autores. VaERL es semantic source of truth. Markdown es substrate editable author-facing. React/Tailwind es la cara principal del producto.

## Scope
Leer outputs del retry focalizado SP-106B, clasificar resultado por capítulo, actualizar status/manifest, mantener 8872 sobre proyecto persistente y exponer CTA honesto.

## Files Changed
- `textifai/web_viewer/project_reader.py`
- `tests/test_textifai_targeted_retry_consolidation.py`
- `tests/fixtures/textifai/targeted_retry_consolidation/expected/*.json`
- `docs/handoffs/safepoint-106c_targeted-retry-consolidation.md`

## SP106B Context
SP-106B lanzó DeepSeek `deepseek-v4-flash` sobre 15 capítulos `needs_retry`. El run terminó y dejó artifacts privados en el project package.

## Retry Output Discovery
Outputs encontrados bajo `dev/provider_outputs/targeted_retry_sp106b/20260528T184056Z`. No se hicieron provider calls nuevas en SP-106C.

## Retry Result Classification
15 capítulos fueron intentados. El outcome de retry indica 13 capítulos aún `needs_retry`; no se crearon reviews semánticas.

## Retry Artifact Integration
No se integró VaERL/graph/review con éxito falso. Los artifacts quedan localizados pero el outcome sigue indicando retry técnico pendiente.

## Manifest / Status Update
Manifest privado actualizado con `retry_summary`, `chapters_retried=15`, `chapters_still_failed=13` y `technical_failures=13`.

## Workspace Status UX
`workspace_status` muestra textos author-facing: 20 capítulos detectados, 5 listos, 15 reintentados, 13 pendientes, 0 decisiones editoriales.

## Persistent Workspace on 8872
8872 sigue usando proyecto persistente 20ch como base manual-review; mini fixture queda fallback dev.

## Editor / Graph / Review Validation
Editor conserva 20 capítulos; graph/review siguen sobre proyecto persistente, no mini fixture.

## Retry CTA State
CTA honesto: `Reintentar capítulos fallidos` si quedan fallos técnicos; `Abrir workspace` sigue disponible.

## Private Decision Handoff
- `docs/handoffs/private/safepoint-106c_targeted-retry-consolidation/decision_handoff_private.md`

## Product Decision
No inventar integración. El proyecto queda usable con warnings, y retry técnico sigue pendiente para 13 capítulos.

## Recommended Next Phase
SP-106D: mejorar retry de capítulos aún fallidos con estrategia distinta o adapter específico de integración por capítulo.

## What Worked
Retry outputs localizados, clasificación completada, manifest/status actualizado, UI status coherente.

## What Failed
El retry focalizado no resolvió 13 capítulos. No hay integración segura de artifacts en VaERL/graph sin fingir éxito.

## Data Written
Reports commit-safe, handoff público, manifest privado/status privado.

## Privacy / Non-committed Output
Project package, provider outputs, registry local, source prose y handoff privado no se commitean.

## Tests Added / Updated
`tests/test_textifai_targeted_retry_consolidation.py`.

## Validation Performed
Ver respuesta final.

## Safety Constraints
No full rerun, no retry semántico, no source prose en reports, no raw provider outputs en git, no editor write-back.

## Known Limitations
13 capítulos siguen necesitando reintento técnico.

## Future Extensions
Endpoint controlado de retry, adapter por capítulo, integración incremental real en VaERL/graph/review.

## Runtime Changes
`project_reader.py` prioriza `manifest.status` para labels de retry consolidados.

## Write-back
NO.

## Branch
`phase-1.3-ingestion-vaerl-hardening`
