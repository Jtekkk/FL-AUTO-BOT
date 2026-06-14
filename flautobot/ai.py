"""AI music director -- turn a natural-language brief into a song with Claude.

The LLM does the *reasoning and creation*: it interprets a prompt like
"a dark, melancholic lofi beat around 72 BPM with a jazzy progression" and
designs a concrete :class:`SongPlan` -- key, scale, tempo, an authored chord
progression (as scale degrees), instrumentation and grooves. The deterministic
engine (:func:`flautobot.arrange.compose`) then *renders* that plan to MIDI, so
the output is always musically valid and reproducible from a seed.

This layer is optional. It needs the ``anthropic`` SDK and an API key
(``ANTHROPIC_API_KEY``); without them the rest of FL Auto Bot works unchanged::

    pip install "anthropic"          # or: pip install -e ".[ai]"
    export ANTHROPIC_API_KEY=sk-ant-...

    from flautobot.ai import AIDirector
    song, plan = AIDirector().compose("uplifting summer house in F# minor, 124 bpm")
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from . import theory
from .arrange import compose
from .generators.arp import ARP_MODES
from .generators.bass import BASS_STYLES
from .generators.chords import CHORD_STYLES
from .genres import get_genre, list_genres
from .song import Song

# Default to the most capable Claude model for creative reasoning.
DEFAULT_MODEL = "claude-opus-4-8"
LANES = ["drums", "bass", "chords", "melody", "arp"]


class AIError(RuntimeError):
    """Raised when the AI director can't run (missing SDK/key, API error)."""


SYSTEM_PROMPT = f"""\
You are the music director for "FL Auto Bot", a tool that composes songs and \
exports them as MIDI for FL Studio. Translate the user's brief into a concrete, \
musical plan that a deterministic renderer will turn into notes.

You are choosing real musical decisions, so be deliberate and tasteful:
- Pick a `genre` preset that best fits the brief (this sets the drum groove and \
default sounds). Options: {", ".join(list_genres())}.
- Choose `key` (a tonic like "A", "F#", "Eb"), `scale`, `tempo` (BPM) and `bars` \
(song length) to match the requested mood and energy.
- Author the `progression` yourself as a list of diatonic scale DEGREES (integers \
1-7, where 1 is the tonic chord). 4 or 8 chords usually works well. Make it \
interesting and appropriate -- e.g. [1,6,4,5] is bright, [1,6,3,7] is moody minor, \
[2,5,1,1] is jazzy.
- `tracks`: which instrument lanes to include, from {LANES}. Sparse, atmospheric \
briefs use fewer; energetic ones use more.
- `bass_style` one of {list(BASS_STYLES)}; `chord_style` one of {list(CHORD_STYLES)}; \
`arp_mode` one of {list(ARP_MODES)}.
- `swing` 0.0-1.0 (shuffle feel; lofi/hip-hop like ~0.2, house ~0.1, techno 0.0).
- `sevenths`: true for richer/jazzier chords, false for simple triads.
- `mood`: a few keywords describing the vibe.
- `explanation`: one or two sentences on WHY these choices fit the brief.

Always return a complete plan. Prefer musical coherence over novelty for its own sake."""


def _schema() -> Dict[str, Any]:
    """JSON schema for the structured plan (drives Claude's `output_config`)."""
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "title": {"type": "string"},
            "genre": {"type": "string", "enum": list_genres()},
            "key": {"type": "string"},
            "scale": {"type": "string", "enum": sorted(theory.SCALES)},
            "tempo": {"type": "integer"},
            "bars": {"type": "integer"},
            "progression": {"type": "array", "items": {"type": "integer"}},
            "tracks": {"type": "array", "items": {"type": "string", "enum": LANES}},
            "bass_style": {"type": "string", "enum": list(BASS_STYLES)},
            "chord_style": {"type": "string", "enum": list(CHORD_STYLES)},
            "arp_mode": {"type": "string", "enum": list(ARP_MODES)},
            "swing": {"type": "number"},
            "sevenths": {"type": "boolean"},
            "mood": {"type": "string"},
            "explanation": {"type": "string"},
        },
        "required": [
            "title", "genre", "key", "scale", "tempo", "bars", "progression",
            "tracks", "bass_style", "chord_style", "arp_mode", "swing",
            "sevenths", "mood", "explanation",
        ],
    }


