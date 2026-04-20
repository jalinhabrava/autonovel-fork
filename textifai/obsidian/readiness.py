from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from textifai.obsidian.source import open_obsidian_source
from vault.bootstrap import validate_vault


CONTEXT_SENSITIVE_FLOWS = (
    "editorial_structuring_flow",
    "validate_structuring_flow",
    "narration_handoff_flow",
    "review_handoff_flow",
    "structured_followup_flow",
    "world_lookup_flow",
    "context_search_flow",
    "scene_context_flow",
    "chapter_context_flow",
    "consistency_check_flow",
)

BOOTSTRAP_FLOWS = ("bootstrap_extract_flow",)


@dataclass(frozen=True)
class ObsidianOperationalReadiness:
    vault_root: str
    vault_exists: bool
    vault_valid: bool
    vault_validation_errors: list[str] = field(default_factory=list)
    source_reliability: str = "vault_reader_only"
    source_kind: str = "vault_markdown"
    snapshot_path: str | None = None
    operational_mode: str = "bootstrap_only"
    bridge_snapshot_required_for_grounded_responses: bool = True
    interaction_requires_context_refresh: bool = True
    can_bootstrap_project: bool = True
    can_query_vaerl: bool = False
    can_answer_degraded_contextual: bool = False
    can_answer_strong_grounded: bool = False
    can_evaluate_prompt_quality: bool = False
    allowed_flow_names: list[str] = field(default_factory=list)
    degraded_flow_names: list[str] = field(default_factory=list)
    blocked_flow_names: list[str] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def evaluate_obsidian_operational_readiness(
    vault_root: str | Path,
    *,
    require_fresh_bridge_for_grounded_responses: bool = True,
) -> ObsidianOperationalReadiness:
    root = Path(vault_root).expanduser().resolve()
    vault_exists = root.exists()
    validation_errors = [] if vault_exists else [f"vault_root_missing:{root}"]
    if vault_exists:
        validation_errors = validate_vault(root)
    vault_valid = not validation_errors

    if not vault_valid:
        return ObsidianOperationalReadiness(
            vault_root=str(root),
            vault_exists=vault_exists,
            vault_valid=False,
            vault_validation_errors=list(validation_errors),
            operational_mode="bootstrap_only",
            bridge_snapshot_required_for_grounded_responses=require_fresh_bridge_for_grounded_responses,
            can_bootstrap_project=True,
            can_query_vaerl=False,
            can_answer_degraded_contextual=False,
            can_answer_strong_grounded=False,
            can_evaluate_prompt_quality=False,
            allowed_flow_names=list(BOOTSTRAP_FLOWS),
            degraded_flow_names=[],
            blocked_flow_names=list(CONTEXT_SENSITIVE_FLOWS),
            required_actions=[
                "create_or_validate_vault",
                "install_obsidian_bridge_plugin",
                "generate_initial_snapshot",
            ],
            notes=["The vault is not operational yet; TextifAI should remain in bootstrap mode until initialization is complete."],
        )

    opened = open_obsidian_source(root)
    reliability = opened.status.reliability
    source_kind = opened.status.source_kind
    snapshot_path = opened.status.snapshot_path

    if reliability == "obsidian_bridge_snapshot_fresh":
        return ObsidianOperationalReadiness(
            vault_root=str(root),
            vault_exists=True,
            vault_valid=True,
            source_reliability=reliability,
            source_kind=source_kind,
            snapshot_path=snapshot_path,
            operational_mode="anchored_context_ready",
            bridge_snapshot_required_for_grounded_responses=require_fresh_bridge_for_grounded_responses,
            can_bootstrap_project=True,
            can_query_vaerl=True,
            can_answer_degraded_contextual=True,
            can_answer_strong_grounded=True,
            can_evaluate_prompt_quality=True,
            allowed_flow_names=[*BOOTSTRAP_FLOWS, *CONTEXT_SENSITIVE_FLOWS],
            degraded_flow_names=[],
            blocked_flow_names=[],
            required_actions=[],
            notes=["Fresh, valid bridge snapshot detected: strong grounding is available."],
        )

    if reliability in {"obsidian_bridge_snapshot_stale", "vault_reader_only"}:
        notes = []
        required_actions = []
        if reliability == "obsidian_bridge_snapshot_stale":
            notes.append("A bridge snapshot exists, but it is no longer fresh; refresh the export from Obsidian before relying on strong grounding.")
            required_actions.append("refresh_obsidian_bridge_snapshot_from_obsidian")
        else:
            notes.append("The vault is usable and VaERL can query it, but a fresh bridge snapshot is still required for strong grounding.")
            required_actions.extend(["install_or_enable_obsidian_bridge_plugin", "generate_fresh_obsidian_bridge_snapshot"])
        return ObsidianOperationalReadiness(
            vault_root=str(root),
            vault_exists=True,
            vault_valid=True,
            source_reliability=reliability,
            source_kind=source_kind,
            snapshot_path=snapshot_path,
            operational_mode="degraded_context",
            bridge_snapshot_required_for_grounded_responses=require_fresh_bridge_for_grounded_responses,
            can_bootstrap_project=True,
            can_query_vaerl=True,
            can_answer_degraded_contextual=True,
            can_answer_strong_grounded=not require_fresh_bridge_for_grounded_responses and reliability == "vault_reader_only",
            can_evaluate_prompt_quality=False,
            allowed_flow_names=[*BOOTSTRAP_FLOWS, *CONTEXT_SENSITIVE_FLOWS],
            degraded_flow_names=list(CONTEXT_SENSITIVE_FLOWS),
            blocked_flow_names=[],
            required_actions=required_actions,
            notes=notes,
        )

    return ObsidianOperationalReadiness(
        vault_root=str(root),
        vault_exists=True,
        vault_valid=True,
        source_reliability=reliability,
        source_kind=source_kind,
        snapshot_path=snapshot_path,
        operational_mode="degraded_context",
        bridge_snapshot_required_for_grounded_responses=require_fresh_bridge_for_grounded_responses,
        can_bootstrap_project=True,
        can_query_vaerl=True,
        can_answer_degraded_contextual=True,
        can_answer_strong_grounded=False,
        can_evaluate_prompt_quality=False,
        allowed_flow_names=[*BOOTSTRAP_FLOWS, *CONTEXT_SENSITIVE_FLOWS],
        degraded_flow_names=list(CONTEXT_SENSITIVE_FLOWS),
        blocked_flow_names=[],
        required_actions=["repair_obsidian_bridge_source"],
        notes=["Context is available, but bridge reliability is still too weak for strong evaluation."],
    )
