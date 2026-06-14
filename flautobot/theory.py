"""Music-theory primitives: notes, scales, chords and diatonic progressions.

Everything is expressed in MIDI note numbers (0-127) where 60 = C4 in the
standard scientific-pitch convention used by almost every tool, including
``mido``.

Note on FL Studio: FL Studio's piano roll *labels* MIDI note 60 as ``C5``
(it uses an octave offset of +1 for display only). The underlying MIDI
number is identical, so exported files line up perfectly -- only the on-screen
octave label differs. See the README for details.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Sequence

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
_NAME_TO_PC = {name: i for i, name in enumerate(NOTE_NAMES)}
# Common enharmonic spellings so users can type "Bb", "Eb", "Db"...
_NAME_TO_PC.update({"Db": 1, "Eb": 3, "Gb": 6, "Ab": 8, "Bb": 10})

# Scale formulas as semitone offsets from the root.
SCALES = {
    "major": [0, 2, 4, 5, 7, 9, 11],
    "minor": [0, 2, 3, 5, 7, 8, 10],            # natural minor / aeolian
    "harmonic_minor": [0, 2, 3, 5, 7, 8, 11],
    "melodic_minor": [0, 2, 3, 5, 7, 9, 11],
    "dorian": [0, 2, 3, 5, 7, 9, 10],
    "phrygian": [0, 1, 3, 5, 7, 8, 10],
    "lydian": [0, 2, 4, 6, 7, 9, 11],
    "mixolydian": [0, 2, 4, 5, 7, 9, 10],
    "locrian": [0, 1, 3, 5, 6, 8, 10],
    "major_pentatonic": [0, 2, 4, 7, 9],
    "minor_pentatonic": [0, 3, 5, 7, 10],
    "blues": [0, 3, 5, 6, 7, 10],
}

# Chord formulas as semitone offsets from the chord root.
CHORDS = {
    "maj": [0, 4, 7],
    "min": [0, 3, 7],
    "dim": [0, 3, 6],
    "aug": [0, 4, 8],
    "sus2": [0, 2, 7],
    "sus4": [0, 5, 7],
    "maj7": [0, 4, 7, 11],
    "min7": [0, 3, 7, 10],
    "dom7": [0, 4, 7, 10],
    "dim7": [0, 3, 6, 9],
    "min7b5": [0, 3, 6, 10],
    "add9": [0, 4, 7, 14],
    "min9": [0, 3, 7, 10, 14],
    "maj9": [0, 4, 7, 11, 14],
}


def name_to_number(name: str, octave: int) -> int:
    """Return the MIDI number for e.g. ``("C", 4) -> 60`` or ``("F#", 3)``."""
    pc = _NAME_TO_PC.get(name.strip().capitalize() if len(name) == 1 else name.strip())
    if pc is None:
        # Capitalise just the letter, keep the accidental (e.g. "bb" -> "Bb").
        key = name[0].upper() + name[1:]
        pc = _NAME_TO_PC.get(key)
    if pc is None:
        raise ValueError(f"Unknown note name: {name!r}")
    return 12 * (octave + 1) + pc


def number_to_name(number: int) -> str:
    """Return e.g. ``60 -> 'C4'`` (scientific pitch, 60 = C4)."""
    return f"{NOTE_NAMES[number % 12]}{number // 12 - 1}"


def parse_root(root: str) -> int:
    """Parse a root such as ``'C'``, ``'A'``, ``'F#4'`` or ``'Eb3'`` to a pitch class.

    A bare letter defaults to octave 4. The returned value is a *pitch class*
    (0-11); generators decide the actual octave they want.
    """
    root = root.strip()
    # Split a trailing octave digit (optionally negative) if present.
    i = len(root)
    while i > 0 and (root[i - 1].isdigit() or root[i - 1] == "-"):
        i -= 1
    name = root[:i] if i > 0 else root
    return name_to_number(name, 4) % 12


def scale_pitch_classes(root_pc: int, scale: str) -> List[int]:
    """Pitch classes (0-11) of ``scale`` starting on ``root_pc``."""
    if scale not in SCALES:
        raise ValueError(f"Unknown scale {scale!r}. Options: {sorted(SCALES)}")
    return [(root_pc + step) % 12 for step in SCALES[scale]]


def build_chord(root_midi: int, chord_type: str = "maj") -> List[int]:
    """Return the MIDI notes of ``chord_type`` rooted at ``root_midi``."""
    if chord_type not in CHORDS:
        raise ValueError(f"Unknown chord {chord_type!r}. Options: {sorted(CHORDS)}")
    return [root_midi + iv for iv in CHORDS[chord_type]]


def snap_to_scale(pitch: int, scale_pcs: Sequence[int]) -> int:
    """Snap ``pitch`` to the nearest member of ``scale_pcs`` (ties go up)."""
    for distance in range(0, 7):
        for delta in (distance, -distance):
            if (pitch + delta) % 12 in scale_pcs:
                return pitch + delta
    return pitch  # pragma: no cover - a non-empty scale always matches


def clamp_to_range(pitch: int, low: int = 0, high: int = 127) -> int:
    """Fold ``pitch`` by octaves until it lands within ``[low, high]``."""
    while pitch < low:
        pitch += 12
    while pitch > high:
        pitch -= 12
    return max(low, min(high, pitch))


@dataclass
class ChordEvent:
    """One chord in a progression, with everything generators need.

    ``notes`` are the voiced chord tones (mid register). ``root_pc`` and the
    full key ``scale_pcs`` let bass/melody generators stay in key.
    """

    degree: int
    quality: str
    root_pc: int
    notes: List[int]
    scale_pcs: List[int] = field(default_factory=list)

    @property
    def root_midi(self) -> int:
        return self.notes[0]

    def tones_pcs(self) -> List[int]:
        return sorted({n % 12 for n in self.notes})


def diatonic_chord(root_pc: int, scale: str, degree: int, sevenths: bool = False,
                   octave: int = 4) -> ChordEvent:
    """Build the diatonic chord on ``degree`` (1-7) by stacking scale thirds.

    Stacking thirds *within the scale* yields the correct chord quality
    automatically (e.g. degree ii of a major scale comes out minor), which is
    what keeps generated progressions sounding in-key.
    """
    pcs = SCALES[scale]
    n = len(pcs)
    idx = (degree - 1) % n
    octave_carry = (degree - 1) // n
    steps = [0, 2, 4, 6] if sevenths else [0, 2, 4]

    notes: List[int] = []
    base = 12 * (octave + 1) + root_pc + 12 * octave_carry
    for s in steps:
        scale_index = idx + s
        wraps = scale_index // n
        offset = pcs[scale_index % n] + 12 * wraps
        notes.append(base + offset)

    quality = _classify_triad([(p - notes[0]) % 12 for p in notes[:3]])
    if sevenths:
        quality += "7"
    return ChordEvent(
        degree=degree,
        quality=quality,
        root_pc=notes[0] % 12,
        notes=notes,
        scale_pcs=scale_pitch_classes(root_pc, scale),
    )


def _classify_triad(intervals: Sequence[int]) -> str:
    third, fifth = intervals[1], intervals[2]
    if third == 4 and fifth == 7:
        return "maj"
    if third == 3 and fifth == 7:
        return "min"
    if third == 3 and fifth == 6:
        return "dim"
    if third == 4 and fifth == 8:
        return "aug"
    return "?"


def progression(root_pc: int, scale: str, degrees: Sequence[int],
                sevenths: bool = False, octave: int = 4) -> List[ChordEvent]:
    """Turn scale ``degrees`` (e.g. ``[1, 5, 6, 4]``) into ``ChordEvent``s."""
    return [diatonic_chord(root_pc, scale, d, sevenths, octave) for d in degrees]
