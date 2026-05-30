# Safepoint 119 — Tooling Baseline + Environment Doctor

## Scope

- Tooling/devex/documentation safety pass only.
- No product behavior, provider, ingestion, or write-back changes.

## Detected Baseline

- Python: `3.12` via `.python-version`.
- Node: `22.22.2` in current environment.
- npm: `10.9.7` in current environment.
- React shell: `textifai/web_viewer/react_shell`.
- Viewer server: `textifai.web_viewer.server`.

## Version Hints Added

- Documented Python/uv command contract.
- Documented Node/npm test/build expectations.
- Kept versions as tested-in-environment notes, not hard upgrades.

## Doctor Script

- Added `scripts/dev/textifai_doctor.py`.
- Checks `uv`, Python context, imports, Node/npm, React shell files, `node_modules`, and generated bundle path.
- Does not call provider APIs or mutate project state.

## Dev Quickstart

- Added `docs/dev/tooling.md`.
- Includes viewer start command, build command, tests, and troubleshooting.

## Packaging Notes

- Added `docs/architecture/textifai_packaging_dependencies.md`.
- Covers `.textifai`, `.txtfai`, SQLite, runtime vs build-time deps, and optional provider keys.

## Generated Artifacts Policy

- Added `docs/architecture/generated_artifacts_policy.md`.
- Documents `textifai/web_viewer/static/react-shell/` as generated output.

## Validation

- Tests added in `tests/test_textifai_tooling_baseline.py`.
- Fixture reports added under `tests/fixtures/textifai/tooling/expected/`.

## Remaining Blockers

- Need targeted validation of doctor script and React build.
