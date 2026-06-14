"""Stream a generated song into FL Studio in real time over MIDI.

This needs a *virtual MIDI port* connecting this process to FL Studio:

* **Windows:** install `loopMIDI <https://www.tobias-erichsen.de/software/loopmidi.html>`_,
  create a port, then in FL Studio enable it under Options -> MIDI -> Input.
  Pass its name with ``--port``.
* **macOS:** enable the IAC Driver in *Audio MIDI Setup* (Window -> Show MIDI
  Studio), then enable it in FL Studio's MIDI settings. Use ``--virtual`` or
  ``--port "IAC Driver Bus 1"``.
* **Linux:** any ALSA/JACK MIDI loopback works; ``--virtual`` creates a port.

In FL Studio: select an instrument channel, make sure it's receiving from the
port, and arm recording (or just listen) while the bot plays.

Requires the optional ``python-rtmidi`` backend (``pip install python-rtmidi``).
"""

from __future__ import annotations

from typing import List, Optional

from .song import Song

DEFAULT_PORT_NAME = "FL Auto Bot"


class LiveError(RuntimeError):
    """Raised when the MIDI backend or a port is unavailable."""


def _require_backend():
    try:
        import mido  # noqa: F401
        import rtmidi  # noqa: F401  (ensures the rtmidi backend can load)
        return mido
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise LiveError(
            "Live MIDI needs the 'python-rtmidi' backend.\n"
            "  Install it with:  pip install python-rtmidi\n"
            "Then create a virtual MIDI port (loopMIDI / IAC Driver) and point "
            "FL Studio at it."
        ) from exc


def list_ports() -> List[str]:
    """Return the available MIDI output ports."""
    mido = _require_backend()
    try:
        return list(mido.get_output_names())
    except Exception as exc:  # pragma: no cover - environment dependent
        raise LiveError(f"Could not query MIDI ports: {exc}") from exc


def _open_output(mido, port_name: Optional[str], virtual: bool):
    try:
        if virtual:
            return mido.open_output(port_name or DEFAULT_PORT_NAME, virtual=True)
        if port_name:
            return mido.open_output(port_name)
        names = mido.get_output_names()
        if not names:
            raise LiveError(
                "No MIDI output ports found. Create a virtual port (loopMIDI on "
                "Windows, IAC Driver on macOS) or pass --virtual."
            )
        return mido.open_output(names[0])
    except LiveError:
        raise
    except Exception as exc:
        raise LiveError(
            f"Could not open MIDI port {port_name or '(default)'}: {exc}\n"
            f"Available ports: {_safe_ports(mido)}"
        ) from exc


def _safe_ports(mido) -> List[str]:
    try:
        return list(mido.get_output_names())
    except Exception:  # pragma: no cover
        return []


def _all_notes_off(mido, out) -> None:
    for ch in range(16):
        out.send(mido.Message("control_change", channel=ch, control=123, value=0))


def play_song(
    song: Song,
    port_name: Optional[str] = None,
    *,
    virtual: bool = False,
    loop: bool = False,
) -> None:
    """Play ``song`` into FL Studio over a MIDI port until done or interrupted.

    Set ``virtual=True`` to create a port named "FL Auto Bot" (macOS/Linux), or
    pass ``port_name`` to target an existing loopMIDI/IAC port. ``loop=True``
    repeats until you press Ctrl+C.
    """
    from .midi_export import song_to_midifile

    mido = _require_backend()
    mid = song_to_midifile(song)
    out = _open_output(mido, port_name, virtual)
    try:
        while True:
            for msg in mid.play():
                out.send(msg)
            if not loop:
                break
    except KeyboardInterrupt:
        pass
    finally:
        _all_notes_off(mido, out)
        out.close()
