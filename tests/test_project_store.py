import json
import tempfile
import unittest
from pathlib import Path

from stores.project_store import ProjectStore


class ProjectStoreTests(unittest.TestCase):
    def test_workspace_store_reads_writes_state_artifacts_and_chapters(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            store = ProjectStore(base)
            store.ensure_runtime_dirs()

            store.write_artifact("voice", "# Voice")
            store.write_chapter(1, "# Chapter One\nHello world")
            state = {"phase": "drafting", "chapters_drafted": 1}
            store.write_state(state)
            store.append_result_row(
                commit="abc123",
                phase="drafting",
                score=7.2,
                word_count=1234,
                status="keep",
                description="test row",
            )

            self.assertEqual(store.read_voice(), "# Voice")
            self.assertEqual(store.read_chapter(1), "# Chapter One\nHello world")
            self.assertEqual(store.read_state({}), state)
            self.assertEqual(store.count_chapters(), 1)
            self.assertEqual(store.get_title(), "Chapter One")

            results_text = store.read_artifact("results")
            self.assertIn("commit\tphase\tscore", results_text)
            self.assertIn("abc123\tdrafting\t7.2\t1234\tkeep\ttest row", results_text)

    def test_workspace_store_uses_classic_paths_via_adapter(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            store = ProjectStore(base)

            self.assertEqual(store.artifact_path("world"), base / "world.md")
            self.assertEqual(store.artifact_path("state"), base / "state.json")
            self.assertEqual(store.chapter_path(7), base / "chapters" / "ch_07.md")


if __name__ == "__main__":
    unittest.main()
