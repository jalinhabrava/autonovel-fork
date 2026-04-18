from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol

from providers.text_provider import TextGenerationRequest, TextMessage, get_text_provider, get_text_provider_config_error
from textifai.author_understanding.normalization import extract_json_payload
from textifai.derived_sources.contracts import DerivedExtractionSeed, DerivedLLMExtractionPayload, LLMEscalationDecision
from textifai.derived_sources.normalization import normalize_derived_llm_payload
from textifai.derived_sources.prompt_builder import build_derived_understanding_prompt


class DerivedSourceLLMInterpreter(Protocol):
    def interpret(
        self,
        *,
        seed: DerivedExtractionSeed,
        escalation: LLMEscalationDecision,
    ) -> DerivedLLMExtractionPayload | None: ...


@dataclass(frozen=True)
class DerivedSourceLLMConfig:
    task_name: str = "derived_source_understanding"
    provider_name: str | None = None
    model: str | None = None
    max_tokens: int = 1800
    temperature: float = 0.1
    timeout_seconds: int = 120
    retries: int = 1


class ProviderBackedDerivedSourceInterpreter:
    def __init__(self, *, config: DerivedSourceLLMConfig | None = None) -> None:
        self.config = config or DerivedSourceLLMConfig()

    def interpret(
        self,
        *,
        seed: DerivedExtractionSeed,
        escalation: LLMEscalationDecision,
    ) -> DerivedLLMExtractionPayload | None:
        if get_text_provider_config_error(self.config.task_name, self.config.provider_name):
            return None
        prompt = build_derived_understanding_prompt(seed=seed, escalation=escalation)
        payload = json.dumps(
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
                messages=[TextMessage(role="user", content=payload)],
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                timeout_seconds=self.config.timeout_seconds,
                retries=self.config.retries,
            )
        )
        raw_payload = extract_json_payload(response.text)
        if raw_payload is None:
            return None
        return normalize_derived_llm_payload(
            payload=raw_payload,
            source_id=seed.source_id,
            source_format=seed.source_format,
            llm_used=True,
            format_profile=seed.format_profile,
        )
