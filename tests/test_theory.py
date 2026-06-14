from flautobot import theory


def test_note_number_roundtrip():
    assert theory.name_to_number("C", 4) == 60
    assert theory.name_to_number("A", 4) == 69
    assert theory.name_to_number("F#", 3) == 54
    assert theory.number_to_name(60) == "C4"
    assert theory.number_to_name(69) == "A4"


def test_parse_root_accidentals_and_octaves():
    assert theory.parse_root("C") == 0
    assert theory.parse_root("A") == 9
    assert theory.parse_root("F#3") == 6
    assert theory.parse_root("Eb") == 3
    assert theory.parse_root("Bb2") == 10


def test_scale_pitch_classes():
    assert theory.scale_pitch_classes(0, "major") == [0, 2, 4, 5, 7, 9, 11]
    assert theory.scale_pitch_classes(9, "minor") == [9, 11, 0, 2, 4, 5, 7]


def test_build_chord():
    assert theory.build_chord(60, "maj") == [60, 64, 67]
    assert theory.build_chord(60, "min7") == [60, 63, 67, 70]


def test_diatonic_triads_have_correct_quality():
    # C major: I=maj, ii=min, iii=min, IV=maj, V=maj, vi=min, vii=dim
    qualities = [theory.diatonic_chord(0, "major", d).quality for d in range(1, 8)]
    assert qualities == ["maj", "min", "min", "maj", "maj", "min", "dim"]


def test_diatonic_chord_notes_in_key():
    chord = theory.diatonic_chord(0, "major", 1)
    assert chord.notes == [60, 64, 67]
    assert chord.root_pc == 0
    assert chord.scale_pcs == [0, 2, 4, 5, 7, 9, 11]


def test_sevenths_add_a_fourth_tone():
    chord = theory.diatonic_chord(0, "major", 5, sevenths=True)
    assert len(chord.notes) == 4
    assert chord.notes == [67, 71, 74, 77]  # G B D F


def test_progression_length_and_scale():
    prog = theory.progression(9, "minor", [1, 6, 4, 5])
    assert len(prog) == 4
    assert all(c.scale_pcs == theory.scale_pitch_classes(9, "minor") for c in prog)


def test_snap_to_scale_and_clamp():
    cmaj = theory.scale_pitch_classes(0, "major")
    assert theory.snap_to_scale(61, cmaj) in (60, 62)   # C# -> C or D
    assert 0 <= theory.clamp_to_range(200) <= 127
    assert theory.clamp_to_range(60, 48, 72) == 60
