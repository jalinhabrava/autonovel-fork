# TextifAI Tooling Quickstart

## Prerequisites

- Python 3.12
- `uv`
- Node.js 22.x and `npm` 10.x
- SQLite stdlib from Python

## Command Rules

- Always run Python via `uv run python`.
- Never use bare `python`.
- Use `uv run python -m unittest ...` for tests.
- Use `uv run python -m textifai...` for module entrypoints.

## React Shell

- React shell path: `textifai/web_viewer/react_shell`
- Install dependencies: `cd textifai/web_viewer/react_shell && npm ci`
- Fallback install: `cd textifai/web_viewer/react_shell && npm install`
- Build static bundle: `cd textifai/web_viewer/react_shell && npm run build`
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
- Checks `uv`, Python context, imports, Node/npm, React shell, generated bundle, and viewer module.

## Troubleshooting

- Bare `python` missing: rerun with `uv run python`.
- Viewer already on 8872: stop stale process before restart.
- Vite bundle changed but server stale: rebuild `npm run build`.
- Missing `node_modules`: run `npm ci` in React shell.
- Lock mismatch: keep `package-lock.json` in sync with `npm ci`.
- Generated bundle noise: only stage `textifai/web_viewer/static/react-shell/*` when intentionally rebuilt.
