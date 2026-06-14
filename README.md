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

> 🤖 **Prefer plain English?** `flautobot ai "dark lofi beat at 72 bpm with a jazzy
> progression"` lets **Claude** design the song (key, progression, arrangement) and
> the engine render it. See [AI music director](#-ai-music-director-optional).

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
pip install -r requirements.txt      # mido (required) + python-rtmidi (live) + anthropic (ai)

# optional: install the `flautobot` command
pip install -e .
```

Requires Python 3.9+. Only `mido` is required. `python-rtmidi` is needed only for
**live** streaming and `anthropic` only for the **AI** director — skip either if you
don't use it (`pip install mido` covers MIDI export on its own).

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

# Or just describe what you want and let Claude design it (see "AI" below)
python -m flautobot ai "uplifting summer house in F# minor, 124 bpm"
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

## 🤖 AI music director (optional)

Describe a song in plain English and let **Claude** design it. The LLM does the
*reasoning and creation* — it interprets your brief and authors a concrete plan
(key, scale, tempo, an original chord progression, instrumentation — even its own
drum groove) — and the deterministic engine *renders* that plan to MIDI. You get
the creativity of an LLM with output that's always musically valid and reproducible
from a seed.

```bash
pip install anthropic                 # or: pip install -e ".[ai]"
export ANTHROPIC_API_KEY=sk-ant-...

python -m flautobot ai "dark, melancholic lofi beat around 72 bpm, jazzy chords"
python -m flautobot ai "energetic festival house in F# minor, big drop" --stems
python -m flautobot ai "spacey ambient, no drums, slow evolving pads" --plan-only
python -m flautobot ai "driving techno at 132 bpm" --play --virtual   # into FL Studio
```

It prints the plan — including *why* Claude made each choice — then renders MIDI:

```
Midnight Coast
  lofi | F# dorian | 72 BPM | 16 bars | progression 2-5-1-1
  tracks: drums, bass, chords, melody | swing 0.2 | 7ths True
  mood: nocturnal, wistful, warm
  why: A ii-V-i in F# dorian gives a jazzy, unresolved feel that suits a
       late-night lofi mood; sustained bass and swung drums keep it relaxed.
```

From Python:

```python
from flautobot.ai import AIDirector
from flautobot import write_midi

song, plan = AIDirector().compose("uplifting summer house in A minor, 124 bpm")
print(plan.explanation)
write_midi(song, "output/ai_track.mid")
```

Uses Claude (`claude-opus-4-8` by default; override with `--model`). The plan comes
back as **validated structured JSON**, so it always maps cleanly onto the engine —
out-of-range values are clamped, unknown genres fall back to sensible defaults. No
API key? Everything else in FL Auto Bot still works; the AI layer is purely additive.

### Refine it conversationally

Keep the context and adjust in plain English — each instruction updates the plan and
writes a new revision (`*_rev1.mid`, `*_rev2.mid`, …):

```bash
python -m flautobot ai "boom-bap hip hop in C minor" --chat
# refine> make it darker and add more swing
# refine> add an arp and drop the melody
# refine> (blank line to finish)
```

### Run fully offline (Ollama)

No API key, no cloud — use a local model via [Ollama](https://ollama.com):

```bash
ollama serve &                 # start the local server
ollama pull llama3.1           # any chat model works

python -m flautobot ai "lofi at 72 bpm" --backend ollama
python -m flautobot ai "hard techno" --backend ollama --model qwen2.5 --chat
```

The validation layer keeps even smaller local models reliable — anything off-spec is
clamped to a musical default. (`--backend ollama` needs no extra Python packages.)

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
├── ai.py            AI director: brief → Claude/Ollama → validated plan → render
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
pytest                 # 67 tests: theory, generators, arrangement, MIDI export, AI
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
