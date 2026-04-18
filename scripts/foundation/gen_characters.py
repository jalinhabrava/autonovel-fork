#!/usr/bin/env python3
"""
One-shot characters.md generator for foundation phase.
Reads seed.txt + voice.md + world.md + CRAFT.md, calls writer model.
"""
import sys
from pathlib import Path
from dotenv import load_dotenv
from providers.text_provider import TextGenerationRequest, TextMessage, get_text_provider
from stores.project_store import ProjectStore

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")
STORE = ProjectStore(BASE_DIR)
TEXT_PROVIDER = get_text_provider("gen_characters")

def call_writer(prompt, max_tokens=16000):
    request = TextGenerationRequest(
        task="gen_characters",
        max_tokens=max_tokens,
        system=(
            "You are a character designer for literary fiction with deep knowledge of "
            "wound/want/need/lie frameworks, Sanderson's three sliders, and dialogue "
            "distinctiveness. You create characters who feel like real people with "
            "contradictions, secrets, and speech patterns you can hear. "
            "You never use AI slop words. You write in clean, direct prose."
        ),
        messages=[TextMessage(role="user", content=prompt)],
    )
    return TEXT_PROVIDER.generate(request).text

seed = STORE.read_seed()
world = STORE.read_world()

# Voice Part 2 only
voice = STORE.read_voice()
voice_lines = voice.split('\n')
part2_start = next(i for i, l in enumerate(voice_lines) if 'Part 2' in l)
voice_part2 = '\n'.join(voice_lines[part2_start:])

prompt = f"""Build a complete character registry for this fantasy novel. This is CHARACTERS.MD --
the definitive reference for WHO exists in this story, what drives them, how they speak,
and what secrets they carry.

SEED CONCEPT:
{seed}

WORLD BIBLE (the world these characters inhabit):
{world}

VOICE IDENTITY (the novel's tone):
{voice_part2}

CHARACTER CRAFT REQUIREMENTS (from CRAFT.md):

### The Three Sliders (Sanderson)
Every character has three independent dials (0-10):
  PROACTIVITY -- Do they drive the plot or react to it?
  LIKABILITY  -- Does the reader empathize with them?
  COMPETENCE  -- Are they good at what they do?
Rule: compelling = HIGH on at least TWO, or HIGH on one with clear growth.

### Wound / Want / Need / Lie Framework
A causal chain:
  GHOST (backstory event) -> WOUND (ongoing damage) -> LIE (false belief to cope)
    -> WANT (external goal driven by Lie) -> NEED (internal truth, opposes Lie)
Rules: Want and Need must be IN TENSION. Lie statable in one sentence.
  Truth is its direct opposite.

### Dialogue Distinctiveness (8 dimensions)
1. Vocabulary level  2. Sentence length  3. Contractions/formality
4. Verbal tics  5. Question vs statement ratio  6. Interruption patterns
7. Metaphor domain  8. Directness vs indirectness
Test: Remove dialogue tags. Can you tell who's speaking?

BUILD THE REGISTRY WITH AT LEAST THESE CHARACTERS:

1. **The protagonist / primary POV character**
   - Full wound/want/need/lie chain
   - Three sliders with justification
   - Arc type (positive/negative/flat)
   - Detailed speech pattern (8 dimensions)
   - Physical habits and tells
   - At least 2 secrets
   - Key relationships mapped

2. **A core family member, mentor, or intimate tie**
   - Same depth as the protagonist
   - What this person knows and what they are hiding
   - How their private history creates pressure on the present story

3. **An absent or off-page character with major story gravity**
   - Even if absent for much of the story, they need full depth
   - What actually happened in the event or deal everyone circles around
   - Their presence through absence

4. **The primary antagonist or strongest counterforce**
   - Not a villain by default -- someone whose interests conflict with the protagonist's
   - Their own wound/want/need/lie (they should be understandable)

5. **An institutional power figure**
   - The system personified
   - They believe they are protecting something worth protecting

6. **An outsider, rival faction voice, or ideological challenger**
   - The perspective that tests the story's dominant assumptions
   - What they represent thematically

7. **At least 1-2 additional characters** that the story needs
   - A peer, friend, confidant, or foil?
   - Someone tied to the central conflict who knows more than they say?
   - Someone with divided loyalties?

FOR EACH CHARACTER INCLUDE:
- Name, age, role
- Ghost/Wound/Want/Need/Lie chain (for major characters)
- Three sliders (proactivity/likability/competence) with numbers and justification
- Arc type and arc trajectory
- Speech pattern (all 8 dimensions, with example lines)
- Physical appearance (specific, not generic)
- Physical habits and unconscious tells
- Secrets (what the reader doesn't learn immediately)
- Key relationships (mapped to other characters)
- Thematic role (what question does this character embody?)

IMPORTANT:
- Characters must INTERCONNECT. Their wants should conflict with each other.
- Every secret should be something that would CHANGE the story if revealed.
- Speech patterns must be distinct enough to pass the no-tags test.
- Give the protagonist habits that arise from their gift, wound, profession, or survival strategy.
- If there is a parent/guardian figure, tie any recurring physical tell to something specific.
- The antagonist should be as fully realized as the protagonist -- a worthy counterforce.
- Target ~3000-4000 words. Dense character work, not padding.
"""

print("Calling writer model...", file=sys.stderr)
result = call_writer(prompt)
print(result)
