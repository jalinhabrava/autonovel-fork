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

## SP-126B Progress Note
- App overview/workspace copy in `textifai/web_viewer/react_shell/src/App.tsx` migrated to i18n.
- `textifai/web_viewer/react_shell/src/modules/project/ProjectHubView.tsx` deferred because file had pre-existing dirty style/token changes before SP-126B started.
- Remaining hotspots: `ProjectHubView.tsx`, `GraphInspector.tsx`, `GraphToolbar.tsx`, `CanonVaerlView.tsx`, `EditorView.tsx`, `ReviewQueueView.tsx`, `IngestionView.tsx`, `AIStudioView.tsx`.

## SP-126C Dirty-File Triage

SP-126B commit `33da88df462e5fa407bd0edd9f87bd0c334e3281` is present on `origin/phase-1.4-authoring-workbench-projectstore`; no SP-126B push was required before triage.

No additional i18n slice was migrated in SP-126C. All preferred target files were dirty before SP-126C or tied to graph palette/style diffs, so migrating any one of them would mix i18n with unrelated visual or semantic-color work.

| File | Dirty before SP-126C | Diff nature | Recommendation |
| --- | --- | --- | --- |
| `textifai/web_viewer/react_shell/src/graph/GraphCanvas.tsx` | yes | graph palette/style extraction | do not touch in SP-126C |
| `textifai/web_viewer/react_shell/src/graph/GraphTheme.ts` | yes | graph semantic color indirection | do not touch in SP-126C |
| `textifai/web_viewer/react_shell/src/graph/GraphToolbar.tsx` | yes | graph chip palette/style changes; copy already uses `t(...)` | defer; only migrate later after graph style diffs land or are reverted |
| `textifai/web_viewer/react_shell/src/graph/GraphPalette.ts` | yes, untracked | new graph palette constants | do not touch in SP-126C |
| `textifai/web_viewer/react_shell/src/modules/ai/AIStudioView.tsx` | yes | style/token class changes; visible copy already uses `t(...)` | defer |
| `textifai/web_viewer/react_shell/src/modules/ingestion/IngestionView.tsx` | yes | style/token class changes; visible copy already uses `t(...)`; machine status remains raw | defer |
| `textifai/web_viewer/react_shell/src/modules/project/ProjectHubView.tsx` | yes | style/token class changes plus one existing Spanish note | defer |
| `textifai/web_viewer/react_shell/src/modules/canon/CanonVaerlView.tsx` | yes | style/token class changes in canon-sensitive module | defer |
| `textifai/web_viewer/react_shell/src/modules/canon/StoryAliasView.tsx` | yes | style/token class changes in canon-sensitive module | defer |

Deferred hotspots for later clean safepoints:

- `ProjectHubView.tsx` — migrate remaining user-facing note after style/token diff is resolved; keep `manifest.json` and `.txtfai` raw.
- `GraphInspector.tsx` — schedule as dedicated graph/canon i18n slice because inspector labels are larger and entity-sensitive.
- `CanonVaerlView.tsx` and `StoryAliasView.tsx` — schedule after canon module style diffs are clean.
- `AIStudioView.tsx` and `IngestionView.tsx` — revisit after style diffs are resolved; current visible copy already routes through i18n keys except machine/runtime values.

Assessment: `arc_i18n_dirty_worktree_triage_ready`.
