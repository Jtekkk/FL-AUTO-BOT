"""Tests for the AI director's deterministic parts (no network / API key needed).

The actual Claude call in ``AIDirector.plan`` is not exercised here; instead we
test the plan validation and the plan -> MIDI rendering bridge, plus the
``compose`` override path the director relies on.
"""

import flautobot
from flautobot import compose
from flautobot.ai import SongPlan, render_plan


# --- compose() override path -------------------------------------------------

def test_compose_progression_override_changes_chords():
    a = compose(genre="house", key="C", bars=8, seed=1, progression=[1, 4, 5, 1])
    b = compose(genre="house", key="C", bars=8, seed=1, progression=[6, 4, 1, 5])
    ca = next(t for t in a.tracks if t.name == "Chords")
    cb = next(t for t in b.tracks if t.name == "Chords")
    assert [n.pitch for n in ca.notes] != [n.pitch for n in cb.notes]


def test_compose_tracks_override_limits_lanes():
    song = compose(genre="house", key="A", bars=16, seed=2, tracks=["drums", "bass"])
    names = {t.name for t in song.tracks}
    assert names == {"Drums", "Bass"}


def test_compose_style_overrides_apply():
    song = compose(genre="techno", key="E", bars=8, seed=4,
                   tracks=["bass"], bass_style="sustained")
    bass = next(t for t in song.tracks if t.name == "Bass")
    # Sustained bass = one long note per chord, far fewer than rolling 16ths.
    assert len(bass.notes) <= 8


# --- SongPlan validation / clamping -----------------------------------------

def test_plan_clamps_out_of_range_values():
    plan = SongPlan.from_response({
        "title": "Test", "genre": "nope", "key": "H#", "scale": "weird",
        "tempo": 9999, "bars": -5, "progression": [8, 0, 15],
        "tracks": ["foo", "drums", "bass"], "bass_style": "nope",
        "chord_style": "nope", "arp_mode": "nope", "swing": 5.0, "sevenths": "yes",
        "mood": "x", "explanation": "y",
    })
    assert plan.genre == "house"          # unknown genre -> default
    assert plan.key == "A"                # unparseable tonic -> default
    assert plan.scale == "minor"          # unknown scale -> default
    assert plan.tempo == 300              # clamped to max
    assert plan.bars == 1                 # clamped to min
    assert all(1 <= d <= 7 for d in plan.progression)
    assert plan.tracks == ["drums", "bass"]   # "foo" dropped
    assert plan.bass_style == "offbeat"
    assert plan.swing == 1.0


def test_plan_fills_empty_fields_with_sensible_defaults():
    plan = SongPlan.from_response({"genre": "lofi"})
    assert plan.progression                # never empty
    assert plan.tracks                     # never empty
    assert 40 <= plan.tempo <= 300


def test_plan_summary_mentions_title():
    plan = SongPlan.from_response({"title": "Midnight Drive", "genre": "synthwave"})
    assert "Midnight Drive" in plan.summary()


# --- render_plan bridge ------------------------------------------------------

def test_render_plan_produces_matching_song():
    plan = SongPlan.from_response({
        "title": "Rainy Day", "genre": "lofi", "key": "F#", "scale": "dorian",
        "tempo": 72, "bars": 16, "progression": [2, 5, 1, 1],
        "tracks": ["drums", "bass", "chords", "melody"],
        "bass_style": "sustained", "chord_style": "block", "arp_mode": "up",
        "swing": 0.2, "sevenths": True, "mood": "mellow", "explanation": "jazzy",
    })
    song = render_plan(plan, seed=7)
    assert song.tempo == 72
    assert song.name == "Rainy Day"
    assert {"Drums", "Bass", "Chords", "Melody"} == {t.name for t in song.tracks}
    assert song.note_count() > 0


def test_render_plan_is_reproducible_with_seed():
    plan = SongPlan.from_response({"genre": "house", "key": "A", "bars": 16})
    a = render_plan(plan, seed=3)
    b = render_plan(plan, seed=3)
    assert a.note_count() == b.note_count()


def test_package_exposes_ai_symbols():
    for name in ("AIDirector", "SongPlan", "render_plan", "AIError"):
        assert hasattr(flautobot, name)
