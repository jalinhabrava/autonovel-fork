from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from textifai.import_review.chunking_reduction_preflight import map_technical_signals_to_writer_status
from textifai.import_review.viewer_graph_adapter import adapt_ingestion_graph_to_viewer_graph, build_runtime_ingestion_graph
from textifai.web_viewer.project_reader import ProjectRef, read_project

VIEWER_ROOT = Path("tests/fixtures/textifai/viewer_patch/expected")
RETRY_ROOT = Path("tests/fixtures/textifai/retry_patch/expected")
VIEWER_REPORTS = [
    "vaerl_runtime_graph_projection_patch_after_sp088.json",
    "obsidian_compatible_vaerl_projection_after_sp088.json",
    "viewer_overview_patch_after_sp088.json",
    "node_detail_data_contract_patch_after_sp088.json",
    "relationship_projection_patch_after_sp088.json",
    "artifacts_debug_role_patch_after_sp088.json",
    "real_runtime_projection_revalidation_after_sp088.json",
    "viewer_manual_review_after_projection_patch_after_sp088.json",
    "vaerl_projection_patch_decision_after_sp088.json",
    "vaerl_projection_general_pipeline_learnings_after_sp088.json",
    "vaerl_projection_provider_specific_learnings_after_sp088.json",
]
RETRY_REPORTS = [
    "retry_review_mapping_patch_after_sp088.json",
    "sp087_reclassified_writer_outcome_after_sp088.json",
    "fail_only_rerun_plan_patch_after_sp088.json",
    "writer_outcome_mapping_patch_after_sp088.json",
]
FORBIDDEN_WRITER_TERMS = ["chunk", "reduction", "parseable", "source_ref", "provider", "finish_reason", "json", "continuation", "patch", "model", "profile", "token", "api", "telemetry", "run_id", "failure_mode"]


def _synthetic_chapter_payload() -> dict:
    ref = {"source_id": "synthetic", "chapter_id": "ch_001", "chunk_id": "c1", "char_start": 10, "char_end": 20}
    return {
        "chapter_id": "ch_001",
        "characters": [{"canonical": "Ada", "surface": "Ada Bright", "aliases": ["Bright"], "facts": ["keeps the archive"], "source_refs": [ref]}],
        "places": [{"canonical": "Farmhouse", "surface": "old farmhouse", "facts": ["meeting place"], "source_refs": [ref]}],
        "objects": [{"canonical": "Copper Key", "surface": "copper key", "facts": ["opens the cellar"], "source_refs": [ref]}],
        "events": [{"canonical": "Cellar Discovery", "surface": "the discovery", "facts": ["Ada finds the key"], "source_refs": [ref]}],
        "relations": [{"from_canonical": "Ada", "to_canonical": "Copper Key", "relation_label": "finds", "relation_category": "object_link", "facts": ["found near the cellar"], "source_refs": [ref]}],
    }


