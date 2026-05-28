# React UI Target Parity

## Product Reading
TextifAI es plataforma first-party para autores. VaERL sigue siendo semantic source of truth y Markdown el substrate editable author-facing. Esta fase convierte la UI React/Tailwind en cara principal visual del producto, siguiendo el wireframe objetivo.

## Scope
- Implementar paridad visual estructural con `TextifAI_UI_TARGET_WIREFRAME.jsx`.
- Mantener APIs, loaders, artifacts, review queue y legacy graph/wiki sin rewrite destructivo.

## Files Changed
- `textifai/web_viewer/react_shell/src/App.tsx`
- `textifai/web_viewer/react_shell/src/api.ts`
- `textifai/web_viewer/react_shell/package.json`
- `textifai/web_viewer/react_shell/package-lock.json`
- reports/tests de SP-105C

## SP105B Context
SP-105B creó shell React funcional y legacy embed. SP-105C reemplaza el look básico por el diseño objetivo: neutral shell, rounded container, header, sidebar target e iconos lucide.

## Target Wireframe Used
`C:/Users/ladir/Downloads/TextifAI_UI_TARGET_WIREFRAME.jsx` usado como fuente visual principal. No se commitea el archivo de referencia.

## Design System Parity
Implementados `Shell`, `TopBar`, `Button`, `Metric`, `SidebarNav`, `StatusChip`, `ProjectRow`, `DecisionCard`, `EntityRecordTable`, `InspectorCard`, `LegacyEmbed` con clases Tailwind del target.

## Shell Parity
Outer `min-h-screen bg-neutral-100 text-neutral-900 p-4 md:p-6`, contenedor `max-w-7xl rounded-3xl bg-white shadow-xl overflow-hidden border`, header `bg-neutral-50`, grid `grid-cols-12 min-h-[760px]`.

## Navigation / Icons
Nav usa `lucide-react`: `BookOpen`, `Upload`, `Network`, `GitBranch`, `Inbox`, `PenLine`, `FileText`, `MessageSquareText`.

## Screen Parity
Las ocho pantallas target existen y usan TopBar/cards/grids target. Project Hub/Ingestion/Codex/Review/Editor consumen datos reales. Graph/Story Bible quedan embebidas dentro de target shell.

## Real Data / API Adapters
Adapters creados para `/api/projects`, `/api/projects/<id>`, `/graph`, `/note`, `/artifacts`, `/api/ingestion/config`, `/api/ingestion/jobs`.

## Legacy Embed Boundaries
Graph y Story Bible usan `LegacyEmbed` con `?embed=1&view=...&project=...`. Legacy shell no es experiencia primaria.

## i18n Decision
Se prioriza paridad del target en inglés. Strings de shell React quedan en inglés temporalmente para evitar mezcla visual/textual; i18n completa queda para siguiente fase.

## Build / Runtime Validation
Validar con build React, tests SP-105C y endpoints `8872`.

## Private Decision Handoff
- `docs/handoffs/private/safepoint-105c_react-ui-target-parity/decision_handoff_private.md`

## Product Decision
`react_ui_target_parity_ready_for_manual_review`

## Recommended Next Phase
Reemplazar embeds legacy restantes con componentes React nativos, empezando por Story Bible o Graph inspector.

## What Worked
El shell target pudo conectarse a datos reales sin tocar backend ni romper APIs.

## What Failed
No se implementó renderer React de Graph ni editor completo, por seguridad de alcance.

## Data Written
Reports JSON SP-105C, tests SP-105C, handoffs público/privado.

## Privacy / Non-committed Output
No se commitea handoff privado ni target JSX original.

## Tests Added / Updated
- `tests/test_textifai_react_ui_target_parity.py`

## Validation Performed
Pendiente de validación final en esta fase.

## Safety Constraints
No provider calls. No write-back. No Open Design runtime dependency. No node_modules staged.

## Known Limitations
Legacy embed permanece en Graph y Story Bible.

## Future Extensions
Manifest picker real, `.txtfai`, native Graph renderer, native Story Bible, i18n completo.

## Runtime Changes
React shell añade `lucide-react` y `framer-motion` en package aislado del shell.

## Write-back
No write-back.

## Branch
`phase-1.3-ingestion-vaerl-hardening`
