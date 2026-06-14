"""Drum-pattern generation using a 16-step grid per bar.

Patterns are written as 16-character strings (one bar of 16th notes):

    ``X`` accented hit   ``x`` normal hit   ``o`` ghost/soft hit   ``.`` rest

Styles map a drum voice (kick, snare, ...) to one of those strings. The
generator adds optional swing and light humanisation so the output doesn't
feel robotic.
"""

from __future__ import annotations

import random
from typing import Dict, List

from ..song import Note

# General MIDI percussion map (these pitches trigger the matching FL Studio /
# GM drum sounds when the track is routed to the percussion channel).
DRUM_MAP = {
    "kick": 36,
    "rim": 37,
    "snare": 38,
    "clap": 39,
    "closed_hat": 42,
    "pedal_hat": 44,
    "open_hat": 46,
    "low_tom": 45,
    "mid_tom": 47,
    "high_tom": 50,
    "crash": 49,
    "ride": 51,
    "shaker": 70,
    "cowbell": 56,
}

_VEL = {"X": 1.0, "x": 0.8, "o": 0.5}

# One bar (16 steps) per voice. Step 0 is the downbeat.
DRUM_STYLES: Dict[str, Dict[str, str]] = {
    "house": {
        "kick":       "X...X...X...X...",
        "clap":       "....X.......X...",
        "closed_hat": "..x...x...x...x.",
        "open_hat":   "..x...x...x...x.",
    },
    "deep_house": {
        "kick":       "X...X...X...X...",
        "clap":       "....x.......x...",
        "closed_hat": "x.x.x.x.x.x.x.x.",
        "open_hat":   "..o...o...o...o.",
        "shaker":     ".x.x.x.x.x.x.x.x",
    },
    "techno": {
        "kick":       "X...X...X...X...",
        "closed_hat": "..x...x...x...x.",
        "clap":       "........X.......",
        "ride":       ".x.x.x.x.x.x.x.x",
    },
    "boombap": {
        "kick":       "X.....x...X.....",
        "snare":      "....X.......X...",
        "closed_hat": "x.x.x.x.x.x.x.x.",
    },
    "lofi": {
        "kick":       "X.....x...X.....",
        "snare":      "....x.......x...",
        "closed_hat": "x.o.x.o.x.o.x.o.",
        "rim":        "..........o.....",
    },
    "trap": {
        "kick":       "X......x..X.....",
        "clap":       "........X.......",
        "closed_hat": "xxxxxxxxxxxxxxxx",
    },
    "dnb": {
        "kick":       "X.........x.....",
        "snare":      "....X.......X..o",
        "closed_hat": "x.x.x.x.x.x.x.x.",
    },
    "ambient": {
        "kick":       "X...............",
        "shaker":     "....o.......o...",
    },
}

STEPS_PER_BAR = 16


def generate_drums(
    style: str,
    bars: int,
    *,
    beats_per_bar: int = 4,
    base_velocity: int = 100,
    swing: float = 0.0,
    humanize: float = 0.04,
    fill_every: int = 0,
    rng: random.Random | None = None,
) -> List[Note]:
    """Generate ``bars`` worth of drum notes for ``style``.

    Args:
        style: a key of :data:`DRUM_STYLES`.
        bars: how many bars to render.
        swing: 0..1, delays every other 16th to create a shuffle.
        humanize: 0..1, adds subtle timing/velocity variation.
        fill_every: if > 0, add a snare/tom fill on the last beat of every
            Nth bar (e.g. ``4`` -> a fill before each new 4-bar phrase).
        rng: optional seeded ``random.Random`` for reproducible output.
    """
    if style not in DRUM_STYLES:
        raise ValueError(f"Unknown drum style {style!r}. Options: {sorted(DRUM_STYLES)}")
    rng = rng or random.Random()
    pattern = DRUM_STYLES[style]
    step_beats = beats_per_bar / STEPS_PER_BAR
    swing_delay = swing * step_beats * 0.5

    notes: List[Note] = []
    for bar in range(bars):
        bar_start = bar * beats_per_bar
        for voice, steps in pattern.items():
            pitch = DRUM_MAP[voice]
            for i, ch in enumerate(steps):
                if ch not in _VEL:
                    continue
                start = bar_start + i * step_beats
                if i % 2 == 1:
                    start += swing_delay
                vel = base_velocity * _VEL[ch]
                if humanize:
                    start += rng.uniform(-humanize, humanize) * step_beats
                    vel *= 1 + rng.uniform(-humanize, humanize)
                notes.append(Note(
                    pitch=pitch,
                    start=max(0.0, start),
                    duration=step_beats * 0.9,
                    velocity=_clamp_vel(vel),
                ))
        if fill_every and (bar + 1) % fill_every == 0:
            notes.extend(_fill(bar_start, beats_per_bar, base_velocity, rng))
    return notes


def _fill(bar_start: float, beats_per_bar: int, base_velocity: int,
          rng: random.Random) -> List[Note]:
    """A quick tom/snare fill across the final beat of a bar."""
    toms = [DRUM_MAP["snare"], DRUM_MAP["mid_tom"], DRUM_MAP["low_tom"], DRUM_MAP["high_tom"]]
    start = bar_start + beats_per_bar - 1
    notes = []
    for i in range(4):
        notes.append(Note(
            pitch=rng.choice(toms),
            start=start + i * 0.25,
            duration=0.22,
            velocity=_clamp_vel(base_velocity * rng.uniform(0.7, 1.0)),
        ))
    return notes


def _clamp_vel(v: float) -> int:
    return max(1, min(127, int(round(v))))
