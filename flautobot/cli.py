"""Command-line interface for FL Auto Bot.

Examples::

    flautobot genres                       # list available styles
    flautobot generate -g house -k A       # write a .mid you can drag into FL
    flautobot generate -g lofi -k F#m -b 16 --stems --seed 42
    flautobot ports                        # list MIDI ports for live mode
    flautobot live -g techno --virtual     # stream into FL Studio in real time
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path
from typing import Optional

from . import __version__
from .arrange import compose
from .genres import GENRES, list_genres


def _split_key_scale(key: str) -> tuple[str, Optional[str]]:
    """Allow shorthand like ``F#m`` (-> key F#, minor) or ``Cmaj``."""
    k = key.strip()
    for suffix, scale in (("min", "minor"), ("maj", "major"), ("m", "minor")):
        if k.lower().endswith(suffix) and len(k) > len(suffix):
            return k[: -len(suffix)], scale
    return k, None


def _add_gen_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("-g", "--genre", default="house",
                   help=f"style preset (default: house). Options: {', '.join(list_genres())}")
    p.add_argument("-k", "--key", default="A",
                   help="tonic, e.g. A, F#, Eb, or shorthand F#m / Cmaj (default: A)")
    p.add_argument("-s", "--scale", default=None,
                   help="override scale, e.g. minor, dorian, major_pentatonic")
    p.add_argument("-t", "--tempo", type=float, default=None, help="override BPM")
    p.add_argument("-b", "--bars", type=int, default=32, help="length in bars (default: 32)")
    p.add_argument("--seed", type=int, default=None, help="seed for reproducible output")
    p.add_argument("--name", default=None, help="song / file name")


def _compose_from_args(args) -> tuple:
    key, shorthand_scale = _split_key_scale(args.key)
    scale = args.scale or shorthand_scale
    seed = args.seed if args.seed is not None else random.randrange(1_000_000)
    song = compose(
        genre=args.genre, key=key, scale=scale, tempo=args.tempo,
        bars=args.bars, seed=seed, name=args.name,
    )
    return song, seed


def _cmd_genres(_args) -> int:
    print("Available genres:\n")
    for name in list_genres():
        g = GENRES[name]
        print(f"  {name:<12} {g.tempo:>5g} BPM   {g.scale:<16} "
              f"prog: {'/'.join(sorted(_active_lanes(g)))}")
    return 0


def _active_lanes(g) -> list:
    lanes = []
    if g.use_drums: lanes.append("drums")
    if g.use_bass: lanes.append("bass")
    if g.use_chords: lanes.append("chords")
    if g.use_melody: lanes.append("melody")
    if g.use_arp: lanes.append("arp")
    return lanes


def _cmd_generate(args) -> int:
    song, seed = _compose_from_args(args)
    from .midi_export import write_midi, write_stems

    if args.out:
        out_path = Path(args.out)
    else:
        safe = song.name.lower().replace(" ", "_").replace("#", "s")
        out_path = Path("output") / f"{safe}_seed{seed}.mid"

    write_midi(song, out_path)
    print(song.summary())
    print(f"\nseed: {seed}  (re-run with --seed {seed} to reproduce)")
    print(f"MIDI: {out_path}")

    if args.stems:
        stem_dir = out_path.parent / (out_path.stem + "_stems")
        paths = write_stems(song, stem_dir, out_path.stem)
        print(f"Stems ({len(paths)}): {stem_dir}/")
    print("\nDrag the .mid onto the FL Studio playlist (choose 'Split by channel'),"
          "\nor drop a stem onto a channel's piano roll.")
    return 0


