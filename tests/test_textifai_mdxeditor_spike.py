from __future__ import annotations

import json
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "textifai" / "mdxeditor_spike"
EXPECTED_ROOT = FIXTURE_ROOT / "expected"
APP_TSX = REPO_ROOT / "textifai" / "web_viewer" / "react_shell" / "src" / "App.tsx"
REACT_PACKAGE = REPO_ROOT / "textifai" / "web_viewer" / "react_shell" / "package.json"


class TextifaiMDXEditorSpikeTests(unittest.TestCase):
    def _json(self, name: str) -> dict:
        return json.loads((EXPECTED_ROOT / name).read_text(encoding="utf-8"))

    def test_license_audit_report_exists(self) -> None:
        report = self._json("mdxeditor_license_audit_after_sp112b.json")
        package = json.loads(REACT_PACKAGE.read_text(encoding="utf-8"))
        self.assertEqual(report["candidate_package"], "@mdxeditor/editor")
        self.assertEqual(report["license"], "MIT")
        self.assertIn("@mdxeditor/editor", package["dependencies"])
        self.assertNotIn("@mdxeditor/editor", json.loads((REPO_ROOT / "package.json").read_text(encoding="utf-8")).get("dependencies", {})) if (REPO_ROOT / "package.json").exists() else None

    def test_roundtrip_fixture_documents_preservation_targets(self) -> None:
        markdown = (FIXTURE_ROOT / "markdown_roundtrip_input.md").read_text(encoding="utf-8")
        report = self._json("mdxeditor_roundtrip_contract_after_sp112b.json")
        self.assertTrue(markdown.startswith("---\n"))
        self.assertIn("[[Characters/Ren.md]]", markdown)
        self.assertIn("# Capítulo 3: Marea de ceniza", markdown)
        self.assertIn("**recuerda**", markdown)
        self.assertIn("*casi dormida*", markdown)
        self.assertIn("https://example.org/cronica/faro?lang=es&ref=cap3", markdown)
        self.assertIn("彼は「行くな」と言った", markdown)
        self.assertIn("Lucía", markdown)
        self.assertTrue(report["must_preserve"]["frontmatter"])
        self.assertTrue(report["must_preserve"]["wikilinks"])

    def test_editor_experimental_mode_uses_chapter_manifest(self) -> None:
        app = APP_TSX.read_text(encoding="utf-8")
        self.assertIn("@mdxeditor/editor", app)
        self.assertIn("MDXEditor", app)
        self.assertIn("editorSource?.chapters", app)
        self.assertIn("chapter_manifest", app)
        self.assertIn("Editor experimental MDXEditor", app)
        self.assertIn("Modo experimental. No write-back en esta fase.", app)

    def test_save_disabled_and_no_writeback_contract(self) -> None:
        app = APP_TSX.read_text(encoding="utf-8")
        report = self._json("mdxeditor_editor_runtime_after_sp112b.json")
        self.assertIn("Guardar llegará en SP-113B", app)
        self.assertIn("disabled>Guardar llegará en SP-113B", app)
        self.assertFalse(report["write_back_enabled"])
        self.assertEqual(report["save_action"], "disabled_or_non_functional")
        self.assertNotIn("fetch(`/api/projects/${encodeURIComponent(projectId)}/note", app)
        self.assertNotIn("method: 'PUT'", app)
        self.assertNotIn("method: 'POST'", app)

    def test_runtime_report_preserves_context_and_fullscreen(self) -> None:
        report = self._json("mdxeditor_editor_runtime_after_sp112b.json")
        self.assertEqual(report["editor_source"], "chapter_manifest")
        self.assertTrue(report["right_context_panel_preserved"])
        self.assertTrue(report["fullscreen_preserved"])
        self.assertFalse(report["project_package_staged"])

    def test_reports_are_commit_safe(self) -> None:
        forbidden = [
            "/home/david/TextifAIProjects/",
            "/home/david/OnT/",
            "provider_response_raw",
            "final_prompt_sent",
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "/tmp/",
        ]
        for path in EXPECTED_ROOT.glob("*.json"):
            text = path.read_text(encoding="utf-8")
            data = json.loads(text)
            self.assertIn("assessment", data, path.name)
            for needle in forbidden:
                self.assertNotIn(needle, text, path.name)

    def test_decision_assessment_allowed(self) -> None:
        report = self._json("mdxeditor_spike_decision_after_sp112b.json")
        self.assertIn(
            report["assessment"],
            {
                "mdxeditor_spike_go_for_writeback",
                "mdxeditor_spike_go_with_source_mode_constraint",
                "mdxeditor_spike_partial_wikilink_or_frontmatter_risk",
                "mdxeditor_spike_blocked_by_license_or_roundtrip",
                "sp113a_partial_needs_followup",
            },
        )


if __name__ == "__main__":
    unittest.main()
