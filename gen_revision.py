#!/usr/bin/env python3
"""
Revision chapter generator. Rewrites a chapter from a specific revision brief.
Usage: python gen_revision.py <chapter_num> <brief_file>
"""
import sys
from pathlib import Path
from dotenv import load_dotenv
from providers.text_provider import TextGenerationRequest, TextMessage, get_text_provider
from stores.project_store import ProjectStore

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")
STORE = ProjectStore(BASE_DIR)
TEXT_PROVIDER = get_text_provider("gen_revision")

def call_writer(prompt, max_tokens=16000):
    request = TextGenerationRequest(
        task="gen_revision",
        max_tokens=max_tokens,
        system=(
            "You are rewriting a fantasy novel chapter based on a specific revision brief. "
            "You follow the brief exactly. You preserve the voice, world, and characters "
            "from the existing draft while making the structural changes specified. "
            "You write the FULL chapter. Do not truncate or summarize."
        ),
        messages=[TextMessage(role="user", content=prompt)],
    )
    return TEXT_PROVIDER.generate(request).text

def main():
    ch_num = int(sys.argv[1])
    brief_file = sys.argv[2]
    
    voice = STORE.read_voice()
    characters = STORE.read_characters()
    world = STORE.read_world()
    brief = Path(brief_file).read_text()
    title = STORE.get_title()
    
    # Load adjacent chapters for continuity
    prev_path = STORE.chapter_path(ch_num - 1)
    next_path = STORE.chapter_path(ch_num + 1)
    prev_tail = prev_path.read_text()[-2000:] if prev_path.exists() else "(first chapter)"
    next_head = next_path.read_text()[:1500] if next_path.exists() else "(last chapter)"
    
    # Load old version if exists
    old_path = STORE.chapter_path(ch_num)
    old_text = old_path.read_text() if old_path.exists() else "(no existing draft)"
    
    prompt = f"""Rewrite Chapter {ch_num} of "{title}".

REVISION BRIEF (follow this exactly):
{brief}

VOICE DEFINITION:
{voice}

CHARACTER REGISTRY:
{characters}

WORLD BIBLE:
{world}

PREVIOUS CHAPTER ENDING (maintain continuity):
{prev_tail}

NEXT CHAPTER OPENING (end so this flows into it):
{next_head}

THE EXISTING DRAFT (use as raw material -- keep what works, cut what doesn't):
{old_text}

ANTI-PATTERN RULES:
- NO triadic sensory lists (X. Y. Z.)
- NO "He did not [verb]" more than once
- NO "He thought about [X]" constructions
- NO "the way [X] did [Y]" more than twice
- NO "not X, but Y" formula in narration
- NO over-explaining after showing
- MAX 2 section breaks
- At least one moment that genuinely surprises
- 70%+ in-scene (dialogue and action, not summary)
- Dialogue should sound like speech, not prose

Write the FULL revised chapter now."""

    print(f"Rewriting Chapter {ch_num}...", file=sys.stderr)
    result = call_writer(prompt)
    
    out_path = STORE.write_chapter(ch_num, result)
    print(f"Saved to {out_path}", file=sys.stderr)
    print(f"Word count: {len(result.split())}", file=sys.stderr)

if __name__ == "__main__":
    main()
