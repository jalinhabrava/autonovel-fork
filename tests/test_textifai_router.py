import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from textifai.runtime_config import load_runtime_environment
from textifai.session import create_session
from textifai.router import dispatch_command
from vault.bootstrap import bootstrap_vault


class TextifAIRouterTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.tempdir.name)
        self.vault_root = self.base_dir / "Vault"
        bootstrap_vault(self.vault_root, title="Test Project")
        (self.base_dir / ".env").write_text(
            "\n".join(
                [
                    "AUTONOVEL_PROJECT_BACKEND=vault",
                    f"AUTONOVEL_VAULT_ROOT={self.vault_root}",
                    "AUTONOVEL_TEXT_PROVIDER=ollama",
                    "TEXTIFAI_INTERFACE_LANGUAGE=es",
                    "TEXTIFAI_USER_COMMAND_LANGUAGE=es",
                    'TEXTIFAI_ARTIFACT_LANGUAGES={"chapter":"ja","scene":"ja","decision":"es","character":"ja","voice":"en","lore":"es","world":"es"}',
                ]
            )
            + "\n"
        )
        self.session = create_session(load_runtime_environment(self.base_dir))

    def tearDown(self):
        self.tempdir.cleanup()

    def test_world_and_find_delegate_to_context_commands(self):
        with patch("textifai.router.build_world_context", return_value=_pack("world")) as world_mock:
            response = dispatch_command(self.session, "world")
        world_mock.assert_called_once()
        self.assertIn("resultado de contexto de textifai", response.lower())
        self.assertEqual(self.session.last_context_pack["type"], "context_pack")
        self.assertEqual(self.session.last_context_request["intent"], "world_lookup")
        self.assertEqual(self.session.last_context_request["operation_language"], "es")
        self.assertEqual(self.session.last_context_request["artifact_target_language"], "es")

        with patch("textifai.router.build_find_context", return_value=_pack("find")) as find_mock:
            response = dispatch_command(self.session, "find hidden door")
        find_mock.assert_called_once()
        self.assertIn("intent", response.lower())
        self.assertEqual(self.session.last_context_request["intent"], "context_search")
        self.assertEqual(self.session.last_context_request["operation_language"], "es")

    def test_scene_and_chapter_prompt_for_missing_ids(self):
        prompts = iter(["scene_054_b", "ch_12"])
        with patch("textifai.router.build_scene_context", return_value=_pack("scene")) as scene_mock:
            dispatch_command(self.session, "scene", input_fn=lambda _: next(prompts))
        scene_mock.assert_called_once()
        self.assertEqual(self.session.last_context_request["artifact_target_language"], "ja")

        with patch("textifai.router.build_chapter_context", return_value=_pack("chapter")) as chapter_mock:
            dispatch_command(self.session, "chapter", input_fn=lambda _: next(prompts))
        chapter_mock.assert_called_once()
        self.assertEqual(self.session.last_context_request["artifact_target_language"], "ja")

    def test_check_is_limited_and_uses_consistency_check(self):
        decision_path = self.vault_root / "06_Canon" / "Decisions" / "magic_costs.md"
        decision_path.write_text(
            "---\nkind: canon_decision\ntitle: Magic Costs\nstatus: proposed\nschema_version: 1.0\n---\n\n# Magic Costs\n\nMagic has a visible cost.\n"
        )
        with patch("textifai.router.consistency_check", return_value=_report()) as check_mock:
            response = dispatch_command(self.session, "check decision:magic_costs")
        check_mock.assert_called_once()
        self.assertIn("comprobación de consistencia", response.lower())
        payload = check_mock.call_args.args[1]
        self.assertEqual(payload["artifact_language"], "es")
        self.assertEqual(payload["operation_language"], "es")

        guidance = dispatch_command(self.session, "check")
        self.assertIn("uso: check", guidance.lower())

    def test_decide_validate_and_reject_delegate_to_persistence(self):
        prompts = iter(["Costly Magic", "Magic always costs something.", "Sera,Ren"])
        with patch(
            "textifai.router.decide",
            return_value={"type": "decision_canon", "state": "validated", "target_type": "decision", "target_id": "costly_magic", "path": "x.md"},
        ) as decide_mock:
            response = dispatch_command(self.session, "decide", input_fn=lambda _: next(prompts))
        decide_mock.assert_called_once()
        self.assertIn("decisión registrada", response.lower())
        payload = decide_mock.call_args.args[1]
        self.assertEqual(payload["artifact_language"], "es")
        self.assertEqual(payload["operation_language"], "es")

        decision_path = self.vault_root / "06_Canon" / "Decisions" / "magic_costs.md"
        decision_path.write_text(
            "---\nkind: canon_decision\ntitle: Magic Costs\nstatus: proposed\nschema_version: 1.0\n---\n\n# Magic Costs\n\nMagic has a visible cost.\n"
        )
        with patch(
            "textifai.router.validate",
            return_value={"state": "validated", "target_type": "decision", "target_id": "magic_costs", "path": "x.md"},
        ) as validate_mock:
            response = dispatch_command(self.session, "validate decision:magic_costs")
        validate_mock.assert_called_once()
        self.assertIn("resultado de persistencia", response.lower())
        self.assertIn("next_step", response)

        with patch(
            "textifai.router.reject",
            return_value={"state": "rejected", "target_type": "decision", "target_id": "magic_costs", "path": "x.md"},
        ) as reject_mock:
            response = dispatch_command(self.session, "reject 06_Canon/Decisions/magic_costs.md")
        reject_mock.assert_called_once()
        self.assertIn("rejected", response.lower())


def _pack(target: str) -> dict:
    return {
        "type": "context_pack",
        "intent": "context_search",
        "scope": {"target_id": target},
        "policy": {"name": "default"},
        "hard_constraints": [{"title": "Magic Costs"}],
        "narrative_context": [],
        "voice_context": {"project_voice": [], "character_voice": []},
        "evidence": [],
        "meta": {},
    }


def _report() -> dict:
    return {
        "type": "consistency_report",
        "ok": True,
        "summary": "No blocking issues detected.",
        "target_type": "decision",
        "target_id": "magic_costs",
        "canon_refs": ["magic_costs"],
        "lore_refs": [],
        "issues": [],
        "suggested_actions": [],
        "context_pack": _pack("magic_costs"),
    }


if __name__ == "__main__":
    unittest.main()
