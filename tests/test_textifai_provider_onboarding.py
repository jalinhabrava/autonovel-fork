import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from textifai.obsidian.cli import run_cli
from textifai.provider_onboarding import (
    ProviderConfiguration,
    ProviderReadiness,
    configure_provider,
    evaluate_provider_readiness,
)


class TextifAIProviderOnboardingTests(unittest.TestCase):
    def test_review_queue_cli_filters_json_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp)
            system_root = base_dir / "99_System"
            system_root.mkdir()
            (system_root / "review_queue.json").write_text(
                json.dumps(
                    {
                        "schema_version": "textifai.review_queue.v1",
                        "status": "ready_for_author_review",
                        "item_count": 2,
                        "counts_by_type": {"review_entity": 1, "unresolved_relationship_target": 1},
                        "counts_by_severity": {"medium": 1, "low": 1},
                        "items": [
                            {
                                "review_item_id": "rq_review",
                                "review_type": "review_entity",
                                "severity": "low",
                                "suggested_action": "merge_into_primary_or_keep_review",
                                "source_entity": "Consejo",
                                "target_text": "Consejo",
                                "candidate_entities": [],
                                "evidence": [],
                            },
                            {
                                "review_item_id": "rq_target",
                                "review_type": "unresolved_relationship_target",
                                "severity": "medium",
                                "suggested_action": "resolve_target_or_keep_unmaterialized",
                                "source_entity": "Sera",
                                "target_text": "Consejo",
                                "candidate_entities": [{"canonical_name": "Consejo", "entity_kind": "faction"}],
                                "evidence": [{"kind": "relationship_fact", "text": "El Consejo vigila a Sera."}],
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with patch("builtins.print") as print_mock:
                code = run_cli(
                    argv=[
                        "review-queue",
                        "--system-root",
                        str(system_root),
                        "--type",
                        "unresolved_relationship_target",
                        "--json",
                    ],
                    repo_root=base_dir,
                )

            self.assertEqual(code, 0)
            payload = json.loads(print_mock.call_args[0][0])
            self.assertEqual(payload["item_count"], 1)
            self.assertEqual(payload["items"][0]["review_item_id"], "rq_target")
            self.assertEqual(payload["counts_by_type"], {"unresolved_relationship_target": 1})

    def test_review_queue_cli_prints_human_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp)
            system_root = base_dir / "99_System"
            system_root.mkdir()
            (system_root / "review_queue.json").write_text(
                json.dumps(
                    {
                        "schema_version": "textifai.review_queue.v1",
                        "status": "ready_for_author_review",
                        "items": [
                            {
                                "review_item_id": "rq_target",
                                "review_type": "unresolved_relationship_target",
                                "severity": "medium",
                                "suggested_action": "resolve_target_or_keep_unmaterialized",
                                "source_entity": "Sera",
                                "target_text": "Consejo",
                                "candidate_entities": [{"canonical_name": "Consejo", "entity_kind": "faction"}],
                                "evidence": [{"kind": "relationship_fact", "text": "El Consejo vigila a Sera."}],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with patch("builtins.print") as print_mock:
                code = run_cli(argv=["review-queue", "--system-root", str(system_root)], repo_root=base_dir)

            self.assertEqual(code, 0)
            output = "\n".join(str(call.args[0]) for call in print_mock.call_args_list)
            self.assertIn("Review queue: ready_for_author_review (1 items)", output)
            self.assertIn("rq_target", output)
            self.assertIn("candidates: Consejo (faction)", output)

    def test_configure_provider_skip_disables_author_flows(self):
        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp)

            readiness = configure_provider(
                base_dir=base_dir,
                configuration=ProviderConfiguration(provider_choice="skip"),
                test_connectivity=False,
            )

            env_text = (base_dir / ".env").read_text(encoding="utf-8")
            self.assertIn("AUTONOVEL_TEXT_PROVIDER=", env_text)
            self.assertFalse(readiness.provider_configured)
            self.assertFalse(readiness.author_flows_available)
            self.assertEqual(readiness.configuration_error, "provider_not_configured")

    def test_evaluate_provider_readiness_reports_reachable_openai_compatible_provider(self):
        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp)
            (base_dir / ".env").write_text(
                "\n".join(
                    [
                        "AUTONOVEL_TEXT_PROVIDER=openai_compatible",
                        "AUTONOVEL_OPENAI_COMPATIBLE_API_BASE_URL=http://localhost:1234/v1",
                        "AUTONOVEL_OPENAI_COMPATIBLE_API_KEY=test-key",
                        "AUTONOVEL_WRITER_MODEL=test-model",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            class _FakeProvider:
                def generate(self, request):
                    return type("Response", (), {"text": "OK", "model": "test-model"})()

            with (
                patch("textifai.provider_onboarding.resolve_text_request") as resolve_mock,
                patch("textifai.provider_onboarding.get_text_provider") as provider_mock,
            ):
                resolve_mock.return_value = type("Resolved", (), {"model": "test-model"})()
                provider_mock.return_value = _FakeProvider()

                readiness = evaluate_provider_readiness(base_dir)

            self.assertTrue(readiness.provider_configured)
            self.assertTrue(readiness.provider_reachable)
            self.assertTrue(readiness.author_flows_available)
            self.assertEqual(readiness.provider_mode, "local_openai_compatible")
            self.assertEqual(readiness.provider_model, "test-model")

    def test_configure_provider_supports_anthropic_configuration(self):
        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp)

            readiness = configure_provider(
                base_dir=base_dir,
                configuration=ProviderConfiguration(
                    provider_choice="anthropic",
                    provider_name="anthropic",
                    api_base="https://api.anthropic.com",
                    api_key="test-key",
                    model="claude-sonnet-4-6",
                ),
                test_connectivity=False,
            )

            env_text = (base_dir / ".env").read_text(encoding="utf-8")
            self.assertIn("AUTONOVEL_TEXT_PROVIDER=anthropic", env_text)
            self.assertIn("AUTONOVEL_WRITER_MODEL=claude-sonnet-4-6", env_text)
            self.assertIn("ANTHROPIC_API_KEY=test-key", env_text)
            self.assertTrue(readiness.provider_configured)
            self.assertEqual(readiness.provider_mode, "remote_anthropic")

    def test_provider_cli_reports_json_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp)
            fake_readiness = ProviderReadiness(
                provider_name="openai_compatible",
                provider_mode="local_openai_compatible",
                provider_model="test-model",
                provider_configured=True,
                provider_reachable=True,
                author_flows_available=True,
                available_for_author_response=True,
                configuration_error=None,
                connectivity_error=None,
                api_base="http://localhost:1234/v1",
            )
            with patch("textifai.obsidian.cli.evaluate_provider_readiness") as readiness_mock, patch(
                "builtins.print"
            ) as print_mock:
                readiness_mock.return_value = fake_readiness
                code = run_cli(argv=["provider", "--skip-connectivity-test", "--json"], repo_root=base_dir)

            self.assertEqual(code, 0)
            printed = print_mock.call_args[0][0]
            payload = json.loads(printed)
            self.assertEqual(payload["provider_mode"], "local_openai_compatible")
            self.assertTrue(payload["author_flows_available"])

    def test_provider_cli_accepts_json_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp)
            fake_readiness = ProviderReadiness(
                provider_name="openai",
                provider_mode="remote_openai",
                provider_model="gpt-5.4",
                provider_configured=True,
                provider_reachable=True,
                author_flows_available=True,
                available_for_author_response=True,
                configuration_error=None,
                connectivity_error=None,
                api_base="https://api.openai.com/v1",
            )
            with patch("textifai.obsidian.cli.evaluate_provider_readiness") as readiness_mock, patch(
                "builtins.print"
            ) as print_mock:
                readiness_mock.return_value = fake_readiness
                code = run_cli(argv=["provider", "--json"], repo_root=base_dir)

            self.assertEqual(code, 0)
            printed = print_mock.call_args[0][0]
            payload = json.loads(printed)
            self.assertEqual(payload["provider_name"], "openai")
            self.assertEqual(payload["provider_mode"], "remote_openai")


if __name__ == "__main__":
    unittest.main()