@dataclass
class SongPlan:
    """A validated, render-ready plan produced by the LLM."""

    title: str
    genre: str
    key: str
    scale: str
    tempo: int
    bars: int
    progression: List[int]
    tracks: List[str]
    bass_style: str
    chord_style: str
    arp_mode: str
    swing: float
    sevenths: bool
    mood: str = ""
    explanation: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_response(cls, data: Dict[str, Any]) -> "SongPlan":
        """Build a plan from raw model JSON, clamping everything to safe values."""
        genre = data.get("genre", "house")
        try:
            get_genre(genre)
        except ValueError:
            genre = "house"

        key = str(data.get("key", "A")).strip() or "A"
        try:
            theory.parse_root(key)
        except ValueError:
            key = "A"

        scale = data.get("scale", "minor")
        if scale not in theory.SCALES:
            scale = "minor"

        # Map degrees into 1..7 and drop anything non-integer.
        degrees = [((int(d) - 1) % 7) + 1 for d in data.get("progression", [])
                   if isinstance(d, (int, float))]
        if not degrees:
            degrees = [1, 6, 4, 5]

        tracks = [t for t in data.get("tracks", []) if t in LANES]
        if not tracks:
            tracks = ["drums", "bass", "chords"]

        return cls(
            title=str(data.get("title") or "AI Track"),
            genre=genre,
            key=key,
            scale=scale,
            tempo=int(_clamp(data.get("tempo", 120), 40, 300)),
            bars=int(_clamp(data.get("bars", 32), 1, 256)),
            progression=degrees,
            tracks=tracks,
            bass_style=_pick(data.get("bass_style"), BASS_STYLES, "offbeat"),
            chord_style=_pick(data.get("chord_style"), CHORD_STYLES, "pad"),
            arp_mode=_pick(data.get("arp_mode"), ARP_MODES, "up"),
            swing=float(_clamp(data.get("swing", 0.0), 0.0, 1.0)),
            sevenths=bool(data.get("sevenths", False)),
            mood=str(data.get("mood", "")),
            explanation=str(data.get("explanation", "")),
            raw=data,
        )

    def summary(self) -> str:
        deg = "-".join(str(d) for d in self.progression)
        return (f"{self.title}\n"
                f"  {self.genre} | {self.key} {self.scale} | {self.tempo} BPM | "
                f"{self.bars} bars | progression {deg}\n"
                f"  tracks: {', '.join(self.tracks)} | swing {self.swing:g} | "
                f"7ths {self.sevenths}\n"
                f"  mood: {self.mood}\n"
                f"  why: {self.explanation}")


def render_plan(plan: SongPlan, seed: Optional[int] = None) -> Song:
    """Render a :class:`SongPlan` to a :class:`Song` (no network involved)."""
    return compose(
        genre=plan.genre, key=plan.key, scale=plan.scale, tempo=plan.tempo,
        bars=plan.bars, seed=seed, name=plan.title,
        progression=plan.progression, tracks=plan.tracks, swing=plan.swing,
        sevenths=plan.sevenths, bass_style=plan.bass_style,
        chord_style=plan.chord_style, arp_mode=plan.arp_mode,
    )


class AIDirector:
    """Wraps Claude to plan songs from natural-language briefs."""

    def __init__(self, api_key: Optional[str] = None, model: str = DEFAULT_MODEL,
                 max_tokens: int = 8000) -> None:
        try:
            import anthropic
        except ImportError as exc:
            raise AIError(
                "The AI director needs the Anthropic SDK.\n"
                "  Install it with:  pip install anthropic   (or: pip install -e \".[ai]\")"
            ) from exc
        self._anthropic = anthropic
        self.model = model
        self.max_tokens = max_tokens
        self._schema = _schema()
        try:
            self.client = anthropic.Anthropic(api_key=api_key) if api_key \
                else anthropic.Anthropic()
        except Exception as exc:  # missing key surfaces here
            raise AIError(
                f"Could not initialise the Anthropic client: {exc}\n"
                "Set your key:  export ANTHROPIC_API_KEY=sk-ant-..."
            ) from exc

    def plan(self, brief: str) -> SongPlan:
        """Ask Claude to design a song plan for ``brief``."""
        anthropic = self._anthropic
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                thinking={"type": "adaptive"},
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": brief}],
                output_config={"format": {"type": "json_schema", "schema": self._schema}},
            )
        except anthropic.AuthenticationError as exc:
            raise AIError("Authentication failed -- check ANTHROPIC_API_KEY.") from exc
        except anthropic.RateLimitError as exc:
            raise AIError("Rate limited by the Claude API; try again shortly.") from exc
        except anthropic.APIConnectionError as exc:
            raise AIError(f"Network error reaching the Claude API: {exc}") from exc
        except anthropic.APIError as exc:
            raise AIError(f"Claude API error: {exc}") from exc
        except Exception as exc:
            # e.g. a TypeError when no credentials resolve (key is checked lazily).
            raise AIError(
                f"Could not reach Claude: {exc}\n"
                "Make sure ANTHROPIC_API_KEY is set:  export ANTHROPIC_API_KEY=sk-ant-..."
            ) from exc

        if response.stop_reason == "refusal":
            raise AIError("The model declined to produce a plan for this brief.")
        if response.stop_reason == "max_tokens":
            raise AIError("The plan was cut off (max_tokens). Try a simpler brief.")

        text = next((b.text for b in response.content if b.type == "text"), None)
        if not text:
            raise AIError("The model returned no plan text.")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise AIError(f"Could not parse the model's plan as JSON: {exc}") from exc
        return SongPlan.from_response(data)

    def compose(self, brief: str, seed: Optional[int] = None) -> tuple[Song, SongPlan]:
        """Plan from ``brief`` and render the resulting song."""
        plan = self.plan(brief)
        return render_plan(plan, seed=seed), plan


def _clamp(value: Any, low: float, high: float) -> float:
    try:
        return max(low, min(high, float(value)))
    except (TypeError, ValueError):
        return low


def _pick(value: Any, allowed, default: str) -> str:
    return value if value in allowed else default