class TextifAIVaERLProjectionPatchTests(unittest.TestCase):
    def test_runtime_graph_projection_uses_real_labels_and_preserves_fields(self):
        runtime = build_runtime_ingestion_graph(chapter_payloads=[_synthetic_chapter_payload()], chapter_status_map={"ch_001": "needs_review"})
        graph = adapt_ingestion_graph_to_viewer_graph(runtime)
        labels = {node["label"] for node in graph["nodes"]}
        self.assertIn("Ada", labels)
        self.assertIn("Copper Key", labels)
        ada = next(node for node in graph["nodes"] if node["label"] == "Ada")
        self.assertIn("Bright", ada["aliases"])
        self.assertIn("keeps the archive", ada["facts"])
        self.assertTrue(ada["source_refs"])
        self.assertEqual(graph["metadata"]["graph_summary"]["synthetic_label_count"], 0)

    def test_relation_label_is_semantic_not_generic_when_present(self):
        runtime = build_runtime_ingestion_graph(chapter_payloads=[_synthetic_chapter_payload()])
        graph = adapt_ingestion_graph_to_viewer_graph(runtime)
        self.assertEqual(graph["edges"][0]["label"], "finds")
        self.assertNotIn(graph["edges"][0]["label"], {"appears_in", "happens_at"})
        ada = next(node for node in graph["nodes"] if node["label"] == "Ada")
        self.assertTrue(ada["entity"]["relationships_out"])

    def test_project_reader_overview_reads_writer_outcome_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "viewer_project"
            system = root / "99_System"
            system.mkdir(parents=True)
            graph = build_runtime_ingestion_graph(chapter_payloads=[_synthetic_chapter_payload()])
            graph["metadata"] = {
                "source": "synthetic",
                "writer_outcome": {
                    "total_chapters": 1,
                    "chapters_ready": 0,
                    "chapters_ready_with_warnings": 0,
                    "chapters_needing_retry": 0,
                    "chapters_needing_review": 1,
                    "chapters_failed": 0,
                    "primary_action": {"label": "Review results"},
                    "secondary_action": {"label": "Later"},
                    "user_summary": "1 chapter processed.",
                },
            }
            (system / "ingestion_graph.json").write_text(json.dumps(graph), encoding="utf-8")
            project = read_project(ProjectRef(project_id="p", name="p", kind="local", root=root, system_root=system))
            self.assertEqual(project["overview"]["chapters_processed"], 1)
            self.assertEqual(project["overview"]["chapters_needing_review"], 1)
            self.assertEqual(project["overview"]["primary_action"]["label"], "Review results")

    def test_retry_mapping_keeps_low_density_out_of_needs_retry(self):
        result = map_technical_signals_to_writer_status(
            final_chapter_valid=True,
            has_internal_warnings=True,
            has_retryable_failures=False,
            has_semantic_thinness=True,
            unrecoverable_failure=False,
        )
        self.assertEqual(result["chapter_status"], "needs_review")

    def test_retry_mapping_reserves_retry_for_technical_failures(self):
        result = map_technical_signals_to_writer_status(
            final_chapter_valid=True,
            has_internal_warnings=False,
            has_retryable_failures=True,
            has_semantic_thinness=False,
            unrecoverable_failure=False,
        )
        self.assertEqual(result["chapter_status"], "needs_retry")

    def test_reports_parse_and_are_privacy_safe(self):
        for path in [*(VIEWER_ROOT / name for name in VIEWER_REPORTS), *(RETRY_ROOT / name for name in RETRY_REPORTS)]:
            payload = json.loads(path.read_text(encoding="utf-8"))
            text = json.dumps(payload, ensure_ascii=False).casefold()
            self.assertIn("assessment", payload)
            self.assertNotIn("sk-", text)
            self.assertNotIn("final_prompt_sent", text)
            self.assertNotIn("provider_response_raw", text)
            self.assertNotIn("王者の杖", text)
            secret = os.environ.get("DEEPSEEK_API_KEY")
            if secret:
                self.assertNotIn(secret.casefold(), text)

    def test_sp087_reclassified_outcome_and_rerun_plan(self):
        outcome = json.loads((RETRY_ROOT / "sp087_reclassified_writer_outcome_after_sp088.json").read_text(encoding="utf-8"))
        rerun = json.loads((RETRY_ROOT / "fail_only_rerun_plan_patch_after_sp088.json").read_text(encoding="utf-8"))
        self.assertEqual(outcome["previous_counts"]["needs_retry"], 13)
        self.assertEqual(outcome["new_counts"].get("needs_retry", 0), 0)
        self.assertEqual(len(outcome["chapter_level_mapping"]), 20)
        self.assertFalse(rerun["retryable_chapters_only_true_technical_retry"])
        self.assertEqual(rerun["expected_calls"], 0)

    def test_writer_outcome_report_contains_no_forbidden_terms(self):
        payload = json.loads((RETRY_ROOT / "writer_outcome_mapping_patch_after_sp088.json").read_text(encoding="utf-8"))
        writer_text = json.dumps(
            {
                "if_no_retries": payload["if_no_retries"],
                "if_reviews": payload["if_reviews"],
                "if_retries": payload["if_retries"],
                "example_writer_summary": payload["example_writer_summary"],
                "example_primary_action": payload["example_primary_action"],
                "example_secondary_action": payload["example_secondary_action"],
            },
            ensure_ascii=False,
        ).casefold()
        for term in FORBIDDEN_WRITER_TERMS:
            self.assertNotIn(term.casefold(), writer_text)
        self.assertEqual(payload["if_no_retries"]["primary_action"], "Review results")


if __name__ == "__main__":
    unittest.main()
