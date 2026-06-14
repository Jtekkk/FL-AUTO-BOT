import pytest

from flautobot import compose, list_genres
from flautobot.arrange import _largest_remainder, _section_plan


@pytest.mark.parametrize("genre", list_genres())
def test_every_genre_composes(genre):
    song = compose(genre=genre, key="C", bars=16, seed=1)
    assert song.note_count() > 0
    assert len(song.tracks) >= 2
    assert song.length_bars <= 16.5


def test_compose_is_reproducible():
    a = compose(genre="house", key="A", bars=16, seed=42)
    b = compose(genre="house", key="A", bars=16, seed=42)
    assert a.note_count() == b.note_count()
    assert [t.name for t in a.tracks] == [t.name for t in b.tracks]
    an = [(n.pitch, round(n.start, 6)) for n in a.tracks[0].notes]
    bn = [(n.pitch, round(n.start, 6)) for n in b.tracks[0].notes]
    assert an == bn


def test_different_seeds_differ():
    a = compose(genre="house", key="A", bars=16, seed=1)
    b = compose(genre="house", key="A", bars=16, seed=2)
    assert a.note_count() != b.note_count() or \
        [n.pitch for n in a.tracks[-1].notes] != [n.pitch for n in b.tracks[-1].notes]


def test_full_length_song_has_bass_and_melody_lane():
    song = compose(genre="house", key="A", bars=16, seed=7)
    names = {t.name for t in song.tracks}
    assert {"Drums", "Bass", "Chords", "Melody"} <= names


def test_scale_override_changes_pitches():
    major = compose(genre="house", key="C", scale="major", bars=8, seed=3)
    minor = compose(genre="house", key="C", scale="minor", bars=8, seed=3)
    chords_major = next(t for t in major.tracks if t.name == "Chords")
    chords_minor = next(t for t in minor.tracks if t.name == "Chords")
    assert [n.pitch for n in chords_major.notes] != [n.pitch for n in chords_minor.notes]


def test_section_plan_sums_to_total():
    for total in (8, 16, 24, 32, 64, 7, 100):
        plan = _section_plan(total)
        assert sum(n for _, n, _, _ in plan) == total


def test_largest_remainder_exact_and_min_one():
    alloc = _largest_remainder(10, [1, 1, 2, 1, 2, 1])
    assert sum(alloc) == 10
    assert all(a >= 1 for a in alloc)


def test_unknown_genre_raises():
    with pytest.raises(ValueError):
        compose(genre="reggaeton_xyz", key="C")
