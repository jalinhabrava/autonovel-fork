# SP-140 Handoff

## Resultado
SP-140 completó migración i18n de chrome hardcoded restante en `textifai/web_viewer/react_shell/src`, con foco en `App.tsx` y varios micro-slices seguros.

## Branch
- `phase-1.4-authoring-workbench-projectstore`

## Commits
- `3a4c114` — `sp-140a migrate app fallback chrome strings to i18n`
- `6e422df` — `sp-140b migrate graph edit draft chrome strings to i18n`
- `5c99f8b` — `sp-140c migrate app review inspector chrome strings to i18n`
- `af4f161` — `sp-140d migrate app graph chrome strings to i18n`
- `7b6cfd3` — `sp-140e migrate remaining app inspector chrome strings to i18n`
- `370bf9d` — `sp-140f migrate app codex graph route chrome strings to i18n`
- `b118460` — `sp-140g finalize arc i18n hardcoded string audit`

## Files touched
- `textifai/web_viewer/react_shell/src/App.tsx`
- `textifai/web_viewer/react_shell/src/graph/GraphNodeEditDraftModal.tsx`
- `textifai/web_viewer/react_shell/src/i18n/ui.ts`
- `tests/test_textifai_i18n_ui_strings.py`
- `docs/i18n/sp126-hardcoded-ui-string-audit.md`
- `docs/i18n/sp140-i18n-completion-audit.md`

## Validation
- `uv run python scripts/dev/textifai_doctor.py` ✅
- `uv run python -m unittest -v tests.test_textifai_i18n_ui_strings tests.test_textifai_react_shell_migration` ✅
- `bash scripts/dev/textifai_react_build.sh` ✅
- Generated bundles restored after build ✅

## What changed
- Added/expanded EN/ES keys for remaining safe UI chrome.
- Migrated fallback labels, route headers, graph/codex headers, inspector labels, and some project-row counts.
- Left payload, IDs, markdown, evidence excerpts, machine values, and heuristic/internal literals raw.

## Remaining raw by design
- `chapter_manifest`
- route/view IDs
- project/entity payload values
- markdown bodies and evidence excerpts
- internal scoring/heuristic literals like `20 capítulos`
- intentionally deferred mixed-content legacy strings

## Notes
- No generated bundles committed.
- `git status` ended clean.
- Handoff artifact is this file: `docs/i18n/sp140-handoff.md`
