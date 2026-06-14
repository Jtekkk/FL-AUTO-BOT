"""Example: describe songs in plain English and let Claude design them.

Needs the Anthropic SDK and an API key::

    pip install anthropic
    export ANTHROPIC_API_KEY=sk-ant-...
    python examples/ai_brief.py

Each brief is turned into a plan by Claude, then rendered to a .mid you can drag
into FL Studio. Without a key it prints a friendly message and exits.
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from flautobot import write_midi
from flautobot.ai import AIDirector, AIError

BRIEFS = [
    "dark, melancholic lofi beat around 72 bpm with a jazzy ii-V-i progression",
    "energetic festival house in F# minor with a big uplifting drop",
    "spacey ambient piece, no drums, slow evolving pads in a major key",
]

try:
    director = AIDirector()  # reads ANTHROPIC_API_KEY from the environment
except AIError as exc:
    print(exc)
    sys.exit(1)

for i, brief in enumerate(BRIEFS, 1):
    try:
        song, plan = director.compose(brief, seed=i)
    except AIError as exc:
        print(f"[{brief}] -> {exc}")
        continue
    path = write_midi(song, f"output/ai_{i:02d}.mid")
    print(plan.summary())
    print(f"  -> {path}  ({song.note_count()} notes)\n")
