from __future__ import annotations

import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

from providers.text_provider import TextGenerationResponse

MODULE_PATH = Path("scripts/dev/real_provider_dryrun.py").resolve()
SPEC = importlib.util.spec_from_file_location("real_provider_dryrun", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


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
