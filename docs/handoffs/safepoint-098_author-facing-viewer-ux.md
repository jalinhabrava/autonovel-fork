# Author-Facing Viewer UX

## Product Reading
TextifAI debe sentirse como plataforma first-party para autores: VaERL como source of truth, Markdown como substrate editable y viewer/wiki/graph/node detail como superficies narrativas centrales. El autor no debe ver roots, project ids, copy dev-facing ni nodos duplicados pobres cuando existe ficha canónica mejor.

## Scope
Patch provider-free sobre SP-097. Sin provider calls, sin write-back, sin D3, sin cambios en `package.json`/`package-lock.json`, sin instalar Open Design ni skills globales.

## Files Changed
- `textifai/web_viewer/project_reader.py`
- `textifai/web_viewer/static/index.html`
- `textifai/web_viewer/static/app.js`
- `tests/test_textifai_author_facing_viewer_ux.py`
- `tests/fixtures/textifai/viewer_author_ux/expected/*.json`
- `docs/handoffs/safepoint-098_author-facing-viewer-ux.md`

## SP097 Context
SP-097 estabilizó server/graph contract/edge identity, pero el viewer seguía mostrando selector dev-facing, mezcla de idiomas, rutas técnicas y duplicados `Concepts/Sera.md` / `Concepts/Ren.md` en la experiencia principal.

## Project Selector Author Mode
- `viewer_project` pasa a ser proyecto preferido cuando existe.
- Selector deja de usar copy sobre served root/filesystem browsing.
- `viewer_project` se marca como proyecto de autor.
- `markdown_vault` queda visible como artefacto técnico con detalles colapsados.
- Header principal deja de mostrar root/path técnica como copy primaria.

## i18n / String Dictionary
- Se añade `I18N = { en, es }`, `state.locale`, `t()` y fallback `en`.
- Estrategia: `work.language -> navigator.language -> en`.
- Tabs, selector, wiki base, controles core de graph y mensajes author-facing pasan por dictionary.

## Canonical Node Resolution
- Backend deriva `canonical_redirects` y `canonical_note_redirects` cuando faltan en runtime.
- Prioridad de kind exact-label: `character > place > object > event > concept > review > chapter`.
- `Concepts/Sera.md -> Characters/Sera.md`.
- `Concepts/Ren.md -> Characters/Ren.md`.
- Frontend aplica redirects en graph click, wiki links, backlinks, outgoing note links, recent y detail.

## Node Detail Information Architecture
- Ficha author-facing prioriza:
  1. Bio / Summary
  2. Key facts
  3. Story relationships
  4. Appearances / evidence
  5. Markdown links
  6. Technical details collapsed
- Summary/facts se leen desde la nota canónica correcta.
- Technical details se mueven a `<details>` colapsado.

## Graph Layout / Edge Labels
- Layout inicial mejora con spiral+jitter seed, center bias, bounds menos rígidos y auto-fit con padding.
- Reset limpia posiciones persistidas.
- Edge labels se ocultan por defecto y se muestran en hover; detail panel cubre contexto narrativo.

## Broken Actions Cleanup
- `Open Review Context` solo aparece cuando existe contexto real.
- `Open note` se sustituye por affordance author-facing (`View in wiki`) y se oculta cuando es redundante.
- Acciones placebo se eliminan de ficha primaria.

## Open Design Tooling Status
- Repo local `/tmp/textifai_dev_tools/open-design`: ausente.
- `codex` CLI: presente.
- `skills` CLI: ausente.
- MCP Open Design: no disponible en este entorno.
- Se usan docs/checklists locales y se deja rehidratación dev-only documentada, con aprobación requerida para instalar skills globales.

## Private Decision Handoff
Subir a ChatGPT en este orden:
1. `docs/handoffs/private/safepoint-098_author-facing-viewer-ux/decision_handoff_private.md`
2. `docs/handoffs/private/safepoint-098_author-facing-viewer-ux/canonical_node_resolution_private.md`
3. `docs/handoffs/private/safepoint-098_author-facing-viewer-ux/viewer_ux_before_after_private.md`
4. `docs/handoffs/private/safepoint-098_author-facing-viewer-ux/open_design_tooling_private.md`

## Product Decision
`author_facing_viewer_ux_ready_with_open_design_pending`

## Recommended Next Phase
Manual review author-facing sobre `8872`; luego decidir entre ACK explícito para `d3-force` o fase de editor Markdown + patch proposal queue.

## What Worked
- Default `viewer_project` autor-céntrico.
- i18n mínimo sin dependencia externa.
- Redirects canónicos exact-label eliminan apertura de concept duplicate para Sera/Ren.
- Detail panel ya muestra summary/facts author-facing.
- Edge labels dejan de ensuciar grafo por defecto.

## What Failed
- Open Design real no puede usarse hoy porque repo local y MCP no están presentes.
- Custom SVG sigue teniendo techo inferior a D3-force para evolución futura.

## Data Written
- Reports commit-safe bajo `tests/fixtures/textifai/viewer_author_ux/expected/`.
- Private handoffs SP-098 bajo `docs/handoffs/private/safepoint-098_author-facing-viewer-ux/`.

## Privacy / Non-committed Output
- No se commitean `/tmp/**` ni `docs/handoffs/private/**`.
- No provider outputs, no prompts privados, no source prose largo, no API keys.

## Tests Added / Updated
- `tests/test_textifai_author_facing_viewer_ux.py`

## Validation Performed
- Nueva suite author-facing UX.
- Regression suites SP-097 / SP-096 / SP-095 preflight / viewer wiring / materialization / provider onboarding.
- Endpoint checks en `8872`.

## Safety Constraints
- Provider-free.
- No OpenAI.
- No DeepSeek.
- No write-back.
- No browser automation.
- No package changes.
- No global Codex skill installation.

## Known Limitations
- Redirects exact-label no resuelven alias semántico ambiguo.
- Open Design queda pendiente de rehidratación aprobada.
- Layout mejora sin D3, pero no iguala motor dedicado.

## Future Extensions
- Rehidratación dev-only de Open Design.
- ACK separado para `d3-force`.
- Editor Markdown + patch proposal queue.
- Enrichment LLM de bios cuando se apruebe.

## Runtime Changes
- Viewer estable sigue en `0.0.0.0:8872` con runtime SP-096.
- Frontend y backend aplican redirects y copy author-facing sobre mismo runtime.

## Write-back
NO.

## Branch
`phase-1.3-ingestion-vaerl-hardening`
