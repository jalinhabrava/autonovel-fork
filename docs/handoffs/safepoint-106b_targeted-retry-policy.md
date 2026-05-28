# Targeted Retry Policy + Persistent Workspace Verification

## Product Reading
TextifAI es plataforma first-party para autores. VaERL es semantic source of truth. Markdown es substrate editable author-facing. React/Tailwind es cara principal.

## Scope
Verificar workspace persistente 20ch, separar retry técnico de review semántica, añadir política de retry, iniciar retry focalizado y exponer estado author-facing.

## Files Changed
- `textifai/web_viewer/project_reader.py`
- `textifai/web_viewer/react_shell/src/api.ts`
- `textifai/web_viewer/react_shell/src/App.tsx`
- `scripts/dev/targeted_retry.py`
- `tests/test_textifai_targeted_retry_policy.py`
- `tests/fixtures/textifai/targeted_retry_policy/expected/*.json`

## SP106 Context
SP-106 creó `/home/david/TextifAIProjects/OnT_Spanish_20ch.textifai/` con manifest, 20 capítulos, graph y registry local.

## Persistent Workspace Verification
8872 lista el proyecto persistente y lo prefiere sobre mini fixture dev.

## Retry vs Review Classification
Retry técnico = capítulo `needs_retry`. Review semántica queda en Review Queue y no se reintenta.

## Ingestion Retry Policy
Manifest privado actualizado con `allow_auto_retries`, `max_retries_per_chapter`, `retry_only_technical_failures`, `ask_before_extra_costly_retry`.

## Targeted Retry Execution
Se inició retry focalizado sobre 15 capítulos con DeepSeek `deepseek-v4-flash`. No full novel rerun.

## Manifest / Status Update
Manifest privado actualizado con counts de capítulos, retry y review.

## Workspace Ingestion UX
Backend expone `workspace_status` con frases author-facing: capítulos detectados, listos, reintentados, pendientes y decisiones editoriales.

## Editor / Graph / Review Validation
Editor conserva 20 capítulos. Graph usa proyecto persistente. Review usa queue real.

## Private Decision Handoff
- `docs/handoffs/private/safepoint-106b_targeted-retry-policy/decision_handoff_private.md`

## Product Decision
Mantener retry focalizado técnico y no confundirlo con decisiones editoriales.

## Recommended Next Phase
SP-106C: consolidar resultados de retry cuando acabe, integrar artifacts retry en VaERL/graph, y mostrar CTA real en UI.

## What Worked
Proyecto persistente detectable; policy añadida; retry técnico iniciado; reports/tests añadidos.

## What Failed
Pipeline alto nivel no soporta `--chapter-ids`; se usó motor inferior `real_deepseek_e2e_dryrun.py`.

## Data Written
Manifest privado, writer outcome privado, reports privados del provider, reports commit-safe.

## Privacy / Non-committed Output
Proyecto `.textifai`, registry local, provider outputs y handoff privado no se commitean.

## Tests Added / Updated
`tests/test_textifai_targeted_retry_policy.py`.

## Validation Performed
Ver comandos en respuesta final.

## Safety Constraints
No source prose en reports commit-safe. No registry commit. No full rerun. No editor write-back.

## Known Limitations
Retry run puede seguir en curso; integración final de artifacts retry queda para fase siguiente si run largo no termina antes de cierre.

## Future Extensions
CTA operativo para retry, mini-ingestión por capítulo, Add to VaERL, `.txtfai` bundle.

## Runtime Changes
Backend expone `ingestion_policy` y `workspace_status`.

## Write-back
NO.

## Branch
`phase-1.3-ingestion-vaerl-hardening`
