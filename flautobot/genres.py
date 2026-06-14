"""Genre presets.

Each :class:`Genre` bundles the tempo, scale, chord progressions, groove and
instrument choices that make a style recognisable. The arranger reads these to
decide which generators to run and how.

``program`` numbers are General MIDI patches (0-indexed). They give sensible
sounds out of the box; in FL Studio you'll usually swap them for your own
instruments per channel.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class Genre:
    name: str
    tempo: float
    scale: str
    progressions: List[List[int]]
    drum_style: str
    bass_style: str = "offbeat"
    chord_style: str = "pad"
    swing: float = 0.0
    sevenths: bool = False
    chord_octave: int = 4
    fill_every: int = 4

    use_drums: bool = True
    use_bass: bool = True
    use_chords: bool = True
    use_melody: bool = True
    use_arp: bool = False

    melody_density: float = 0.6
    melody_register: Tuple[int, int] = (60, 84)

    arp_mode: str = "up"
    arp_rate: float = 0.25
    arp_octaves: int = 2

    # GM programs per instrument lane.
    programs: Dict[str, int] = field(default_factory=lambda: {
        "bass": 38, "chords": 4, "melody": 81, "arp": 80,
    })


GENRES: Dict[str, Genre] = {
    "house": Genre(
        name="house", tempo=124, scale="minor",
        progressions=[[1, 6, 4, 5], [6, 4, 1, 5], [1, 4, 5, 1], [1, 5, 6, 4]],
        drum_style="house", bass_style="offbeat", chord_style="stab",
        swing=0.08, sevenths=True, melody_density=0.5, use_melody=True,
        programs={"bass": 38, "chords": 5, "melody": 81, "arp": 80},
    ),
    "deep_house": Genre(
        name="deep_house", tempo=122, scale="dorian",
        progressions=[[1, 4, 1, 5], [1, 6, 2, 5], [2, 5, 1, 1]],
        drum_style="deep_house", bass_style="offbeat", chord_style="pad",
        swing=0.12, sevenths=True, use_melody=False, use_arp=True,
        arp_mode="up", arp_rate=0.25, arp_octaves=2,
        programs={"bass": 39, "chords": 89, "melody": 81, "arp": 80},
    ),
    "techno": Genre(
        name="techno", tempo=132, scale="phrygian",
        progressions=[[1, 1, 2, 1], [1, 6, 1, 7], [1, 1, 1, 1]],
        drum_style="techno", bass_style="rolling", chord_style="stab",
        swing=0.0, sevenths=False, use_melody=False, use_arp=True,
        chord_octave=3, arp_mode="updown", arp_rate=0.25, arp_octaves=2,
        programs={"bass": 38, "chords": 81, "melody": 81, "arp": 81},
    ),
    "lofi": Genre(
        name="lofi", tempo=78, scale="dorian",
        progressions=[[2, 5, 1, 1], [1, 4, 2, 5], [6, 2, 5, 1]],
        drum_style="lofi", bass_style="sustained", chord_style="block",
        swing=0.22, sevenths=True, melody_density=0.4,
        melody_register=(60, 79),
        programs={"bass": 33, "chords": 4, "melody": 0, "arp": 4},
    ),
    "boombap": Genre(
        name="boombap", tempo=90, scale="minor",
        progressions=[[1, 4, 1, 5], [1, 6, 4, 5], [1, 7, 6, 5]],
        drum_style="boombap", bass_style="sustained", chord_style="block",
        swing=0.16, sevenths=True, melody_density=0.45,
        programs={"bass": 33, "chords": 4, "melody": 0, "arp": 4},
    ),
    "trap": Genre(
        name="trap", tempo=140, scale="minor",
        progressions=[[1, 1, 6, 6], [1, 6, 7, 7], [1, 1, 4, 5]],
        drum_style="trap", bass_style="808", chord_style="arpeggiated_stab",
        swing=0.0, sevenths=False, chord_octave=4, melody_density=0.35,
        melody_register=(67, 91),
        programs={"bass": 38, "chords": 89, "melody": 81, "arp": 80},
    ),
    "dnb": Genre(
        name="dnb", tempo=174, scale="minor",
        progressions=[[1, 6, 4, 5], [1, 5, 6, 4], [6, 4, 1, 5]],
        drum_style="dnb", bass_style="rolling", chord_style="pad",
        swing=0.0, sevenths=True, use_melody=True, melody_density=0.4,
        programs={"bass": 38, "chords": 89, "melody": 81, "arp": 80},
    ),
    "ambient": Genre(
        name="ambient", tempo=70, scale="lydian",
        progressions=[[1, 4, 6, 5], [1, 5, 4, 1], [1, 2, 4, 1]],
        drum_style="ambient", bass_style="sustained", chord_style="pad",
        swing=0.0, sevenths=True, use_melody=True, use_arp=True,
        melody_density=0.3, fill_every=0, melody_register=(67, 91),
        arp_mode="updown", arp_rate=0.5, arp_octaves=2,
        programs={"bass": 89, "chords": 88, "melody": 73, "arp": 88},
    ),
    "synthwave": Genre(
        name="synthwave", tempo=100, scale="minor",
        progressions=[[1, 6, 4, 5], [6, 4, 1, 5], [1, 7, 6, 4]],
        drum_style="house", bass_style="eighths", chord_style="pad",
        swing=0.0, sevenths=True, use_arp=True, melody_density=0.5,
        arp_mode="up", arp_rate=0.25, arp_octaves=2,
        programs={"bass": 39, "chords": 81, "melody": 81, "arp": 80},
    ),
}


def get_genre(name: str) -> Genre:
    key = name.strip().lower().replace("-", "_").replace(" ", "_")
    if key not in GENRES:
        raise ValueError(f"Unknown genre {name!r}. Options: {list_genres()}")
    return GENRES[key]


def list_genres() -> List[str]:
    return sorted(GENRES)
