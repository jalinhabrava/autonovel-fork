from __future__ import annotations

import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_ROOT = REPO_ROOT / "tests" / "fixtures" / "textifai" / "mdxeditor_spike" / "expected"
APP_TSX = REPO_ROOT / "textifai" / "web_viewer" / "react_shell" / "src" / "App.tsx"


class TextifaiMDXEditorSpikeTests(unittest.TestCase):
    def _json(self, name: str) -> dict:
        return json.loads((EXPECTED_ROOT / name).read_text(encoding="utf-8"))

    def test_reports_exist(self) -> None:
        for name in [
            "codemirror_markdown_usability_after_sp113a.json",
            "editor_toolbar_adapter_contract_after_sp113a.json",
            "editor_usability_after_sp113a.json",
        ]:
            self.assertTrue((EXPECTED_ROOT / name).exists(), name)

    def test_codemirror_line_wrapping_contract(self) -> None:
        app = APP_TSX.read_text(encoding="utf-8")
        report = self._json("codemirror_markdown_usability_after_sp113a.json")
        self.assertIn("EditorView.lineWrapping", app)
        self.assertTrue(report["markdown_line_wrapping_enabled"])

    def test_toolbar_parity_and_noop_contract(self) -> None:
        app = APP_TSX.read_text(encoding="utf-8")
        report = self._json("editor_toolbar_adapter_contract_after_sp113a.json")
        self.assertIn("textifai-editor-toolbar", app)
        self.assertTrue(report["markdown_toolbar_visual_match"])
        self.assertTrue(report["no_noop_toolbar_buttons"])

    def test_selection_commands_and_undo_redo(self) -> None:
        app = APP_TSX.read_text(encoding="utf-8")
        report = self._json("codemirror_markdown_usability_after_sp113a.json")
        self.assertIn("dispatchMarkdownChange", app)
        self.assertIn("applyMarkdownWrap", app)
        self.assertIn("applyMarkdownLinePrefix", app)
        self.assertIn("applyMarkdownLink", app)
        self.assertIn("undo(editorTextareaRef.current?.view?.state", app)
        self.assertIn("redo(editorTextareaRef.current?.view?.state", app)
        self.assertTrue(report["markdown_selection_commands"])
        self.assertEqual(report["markdown_undo_redo_status"], "working")

    def test_save_disabled_and_contract_fields(self) -> None:
        app = APP_TSX.read_text(encoding="utf-8")
        self.assertIn("Write-back Markdown con hash guard y backup", app)
        required = {
            "save_disabled": False,
            "chapter_hash_unchanged": False,
        }
        for name in [
            "codemirror_markdown_usability_after_sp113a.json",
            "editor_toolbar_adapter_contract_after_sp113a.json",
            "editor_usability_after_sp113a.json",
        ]:
            data = self._json(name)
            for key, value in required.items():
                self.assertEqual(data.get(key), value, f"{name}:{key}")


if __name__ == "__main__":
    unittest.main()
