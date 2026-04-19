from __future__ import annotations

import json
import os

from providers.text_provider import TextGenerationRequest, TextMessage, get_text_provider
from textifai.author_response.contracts import AnchoredAuthorPrompt


DEFAULT_OPENAI_AUTHOR_RESPONSE_MODEL = "gpt-4.1-mini"


class OpenAIAuthorResponseClient:
    def __init__(self, *, model: str | None = None) -> None:
        self.model = model or os.environ.get("TEXTIFAI_AUTHOR_RESPONSE_OPENAI_MODEL", DEFAULT_OPENAI_AUTHOR_RESPONSE_MODEL)

    def is_available(self) -> bool:
        return bool(os.environ.get("OPENAI_API_KEY", "").strip())

    def generate(self, *, prompt: AnchoredAuthorPrompt) -> tuple[str, str]:
        provider = get_text_provider(provider_name="openai")
        user_payload = prompt.llm_rendered_prompt_payload.get("user_payload", prompt.dynamic_context_payload)
        response = provider.generate(
            TextGenerationRequest(
                provider_name="openai",
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
        return response.text.strip(), response.model


def _render_user_message(rendered_prompt_payload: dict, user_payload: dict) -> str:
    return (
        "Render an author-facing response using the following semantic prompt payload.\n\n"
        f"Dynamic context:\n{json.dumps(user_payload, ensure_ascii=False, indent=2, sort_keys=True)}"
    )
