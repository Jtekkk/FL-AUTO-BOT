"""Bassline generation that follows the chord progression."""

from __future__ import annotations

import random
from typing import List

from ..song import Note
from ..theory import ChordEvent, snap_to_scale

# Bass styles understood by :func:`generate_bass`.
BASS_STYLES = ("sustained", "offbeat", "eighths", "rolling", "walking", "808")


def _root_midi(chord: ChordEvent, octave: int) -> int:
    return 12 * (octave + 1) + chord.root_pc


def generate_bass(
    chords: List[ChordEvent],
    bars: int,
    *,
    beats_per_bar: int = 4,
    chord_beats: float | None = None,
    style: str = "offbeat",
    octave: int = 2,
    velocity: int = 100,
    rng: random.Random | None = None,
) -> List[Note]:
    """Render a bassline under ``chords`` for ``bars`` bars.

    The progression is tiled across the timeline, each chord lasting
    ``chord_beats`` (defaults to one bar).
    """
    if style not in BASS_STYLES:
        raise ValueError(f"Unknown bass style {style!r}. Options: {BASS_STYLES}")
    rng = rng or random.Random()
    chord_beats = chord_beats or beats_per_bar
    total_beats = bars * beats_per_bar

    notes: List[Note] = []
    slot = 0
    t = 0.0
    while t < total_beats - 1e-6:
        chord = chords[slot % len(chords)]
        root = _root_midi(chord, octave)
        span = min(chord_beats, total_beats - t)
        notes.extend(_bass_slot(style, chord, root, t, span, beats_per_bar, velocity, rng))
        t += chord_beats
        slot += 1
    return notes


def _bass_slot(style, chord, root, start, span, beats_per_bar, velocity, rng) -> List[Note]:
    notes: List[Note] = []

    if style == "sustained":
        notes.append(Note(root, start, span, velocity))

    elif style == "offbeat":
        # Classic house: short note on every off-beat ("and" of each beat).
        beat = 0.5
        while beat < span - 1e-6:
            notes.append(Note(root, start + beat, 0.45, _hum(velocity, rng)))
            beat += 1.0

    elif style == "eighths":
        step = 0.5
        n = int(round(span / step))
        for i in range(n):
            notes.append(Note(root, start + i * step, step * 0.9, _hum(velocity, rng)))

    elif style == "rolling":
        # Driving 16ths with the odd octave pop for movement.
        step = 0.25
        n = int(round(span / step))
        for i in range(n):
            pitch = root + (12 if i % 4 == 3 else 0)
            notes.append(Note(pitch, start + i * step, step * 0.9, _hum(velocity, rng)))

    elif style == "walking":
        # Step through chord tones, one per beat.
        tones = sorted(chord.notes)
        beat = 0.0
        i = 0
        while beat < span - 1e-6:
            pc = tones[i % len(tones)] % 12
            pitch = snap_to_scale(root + (pc - root % 12), chord.scale_pcs or [pc])
            notes.append(Note(pitch, start + beat, 0.95, _hum(velocity, rng)))
            beat += 1.0
            i += 1

    elif style == "808":
        # Long root with an occasional rhythmic restrike (trap flavour).
        notes.append(Note(root, start, span * rng.choice([1.0, 0.5, 0.75]),
                          _hum(velocity, rng)))
        if span >= beats_per_bar and rng.random() < 0.6:
            mid = start + span * 0.5
            notes.append(Note(root, mid, span * 0.5, _hum(velocity, rng)))

    return notes


def _hum(velocity: int, rng: random.Random) -> int:
    return max(1, min(127, int(velocity * rng.uniform(0.9, 1.0))))
