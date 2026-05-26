from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from textifai.import_review.viewer_graph_adapter import adapt_ingestion_graph_to_viewer_graph
from textifai.web_viewer.project_reader import ProjectCatalog, read_artifact, read_project


FIXTURE_ROOT = Path("tests/fixtures/textifai/viewer_preflight")
INPUT_ROOT = FIXTURE_ROOT / "input"
EXPECTED_ROOT = FIXTURE_ROOT / "expected"

REPORT_FILES = [
    "ingestion_graph_output_inventory_after_sp085.json",
    "viewer_expected_graph_contract_after_sp085.json",
    "viewer_adapter_validation_after_sp085.json",
    "viewer_smoke_test_report_after_sp085.json",
    "viewer_preflight_decision_after_sp085.json",
    "writer_facing_viewer_expectation_after_sp085.json",
    "viewer_preflight_general_pipeline_learnings_after_sp085.json",
    "viewer_preflight_provider_specific_learnings_after_sp085.json",
]

WRITER_FORBIDDEN_TERMS = [
    "chunk",
    "reduction",
    "parseable",
    "provider",
    "finish_reason",
    "json",
    "token",
    "api",
    "telemetry",
]

PRIVATE_FORBIDDEN_TERMS = [
    "sk-",
    "BEGIN PRIVATE",
    "provider_response_raw",
    "final_prompt_sent",
    "system_prompt.md",
    "user_prompt.md",
    "王者の杖",
    "セラ",
]


class TextifAIViewerPreflightTests(unittest.TestCase):
    def test_sample_ingestion_graph_parses(self):
        payload = _read_json(INPUT_ROOT / "sample_ingestion_graph_after_sp085.json")
        self.assertEqual(payload["schema_version"], "textifai.ingestion_graph.fixture.v1")
        self.assertEqual(payload["source"], "synthetic")
        self.assertGreaterEqual(len(payload["characters"]), 1)
        self.assertGreaterEqual(len(payload["relations"]), 1)
        self.assertTrue(any(chapter["status"] == "needs_review" for chapter in payload["chapters"]))

    def test_adapter_produces_viewer_nodes_edges(self):
        payload = _read_json(INPUT_ROOT / "sample_ingestion_graph_after_sp085.json")
        graph = adapt_ingestion_graph_to_viewer_graph(payload)

        self.assertGreaterEqual(len(graph["nodes"]), 6)
        self.assertGreaterEqual(len(graph["edges"]), 4)
        for node in graph["nodes"]:
            self.assertTrue(node["id"])
            self.assertTrue(node["label"])
            self.assertIn(node["kind"], {"character", "place", "concept", "object", "event", "unresolved", "chapter"})
            self.assertIn("role", node)
            self.assertIn("tags", node)
        for edge in graph["edges"]:
            self.assertTrue(edge["source"])
            self.assertTrue(edge["target"])
            self.assertTrue(edge["label"])
            self.assertEqual(edge["type"], edge["label"])

    def test_source_refs_preserved_when_present(self):
        payload = _read_json(INPUT_ROOT / "sample_ingestion_graph_after_sp085.json")
        graph = adapt_ingestion_graph_to_viewer_graph(payload)

        self.assertTrue(all(node.get("source_refs") for node in graph["nodes"]))
        self.assertTrue(all(edge.get("source_refs") for edge in graph["edges"]))

    def test_missing_optional_fields_do_not_crash_adapter(self):
        graph = adapt_ingestion_graph_to_viewer_graph(
            {
                "source": "synthetic",
                "nodes": [{"id": "concept:minimal", "label": "Minimal", "kind": "concept"}],
                "edges": [],
            }
        )

        self.assertEqual(graph["nodes"][0]["id"], "concept:minimal")
        self.assertEqual(graph["nodes"][0]["status"], "ready")
        self.assertIn("node_without_source_refs:concept:minimal", graph["metadata"]["warnings"])

    def test_reports_parse_and_are_privacy_safe(self):
        for name in REPORT_FILES:
            payload = _read_json(EXPECTED_ROOT / name)
            text = json.dumps(payload, ensure_ascii=False)
            self.assertIn("assessment", payload)
            for forbidden in PRIVATE_FORBIDDEN_TERMS:
                self.assertNotIn(forbidden, text)
            secret = os.environ.get("DEEPSEEK_API_KEY")
            if secret:
                self.assertNotIn(secret, text)

    def test_expected_viewer_graph_fixture_parses(self):
        payload = _read_json(EXPECTED_ROOT / "sample_viewer_graph_after_sp085.json")
        self.assertIn("nodes", payload)
        self.assertIn("edges", payload)
        self.assertIn("metadata", payload)
        self.assertGreater(len(payload["nodes"]), 0)
        self.assertGreater(len(payload["edges"]), 0)

    def test_writer_facing_expectation_has_no_internal_terms(self):
        payload = _read_json(EXPECTED_ROOT / "writer_facing_viewer_expectation_after_sp085.json")
        text = json.dumps(payload, ensure_ascii=False).casefold()

        for term in WRITER_FORBIDDEN_TERMS:
            self.assertNotIn(term.casefold(), text)
        self.assertIn("writer_can_see", payload)
        self.assertEqual(payload["primary_action"]["action_id"], "review_story_map")

    def test_viewer_smoke_report_parses(self):
        report = _read_json(EXPECTED_ROOT / "viewer_smoke_test_report_after_sp085.json")
        self.assertTrue(report["viewer_exists"])
        self.assertTrue(report["adapter_used"])
        self.assertEqual(report["console_errors"], [])
        self.assertGreater(report["nodes_renderizable"], 0)
        self.assertGreater(report["relations_renderizable"], 0)

    def test_decision_enum_valid(self):
        decision = _read_json(EXPECTED_ROOT / "viewer_preflight_decision_after_sp085.json")
        valid = {
            "viewer_preflight_ready_for_20_chapter_e2e",
            "viewer_preflight_ready_with_minor_warnings",
            "viewer_preflight_needs_compatibility_patch",
            "viewer_preflight_blocked",
        }
        self.assertIn(decision["assessment"], valid)
        self.assertFalse(decision["blocker"])
        self.assertEqual(decision["provider_calls"], "NO")

    def test_current_viewer_can_load_ingestion_graph_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "runs" / "sample_viewer_project"
            system = project / "99_System"
            system.mkdir(parents=True)
            sample = (INPUT_ROOT / "sample_ingestion_graph_after_sp085.json").read_text(encoding="utf-8")
            (system / "ingestion_graph.json").write_text(sample, encoding="utf-8")
            (system / "obsidian_import.json").write_text(json.dumps({"work": {"title": "Synthetic"}, "chapters": [], "entities": []}), encoding="utf-8")
            (system / "review_queue.json").write_text(json.dumps({"item_count": 0, "items": []}), encoding="utf-8")

            catalog = ProjectCatalog([root / "runs"])
            project_ref = catalog.get_project(catalog.list_projects()[0]["project_id"])
            payload = read_project(project_ref)
            artifact = read_artifact(project_ref, "ingestion_graph.json")

        self.assertEqual(artifact["kind"], "json")
        self.assertGreaterEqual(len(payload["graph"]["nodes"]), 6)
        self.assertGreaterEqual(len(payload["graph"]["edges"]), 4)
        self.assertTrue(any(node.get("source_refs") for node in payload["graph"]["nodes"]))


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
