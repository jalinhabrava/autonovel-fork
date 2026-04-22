from __future__ import annotations

from dataclasses import asdict, dataclass
from statistics import median
from typing import Any


@dataclass(frozen=True)
class BootstrapChapterProfile:
    chapter_id: str
    sequence_index: int
    title: str
    input_tokens: int
    complexity_bucket: str
    expected_output_tokens: int


@dataclass(frozen=True)
class BootstrapProfile:
    work_title: str
    language: str
    chapter_count: int
    total_input_tokens: int
    token_p50: int
    token_p95: int
    token_max: int
    needs_structured_outputs: bool
    chapters: list[BootstrapChapterProfile]

    def to_json(self) -> dict[str, Any]:
        return {
            "work_title": self.work_title,
            "language": self.language,
            "chapter_count": self.chapter_count,
            "total_input_tokens": self.total_input_tokens,
            "token_p50": self.token_p50,
            "token_p95": self.token_p95,
            "token_max": self.token_max,
            "needs_structured_outputs": self.needs_structured_outputs,
            "chapters": [asdict(item) for item in self.chapters],
        }


def build_bootstrap_profile(
    *,
    work_title: str,
    language: str,
    chapters: list[Any],
    estimate_tokens,
) -> BootstrapProfile:
    chapter_profiles: list[BootstrapChapterProfile] = []
    token_counts: list[int] = []
    for sequence_index, chapter in enumerate(chapters, start=1):
        title = str(getattr(chapter, "title", "") or "").strip()
        text = str(getattr(chapter, "text", "") or "")
        tokens = max(1, int(estimate_tokens(text)))
        token_counts.append(tokens)
        chapter_profiles.append(
            BootstrapChapterProfile(
                chapter_id=f"ch_{sequence_index:03d}",
                sequence_index=sequence_index,
                title=title,
                input_tokens=tokens,
                complexity_bucket=_classify_complexity_bucket(title=title, text=text, tokens=tokens),
                expected_output_tokens=_expected_chapter_output_tokens(tokens),
            )
        )
    sorted_counts = sorted(token_counts) or [0]
    return BootstrapProfile(
        work_title=work_title,
        language=language,
        chapter_count=len(chapter_profiles),
        total_input_tokens=sum(token_counts),
        token_p50=int(median(sorted_counts)),
        token_p95=sorted_counts[min(len(sorted_counts) - 1, max(0, round((len(sorted_counts) - 1) * 0.95)))],
        token_max=max(sorted_counts),
        needs_structured_outputs=True,
        chapters=chapter_profiles,
    )


def classify_chapter_complexity(*, title: str, text: str, input_tokens: int) -> str:
    return _classify_complexity_bucket(title=title, text=text, tokens=input_tokens)


def _classify_complexity_bucket(*, title: str, text: str, tokens: int) -> str:
    noisy_title = any(mark in title for mark in ("[", "]", "(", ")", "*", "·"))
    markdown_noise = text.count("[[") + text.count("]]") + text.count("](")
    heading_count = text.count("\n#")
    if tokens >= 18000 or markdown_noise >= 15 or heading_count >= 10:
        return "large_or_complex"
    if tokens >= 8000 or noisy_title or markdown_noise >= 5:
        return "medium_complex"
    return "small_clean"


def _expected_chapter_output_tokens(input_tokens: int) -> int:
    if input_tokens >= 16000:
        return 2800
    if input_tokens >= 7000:
        return 2200
    return 1400
