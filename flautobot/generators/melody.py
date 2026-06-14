"""Scale-aware melody generation.

Strategy for music that actually resolves:

* Strong beats snap to a **chord tone** of the currently sounding chord.
* Weak beats move by small **stepwise** intervals within the key.
* A single rhythmic *motif* is reused across the phrase for cohesion, with a
  fresh "response" rhythm at the end of every 4-bar group.
"""

from __future__ import annotations

import random
from typing import List, Tuple

from ..song import Note
from ..theory import ChordEvent


def _scale_tones(scale_pcs, low: int, high: int) -> List[int]:
    return [p for p in range(low, high + 1) if p % 12 in scale_pcs]


def _nearest_index(tones: List[int], pitch: int) -> int:
    return min(range(len(tones)), key=lambda i: abs(tones[i] - pitch))


def _rhythm(beats_per_bar: int, density: float, rng: random.Random) -> List[Tuple[float, float]]:
    """Return ``(start, duration)`` slots within one bar (rests are gaps)."""
    palette = [0.25, 0.5, 0.5, 0.75, 1.0]
    emit_prob = 0.45 + 0.5 * density
    slots: List[Tuple[float, float]] = []
    t = 0.0
    while t < beats_per_bar - 1e-6:
        remaining = beats_per_bar - t
        choices = [d for d in palette if d <= remaining + 1e-9] or [remaining]
        dur = rng.choice(choices)
        if t == 0.0 or rng.random() < emit_prob:
            slots.append((t, dur))
        t += dur
    return slots


def generate_melody(
    chords: List[ChordEvent],
    bars: int,
    *,
    beats_per_bar: int = 4,
    chord_beats: float | None = None,
    register: Tuple[int, int] = (60, 84),
    density: float = 0.6,
    velocity: int = 100,
    rng: random.Random | None = None,
) -> List[Note]:
    """Generate a melody over ``chords`` for ``bars`` bars."""
    rng = rng or random.Random()
    chord_beats = chord_beats or beats_per_bar
    low, high = register
    scale_pcs = chords[0].scale_pcs or chords[0].tones_pcs()
    tones = _scale_tones(scale_pcs, low, high)
    if not tones:
        return []

    motif = _rhythm(beats_per_bar, density, rng)
    idx = _nearest_index(tones, (low + high) // 2)
    notes: List[Note] = []

    for bar in range(bars):
        bar_start = bar * beats_per_bar
        # End of every 4-bar group gets a contrasting "answer" rhythm.
        rhythm = _rhythm(beats_per_bar, density, rng) if (bar + 1) % 4 == 0 else motif
        for start, dur in rhythm:
            abs_beat = bar_start + start
            chord = chords[int(abs_beat // chord_beats) % len(chords)]
            on_beat = abs(start - round(start)) < 1e-6

            if on_beat or start == 0.0:
                chord_pcs = chord.tones_pcs()
                candidates = [i for i, p in enumerate(tones) if p % 12 in chord_pcs]
                if candidates:
                    idx = min(candidates, key=lambda i: abs(tones[i] - tones[idx]))
            else:
                step = rng.choice([-2, -1, -1, 1, 1, 2])
                idx = max(0, min(len(tones) - 1, idx + step))

            notes.append(Note(
                pitch=tones[idx],
                start=abs_beat,
                duration=dur * 0.95,
                velocity=max(1, min(127, int(velocity * rng.uniform(0.85, 1.0)))),
            ))
    return notes
