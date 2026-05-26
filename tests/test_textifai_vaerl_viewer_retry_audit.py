from __future__ import annotations

import json
import os
import unittest
from pathlib import Path


VIEWER_ROOT = Path("tests/fixtures/textifai/viewer_audit/expected")
RETRY_ROOT = Path("tests/fixtures/textifai/retry_audit/expected")

VIEWER_REPORTS = [
    "existing_viewer_obsidian_inventory_after_sp087.json",
    "previous_graph_detail_capabilities_after_sp087.json",
    "current_ingestion_graph_projection_audit_after_sp087.json",
    "obsidian_import_vs_ingestion_graph_gap_after_sp087.json",
    "node_detail_panel_gap_after_sp087.json",
    "viewer_overview_writer_outcome_gap_after_sp087.json",
    "viewer_artifacts_role_audit_after_sp087.json",
    "graph_relationship_quality_audit_after_sp087.json",
    "vaerl_viewer_contract_recommendation_after_sp087.json",
    "vaerl_viewer_retry_audit_decision_after_sp087.json",
    "vaerl_viewer_general_pipeline_learnings_after_sp087.json",
    "vaerl_viewer_provider_specific_learnings_after_sp087.json",
]

RETRY_REPORTS = [
    "sp087_retry_classification_audit_after_sp087.json",
    "retry_vs_review_semantics_after_sp087.json",
    "technical_to_user_status_correction_plan_after_sp087.json",
]


class TextifAIVaERLViewerRetryAuditTests(unittest.TestCase):
    def test_all_reports_parse_and_are_private_safe(self):
        for path in [*(VIEWER_ROOT / name for name in VIEWER_REPORTS), *(RETRY_ROOT / name for name in RETRY_REPORTS)]:
            payload = _read_json(path)
            text = json.dumps(payload, ensure_ascii=False)
            self.assertIn("assessment", payload)
            self.assertNotIn("BEGIN PRIVATE", text)
            self.assertNotIn("final_prompt_sent.md", text)
            self.assertNotIn("provider_response_raw.txt", text)
            self.assertNotIn("王者の杖", text)
            secret = os.environ.get("DEEPSEEK_API_KEY")
            if secret:
                self.assertNotIn(secret, text)

    def test_decision_enum_valid(self):
        decision = _read_json(VIEWER_ROOT / "vaerl_viewer_retry_audit_decision_after_sp087.json")
        self.assertIn(
            decision["assessment"],
            {
                "vaerl_viewer_retry_audit_ready_for_patch",
                "vaerl_viewer_retry_audit_ready_with_open_questions",
                "vaerl_viewer_retry_audit_blocked_missing_artifacts",
                "vaerl_viewer_retry_audit_inconclusive",
            },
        )
        self.assertEqual(decision["provider_calls"], "NO")
        self.assertEqual(decision["write_back"], "NO")

    def test_retry_audit_contains_twenty_chapters_and_reclassifies_false_retries(self):
        audit = _read_json(RETRY_ROOT / "sp087_retry_classification_audit_after_sp087.json")
        self.assertEqual(audit["chapter_count"], 20)
        self.assertEqual(len(audit["rows"]), 20)
        self.assertEqual(audit["current_counts"]["needs_retry"], 13)
        self.assertEqual(audit["likely_true_retries"], 0)
        self.assertGreater(audit["recommended_counts"]["needs_review"], 0)
        self.assertTrue(all("chapter_id" in row for row in audit["rows"]))

    def test_retry_semantics_define_required_statuses(self):
        semantics = _read_json(RETRY_ROOT / "retry_vs_review_semantics_after_sp087.json")
        statuses = semantics["statuses"]
        for status in ("ready", "ready_with_warnings", "needs_review", "needs_retry", "failed"):
            self.assertIn(status, statuses)
        principles = " ".join(semantics["principles"])
        self.assertIn("low-density does not automatically mean retry", principles)
        self.assertIn("retry reserved for technical or incomplete failures", principles)

    def test_correction_plan_does_not_convert_low_density_to_retry(self):
        plan = _read_json(RETRY_ROOT / "technical_to_user_status_correction_plan_after_sp087.json")
        self.assertIn("low_density_mapping", plan)
        self.assertNotIn("automatic needs_retry", plan["low_density_mapping"])
        self.assertIn("needs_review", plan["low_density_mapping"])
        self.assertTrue(plan["no_implementation_in_this_phase"])

    def test_viewer_contract_requires_real_labels_and_forbids_runtime_synthetic_labels(self):
        contract = _read_json(VIEWER_ROOT / "vaerl_viewer_contract_recommendation_after_sp087.json")
        self.assertEqual(contract["node_contract"]["canonical_label"], "required real canonical or surface label")
        self.assertIn("runtime real outputs must preserve real canonical_label/surface forms", contract["runtime_policy"])

        projection = _read_json(VIEWER_ROOT / "current_ingestion_graph_projection_audit_after_sp087.json")
        self.assertFalse(projection["runtime_uses_real_labels"])
        self.assertGreater(projection["synthetic_label_count"], 0)
        self.assertIn("committed fixtures", contract["runtime_policy"])

    def test_provider_specific_report_does_not_define_core_viewer_contract(self):
        report = _read_json(VIEWER_ROOT / "vaerl_viewer_provider_specific_learnings_after_sp087.json")
        self.assertFalse(report["viewer_dependency_on_deepseek"])
        self.assertIn("provider-agnostic", report["core_logic_boundary"])
        text = json.dumps(report, ensure_ascii=False)
        self.assertNotIn("node_contract", text)
        self.assertNotIn("edge_contract", text)


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
