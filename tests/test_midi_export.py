import mido

from flautobot import compose, song_to_midifile, write_midi, write_stems
from flautobot.song import GM_DRUM_CHANNEL


def test_write_midi_is_valid(tmp_path):
    song = compose(genre="house", key="A", bars=16, seed=7)
    path = write_midi(song, tmp_path / "track.mid")
    mid = mido.MidiFile(path)
    assert mid.type == 1
    assert mid.ticks_per_beat == song.ppq
    # conductor track + one per song track
    assert len(mid.tracks) == len(song.tracks) + 1


def test_tempo_and_time_signature_present():
    song = compose(genre="techno", key="E", bars=8, seed=2)
    mid = song_to_midifile(song)
    metas = [m for tr in mid.tracks for m in tr]
    tempos = [m for m in metas if m.type == "set_tempo"]
    sigs = [m for m in metas if m.type == "time_signature"]
    assert tempos and abs(mido.tempo2bpm(tempos[0].tempo) - song.tempo) < 0.5
    assert sigs and sigs[0].numerator == song.beats_per_bar


def test_no_hanging_notes_and_drum_channel(tmp_path):
    song = compose(genre="trap", key="F", bars=16, seed=5)
    mid = mido.MidiFile(write_midi(song, tmp_path / "t.mid"))
    for tr in mid.tracks:
        ons = sum(1 for m in tr if m.type == "note_on" and m.velocity > 0)
        offs = sum(1 for m in tr if m.type == "note_off"
                   or (m.type == "note_on" and m.velocity == 0))
        assert ons == offs
    drum_channels = {m.channel for tr in mid.tracks for m in tr
                     if m.type == "note_on" and _is_drum_track(tr)}
    assert drum_channels == {GM_DRUM_CHANNEL}


def _is_drum_track(track):
    return any(m.type == "track_name" and m.name == "Drums" for m in track)


def test_write_stems_one_file_per_track(tmp_path):
    song = compose(genre="lofi", key="C", bars=16, seed=1)
    paths = write_stems(song, tmp_path / "stems", "lofi")
    assert len(paths) == len(song.tracks)
    for p in paths:
        mid = mido.MidiFile(p)          # must be readable
        assert any(m.type == "set_tempo" for tr in mid.tracks for m in tr)


def test_notes_never_zero_length(tmp_path):
    song = compose(genre="ambient", key="D", bars=8, seed=9)
    mid = mido.MidiFile(write_midi(song, tmp_path / "a.mid"))
    for tr in mid.tracks:
        t = 0
        on_at = {}
        for m in tr:
            t += m.time
            if m.type == "note_on" and m.velocity > 0:
                on_at[(m.channel, m.note)] = t
            elif m.type == "note_off" or (m.type == "note_on" and m.velocity == 0):
                start = on_at.get((m.channel, m.note))
                if start is not None:
                    assert t > start
