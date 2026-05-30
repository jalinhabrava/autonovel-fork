# Generated Artifacts Policy

## Source Artifacts

- Python source under `textifai/`, `scripts/`, and `tests/`.
- React source under `textifai/web_viewer/react_shell/src/`.
- Docs under `docs/`.

## Generated Artifacts

- `textifai/web_viewer/static/react-shell/app.js`
- `textifai/web_viewer/static/react-shell/app.css`
- `textifai/web_viewer/static/react-shell/` build output

## Policy

- Regenerate static assets with `cd textifai/web_viewer/react_shell && npm run build`.
- Stage generated assets only when intentionally refreshing viewer bundle.
- Do not edit generated bundle files by hand.
- Avoid accidental artifact noise by checking `git status --short` after builds.
