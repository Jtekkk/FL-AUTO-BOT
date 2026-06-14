"""The song data model: Note, Track and Song.

Time is measured in **beats** (quarter notes) as floats throughout the
generators, which keeps the music code readable and tempo-independent. The
MIDI exporter converts beats to ticks at the very end.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

GM_DRUM_CHANNEL = 9  # MIDI channel 10 (0-indexed) is percussion by convention.


@dataclass
class Note:
    """A single note event, positioned in beats."""

    pitch: int          # MIDI note number 0-127
    start: float        # beat offset from the start of the track
    duration: float     # length in beats
    velocity: int = 96  # 1-127

    @property
    def end(self) -> float:
        return self.start + self.duration

    def transposed(self, semitones: int) -> "Note":
        return Note(self.pitch + semitones, self.start, self.duration, self.velocity)


@dataclass
class Track:
    """A named lane of notes bound to a MIDI channel / instrument.

    ``program`` is a General MIDI patch number (0-127). For drum tracks set
    ``is_drum=True`` and the exporter routes them to the percussion channel so
    the pitches map to FL Studio / GM drum sounds.
    """

    name: str
    notes: List[Note] = field(default_factory=list)
    program: int = 0
    channel: Optional[int] = None
    is_drum: bool = False

    def add(self, note: Note) -> None:
        self.notes.append(note)

    def extend(self, notes: List[Note]) -> None:
        self.notes.extend(notes)

    def shifted(self, beats: float) -> List[Note]:
        """Return copies of every note moved later by ``beats``."""
        return [Note(n.pitch, n.start + beats, n.duration, n.velocity) for n in self.notes]

    @property
    def length_beats(self) -> float:
        return max((n.end for n in self.notes), default=0.0)


@dataclass
class Song:
    """A complete arrangement: tempo, meter and a set of tracks."""

    name: str = "FL Auto Bot Track"
    tempo: float = 120.0                 # BPM
    beats_per_bar: int = 4               # numerator of the time signature
    beat_unit: int = 4                   # denominator (4 = quarter note)
    ppq: int = 480                       # ticks per quarter note for export
    tracks: List[Track] = field(default_factory=list)

    def add_track(self, track: Track) -> Track:
        self.tracks.append(track)
        return track

    @property
    def length_beats(self) -> float:
        return max((t.length_beats for t in self.tracks), default=0.0)

    @property
    def length_bars(self) -> float:
        return self.length_beats / self.beats_per_bar

    def note_count(self) -> int:
        return sum(len(t.notes) for t in self.tracks)

    def summary(self) -> str:
        lines = [
            f"{self.name}  |  {self.tempo:g} BPM  |  "
            f"{self.beats_per_bar}/{self.beat_unit}  |  "
            f"{self.length_bars:g} bars  |  {self.note_count()} notes",
        ]
        for t in self.tracks:
            kind = "drums" if t.is_drum else f"prog {t.program}"
            lines.append(f"  - {t.name:<14} {len(t.notes):>4} notes  ({kind})")
        return "\n".join(lines)
