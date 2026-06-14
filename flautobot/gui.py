"""A desktop GUI for FL Auto Bot (Tkinter).

Wraps the whole toolkit in one window: preset generation, the AI brief, the
chat/refine loop and MIDI export. Launch it with::

    flautobot gui          # or:  python -m flautobot gui

Tkinter ships with standard Python. On some Linux builds it's a separate
package (``sudo apt install python3-tk``); this module imports it lazily so the
rest of FL Auto Bot works even where Tk is unavailable.

The UI is intentionally a thin shell over the tested engine
(:func:`flautobot.arrange.compose`, :class:`flautobot.ai.AIDirector`). The
pure, display-free helpers below (``normalize_preset``) are unit-tested; the
widgets just call them.
"""

from __future__ import annotations

import os
import queue
import random
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from . import theory
from .ai import AIDirector
from .arrange import compose
from .genres import get_genre, list_genres
from .midi_export import write_midi, write_stems

# Import Tkinter lazily so importing this module never fails without it.
try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, scrolledtext, ttk
    _TK_OK = True
except ImportError:  # pragma: no cover - environment dependent
    _TK_OK = False


class GuiError(RuntimeError):
    """Raised when the GUI can't start (e.g. Tkinter is unavailable)."""


def _safe_name(text: str) -> str:
    s = text.lower().replace(" ", "_").replace("#", "s")
    return "".join(c for c in s if c.isalnum() or c in "_-") or "track"


def normalize_preset(values: Dict[str, Any]) -> Dict[str, Any]:
    """Validate raw form strings into keyword args for :func:`compose`.

    Raises ``ValueError`` with a human-readable message on bad input. An empty
    seed becomes a fresh random one so the result is reproducible afterwards.
    """
    genre = str(values.get("genre", "")).strip()
    if genre not in list_genres():
        raise ValueError(f"Unknown genre {genre!r}.")

    key = str(values.get("key", "")).strip() or "A"
    theory.parse_root(key)  # raises ValueError on a bad tonic

    scale = str(values.get("scale", "")).strip()
    if scale not in theory.SCALES:
        raise ValueError(f"Unknown scale {scale!r}.")

    try:
        tempo = float(values.get("tempo"))
    except (TypeError, ValueError):
        raise ValueError("Tempo must be a number.")
    if not 20 <= tempo <= 400:
        raise ValueError("Tempo must be between 20 and 400 BPM.")

    try:
        bars = int(values.get("bars"))
    except (TypeError, ValueError):
        raise ValueError("Bars must be a whole number.")
    if not 1 <= bars <= 256:
        raise ValueError("Bars must be between 1 and 256.")

    seed_str = str(values.get("seed", "")).strip()
    if seed_str:
        try:
            seed = int(seed_str)
        except ValueError:
            raise ValueError("Seed must be a whole number (or blank for random).")
    else:
        seed = random.randrange(1_000_000)

    return {"genre": genre, "key": key, "scale": scale,
            "tempo": tempo, "bars": bars, "seed": seed}


def _open_in_file_manager(path: Path) -> None:
    target = str(path)
    try:
        if sys.platform.startswith("darwin"):
            subprocess.run(["open", target], check=False)
        elif os.name == "nt":
            os.startfile(target)  # type: ignore[attr-defined]
        else:
            subprocess.run(["xdg-open", target], check=False)
    except Exception:
        pass


def run() -> int:
    """Launch the GUI. Returns an exit code; raises :class:`GuiError` if no Tk."""
    if not _TK_OK:
        raise GuiError(
            "The GUI needs Tkinter, which isn't available in this Python.\n"
            "  Linux:   sudo apt install python3-tk\n"
            "  macOS:   brew install python-tk   (or use the python.org installer)\n"
            "  Windows: reinstall Python with the 'tcl/tk' option checked.\n"
            "Meanwhile the command line works:  flautobot generate / ai / live"
        )
    App().run()
    return 0


def _console() -> int:
    """Entry point for the ``flautobot-gui`` command (handles missing Tk)."""
    try:
        return run()
    except GuiError as exc:
        print(exc, file=sys.stderr)
        return 1


