from __future__ import annotations

import json
from pathlib import Path

from textifai.import_review.contracts import PromotionPlan, PromotionResult
from textifai.import_review.staging_loader import StagingImportBundle


def write_import_audit(
    *,
    bundle: StagingImportBundle,
    plan: PromotionPlan,
    result: PromotionResult,
) -> Path:
    audit_root = Path(bundle.vault_root) / "99_System" / "import_review"
    audit_root.mkdir(parents=True, exist_ok=True)
    audit_path = audit_root / f"{plan.plan_id}.json"
    payload = {
        "plan_id": plan.plan_id,
        "bundle": {
            "vault_root": bundle.vault_root,
            "staging_root": bundle.staging_root,
            "manifest_path": bundle.manifest_path,
            "coverage_summary": bundle.coverage_summary,
            "warnings": bundle.warnings,
        },
        "plan": _serialize_plan(plan),
        "result": _serialize_result(result),
    }
    audit_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return audit_path


def _serialize_plan(plan: PromotionPlan) -> dict:
    return {
        "plan_id": plan.plan_id,
        "decisions": [decision.__dict__ for decision in plan.decisions],
        "conflicts": list(plan.conflicts),
        "requires_confirmation": plan.requires_confirmation,
        "warnings": list(plan.warnings),
    }


def _serialize_result(result: PromotionResult) -> dict:
    return {
        "plan_id": result.plan_id,
        "promoted_paths": list(result.promoted_paths),
        "pending_drafts": list(result.pending_drafts),
        "rejected_drafts": list(result.rejected_drafts),
        "blocked_drafts": list(result.blocked_drafts),
        "audit_entries": [entry.__dict__ for entry in result.audit_entries],
        "warnings": list(result.warnings),
    }
