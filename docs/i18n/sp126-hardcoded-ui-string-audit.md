# SP-126A Hardcoded UI String Audit

## Scope
Scanned `textifai/web_viewer/react_shell/src` for user-visible string literals and i18n gaps.

## Files scanned
- `textifai/web_viewer/react_shell/src/App.tsx`
- `textifai/web_viewer/react_shell/src/common/ui.tsx`
- `textifai/web_viewer/react_shell/src/graph/GraphInspector.tsx`
- `textifai/web_viewer/react_shell/src/graph/GraphNodeEditDraftModal.tsx`
- `textifai/web_viewer/react_shell/src/graph/GraphToolbar.tsx`
- `textifai/web_viewer/react_shell/src/modules/ai/AIStudioView.tsx`
- `textifai/web_viewer/react_shell/src/modules/canon/CanonVaerlView.tsx`
- `textifai/web_viewer/react_shell/src/modules/canon/EntityFicheView.tsx`
- `textifai/web_viewer/react_shell/src/modules/editor/EditorView.tsx`
- `textifai/web_viewer/react_shell/src/modules/ingestion/IngestionView.tsx`
- `textifai/web_viewer/react_shell/src/modules/project/ProjectHubView.tsx`
- `textifai/web_viewer/react_shell/src/modules/review/ReviewQueueView.tsx`
- `textifai/web_viewer/react_shell/src/shell/AppShell.tsx`
- `textifai/web_viewer/react_shell/src/shell/navigation.ts`
- `textifai/web_viewer/react_shell/src/i18n/ui.ts`

## Top hardcoded-string hotspots
- `textifai/web_viewer/react_shell/src/i18n/ui.ts` — current catalog plus locale foundation.
- `textifai/web_viewer/react_shell/src/App.tsx` — overview cards and several shell labels still hardcoded.
- `textifai/web_viewer/react_shell/src/graph/GraphInspector.tsx` — inspector chrome and fiche controls still contain raw copy.
- `textifai/web_viewer/react_shell/src/modules/*` — feature panels already use `t(...)` in many places, but some label text still lives inline.
- `textifai/web_viewer/react_shell/src/shell/AppShell.tsx` — shell chrome now uses i18n keys for local-first / project-status labels.

## Categories
### A. User-visible text that must become i18n
- Shell chrome labels, status chips, user menu labels, overview cards, navigation labels, action buttons, placeholders, and help copy.
- Remaining hardcoded text in `App.tsx` overview copy.
- Remaining graph/editor/review feature labels not already wired through `t(...)`.

### B. Safe internal/machine strings that must remain as-is
- Route IDs, section IDs, graph node IDs, review state machine values, API payload keys, project IDs, file paths, and VaERL schema fields.
- Technical tokens such as `manifest.json`, `.txtfai`, `run_id`, `editorKey`, `chapter_id`, and storage keys when used as machine identifiers.

### C. Test-only strings
- Fixture names and expectation labels under `tests/fixtures/textifai/i18n/expected/`.
- Audit assertions in `tests/test_textifai_i18n_ui_strings.py`.

### D. Ambiguous strings needing review
- Labels that look like product copy but may encode product concepts: `Canon`, `VaERL`, `Project Hub`, `AI Studio`, `Story Bible`.
- Strings that may be safe labels in UI but could be mistaken for internal tokens when they match machine-like names.

## Recommended migration order
1. Shell / navigation / top-bar chrome.
2. Overview board copy in `App.tsx`.
3. Graph inspector and graph toolbar labels.
4. Review queue and project hub labels.
5. Editor and deeper feature chrome.

## Risky strings not to translate
- `manifest.json`
- `.txtfai`
- `run_id`
- route/view IDs like `hub`, `ingest`, `review`, `graph`, `codex`, `editor`, `ask`, `overview`
- entity names, aliases, chapter titles, project names, graph node labels, and any VaERL schema keys

## Notes
- Existing i18n catalog already spans `en` and `es`.
- SP-126A added locale-resolution foundation and shell-key aliases; deeper feature migration remains for later safepoints.
