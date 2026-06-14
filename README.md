# 🎹 FL Auto Bot

A bot that **algorithmically composes complete songs** and gets them into
**FL Studio** running locally on your machine.

It builds full arrangements — drums, bass, chords, melody and arps — using real
music theory (scales, diatonic chord progressions, voice-leading, grooves), then
hands the result to FL Studio three different ways:

| Path | What it does | Setup |
|------|--------------|-------|
| 🎼 **MIDI export** | Writes `.mid` files you drag onto the playlist / piano roll | None — works out of the box |
| 🔴 **Live MIDI** | Streams the song into FL Studio in real time over a virtual MIDI port | A virtual MIDI port (loopMIDI / IAC) |
| 🧩 **Piano Roll script** | Runs the generator *inside* FL Studio's piano roll | Copy one file into FL's scripts folder |

FL Studio is the instrument and renderer; the bot is the composer. This is a
standard producer workflow — generate ideas, then mix/master/render them in FL.

---

## Why MIDI?

FL Studio has no public API to author a finished `.flp` from the outside, but it
speaks MIDI fluently. Generating MIDI (and streaming it live) is the robust,
DAW-native way to drive FL Studio — your generated parts land on real FL
channels so you keep full control of sounds, mixing and rendering.

---

## Install

```bash
git clone <this repo> && cd FL-AUTO-BOT
pip install -r requirements.txt      # mido (required) + python-rtmidi (live mode)

# optional: install the `flautobot` command
pip install -e .
```

Requires Python 3.9+. `python-rtmidi` is only needed for **live** streaming; if
you just export `.mid` files you can skip it.

---

## Quick start

```bash
# List the available styles
python -m flautobot genres

# Compose a 32-bar house track in A minor and export a .mid
python -m flautobot generate -g house -k A -b 32

# A lofi idea in F# minor, one .mid per track (stems), reproducible via seed
python -m flautobot generate -g lofi -k F#m -b 16 --stems --seed 42

# Stream a techno track straight into FL Studio (see "Live" below)
python -m flautobot live -g techno -k E --virtual
```

Output lands in `./output/`. Every run prints its `seed` so you can reproduce or
tweak a result you liked: `--seed 42`.

If you ran `pip install -e .`, use `flautobot ...` instead of
`python -m flautobot ...`.

### From Python

```python
from flautobot import compose, write_midi

song = compose(genre="house", key="A", scale="minor", bars=32, seed=7)
print(song.summary())
write_midi(song, "output/my_track.mid")
```

---

## Getting it into FL Studio

### 1. MIDI file (simplest)

1. `python -m flautobot generate -g house -k A -b 32`
2. Drag `output/*.mid` onto the FL Studio **playlist**. Choose
   **"Split by channel"** so each part (drums, bass, chords, melody) lands on its
   own pattern/channel.
3. Or use `--stems` and drag each `*_stems/*.mid` onto an individual channel's
   piano roll.
4. Assign instruments, mix, and render. Drums use the **General MIDI drum map**
   (kick = C1/36, snare = D1/38, …) so they map cleanly to FPC / drum racks.

### 2. Live MIDI streaming

Play the generated song into FL Studio in real time — great for recording takes
or auditioning while you tweak a synth.

First create a **virtual MIDI port**:

- **Windows:** install [loopMIDI](https://www.tobias-erichsen.de/software/loopmidi.html),
  add a port. In FL Studio: *Options → MIDI settings → Input* → enable the
  loopMIDI port (turn on "Enable"). Then:
  ```bash
  python -m flautobot ports                       # find the port name
  python -m flautobot live -g house --port "loopMIDI Port"
  ```
- **macOS:** open *Audio MIDI Setup → MIDI Studio*, double-click **IAC Driver**,
  tick "Device is online". Enable it in FL Studio's MIDI input settings. Then:
  ```bash
  python -m flautobot live -g house --virtual     # or --port "IAC Driver Bus 1"
  ```
- **Linux:** `python -m flautobot live -g house --virtual` creates a port you can
  wire up with `aconnect` / a patchbay.

In FL Studio, set an instrument channel to receive from the port (and arm record
if you want to capture it). Add `--loop` to repeat until you press `Ctrl+C`.

### 3. Native Piano Roll script

Generate notes **inside** FL Studio's piano roll:

1. Copy `fl_studio_scripts/piano_roll_FLAutoBot.py` to:
   - Windows: `Documents\Image-Line\FL Studio\Settings\Piano roll scripts\`
   - macOS: `~/Documents/Image-Line/FL Studio/Settings/Piano roll scripts/`
2. In the piano roll, open the menu (top-left arrow) → **Scripting → FL Auto Bot**.
3. Pick key, scale, progression and bars, then **Apply**. Chords (+ optional
   bass and melody) appear in the piano roll, colour-coded.

Requires FL Studio 20.9.3+ (piano roll scripting).

---

## Styles

`drums`, `bass`, `chords`, `melody` and `arp` lanes are mixed per genre:

| Genre | Tempo | Feel |
|-------|-------|------|
| `house` | 124 | Four-on-the-floor, offbeat bass, stabs |
| `deep_house` | 122 | Warm pads, shuffled groove, arps |
| `techno` | 132 | Driving, dark, phrygian, rolling bass |
| `lofi` | 78 | Swung, jazzy 7ths, lazy drums |
| `boombap` | 90 | Classic hip-hop swing |
| `trap` | 140 | 808s, hi-hat rolls, sparse keys |
| `dnb` | 174 | Breakbeat, fast rolling bass |
| `ambient` | 70 | Sparse, lydian pads, slow arps |
| `synthwave` | 100 | Retro arps and pads |

Override anything from the CLI: `--key`, `--scale`, `--tempo`, `--bars`,
`--seed`, `--name`. Scales include `major`, `minor`, `dorian`, `phrygian`,
`lydian`, `mixolydian`, pentatonics and `blues`.

---

## How it works

```
flautobot/
├── theory.py        notes, scales, chords, diatonic progressions
├── song.py          Note / Track / Song data model (time measured in beats)
├── genres.py        style presets (tempo, scale, progressions, groove, sounds)
├── arrange.py       the "composer": picks a progression, lays out
│                    intro/build/main/breakdown/outro, runs the generators
├── generators/
│   ├── drums.py     16-step groove patterns + swing + humanise + fills
│   ├── bass.py      root-following basslines (offbeat, rolling, 808, walking…)
│   ├── chords.py    pads / stabs with simple voice-leading
│   ├── melody.py    chord-tone-anchored, stepwise, motif-based melodies
│   └── arp.py       up / down / updown / random arpeggios
├── midi_export.py   Song → Standard MIDI File(s) via mido
├── live.py          real-time MIDI streaming into FL Studio (python-rtmidi)
└── cli.py           the `flautobot` command
```

A `seed` makes every part of the generation reproducible.

> **Octave note:** the bot uses standard MIDI numbering (middle C = C4 = 60).
> FL Studio *labels* note 60 as `C5` (a display-only offset). The actual pitches
> line up perfectly — only the on-screen octave label differs by one.

---

## Develop

```bash
pip install -r requirements.txt pytest
pytest                 # 52 tests: theory, generators, arrangement, MIDI export
python examples/make_a_track.py
```

---

## Roadmap

- Velocity/automation humanisation curves and fills per section
- More genres (drill, garage, afrobeat) and song-structure templates
- Optional `.flp` project export
- A small web UI

## License

MIT — see [LICENSE](LICENSE).
