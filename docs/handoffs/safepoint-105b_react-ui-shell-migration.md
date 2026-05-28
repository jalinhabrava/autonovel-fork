# React UI Shell Migration Foundation

## Continuity
Current detected safepoint before this increment: `safepoint-105a_review-workspace-cleanup.md`.
This increment continues that line as **SP-105B** without replacing domain logic.

## Product Reading
TextifAI sigue siendo semantic story engine first-party. VaERL y artifacts reales siguen siendo source of truth; la nueva UI solo cambia shell visual y módulos author-facing.

## What Changed
- Root UI now defaults to a new React + TypeScript + Tailwind shell.
- Legacy viewer remains intact inside `index.html` and can run in embedded compatibility mode.
- Complex modules preserve current working logic by reuse, not rewrite.

## Reuse Strategy
- APIs preserved: `/api/projects`, `/api/projects/<id>`, `/graph`, `/note`, `/artifact`, `/api/ingestion/*`.
- Legacy graph/wikI/canon runtime preserved and embeddable with `?embed=1&view=...&project=...`.
- Project discovery, review artifacts, VaERL/canon parsing, ingestion config/jobs, and markdown loading stay in Python/backend + existing JS runtime.

## New UI Surface
- Project Hub
- Ingestion
- Codex / VaERL
- Graph
- Review Queue
- Editor
- Story Bible
- Ask Canon

## Scope Kept Out
- No graph renderer rewrite.
- No LLM calls.
- No fake persistence.
- No ingestion contract rewrite.
- No manifest/.txtfai final packaging yet.

## Risks
- React shell currently reuses legacy Graph and Story Bible through embedded compatibility view.
- Codex and Review are first-pass product shells over current payloads, not final ergonomic pass.
- Tailwind/Vite stack lives in isolated subdir, not yet folded into repo-wide frontend toolchain.

## Validation
- `npm install && npm run build` in `textifai/web_viewer/react_shell`
- Python test suites for legacy + migration compatibility.

## Next Safe Step
- Extract reusable read-only adapters from legacy `app.js` into typed frontend adapters.
- Replace embedded legacy Story Bible / Graph progressively once parity is proven.
- Formalize `manifest.json` project contract in Project Hub.
