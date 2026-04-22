from __future__ import annotations

from pathlib import Path

from textifai.bootstrap.contracts import BootstrapResult
from textifai.bootstrap.staging_writer import validate_staging_outputs


def validate_bootstrap_result(result: BootstrapResult) -> list[str]:
    errors: list[str] = []
    if result.normalization_plan is None:
        errors.append("Missing normalization plan.")
        return errors
    if not result.written_drafts:
        errors.append("No staged drafts were written.")
    manifest_path = _manifest_path(result)
    errors.extend(
        validate_staging_outputs(
            plan=result.normalization_plan,
            written_paths=result.written_drafts,
            manifest_path=manifest_path,
        )
    )
    return errors


def _manifest_path(result: BootstrapResult) -> Path:
    if result.normalization_plan is None:
        return Path(result.vault_root) / "99_Import_Staging" / "_manifests" / "missing.json"
    return Path(result.normalization_plan.target_staging_root) / "_manifests" / f"{result.normalization_plan.plan_id}.json"
