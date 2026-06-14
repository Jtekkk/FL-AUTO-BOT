"""Export a :class:`~flautobot.song.Song` to Standard MIDI Files via ``mido``.

Two outputs are supported:

* :func:`write_midi` -- one multi-track ``.mid`` (drag it onto the FL Studio
  playlist and pick "Split by channel" to fan the parts out to channels).
* :func:`write_stems` -- one ``.mid`` per track, handy for dropping each part
  onto its own FL Studio channel/instrument.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Tuple

import mido
from mido import Message, MetaMessage, MidiFile, MidiTrack

from .song import GM_DRUM_CHANNEL, Song, Track


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, int(value)))


def _track_events(track: Track, ppq: int) -> List[Tuple[int, int, int, int]]:
    """Flatten a track to sorted ``(tick, is_note_on, pitch, velocity)`` events."""
    events: List[Tuple[int, int, int, int]] = []
    for n in track.notes:
        on = max(0, round(n.start * ppq))
        off = max(on + 1, round(n.end * ppq))  # never zero-length
        pitch = _clamp(n.pitch, 0, 127)
        vel = _clamp(n.velocity, 1, 127)
        events.append((on, 1, pitch, vel))
        events.append((off, 0, pitch, 0))
    # Note-offs (is_note_on=0) sort before note-ons at the same tick so a
    # repeated pitch doesn't get cut by its own previous release.
    events.sort(key=lambda e: (e[0], e[1]))
    return events


def _allocate_channels(song: Song) -> dict:
    """Map each track to a MIDI channel, reserving 9 for drums."""
    channels, nxt = {}, 0
    for t in song.tracks:
        if t.is_drum:
            channels[id(t)] = GM_DRUM_CHANNEL
            continue
        if nxt == GM_DRUM_CHANNEL:
            nxt += 1
        channels[id(t)] = nxt % 16
        nxt += 1
    return channels


def _conductor(song: Song) -> MidiTrack:
    meta = MidiTrack()
    meta.append(MetaMessage("track_name", name=song.name, time=0))
    meta.append(MetaMessage("set_tempo", tempo=mido.bpm2tempo(song.tempo), time=0))
    meta.append(MetaMessage("time_signature", numerator=song.beats_per_bar,
                            denominator=song.beat_unit, time=0))
    meta.append(MetaMessage("end_of_track", time=0))
    return meta


def _emit(mt: MidiTrack, track: Track, channel: int, ppq: int) -> None:
    if not track.is_drum:
        mt.append(Message("program_change", channel=channel, program=track.program, time=0))
    prev = 0
    for tick, is_on, pitch, vel in _track_events(track, ppq):
        delta = tick - prev
        prev = tick
        kind = "note_on" if is_on else "note_off"
        mt.append(Message(kind, channel=channel, note=pitch, velocity=vel, time=delta))
    mt.append(MetaMessage("end_of_track", time=0))


def song_to_midifile(song: Song) -> MidiFile:
    """Build a type-1 :class:`mido.MidiFile` from ``song``."""
    mid = MidiFile(type=1, ticks_per_beat=song.ppq)
    mid.tracks.append(_conductor(song))
    channels = _allocate_channels(song)
    for t in song.tracks:
        mt = MidiTrack()
        mt.append(MetaMessage("track_name", name=t.name, time=0))
        _emit(mt, t, channels[id(t)], song.ppq)
        mid.tracks.append(mt)
    return mid


def write_midi(song: Song, path: str | os.PathLike) -> str:
    """Write ``song`` to a single multi-track ``.mid`` and return the path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    song_to_midifile(song).save(path)
    return str(path)


def write_stems(song: Song, out_dir: str | os.PathLike, basename: str) -> List[str]:
    """Write one ``.mid`` per track (each carrying tempo). Return the paths."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    channels = _allocate_channels(song)
    paths: List[str] = []
    for i, t in enumerate(song.tracks):
        mid = MidiFile(type=0, ticks_per_beat=song.ppq)
        mt = MidiTrack()
        mt.append(MetaMessage("track_name", name=t.name, time=0))
        mt.append(MetaMessage("set_tempo", tempo=mido.bpm2tempo(song.tempo), time=0))
        mt.append(MetaMessage("time_signature", numerator=song.beats_per_bar,
                              denominator=song.beat_unit, time=0))
        _emit(mt, t, channels[id(t)], song.ppq)
        mid.tracks.append(mt)
        safe = t.name.lower().replace(" ", "_")
        p = out_dir / f"{basename}_{i + 1:02d}_{safe}.mid"
        mid.save(p)
        paths.append(str(p))
    return paths
