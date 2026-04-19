from __future__ import annotations

from dataclasses import asdict, dataclass
import tempfile
import unittest
import zipfile
from pathlib import Path

from textifai.author_understanding.contracts import (
    AuthorIntentInterpretation,
    DisambiguationResult,
    LLMAuthorUnderstandingPayload,
    MixedRequestPart,
)
from textifai.author_understanding.hybrid_analysis import HybridAuthorUnderstandingAnalyzer
from textifai.conversation.contracts import ConversationRequest, NarrativeSignals, RecognizedIntent
from textifai.conversation.manager import ConversationManager
from textifai.conversation.planner import TaskPlanner
from textifai.conversation.state import create_conversation_state
from textifai.derived_sources import (
    build_derived_understanding_prompt,
    decide_llm_escalation,
    extract_light_source,
    normalize_derived_llm_payload,
    review_derived_source,
    validate_derived_extraction,
)
from textifai.editorial.entity_resolution import resolve_entities
from textifai.editorial_intent.classifier import classify_editorial_intent
from textifai.editorial_intent.contracts import CandidateTarget
from textifai.vaerl.contracts import EntityHint
from textifai.vaerl.resolver import resolve_text_against_vault
from vault.bootstrap import bootstrap_vault
from vault.schema import note_frontmatter


@dataclass(frozen=True)
class ConversationImportCase:
    label: str
    language: str
    conversation_text: str
    import_text: str
    source_format: str
    primary_intent_type: str
    expected_request_type: str
    expected_target_id: str
    expected_target_type: str
    candidate_kind: str
    preserve_signals: list[str]
    change_signals: list[str]
    author_goal_signals: list[str]
    has_mixed_request: bool = False
    mixed_parts: list[tuple[str, str]] | None = None
    content_mix_signals: list[str] | None = None


