# SP-120 i18n completion pass

- scope: strict i18n audit and closeout for React shell after modularization; no product feature work
- i18n catalog/locales: `/home/david/projects/autonovel-fork/textifai/web_viewer/react_shell/src/i18n/ui.ts`; locales `es` and `en`; fallback locale `en`; `t(key, params)` interpolation enabled
- strings covered: shell, navigation, AI, ingestion, project hub, graph toolbar, graph inspector, canon/story alias, graph draft modal, fullscreen labels, editor right-panel compatibility labels, save/dirty/reanalysis strings, review action labels, evidence labels
- allowlist: technical literals only; see `/home/david/projects/autonovel-fork/tests/fixtures/textifai/i18n/expected/ui_hardcoded_strings_allowlist_after_sp119.json`
- remaining intentional hardcoded strings: technical ids (`project_store`, `chapter_manifest`), report/test names, schema/debug keys, API routes, product name `TextifAI`, `VaERL`, package/bundle paths, SP markers
- runtime verification: viewer started on `0.0.0.0:8872` via `uv run python -m textifai.web_viewer.server --root /home/david/TextifAIProjects --host 0.0.0.0 --port 8872`; `GET /` returned `200`; `GET /api/projects` returned `200`; `GET /api/projects/<id>` returned `200`
- tests/build: `tests.test_textifai_i18n_ui_strings` passed; `tests.test_textifai_editor_dirty_state_ux` passed; `tests.test_textifai_chapter_writeback` passed; `tests.test_textifai_mdxeditor_spike` passed; React build re-run after strict audit
- reports: updated SP-119 expected fixtures under `/home/david/projects/autonovel-fork/tests/fixtures/textifai/i18n/expected`
- blockers: no known functional blockers; remaining work only if team wants deeper automated scan across all JSX literals in non-key modules
