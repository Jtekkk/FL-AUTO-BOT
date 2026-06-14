"""AI music director -- turn a natural-language brief into a song.

The LLM does the *reasoning and creation*: it interprets a prompt like
"a dark, melancholic lofi beat around 72 BPM with a jazzy progression" and
designs a concrete :class:`SongPlan` -- key, scale, tempo, an authored chord
progression and (optionally) its own drum groove. The deterministic engine
(:func:`flautobot.arrange.compose`) then *renders* that plan to MIDI, so the
output is always musically valid and reproducible from a seed.

Two backends are supported:

* **Claude** (default) -- the ``anthropic`` SDK + an API key (``ANTHROPIC_API_KEY``).
* **Ollama** -- a local, offline model (e.g. ``llama3.1``) via the Ollama HTTP
  API; no API key, no cloud, stdlib-only.

A :class:`Conversation` keeps context so you can iteratively refine a song
("make it darker", "add an arp"). This layer is optional -- the rest of FL Auto
Bot works without it.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from . import theory
from .arrange import compose
from .generators.arp import ARP_MODES
from .generators.bass import BASS_STYLES
from .generators.chords import CHORD_STYLES
from .generators.drums import DRUM_MAP
from .genres import get_genre, list_genres
from .song import Song

DEFAULT_MODEL = "claude-opus-4-8"          # most capable Claude model
DEFAULT_OLLAMA_MODEL = "llama3.1"
DEFAULT_OLLAMA_HOST = "http://localhost:11434"
LANES = ["drums", "bass", "chords", "melody", "arp"]
_STEP_CHARS = set("Xxo.")


class AIError(RuntimeError):
    """Raised when the AI director can't run (missing SDK/key, API error)."""


SYSTEM_PROMPT = f"""\
You are the music director for "FL Auto Bot", a tool that composes songs and \
exports them as MIDI for FL Studio. Translate the user's brief into a concrete, \
musical plan that a deterministic renderer will turn into notes.

You are choosing real musical decisions, so be deliberate and tasteful:
- Pick a `genre` preset that best fits the brief (sets default sounds). \
Options: {", ".join(list_genres())}.
- Choose `key` (a tonic like "A", "F#", "Eb"), `scale`, `tempo` (BPM) and `bars` \
(song length) to match the requested mood and energy.
- Author the `progression` yourself as a list of diatonic scale DEGREES (integers \
1-7, where 1 is the tonic). 4 or 8 chords usually works; make it interesting -- \
e.g. [1,6,4,5] is bright, [1,6,3,7] is moody minor, [2,5,1,1] is jazzy.
- `tracks`: which instrument lanes to include, from {LANES}.
- `bass_style` one of {list(BASS_STYLES)}; `chord_style` one of {list(CHORD_STYLES)}; \
`arp_mode` one of {list(ARP_MODES)}.
- `swing` 0.0-1.0 (lofi/hip-hop ~0.2, house ~0.1, techno 0.0); `sevenths` true for \
jazzier chords.
- `drum_pattern` (OPTIONAL): to author your own groove instead of the genre's, give \
a list of {{voice, steps}} where `voice` is one of {list(DRUM_MAP)} and `steps` is a \
16-character string for one bar (use `X` accent, `x` normal, `o` ghost, `.` rest). \
Kick is usually on strong beats, snare/clap on beats 2 and 4. Leave it as an empty \
list to use the genre's built-in groove.
- `mood`: a few keywords; `explanation`: one or two sentences on WHY these fit.

When the user asks to refine an existing song, return an updated COMPLETE plan that \
keeps what they liked and changes what they asked for. Respond with a single JSON \
object matching the required fields and nothing else."""


