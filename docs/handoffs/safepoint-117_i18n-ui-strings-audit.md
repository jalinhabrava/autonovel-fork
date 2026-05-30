# Safepoint 117 / 118A — i18n UI strings audit and modular shell foundation

- Scope: extracted frontend UI i18n module, shell/common components, and first wave of React screen modules.
- i18n system found: backend `textifai/i18n.py` (`en`,`es`, fallback `en`); frontend now mirrors this via `src/i18n/ui.ts`.
- Strings audited: navigation, editor save/reanalysis states, review actions, evidence labels, and screen titles touched in modularized views.
- Keys added: centralized in `textifai/web_viewer/react_shell/src/i18n/ui.ts`.
- Locales covered: `es`, `en`; fallback to `en` when key missing.
- Modularization landed: `src/shell/*`, `src/common/ui.tsx`, and section modules under `src/modules/*`.
- Remaining intentional hardcoded: some legacy descriptive copy in still-inline sections and technical placeholders.
- Tests/build: `tests/test_textifai_i18n_ui_strings.py`; `npm run build` passes.
- Runtime verification: production build green after extraction; app composes through `AppShell` and section modules.
