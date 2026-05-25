from __future__ import annotations

import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from types import SimpleNamespace

from providers.text_provider import TextGenerationResponse

MODULE_PATH = Path("scripts/dev/real_provider_dryrun.py").resolve()
SPEC = importlib.util.spec_from_file_location("real_provider_dryrun", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)
MATRIX_MODULE_PATH = Path("scripts/dev/deepseek_prompt_matrix.py").resolve()
MATRIX_SPEC = importlib.util.spec_from_file_location("deepseek_prompt_matrix", MATRIX_MODULE_PATH)
assert MATRIX_SPEC and MATRIX_SPEC.loader
MATRIX_MODULE = importlib.util.module_from_spec(MATRIX_SPEC)
sys.modules[MATRIX_SPEC.name] = MATRIX_MODULE
MATRIX_SPEC.loader.exec_module(MATRIX_MODULE)
FAMILY_MODULE_PATH = Path("scripts/dev/deepseek_family_harness_matrix.py").resolve()
FAMILY_SPEC = importlib.util.spec_from_file_location("deepseek_family_harness_matrix", FAMILY_MODULE_PATH)
assert FAMILY_SPEC and FAMILY_SPEC.loader
FAMILY_MODULE = importlib.util.module_from_spec(FAMILY_SPEC)
sys.modules[FAMILY_SPEC.name] = FAMILY_MODULE
FAMILY_SPEC.loader.exec_module(FAMILY_MODULE)
E2E_MODULE_PATH = Path("scripts/dev/real_deepseek_e2e_dryrun.py").resolve()
E2E_SPEC = importlib.util.spec_from_file_location("real_deepseek_e2e_dryrun", E2E_MODULE_PATH)
assert E2E_SPEC and E2E_SPEC.loader
E2E_MODULE = importlib.util.module_from_spec(E2E_SPEC)
sys.modules[E2E_SPEC.name] = E2E_MODULE
E2E_SPEC.loader.exec_module(E2E_MODULE)
FIXTURE_ROOT = Path("tests/fixtures/textifai/real_provider_dryrun/expected")


