# TextifAI Tooling Quickstart

## Prerequisites

- Python 3.12
- `uv`
- Node.js `>=22 <23` and `npm` 10.x
- SQLite stdlib from Python

## Command Rules

- Always run Python via `uv run python`.
- Never use bare `python`.
- Use `uv run python -m unittest ...` for tests.
- Use `uv run python -m textifai...` for module entrypoints.

## React Shell

- React shell path: `textifai/web_viewer/react_shell`
- React Node policy: `>=22 <23`
- Non-interactive Codex shells may not load `nvm`
- Install dependencies: `cd textifai/web_viewer/react_shell && npm ci`
- Fallback install: `cd textifai/web_viewer/react_shell && npm install`
- Preferred build entrypoint: `scripts/dev/textifai_react_build.sh`
- Do not run bare `npm run build` if Node version is uncertain
- Wrapper loads `~/.nvm/nvm.sh`, honors `.nvmrc`, and fails hard on old Node
- Direct `npm run build` is safe only after confirming `node -v` satisfies `>=22 <23`
- Vite outputs to `textifai/web_viewer/static/react-shell/`.

## Viewer

- Start local viewer: `uv run python -m textifai.web_viewer.server --root <project> --host 127.0.0.1 --port 8872`
- Use `127.0.0.1` for local-only access.
- Use `0.0.0.0` when Windows/WSL needs remote browser access.
- Confirm `GET /`, `GET /api/projects`, and `GET /api/projects/<id>` return HTTP 200.

## Tests

- `uv run python -m unittest -v tests.test_textifai_tooling_baseline`
- `uv run python -m unittest -v tests.test_textifai_project_store_architecture`

## Doctor

- Run: `uv run python scripts/dev/textifai_doctor.py`
- Checks `uv`, Python context, imports, Node/npm, React `.nvmrc`, package engines, React-ready Node compatibility, generated bundle, and viewer module.
- Doctor prints `react_build_ready=false` when current shell Node is not compatible.
- Doctor points React builds to `scripts/dev/textifai_react_build.sh`.

## Troubleshooting

- Bare `python` missing: rerun with `uv run python`.
- Viewer already on 8872: stop stale process before restart.
- Vite bundle changed but server stale: rebuild with `scripts/dev/textifai_react_build.sh`.
- Missing `node_modules`: run `npm ci` in React shell.
- Old Node in Codex shell: `source ~/.nvm/nvm.sh && cd textifai/web_viewer/react_shell && nvm install && nvm use`
- Lock mismatch: keep `package-lock.json` in sync with `npm ci`.
- Generated bundle noise: only stage `textifai/web_viewer/static/react-shell/*` when intentionally rebuilt.
