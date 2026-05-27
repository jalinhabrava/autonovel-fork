# VaERL Entity Quality + Viewer Author UX Patch

## Product Reading
TextifAI debe comportarse como plataforma first-party author-facing: VaERL como source of truth, Markdown como substrate editable, y viewer/wiki/graph como proyecciones útiles. Si el nodo canónico abre el gemelo pobre, si el graph no navega bien, o si el writer outcome grita retry técnico donde no lo hay, producto pierde confianza.

## Scope
Provider-free hardening sobre resultado SP-095. Sin provider calls, sin write-back, sin editor Markdown.

## Files Changed
- `textifai/import_review/vaerl_markdown_materializer.py`
- `textifai/web_viewer/project_reader.py`
- `textifai/web_viewer/static/index.html`
- `textifai/web_viewer/static/app.js`
- `textifai/web_viewer/static/styles.css`
- `scripts/dev/sp096_vaerl_entity_quality_viewer_ux_patch.py`
- `tests/test_textifai_vaerl_entity_quality_and_viewer_ux_patch.py`
- `tests/fixtures/textifai/spanish_20ch_e2e/expected/*after_sp095.json`
- `tests/fixtures/textifai/viewer_wiring/expected/*after_sp095.json`

## SP095 Context
SP-095 validó dirección VaERL → Markdown → viewer real, pero dejó retry sobredimensionado, chapter integrity 19/20, cross-kind duplicates, y graph/backlink dañados por stale link targets.

## Retry Classification Patch
- `needs_retry` queda reservado a fallos técnicos reales.
- `ch_019` queda como retry técnico real.
- capítulos antes marcados retry sin fallo técnico se reclasifican a revisión/warnings en auditoría SP-096.

## Entity Kind / Canonicalization Patch
- Exact duplicate cross-kind ahora prefieren path canónico por prioridad de kind.
- `character` gana a `concept` para labels exactos como Sera/Ren/narrador/abuelo/Beld-san/Gaheris.
- No se borran entidades agresivamente; se redirige resolución canónica y targets de wikilinks.

## Alias Merge Candidates
- Separados en:
  - redirects automáticos exactos cross-kind
  - merge candidates review-only
  - rejected unsafe merges

## Graph Link Resolution Patch
- Root cause corregida: map de links ahora usa final path tras dedupe.
- Resultado medido:
  - unresolved links: `401 -> 40`
  - orphan notes: `283 -> 38`

## Chapter Count Integrity
- `20` seleccionados.
- `19` representados antes.
- `20` representados después con placeholder técnico seguro para `ch_019`.

## Writer Outcome Loading in Viewer
- Viewer backend ahora puede leer `99_System/writer_outcome.json` como fallback explícito.
- Overview vuelve a exponer resumen author-facing.

## Graph Layout Patch
- Center force reforzado.
- Characters/high-degree más centrados.
- Menos ruido de labels.
- Edge labels contextuales.

## Node Drag / Position Persistence
- Drag manual de nodos.
- Pin implícito al drag.
- Persistencia localStorage por proyecto.
- Reset limpia posiciones locales.

## Internal Navigation
- Back/Forward interno en panel graph detail.
- Recent nodes visibles.
- Navegación interna no depende de browser back global.

## Legend / Color System
- Palette por kind aplicada a nodos y leyenda.
- Border/status diferenciado para ready / needs_review / needs_retry.

## Node Bio / Summary Display
- Si note correcto tiene `## Summary` / `## Facts`, viewer lo muestra.
- Si falta resumen, muestra empty state: “No summary yet. This node may need enrichment.”

## LLM Enrichment Contract
- Solo contrato/report. No provider calls.
- Inputs: canonical label, facts, relationships, chapter/source refs, review state.
- Outputs: short bio, role, traits, key relationships, chapter range, evidence refs, confidence.

## Regenerated Runtime Artifacts
- Nuevo runtime privado: ver report de decisión SP-096 para ruta exacta bajo `/tmp/textifai_private_provider_runs/sp096_vaerl_entity_quality_viewer_ux_patch/`.
- Regenerado provider-free desde outputs SP-095.

## Viewer Manual Review Server
- Servidor levantado en `http://127.0.0.1:8873/`.
- Host `0.0.0.0`.
- Endpoints `/`, `/api/projects`, `/api/projects/<id>`, `/graph`, `/note` verificados 200.

## Private Decision Handoff
Subir primero a ChatGPT, en este orden:
1. `docs/handoffs/private/safepoint-096_vaerl-entity-quality-viewer-ux-patch/decision_handoff_private.md`
2. `docs/handoffs/private/safepoint-096_vaerl-entity-quality-viewer-ux-patch/retry_classification_private.md`
3. `docs/handoffs/private/safepoint-096_vaerl-entity-quality-viewer-ux-patch/entity_kind_canonical_private.md`
4. `docs/handoffs/private/safepoint-096_vaerl-entity-quality-viewer-ux-patch/alias_merge_candidates_private.md`
5. `docs/handoffs/private/safepoint-096_vaerl-entity-quality-viewer-ux-patch/graph_link_resolution_private.md`
6. `docs/handoffs/private/safepoint-096_vaerl-entity-quality-viewer-ux-patch/node_bio_summary_private.md`
7. `docs/handoffs/private/safepoint-096_vaerl-entity-quality-viewer-ux-patch/viewer_quality_after_patch_private.md`

## Commit-safe vs Private Decision Handoff
Commit-safe contiene métricas, reglas, decisiones y rutas. Privado contiene ejemplos reales y contexto suficiente para juzgar calidad narrativa/UX sin depender de `/tmp`.

## Product Decision
`vaerl_entity_quality_viewer_ux_patch_ready_for_manual_review`

## Recommended Next Phase
Phase 1.3.M-b5c-5a — Markdown editor + patch proposal queue + targeted semantic enrichment.

## What Worked
- Fix determinista de target consistency.
- Drop grande en unresolved/orphans.
- Chapter integrity recuperada a 20 representados.
- Viewer UX base mejorada sin provider calls.

## What Failed
- No se resuelve todo merge semántico ambiguo automáticamente.
- `ch_019` sigue requiriendo retry técnico real.

## Data Written
- Reports commit-safe SP-096.
- Runtime privado SP-096 en `/tmp`.
- Private summaries SP-096 bajo `docs/handoffs/private/`.

## Privacy / Non-committed Output
- No se commitea `/tmp`.
- No se commitea `docs/handoffs/private/**`.
- No prompts raw, no provider outputs raw, no source prose largo.

## Tests Added / Updated
- `tests/test_textifai_vaerl_entity_quality_and_viewer_ux_patch.py`

## Validation Performed
- SP-096 unit test suite.
- Regression suites para SP-095/SP-094/materialization/viewer/provider onboarding.
- Endpoint checks viewer SP-096.

## Safety Constraints
- Provider-free.
- No OpenAI.
- No DeepSeek.
- No write-back.
- No browser automation.

## Known Limitations
- Alias semánticos no exactos siguen requiring review.
- Persistencia de posiciones es localStorage cliente, no compartida.

## Future Extensions
- Markdown editor in-viewer.
- Patch proposal queue.
- Targeted bio enrichment.
- Persistencia opcional de layout en artifacts review-only.

## Runtime Changes
- Nuevo script provider-free SP-096.
- Nuevo runtime regenerado sin tocar SP-095 in-place.

## Write-back
NO.

## Branch
`phase-1.3-ingestion-vaerl-hardening`