def _cmd_live(args) -> int:
    from . import live

    if args.list_ports:
        try:
            ports = live.list_ports()
        except live.LiveError as exc:
            print(exc, file=sys.stderr)
            return 1
        print("MIDI output ports:")
        for name in ports or ["(none found)"]:
            print(f"  - {name}")
        return 0

    song, seed = _compose_from_args(args)
    print(song.summary())
    print(f"\nseed: {seed}")
    try:
        target = args.port or ("virtual port 'FL Auto Bot'" if args.virtual else "default port")
        print(f"Streaming to {target} ... (Ctrl+C to stop)")
        live.play_song(song, port_name=args.port, virtual=args.virtual, loop=args.loop)
    except live.LiveError as exc:
        print(f"\n{exc}", file=sys.stderr)
        return 1
    print("Done.")
    return 0


def _safe_name(text: str) -> str:
    s = text.lower().replace(" ", "_").replace("#", "s")
    return "".join(c for c in s if c.isalnum() or c in "_-") or "ai_track"


def _ai_out_path(args, plan, seed, rev=None) -> Path:
    if args.out:
        base = Path(args.out)
        return base.with_name(f"{base.stem}_rev{rev}{base.suffix}") if rev else base
    suffix = f"_rev{rev}" if rev else ""
    return Path("output") / f"{_safe_name(plan.title)}_seed{seed}{suffix}.mid"


def _write_ai(song, plan, args, seed, rev=None) -> Path:
    from .midi_export import write_midi, write_stems

    out_path = _ai_out_path(args, plan, seed, rev)
    write_midi(song, out_path)
    print(plan.summary())
    print("\n" + song.summary())
    print(f"MIDI: {out_path}")
    if args.stems:
        stem_dir = out_path.parent / (out_path.stem + "_stems")
        paths = write_stems(song, stem_dir, out_path.stem)
        print(f"Stems ({len(paths)}): {stem_dir}/")
    return out_path


def _play_song(args, song) -> int:
    from . import live

    try:
        target = args.port or ("virtual port" if args.virtual else "default port")
        print(f"\nStreaming to {target} ... (Ctrl+C to stop)")
        live.play_song(song, port_name=args.port, virtual=args.virtual)
    except live.LiveError as exc:
        print(f"\n{exc}", file=sys.stderr)
        return 1
    return 0


def _cmd_ai(args) -> int:
    from . import ai as ai_mod

    brief = " ".join(args.brief).strip()
    seed = args.seed if args.seed is not None else random.randrange(1_000_000)
    try:
        director = ai_mod.AIDirector(backend=args.backend, model=args.model, host=args.host)
    except ai_mod.AIError as exc:
        print(f"AI error: {exc}", file=sys.stderr)
        return 1
    print(f"[{director.planner.name}:{director.model}] designing: {brief!r}\n")

    if args.plan_only:
        try:
            print(director.plan(brief).summary())
        except ai_mod.AIError as exc:
            print(f"AI error: {exc}", file=sys.stderr)
            return 1
        return 0

    if args.chat:
        return _cmd_ai_chat(ai_mod, director, brief, seed, args)

    try:
        song, plan = director.compose(brief, seed=seed)
    except ai_mod.AIError as exc:
        print(f"AI error: {exc}", file=sys.stderr)
        return 1
    _write_ai(song, plan, args, seed)
    print(f"\nseed: {seed}  (re-run the render with --seed {seed})")
    return _play_song(args, song) if args.play else 0


