"""The arranger: turn a genre + key into a complete, sectioned :class:`Song`.

It picks a chord progression, lays out song sections (intro / build / main /
breakdown / outro) and runs the right generators for the tracks that are active
in each section. A ``seed`` makes the whole thing reproducible.
"""

from __future__ import annotations

import math
import random
from typing import List, Optional, Set, Tuple

from . import theory
from .genres import Genre, get_genre
from .generators import (
    generate_arp,
    generate_bass,
    generate_chords,
    generate_drums,
    generate_melody,
)
from .song import GM_DRUM_CHANNEL, Note, Song, Track

_FULL = {"drums", "bass", "chords", "melody", "arp"}

# Song structure as (label, active tracks, relative weight, velocity intensity).
# Bars are distributed across these by weight, so every song -- short or long --
# always reaches a full-instrumentation "main" section.
_LAYOUT: List[Tuple[str, Set[str], int, float]] = [
    ("intro",     {"chords", "arp"},              1, 0.85),
    ("build",     {"drums", "chords", "arp"},     1, 0.90),
    ("main",      _FULL,                          2, 1.00),
    ("breakdown", {"chords", "melody", "arp"},    1, 0.80),
    ("main",      _FULL,                          2, 1.00),
    ("outro",     {"drums", "bass", "chords"},    1, 0.85),
]


def _largest_remainder(total: int, weights: List[int]) -> List[int]:
    """Split ``total`` into integers proportional to ``weights`` (each >= 1)."""
    tw = sum(weights)
    raw = [total * w / tw for w in weights]
    alloc = [max(1, int(math.floor(x))) for x in raw]
    diff = total - sum(alloc)
    order = sorted(range(len(raw)), key=lambda i: raw[i] - math.floor(raw[i]), reverse=True)
    i = 0
    while diff > 0:  # hand out the leftover bars to the biggest remainders
        alloc[order[i % len(order)]] += 1
        diff -= 1
        i += 1
    while diff < 0:  # claw bars back from sections that can spare one
        candidates = sorted((j for j in range(len(alloc)) if alloc[j] > 1),
                            key=lambda j: raw[j] - math.floor(raw[j]))
        alloc[candidates[0]] -= 1
        diff += 1
    return alloc


def _section_plan(total_bars: int) -> List[Tuple[str, int, Set[str], float]]:
    """Lay out sections summing to ``total_bars`` bars."""
    if total_bars < len(_LAYOUT):
        return [("main", total_bars, _FULL, 1.0)]
    bars = _largest_remainder(total_bars, [w for *_, w, _ in _LAYOUT])
    return [(label, n, active, intensity)
            for (label, active, _, intensity), n in zip(_LAYOUT, bars)]


def _shift(notes: List[Note], beats: float, intensity: float) -> List[Note]:
    return [Note(n.pitch, n.start + beats, n.duration,
                 max(1, min(127, int(n.velocity * intensity)))) for n in notes]


def compose(
    genre: str = "house",
    key: str = "A",
    *,
    scale: Optional[str] = None,
    tempo: Optional[float] = None,
    bars: int = 32,
    seed: Optional[int] = None,
    beats_per_bar: int = 4,
    beat_unit: int = 4,
    name: Optional[str] = None,
) -> Song:
    """Compose a full song.

    Args:
        genre: a preset name (see :func:`flautobot.genres.list_genres`).
        key: tonic such as ``"A"``, ``"F#"`` or ``"Eb"``.
        scale: override the genre's default scale (e.g. ``"minor"``).
        tempo: override the genre's BPM.
        bars: total length in bars.
        seed: seed for reproducible generation.
    """
    rng = random.Random(seed)
    g: Genre = get_genre(genre)
    scale_name = scale or g.scale
    root_pc = theory.parse_root(key)
    bpm = tempo or g.tempo

    degrees = rng.choice(g.progressions)
    chords = theory.progression(root_pc, scale_name, degrees, g.sevenths, g.chord_octave)

    song = Song(
        name=name or f"{g.name.title()} in {key} {scale_name}",
        tempo=bpm, beats_per_bar=beats_per_bar, beat_unit=beat_unit,
    )

    # One track per lane, created lazily so we only emit lanes that play.
    tracks = {
        "drums": Track("Drums", program=0, channel=GM_DRUM_CHANNEL, is_drum=True),
        "bass": Track("Bass", program=g.programs["bass"]),
        "chords": Track("Chords", program=g.programs["chords"]),
        "melody": Track("Melody", program=g.programs["melody"]),
        "arp": Track("Arp", program=g.programs["arp"]),
    }
    enabled = {
        "drums": g.use_drums, "bass": g.use_bass, "chords": g.use_chords,
        "melody": g.use_melody, "arp": g.use_arp,
    }

    cursor = 0  # bars elapsed
    for _, sec_bars, active, intensity in _section_plan(bars):
        offset = cursor * beats_per_bar
        live = {k for k in active if enabled.get(k)}

        if "drums" in live:
            n = generate_drums(g.drum_style, sec_bars, beats_per_bar=beats_per_bar,
                               swing=g.swing, fill_every=g.fill_every, rng=rng)
            tracks["drums"].extend(_shift(n, offset, intensity))
        if "bass" in live:
            n = generate_bass(chords, sec_bars, beats_per_bar=beats_per_bar,
                              style=g.bass_style, rng=rng)
            tracks["bass"].extend(_shift(n, offset, intensity))
        if "chords" in live:
            n = generate_chords(chords, sec_bars, beats_per_bar=beats_per_bar,
                               style=g.chord_style, rng=rng)
            tracks["chords"].extend(_shift(n, offset, intensity))
        if "melody" in live:
            n = generate_melody(chords, sec_bars, beats_per_bar=beats_per_bar,
                               register=g.melody_register, density=g.melody_density, rng=rng)
            tracks["melody"].extend(_shift(n, offset, intensity))
        if "arp" in live:
            n = generate_arp(chords, sec_bars, beats_per_bar=beats_per_bar,
                            rate=g.arp_rate, octaves=g.arp_octaves, mode=g.arp_mode, rng=rng)
            tracks["arp"].extend(_shift(n, offset, intensity))
        cursor += sec_bars

    # Add lanes in a musical order, skipping any that never played.
    for key_ in ("drums", "bass", "chords", "arp", "melody"):
        if tracks[key_].notes:
            song.add_track(tracks[key_])
    return song
