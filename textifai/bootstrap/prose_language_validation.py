from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Protocol

from textifai.bootstrap.language import detect_language_profile, sample_text_for_language_detection


@dataclass(frozen=True)
class ProseLanguageValidationMessage:
    severity: str
    code: str
    message: str
    item_index: int | None = None
    sample: str | None = None


@dataclass(frozen=True)
class ProseLanguageValidationResult:
    available: bool
    valid: bool
    validator_name: str
    messages: list[ProseLanguageValidationMessage] = field(default_factory=list)


class ProseLanguageValidator(Protocol):
    validator_name: str

    def validate_texts(
        self,
        *,
        texts: list[str],
        expected_language: str,
        context: str,
    ) -> ProseLanguageValidationResult:
        ...


class HeuristicSpanishProseValidator:
    validator_name = "heuristic_spanish_prose"

    def validate_texts(
        self,
        *,
        texts: list[str],
        expected_language: str,
        context: str,
    ) -> ProseLanguageValidationResult:
        normalized = str(expected_language or "").strip().casefold()
        if not normalized.startswith("es"):
            return ProseLanguageValidationResult(
                available=False,
                valid=False,
                validator_name=self.validator_name,
                messages=[
                    ProseLanguageValidationMessage(
                        severity="warning",
                        code="unsupported_language",
                        message=(
                            f"{context} language validation is unavailable for expected_language={expected_language!r} "
                            f"with validator={self.validator_name}"
                        ),
                    )
                ],
            )

        messages: list[ProseLanguageValidationMessage] = []
        for index, raw_text in enumerate(texts):
            text = str(raw_text or "").strip()
            if _is_structured_trace_token(text):
                continue
            token_count = len(re.findall(r"[A-Za-zÀ-ÿ']+", text))
            if len(text) < 12 or token_count < 3:
                continue
            detected = detect_language_profile(sample_text_for_language_detection(text, max_chars=1200))
            detected_languages = set(detected.detected_languages or [])
            if detected.dominant_language == "es" and "en" not in detected_languages:
                continue
            if detected.dominant_language == "mixed" and "en" not in detected_languages:
                continue
            messages.append(
                ProseLanguageValidationMessage(
                    severity="error",
                    code="prose_language_mismatch",
                    message=(
                        f"{context} contains explanatory prose outside the configured language "
                        f"(expected={expected_language}, item_index={index}, detected={detected.dominant_language or 'unknown'}, "
                        f"detected_languages={sorted(detected_languages)}, sample={text[:120]!r})"
                    ),
                    item_index=index,
                    sample=text[:120],
                )
            )
        return ProseLanguageValidationResult(
            available=True,
            valid=not messages,
            validator_name=self.validator_name,
            messages=messages,
        )


def resolve_prose_language_validator(name: str | None) -> ProseLanguageValidator | None:
    normalized = str(name or "").strip().casefold()
    if not normalized or normalized in {"none", "disabled", "off"}:
        return None
    if normalized in {"heuristic", "heuristic_spanish_prose"}:
        return HeuristicSpanishProseValidator()
    return None


def _is_structured_trace_token(value: str) -> bool:
    token = str(value or "").strip()
    if not token or " " in token:
        return False
    return bool(re.fullmatch(r"[a-z0-9_:-]+(?:,[a-z0-9_:-]+)*", token))
