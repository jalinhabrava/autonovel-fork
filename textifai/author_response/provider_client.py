from __future__ import annotations

import json
import os

from providers.text_provider import (
    TextGenerationRequest,
    TextMessage,
    get_text_provider,
    get_text_provider_config_error,
)
from textifai.author_response.contracts import AnchoredAuthorPrompt


DEFAULT_AUTHOR_RESPONSE_MODEL_ENV = "TEXTIFAI_AUTHOR_RESPONSE_MODEL"
DEFAULT_AUTHOR_RESPONSE_TASK = "author_response"


class ConfiguredAuthorResponseClient:
    def __init__(
        self,
        *,
        task_name: str = DEFAULT_AUTHOR_RESPONSE_TASK,
        provider_name: str | None = None,
        model: str | None = None,
    ) -> None:
        self.task_name = task_name
        self.provider_name = provider_name
        self.model = model or os.environ.get(DEFAULT_AUTHOR_RESPONSE_MODEL_ENV, "").strip() or None

    def resolve_provider_name(self, *, prompt: AnchoredAuthorPrompt) -> str:
        configured = (
            self.provider_name
            or str(prompt.dynamic_context_payload.get("provider_name") or "").strip()
            or os.environ.get("AUTONOVEL_TEXT_PROVIDER", "").strip()
            or "openai"
        )
        return configured

    def is_available(self, *, prompt: AnchoredAuthorPrompt) -> bool:
        provider_name = self.resolve_provider_name(prompt=prompt)
        return get_text_provider_config_error(self.task_name, provider_name) is None

    def generate(self, *, prompt: AnchoredAuthorPrompt) -> tuple[str, str, str]:
        provider_name = self.resolve_provider_name(prompt=prompt)
        provider = get_text_provider(self.task_name, provider_name)
        user_payload = prompt.llm_rendered_prompt_payload.get("user_payload", prompt.dynamic_context_payload)
        response = provider.generate(
            TextGenerationRequest(
                task=self.task_name,
                provider_name=provider_name,
                model=self.model,
                system=prompt.system_prompt,
                messages=[
                    TextMessage(
                        role="user",
                        content=_render_user_message(prompt.llm_rendered_prompt_payload, user_payload),
                    )
                ],
                max_tokens=700,
                temperature=0.3,
                timeout_seconds=60,
                retries=1,
            )
        )
        return response.text.strip(), response.model, provider_name


class OpenAIAuthorResponseClient(ConfiguredAuthorResponseClient):
    def __init__(self, *, model: str | None = None) -> None:
        super().__init__(provider_name="openai", model=model)


def _render_user_message(rendered_prompt_payload: dict, user_payload: dict) -> str:
    return (
        "Render a concise, useful author-facing answer using the following semantic prompt payload.\n\n"
        f"Dynamic context:\n{json.dumps(user_payload, ensure_ascii=False, indent=2, sort_keys=True)}"
    )
