# Open Design-assisted Viewer Redesign Review

## Product Reading
TextifAI es plataforma first-party para autores. VaERL es source of truth semántico; Markdown es substrate editable author-facing. Viewer/wiki/graph/node detail deben sentirse como workspace narrativo, no como debug UI ni explorador de runtime.

## Scope
Fase ACK/análisis. Se usó Open Design como tooling dev y repo de patrones. No se implementó rediseño del viewer, no se llamó provider, no se tocó `package.json`/`package-lock.json`, no hubo write-back.

## Files Changed
- `tests/test_textifai_open_design_viewer_review.py`
- `tests/fixtures/textifai/open_design_viewer_review/expected/open_design_tooling_verification_after_sp098.json`
- `tests/fixtures/textifai/open_design_viewer_review/expected/viewer_design_review_after_sp098.json`
- `tests/fixtures/textifai/open_design_viewer_review/expected/viewer_redesign_brief_after_sp098.json`
- `tests/fixtures/textifai/open_design_viewer_review/expected/graph_engine_recommendation_after_sp098.json`
- `tests/fixtures/textifai/open_design_viewer_review/expected/open_design_viewer_review_decision_after_sp098.json`
- `docs/handoffs/safepoint-099_open-design-viewer-redesign.md`

## Open Design Verification
Open Design repo está en `/tmp/textifai_dev_tools/open-design`, commit `279da4f3`. Node usado: `/home/david/.nvm/versions/node/v24.16.0/bin/node`. Daemon validado en `http://127.0.0.1:7457` con `{"ok":true,"version":"0.8.0"}`. Codex lista MCP `open-design` como registrado. La herramienta MCP de esta sesión aún reportó daemon no reachable, por lo que puede requerir reinicio Codex/app para refrescar el proceso MCP.

## Viewer Current UX Diagnosis
SP-098 corrigió dirección, pero la UI sigue pareciendo técnica. `markdown_vault` compite con `viewer_project`, el grafo tiene riesgo de rails/bordes, ficha de nodo todavía mezcla signals técnicos, y acciones como `Open Review Context` / `Open in Canon` no son verbos claros para autor.

## Design Review
- Dashboard: debe ser home de operaciones narrativas, no resumen de artefactos.
- Project selector: debe mostrar un workspace activo y relegar runtime artifacts a dev drawer.
- Graph global: necesita composición limpia, filtros claros, inspector persistente y edge labels solo hover/selected.
- Graph local: debe ser modo explícito del nodo seleccionado, no checkbox ambiguo.
- Wiki: debe funcionar como KB narrativa con summaries/backlinks/canonical status.
- Node detail: debe abrir con bio/facts/relationships/evidence; metadata técnica colapsada.
- Review queue: debe convertirse en cola de decisiones de autor con impacto y evidencia.
- Dev mode: artifacts/frontmatter/paths deben salir de UX primaria.
- i18n/copy: dictionary existe, pero hay que cubrir toda copy primaria y evitar mezcla de idiomas.
- Markdown editor futuro: mostrar affordance disabled solo donde aporte contexto.

## Redesign Brief
SP-100 debe rediseñar el shell author-facing: header de workspace, selector minimalista, grafo como superficie principal, panel de nodo narrativo, wiki KB, review queue de decisiones y dev details colapsados. Criterios clave: active story workspace claro, `markdown_vault` fuera de author mode, Sera/Ren abren character con bio/facts, grafo sin rails dominantes, labels de edges ocultas, i18n completo y cero botones placebo.

## Graph Engine Recommendation
Recomendación: pedir ACK explícito para `d3-force` en SP-100. Mantener custom SVG reduce cambios de paquete, pero conserva deuda de fuerzas/layout. `d3-force` aporta center/charge/link/collision maduras con coste bajo y permite conservar SVG/DOM. Canvas/ForceGraph2D queda diferido por mayor impacto arquitectónico.

## Open Design / MCP Status
Open Design queda dev-only. No es dependencia runtime TextifAI. Repo, daemon y Codex MCP están instalados/registrados. Si el MCP no aparece en una sesión activa, reiniciar Codex/app y mantener daemon en `127.0.0.1:7457`.

## Private Decision Handoff
Private handoff gitignored creado:
- `docs/handoffs/private/safepoint-099_open-design-viewer-redesign/decision_handoff_private.md`

Upload order para ChatGPT review:
1. `docs/handoffs/private/safepoint-099_open-design-viewer-redesign/decision_handoff_private.md`
2. Este handoff commit-safe.
3. Reports JSON bajo `tests/fixtures/textifai/open_design_viewer_review/expected/`.

## Product Decision
`open_design_viewer_redesign_review_ready_for_sp100_planning`

## Recommended Next Phase
SP-100: Author Workspace Redesign. Pedir ACK de dependencia para `d3-force`; si se aprueba, implementar GraphEngine D3/SVG detrás de contrato actual. Si se rechaza, aplicar fallback custom pero aceptar riesgo visual.

## What Worked
- Open Design está instalado como tooling dev aislado.
- Reports separan design review, brief y recomendación de motor.
- No se tocó runtime viewer.
- No se añadió dependencia de producto.

## What Failed
- MCP registrado no respondió vía herramienta de esta sesión pese a daemon healthy; probable refresh/restart necesario.
- Sin screenshots/browser automation, review visual se basa en código, handoffs y patrones, no en captura real.

## Data Written
- 5 reports commit-safe en `tests/fixtures/textifai/open_design_viewer_review/expected/`.
- 1 test suite commit-safe.
- 1 handoff commit-safe.
- 1 handoff privado gitignored.

## Privacy / Non-committed Output
`docs/handoffs/private/**` queda no staged. `/tmp/textifai_dev_tools/open-design` no se commitea. No provider outputs, no source prose, no API keys.

## Tests Added / Updated
- `tests/test_textifai_open_design_viewer_review.py`

## Validation Performed
- `uv run python -m unittest -v tests.test_textifai_open_design_viewer_review`
- `git status --short`
- `git diff --stat`

## Safety Constraints
No provider calls. No DeepSeek. No OpenAI. No retry. No full-source. No write-back. No screenshots. No browser automation. No package changes.

## Known Limitations
Design review sin screenshot real. MCP activo en config pero herramienta actual puede necesitar reinicio. `d3-force` requiere ACK separado porque implica package change.

## Future Extensions
- D3-force GraphEngine v3.
- Dev mode drawer.
- Full i18n audit coverage.
- Open Design project artifact for clickable wireframe after ACK.
- Markdown editor/write-back phase.

## Runtime Changes
Ninguno en TextifAI. Open Design daemon dev puede correr en `127.0.0.1:7457`.

## Write-back
No write-back.

## Branch
`phase-1.3-ingestion-vaerl-hardening`
