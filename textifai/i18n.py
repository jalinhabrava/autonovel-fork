from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


DEFAULT_LOCALE = "en"
SUPPORTED_LOCALES = ("en", "es")
LOCALE_NAMESPACES = ("common", "shell", "onboarding", "doctor")
LOCALES_ROOT = Path(__file__).resolve().parent / "locales"


@dataclass(frozen=True)
class Translator:
    locale: str
    fallback_locale: str = DEFAULT_LOCALE

    def t(self, key: str, **kwargs) -> str:
        text = _lookup(self.locale, key)
        if text is None and self.locale != self.fallback_locale:
            text = _lookup(self.fallback_locale, key)
        if text is None:
            text = f"[missing:{key}]"
        if kwargs:
            return text.format(**kwargs)
        return text


def get_translator(locale: str | None) -> Translator:
    normalized = normalize_locale(locale)
    return Translator(locale=normalized)


def normalize_locale(locale: str | None) -> str:
    if not locale:
        return DEFAULT_LOCALE
    lowered = str(locale).strip().lower().replace("-", "_")
    primary = lowered.split("_", 1)[0]
    if primary in SUPPORTED_LOCALES:
        return primary
    return DEFAULT_LOCALE


@lru_cache(maxsize=None)
def _load_catalog(locale: str) -> dict[str, str]:
    normalized = normalize_locale(locale)
    catalog: dict[str, str] = {}
    for namespace in LOCALE_NAMESPACES:
        path = LOCALES_ROOT / normalized / f"{namespace}.json"
        if not path.exists():
            continue
        data = json.loads(path.read_text())
        catalog.update(data)
    return catalog


def _lookup(locale: str, key: str) -> str | None:
    return _load_catalog(locale).get(key)
