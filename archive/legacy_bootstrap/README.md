# Legacy Bootstrap Archive

This folder keeps the pre-structured bootstrap pipeline for safety and historical inspection.

Archived here:
- staging-oriented bootstrap orchestration
- legacy normalization-plan pipeline
- legacy story builder
- tests that exercised those archived paths

Reason for archival:
- the active product pipeline now runs through `textifai.import_review.structured_bootstrap_v1`
- `textifai.obsidian.setup.prepare_obsidian_project()` no longer falls back to the archived staging path
- keeping the legacy code under `textifai/` made it too easy to reintroduce stale calls

Active bootstrap path now lives in:
- `textifai/import_review/structured_bootstrap_v1.py`
- `textifai/import_review/model_router.py`
- `textifai/import_review/provider_snapshot.py`
- `textifai/import_review/model_advisor.py`
- `textifai/import_review/empirical_ranker.py`
- `textifai/obsidian/json_import.py`
- `textifai/obsidian/setup.py`
