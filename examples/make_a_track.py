"""Example: compose a few songs programmatically and export MIDI.

Run it with::

    python examples/make_a_track.py

It writes .mid files into ./output that you can drag into FL Studio.
"""

import pathlib
import sys

# Make the example runnable from a fresh clone without `pip install`.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from flautobot import compose, write_midi, write_stems

# 1) A simple one-liner: house track in A minor, reproducible via the seed.
song = compose(genre="house", key="A", bars=32, seed=7)
print(song.summary())
write_midi(song, "output/house_demo.mid")

# 2) Override the scale and tempo for a moody, slower take.
lofi = compose(genre="lofi", key="F#", scale="dorian", tempo=72, bars=16, seed=3)
write_midi(lofi, "output/lofi_demo.mid")
write_stems(lofi, "output/lofi_demo_stems", "lofi_demo")  # one .mid per track

# 3) Batch a few ideas to audition quickly.
for genre in ("deep_house", "techno", "trap", "ambient"):
    s = compose(genre=genre, key="C", bars=16, seed=1)
    path = write_midi(s, f"output/idea_{genre}.mid")
    print(f"{genre:<12} -> {path}  ({s.note_count()} notes)")

print("\nDone. Drag any .mid from ./output onto the FL Studio playlist.")
