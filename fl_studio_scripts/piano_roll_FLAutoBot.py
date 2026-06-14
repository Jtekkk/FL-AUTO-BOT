"""FL Auto Bot -- FL Studio Piano Roll script (native integration).

Run the song generator *inside* FL Studio: it writes a chord progression
(optionally bass + melody) straight into the piano roll you're editing.

INSTALL
    Copy this file to:
      Windows: Documents\\Image-Line\\FL Studio\\Settings\\Piano roll scripts\\
      macOS:   ~/Documents/Image-Line/FL Studio/Settings/Piano roll scripts/
    In FL Studio's piano roll, open the menu (the small arrow, top-left) ->
    Scripting -> "piano_roll_FLAutoBot", set the options and click Apply.

Requires FL Studio 20.9.3+ (piano roll scripting). This script is intentionally
self-contained -- FL's embedded Python can't import the flautobot package -- so
it carries its own small copy of the music-theory helpers.
"""

import flpianoroll as flp
import random

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

SCALES = {
    "minor":   [0, 2, 3, 5, 7, 8, 10],
    "major":   [0, 2, 4, 5, 7, 9, 11],
    "dorian":  [0, 2, 3, 5, 7, 9, 10],
    "phrygian": [0, 1, 3, 5, 7, 8, 10],
    "lydian":  [0, 2, 4, 6, 7, 9, 11],
    "mixolydian": [0, 2, 4, 5, 7, 9, 10],
}
SCALE_NAMES = list(SCALES)

# Progressions as scale degrees (1-based).
PROGRESSIONS = {
    "I-V-vi-IV":   [1, 5, 6, 4],
    "i-VI-III-VII": [1, 6, 3, 7],
    "i-iv-v-i":    [1, 4, 5, 1],
    "vi-IV-I-V":   [6, 4, 1, 5],
    "ii-V-I-I":    [2, 5, 1, 1],
    "i-VII-VI-V":  [1, 7, 6, 5],
}
PROG_NAMES = list(PROGRESSIONS)


def diatonic_chord(root_pc, scale, degree, sevenths, octave=4):
    """Stack scale-thirds on a degree -> in-key chord (list of MIDI numbers)."""
    pcs = SCALES[scale]
    n = len(pcs)
    idx = (degree - 1) % n
    steps = [0, 2, 4, 6] if sevenths else [0, 2, 4]
    base = 12 * (octave + 1) + root_pc
    notes = []
    for s in steps:
        scale_index = idx + s
        notes.append(base + pcs[scale_index % n] + 12 * (scale_index // n))
    return notes


def _add_note(number, time_ticks, length_ticks, velocity=0.78, color=0):
    note = flp.Note()
    note.number = int(number)
    note.time = int(time_ticks)
    note.length = int(length_ticks)
    note.velocity = float(velocity)
    note.color = int(color)
    flp.score.addNote(note)


def createDialog():
    form = flp.ScriptDialog(
        "FL Auto Bot",
        "Generate a chord progression (and optional bass / melody) into the "
        "piano roll.",
    )
    form.AddInputCombo("Key", NOTE_NAMES, 9)          # default A
    form.AddInputCombo("Scale", SCALE_NAMES, 0)        # default minor
    form.AddInputCombo("Progression", PROG_NAMES, 0)   # default I-V-vi-IV
    form.AddInputKnobInt("Bars", 4, 1, 16)
    form.AddInputCheckbox("7th chords", True)
    form.AddInputCheckbox("Add bass", True)
    form.AddInputCheckbox("Add melody", True)
    form.AddInputCheckbox("Replace existing notes", True)
    form.AddInputKnobInt("Seed", 1, 0, 9999)
    return form


def apply(form):
    # Combos return the selected index; knobs/checkboxes return their value.
    key_pc = int(form.GetInputValue("Key"))
    scale = SCALE_NAMES[int(form.GetInputValue("Scale"))]
    degrees = PROGRESSIONS[PROG_NAMES[int(form.GetInputValue("Progression"))]]
    bars = int(form.GetInputValue("Bars"))
    sevenths = bool(form.GetInputValue("7th chords"))
    add_bass = bool(form.GetInputValue("Add bass"))
    add_melody = bool(form.GetInputValue("Add melody"))
    replace = bool(form.GetInputValue("Replace existing notes"))
    rng = random.Random(int(form.GetInputValue("Seed")))

    if replace:
        flp.score.clearNotes()

    ppq = flp.score.PPQ          # ticks per quarter note
    bar_ticks = ppq * 4          # assume 4/4
    scale_pcs = [(key_pc + s) % 12 for s in SCALES[scale]]

    for bar in range(bars):
        degree = degrees[bar % len(degrees)]
        chord = diatonic_chord(key_pc, scale, degree, sevenths, octave=4)
        start = bar * bar_ticks

        # Chord (held for the bar), colour 0.
        for pitch in chord:
            _add_note(pitch, start, bar_ticks - ppq // 8, velocity=0.70, color=0)

        # Bass: root two octaves down, colour 1.
        if add_bass:
            _add_note(chord[0] - 24, start, bar_ticks - ppq // 8, velocity=0.85, color=1)

        # Melody: four scale-tone steps anchored on chord tones, colour 2.
        if add_melody:
            tones = [p for p in range(72, 88) if p % 12 in scale_pcs]
            chord_pcs = {p % 12 for p in chord}
            idx = min(range(len(tones)), key=lambda i: abs(tones[i] - 80))
            for beat in range(4):
                if beat % 2 == 0:  # chord tone on strong beats
                    cands = [i for i, p in enumerate(tones) if p % 12 in chord_pcs]
                    if cands:
                        idx = min(cands, key=lambda i: abs(tones[i] - tones[idx]))
                else:              # stepwise otherwise
                    idx = max(0, min(len(tones) - 1, idx + rng.choice([-2, -1, 1, 2])))
                _add_note(tones[idx], start + beat * ppq, ppq - ppq // 8,
                          velocity=0.80, color=2)

    # Refresh the piano roll display.
    flp.score.markerCount  # touching the score finalises the edit