def _cmd_ai_chat(ai_mod, director, brief, seed, args) -> int:
    convo = director.conversation(seed=seed)
    try:
        song, plan = convo.send(brief)
    except ai_mod.AIError as exc:
        print(f"AI error: {exc}", file=sys.stderr)
        return 1
    _write_ai(song, plan, args, seed, rev=0)
    print('\nRefine it (e.g. "make it darker", "add an arp", "faster").')
    print("Empty line or Ctrl-D to finish.\n")

    rev = 1
    while True:
        try:
            instruction = input("refine> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not instruction or instruction.lower() in {"done", "quit", "exit", "q"}:
            break
        try:
            song, plan = convo.send(instruction)
        except ai_mod.AIError as exc:
            print(f"AI error: {exc}", file=sys.stderr)
            continue
        print()
        _write_ai(song, plan, args, seed, rev=rev)
        rev += 1
    print(f"\nDone. seed: {seed}")
    return 0


def _cmd_ports(_args) -> int:
    from . import live

    try:
        ports = live.list_ports()
    except live.LiveError as exc:
        print(exc, file=sys.stderr)
        return 1
    print("MIDI output ports:")
    for name in ports or ["(none found -- create a loopMIDI / IAC virtual port)"]:
        print(f"  - {name}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="flautobot",
        description="Algorithmically compose songs and get them into FL Studio.",
    )
    parser.add_argument("--version", action="version", version=f"flautobot {__version__}")
    sub = parser.add_subparsers(dest="command")

    p_gen = sub.add_parser("generate", help="compose a song and export MIDI")
    _add_gen_args(p_gen)
    p_gen.add_argument("-o", "--out", default=None, help="output .mid path")
    p_gen.add_argument("--stems", action="store_true", help="also write one .mid per track")
    p_gen.set_defaults(func=_cmd_generate)

    p_live = sub.add_parser("live", help="stream a song into FL Studio over MIDI")
    _add_gen_args(p_live)
    p_live.add_argument("-p", "--port", default=None, help="MIDI output port name")
    p_live.add_argument("--virtual", action="store_true",
                        help="create a virtual port named 'FL Auto Bot' (macOS/Linux)")
    p_live.add_argument("--loop", action="store_true", help="loop until Ctrl+C")
    p_live.add_argument("--list-ports", action="store_true", help="list ports and exit")
    p_live.set_defaults(func=_cmd_live)

    p_ai = sub.add_parser(
        "ai", help="describe a song in words; Claude designs it, then export MIDI")
    p_ai.add_argument("brief", nargs="+",
                      help='natural-language description, e.g. "dark lofi beat at 72 bpm"')
    p_ai.add_argument("-o", "--out", default=None, help="output .mid path")
    p_ai.add_argument("--stems", action="store_true", help="also write one .mid per track")
    p_ai.add_argument("--seed", type=int, default=None, help="seed for the render step")
    p_ai.add_argument("--backend", choices=["claude", "ollama"], default="claude",
                      help="LLM backend (default: claude; ollama runs offline)")
    p_ai.add_argument("--model", default=None,
                      help="model name (default: claude-opus-4-8, or llama3.1 for ollama)")
    p_ai.add_argument("--host", default="http://localhost:11434",
                      help="Ollama host (for --backend ollama)")
    p_ai.add_argument("-i", "--chat", action="store_true",
                      help="interactive refine loop (\"make it darker\", \"add an arp\")")
    p_ai.add_argument("--plan-only", action="store_true",
                      help="print the AI's plan without rendering MIDI")
    p_ai.add_argument("--play", action="store_true",
                      help="also stream the result into FL Studio over MIDI")
    p_ai.add_argument("-p", "--port", default=None, help="MIDI port for --play")
    p_ai.add_argument("--virtual", action="store_true", help="virtual MIDI port for --play")
    p_ai.set_defaults(func=_cmd_ai)

    sub.add_parser("genres", help="list available genres").set_defaults(func=_cmd_genres)
    sub.add_parser("ports", help="list MIDI output ports").set_defaults(func=_cmd_ports)
    return parser


def main(argv: Optional[list] = None) -> int:
    parser = build_parser()
    argv = list(sys.argv[1:] if argv is None else argv)
    commands = {"generate", "live", "genres", "ports", "ai"}
    # Friendly default: bare args (e.g. `flautobot -g lofi`) imply `generate`.
    if not argv:
        argv = ["generate"]
    elif argv[0] not in commands and argv[0] not in ("-h", "--help", "--version"):
        argv = ["generate", *argv]

    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 0
    try:
        return args.func(args)
    except (ValueError, KeyError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
