# SP-118A Handoff — React shell modularization + i18n foundation

## Scope
Mechanical extraction of React shell sections from `App.tsx` into dedicated modules and setup of `src/i18n/ui.ts` translation catalog with locale fallback.

## Modules extracted
- `textifai/web_viewer/react_shell/src/shell/AppShell.tsx`
- `textifai/web_viewer/react_shell/src/shell/navigation.ts`
- `textifai/web_viewer/react_shell/src/common/ui.tsx`
- `textifai/web_viewer/react_shell/src/modules/project/ProjectHubView.tsx`
- `textifai/web_viewer/react_shell/src/modules/ingestion/IngestionView.tsx`
- `textifai/web_viewer/react_shell/src/modules/review/ReviewQueueView.tsx`
- `textifai/web_viewer/react_shell/src/modules/graph/GraphView.tsx`
- `textifai/web_viewer/react_shell/src/modules/canon/CanonVaerlView.tsx`
- `textifai/web_viewer/react_shell/src/modules/editor/EditorView.tsx`
- `textifai/web_viewer/react_shell/src/modules/ai/AIStudioView.tsx`

## i18n system
- `textifai/web_viewer/react_shell/src/i18n/ui.ts`
- locale type and catalog (`es`, `en`), browser/localStorage resolution, fallback to `en`, helper `t(key)`.

## What did not change
No provider calls. No ingestion changes. No write-back architecture changes. No graph regeneration. No review regeneration. No backend redesign.

## Runtime verification
Blocked in current environment:
- `uv` command unavailable in shell.
- Local `node` is `v12.22.9`; Vite build requires newer runtime.

## Tests/build attempted
- Attempted unittest commands through `uv run python -m unittest ...` (blocked: `uv: command not found`).
- Attempted `npm run build` in `textifai/web_viewer/react_shell` (blocked by Node runtime syntax support).

## Remaining blockers
1. Provide `uv` binary in PATH or project bootstrap script for test execution.
2. Run build/tests using modern Node runtime (>= Vite-supported).
3. Complete final pass replacing remaining product-facing hardcoded strings still inside some extracted modules.

## Recommendation for SP-118B
Proceed after runtime/toolchain unblock. Keep Graph inspector fiche editor work inside `modules/graph/*` and feed all new labels through `src/i18n/ui.ts` from day one.