class TextifAIInterpretationLoopAlignmentTests(unittest.TestCase):
    def test_same_intent_different_languages_converge(self):
        cases = [
            (
                "es-structuring",
                "Quiero que esta escena tenga una estructura mas clara sin perder la tension.",
                "structuring_request",
                "scene_054_b",
            ),
            (
                "en-structuring",
                "I want this scene to have a clearer structure without losing the tension.",
                "structuring_request",
                "scene_054_b",
            ),
            (
                "ja-structuring",
                "このシーンは緊張感を失わずに、もっと構造を明確にしたい。",
                "structuring_request",
                "scene_054_b",
            ),
            (
                "pt-structuring",
                "Quero que esta cena tenha uma estrutura mais clara sem perder a tensao.",
                "structuring_request",
                "scene_054_b",
            ),
            (
                "es-narration",
                "Quiero dejar esto listo para narracion sin perder el tono.",
                "narration_preparation",
                "scene_054_b",
            ),
            (
                "en-narration",
                "I want this ready for narration without losing the tone.",
                "narration_preparation",
                "scene_054_b",
            ),
            (
                "ja-narration",
                "この内容を語りの準備にして、トーンを崩さないでほしい。",
                "narration_preparation",
                "scene_054_b",
            ),
            (
                "pt-narration",
                "Quero isto pronto para narracao sem perder o tom.",
                "narration_preparation",
                "scene_054_b",
            ),
        ]
        observed_signatures: set[tuple[str, str, str, str]] = set()
        for label, raw_text, primary_intent_type, target_id in cases:
            interpretation, editorial_intent, planned_task = self._run_author_loop(
                label=label,
                raw_text=raw_text,
                language=label.split("-")[0],
                llm_payload=self._author_payload(
                    raw_text=raw_text,
                    primary_intent_type=primary_intent_type,
                    target_id=target_id,
                    target_type="scene",
                    author_goal_signals=["structure_scene"] if primary_intent_type == "structuring_request" else ["prepare_for_narration"],
                    preserve_signals=["preserve_scene_conflict"],
                    change_signals=["structure_scene"] if primary_intent_type == "structuring_request" else ["prepare_for_narration"],
                ),
            )
            observed_signatures.add(
                (
                    interpretation.primary_intent_type,
                    editorial_intent.request_type if editorial_intent is not None else "none",
                    editorial_intent.semantic_basis if editorial_intent is not None else "none",
                    "semantic" if planned_task.semantic_phase else "operational",
                )
            )
            self.assertEqual(interpretation.source, "hybrid")
            self.assertEqual(interpretation.primary_intent_type, primary_intent_type)
            self.assertTrue(interpretation.entity_hints)
            self.assertEqual(editorial_intent.semantic_basis, "author_understanding_validated")
            self.assertTrue(planned_task.semantic_phase)
            self.assertEqual(planned_task.metadata["phase_classification"], "semantic")
        self.assertEqual(len(observed_signatures), 2)

    def test_same_intent_different_wording_converge(self):
        cases = [
            "hazlo mas claro",
            "make it clearer",
            "もっとわかりやすくして",
            "torna isto mais claro",
            "be more precise here",
            "menos ruido, mas estructura",
            "just clarify this a bit",
            "dame una version mas ordenada",
        ]
        observed_signatures: set[tuple[str, str, tuple[str, ...]]] = set()
        for raw_text in cases:
            interpretation, editorial_intent, _ = self._run_author_loop(
                label=raw_text,
                raw_text=raw_text,
                language="es",
                llm_payload=self._author_payload(
                    raw_text=raw_text,
                    primary_intent_type="editorial_revision",
                    target_id="scene_054_b",
                    target_type="scene",
                    author_goal_signals=["align_tone"],
                    preserve_signals=["preserve_validated_canon"],
                    change_signals=["align_tone"],
                ),
            )
            observed_signatures.add(
                (
                    interpretation.primary_intent_type,
                    editorial_intent.request_type if editorial_intent is not None else "none",
                    tuple(editorial_intent.preserve_constraints if editorial_intent is not None else ()),
                )
            )
            self.assertEqual(interpretation.primary_intent_type, "editorial_revision")
            self.assertTrue(interpretation.entity_hints)
            self.assertEqual(editorial_intent.semantic_basis, "author_understanding_validated")
            self.assertIn("align_tone", editorial_intent.editorial_goals)
        self.assertEqual(len(observed_signatures), 1)

    def test_mixed_language_inputs_normalize_without_privileging_one_language(self):
        cases = [
            "Ordena esta escena y luego leave it ready for narration.",
            "この章を整理して, despues dejalo listo para revision.",
            "Quero revisar isto, mas without breaking the canon.",
            "Hazlo mas claro and keep the tension.",
            "Let's continue con eso y luego narralo.",
            "整理して then keep the canon intact.",
        ]
        observed_signatures: set[tuple[str, str, bool]] = set()
        for raw_text in cases:
            interpretation, editorial_intent, planned_task = self._run_author_loop(
                label=raw_text,
                raw_text=raw_text,
                language="es",
                llm_payload=self._author_payload(
                    raw_text=raw_text,
                    primary_intent_type="mixed_request",
                    target_id="scene_054_b",
                    target_type="scene",
                    author_goal_signals=["structure_scene", "prepare_for_narration"],
                    preserve_signals=["preserve_scene_conflict"],
                    change_signals=["structure_scene", "prepare_for_narration"],
                    has_mixed_request=True,
                    parts=[
                        ("narrative_content", "Sera llega tarde al puerto", 0.91),
                        ("meta_instruction", "ordena esto", 0.83),
                        ("narration_prep", "dejalo listo para narracion", 0.82),
                    ],
                    candidate_targets=[
                        CandidateTarget(target_id="scene_054_b", target_type="scene", confidence=0.84),
                        CandidateTarget(target_id="memory_ritual", target_type="lore", confidence=0.71),
                    ],
                ),
            )
            observed_signatures.add(
                (
                    interpretation.primary_intent_type,
                    editorial_intent.request_type if editorial_intent is not None else "none",
                    interpretation.has_mixed_request,
                )
            )
            self.assertTrue(interpretation.has_mixed_request)
            self.assertTrue(interpretation.entity_hints)
            self.assertEqual(editorial_intent.request_type, "mixed_editorial_request")
            self.assertTrue(planned_task.semantic_phase)
        self.assertEqual(len(observed_signatures), 1)

    def test_cross_language_entity_resolution(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_root = Path(tmp) / "Vault"
            bootstrap_vault(vault_root, title="Test Project")
            (vault_root / "02_World" / "Lore" / "memory_ritual.md").write_text(
                note_frontmatter(
                    "lore",
                    "Memory Ritual",
                    slug="memory_ritual",
                    aliases=["ritual"],
                    project_confirmed_aliases=["ritual de memoria", "memoriaの儀式", "ritual de memoria"],
                )
                + "\n\n"
            )
            (vault_root / "02_World" / "Lore" / "veredyn.md").write_text(
                note_frontmatter("lore", "Veredyn", slug="veredyn") + "\n\n"
            )

            cases = [
                ("title", "Memory Ritual", True, "memory_ritual"),
                ("project alias es", "ritual de memoria", True, "memory_ritual"),
                ("project alias ja", "memoriaの儀式", True, "memory_ritual"),
                ("negative es", "patatas", False, None),
                ("negative pt", "batata", False, None),
                ("negative ja", "じゃがいも", False, None),
            ]
            case_count = 0
            for label, text, should_resolve, expected_id in cases:
                with self.subTest(label=label):
                    if should_resolve:
                        results = resolve_text_against_vault(text=text, vault_path=vault_root)
                        result = next(item for item in results if item.resolved)
                        self.assertTrue(result.resolved)
                        self.assertEqual(result.resolved_entity_id, expected_id)
                    else:
                        results = resolve_text_against_vault(text=text, vault_path=vault_root)
                        if results:
                            self.assertTrue(all(not item.resolved for item in results))
                            self.assertTrue(all(not item.candidate_entities for item in results))
                        else:
                            self.assertEqual(results, [])
                case_count += 1
            self.assertEqual(case_count, 6)

    def test_conversation_vs_import_semantic_convergence(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            vault_root = base / "Vault"
            bootstrap_vault(vault_root, title="Test Project")
            (vault_root / "01_Characters").mkdir(parents=True, exist_ok=True)
            (vault_root / "01_Characters" / "Sera.md").write_text(
                note_frontmatter("character", "Sera", slug="sera") + "\n\nCourier.\n"
            )
            (vault_root / "02_World" / "Lore").mkdir(parents=True, exist_ok=True)
            (vault_root / "02_World" / "Lore" / "memory_ritual.md").write_text(
                note_frontmatter(
                    "lore",
                    "Memory Ritual",
                    slug="memory_ritual",
                    aliases=["ritual"],
                    project_confirmed_aliases=["ritual de memoria"],
                )
                + "\n\nA remembered rite.\n"
            )

            cases = [
                ConversationImportCase(
                    label="es-scene",
                    language="es",
                    conversation_text="Quiero estructurar esta escena sin perder la voz de Sera.",
                    import_text="Sera llega tarde al puerto.\n\nOrdenalo sin perder la voz de Sera.",
                    source_format="docx",
                    primary_intent_type="structuring_request",
                    expected_request_type="structuring_request",
                    expected_target_id="sera",
                    expected_target_type="character",
                    candidate_kind="character",
                    preserve_signals=["preserve_character_voice"],
                    change_signals=["structure_scene"],
                    author_goal_signals=["structure_scene"],
                ),
                ConversationImportCase(
                    label="en-revision",
                    language="en",
                    conversation_text="I want Memory Ritual to stay canon-safe while sounding calmer.",
                    import_text="Memory Ritual should stay canon-safe.\n\nThe note should sound calmer and clearer.",
                    source_format="docx",
                    primary_intent_type="editorial_revision",
                    expected_request_type="editorial_revision",
                    expected_target_id="memory_ritual",
                    expected_target_type="lore",
                    candidate_kind="lore",
                    preserve_signals=["preserve_validated_canon"],
                    change_signals=["align_tone"],
                    author_goal_signals=["align_tone"],
                ),
                ConversationImportCase(
                    label="ja-narration",
                    language="ja",
                    conversation_text="この章を語りの準備にして、Sera を守ってほしい。",
                    import_text="Sera.\n\n語りの準備を進める。",
                    source_format="docx",
                    primary_intent_type="narration_preparation",
                    expected_request_type="narration_preparation",
                    expected_target_id="sera",
                    expected_target_type="character",
                    candidate_kind="character",
                    preserve_signals=["preserve_character_voice"],
                    change_signals=["prepare_for_narration"],
                    author_goal_signals=["prepare_for_narration"],
                ),
                ConversationImportCase(
                    label="pt-mixed",
                    language="pt",
                    conversation_text="Quero revisar isto sem romper o canon e sem perder Sera.",
                    import_text="Quero revisar isto sem romper o canon.\n\nSera continua aqui.",
                    source_format="docx",
                    primary_intent_type="mixed_request",
                    expected_request_type="mixed_editorial_request",
                    expected_target_id="sera",
                    expected_target_type="character",
                    candidate_kind="character",
                    preserve_signals=["preserve_validated_canon", "preserve_character_voice"],
                    change_signals=["align_tone", "structure_scene"],
                    author_goal_signals=["align_tone", "structure_scene"],
                    has_mixed_request=True,
                    mixed_parts=[
                        ("narrative_content", "Sera continua aqui", 0.9),
                        ("meta_instruction", "revisa isto", 0.82),
                        ("preserve", "sem romper o canon", 0.84),
                    ],
                    content_mix_signals=["narrative_and_note_mix"],
                ),
            ]

            case_count = 0
            for case in cases:
                with self.subTest(label=case.label):
                    conversation_intent, conversation_editorial, conversation_planned = self._run_author_loop(
                        label=case.label,
                        raw_text=case.conversation_text,
                        language=case.language,
                        llm_payload=self._author_payload(
                            raw_text=case.conversation_text,
                            primary_intent_type=case.primary_intent_type,
                            target_id=case.expected_target_id,
                            target_type=case.expected_target_type,
                            author_goal_signals=case.author_goal_signals,
                            preserve_signals=case.preserve_signals,
                            change_signals=case.change_signals,
                            has_mixed_request=case.has_mixed_request,
                            parts=case.mixed_parts,
                            candidate_targets=[
                                CandidateTarget(
                                    target_id=case.expected_target_id,
                                    target_type=case.expected_target_type,
                                    confidence=0.84,
                                )
                            ],
                        ),
                        known_characters=[{"id": "sera", "names": ["Sera"]}],
                    )
                    conversation_entities = resolve_entities(
                        text=case.conversation_text,
                        vault_path=vault_root,
                        known_characters=[{"id": "sera", "names": ["Sera"]}],
                    )

                    self.assertEqual(conversation_intent.primary_intent_type, case.primary_intent_type)
                    self.assertEqual(conversation_editorial.request_type, case.expected_request_type)
                    self.assertEqual(conversation_planned.metadata["phase_classification"], "semantic")
                    self.assertTrue(conversation_planned.semantic_phase)
                    self.assertTrue(conversation_editorial.entity_hints)

                    docx_path = base / f"{case.label}.docx"
                    self._write_docx(
                        docx_path,
                        [paragraph for paragraph in case.import_text.split("\n\n") if paragraph.strip()],
                    )
                    seed = extract_light_source(docx_path)
                    escalation = decide_llm_escalation(seed)
                    prompt = build_derived_understanding_prompt(seed=seed, escalation=escalation)
                    self.assertIn("source_format", prompt.user_payload)
                    self.assertIn("llm_escalation", prompt.user_payload)
                    self.assertIn("recognized_or_recovered_text", prompt.required_output_schema)

                    import_payload = normalize_derived_llm_payload(
                        payload={
                            "source_id": seed.source_id,
                            "dominant_language": case.language,
                            "detected_languages": [case.language],
                            "has_mixed_language": case.has_mixed_request,
                            "overall_confidence": 0.84,
                            "structural_confidence": 0.78,
                            "content_mix_signals": case.content_mix_signals or [],
                            "warnings": ["derived_import_review"],
                            "segment_candidates": [
                                {
                                    "candidate_id": "cand_001",
                                    "segment_text": case.import_text,
                                    "heading_text": case.import_text.split("\n\n")[0],
                                    "probable_kind": case.candidate_kind,
                                    "language": case.language,
                                    "confidence": 0.8,
                                    "mixed_content": case.has_mixed_request,
                                    "boundary_hints": ["blank_line_boundary"],
                                    "notes": ["llm_structured_import"],
                                }
                            ],
                            "structure_signals": {
                                "recovered_headings": [case.import_text.split("\n\n")[0]],
                                "probable_block_order": ["cand_001"],
                                "recovered_lists": [],
                                "ordering_confidence": 0.76,
                                "structure_warnings": ["light_recovery"],
                                "confidence": 0.77,
                            },
                            "loss_signals": {
                                "missing_structure_signals": ["heading_loss_risk" if case.has_mixed_request else "minor_formatting_loss"],
                                "paragraph_merge_signals": [],
                                "heading_loss_signals": [],
                                "ordering_uncertainty_signals": [],
                                "coverage_risk_notes": ["review_if_promoted"],
                                "severity": "medium" if case.has_mixed_request else "low",
                                "mixed_language_degradation": [case.language] if case.has_mixed_request else [],
                            },
                            "needs_manual_review": case.has_mixed_request,
                            "recognized_or_recovered_text": case.import_text,
                        },
                        source_id=seed.source_id,
                        source_format=seed.source_format,
                        llm_used=True,
                        format_profile=seed.format_profile,
                    )
                    validated = validate_derived_extraction(seed=seed, payload=import_payload)
                    review = review_derived_source(
                        seed=seed,
                        escalation=escalation,
                        validated_extraction=validated,
                        llm_payload=import_payload,
                    )
                    import_entities = resolve_entities(
                        text=validated.recognized_or_recovered_text,
                        vault_path=vault_root,
                        known_characters=[{"id": "sera", "names": ["Sera"]}],
                    )

                    self.assertEqual(validated.review_status, review.review_status)
                    self.assertTrue(import_entities)
                    conversation_resolved = next(item for item in conversation_entities if item.resolved)
                    import_resolved = next(item for item in import_entities if item.resolved)
                    self.assertEqual(conversation_resolved.resolved_entity_id, import_resolved.resolved_entity_id)
                    self.assertEqual(import_resolved.resolved_entity_id, case.expected_target_id)
                    self.assertIn(conversation_editorial.semantic_basis, {"author_understanding_validated"})
                case_count += 1
            self.assertEqual(case_count, 4)

    def test_followup_multilingual_depends_on_context_not_triggers(self):
        cases = [
            ("es", "sigamos con eso"),
            ("en", "let's continue with that"),
            ("ja", "それで続けよう"),
            ("pt", "vamos continuar com isso"),
        ]
        case_count = 0
        for language, raw_text in cases:
            with self.subTest(language=language):
                manager = ConversationManager()
                state = create_conversation_state(explanation_language=language, artifact_target_language="ja")
                state = state.__class__(
                    **{**state.__dict__, "last_target_type": "lore", "last_target_id": "memory_ritual"}
                )
                manager.state = state
                turn = manager.handle_request(
                    ConversationRequest(
                        raw_text=raw_text,
                        source="user",
                        mode="normal",
                        interface_language=language,
                        user_command_language=language,
                        internal_system_language="en",
                        project_default_language="ja",
                        mixed_language_allowed=True,
                        explanation_language=language,
                    )
                )
                author_understanding = turn.recognized_intent.metadata["author_understanding"]
                self.assertEqual(author_understanding["primary_intent_type"], "contextual_followup")
                self.assertFalse(author_understanding["needs_clarification"])
                self.assertEqual(turn.planned_task.metadata["phase_classification"], "semantic")
                self.assertTrue(turn.planned_task.semantic_phase)
            case_count += 1
        self.assertEqual(case_count, 4)

    def test_semantic_phase_vs_operational_phase(self):
        planner = TaskPlanner()
        request = _request("scene scene_054_b", language="es")
        cases = [
            (
                "semantic inspect scene",
                RecognizedIntent(
                    intent_name="inspect_scene",
                    confidence=0.95,
                    target_type="scene",
                    target_id="scene_054_b",
                    requires_target=True,
                ),
                True,
                "semantic",
            ),
            (
                "semantic consistency",
                RecognizedIntent(
                    intent_name="consistency_check",
                    confidence=0.95,
                    target_type="scene",
                    target_id="scene_054_b",
                    requires_target=True,
                ),
                True,
                "semantic",
            ),
            (
                "operational confirm",
                RecognizedIntent(intent_name="confirm_pending", confidence=0.95),
                False,
                "operational",
            ),
            (
                "operational cancel",
                RecognizedIntent(intent_name="cancel_pending", confidence=0.95),
                False,
                "operational",
            ),
            (
                "operational help",
                RecognizedIntent(intent_name="conversation_help", confidence=0.95),
                False,
                "operational",
            ),
        ]
        case_count = 0
        for label, intent, expected_semantic, expected_classification in cases:
            with self.subTest(label=label):
                task = planner.plan(request, intent, create_conversation_state(explanation_language="es", artifact_target_language="ja"))
                self.assertEqual(task.semantic_phase, expected_semantic)
                self.assertEqual(task.metadata["phase_classification"], expected_classification)
            case_count += 1
        self.assertEqual(case_count, 5)

    def test_false_certainty_and_clarification_stay_conservative(self):
        ambiguous_payloads = [
            self._author_payload(
                raw_text="hazlo mejor",
                primary_intent_type="unknown",
                target_id=None,
                target_type=None,
                needs_clarification=True,
                clarification_reason="ambiguous request",
                author_goal_signals=[],
                preserve_signals=[],
                change_signals=[],
                candidate_targets=[],
            ),
            self._author_payload(
                raw_text="改めて",
                primary_intent_type="mixed_request",
                target_id=None,
                target_type=None,
                needs_clarification=True,
                clarification_reason="ambiguous mixed request",
                author_goal_signals=[],
                preserve_signals=[],
                change_signals=[],
                has_mixed_request=True,
                candidate_targets=[],
                parts=[("meta_instruction", "もう一度", 0.64), ("followup_reference", "それ", 0.62)],
            ),
        ]
        raw_texts = ["hazlo mejor", "改めて"]
        case_count = 0
        for raw_text, payload in zip(raw_texts, ambiguous_payloads, strict=True):
            with self.subTest(raw_text=raw_text):
                interpretation, editorial_intent, planned_task = self._run_author_loop(
                    label=raw_text,
                    raw_text=raw_text,
                    language="es",
                    llm_payload=payload,
                )
                self.assertTrue(interpretation.needs_clarification)
                self.assertIsNone(interpretation.disambiguation.preferred_target)
                self.assertIn(interpretation.primary_intent_type, {"unknown", "mixed_request"})
                if editorial_intent is None:
                    self.assertIsNone(planned_task.metadata.get("editorial_intent"))
                else:
                    self.assertEqual(editorial_intent.followup_mode, "require_clarification")
                    self.assertIsNone(editorial_intent.resolved_target_id)
                    self.assertIsNone(editorial_intent.resolved_target_type)
            case_count += 1
        self.assertEqual(case_count, 2)

    def test_project_aliases_cross_language_help_vaerl(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_root = Path(tmp) / "Vault"
            bootstrap_vault(vault_root, title="Test Project")
            (vault_root / "02_World" / "Lore" / "memory_ritual.md").write_text(
                note_frontmatter(
                    "lore",
                    "Memory Ritual",
                    slug="memory_ritual",
                    project_confirmed_aliases=["ritual de memoria", "memoriaの儀式", "ritual de memoria"],
                )
                + "\n\n"
            )
            cases = [
                ("es", "ritual de memoria"),
                ("pt", "ritual de memoria"),
                ("ja", "memoriaの儀式"),
            ]
            case_count = 0
            for language, text in cases:
                with self.subTest(language=language, text=text):
                    results = resolve_text_against_vault(text=text, vault_path=vault_root)
                    result = next(item for item in results if item.resolved)
                    self.assertTrue(result.resolved)
                    self.assertEqual(result.resolved_entity_id, "memory_ritual")
                    self.assertEqual(result.candidate_entities[0].match_source, "project_confirmed_alias")
                case_count += 1
            self.assertEqual(case_count, 3)

    def test_partial_smoke_simulation(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            vault_root = base / "Vault"
            bootstrap_vault(vault_root, title="Test Project")
            (vault_root / "01_Characters").mkdir(parents=True, exist_ok=True)
            (vault_root / "01_Characters" / "Sera.md").write_text(
                note_frontmatter("character", "Sera", slug="sera") + "\n\nCourier.\n"
            )
            (vault_root / "02_World" / "Lore").mkdir(parents=True, exist_ok=True)
            (vault_root / "02_World" / "Lore" / "memory_ritual.md").write_text(
                note_frontmatter(
                    "lore",
                    "Memory Ritual",
                    slug="memory_ritual",
                    project_confirmed_aliases=["ritual de memoria"],
                )
                + "\n\n"
            )

            step_1_payload = self._author_payload(
                raw_text="Quiero estructurar esta escena sin perder la voz de Sera.",
                primary_intent_type="structuring_request",
                target_id="sera",
                target_type="character",
                author_goal_signals=["structure_scene"],
                preserve_signals=["preserve_character_voice"],
                change_signals=["structure_scene"],
            )
            turn_1 = ConversationManager(
                author_understanding_analyzer=HybridAuthorUnderstandingAnalyzer(
                    llm_interpreter=_StaticAuthorUnderstandingInterpreter(step_1_payload)
                )
            ).handle_request(
                ConversationRequest(
                    raw_text="Quiero estructurar esta escena sin perder la voz de Sera.",
                    source="user",
                    mode="normal",
                    interface_language="es",
                    user_command_language="es",
                    internal_system_language="en",
                    project_default_language="ja",
                    mixed_language_allowed=True,
                    explanation_language="es",
                    metadata={"known_characters": [{"id": "sera", "names": ["Sera"]}]},
                )
            )
            self.assertEqual(turn_1.recognized_intent.metadata["author_understanding"]["primary_intent_type"], "structuring_request")
            self.assertTrue(turn_1.planned_task.semantic_phase)

            manager = ConversationManager()
            followup_state = create_conversation_state(explanation_language="ja", artifact_target_language="ja")
            followup_state = followup_state.__class__(
                **{**followup_state.__dict__, "last_target_type": "lore", "last_target_id": "memory_ritual"}
            )
            manager.state = followup_state
            turn_2 = manager.handle_request(
                ConversationRequest(
                    raw_text="それで続けよう",
                    source="user",
                    mode="normal",
                    interface_language="ja",
                    user_command_language="ja",
                    internal_system_language="en",
                    project_default_language="ja",
                    mixed_language_allowed=True,
                    explanation_language="ja",
                )
            )
            self.assertEqual(turn_2.recognized_intent.metadata["author_understanding"]["primary_intent_type"], "contextual_followup")
            self.assertTrue(turn_2.planned_task.semantic_phase)

            alias_results = resolve_text_against_vault(text="ritual de memoria", vault_path=vault_root)
            alias_result = next(item for item in alias_results if item.resolved)
            self.assertEqual(alias_result.resolved_entity_id, "memory_ritual")

            source_path = base / "imported.docx"
            self._write_docx(
                source_path,
                [
                    "Sera llega tarde al puerto.",
                    "Ordenalo y dejalo listo para narracion.",
                    "文脈を保ってください。",
                ],
            )
            seed = extract_light_source(source_path)
            escalation = decide_llm_escalation(seed)
            prompt = build_derived_understanding_prompt(seed=seed, escalation=escalation)
            self.assertIn("recognized_or_recovered_text", prompt.required_output_schema)
            self.assertIn("quality_signals", prompt.user_payload)
            derived_payload = normalize_derived_llm_payload(
                payload={
                    "source_id": seed.source_id,
                    "dominant_language": "es",
                    "detected_languages": ["es", "ja"],
                    "has_mixed_language": True,
                    "overall_confidence": 0.81,
                    "structural_confidence": 0.74,
                    "content_mix_signals": ["narrative_and_note_mix"],
                    "warnings": ["mixed_language"],
                    "segment_candidates": [
                        {
                            "candidate_id": "cand_001",
                            "segment_text": "Sera llega tarde al puerto.",
                            "heading_text": "Sera llega tarde al puerto.",
                            "probable_kind": "scene",
                            "language": "es",
                            "confidence": 0.82,
                            "mixed_content": True,
                            "boundary_hints": ["blank_line_boundary"],
                            "notes": ["llm_structured_import"],
                        }
                    ],
                    "structure_signals": {
                        "recovered_headings": ["Sera llega tarde al puerto."],
                        "probable_block_order": ["cand_001"],
                        "recovered_lists": [],
                        "ordering_confidence": 0.73,
                        "structure_warnings": ["light_recovery"],
                        "confidence": 0.74,
                    },
                    "loss_signals": {
                        "missing_structure_signals": ["paragraph_merge_risk"],
                        "paragraph_merge_signals": ["possible_merge"],
                        "heading_loss_signals": [],
                        "ordering_uncertainty_signals": ["minor_order_uncertainty"],
                        "coverage_risk_notes": ["needs_review"],
                        "severity": "medium",
                        "mixed_language_degradation": ["es_ja_mix"],
                    },
                    "needs_manual_review": True,
                    "recognized_or_recovered_text": "Sera llega tarde al puerto.\n\nOrdenalo y dejalo listo para narracion.\n\n文脈を保ってください。",
                },
                source_id=seed.source_id,
                source_format=seed.source_format,
                llm_used=True,
                format_profile=seed.format_profile,
            )
            validated = validate_derived_extraction(seed=seed, payload=derived_payload)
            review = review_derived_source(
                seed=seed,
                escalation=escalation,
                validated_extraction=validated,
                llm_payload=derived_payload,
            )
            self.assertEqual(review.review_status, validated.review_status)
            self.assertTrue(review.strict_confirmation_required)

            planner = TaskPlanner()
            semantic_task = planner.plan(
                _request("scene scene_054_b", language="es"),
                RecognizedIntent(
                    intent_name="inspect_scene",
                    confidence=0.93,
                    target_type="scene",
                    target_id="scene_054_b",
                    requires_target=True,
                ),
                create_conversation_state(explanation_language="es", artifact_target_language="ja"),
            )
            operational_task = planner.plan(
                _request("confirm pending", language="en"),
                RecognizedIntent(intent_name="confirm_pending", confidence=0.96),
                create_conversation_state(explanation_language="es", artifact_target_language="ja"),
            )
            self.assertTrue(semantic_task.semantic_phase)
            self.assertFalse(operational_task.semantic_phase)
            self.assertEqual(semantic_task.metadata["phase_classification"], "semantic")
            self.assertEqual(operational_task.metadata["phase_classification"], "operational")

            turn_3 = manager.handle_request(
                ConversationRequest(
                    raw_text="let's continue with that",
                    source="user",
                    mode="normal",
                    interface_language="en",
                    user_command_language="en",
                    internal_system_language="en",
                    project_default_language="ja",
                    mixed_language_allowed=True,
                    explanation_language="en",
                )
            )
            self.assertEqual(turn_3.recognized_intent.metadata["author_understanding"]["primary_intent_type"], "contextual_followup")
            self.assertTrue(turn_3.planned_task.semantic_phase)

    def _run_author_loop(
        self,
        *,
        label: str,
        raw_text: str,
        language: str,
        llm_payload: LLMAuthorUnderstandingPayload,
        state=None,
        known_characters: list[dict[str, object]] | None = None,
    ) -> tuple[AuthorIntentInterpretation, object, object]:
        analyzer = HybridAuthorUnderstandingAnalyzer(
            llm_interpreter=_StaticAuthorUnderstandingInterpreter(llm_payload)
        )
        request = _request(raw_text, language, metadata={"known_characters": known_characters or [], "test_case": label})
        rule_intent = RecognizedIntent(intent_name="unknown", confidence=0.2)
        entity_results = []
        interpretation = analyzer.analyze(
            request=request,
            rule_intent=rule_intent,
            narrative_signals=rule_intent.narrative_signals,
            entity_results=entity_results,
            state=state,
        )
        editorial_intent = classify_editorial_intent(
            raw_text=raw_text,
            recognized_intent_name=rule_intent.intent_name,
            entity_results=entity_results,
            narrative_signals=rule_intent.narrative_signals,
            state=state,
            author_understanding=interpretation,
        )
        recognized_intent = RecognizedIntent(
            intent_name=rule_intent.intent_name,
            confidence=rule_intent.confidence,
            editorial_intent=editorial_intent,
            narrative_signals=rule_intent.narrative_signals,
            metadata={
                "author_understanding": asdict(interpretation),
                "editorial_intent": asdict(editorial_intent) if editorial_intent is not None else None,
                "vaerl_results": [asdict(item) for item in entity_results],
            },
        )
        planned_task = TaskPlanner().plan(request, recognized_intent, state)
        return interpretation, editorial_intent, planned_task

    def _author_payload(
        self,
        *,
        raw_text: str,
        primary_intent_type: str,
        target_id: str | None,
        target_type: str | None,
        author_goal_signals: list[str],
        preserve_signals: list[str],
        change_signals: list[str],
        confidence: float = 0.9,
        has_mixed_request: bool = False,
        parts: list[tuple[str, str, float]] | None = None,
        candidate_targets: list[CandidateTarget] | None = None,
        entity_hints: list[EntityHint] | None = None,
        needs_clarification: bool = False,
        clarification_reason: str | None = None,
    ) -> LLMAuthorUnderstandingPayload:
        candidate_targets = list(candidate_targets or [])
        if not candidate_targets and target_id and target_type:
            candidate_targets = [CandidateTarget(target_id=target_id, target_type=target_type, confidence=0.84)]
        entity_hints = list(entity_hints or [])
        if not entity_hints and target_id and target_type:
            entity_hints = [
                EntityHint(
                    hint_text=target_id.replace("_", " "),
                    normalized_hint=target_id,
                    hint_kind="semantic_target",
                    hint_source="author_understanding",
                    confidence=0.84,
                    supported_by_author_understanding=True,
                    candidate_target_id=target_id,
                    candidate_target_type=target_type,
                )
            ]
        if parts is None:
            parts = [("mixed", raw_text, 0.72)]
        mixed_parts = [MixedRequestPart(part_type=part_type, text=text, confidence=score) for part_type, text, score in parts]
        preferred_target = candidate_targets[0] if candidate_targets else None
        disambiguation = DisambiguationResult(
            candidate_targets=list(candidate_targets),
            preferred_target=preferred_target if not needs_clarification else None,
            confidence=preferred_target.confidence if preferred_target else 0.0,
            reason=clarification_reason or ("supported target" if preferred_target else "ambiguous request"),
            requires_user_confirmation=needs_clarification or not bool(preferred_target),
        )
        return LLMAuthorUnderstandingPayload(
            raw_text=raw_text,
            provider_name="stub",
            model="stub-model",
            primary_intent_type=primary_intent_type,
            secondary_intent_types=[],
            confidence=confidence,
            has_mixed_request=has_mixed_request,
            author_goal_signals=list(author_goal_signals),
            preserve_signals=list(preserve_signals),
            change_signals=list(change_signals),
            entity_hints=entity_hints,
            followup_reference_text=None,
            narrative_content_text=raw_text if primary_intent_type == "narrative_facts" else None,
            meta_instruction_text=raw_text if primary_intent_type in {"structuring_request", "editorial_revision", "narration_preparation", "mixed_request"} else None,
            needs_clarification=needs_clarification,
            clarification_reason=clarification_reason,
            parts=mixed_parts,
            candidate_targets=list(candidate_targets),
            preferred_target=preferred_target,
            disambiguation_reason=(clarification_reason or "supported target") if preferred_target else "ambiguous request",
            raw_payload={"test_case": primary_intent_type},
        )

    def _write_docx(self, path: Path, paragraphs: list[str]) -> None:
        content = [
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">',
            "<w:body>",
        ]
        for paragraph in paragraphs:
            content.append(f"<w:p><w:r><w:t>{_escape_xml(paragraph)}</w:t></w:r></w:p>")
        content.append("</w:body></w:document>")
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("word/document.xml", "".join(content))


def _request(raw_text: str, language: str, metadata: dict[str, object] | None = None) -> ConversationRequest:
    return ConversationRequest(
        raw_text=raw_text,
        source="user",
        mode="normal",
        interface_language=language,
        user_command_language=language,
        internal_system_language="en",
        project_default_language="ja",
        mixed_language_allowed=True,
        explanation_language=language,
        metadata=metadata or {},
    )


def _escape_xml(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )
class _StaticAuthorUnderstandingInterpreter:
    def __init__(self, payload: LLMAuthorUnderstandingPayload) -> None:
        self.payload = payload

    def interpret(self, **kwargs):
        return self.payload


if __name__ == "__main__":
    unittest.main()