if _TK_OK:

    OUTPUT_DIR = Path("output")
    PADDING = {"padx": 6, "pady": 4}

    class App:
        """The main FL Auto Bot window."""

        def __init__(self) -> None:
            self.root = tk.Tk()
            self.root.title("FL Auto Bot 🎹")
            self.root.minsize(640, 620)

            self._queue: "queue.Queue" = queue.Queue()
            self._busy = False
            self._buttons: list = []
            self.song = None            # the most recent Song
            self.conversation = None    # active AI refine conversation
            self._rev = 0               # refine revision counter

            self.genre = tk.StringVar(value="house")
            self.key = tk.StringVar(value="A")
            self.scale = tk.StringVar(value=get_genre("house").scale)
            self.tempo = tk.StringVar(value=str(int(get_genre("house").tempo)))
            self.bars = tk.StringVar(value="32")
            self.seed = tk.StringVar(value="")
            self.stems = tk.BooleanVar(value=False)
            self.brief = tk.StringVar(value="")
            self.backend = tk.StringVar(value="claude")
            self.model = tk.StringVar(value="")
            self.refine = tk.StringVar(value="")
            self.status = tk.StringVar(value="Ready.")

            self._build()
            self.root.after(120, self._poll)

        # -- layout -----------------------------------------------------------

        def _build(self) -> None:
            self._build_preset()
            self._build_ai()
            self._build_actions()
            self._build_log()
            ttk.Label(self.root, textvariable=self.status, relief="sunken",
                      anchor="w").pack(side="bottom", fill="x")

        def _build_preset(self) -> None:
            frame = ttk.LabelFrame(self.root, text="Preset")
            frame.pack(fill="x", **PADDING)

            ttk.Label(frame, text="Genre").grid(row=0, column=0, sticky="e", **PADDING)
            combo = ttk.Combobox(frame, textvariable=self.genre, values=list_genres(),
                                 state="readonly", width=12)
            combo.grid(row=0, column=1, sticky="w", **PADDING)
            combo.bind("<<ComboboxSelected>>", self._on_genre)

            ttk.Label(frame, text="Key").grid(row=0, column=2, sticky="e", **PADDING)
            ttk.Entry(frame, textvariable=self.key, width=6).grid(
                row=0, column=3, sticky="w", **PADDING)

            ttk.Label(frame, text="Scale").grid(row=0, column=4, sticky="e", **PADDING)
            ttk.Combobox(frame, textvariable=self.scale, values=sorted(theory.SCALES),
                         state="readonly", width=14).grid(row=0, column=5, sticky="w", **PADDING)

            ttk.Label(frame, text="Tempo").grid(row=1, column=0, sticky="e", **PADDING)
            ttk.Spinbox(frame, from_=20, to=400, textvariable=self.tempo, width=6).grid(
                row=1, column=1, sticky="w", **PADDING)

            ttk.Label(frame, text="Bars").grid(row=1, column=2, sticky="e", **PADDING)
            ttk.Spinbox(frame, from_=1, to=256, textvariable=self.bars, width=6).grid(
                row=1, column=3, sticky="w", **PADDING)

            ttk.Label(frame, text="Seed").grid(row=1, column=4, sticky="e", **PADDING)
            ttk.Entry(frame, textvariable=self.seed, width=14).grid(
                row=1, column=5, sticky="w", **PADDING)

            ttk.Checkbutton(frame, text="Also export stems",
                            variable=self.stems).grid(row=2, column=1, columnspan=2,
                                                      sticky="w", **PADDING)
            self._button(frame, "Generate from preset", self._generate_preset).grid(
                row=2, column=5, sticky="e", **PADDING)

        def _build_ai(self) -> None:
            frame = ttk.LabelFrame(self.root, text="AI director — describe a song")
            frame.pack(fill="x", **PADDING)

            ttk.Entry(frame, textvariable=self.brief).grid(
                row=0, column=0, columnspan=5, sticky="we", **PADDING)
            frame.columnconfigure(0, weight=1)

            ttk.Label(frame, text="Backend").grid(row=1, column=0, sticky="e", **PADDING)
            ttk.Radiobutton(frame, text="Claude", value="claude",
                            variable=self.backend).grid(row=1, column=1, sticky="w")
            ttk.Radiobutton(frame, text="Ollama (offline)", value="ollama",
                            variable=self.backend).grid(row=1, column=2, sticky="w")
            ttk.Label(frame, text="Model").grid(row=1, column=3, sticky="e", **PADDING)
            ttk.Entry(frame, textvariable=self.model, width=18).grid(
                row=1, column=4, sticky="w", **PADDING)

            self._button(frame, "Design with AI", self._design_ai).grid(
                row=2, column=4, sticky="e", **PADDING)

            ttk.Label(frame, text="Refine").grid(row=3, column=0, sticky="e", **PADDING)
            entry = ttk.Entry(frame, textvariable=self.refine)
            entry.grid(row=3, column=1, columnspan=3, sticky="we", **PADDING)
            entry.bind("<Return>", lambda _e: self._refine_ai())
            self._button(frame, "Refine ▶", self._refine_ai).grid(
                row=3, column=4, sticky="e", **PADDING)

        def _build_actions(self) -> None:
            frame = ttk.Frame(self.root)
            frame.pack(fill="x", **PADDING)
            self._button(frame, "Save MIDI as…", self._save_midi).pack(side="left", padx=4)
            self._button(frame, "Save stems…", self._save_stems).pack(side="left", padx=4)
            self._button(frame, "▶ Play to FL Studio", self._play_live).pack(side="left", padx=4)
            ttk.Button(frame, text="Open output folder",
                       command=lambda: _open_in_file_manager(OUTPUT_DIR)).pack(side="right", padx=4)

        def _build_log(self) -> None:
            frame = ttk.LabelFrame(self.root, text="Plan & log")
            frame.pack(fill="both", expand=True, **PADDING)
            self.log = scrolledtext.ScrolledText(frame, height=14, wrap="word",
                                                 state="disabled")
            self.log.pack(fill="both", expand=True)
            self._log("Pick a preset and Generate, or type a brief and Design with AI.\n"
                      "AI needs ANTHROPIC_API_KEY (Claude) or a local Ollama server.")

        def _button(self, parent, text: str, command: Callable) -> "ttk.Button":
            btn = ttk.Button(parent, text=text, command=command)
            self._buttons.append(btn)
            return btn

        # -- helpers ----------------------------------------------------------

        def _on_genre(self, _event=None) -> None:
            g = get_genre(self.genre.get())
            self.scale.set(g.scale)
            self.tempo.set(str(int(g.tempo)))

        def _log(self, text: str) -> None:
            self.log.configure(state="normal")
            self.log.insert("end", text.rstrip() + "\n")
            self.log.see("end")
            self.log.configure(state="disabled")

        def _set_busy(self, busy: bool, status: str = "Ready.") -> None:
            self._busy = busy
            self.status.set(status)
            for btn in self._buttons:
                btn.configure(state="disabled" if busy else "normal")

        def _async(self, work: Callable[[], Any], on_ok: Callable[[Any], None],
                   status: str) -> None:
            """Run ``work`` off the UI thread; deliver the result on it."""
            if self._busy:
                return
            self._set_busy(True, status)

            def runner() -> None:
                try:
                    result = work()
                except Exception as exc:  # surfaced on the UI thread
                    self._queue.put(("err", exc, None))
                else:
                    self._queue.put(("ok", result, on_ok))

            threading.Thread(target=runner, daemon=True).start()

        def _post_log(self, text: str) -> None:
            self._queue.put(("log", text, None))

        def _poll(self) -> None:
            try:
                while True:
                    kind, payload, cb = self._queue.get_nowait()
                    if kind == "log":
                        self._log(payload)
                        continue
                    self._set_busy(False)
                    if kind == "ok" and cb:
                        cb(payload)
                    elif kind == "err":
                        self._log(f"⚠  {payload}")
                        self.status.set("Error — see log.")
            except queue.Empty:
                pass
            self.root.after(120, self._poll)

        def _write_song(self, song, title: str, seed: int, rev: Optional[int] = None) -> Path:
            suffix = f"_rev{rev}" if rev else ""
            path = OUTPUT_DIR / f"{_safe_name(title)}_seed{seed}{suffix}.mid"
            write_midi(song, path)
            self.song = song
            if self.stems.get():
                stem_dir = OUTPUT_DIR / (path.stem + "_stems")
                write_stems(song, stem_dir, path.stem)
                self._log(f"Stems -> {stem_dir}/")
            return path

        # -- actions ----------------------------------------------------------

        def _generate_preset(self) -> None:
            try:
                kwargs = normalize_preset({
                    "genre": self.genre.get(), "key": self.key.get(),
                    "scale": self.scale.get(), "tempo": self.tempo.get(),
                    "bars": self.bars.get(), "seed": self.seed.get(),
                })
            except ValueError as exc:
                messagebox.showerror("Invalid input", str(exc))
                return
            seed = kwargs["seed"]
            song = compose(**kwargs)
            path = self._write_song(song, song.name, seed)
            self._log(f"\n{song.summary()}\nseed: {seed}\nMIDI -> {path}")
            self.status.set(f"Generated {path.name}")

        def _design_ai(self) -> None:
            brief = self.brief.get().strip()
            if not brief:
                messagebox.showinfo("AI director", "Type a brief first, e.g. "
                                    "\"dark lofi at 72 bpm\".")
                return
            backend, model = self.backend.get(), self.model.get().strip() or None
            seed = self.seed.get().strip()
            seed = int(seed) if seed.isdigit() else random.randrange(1_000_000)
            self._log(f"\n[{backend}] designing: {brief!r} …")

            def work():
                director = AIDirector(backend=backend, model=model)
                convo = director.conversation(seed=seed)
                song, plan = convo.send(brief)
                return convo, song, plan, seed

            self._async(work, self._on_designed, f"Designing with {backend}…")

        def _on_designed(self, payload) -> None:
            convo, song, plan, seed = payload
            self.conversation = convo
            self._rev = 0
            path = self._write_song(song, plan.title, seed)
            self._log(f"\n{plan.summary()}\n\n{song.summary()}\nMIDI -> {path}")
            self.status.set(f"AI: {path.name} — refine it below.")

        def _refine_ai(self) -> None:
            if self.conversation is None:
                messagebox.showinfo("Refine", "Design a song with AI first.")
                return
            instruction = self.refine.get().strip()
            if not instruction:
                return
            self.refine.set("")
            self._log(f"\nrefine> {instruction}")
            convo = self.conversation

            def work():
                song, plan = convo.send(instruction)
                return song, plan

            self._async(work, self._on_refined, "Refining…")

        def _on_refined(self, payload) -> None:
            song, plan = payload
            self._rev += 1
            seed = self.conversation.seed if self.conversation else 0
            path = self._write_song(song, plan.title, seed or 0, rev=self._rev)
            self._log(f"\n{plan.summary()}\n\n{song.summary()}\nMIDI -> {path}")
            self.status.set(f"Refined -> {path.name}")

        def _save_midi(self) -> None:
            if not self._has_song():
                return
            path = filedialog.asksaveasfilename(
                defaultextension=".mid", filetypes=[("MIDI", "*.mid")],
                initialfile=f"{_safe_name(self.song.name)}.mid")
            if path:
                write_midi(self.song, path)
                self._log(f"Saved -> {path}")
                self.status.set("Saved.")

        def _save_stems(self) -> None:
            if not self._has_song():
                return
            folder = filedialog.askdirectory(title="Choose a folder for the stems")
            if folder:
                paths = write_stems(self.song, folder, _safe_name(self.song.name))
                self._log(f"Saved {len(paths)} stems -> {folder}/")
                self.status.set("Stems saved.")

        def _play_live(self) -> None:
            if not self._has_song():
                return
            from . import live

            song = self.song
            self._log("Streaming to FL Studio (virtual port 'FL Auto Bot')…")
            self.status.set("Playing — open the port in FL Studio's MIDI settings.")

            def runner():
                try:
                    live.play_song(song, virtual=True)
                except live.LiveError as exc:
                    self._post_log(f"⚠  {exc}")
                else:
                    self._post_log("Playback finished.")

            threading.Thread(target=runner, daemon=True).start()

        def _has_song(self) -> bool:
            if self.song is None:
                messagebox.showinfo("Nothing yet", "Generate or design a song first.")
                return False
            return True

        def run(self) -> None:
            self.root.mainloop()
