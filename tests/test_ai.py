"""Tests for the AI director's deterministic parts (no network / API key needed).

The actual Claude call in ``AIDirector.plan`` is not exercised here; instead we
test the plan validation and the plan -> MIDI rendering bridge, plus the
``compose`` override path the director relies on.
"""

import json

import pytest

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
    for name in ("AIDirector", "Conversation", "SongPlan", "render_plan", "AIError"):
        assert hasattr(flautobot, name)


# --- custom drum patterns ----------------------------------------------------

KICK_4 = "X...X...X...X..."  # 16 steps, four-on-the-floor


def test_parse_drum_pattern_validates():
    from flautobot.ai import _parse_drum_pattern

    out = _parse_drum_pattern([
        {"voice": "kick", "steps": KICK_4},          # ok
        {"voice": "snare", "steps": "....X......."},  # wrong length -> drop
        {"voice": "bogus", "steps": "x" * 16},        # unknown voice -> drop
        {"voice": "clap", "steps": "z" * 16},         # bad chars -> drop
        "not-a-dict",                                  # skipped
    ])
    assert out == {"kick": KICK_4}
    assert _parse_drum_pattern(None) == {}


def test_generate_drums_uses_custom_pattern():
    from flautobot.generators.drums import DRUM_MAP, generate_drums

    notes = generate_drums("house", 1, pattern={"kick": KICK_4}, humanize=0.0)
    assert {n.pitch for n in notes} == {DRUM_MAP["kick"]}
    assert len(notes) == 4


def test_render_plan_custom_drums_replaces_genre_groove():
    from flautobot.generators.drums import DRUM_MAP

    plan = SongPlan.from_response({
        "genre": "house", "key": "C", "bars": 8, "tracks": ["drums"],
        "drum_pattern": [{"voice": "kick", "steps": KICK_4}],
    })
    assert plan.drum_pattern == {"kick": KICK_4}
    song = render_plan(plan, seed=1)
    drums = next(t for t in song.tracks if t.name == "Drums")
    pitches = {n.pitch for n in drums.notes}
    assert DRUM_MAP["kick"] in pitches
    assert DRUM_MAP["clap"] not in pitches      # genre's clap is gone -> custom won


# --- backends & conversation (no network) -----------------------------------

class _FakePlanner:
    """Stand-in backend that returns canned JSON and records the messages."""

    name = "fake"
    model = "fake-model"

    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.calls = []

    def complete(self, system, messages, schema):
        self.calls.append([dict(m) for m in messages])
        return self.payloads.pop(0)


def test_backend_selection_and_unknown_backend():
    from flautobot.ai import AIDirector, AIError, OllamaPlanner

    director = AIDirector(backend="ollama", model="llama3.1")  # no network at build
    assert director.planner.name == "ollama"
    assert isinstance(director.planner, OllamaPlanner)
    assert director.model == "llama3.1"
    with pytest.raises(AIError):
        AIDirector(backend="gpt-9000")


def test_conversation_accumulates_history_and_renders():
    from flautobot.ai import AIDirector

    p1 = json.dumps({"title": "Sunrise", "genre": "house", "key": "A", "bars": 16})
    p2 = json.dumps({"title": "Midnight", "genre": "techno", "key": "A",
                     "scale": "phrygian", "bars": 16})
    director = AIDirector(backend="ollama")
    director.planner = _FakePlanner([p1, p2])

    convo = director.conversation(seed=1)
    song1, plan1 = convo.send("uplifting house")
    assert plan1.genre == "house" and song1.note_count() > 0

    song2, plan2 = convo.send("make it darker techno")
    assert plan2.genre == "techno"
    # The refinement call sees the full prior turn plus the new instruction.
    roles = [m["role"] for m in director.planner.calls[-1]]
    assert roles == ["user", "assistant", "user"]


def test_director_salvages_json_wrapped_in_prose():
    from flautobot.ai import AIDirector

    director = AIDirector(backend="ollama")
    director.planner = _FakePlanner(
        ['Sure! Here is your plan:\n{"genre": "lofi", "key": "C"}\nEnjoy.'])
    convo = director.conversation()
    _, plan = convo.send("lofi please")
    assert plan.genre == "lofi"
