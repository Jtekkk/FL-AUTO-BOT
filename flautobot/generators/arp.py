"""Arpeggiator: turns each chord into a stream of single notes."""

from __future__ import annotations

import random
from typing import List

from ..song import Note
from ..theory import ChordEvent

ARP_MODES = ("up", "down", "updown", "random")


def _arp_sequence(chord_notes: List[int], octaves: int, mode: str,
                  rng: random.Random) -> List[int]:
    base = sorted(chord_notes)
    seq: List[int] = []
    for o in range(octaves):
        seq.extend(p + 12 * o for p in base)
    if mode == "down":
        seq = list(reversed(seq))
    elif mode == "updown":
        seq = seq + list(reversed(seq[1:-1])) if len(seq) > 2 else seq
    elif mode == "random":
        rng.shuffle(seq)
    return seq


def generate_arp(
    chords: List[ChordEvent],
    bars: int,
    *,
    beats_per_bar: int = 4,
    chord_beats: float | None = None,
    rate: float = 0.25,
    octaves: int = 2,
    mode: str = "up",
    gate: float = 0.9,
    velocity: int = 90,
    rng: random.Random | None = None,
) -> List[Note]:
    """Arpeggiate ``chords`` at ``rate`` beats per step for ``bars`` bars."""
    if mode not in ARP_MODES:
        raise ValueError(f"Unknown arp mode {mode!r}. Options: {ARP_MODES}")
    rng = rng or random.Random()
    chord_beats = chord_beats or beats_per_bar
    total_beats = bars * beats_per_bar

    notes: List[Note] = []
    slot = 0
    t = 0.0
    while t < total_beats - 1e-6:
        chord = chords[slot % len(chords)]
        seq = _arp_sequence(chord.notes, octaves, mode, rng)
        span = min(chord_beats, total_beats - t)
        steps = int(round(span / rate))
        for i in range(steps):
            pitch = seq[i % len(seq)]
            notes.append(Note(
                pitch=pitch,
                start=t + i * rate,
                duration=rate * gate,
                velocity=max(1, min(127, int(velocity * rng.uniform(0.9, 1.0)))),
            ))
        t += chord_beats
        slot += 1
    return notes