def _schema() -> Dict[str, Any]:
    """JSON schema for the structured plan."""
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
            "drum_pattern": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "voice": {"type": "string", "enum": list(DRUM_MAP)},
                        "steps": {"type": "string"},
                    },
                    "required": ["voice", "steps"],
                },
            },
            "mood": {"type": "string"},
            "explanation": {"type": "string"},
        },
        "required": [
            "title", "genre", "key", "scale", "tempo", "bars", "progression",
            "tracks", "bass_style", "chord_style", "arp_mode", "swing",
            "sevenths", "drum_pattern", "mood", "explanation",
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
    drum_pattern: Dict[str, str] = field(default_factory=dict)
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
            drum_pattern=_parse_drum_pattern(data.get("drum_pattern")),
            mood=str(data.get("mood", "")),
            explanation=str(data.get("explanation", "")),
            raw=data,
        )

    def summary(self) -> str:
        deg = "-".join(str(d) for d in self.progression)
        groove = "custom" if self.drum_pattern else "genre default"
        return (f"{self.title}\n"
                f"  {self.genre} | {self.key} {self.scale} | {self.tempo} BPM | "
                f"{self.bars} bars | progression {deg}\n"
                f"  tracks: {', '.join(self.tracks)} | swing {self.swing:g} | "
                f"7ths {self.sevenths} | drums: {groove}\n"
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
        drum_pattern=plan.drum_pattern or None,
    )


# --- Backends ----------------------------------------------------------------

class AnthropicPlanner:
    """Planner backed by Claude via the Anthropic SDK."""

    name = "claude"

    def __init__(self, model: str = DEFAULT_MODEL, api_key: Optional[str] = None,
                 max_tokens: int = 8000) -> None:
        try:
            import anthropic
        except ImportError as exc:
            raise AIError(
                "The Claude backend needs the Anthropic SDK.\n"
                "  Install it with:  pip install anthropic   (or: pip install -e \".[ai]\")\n"
                "Or run fully offline with:  --backend ollama"
            ) from exc
        self._anthropic = anthropic
        self.model = model
        self.max_tokens = max_tokens
        try:
            self.client = anthropic.Anthropic(api_key=api_key) if api_key \
                else anthropic.Anthropic()
        except Exception as exc:
            raise AIError(f"Could not initialise the Anthropic client: {exc}") from exc

    def complete(self, system: str, messages: List[dict], schema: dict) -> str:
        anthropic = self._anthropic
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                thinking={"type": "adaptive"},
                system=system,
                messages=messages,
                output_config={"format": {"type": "json_schema", "schema": schema}},
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
            raise AIError(
                f"Could not reach Claude: {exc}\n"
                "Make sure ANTHROPIC_API_KEY is set:  export ANTHROPIC_API_KEY=sk-ant-...\n"
                "Or run fully offline with:  --backend ollama"
            ) from exc

        if response.stop_reason == "refusal":
            raise AIError("The model declined to produce a plan for this brief.")
        if response.stop_reason == "max_tokens":
            raise AIError("The plan was cut off (max_tokens). Try a simpler brief.")
        text = next((b.text for b in response.content if b.type == "text"), None)
        if not text:
            raise AIError("The model returned no plan text.")
        return text