class RealProviderDryRunGuardsTests(unittest.TestCase):
    def test_without_allow_provider_calls_aborts_before_provider_creation(self):
        with tempfile.TemporaryDirectory() as tmp:
            prompt_path = Path(tmp) / "capture.md"
            prompt_path.write_text(_sample_capture_markdown(), encoding="utf-8")
            called = {"provider": False}

            def fail_provider(*args, **kwargs):
                called["provider"] = True
                raise AssertionError("provider should not be created")

            args = MODULE.build_parser().parse_args(
                [
                    "--prompt-file",
                    str(prompt_path),
                    "--provider",
                    "deepseek",
                    "--model",
                    "deepseek-v4-flash",
                ]
            )

            with self.assertRaises(MODULE.DryRunError):
                MODULE.run_once(args, provider_factory=fail_provider, provider_config_error=lambda *_: None)

            self.assertFalse(called["provider"])

    def test_max_provider_requests_must_be_exactly_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            prompt_path = Path(tmp) / "capture.md"
            prompt_path.write_text(_sample_capture_markdown(), encoding="utf-8")
            args = MODULE.build_parser().parse_args(
                [
                    "--prompt-file",
                    str(prompt_path),
                    "--provider",
                    "deepseek",
                    "--model",
                    "deepseek-v4-flash",
                    "--allow-provider-calls",
                    "--max-provider-requests",
                    "2",
                ]
            )

            with self.assertRaises(MODULE.DryRunError):
                MODULE.run_once(args, provider_factory=lambda *_: None, provider_config_error=lambda *_: None)

    def test_missing_prompt_file_aborts(self):
        args = MODULE.build_parser().parse_args(
            [
                "--prompt-file",
                "/tmp/does_not_exist.md",
                "--provider",
                "deepseek",
                "--model",
                "deepseek-v4-flash",
                "--allow-provider-calls",
                "--max-provider-requests",
                "1",
            ]
        )

        with self.assertRaises(MODULE.DryRunError):
            MODULE.run_once(args, provider_factory=lambda *_: None, provider_config_error=lambda *_: None)

    def test_markdown_parser_extracts_system_and_message_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            prompt_path = Path(tmp) / "capture.md"
            prompt_path.write_text(_sample_capture_markdown(), encoding="utf-8")

            prompt = MODULE._read_capture_markdown(prompt_path)

        self.assertEqual(prompt.system_prompt, "Return only valid JSON for one chapter extraction.")
        self.assertEqual(prompt.user_prompt, '{"chapter_id":"ch_002","content":"test"}')
        self.assertEqual(len(prompt.file_sha256), 64)

    def test_fake_provider_run_writes_manifest_response_and_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            prompt_path = Path(tmp) / "capture.md"
            prompt_path.write_text(_sample_capture_markdown(), encoding="utf-8")
            output_root = Path(tmp) / "out"
            captured = {}

            class Provider:
                def generate(self, request):
                    captured["request"] = request
                    return TextGenerationResponse(
                        text=json.dumps(_valid_payload(), ensure_ascii=False),
                        raw={"ok": True},
                        provider_name="deepseek",
                        model="deepseek-v4-flash",
                        task="bootstrap_chapter_extraction",
                    )

            args = MODULE.build_parser().parse_args(
                [
                    "--prompt-file",
                    str(prompt_path),
                    "--provider",
                    "deepseek",
                    "--model",
                    "deepseek-v4-flash",
                    "--output-root",
                    str(output_root),
                    "--allow-provider-calls",
                    "--max-provider-requests",
                    "1",
                    "--response-format-json",
                    "--no-write-back",
                ]
            )

            result = MODULE.run_once(args, provider_factory=lambda *_: Provider(), provider_config_error=lambda *_: None)

            output_dir = Path(result.output_dir)
            self.assertTrue((output_dir / "dryrun_manifest.json").exists())
            self.assertTrue((output_dir / "provider_response_raw.txt").exists())
            self.assertTrue((output_dir / "provider_response.json").exists())
            self.assertTrue((output_dir / "validation_report.json").exists())
            self.assertFalse((output_dir / "prompt_trace.json").exists())
            self.assertEqual(captured["request"].response_format, {"type": "json_object"})
            self.assertEqual(captured["request"].provider_name, "deepseek")
            self.assertEqual(captured["request"].model, "deepseek-v4-flash")
            self.assertEqual(captured["request"].max_tokens, 8192)

            manifest = json.loads((output_dir / "dryrun_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["max_output_tokens"], 8192)
            self.assertEqual(manifest["max_output_tokens_source"], "default")
            self.assertEqual(manifest["provider_profile_id"], None)
            self.assertFalse(manifest["provider_profile_applied"])
            validation = json.loads((output_dir / "validation_report.json").read_text(encoding="utf-8"))
            self.assertTrue(validation["ok"])
            self.assertEqual(validation["details"]["chapter_id"], "ch_002")
            self.assertFalse((output_dir / "runs").exists())
            self.assertFalse((output_dir / "vault").exists())

    def test_non_parseable_output_generates_failed_validation_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            prompt_path = Path(tmp) / "capture.md"
            prompt_path.write_text(_sample_capture_markdown(), encoding="utf-8")
            output_root = Path(tmp) / "out"

            class Provider:
                def generate(self, request):
                    return TextGenerationResponse(
                        text="not json",
                        raw={},
                        provider_name="deepseek",
                        model="deepseek-v4-flash",
                        task="bootstrap_chapter_extraction",
                    )

            args = MODULE.build_parser().parse_args(
                [
                    "--prompt-file",
                    str(prompt_path),
                    "--provider",
                    "deepseek",
                    "--model",
                    "deepseek-v4-flash",
                    "--output-root",
                    str(output_root),
                    "--allow-provider-calls",
                    "--max-provider-requests",
                    "1",
                    "--response-format-json",
                ]
            )

            result = MODULE.run_once(args, provider_factory=lambda *_: Provider(), provider_config_error=lambda *_: None)
            output_dir = Path(result.output_dir)
            self.assertFalse((output_dir / "provider_response.json").exists())
            validation = json.loads((output_dir / "validation_report.json").read_text(encoding="utf-8"))
            self.assertFalse(validation["ok"])
            self.assertFalse(validation["response_parseable_json"])

    def test_user_provided_max_output_tokens_reaches_request_and_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            prompt_path = Path(tmp) / "capture.md"
            prompt_path.write_text(_sample_capture_markdown(), encoding="utf-8")
            output_root = Path(tmp) / "out"
            captured = {}

            class Provider:
                def generate(self, request):
                    captured["request"] = request
                    return TextGenerationResponse(
                        text=json.dumps(_valid_payload(), ensure_ascii=False),
                        raw={},
                        provider_name="deepseek",
                        model="deepseek-v4-flash",
                        task="bootstrap_chapter_extraction",
                    )

            args = MODULE.build_parser().parse_args(
                [
                    "--prompt-file",
                    str(prompt_path),
                    "--provider",
                    "deepseek",
                    "--model",
                    "deepseek-v4-flash",
                    "--output-root",
                    str(output_root),
                    "--allow-provider-calls",
                    "--max-provider-requests",
                    "1",
                    "--max-output-tokens",
                    "8192",
                    "--response-format-json",
                ]
            )

            result = MODULE.run_once(args, provider_factory=lambda *_: Provider(), provider_config_error=lambda *_: None)

            self.assertEqual(captured["request"].max_tokens, 8192)
            manifest = json.loads((Path(result.output_dir) / "dryrun_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["max_output_tokens"], 8192)
            self.assertEqual(manifest["max_output_tokens_source"], "user_provided")

    def test_provider_profile_auto_applies_overlay_and_records_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            prompt_path = Path(tmp) / "capture.md"
            prompt_path.write_text(_sample_capture_markdown(), encoding="utf-8")
            output_root = Path(tmp) / "out"
            captured = {}

            class Provider:
                def generate(self, request):
                    captured["request"] = request
                    return TextGenerationResponse(
                        text=json.dumps(_valid_payload(), ensure_ascii=False),
                        raw={},
                        provider_name="deepseek",
                        model="deepseek-v4-flash",
                        task="bootstrap_chapter_extraction",
                    )

            args = MODULE.build_parser().parse_args(
                [
                    "--prompt-file",
                    str(prompt_path),
                    "--provider",
                    "deepseek",
                    "--model",
                    "deepseek-v4-flash",
                    "--output-root",
                    str(output_root),
                    "--allow-provider-calls",
                    "--max-provider-requests",
                    "1",
                    "--provider-profile",
                    "auto",
                    "--response-format-json",
                ]
            )

            result = MODULE.run_once(args, provider_factory=lambda *_: Provider(), provider_config_error=lambda *_: None)
            self.assertIn("## Provider Profile Overlay", captured["request"].system)
            self.assertEqual(captured["request"].max_tokens, 8192)
            manifest = json.loads((Path(result.output_dir) / "dryrun_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["provider_profile_requested"], "auto")
            self.assertEqual(manifest["provider_profile_id"], "deepseek-v4-flash:bootstrap_chapter_extraction:oer_focus_v1")
            self.assertTrue(manifest["provider_profile_applied"])
            self.assertEqual(manifest["max_output_tokens_source"], "provider_profile")

    def test_prompt_overlay_file_appends_dev_overlay_and_records_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            prompt_path = Path(tmp) / "capture.md"
            prompt_path.write_text(_sample_capture_markdown(), encoding="utf-8")
            overlay_path = Path(tmp) / "overlay.md"
            overlay_path.write_text("Return exactly one valid JSON object. Do not use markdown.", encoding="utf-8")
            output_root = Path(tmp) / "out"
            captured = {}

            class Provider:
                def generate(self, request):
                    captured["request"] = request
                    return TextGenerationResponse(
                        text=json.dumps(_valid_payload(), ensure_ascii=False),
                        raw={},
                        provider_name="deepseek",
                        model="deepseek-v4-flash",
                        task="bootstrap_chapter_extraction",
                    )

            args = MODULE.build_parser().parse_args(
                [
                    "--prompt-file",
                    str(prompt_path),
                    "--provider",
                    "deepseek",
                    "--model",
                    "deepseek-v4-flash",
                    "--output-root",
                    str(output_root),
                    "--allow-provider-calls",
                    "--max-provider-requests",
                    "1",
                    "--response-format-json",
                    "--prompt-overlay-file",
                    str(overlay_path),
                ]
            )

            result = MODULE.run_once(args, provider_factory=lambda *_: Provider(), provider_config_error=lambda *_: None)
            manifest = json.loads((Path(result.output_dir) / "dryrun_manifest.json").read_text(encoding="utf-8"))

            self.assertIn("## Dev Prompt Overlay", captured["request"].system)
            self.assertIn("Do not use markdown", captured["request"].system)
            self.assertTrue(manifest["prompt_overlay_applied"])
            self.assertEqual(manifest["prompt_overlay_file"], str(overlay_path))

    def test_prompt_matrix_variant_definitions_are_work_agnostic_and_scoring_prefers_density(self):
        blob = json.dumps(MATRIX_MODULE.variant_definitions(), ensure_ascii=False)
        self.assertNotIn("セラ", blob)
        self.assertNotIn("王者の杖", blob)
        self.assertNotIn("アデルマン", blob)
        self.assertNotIn("ティセイア", blob)
        self.assertNotIn("ベル", blob)
        self.assertEqual(len(MATRIX_MODULE.VARIANTS), 6)

        round2_blob = json.dumps(MATRIX_MODULE.variant_definitions("round2"), ensure_ascii=False)
        self.assertNotIn("セラ", round2_blob)
        self.assertNotIn("王者の杖", round2_blob)
        self.assertNotIn("アデルマン", round2_blob)
        self.assertNotIn("ティセイア", round2_blob)
        self.assertNotIn("ベル", round2_blob)
        self.assertEqual(len(MATRIX_MODULE.variant_definitions("round2")), 6)

        family_blob = json.dumps(FAMILY_MODULE.variant_definitions(), ensure_ascii=False)
        self.assertNotIn("セラ", family_blob)
        self.assertNotIn("王者の杖", family_blob)
        self.assertNotIn("アデルマン", family_blob)
        self.assertNotIn("ティセイア", family_blob)
        self.assertNotIn("ベル", family_blob)
        self.assertEqual(len(FAMILY_MODULE.variant_definitions()), 4)

        low = MATRIX_MODULE.score_variant(
            parseable_json=True,
            validation_ok=True,
            counts={"characters": 1, "places": 1, "concepts": 1, "objects": 1, "events": 1, "relations": 1, "unresolved_mentions": 0},
            event_importance_present=True,
            relation_category_present=True,
            missing_required_sections=[],
            response_text_chars=3000,
        )
        high = MATRIX_MODULE.score_variant(
            parseable_json=True,
            validation_ok=True,
            counts={"characters": 2, "places": 2, "concepts": 2, "objects": 3, "events": 4, "relations": 5, "unresolved_mentions": 1},
            event_importance_present=True,
            relation_category_present=True,
            missing_required_sections=[],
            response_text_chars=4000,
        )
        self.assertGreater(high, low)
        self.assertEqual(
            MATRIX_MODULE.score_variant(
                parseable_json=False,
                validation_ok=False,
                counts={},
                event_importance_present=False,
                relation_category_present=False,
                missing_required_sections=["characters"],
                response_text_chars=1000,
            ),
            0.0,
        )

    def test_zero_or_negative_max_output_tokens_aborts_before_provider_creation(self):
        for value in ["0", "-1"]:
            with self.subTest(value=value):
                with tempfile.TemporaryDirectory() as tmp:
                    prompt_path = Path(tmp) / "capture.md"
                    prompt_path.write_text(_sample_capture_markdown(), encoding="utf-8")
                    called = {"provider": False}

                    def fail_provider(*args, **kwargs):
                        called["provider"] = True
                        raise AssertionError("provider should not be created")

                    args = MODULE.build_parser().parse_args(
                        [
                            "--prompt-file",
                            str(prompt_path),
                            "--provider",
                            "deepseek",
                            "--model",
                            "deepseek-v4-flash",
                            "--allow-provider-calls",
                            "--max-provider-requests",
                            "1",
                            "--max-output-tokens",
                            value,
                        ]
                    )

                    with self.assertRaises(MODULE.DryRunError):
                        MODULE.run_once(args, provider_factory=fail_provider, provider_config_error=lambda *_: None)
                    self.assertFalse(called["provider"])

    def test_run_returns_error_code_and_does_not_print_secret(self):
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            code = MODULE.run(
                [
                    "--prompt-file",
                    "/tmp/missing.md",
                    "--provider",
                    "deepseek",
                    "--model",
                    "deepseek-v4-flash",
                ],
                provider_factory=lambda *_: None,
                provider_config_error=lambda *_: None,
            )
        self.assertEqual(code, 2)
        self.assertIn("ERROR:", stderr.getvalue())
        self.assertNotIn("test-key", stderr.getvalue())

    def test_expected_runtime_reports_are_parseable_and_do_not_embed_private_output(self):
        for path in [
            FIXTURE_ROOT / "deepseek_ch002_runtime_summary_after_sp059.json",
            FIXTURE_ROOT / "deepseek_ch002_vs_sp056_baseline_report.json",
            FIXTURE_ROOT / "deepseek_ch002_runtime_issue_report.json",
            FIXTURE_ROOT / "provider_prompt_profiles_product_opportunity_report.json",
            FIXTURE_ROOT / "deepseek_ch002_profiled_runtime_summary_after_sp061.json",
            FIXTURE_ROOT / "deepseek_ch002_profiled_vs_generic_report.json",
            FIXTURE_ROOT / "deepseek_ch002_profiled_vs_sp056_baseline_report.json",
            FIXTURE_ROOT / "deepseek_provider_profile_runtime_issue_report.json",
            FIXTURE_ROOT / "deepseek_ch002_profiled_runtime_summary_after_sp062.json",
            FIXTURE_ROOT / "deepseek_ch002_profiled_vs_generic_report_after_sp062.json",
            FIXTURE_ROOT / "deepseek_ch002_profiled_vs_sp056_baseline_report_after_sp062.json",
            FIXTURE_ROOT / "deepseek_provider_profile_runtime_issue_report_after_sp062.json",
            FIXTURE_ROOT / "deepseek_ch002_compact_profile_runtime_summary_after_sp064.json",
            FIXTURE_ROOT / "deepseek_ch002_compact_profile_vs_generic_report_after_sp064.json",
            FIXTURE_ROOT / "deepseek_ch002_compact_profile_vs_failed_profile_report_after_sp064.json",
            FIXTURE_ROOT / "deepseek_ch002_compact_profile_vs_sp056_baseline_report_after_sp064.json",
            FIXTURE_ROOT / "deepseek_compact_profile_runtime_issue_report_after_sp064.json",
            FIXTURE_ROOT / "deepseek_ch002_prompt_matrix_summary_after_sp065.json",
            FIXTURE_ROOT / "deepseek_ch002_prompt_matrix_variant_report_after_sp065.json",
            FIXTURE_ROOT / "deepseek_ch002_prompt_matrix_decision_after_sp065.json",
            FIXTURE_ROOT / "deepseek_strategy_matrix_summary_after_sp066.json",
            FIXTURE_ROOT / "deepseek_strategy_matrix_variants_after_sp066.json",
            FIXTURE_ROOT / "deepseek_strategy_matrix_ch002_report_after_sp066.json",
            FIXTURE_ROOT / "deepseek_strategy_matrix_ch003_report_after_sp066.json",
            FIXTURE_ROOT / "deepseek_strategy_matrix_decision_after_sp066.json",
            FIXTURE_ROOT / "deepseek_flash_harness_round2_summary_after_sp067.json",
            FIXTURE_ROOT / "deepseek_flash_harness_round2_variants_after_sp067.json",
            FIXTURE_ROOT / "deepseek_flash_harness_round2_ch002_report_after_sp067.json",
            FIXTURE_ROOT / "deepseek_flash_harness_round2_ch003_report_after_sp067.json",
            FIXTURE_ROOT / "deepseek_flash_harness_round2_decision_after_sp067.json",
            FIXTURE_ROOT / "deepseek_family_model_discovery_after_sp068.json",
            FIXTURE_ROOT / "deepseek_family_harness_matrix_summary_after_sp068.json",
            FIXTURE_ROOT / "deepseek_family_harness_matrix_variants_after_sp068.json",
            FIXTURE_ROOT / "deepseek_family_harness_ch002_report_after_sp068.json",
            FIXTURE_ROOT / "deepseek_family_harness_ch003_report_after_sp068.json",
            FIXTURE_ROOT / "deepseek_family_harness_decision_after_sp068.json",
        ]:
            with self.subTest(path=path):
                payload = json.loads(path.read_text(encoding="utf-8"))
                blob = json.dumps(payload, ensure_ascii=False)
                self.assertTrue(isinstance(payload, dict))
                self.assertNotIn("provider_response_raw.txt", blob)
                self.assertNotIn("```", blob)
                self.assertNotIn("chapter_text", blob)
                self.assertNotIn("OPENAI_API_KEY", blob)
                self.assertNotIn("DEEPSEEK_API_KEY", blob)

    def test_compact_profile_runtime_reports_record_executed_valid_json_state(self):
        summary = json.loads((FIXTURE_ROOT / "deepseek_ch002_compact_profile_runtime_summary_after_sp064.json").read_text(encoding="utf-8"))
        generic = json.loads((FIXTURE_ROOT / "deepseek_ch002_compact_profile_vs_generic_report_after_sp064.json").read_text(encoding="utf-8"))
        failed = json.loads((FIXTURE_ROOT / "deepseek_ch002_compact_profile_vs_failed_profile_report_after_sp064.json").read_text(encoding="utf-8"))
        baseline = json.loads((FIXTURE_ROOT / "deepseek_ch002_compact_profile_vs_sp056_baseline_report_after_sp064.json").read_text(encoding="utf-8"))
        issues = json.loads((FIXTURE_ROOT / "deepseek_compact_profile_runtime_issue_report_after_sp064.json").read_text(encoding="utf-8"))

        self.assertEqual(summary["real_provider_call_status"], "executed_one_call_compact_profile_valid_json")
        self.assertEqual(summary["provider_calls"], 1)
        self.assertTrue(summary["provider_profile_applied"])
        self.assertTrue(summary["response_parseable_json"])
        self.assertTrue(summary["validation_ok"])
        self.assertEqual(summary["chapter_id"], "ch_002")
        self.assertEqual(generic["overall_assessment"], "compact_profile_restored_json_but_still_thin")
        self.assertEqual(failed["overall_assessment"], "compact_profile_restored_json_but_still_thin")
        self.assertEqual(baseline["overall_assessment"], "compact_profile_improved_but_below_manual")
        self.assertEqual(issues["real_provider_call_status"], "executed_one_call_compact_profile_valid_json")

    def test_prompt_matrix_reports_record_candidate_found_without_private_payloads(self):
        summary = json.loads((FIXTURE_ROOT / "deepseek_ch002_prompt_matrix_summary_after_sp065.json").read_text(encoding="utf-8"))
        variants = json.loads((FIXTURE_ROOT / "deepseek_ch002_prompt_matrix_variant_report_after_sp065.json").read_text(encoding="utf-8"))
        decision = json.loads((FIXTURE_ROOT / "deepseek_ch002_prompt_matrix_decision_after_sp065.json").read_text(encoding="utf-8"))

        self.assertEqual(summary["assessment"], "flash_profile_candidate_found")
        self.assertEqual(summary["provider_calls_executed"], 4)
        self.assertIn("variant_04_section_targets", summary["json_invalid_variants"])
        self.assertEqual(decision["best_variant"]["variant_id"], "variant_03_dense_explicit")
        self.assertEqual(decision["comparison_vs_sp056_manual"]["assessment"], "still_below_manual_density")
        self.assertEqual(len(variants["variants"]), 6)

    def test_strategy_matrix_reports_parse_and_use_valid_decision_enum(self):
        summary = json.loads((FIXTURE_ROOT / "deepseek_strategy_matrix_summary_after_sp066.json").read_text(encoding="utf-8"))
        decision = json.loads((FIXTURE_ROOT / "deepseek_strategy_matrix_decision_after_sp066.json").read_text(encoding="utf-8"))
        valid_enum = {
            "flash_profile_candidate_confirmed",
            "flash_valid_but_requires_retry_policy",
            "flash_not_suitable_for_primary_but_useful_for_draft",
            "pro_candidate_better_if_available",
            "deepseek_strategy_requires_openai_fallback",
            "experiment_blocked",
        }

        self.assertIn(summary["assessment"], valid_enum)
        self.assertIn(decision["assessment"], valid_enum)
        self.assertLessEqual(summary["provider_calls_count"], 16)
        self.assertIn("deepseek-v4-flash", summary["models_attempted"])

    def test_flash_harness_round2_reports_parse_and_use_valid_decision_enum(self):
        summary = json.loads((FIXTURE_ROOT / "deepseek_flash_harness_round2_summary_after_sp067.json").read_text(encoding="utf-8"))
        decision = json.loads((FIXTURE_ROOT / "deepseek_flash_harness_round2_decision_after_sp067.json").read_text(encoding="utf-8"))
        valid_enum = {
            "deepseek_flash_harness_candidate_found",
            "deepseek_flash_harness_needs_more_iteration",
            "deepseek_flash_outputs_valid_but_too_thin",
            "deepseek_flash_unstable_even_with_harness",
            "experiment_blocked",
        }

        self.assertIn(summary["assessment"], valid_enum)
        self.assertIn(decision["assessment"], valid_enum)
        self.assertEqual(summary["provider"], "deepseek")
        self.assertEqual(summary["model"], "deepseek-v4-flash")
        self.assertLessEqual(summary["provider_calls_count"], 12)

    def test_deepseek_family_reports_parse_and_use_valid_decision_enum(self):
        discovery = json.loads((FIXTURE_ROOT / "deepseek_family_model_discovery_after_sp068.json").read_text(encoding="utf-8"))
        summary = json.loads((FIXTURE_ROOT / "deepseek_family_harness_matrix_summary_after_sp068.json").read_text(encoding="utf-8"))
        decision = json.loads((FIXTURE_ROOT / "deepseek_family_harness_decision_after_sp068.json").read_text(encoding="utf-8"))
        valid_enum = {
            "deepseek_family_harness_candidate_found",
            "deepseek_family_harness_needs_more_iteration",
            "deepseek_flash_usable_but_ch002_weak",
            "deepseek_pro_or_reasoner_promising",
            "deepseek_family_experiment_blocked",
        }

        self.assertEqual(discovery["status"], "completed")
        self.assertIn("deepseek-v4-flash", discovery["visible_model_ids"])
        self.assertIn(summary["assessment"], valid_enum)
        self.assertIn(decision["assessment"], valid_enum)
        self.assertLessEqual(summary["provider_calls_count"], 24)

    def test_prompt_experiment_observability_reports_parse(self):
        root = Path("tests/fixtures/textifai/prompt_experiments/expected")
        taxonomy = json.loads((root / "deepseek_prompt_experiment_taxonomy_after_sp070.json").read_text(encoding="utf-8"))
        diff = json.loads((root / "deepseek_variant_diff_report_after_sp070.json").read_text(encoding="utf-8"))
        failure = json.loads((root / "deepseek_failure_mode_taxonomy_after_sp070.json").read_text(encoding="utf-8"))
        decision = json.loads((root / "deepseek_variant_decision_report_after_sp070.json").read_text(encoding="utf-8"))

        self.assertEqual(taxonomy["assessment"], "prompt_experiment_observability_ready_for_chunking_preflight")
        self.assertEqual(diff["assessment"], "prompt_experiment_observability_ready_for_chunking_preflight")
        self.assertEqual(failure["assessment"], "prompt_experiment_observability_ready_for_chunking_preflight")
        self.assertEqual(decision["assessment"], "prompt_experiment_observability_ready_for_chunking_preflight")

    def test_targeted_ingestion_reports_parse_and_use_valid_decision_enum(self):
        summary = json.loads((FIXTURE_ROOT / "deepseek_targeted_ingestion_matrix_summary_after_sp071.json").read_text(encoding="utf-8"))
        variants = json.loads((FIXTURE_ROOT / "deepseek_targeted_ingestion_matrix_variants_after_sp071.json").read_text(encoding="utf-8"))
        ch002 = json.loads((FIXTURE_ROOT / "deepseek_targeted_ingestion_ch002_report_after_sp071.json").read_text(encoding="utf-8"))
        ch003 = json.loads((FIXTURE_ROOT / "deepseek_targeted_ingestion_ch003_report_after_sp071.json").read_text(encoding="utf-8"))
        decision = json.loads((FIXTURE_ROOT / "deepseek_targeted_ingestion_decision_after_sp071.json").read_text(encoding="utf-8"))
        hyp = json.loads((FIXTURE_ROOT / "deepseek_targeted_ingestion_hypothesis_after_sp071.json").read_text(encoding="utf-8"))
        targeted_diff = json.loads((Path("tests/fixtures/textifai/prompt_experiments/expected") / "deepseek_targeted_ingestion_variant_diff_after_sp071.json").read_text(encoding="utf-8"))
        targeted_fail = json.loads((Path("tests/fixtures/textifai/prompt_experiments/expected") / "deepseek_targeted_ingestion_failure_modes_after_sp071.json").read_text(encoding="utf-8"))

        valid_enum = {
            "deepseek_ingestion_harness_improved",
            "deepseek_ingestion_harness_improved_but_still_needs_review",
            "deepseek_ingestion_harness_no_clear_improvement",
            "deepseek_ingestion_experiment_blocked",
        }

        self.assertIn(summary["assessment"], valid_enum)
        self.assertIn(decision["assessment"], valid_enum)
        self.assertIn(decision["product_decision"], valid_enum)
        self.assertEqual(variants["assessment"], summary["assessment"])

    def test_real_deepseek_e2e_reports_parse_and_use_valid_decision_enum(self):
        plan = json.loads((FIXTURE_ROOT / "real_deepseek_e2e_execution_plan_after_sp074.json").read_text(encoding="utf-8"))
        summary = json.loads((FIXTURE_ROOT / "real_deepseek_e2e_summary_after_sp074.json").read_text(encoding="utf-8"))
        chunks = json.loads((FIXTURE_ROOT / "real_deepseek_e2e_chunk_results_after_sp074.json").read_text(encoding="utf-8"))
        reduction = json.loads((FIXTURE_ROOT / "real_deepseek_e2e_reduction_summary_after_sp074.json").read_text(encoding="utf-8"))
        decision = json.loads((FIXTURE_ROOT / "real_deepseek_e2e_decision_after_sp074.json").read_text(encoding="utf-8"))
        valid_enum = {
            "real_deepseek_e2e_dryrun_passed_with_review_warnings",
            "real_deepseek_e2e_dryrun_partial_success",
            "real_deepseek_e2e_dryrun_failed_but_debuggable",
            "real_deepseek_e2e_dryrun_blocked",
        }

        for payload in (plan, summary, chunks, reduction, decision):
            text = json.dumps(payload, ensure_ascii=False)
            self.assertNotIn("sk-", text)
            self.assertNotIn("Authorization: Bearer", text)
            self.assertNotIn("CHUNK_TEXT:", text)
            self.assertNotIn("provider_response_raw", text.split("private_dir")[0])

        self.assertEqual(plan["assessment"], "real_deepseek_e2e_execution_plan_ready")
        self.assertIn(summary["assessment"], valid_enum)
        self.assertIn(decision["assessment"], valid_enum)
        self.assertLessEqual(summary["provider_call_count"], 24)
        self.assertFalse(summary["write_back"])
        self.assertTrue(summary["private_packet_root"].startswith("/tmp/textifai_private_provider_runs/"))
        self.assertTrue(all(row.get("chunk_id") for row in chunks["chunks"]))
        self.assertTrue(
            all(
                row.get("source_span")
                for row in chunks["chunks"]
                if row.get("mode") in {"chapter_partial", "chapter_partial_continuation"}
            )
        )
        self.assertIn("source_ref_preservation", reduction)

    def test_real_deepseek_e2e_script_requires_no_write_back_and_allow_flag(self):
        parser = E2E_MODULE.build_parser()
        args = parser.parse_args(
            [
                "--source-file",
                "/tmp/source.md",
                "--chapter-ids",
                "ch_002",
                "--models",
                "deepseek-v4-flash",
                "--output-root",
                "/tmp/textifai_private_provider_runs/test",
                "--max-provider-requests",
                "24",
                "--max-output-tokens",
                "8192",
                "--response-format-json",
                "--no-write-back",
            ]
        )

        self.assertFalse(args.allow_provider_calls)
        self.assertTrue(args.no_write_back)
        self.assertEqual(args.max_provider_requests, 24)

    def test_output_budget_and_continuation_protocol_reports_parse(self):
        resolver = json.loads((FIXTURE_ROOT / "output_budget_capability_resolver_after_sp075.json").read_text(encoding="utf-8"))
        response_control = json.loads((FIXTURE_ROOT / "response_control_contract_after_sp075.json").read_text(encoding="utf-8"))
        continuation = json.loads((FIXTURE_ROOT / "continuation_repair_contract_after_sp075.json").read_text(encoding="utf-8"))
        source_refs = json.loads((FIXTURE_ROOT / "source_ref_carry_forward_after_sp075.json").read_text(encoding="utf-8"))
        truncation = json.loads((FIXTURE_ROOT / "truncation_detection_after_sp075.json").read_text(encoding="utf-8"))

        for payload in (resolver, response_control, continuation, source_refs, truncation):
            text = json.dumps(payload, ensure_ascii=False)
            self.assertNotIn("sk-", text)
            self.assertNotIn("Authorization: Bearer", text)
            self.assertNotIn("CHUNK_TEXT:", text)

        self.assertEqual(resolver["assessment"], "source_refs_and_output_budget_protocol_ready")
        self.assertEqual(response_control["assessment"], "source_refs_and_output_budget_protocol_ready")
        self.assertEqual(continuation["assessment"], "source_refs_and_output_budget_protocol_ready")
        self.assertEqual(source_refs["assessment"], "source_refs_and_output_budget_protocol_ready")
        self.assertEqual(truncation["assessment"], "source_refs_and_output_budget_protocol_ready")
        self.assertTrue(resolver["flash_resolution"]["effective_max_output_tokens"] > 0)
        self.assertIn("response_control.partial", continuation["trigger_conditions"])

    def test_full_real_deepseek_validation_reports_parse_and_stay_private_safe(self):
        plan = json.loads((FIXTURE_ROOT / "full_deepseek_e2e_execution_plan_after_sp076.json").read_text(encoding="utf-8"))
        summary = json.loads((FIXTURE_ROOT / "full_deepseek_e2e_summary_after_sp076.json").read_text(encoding="utf-8"))
        chunks = json.loads((FIXTURE_ROOT / "full_deepseek_e2e_chunk_results_after_sp076.json").read_text(encoding="utf-8"))
        reduction = json.loads((FIXTURE_ROOT / "full_deepseek_e2e_reduction_summary_after_sp076.json").read_text(encoding="utf-8"))
        budget = json.loads((FIXTURE_ROOT / "full_deepseek_e2e_budget_report_after_sp076.json").read_text(encoding="utf-8"))
        source_refs = json.loads((FIXTURE_ROOT / "full_deepseek_e2e_source_ref_audit_after_sp076.json").read_text(encoding="utf-8"))
        truncation = json.loads((FIXTURE_ROOT / "full_deepseek_e2e_truncation_continuation_audit_after_sp076.json").read_text(encoding="utf-8"))
        decision = json.loads((FIXTURE_ROOT / "full_deepseek_e2e_decision_after_sp076.json").read_text(encoding="utf-8"))

        valid_enum = {
            "real_deepseek_e2e_validation_passed_ready_for_larger_e2e",
            "real_deepseek_e2e_validation_passed_with_review_warnings",
            "real_deepseek_e2e_validation_partial_success_needs_patch",
            "real_deepseek_e2e_validation_failed_but_debuggable",
            "real_deepseek_e2e_validation_blocked",
        }
        continuation_statuses = {
            "not_triggered",
            "executed",
            "executed_replaced_primary",
            "executed_but_not_parseable",
            "skipped_cap_reached",
        }

        for payload in (plan, summary, chunks, reduction, budget, source_refs, truncation, decision):
            text = json.dumps(payload, ensure_ascii=False)
            self.assertNotIn("sk-", text)
            self.assertNotIn("Authorization: Bearer", text)
            self.assertNotIn("CHUNK_TEXT:", text)
            self.assertNotIn("provider_response_raw.txt\n", text)

        self.assertEqual(plan["assessment"], "real_deepseek_e2e_execution_plan_ready")
        self.assertLessEqual(plan["planned_provider_call_count_with_continuation_reserve"], plan["provider_call_cap"])
        self.assertIn(summary["assessment"], valid_enum)
        self.assertIn(decision["assessment"], valid_enum)
        self.assertIn(decision["product_decision"], valid_enum)
        self.assertLessEqual(summary["provider_call_count"], summary["provider_call_cap"])
        self.assertFalse(summary["write_back"])
        self.assertTrue(summary["private_packet_root"].startswith("/tmp/textifai_private_provider_runs/"))
        self.assertIn("deepseek-v4-flash", summary["models"])
        self.assertIn("deepseek-v4-pro", summary["models"])
        self.assertIn("ch_002", summary["chapters"])
        self.assertIn("ch_003", summary["chapters"])
        self.assertTrue(all(row.get("chunk_id") for row in chunks["chunks"]))
        self.assertTrue(
            all(
                row.get("source_span")
                for row in chunks["chunks"]
                if row.get("mode") in {"chapter_partial", "chapter_partial_continuation"}
            )
        )
        self.assertTrue(all("effective_max_output_tokens" in row for row in budget["runs"]))
        self.assertTrue(all(row.get("decision_source") for row in budget["runs"]))
        self.assertIn("item_level_source_ref_coverage_ratio", source_refs)
        self.assertIn("parseable_reduction_runs", source_refs)
        self.assertTrue(all(event.get("continuation_status") in continuation_statuses for event in truncation["events"]))
        self.assertIn("triggered_continuation_count", truncation)
        self.assertIn("source_ref_preservation", reduction)

    def test_pro_compact_reduction_and_patch_reports_parse_and_stay_private_safe(self):
        compact_policy = json.loads((FIXTURE_ROOT / "pro_compact_reduction_policy_after_sp077.json").read_text(encoding="utf-8"))
        patch_contract = json.loads((FIXTURE_ROOT / "patch_based_continuation_contract_after_sp077.json").read_text(encoding="utf-8"))
        finish_strategy = json.loads((FIXTURE_ROOT / "finish_reason_length_strategy_after_sp077.json").read_text(encoding="utf-8"))
        response_policy = json.loads((FIXTURE_ROOT / "response_control_runtime_policy_after_sp077.json").read_text(encoding="utf-8"))
        plan = json.loads((FIXTURE_ROOT / "pro_compact_reduction_recheck_execution_plan_after_sp077.json").read_text(encoding="utf-8"))
        summary = json.loads((FIXTURE_ROOT / "pro_compact_reduction_recheck_summary_after_sp077.json").read_text(encoding="utf-8"))
        truncation = json.loads((FIXTURE_ROOT / "pro_compact_reduction_recheck_truncation_audit_after_sp077.json").read_text(encoding="utf-8"))
        source_refs = json.loads((FIXTURE_ROOT / "pro_compact_reduction_recheck_source_ref_audit_after_sp077.json").read_text(encoding="utf-8"))
        decision = json.loads((FIXTURE_ROOT / "pro_compact_reduction_recheck_decision_after_sp077.json").read_text(encoding="utf-8"))

        valid_enum = {
            "pro_compact_reduction_recovery_ready",
            "pro_compact_reduction_improved_but_needs_review",
            "pro_reduction_truncation_still_blocking",
            "pro_reduction_recovery_blocked",
        }

        for payload in (compact_policy, patch_contract, finish_strategy, response_policy, plan, summary, truncation, source_refs, decision):
            text = json.dumps(payload, ensure_ascii=False)
            self.assertNotIn("sk-", text)
            self.assertNotIn("Authorization: Bearer", text)
            self.assertNotIn("CHUNK_TEXT:", text)

        self.assertIn(summary["assessment"], valid_enum)
        self.assertIn(decision["assessment"], valid_enum)
        self.assertIn(decision["product_decision"], valid_enum)
        self.assertLessEqual(summary["provider_call_count"], 6)
        self.assertTrue(summary["compact_mode_used"])
        self.assertTrue(summary["patch_continuation_mode"])
        self.assertEqual(plan["provider_call_cap"], 6)
        self.assertEqual(plan["models"], ["deepseek-v4-pro"])
        self.assertEqual(plan["chapters"], ["ch_001"])
        self.assertIn("caps", compact_policy)
        self.assertIn("merge_rules", patch_contract)
        self.assertEqual(finish_strategy["primary_strategy"], "retry_same_model_profile_in_compact_reduction_mode")
        self.assertFalse(response_policy["response_control_required_for_success"])
        self.assertTrue(any(event.get("continuation_status") in {"patch_merged", "executed", "not_triggered"} for event in truncation["events"]))
        self.assertIn("item_level_source_ref_coverage_ratio", source_refs)

    def test_larger_deepseek_multichunk_reports_parse_and_stay_private_safe(self):
        plan = json.loads((FIXTURE_ROOT / "larger_deepseek_multichunk_execution_plan_after_sp078.json").read_text(encoding="utf-8"))
        summary = json.loads((FIXTURE_ROOT / "larger_deepseek_multichunk_summary_after_sp078.json").read_text(encoding="utf-8"))
        chunks = json.loads((FIXTURE_ROOT / "larger_deepseek_multichunk_chunk_results_after_sp078.json").read_text(encoding="utf-8"))
        reduction = json.loads((FIXTURE_ROOT / "larger_deepseek_multichunk_reduction_summary_after_sp078.json").read_text(encoding="utf-8"))
        budget_usage = json.loads((FIXTURE_ROOT / "larger_deepseek_multichunk_budget_usage_after_sp078.json").read_text(encoding="utf-8"))
        chunk_audit = json.loads((FIXTURE_ROOT / "larger_deepseek_multichunk_chunk_audit_after_sp078.json").read_text(encoding="utf-8"))
        source_refs = json.loads((FIXTURE_ROOT / "larger_deepseek_multichunk_source_ref_audit_after_sp078.json").read_text(encoding="utf-8"))
        truncation = json.loads((FIXTURE_ROOT / "larger_deepseek_multichunk_truncation_continuation_after_sp078.json").read_text(encoding="utf-8"))
        decision = json.loads((FIXTURE_ROOT / "larger_deepseek_multichunk_decision_after_sp078.json").read_text(encoding="utf-8"))

        valid_enum = {
            "larger_deepseek_e2e_multichunk_passed_ready_for_broader_e2e",
            "larger_deepseek_e2e_multichunk_passed_with_review_warnings",
            "larger_deepseek_e2e_multichunk_partial_success_needs_patch",
            "larger_deepseek_e2e_multichunk_failed_but_debuggable",
            "larger_deepseek_e2e_multichunk_blocked",
        }
        continuation_statuses = {
            "not_triggered",
            "executed",
            "executed_replaced_primary",
            "executed_but_not_parseable",
            "skipped_cap_reached",
            "patch_merged",
        }

        for payload in (plan, summary, chunks, reduction, budget_usage, chunk_audit, source_refs, truncation, decision):
            text = json.dumps(payload, ensure_ascii=False)
            self.assertNotIn("sk-", text)
            self.assertNotIn("Authorization: Bearer", text)
            self.assertNotIn("CHUNK_TEXT:", text)
            self.assertNotIn("provider_response_raw.txt\n", text)

        self.assertIn(summary["assessment"], valid_enum)
        self.assertIn(decision["assessment"], valid_enum)
        self.assertIn(decision["product_decision"], valid_enum)
        self.assertLessEqual(plan["planned_provider_call_count_with_continuation_reserve"], 48)
        self.assertLessEqual(summary["provider_call_count"], 48)
        self.assertTrue(summary["private_packet_root"].startswith("/tmp/textifai_private_provider_runs/"))
        self.assertEqual(plan["natural_vs_forced_multichunk"], "forced_budget_preflight")
        self.assertTrue(chunk_audit["has_multichunk_run"])
        self.assertTrue(any(row["number_of_chunks"] > 1 for row in chunk_audit["runs"]))
        self.assertGreaterEqual(source_refs["item_level_source_ref_coverage_ratio"], 0.0)
        self.assertLessEqual(source_refs["item_level_source_ref_coverage_ratio"], 1.0)
        self.assertTrue(all("effective_max_output_tokens" in row for row in budget_usage["runs"]))
        self.assertTrue(all(event.get("continuation_status") in continuation_statuses for event in truncation["events"]))
        self.assertTrue(all(row.get("chunk_id") for row in chunks["chunks"]))
        self.assertTrue(all(row.get("source_span") for row in chunks["chunks"]))
        self.assertTrue(all(row.get("parseable_json") for row in reduction["reductions"]))

    def test_broader_deepseek_natural_chunking_reports_parse_and_separate_general_vs_provider_specific(self):
        natural_plan = json.loads((FIXTURE_ROOT / "natural_chunking_calibration_plan_after_sp079.json").read_text(encoding="utf-8"))
        plan = json.loads((FIXTURE_ROOT / "broader_deepseek_natural_chunking_execution_plan_after_sp079.json").read_text(encoding="utf-8"))
        summary = json.loads((FIXTURE_ROOT / "broader_deepseek_natural_chunking_summary_after_sp079.json").read_text(encoding="utf-8"))
        chunks = json.loads((FIXTURE_ROOT / "broader_deepseek_natural_chunking_chunk_results_after_sp079.json").read_text(encoding="utf-8"))
        reduction = json.loads((FIXTURE_ROOT / "broader_deepseek_natural_chunking_reduction_summary_after_sp079.json").read_text(encoding="utf-8"))
        budget_usage = json.loads((FIXTURE_ROOT / "broader_deepseek_natural_chunking_budget_usage_after_sp079.json").read_text(encoding="utf-8"))
        chunk_audit = json.loads((FIXTURE_ROOT / "broader_deepseek_natural_chunking_chunk_audit_after_sp079.json").read_text(encoding="utf-8"))
        source_refs = json.loads((FIXTURE_ROOT / "broader_deepseek_natural_chunking_source_ref_audit_after_sp079.json").read_text(encoding="utf-8"))
        truncation = json.loads((FIXTURE_ROOT / "broader_deepseek_natural_chunking_truncation_audit_after_sp079.json").read_text(encoding="utf-8"))
        decision = json.loads((FIXTURE_ROOT / "broader_deepseek_natural_chunking_decision_after_sp079.json").read_text(encoding="utf-8"))
        general = json.loads((FIXTURE_ROOT / "broader_deepseek_general_pipeline_learnings_after_sp079.json").read_text(encoding="utf-8"))
        provider_specific = json.loads((FIXTURE_ROOT / "broader_deepseek_provider_specific_learnings_after_sp079.json").read_text(encoding="utf-8"))

        valid_enum = {
            "natural_chunking_calibrated_ready_for_broader_e2e",
            "natural_chunking_good_but_needs_threshold_tuning",
            "natural_chunking_under_splits_needs_patch",
            "natural_chunking_e2e_failed_but_debuggable",
            "natural_chunking_calibration_blocked",
        }
        continuation_statuses = {
            "not_triggered",
            "executed",
            "executed_replaced_primary",
            "executed_but_not_parseable",
            "skipped_cap_reached",
            "patch_merged",
        }

        for payload in (natural_plan, plan, summary, chunks, reduction, budget_usage, chunk_audit, source_refs, truncation, decision, general, provider_specific):
            text = json.dumps(payload, ensure_ascii=False)
            self.assertNotIn("sk-", text)
            self.assertNotIn("Authorization: Bearer", text)
            self.assertNotIn("CHUNK_TEXT:", text)
            self.assertNotIn("provider_response_raw.txt\n", text)

        self.assertIn(natural_plan["assessment"], valid_enum)
        self.assertIn(summary["assessment"], valid_enum)
        self.assertIn(decision["assessment"], valid_enum)
        self.assertIn(decision["product_decision"], valid_enum)
        self.assertEqual(plan["assessment"], "natural_chunking_execution_plan_ready")
        self.assertLessEqual(plan["planned_provider_call_count_with_continuation_reserve"], 64)
        self.assertLessEqual(summary["provider_call_count"], 64)
        self.assertTrue(summary["private_packet_root"].startswith("/tmp/textifai_private_provider_runs/"))
        self.assertEqual(plan["natural_vs_forced_multichunk"], "natural")
        self.assertEqual(natural_plan["summary"]["multi_chunk_rows"], 0)
        self.assertIn("threshold_sensitivity", natural_plan)
        self.assertTrue(natural_plan["threshold_sensitivity"]["rows_have_threshold_fields"])
        self.assertTrue(all("effective_max_output_tokens" in row for row in budget_usage["runs"]))
        self.assertTrue(all(event.get("continuation_status") in continuation_statuses for event in truncation["events"]))
        self.assertGreaterEqual(source_refs["item_level_source_ref_coverage_ratio"], 0.0)
        self.assertLessEqual(source_refs["item_level_source_ref_coverage_ratio"], 1.0)
        self.assertTrue(all(row.get("chunk_id") for row in chunks["chunks"]))
        self.assertTrue(
            all(
                row.get("source_span")
                for row in chunks["chunks"]
                if row.get("mode") in {"chapter_partial", "chapter_partial_continuation"}
            )
        )
        self.assertEqual(general["assessment"], summary["assessment"])
        self.assertEqual(provider_specific["assessment"], summary["assessment"])
        self.assertIn("what_should_be_abstracted", general)
        self.assertIn("what_should_stay_provider_specific", provider_specific)
        self.assertTrue(any("budget resolver" in item for item in general["what_should_be_abstracted"]))
        self.assertTrue(any("DeepSeek concrete model ids" == item for item in provider_specific["what_should_stay_provider_specific"]))
        self.assertFalse(any("DeepSeek concrete model ids" == item for item in general["what_should_be_abstracted"]))
        self.assertIn("provider_adapter_implications", general)
        self.assertIn("provider_adapter_implications", provider_specific)

    def test_patch_merge_preserves_source_refs_provider_free(self):
        chunk = E2E_MODULE.StructuredSourceChunk(
            source_id="src",
            chunk_id="src_ch_001_chunk_001",
            chapter_id="ch_001",
            section_id="ch_001",
            sequence_index=1,
            heading_path=["Chapter 1"],
            text="text",
            char_start=10,
            char_end=110,
            char_count=100,
            estimated_tokens=20,
            chunk_kind="chapter",
            split_reason="synthetic",
            predecessor_chunk_id=None,
            successor_chunk_id=None,
            parent_chunk_id="src_ch_001",
            source_span={"char_start": 10, "char_end": 110},
            budget_profile_id="test",
            provider_profile_id="deepseek-v4-pro:bootstrap_chapter_extraction:balanced_kb_v1",
        )
        run = {
            "chapter": {"chapter_id": "ch_001"},
            "chunks": [chunk],
            "effective_output_budget": SimpleNamespace(effective_max_output_tokens=8192),
        }
        call_result = {
            "mode": "chapter_reduction_compact",
            "chunk_id": "reduction",
            "parseable_json": False,
            "finish_reason": "length",
            "usage": {"completion_tokens": 8192, "completion_tokens_details": {"reasoning_tokens": 5000}},
            "effective_max_output_tokens": 8192,
            "response_control": {"completion_status": "unknown"},
            "failure_mode": "finish_reason_length",
        }
        patch_result = {
            "parsed": {
                "continuation_patch": {
                    "objects": [{"canonical_name": "Bastón", "surface": "杖", "source_refs": []}],
                    "events": [{"canonical_name": "Prueba", "event_importance": "major", "source_refs": []}],
                }
            },
            "finish_reason": "stop",
            "usage": {"completion_tokens": 300},
        }
        partial_payloads = [
            {
                "partial_signals": {
                    "objects": [{"canonical": "Bastón", "surface": "杖"}],
                    "events": [{"canonical": "Prueba", "event_importance": "major"}],
                }
            }
        ]

        merged = E2E_MODULE._merge_patch_into_reduction(
            call_result=call_result,
            patch_result=patch_result,
            run=run,
            partial_payloads=partial_payloads,
        )
        self.assertIsNotNone(merged)
        chapter = merged["parsed"]["chapters"][0]
        self.assertTrue(chapter["objects"])
        self.assertTrue(chapter["events"])
        self.assertTrue(chapter["objects"][0].get("source_refs"))
        self.assertTrue(chapter["events"][0].get("source_refs"))

    def test_profiled_runtime_reports_record_safe_not_executed_state(self):
        summary = json.loads((FIXTURE_ROOT / "deepseek_ch002_profiled_runtime_summary_after_sp061.json").read_text(encoding="utf-8"))
        generic = json.loads((FIXTURE_ROOT / "deepseek_ch002_profiled_vs_generic_report.json").read_text(encoding="utf-8"))
        baseline = json.loads((FIXTURE_ROOT / "deepseek_ch002_profiled_vs_sp056_baseline_report.json").read_text(encoding="utf-8"))
        issues = json.loads((FIXTURE_ROOT / "deepseek_provider_profile_runtime_issue_report.json").read_text(encoding="utf-8"))

        self.assertEqual(summary["real_provider_call_status"], "not_executed_missing_key_and_prompt")
        self.assertEqual(summary["provider_calls"], 0)
        self.assertFalse(summary["output_committed"])
        self.assertEqual(generic["overall_assessment"], "profile_call_failed")
        self.assertEqual(baseline["overall_assessment"], "profiled_deepseek_invalid")
        self.assertEqual(issues["provider_profile_overlay_runtime_effect"], "failed")

    def test_profiled_runtime_reports_record_executed_profiled_json_invalid_state(self):
        summary = json.loads((FIXTURE_ROOT / "deepseek_ch002_profiled_runtime_summary_after_sp062.json").read_text(encoding="utf-8"))
        generic = json.loads((FIXTURE_ROOT / "deepseek_ch002_profiled_vs_generic_report_after_sp062.json").read_text(encoding="utf-8"))
        baseline = json.loads((FIXTURE_ROOT / "deepseek_ch002_profiled_vs_sp056_baseline_report_after_sp062.json").read_text(encoding="utf-8"))
        issues = json.loads((FIXTURE_ROOT / "deepseek_provider_profile_runtime_issue_report_after_sp062.json").read_text(encoding="utf-8"))

        self.assertEqual(summary["real_provider_call_status"], "executed_one_call_profiled_json_invalid")
        self.assertEqual(summary["provider_calls"], 1)
        self.assertTrue(summary["environment_check"]["key_present"])
        self.assertTrue(summary["provider_profile_applied"])
        self.assertFalse(summary["response_parseable_json"])
        self.assertEqual(generic["overall_assessment"], "profile_regressed")
        self.assertEqual(baseline["overall_assessment"], "profiled_deepseek_invalid")
        self.assertEqual(issues["real_provider_call_status"], "executed_one_call_profiled_json_invalid")


def _sample_capture_markdown() -> str:
    return (
        "# TextifAI Bootstrap Prompt Capture\n\n"
        "## System\n\n"
        "```text\nReturn only valid JSON for one chapter extraction.\n```\n\n"
        "## Messages\n\n"
        "### Message 1\n"
        "- role: `user`\n\n"
        "```text\n{\"chapter_id\":\"ch_002\",\"content\":\"test\"}\n```\n"
    )


def _valid_payload() -> dict:
    return {
        "work": {"title": "王者の杖", "language": "ja"},
        "chapters": [
            {
                "chapter_id": "ch_002",
                "objects": [{"surface": "触媒"}],
                "events": [{"event_importance": "major", "summary": "x"}],
                "relations": [
                    {
                        "relation_category": "magic_or_system",
                        "relation_label": "linked",
                        "relation_summary": "x",
                    }
                ],
            }
        ],
    }


if __name__ == "__main__":
    unittest.main()
