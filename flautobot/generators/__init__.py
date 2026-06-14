"""Pattern generators: drums, bass, chords, melody and arpeggios.

Every generator returns a plain ``list[Note]`` positioned in beats, so callers
are free to drop the notes onto any :class:`~flautobot.song.Track`.
"""

from .drums import generate_drums, DRUM_STYLES, DRUM_MAP
from .bass import generate_bass
from .chords import generate_chords
from .melody import generate_melody
from .arp import generate_arp

__all__ = [
    "generate_drums",
    "generate_bass",
    "generate_chords",
    "generate_melody",
    "generate_arp",
    "DRUM_STYLES",
    "DRUM_MAP",
]
