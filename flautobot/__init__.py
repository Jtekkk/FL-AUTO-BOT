"""FL Auto Bot -- algorithmically compose songs and get them into FL Studio.

Quick start::

    from flautobot import compose, write_midi

    song = compose(genre="house", key="A", bars=32, seed=7)
    write_midi(song, "output/track.mid")   # drag the .mid into FL Studio

See :mod:`flautobot.cli` for the command line, and :mod:`flautobot.live` to
stream straight into FL Studio over a virtual MIDI port.
"""

from __future__ import annotations

from .arrange import compose
from .genres import GENRES, get_genre, list_genres
from .midi_export import song_to_midifile, write_midi, write_stems
from .song import Note, Song, Track

__version__ = "0.1.0"

__all__ = [
    "compose",
    "Song",
    "Track",
    "Note",
    "write_midi",
    "write_stems",
    "song_to_midifile",
    "get_genre",
    "list_genres",
    "GENRES",
    "__version__",
]
