"""Chord / pad generation from a progression, with light voice-leading."""

from __future__ import annotations

import random
from typing import List

from ..song import Note
from ..theory import ChordEvent

CHORD_STYLES = ("pad", "block", "stab", "arpeggiated_stab")


def _voice_lead(prev: List[int], current: List[int]) -> List[int]:
    """Octave-shift ``current`` so its root sits closest to ``prev``'s root."""
    if not prev:
        return current
    target = prev[0]
    root = current[0]
    while root - target > 6:
        current = [n - 12 for n in current]
        root -= 12
    while target - root > 6:
        current = [n + 12 for n in current]
        root += 12
    return current


def generate_chords(
    chords: List[ChordEvent],
    bars: int,
    *,
    beats_per_bar: int = 4,
    chord_beats: float | None = None,
    style: str = "pad",
    velocity: int = 80,
    rng: random.Random | None = None,
) -> List[Note]:
    """Render the progression as pads / stabs across ``bars`` bars."""
    if style not in CHORD_STYLES:
        raise ValueError(f"Unknown chord style {style!r}. Options: {CHORD_STYLES}")
    rng = rng or random.Random()
    chord_beats = chord_beats or beats_per_bar
    total_beats = bars * beats_per_bar

    notes: List[Note] = []
    prev_voicing: List[int] = []
    slot = 0
    t = 0.0
    while t < total_beats - 1e-6:
        chord = chords[slot % len(chords)]
        voicing = _voice_lead(prev_voicing, list(chord.notes))
        prev_voicing = voicing
        span = min(chord_beats, total_beats - t)
        notes.extend(_chord_slot(style, voicing, t, span, velocity, rng))
        t += chord_beats
        slot += 1
    return notes


def _chord_slot(style, voicing, start, span, velocity, rng) -> List[Note]:
    notes: List[Note] = []

    if style in ("pad", "block"):
        dur = span if style == "pad" else span * 0.95
        for p in voicing:
            notes.append(Note(p, start, dur, _hum(velocity, rng)))

    elif style == "stab":
        # Short chord hits on the off-beats -- the house/disco "stab".
        beat = 0.5
        while beat < span - 1e-6:
            for p in voicing:
                notes.append(Note(p, start + beat, 0.22, _hum(velocity, rng)))
            beat += 1.0

    elif style == "arpeggiated_stab":
        # Quick upward roll, then let it ring for the bar.
        for i, p in enumerate(sorted(voicing)):
            notes.append(Note(p, start + i * 0.05, span - i * 0.05, _hum(velocity, rng)))

    return notes


def _hum(velocity: int, rng: random.Random) -> int:
    return max(1, min(127, int(velocity * rng.uniform(0.9, 1.0))))
