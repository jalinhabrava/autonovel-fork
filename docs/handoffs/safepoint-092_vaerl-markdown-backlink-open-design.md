# VaERL Markdown Materialization + Backlink Index MVP + Open Design Dev Tooling Spike

## Product Reading
TextifAI es plataforma first-party para autores. VaERL sigue siendo semantic source of truth; Markdown es substrate editable; views son proyecciones. Esta fase convierte arquitectura SP-091 en MVP provider-free: VaERL -> Markdown vault, wikilinks/backlinks, graph index, y disciplina UI/UX con Open Design solo como dev tooling.

## Scope
- Implementar materializer provider-free.
- Implementar backlink/wikilink graph index provider-free.
- Crear fixture sintética y vault commiteable.
- Crear dirección de diseño y checklist UI.
- Auditar Open Design como tooling dev externo.
- Crear reports/tests/handoff.

## Files Changed
- `textifai/import_review/vaerl_markdown_materializer.py`
- `textifai/import_review/markdown_graph_index.py`
- `docs/textifai-design-direction.md`
- `docs/textifai-ui-review-checklist.md`
- `tests/test_textifai_markdown_materialization.py`
- `tests/test_textifai_design_tooling.py`
- `tests/fixtures/textifai/markdown_materialization/**`
- `tests/fixtures/textifai/design_tooling/**`
- `docs/handoffs/safepoint-092_vaerl-markdown-backlink-open-design.md`

## SP091 Context
SP-091 definió plataforma first-party por capas y eligió como siguiente fase materializar Markdown + backlinks. Quartz/Obsidian quedan como referencia/patrones, no workflow externo principal.

## Existing Markdown Materialization Inventory
Existían piezas valiosas: `obsidian.json_import`, parser frontmatter/wikilinks, VaERL index/backlinks, review_queue y viewer notes/artifacts. Gap: no había materializer VaERL-first provider-free ni graph index Markdown independiente para wiki/editor.

## VaERL Markdown Materializer
Nuevo `textifai.import_review.vaerl_markdown_materializer` crea carpetas `Characters`, `Places`, `Events`, `Objects`, `Concepts`, `Chapters`, `Reviews`, `System`. Cada nota incluye frontmatter, título, summary, facts, relationships, evidence pointers, wikilinks y Review Notes. Edits no cambian VaERL silenciosamente: generan patch proposals.

## Backlink / Wikilink Graph Index
Nuevo `textifai.import_review.markdown_graph_index` lee Markdown materializado y genera notes, outgoing wikilinks, backlinks, tags, nodes, edges, orphan notes, unresolved links, degree counts y local graph.

## Synthetic Fixture / Vault
Se creó fixture sintética VaERL y vault sintético commiteable en `tests/fixtures/textifai/markdown_materialization/expected/sample_vault_after_sp091/`. Sin datos privados.

## Viewer Markdown Index Integration
No se hizo UI wiring final. Se dejó contrato/report para que viewer/wiki futuro pueda consumir manifest/index: paths, frontmatter, tags, backlinks, degree, local graph.

## TextifAI Design Direction
`docs/textifai-design-direction.md` define principios author-first, narrative KB, Markdown/wiki central, status visible, AI grounded, debug secondary, hierarchy, empty states, CTA clarity y accessibility basics.

## Open Design Dev Tooling Audit
Open Design fue clonado en `/tmp/textifai_dev_tools/open-design` para auditoría externa. No se instaló en repo ni runtime. README lo presenta como alternativa local-first con CLIs/agentes, skills y design systems. License verificada en clone: Apache-2.0. Recomendación: tooling dev externo/referencia, no dependencia producto.

## Open Design Dev-only Install Plan
Plan recomienda `/tmp/textifai_dev_tools/open-design`, `git clone`, `corepack`, `pnpm install`, uso local. No cambios package.json/package-lock. Rollback: `rm -rf /tmp/textifai_dev_tools/open-design`.

## UI Review Checklist
`docs/textifai-ui-review-checklist.md` cubre dashboard, graph readability, wiki/browser, node detail, editor/AI suite, author-facing language, debug secondary, no internal terms, responsive layout.

## Lean Legacy Cleanup
Reusar frontmatter/note_path/review semantics. Adaptar obsidian_import a proyección. Deprecar debug JSON como UX primaria, external Obsidian workflow, fallback ambiguo eterno.

## Product Decision
`vaerl_markdown_backlink_mvp_ready_with_design_warnings`

## Recommended Next Phase
Phase 1.3.M-b5c-4v — Wire VaERL Markdown Wiki/Backlink Index into Viewer MVP

## What Worked
- MVP materializer implementado.
- Backlink graph index implementado.
- Fixture vault sintética generada.
- Open Design audit externo sin contaminar repo.
- Diseño UI tratado como producto, no decoración final.

## What Failed
- Viewer UI aún no consume index/manifest.
- Edit-to-VaERL patch proposals definidos, no implementados.
- Open Design no instalado completo; solo clone/audit por seguridad.

## Data Written
- Código provider-free.
- Fixture vault sintética.
- Reports commit-safe.
- Docs diseño/checklist.
- Clone Open Design en `/tmp` no commiteado.

## Privacy / Non-committed Output
No provider calls. No private prose. No `/tmp` commit. No Open Design repo commit. No package changes.

## Tests Added / Updated
- `tests/test_textifai_markdown_materialization.py`
- `tests/test_textifai_design_tooling.py`

## Validation Performed
- Suites nuevas SP-092 y regresiones pedidas ejecutadas.
- `py_compile` módulos nuevos.
- `git status --short` y `git diff --stat` revisados.

## Safety Constraints
No provider calls. No OpenAI. No DeepSeek. No retry. No full-source. No write-back. No `html-anything`. Open Design dev-only.

## Known Limitations
- Parser YAML es simple y suficiente para el MVP/test; puede reemplazarse por parser robusto luego.
- UI viewer/wiki no conectada todavía.
- Patch proposal desde edits Markdown aún pendiente.

## Future Extensions
- Wire index al viewer.
- Wiki browser first-party.
- Edit-to-VaERL patch proposal queue.
- Graph layout/readability upgrade.
- Open Design design sprint externo.

## Runtime Changes
Nuevos módulos provider-free disponibles; no cambia runtime existente si no se invocan.

## Write-back
NO.

## Branch
`phase-1.3-ingestion-vaerl-hardening`
