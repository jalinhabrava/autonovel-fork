from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol

from providers.text_provider import TextGenerationRequest, TextMessage, get_text_provider, get_text_provider_config_error
from textifai.author_understanding.contracts import LLMAuthorUnderstandingPayload
from textifai.author_understanding.normalization import extract_json_payload, normalize_author_understanding_payload
from textifai.author_understanding.prompt_builder import build_author_understanding_prompt
from textifai.conversation.contracts import ConversationRequest, NarrativeSignals, RecognizedIntent
from textifai.conversation.state import ConversationState
from textifai.vaerl.contracts import EntityResolutionResult


class AuthorUnderstandingLLMInterpreter(Protocol):
    def interpret(
        self,
        *,
        request: ConversationRequest,
        rule_intent: RecognizedIntent,
        narrative_signals: NarrativeSignals | None,
        entity_results: list[EntityResolutionResult],
        state: ConversationState | None,
    ) -> LLMAuthorUnderstandingPayload | None: ...


@dataclass(frozen=True)
class AuthorUnderstandingLLMConfig:
    task_name: str = "author_understanding"
    provider_name: str | None = None
    model: str | None = None
    max_tokens: int = 1200
    temperature: float = 0.1
    timeout_seconds: int = 120
    retries: int = 1


class ProviderBackedAuthorUnderstandingInterpreter:
    def __init__(self, *, config: AuthorUnderstandingLLMConfig | None = None) -> None:
        self.config = config or AuthorUnderstandingLLMConfig()

    def interpret(
        self,
        *,
        request: ConversationRequest,
        rule_intent: RecognizedIntent,
        narrative_signals: NarrativeSignals | None,
        entity_results: list[EntityResolutionResult],
        state: ConversationState | None,
    ) -> LLMAuthorUnderstandingPayload | None:
        if get_text_provider_config_error(self.config.task_name, self.config.provider_name):
            return None

        prompt = build_author_understanding_prompt(
            request=request,
            rule_intent=rule_intent,
            narrative_signals=narrative_signals,
            entity_results=entity_results,
            state=state,
        )
        user_prompt = json.dumps(
            {
                "prompt_version": prompt.prompt_version,
                "user_payload": prompt.user_payload,
                "required_output_schema": prompt.required_output_schema,
                "catalogs": prompt.catalogs,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        provider = get_text_provider(self.config.task_name, self.config.provider_name)
        response = provider.generate(
            TextGenerationRequest(
                task=self.config.task_name,
                provider_name=self.config.provider_name,
                model=self.config.model,
                system=prompt.system_prompt,
                messages=[TextMessage(role="user", content=user_prompt)],
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                timeout_seconds=self.config.timeout_seconds,
                retries=self.config.retries,
            )
        )
        payload = extract_json_payload(response.text)
        if payload is None:
            return None
        return normalize_author_understanding_payload(
            raw_text=request.raw_text,
            payload=payload,
            provider_name=response.provider_name,
            model=response.model,
        )