class OllamaPlanner:
    """Planner backed by a local Ollama model (offline, no API key)."""

    name = "ollama"

    def __init__(self, model: str = DEFAULT_OLLAMA_MODEL,
                 host: str = DEFAULT_OLLAMA_HOST, timeout: float = 120.0) -> None:
        self.model = model
        self.host = host.rstrip("/")
        self.timeout = timeout

    def complete(self, system: str, messages: List[dict], schema: dict) -> str:
        body = json.dumps({
            "model": self.model,
            "messages": [{"role": "system", "content": system}, *messages],
            "stream": False,
            "format": schema,        # Ollama structured outputs (>= 0.5)
            "options": {"temperature": 0.7},
        }).encode("utf-8")
        request = urllib.request.Request(
            f"{self.host}/api/chat", data=body,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise AIError(
                f"Could not reach Ollama at {self.host}: {exc.reason}\n"
                "Start it with:  ollama serve   and pull a model:  ollama pull "
                f"{self.model}"
            ) from exc
        except Exception as exc:
            raise AIError(f"Ollama request failed: {exc}") from exc

        text = (payload.get("message") or {}).get("content")
        if not text:
            raise AIError("Ollama returned no content.")
        return text


def _make_planner(backend: str, model: Optional[str], api_key: Optional[str],
                  host: str = DEFAULT_OLLAMA_HOST) -> Any:
    backend = backend.strip().lower()
    if backend == "claude":
        return AnthropicPlanner(model or DEFAULT_MODEL, api_key)
    if backend == "ollama":
        return OllamaPlanner(model or DEFAULT_OLLAMA_MODEL, host)
    raise AIError(f"Unknown backend {backend!r}. Use 'claude' or 'ollama'.")


# --- Director & conversation -------------------------------------------------

class AIDirector:
    """Plans songs from natural-language briefs using a chosen backend."""

    def __init__(self, backend: str = "claude", model: Optional[str] = None,
                 api_key: Optional[str] = None, host: str = DEFAULT_OLLAMA_HOST) -> None:
        self.planner = _make_planner(backend, model, api_key, host)
        self.system = SYSTEM_PROMPT
        self.schema = _schema()

    @property
    def model(self) -> str:
        return getattr(self.planner, "model", self.planner.name)

    def _to_plan(self, text: str) -> SongPlan:
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # Local models sometimes wrap JSON in prose -- salvage the object.
            start, end = text.find("{"), text.rfind("}")
            if start == -1 or end <= start:
                raise AIError("The model did not return parseable JSON.")
            try:
                data = json.loads(text[start:end + 1])
            except json.JSONDecodeError as exc:
                raise AIError(f"Could not parse the model's plan as JSON: {exc}") from exc
        return SongPlan.from_response(data)

    def plan(self, brief: str) -> SongPlan:
        """Ask the backend to design a song plan for ``brief``."""
        text = self.planner.complete(
            self.system, [{"role": "user", "content": brief}], self.schema)
        return self._to_plan(text)

    def compose(self, brief: str, seed: Optional[int] = None) -> Tuple[Song, SongPlan]:
        """Plan from ``brief`` and render the resulting song."""
        plan = self.plan(brief)
        return render_plan(plan, seed=seed), plan

    def conversation(self, seed: Optional[int] = None) -> "Conversation":
        """Start a stateful conversation for iterative refinement."""
        return Conversation(self, seed=seed)


class Conversation:
    """A multi-turn refine loop: send a brief, then adjustments build on it."""

    def __init__(self, director: AIDirector, seed: Optional[int] = None) -> None:
        self.director = director
        self.seed = seed
        self.messages: List[dict] = []
        self.plan: Optional[SongPlan] = None

    def send(self, instruction: str) -> Tuple[Song, SongPlan]:
        """Send a brief or a refinement and get the updated song + plan."""
        self.messages.append({"role": "user", "content": instruction})
        text = self.director.planner.complete(
            self.director.system, self.messages, self.director.schema)
        self.messages.append({"role": "assistant", "content": text})
        self.plan = self.director._to_plan(text)
        return render_plan(self.plan, seed=self.seed), self.plan


def _parse_drum_pattern(value: Any) -> Dict[str, str]:
    """Validate an LLM drum pattern (list of {voice, steps}) into a clean dict."""
    pattern: Dict[str, str] = {}
    if not isinstance(value, list):
        return pattern
    for item in value:
        if not isinstance(item, dict):
            continue
        voice, steps = item.get("voice"), item.get("steps")
        if (voice in DRUM_MAP and isinstance(steps, str)
                and len(steps) == 16 and set(steps) <= _STEP_CHARS):
            pattern[voice] = steps
    return pattern


def _clamp(value: Any, low: float, high: float) -> float:
    try:
        return max(low, min(high, float(value)))
    except (TypeError, ValueError):
        return low


def _pick(value: Any, allowed, default: str) -> str:
    return value if value in allowed else default
