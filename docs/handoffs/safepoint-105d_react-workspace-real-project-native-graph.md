# React Workspace Real Project + Native Graph

## Product Reading
TextifAI es plataforma first-party para autores. VaERL es semantic source of truth; Markdown es substrate editable author-facing. React/Tailwind ya es cara principal del producto y debe operar sobre datos reales, no fixtures mínimas.

## Scope
- Diagnosticar carga real 20ch.
- Cambiar shell a workspace fullscreen responsive.
- Restaurar user card + settings modal.
- Limpiar Editor a capítulos/manuscrito.
- Reemplazar Graph legacy primario por superficie React nativa.
- Mantener APIs existentes, sin provider calls y sin write-back.

## Files Changed
- `textifai/web_viewer/react_shell/src/App.tsx`
- `textifai/web_viewer/react_shell/src/api.ts`
- `textifai/web_viewer/static/react-shell/app.js`
- `textifai/web_viewer/static/react-shell/app.css`
- `tests/test_textifai_react_workspace_real_project.py`
- `tests/test_textifai_react_ui_target_parity.py`
- `tests/fixtures/textifai/react_workspace_real_project/expected/*.json`

## SP105C Context
SP-105C logró paridad visual inicial con target wireframe, pero dejó Graph/Story Bible como embeds legacy y el layout seguía centrado con ancho máximo.

## Real 20ch Project Loading
Runtime real SP-095 de 20 capítulos está documentado, pero no existe actualmente en `/tmp`. El servidor 8872 expone SP-096 con nombre 20ch pero payload de 2 capítulos.

## Project Selection
React shell añade `choosePreferredProject(...)`: prioriza `chapter_count >= 20`, metadata 20ch y `recommended`. Si solo hay fixture reducida, la selecciona con warning visible y no la presenta como base UX final.

## Fullscreen Responsive Workspace
Shell usa `h-screen`, `w-full`, `max-w-none`, main scroll interno y sidebar estable. Se elimina cap duro `max-w-7xl` para aprovechar viewport completo.

## User Card / Settings Flow
Settings primarios viven en user card abajo izquierda. Click abre dropdown; Ajustes abre modal central con Apariencia, Idioma, Proyecto y Dev/debug. Sin persistencia falsa.

## Editor Chapter-only Scope
Editor consume `chapterNotes = notes.filter(isChapterNote)`. Primaries quedan excluidos de Editor y pertenecen a Codex/VaERL, Graph o Story Bible.

## Editor Fullscreen Mode
Botón Pantalla completa activa modo fijo. Sidebar/lista se oculta y panel derecho de contexto se conserva.

## Native React Graph Surface
Graph primario renderiza SVG React nativo desde `/api/projects/<id>/graph`, con filtros por tipo, canvas central, selección por click, inspector derecho y controles author-facing.

## Node Note Edit Affordance
Inspector de Graph expone `Editar`; abre modal/drawer draft/read-only placeholder. Guardado real queda para SP-106 drafts/patch queue. No write-back.

## Story Bible Legacy Boundary
Story Bible permanece como embed transicional visualmente envuelto. Graph ya no es legacy primario. Conversión Story Bible queda para fase posterior.

## i18n Consistency
Editor, Graph y Ajustes usan español consistente. Navegación conserva labels target de SP-105C parcialmente en inglés por continuidad visual.

## Build / Runtime Validation
Build React ejecutado tras `npm install`; output generado en `textifai/web_viewer/static/react-shell/`.

## Private Decision Handoff
- `docs/handoffs/private/safepoint-105d_react-workspace-real-project-native-graph/decision_handoff_private.md`

## Product Decision
`blocked_missing_real_20ch_project`

## Recommended Next Phase
Restaurar runtime SP-095 20ch o registrar artifact equivalente sin provider calls; luego revisión manual UX sobre 20 capítulos reales y conversión nativa de Story Bible.

## What Worked
- Shell fullscreen usable.
- Settings flow junto al usuario.
- Editor separado de primaries.
- Graph nativo mínimo sobre payload real.

## What Failed
No se pudo cargar runtime real 20ch porque el viewer_project SP-095 ya no existe en `/tmp`.

## Data Written
Reports SP-105D, tests SP-105D, handoff público, handoff privado gitignored y build React.

## Privacy / Non-committed Output
No se stagea handoff privado ni `/tmp`. No se commitea runtime provider ni source prose.

## Tests Added / Updated
- `tests/test_textifai_react_workspace_real_project.py`
- `tests/test_textifai_react_ui_target_parity.py`

## Validation Performed
Build React, test SP-105D, regresiones solicitadas y endpoints 8872.

## Safety Constraints
No provider calls. No DeepSeek. No OpenAI. No retry. No write-back. No screenshots. No browser automation.

## Known Limitations
- Base real 20ch ausente.
- Graph layout SVG simple, no force simulation.
- Story Bible sigue legacy boundary.
- Settings no persisten.

## Future Extensions
- Restaurar/registrar runtime 20ch.
- Story Bible React nativo.
- Draft patch queue SP-106.
- i18n completo.
- Graph force layout nativo si necesario.

## Runtime Changes
React shell rebuild. Sin cambios backend.

## Write-back
No write-back.

## Branch
`phase-1.3-ingestion-vaerl-hardening`
