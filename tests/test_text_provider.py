import sys
import types
import unittest
from unittest.mock import patch

from providers import text_provider
from providers.text_provider import (
    LMStudioTextProvider,
    OllamaTextProvider,
    OpenAICompatibleTextProvider,
    OpenAITextProvider,
    AnthropicCompatibleTextProvider,
    AnthropicTextProvider,
    TextGenerationRequest,
    TextMessage,
    get_text_provider,
    get_text_provider_config_error,
    get_text_provider_name,
    resolve_text_request,
)


class DummyResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def make_fake_httpx(post):
    class HTTPError(Exception):
        pass

    class TimeoutException(HTTPError):
        pass

    class ReadTimeout(TimeoutException):
        pass

    return types.SimpleNamespace(
        post=post,
        HTTPError=HTTPError,
        TimeoutException=TimeoutException,
        ReadTimeout=ReadTimeout,
    )


class TextProviderTests(unittest.TestCase):
    def setUp(self):
        text_provider.load_inference_config.cache_clear()

    def tearDown(self):
        text_provider.load_inference_config.cache_clear()

    def test_resolve_request_uses_task_config_and_env_model(self):
        with patch.dict(
            "os.environ",
            {
                "AUTONOVEL_WRITER_MODEL": "writer-from-env",
            },
            clear=True,
        ):
            request = TextGenerationRequest(
                task="draft_chapter",
                messages=[TextMessage(role="user", content="hello")],
            )
            resolved = resolve_text_request(request)

        self.assertEqual(resolved.provider_name, "anthropic")
        self.assertEqual(resolved.model, "writer-from-env")
        self.assertEqual(resolved.temperature, 0.8)
        self.assertEqual(resolved.max_tokens, 16000)
        self.assertEqual(
            resolved.extra_headers.get("anthropic-beta"),
            "context-1m-2025-08-07",
        )

    def test_provider_name_can_come_from_task_config(self):
        fake_config = {
            "defaults": {"provider": "anthropic"},
            "roles": {"writer": {"provider": "anthropic", "model": "x"}},
            "tasks": {"draft_chapter": {"role": "writer", "provider": "ollama"}},
        }
        with patch("providers.text_provider.load_inference_config", return_value=fake_config):
            with patch.dict("os.environ", {"AUTONOVEL_TEXT_PROVIDER": ""}, clear=False):
                provider_name = get_text_provider_name("draft_chapter")
        self.assertEqual(provider_name, "ollama")

    def test_anthropic_provider_retries_and_normalizes_output(self):
        calls = {"count": 0}

        fake_httpx = None

        def fake_post(*args, **kwargs):
            calls["count"] += 1
            if calls["count"] == 1:
                raise fake_httpx.ReadTimeout("timeout")
            return DummyResponse({"content": [{"type": "text", "text": "hello world"}]})

        fake_httpx = make_fake_httpx(fake_post)

        with patch.dict(
            "os.environ",
            {
                "AUTONOVEL_TEXT_PROVIDER": "anthropic",
                "ANTHROPIC_API_KEY": "test-key",
            },
            clear=False,
        ):
            with patch.dict(sys.modules, {"httpx": fake_httpx}):
                provider = get_text_provider("gen_world")
                response = provider.generate(
                    TextGenerationRequest(
                        task="gen_world",
                        messages=[TextMessage(role="user", content="ping")],
                    )
                )

        self.assertEqual(response.text, "hello world")
        self.assertEqual(response.provider_name, "anthropic")
        self.assertEqual(calls["count"], 2)

    def test_openai_compatible_provider_normalizes_output(self):
        with patch.dict(
            "os.environ",
            {
                "AUTONOVEL_TEXT_PROVIDER": "openai",
                "OPENAI_API_KEY": "test-key",
            },
            clear=False,
        ):
            fake_httpx = make_fake_httpx(
                lambda *args, **kwargs: DummyResponse(
                    {"choices": [{"message": {"content": "normalized text"}}]}
                )
            )
            with patch.dict(sys.modules, {"httpx": fake_httpx}):
                provider = get_text_provider("review_full")
                response = provider.generate(
                    TextGenerationRequest(
                        task="review_full",
                        messages=[TextMessage(role="user", content="ping")],
                    )
                )

        self.assertEqual(response.text, "normalized text")
        self.assertEqual(response.provider_name, "openai")

    def test_openai_gpt_five_models_use_max_completion_tokens(self):
        captured = {}

        def fake_post(*args, **kwargs):
            captured["payload"] = kwargs["json"]
            return DummyResponse({"choices": [{"message": {"content": "normalized text"}}]})

        with patch.dict(
            "os.environ",
            {
                "AUTONOVEL_TEXT_PROVIDER": "openai",
                "OPENAI_API_KEY": "test-key",
            },
            clear=False,
        ):
            fake_httpx = make_fake_httpx(fake_post)
            with patch.dict(sys.modules, {"httpx": fake_httpx}):
                provider = get_text_provider("review_full")
                response = provider.generate(
                    TextGenerationRequest(
                        task="review_full",
                        model="gpt-5.4",
                        messages=[TextMessage(role="user", content="ping")],
                    )
                )

        self.assertEqual(response.text, "normalized text")
        self.assertIn("max_completion_tokens", captured["payload"])
        self.assertNotIn("max_tokens", captured["payload"])

    def test_openai_compatible_gpt_five_style_model_keeps_max_tokens(self):
        captured = {}

        def fake_post(*args, **kwargs):
            captured["payload"] = kwargs["json"]
            return DummyResponse({"choices": [{"message": {"content": "normalized text"}}]})

        with patch.dict(
            "os.environ",
            {
                "AUTONOVEL_TEXT_PROVIDER": "openai_compatible",
                "AUTONOVEL_OPENAI_COMPATIBLE_API_BASE_URL": "http://localhost:1234/v1",
                "AUTONOVEL_OPENAI_COMPATIBLE_API_KEY": "test-key",
            },
            clear=False,
        ):
            fake_httpx = make_fake_httpx(fake_post)
            with patch.dict(sys.modules, {"httpx": fake_httpx}):
                provider = get_text_provider("review_full")
                response = provider.generate(
                    TextGenerationRequest(
                        task="review_full",
                        model="gpt-5.4",
                        messages=[TextMessage(role="user", content="ping")],
                    )
                )

        self.assertEqual(response.text, "normalized text")
        self.assertIn("max_tokens", captured["payload"])
        self.assertNotIn("max_completion_tokens", captured["payload"])

    def test_deepseek_provider_uses_openai_compatible_payload_and_json_response_format(self):
        captured = {}

        def fake_post(*args, **kwargs):
            captured["url"] = args[0]
            captured["headers"] = kwargs["headers"]
            captured["payload"] = kwargs["json"]
            captured["timeout"] = kwargs["timeout"]
            return DummyResponse({"choices": [{"message": {"content": "{\"ok\": true}"}}]})

        with patch.dict(
            "os.environ",
            {
                "AUTONOVEL_TEXT_PROVIDER": "deepseek",
                "AUTONOVEL_BOOTSTRAP_MODEL": "deepseek-v4-flash",
                "DEEPSEEK_API_KEY": "test-key",
                "AUTONOVEL_DEEPSEEK_API_BASE_URL": "https://api.deepseek.com",
            },
            clear=False,
        ):
            fake_httpx = make_fake_httpx(fake_post)
            with patch.dict(sys.modules, {"httpx": fake_httpx}):
                provider = get_text_provider("bootstrap_chapter_extraction")
                response = provider.generate(
                    TextGenerationRequest(
                        task="bootstrap_chapter_extraction",
                        messages=[TextMessage(role="user", content="Return JSON")],
                        response_format={"type": "json_object"},
                    )
                )

        self.assertIsInstance(provider, OpenAICompatibleTextProvider)
        self.assertEqual(provider.provider_name, "deepseek")
        self.assertEqual(provider.api_base, "https://api.deepseek.com")
        self.assertEqual(response.text, "{\"ok\": true}")
        self.assertEqual(response.provider_name, "deepseek")
        self.assertEqual(response.model, "deepseek-v4-flash")
        self.assertEqual(captured["url"], "https://api.deepseek.com/chat/completions")
        self.assertEqual(captured["headers"]["Authorization"], "Bearer test-key")
        self.assertEqual(captured["payload"]["model"], "deepseek-v4-flash")
        self.assertEqual(captured["payload"]["messages"], [{"role": "user", "content": "Return JSON"}])
        self.assertEqual(captured["payload"]["response_format"], {"type": "json_object"})
        self.assertIn("max_tokens", captured["payload"])

    def test_deepseek_missing_api_key_reports_config_error_without_network(self):
        with patch.dict(
            "os.environ",
            {
                "AUTONOVEL_TEXT_PROVIDER": "deepseek",
                "DEEPSEEK_API_KEY": "",
            },
            clear=False,
        ):
            self.assertEqual(
                get_text_provider_config_error("bootstrap_chapter_extraction"),
                "DEEPSEEK_API_KEY not set in .env",
            )

    def test_deepseek_provider_name_can_come_from_bootstrap_provider_env(self):
        with patch.dict(
            "os.environ",
            {
                "AUTONOVEL_TEXT_PROVIDER": "",
                "AUTONOVEL_BOOTSTRAP_PROVIDER": "deepseek",
                "AUTONOVEL_BOOTSTRAP_MODEL": "deepseek-v4-pro",
                "DEEPSEEK_API_KEY": "test-key",
            },
            clear=False,
        ):
            resolved = resolve_text_request(
                TextGenerationRequest(
                    task="bootstrap_chapter_extraction",
                    messages=[TextMessage(role="user", content="hello")],
                )
            )

        self.assertEqual(resolved.provider_name, "deepseek")
        self.assertEqual(resolved.model, "deepseek-v4-pro")

    def test_anthropic_payload_keeps_system_and_max_tokens(self):
        captured = {}

        def fake_post(*args, **kwargs):
            captured["headers"] = kwargs["headers"]
            captured["payload"] = kwargs["json"]
            return DummyResponse({"content": [{"type": "text", "text": "anthropic text"}]})

        with patch.dict(
            "os.environ",
            {
                "AUTONOVEL_TEXT_PROVIDER": "anthropic",
                "ANTHROPIC_API_KEY": "test-key",
            },
            clear=False,
        ):
            fake_httpx = make_fake_httpx(fake_post)
            with patch.dict(sys.modules, {"httpx": fake_httpx}):
                provider = get_text_provider("gen_world")
                response = provider.generate(
                    TextGenerationRequest(
                        task="gen_world",
                        system="System prompt",
                        messages=[TextMessage(role="user", content="ping")],
                    )
                )

        self.assertEqual(response.text, "anthropic text")
        self.assertEqual(captured["payload"]["system"], "System prompt")
        self.assertIn("max_tokens", captured["payload"])
        self.assertEqual(captured["headers"]["x-api-key"], "test-key")

    def test_smoke_factory_supports_all_registered_provider_aliases(self):
        cases = [
            ("anthropic", AnthropicTextProvider),
            ("openai", OpenAITextProvider),
            ("deepseek", OpenAICompatibleTextProvider),
            ("lmstudio", LMStudioTextProvider),
            ("ollama", OllamaTextProvider),
            ("openai_compatible", OpenAICompatibleTextProvider),
            ("anthropic_compatible", AnthropicCompatibleTextProvider),
        ]
        env = {
            "ANTHROPIC_API_KEY": "x",
            "OPENAI_API_KEY": "x",
            "DEEPSEEK_API_KEY": "x",
            "AUTONOVEL_ANTHROPIC_COMPATIBLE_API_BASE_URL": "https://example.test",
            "AUTONOVEL_OPENAI_COMPATIBLE_API_BASE_URL": "https://example.test/v1",
        }
        for provider_name, expected_type in cases:
            with self.subTest(provider_name=provider_name):
                with patch.dict(
                    "os.environ",
                    {
                        **env,
                        "AUTONOVEL_TEXT_PROVIDER": provider_name,
                    },
                    clear=False,
                ):
                    provider = get_text_provider("gen_world")
                self.assertIsInstance(provider, expected_type)

    def test_config_error_is_provider_specific(self):
        with patch.dict("os.environ", {"AUTONOVEL_TEXT_PROVIDER": "ollama"}, clear=False):
            self.assertIsNone(get_text_provider_config_error("gen_world"))

        with patch.dict(
            "os.environ",
            {"AUTONOVEL_TEXT_PROVIDER": "openai", "OPENAI_API_KEY": ""},
            clear=False,
        ):
            self.assertEqual(
                get_text_provider_config_error("review_full"),
                "OPENAI_API_KEY not set in .env",
            )


if __name__ == "__main__":
    unittest.main()
