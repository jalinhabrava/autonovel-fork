# TextifAI Packaging Dependencies

## Dependency Classes

- Dev dependencies: `uv`, Python tooling, `node`, `npm`, Vite, TypeScript, React shell deps.
- Runtime dependencies: Python 3.12, SQLite stdlib, project source, generated static bundle.
- Build-time dependencies: `uv` and `npm` for development builds, Vite for bundle generation.
- Optional provider dependencies: OpenAI, Anthropic, FAL, ElevenLabs keys for configured online flows only.

## Local Project Data

- Future packaged apps should keep project state under `.textifai/`.
- Bundle format should remain `.txtfai` for portable project packaging.
- SQLite stays core for local persistence and index storage.

## React Bundle Strategy

- React source lives in `textifai/web_viewer/react_shell/`.
- Build output lives in `textifai/web_viewer/static/react-shell/`.
- React build policy is Node `>=22 <23`.
- Non-interactive Codex shells may miss `nvm`; use `scripts/dev/textifai_react_build.sh` for Vite builds.
- End users should not need Node if static bundle ships with runtime.

## Python Runtime

- Packaged executable should embed Python runtime or require documented Python install path.
- Local viewer and editor must run without provider keys.
- Ingestion and reanalysis may require provider keys later if configured.

## Future Vector Backend

- Vector backend remains pluggable.
- Packaging should not hard-wire specific external vector service.
