import unittest

from dataclasses import asdict
from textifai.conversation.contracts import ConversationRequest
from textifai.conversation.hybrid_recognizer import HybridIntentRecognizer
from textifai.conversation.manager import ConversationManager
from textifai.conversation.executor import MinimalExecutionLayer
from textifai.conversation.state import create_conversation_state
from textifai.runtime_config import load_runtime_environment
from textifai.session import create_session
from pathlib import Path
import tempfile
from vault.bootstrap import bootstrap_vault
from vault.schema import note_frontmatter


class TextifAIConversationManagerTests(unittest.TestCase):
    def test_manager_creates_state_and_updates_it_per_turn(self):
        manager = ConversationManager()
        request = ConversationRequest(
            raw_text="scene scene_054_b",
            source="user",
            mode="normal",
            interface_language="es",
            user_command_language="es",
            internal_system_language="en",
            project_default_language="ja",
            mixed_language_allowed=True,
            artifact_target_language="ja",
            explanation_language="es",
        )
        turn = manager.handle_request(request)
        self.assertEqual(turn.turn_index, 1)
        self.assertEqual(turn.recognized_intent.intent_name, "inspect_scene")
        self.assertEqual(turn.planned_task.flow_name, "scene_context_flow")
        self.assertEqual(manager.state.turn_count, 1)
        self.assertEqual(manager.state.last_goal, "scene_context_flow")
        self.assertEqual(manager.state.last_target_type, "scene")
        self.assertEqual(manager.state.last_target_id, "scene_054_b")
        self.assertEqual(manager.state.explanation_language, "es")
        self.assertEqual(manager.state.artifact_target_language, "ja")

    def test_manager_can_use_hybrid_recognizer_and_preserve_trace(self):
        recognizer = HybridIntentRecognizer(
            llm_classifier=_StubClassifier(
                {
                    "intent_name": "inspect_scene",
                    "confidence": 0.88,
                    "target_type": "scene",
                    "target_id": "scene_054_b",
                    "classification_note": "LLM disambiguated a freeform scene request.",
                    "narrative_signals": {
                        "mentioned_entities": ["Sera"],
                        "mentioned_character_ids": ["sera"],
                        "target_hint": "scene_054_b",
                        "target_inference_source": "conversation_state",
                        "issue_types": ["character_voice_mismatch"],
                        "constraint_hints": ["check_character_voice"],
                        "confidence": 0.82,
                    },
                }
            )
        )
        manager = ConversationManager(recognizer=recognizer)
        request = ConversationRequest(
            raw_text="quiero ver esta escena",
            source="user",
            mode="normal",
            interface_language="es",
            user_command_language="es",
            internal_system_language="en",
            project_default_language="ja",
            mixed_language_allowed=True,
            artifact_target_language="ja",
            explanation_language="es",
            metadata={"known_characters": [{"id": "sera", "names": ["Sera"]}]},
        )
        turn = manager.handle_request(request)
        self.assertEqual(turn.recognized_intent.recognizer_kind, "hybrid_llm")
        self.assertEqual(turn.recognized_intent.metadata["recognition_source"], "hybrid_llm")
        self.assertEqual(turn.planned_task.flow_name, "scene_context_flow")
        self.assertEqual(turn.recognized_intent.narrative_signals.issue_types, ["character_voice_mismatch"])

    def test_manager_syncs_real_execution_context_into_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp)
            vault_root = base_dir / "Vault"
            bootstrap_vault(vault_root, title="Test Project")
            (base_dir / ".env").write_text(
                "\n".join(
                    [
                        "AUTONOVEL_PROJECT_BACKEND=vault",
                        f"AUTONOVEL_VAULT_ROOT={vault_root}",
                        "AUTONOVEL_TEXT_PROVIDER=ollama",
                    ]
                )
                + "\n"
            )
            session = create_session(load_runtime_environment(base_dir))
            manager = ConversationManager(session=session, executor=MinimalExecutionLayer(session=session))
            request = ConversationRequest(
                raw_text="world",
                source="user",
                mode="normal",
                interface_language="en",
                user_command_language="en",
                internal_system_language="en",
                project_default_language="en",
                mixed_language_allowed=True,
                explanation_language="en",
            )
            turn = manager.handle_request(request)
            self.assertEqual(turn.result_type, "context_pack")
            self.assertIsNotNone(manager.state.last_context_request)
            self.assertIsNotNone(manager.state.last_context_pack)
            self.assertIs(session.conversation_state, manager.state)

    def test_manager_returns_unsupported_flow_for_natural_bootstrap(self):
        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp)
            vault_root = base_dir / "Vault"
            bootstrap_vault(vault_root, title="Test Project")
            (base_dir / ".env").write_text(
                "\n".join(
                    [
                        "AUTONOVEL_PROJECT_BACKEND=vault",
                        f"AUTONOVEL_VAULT_ROOT={vault_root}",
                        "AUTONOVEL_TEXT_PROVIDER=ollama",
                    ]
                )
                + "\n"
            )
            session = create_session(load_runtime_environment(base_dir))
            manager = ConversationManager(session=session, executor=MinimalExecutionLayer(session=session))
            request = ConversationRequest(
                raw_text="haz bootstrap del canon de los capítulos 1 a 3",
                source="user",
                mode="normal",
                interface_language="es",
                user_command_language="es",
                internal_system_language="en",
                project_default_language="ja",
                mixed_language_allowed=True,
                explanation_language="es",
            )
            turn = manager.handle_request(request)
            self.assertEqual(turn.result_type, "unsupported_flow")

    def test_manager_freeform_editorial_request_without_provider_stays_honest(self):
        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp)
            vault_root = base_dir / "Vault"
            bootstrap_vault(vault_root, title="Test Project")
            (base_dir / ".env").write_text(
                "\n".join(
                    [
                        "AUTONOVEL_PROJECT_BACKEND=vault",
                        f"AUTONOVEL_VAULT_ROOT={vault_root}",
                        "AUTONOVEL_TEXT_PROVIDER=ollama",
                    ]
                )
                + "\n"
            )
            session = create_session(load_runtime_environment(base_dir))
            manager = ConversationManager(session=session, executor=MinimalExecutionLayer(session=session))
            request = ConversationRequest(
                raw_text="Sera llega tarde al puerto, Toma la acusa de mentir y ella revela que perdió el mapa",
                source="user",
                mode="normal",
                interface_language="es",
                user_command_language="es",
                internal_system_language="en",
                project_default_language="ja",
                mixed_language_allowed=True,
                explanation_language="es",
                metadata={
                    "known_characters": [
                        {"id": "sera", "names": ["Sera"]},
                        {"id": "toma", "names": ["Toma"]},
                    ]
                },
            )
            turn = manager.handle_request(request)
            self.assertEqual(turn.result_type, "conversation_clarification")
            self.assertEqual(turn.provider_mode, "disabled")
            self.assertIsNone(turn.author_facing_response)

    def test_manager_uses_recent_lore_target_for_validate_this_note(self):
        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp)
            vault_root = base_dir / "Vault"
            bootstrap_vault(vault_root, title="Test Project")
            (vault_root / "02_World" / "Lore" / "magic_limits.md").write_text(
                note_frontmatter("lore", "Magic Limits", slug="magic_limits") + "\n\n"
            )
            (base_dir / ".env").write_text(
                "\n".join(
                    [
                        "AUTONOVEL_PROJECT_BACKEND=vault",
                        f"AUTONOVEL_VAULT_ROOT={vault_root}",
                        "AUTONOVEL_TEXT_PROVIDER=ollama",
                    ]
                )
                + "\n"
            )
            session = create_session(load_runtime_environment(base_dir))
            state = session.conversation_state
            manager = ConversationManager(session=session, executor=MinimalExecutionLayer(session=session))
            manager.state = manager.state or manager.executor.session.conversation_state or None
            if manager.state is None:
                from textifai.conversation.state import create_conversation_state

                manager.state = create_conversation_state(explanation_language="es", artifact_target_language="ja")
            manager.state = manager.state.__class__(
                **{
                    **manager.state.__dict__,
                    "last_target_type": "lore",
                    "last_target_id": "magic_limits",
                }
            )
            session.conversation_state = manager.state
            request = ConversationRequest(
                raw_text="validate lore:magic_limits",
                source="user",
                mode="normal",
                interface_language="es",
                user_command_language="es",
                internal_system_language="en",
                project_default_language="ja",
                mixed_language_allowed=True,
                explanation_language="es",
            )
            turn = manager.handle_request(request)
            self.assertEqual(turn.result_type, "pending_confirmation")
            self.assertEqual(manager.state.pending_operation.target_type, "lore")
            self.assertEqual(manager.state.pending_operation.target_id, "magic_limits")

    def test_manager_returns_minimal_followup_clarification_for_esta_nota(self):
        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp)
            vault_root = base_dir / "Vault"
            bootstrap_vault(vault_root, title="Test Project")
            (vault_root / "02_World" / "Lore" / "magic_limits.md").write_text(
                note_frontmatter("lore", "Magic Limits", slug="magic_limits") + "\n\n"
            )
            (base_dir / ".env").write_text(
                "\n".join(
                    [
                        "AUTONOVEL_PROJECT_BACKEND=vault",
                        f"AUTONOVEL_VAULT_ROOT={vault_root}",
                        "AUTONOVEL_TEXT_PROVIDER=ollama",
                    ]
                )
                + "\n"
            )
            session = create_session(load_runtime_environment(base_dir))
            manager = ConversationManager(session=session, executor=MinimalExecutionLayer(session=session))
            state = create_conversation_state(explanation_language="es", artifact_target_language="ja")
            manager.state = state.__class__(**{**state.__dict__, "last_target_type": "lore", "last_target_id": "magic_limits"})
            session.conversation_state = manager.state
            request = ConversationRequest(
                raw_text="esta nota",
                source="user",
                mode="normal",
                interface_language="es",
                user_command_language="es",
                internal_system_language="en",
                project_default_language="ja",
                mixed_language_allowed=True,
                explanation_language="es",
            )
            turn = manager.handle_request(request)
            self.assertEqual(turn.result_type, "context_pack")
            self.assertTrue(bool(turn.result_summary))
            self.assertEqual(turn.provider_mode, "disabled")
            self.assertIsNone(turn.author_facing_response)
            self.assertIsInstance(session.last_result, dict)
            self.assertEqual(session.last_result["type"], "context_pack")

    def test_manager_explicit_consistency_check_anchors_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp)
            vault_root = base_dir / "Vault"
            bootstrap_vault(vault_root, title="Test Project")
            (vault_root / "02_World" / "Lore" / "memory_ritual.md").write_text(
                note_frontmatter("lore", "Memory Ritual", slug="memory_ritual", aliases=["ritual de memoria"]) + "\n\n"
            )
            (vault_root / "02_World" / "Lore" / "harbor_map.md").write_text(
                note_frontmatter("lore", "Harbor Map", slug="harbor_map", aliases=["mapa"]) + "\n\n"
            )
            (base_dir / ".env").write_text(
                "\n".join(
                    [
                        "AUTONOVEL_PROJECT_BACKEND=vault",
                        f"AUTONOVEL_VAULT_ROOT={vault_root}",
                        "AUTONOVEL_TEXT_PROVIDER=ollama",
                    ]
                )
                + "\n"
            )
            session = create_session(load_runtime_environment(base_dir))
            manager = ConversationManager(session=session, executor=MinimalExecutionLayer(session=session))
            request = ConversationRequest(
                raw_text="check lore:harbor_map",
                source="user",
                mode="normal",
                interface_language="es",
                user_command_language="es",
                internal_system_language="en",
                project_default_language="ja",
                mixed_language_allowed=True,
                explanation_language="es",
            )
            turn = manager.handle_request(request)
            self.assertEqual(turn.planned_task.flow_name, "consistency_check_flow")
            self.assertEqual(turn.result_type, "consistency_report")
            self.assertEqual(turn.planned_task.target_id, "harbor_map")
            self.assertEqual(turn.planned_task.target_type, "lore")

    def test_manager_routes_prep_for_narration_to_previous_editorial_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp)
            vault_root = base_dir / "Vault"
            bootstrap_vault(vault_root, title="Test Project")
            (base_dir / ".env").write_text(
                "\n".join(
                    [
                        "AUTONOVEL_PROJECT_BACKEND=vault",
                        f"AUTONOVEL_VAULT_ROOT={vault_root}",
                        "AUTONOVEL_TEXT_PROVIDER=ollama",
                    ]
                )
                + "\n"
            )
            session = create_session(load_runtime_environment(base_dir))
            manager = ConversationManager(session=session, executor=MinimalExecutionLayer(session=session))
            session.remember(
                {
                    "type": "editorial_structuring",
                    "data": {
                        "story_facts": {
                            "source_text": "Sera reaches the port late and Toma confronts her.",
                            "language": "es",
                            "characters_involved": ["Sera", "Toma"],
                            "locations_involved": ["Port"],
                            "objects_involved": ["Map"],
                            "premise": "Sera arrives late to the port.",
                            "core_conflict": "Toma confronts Sera over the missing map.",
                            "goals": ["Preserve the mission route."],
                            "constraints": [],
                            "canon_constraints": [],
                            "explicit_facts": [
                                {
                                    "text": "Sera arrives late at the port.",
                                    "fact_kind": "event",
                                    "source": "explicit_input",
                                }
                            ],
                            "inferred_facts": [],
                            "open_questions": [],
                        },
                        "beat_outline": {
                            "source_kind": "beat_outline",
                            "title": "Port confrontation",
                            "beats": [
                                {
                                    "index": 1,
                                    "summary": "Sera arrives late and Toma confronts her.",
                                    "purpose": "Establish the conflict around the missing map.",
                                    "characters": ["Sera", "Toma"],
                                    "tension_level": "rising",
                                }
                            ],
                            "emotional_arc": ["tension"],
                            "target_language": "ja",
                            "continuity_notes": [],
                            "canon_checks": [],
                        },
                        "revision_intent": {
                            "source_text": "Keep the confrontation tense and clear.",
                            "target_scope": "scene",
                            "issue_types": ["clarity"],
                            "desired_changes": ["Preserve the port confrontation."],
                            "must_preserve": ["Sera loses the map."],
                            "priority": "high",
                            "target_hint": None,
                        },
                        "entity_resolution_results": [],
                        "result_kind": "mixed",
                        "ready_for_validation": True,
                    },
                    "summary": "Seeded structuring result for followthrough.",
                }
            )
            second_request = ConversationRequest(
                raw_text="prepare_narration",
                source="user",
                mode="normal",
                interface_language="es",
                user_command_language="es",
                internal_system_language="en",
                project_default_language="ja",
                mixed_language_allowed=True,
                explanation_language="es",
                metadata={
                    "known_characters": [
                        {"id": "sera", "names": ["Sera"]},
                        {"id": "toma", "names": ["Toma"]},
                    ]
                },
            )
            second_turn = manager.handle_request(second_request)
            self.assertEqual(second_turn.result_type, "followthrough")
            remembered = session.last_result["data"]
            self.assertIsNotNone(remembered["narration_request"])
            self.assertIsNotNone(remembered["narration_prep"])
            self.assertEqual(remembered["narration_prep"]["source_kind"], "beat_outline")

    def test_manager_anchors_canon_contradiction_to_lore_target_with_vaerl(self):
        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp)
            vault_root = base_dir / "Vault"
            bootstrap_vault(vault_root, title="Test Project")
            (vault_root / "02_World" / "Lore" / "memory_ritual.md").write_text(
                note_frontmatter("lore", "Memory Ritual", slug="memory_ritual", aliases=["ritual de memoria"]) + "\n\n"
            )
            (vault_root / "02_World" / "Lore" / "ritual_notes.md").write_text(
                note_frontmatter("lore", "Ritual Notes", slug="ritual_notes", aliases=["ritual"]) + "\n\n"
            )
            (base_dir / ".env").write_text(
                "\n".join(
                    [
                        "AUTONOVEL_PROJECT_BACKEND=vault",
                        f"AUTONOVEL_VAULT_ROOT={vault_root}",
                        "AUTONOVEL_TEXT_PROVIDER=ollama",
                    ]
                )
                + "\n"
            )
            session = create_session(load_runtime_environment(base_dir))
            manager = ConversationManager(session=session, executor=MinimalExecutionLayer(session=session))
            request = ConversationRequest(
                raw_text="check lore:ritual_notes",
                source="user",
                mode="normal",
                interface_language="es",
                user_command_language="es",
                internal_system_language="en",
                project_default_language="ja",
                mixed_language_allowed=True,
                explanation_language="es",
            )
            turn = manager.handle_request(request)
            self.assertEqual(turn.planned_task.flow_name, "consistency_check_flow")
            self.assertEqual(turn.planned_task.target_type, "lore")
            self.assertEqual(turn.planned_task.target_id, "ritual_notes")


class _StubClassifier:
    def __init__(self, result):
        self.result = result

    def classify_intent(self, *, request, rule_intent, state):
        return dict(self.result)


if __name__ == "__main__":
    unittest.main()
