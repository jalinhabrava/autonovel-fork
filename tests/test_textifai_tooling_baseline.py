from __future__ import annotations

import json
from pathlib import Path
import unittest


REPO = Path(__file__).resolve().parents[1]
DOC_TOOLING = REPO / "docs/dev/tooling.md"
DOC_PACKAGING = REPO / "docs/architecture/textifai_packaging_dependencies.md"
DOC_ARTIFACTS = REPO / "docs/architecture/generated_artifacts_policy.md"
DOCTOR = REPO / "scripts/dev/textifai_doctor.py"
REACT_PACKAGE = REPO / "textifai/web_viewer/react_shell/package.json"
EXPECTED = REPO / "tests/fixtures/textifai/tooling/expected"


class TextifAIToolingBaselineTests(unittest.TestCase):
    def test_required_docs_and_script_exist(self):
        for path in [DOC_TOOLING, DOC_PACKAGING, DOC_ARTIFACTS, DOCTOR, REACT_PACKAGE]:
            self.assertTrue(path.exists(), str(path))

    def test_docs_contract_bare_python_is_not_allowed(self):
        tooling = DOC_TOOLING.read_text(encoding="utf-8").lower()
        doctor = DOCTOR.read_text(encoding="utf-8").lower()
        self.assertIn("uv run python", tooling)
        self.assertIn("uv run python", doctor)
        self.assertNotIn("never use bare `python`", doctor)

    def test_docs_cover_viewer_and_bundle_policy(self):
        tooling = DOC_TOOLING.read_text(encoding="utf-8")
        packaging = DOC_PACKAGING.read_text(encoding="utf-8")
        artifacts = DOC_ARTIFACTS.read_text(encoding="utf-8")
        self.assertIn("textifai.web_viewer.server", tooling)
        self.assertIn("8872", tooling)
        self.assertIn(".txtfai", packaging)
        self.assertIn("textifai/web_viewer/static/react-shell/", artifacts)

    def test_expected_reports_parse(self):
        for path in EXPECTED.glob("*.json"):
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["python_invocation"], "uv run python")
            self.assertFalse(payload["bare_python_allowed"])


if __name__ == "__main__":
    unittest.main()
