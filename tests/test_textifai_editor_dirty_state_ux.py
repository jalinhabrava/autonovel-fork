from __future__ import annotations

import json
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EXPECTED = REPO / "tests" / "fixtures" / "textifai" / "editor_dirty_state" / "expected"
APP = REPO / "textifai" / "web_viewer" / "react_shell" / "src" / "App.tsx"
API = REPO / "textifai" / "web_viewer" / "react_shell" / "src" / "api.ts"
SERVER = REPO / "textifai" / "web_viewer" / "server.py"

NAMES = [
    "editor_save_status_ux_after_sp116.json",
    "editor_contextual_banner_after_sp116.json",
    "editor_canon_risks_panel_after_sp116.json",
    "editor_reanalysis_entrypoint_after_sp116.json",
    "editor_dirty_state_decision_after_sp116.json",
]

class TextifaiEditorDirtyStateUXTests(unittest.TestCase):
    def _j(self, name: str) -> dict:
        return json.loads((EXPECTED / name).read_text(encoding="utf-8"))

    def test_reports_exist(self) -> None:
        for name in NAMES:
            self.assertTrue((EXPECTED / name).exists(), name)

    def test_reports_contract_flags(self) -> None:
        for name in NAMES:
            payload = self._j(name)
            for key in [
                "local_save_status_zone", "semantic_status_zone", "duplicate_warnings_removed",
                "contextual_banner_fade", "conflict_persistent", "success_auto_fade",
                "canon_risks_needs_reanalysis", "reanalysis_button_placeholder",
                "reanalysis_endpoint_not_implemented", "no_vaerl_writeback",
                "no_graph_regeneration", "no_review_regeneration", "no_source_prose",
            ]:
                self.assertTrue(payload.get(key), f"{name}:{key}")
            self.assertNotIn("chapter_markdown", payload)
            self.assertNotIn("source_prose", payload)

    def test_local_save_states_and_banner_behavior_documented_in_ui(self) -> None:
        app = APP.read_text(encoding="utf-8")
        self.assertIn("type SaveStatus = 'idle' | 'dirty' | 'saving' | 'saved' | 'error' | 'conflict'", app)
        self.assertIn("Cambios sin guardar", app)
        self.assertIn("Guardando…", app)
        self.assertIn("Capítulo guardado. Canon/VaERL pendiente de reanálisis.", app)
        self.assertIn("Conflicto: el capítulo cambió en disco. Recarga antes de guardar.", app)
        self.assertIn("setTimeout(() => setEditorSaveBannerVisible(false), 4000)", app)

    def test_no_duplicate_warning_zones_and_semantic_state_in_canon_risks(self) -> None:
        app = APP.read_text(encoding="utf-8")
        self.assertNotIn("Guardar escribe Markdown y marca Canon/VaERL pendiente de reanálisis; no reanaliza Graph ni Review.", app)
        self.assertTrue("Canon risks" in app or "t('editor.canon_risks')" in app)
        self.assertTrue("Pendiente de reanálisis" in app or "t('editor.reanalysis.pending')" in app)
        self.assertTrue("Este capítulo fue editado. Canon/VaERL, Grafo y Revisión no se han regenerado." in app or "t('editor.reanalysis.notice')" in app)

    def test_reanalysis_entrypoint_is_placeholder_not_implemented(self) -> None:
        api = API.read_text(encoding="utf-8")
        server = SERVER.read_text(encoding="utf-8")
        app = APP.read_text(encoding="utf-8")
        self.assertIn("requestChapterReanalysis", api)
        self.assertIn("/reanalyze", api)
        self.assertIn("status': 'not_implemented'", server)
        self.assertTrue("Reanalizar capítulo" in app or "t('editor.reanalysis.action')" in app)

if __name__ == "__main__":
    unittest.main()
