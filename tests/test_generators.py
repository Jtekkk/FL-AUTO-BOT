import random

import pytest

from flautobot import theory
from flautobot.generators import (
    DRUM_MAP,
    DRUM_STYLES,
    generate_arp,
    generate_bass,
    generate_chords,
    generate_drums,
    generate_melody,
)


def _chords():
    return theory.progression(9, "minor", [1, 6, 4, 5], sevenths=True)


def test_every_drum_pattern_is_16_steps():
    for style, voices in DRUM_STYLES.items():
        for voice, pattern in voices.items():
            assert len(pattern) == 16, f"{style}/{voice} is {len(pattern)} steps"
            assert voice in DRUM_MAP, f"{voice} missing from DRUM_MAP"
            assert set(pattern) <= set("Xxo."), f"bad chars in {style}/{voice}"


@pytest.mark.parametrize("style", list(DRUM_STYLES))
def test_generate_drums_pitches_and_timing(style):
    notes = generate_drums(style, 2, rng=random.Random(1))
    assert notes
    valid = set(DRUM_MAP.values())
    for n in notes:
        assert n.pitch in valid
        assert n.start >= 0
        assert 1 <= n.velocity <= 127


def test_drums_reproducible_with_seed():
    a = generate_drums("house", 4, rng=random.Random(99))
    b = generate_drums("house", 4, rng=random.Random(99))
    assert [(n.pitch, round(n.start, 6), n.velocity) for n in a] == \
           [(n.pitch, round(n.start, 6), n.velocity) for n in b]


def test_unknown_drum_style_raises():
    with pytest.raises(ValueError):
        generate_drums("does_not_exist", 1)


def test_bass_follows_roots_and_stays_low():
    chords = _chords()
    notes = generate_bass(chords, 4, style="offbeat", octave=2, rng=random.Random(3))
    assert notes
    roots = {c.root_pc for c in chords}
    # Every bass note's pitch class should be a chord root (offbeat plays roots).
    assert all(n.pitch % 12 in roots for n in notes)
    assert all(36 <= n.pitch <= 60 for n in notes)


@pytest.mark.parametrize("style", ["sustained", "offbeat", "eighths", "rolling", "walking", "808"])
def test_bass_styles_all_produce_notes(style):
    notes = generate_bass(_chords(), 4, style=style, rng=random.Random(5))
    assert notes
    assert all(1 <= n.velocity <= 127 for n in notes)


def test_chords_produce_multiple_simultaneous_notes():
    notes = generate_chords(_chords(), 4, style="pad", rng=random.Random(7))
    assert notes
    starts = [round(n.start, 4) for n in notes]
    # A pad stacks several notes at the same start time.
    assert any(starts.count(s) >= 3 for s in set(starts))


def test_melody_stays_in_scale_and_register():
    chords = _chords()
    notes = generate_melody(chords, 4, register=(60, 84), rng=random.Random(11))
    assert notes
    scale_pcs = set(chords[0].scale_pcs)
    for n in notes:
        assert n.pitch % 12 in scale_pcs
        assert 60 <= n.pitch <= 84


def test_arp_is_single_notes_at_rate():
    notes = generate_arp(_chords(), 2, rate=0.25, octaves=2, mode="up", rng=random.Random(13))
    assert notes
    # No two arp notes share a start (monophonic stream).
    starts = [round(n.start, 4) for n in notes]
    assert len(starts) == len(set(starts))


def test_generators_fill_requested_length():
    chords = _chords()
    notes = generate_bass(chords, 8, style="eighths", rng=random.Random(1))
    last_end = max(n.end for n in notes)
    assert last_end >= 8 * 4 - 1.0  # ~32 beats of content for 8 bars of 4/4
