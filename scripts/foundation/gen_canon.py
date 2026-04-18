#!/usr/bin/env python3
"""
Generate canon.md by extracting all hard facts from world.md + characters.md.
"""
import sys
from pathlib import Path
from dotenv import load_dotenv
from providers.text_provider import TextGenerationRequest, TextMessage, get_text_provider
from stores.project_store import ProjectStore

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")
STORE = ProjectStore(BASE_DIR)
TEXT_PROVIDER = get_text_provider("gen_canon")

def call_writer(prompt, max_tokens=16000):
    request = TextGenerationRequest(
        task="gen_canon",
        max_tokens=max_tokens,
        system=(
            "You are a continuity editor extracting hard facts from fantasy novel "
            "planning documents. You are precise, exhaustive, and never invent facts "
            "that aren't in the source material. Every entry must be traceable to a "
            "specific statement in the source documents."
        ),
        messages=[TextMessage(role="user", content=prompt)],
    )
    return TEXT_PROVIDER.generate(request).text

world = STORE.read_world()
characters = STORE.read_characters()
seed = STORE.read_seed()

prompt = f"""Extract EVERY hard fact from these planning documents into a structured canon database.
A "hard fact" is anything a writer must not contradict: names, ages, dates, physical descriptions,
rules of the magic system, geography, relationships, established events.

SOURCE DOCUMENTS:

=== SEED.TXT ===
{seed}

=== WORLD.MD ===
{world}

=== CHARACTERS.MD ===
{characters}

FORMAT THE OUTPUT AS CANON.MD with these categories:

## Geography
- Specific facts about locations, distances, physical properties

## Timeline
- Dated events, ages, durations

## Magic System Rules
- Hard rules of the story's primary magic or speculative system
- Specifics of any exceptional gift, anomaly, curse, or rare ability

## Character Facts
- Ages, physical descriptions, habits, relationships
- One entry per fact (not paragraphs)

## Political / Factional
- Who controls what, alliances, conflicts, contracts

## Cultural
- Customs, taboos, laws, festivals, food, clothing

## Established In-Story
- Events that have already happened in the story's past
- The core disputes, losses, contracts, betrayals, wars, discoveries, or disappearances that already happened

RULES:
- One fact per bullet point. Short. Specific. Checkable.
- Include the source (world.md or characters.md) in parentheses after each fact.
- Aim for 80-120 entries minimum. Be exhaustive.
- If two documents give slightly different details, note the discrepancy.
- DO NOT invent facts. Only record what's explicitly stated.
"""

print("Calling writer model...", file=sys.stderr)
result = call_writer(prompt)
print(result)
