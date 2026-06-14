"""Tests for the GUI's display-free logic.

The Tkinter widgets can't run headless, but the module is import-safe without Tk
and its pure helpers (``normalize_preset``) are fully testable.
"""

import pytest

from flautobot import compose
from flautobot import gui


def test_module_imports_without_tkinter():
    # Importing must never fail just because Tk is missing.
    assert hasattr(gui, "normalize_preset")
    assert isinstance(gui._TK_OK, bool)


def test_run_raises_friendly_error_when_no_tk():
    if gui._TK_OK:
        pytest.skip("Tkinter is available; the no-Tk path can't be exercised here.")
    with pytest.raises(gui.GuiError):
        gui.run()


def test_normalize_preset_valid_and_renderable():
    kwargs = gui.normalize_preset({
        "genre": "house", "key": "F#", "scale": "minor",
        "tempo": "124", "bars": "16", "seed": "42",
    })
    assert kwargs["seed"] == 42
    assert kwargs["tempo"] == 124.0
    assert kwargs["bars"] == 16
    # The kwargs must be directly usable by the engine.
    song = compose(**kwargs)
    assert song.note_count() > 0


def test_normalize_preset_blank_seed_is_randomised():
    kwargs = gui.normalize_preset({
        "genre": "lofi", "key": "A", "scale": "dorian",
        "tempo": "78", "bars": "8", "seed": "",
    })
    assert isinstance(kwargs["seed"], int)
    assert 0 <= kwargs["seed"] < 1_000_000


@pytest.mark.parametrize("bad,field", [
    ({"genre": "nope"}, "genre"),
    ({"key": "H#"}, "key"),
    ({"tempo": "fast"}, "tempo"),
    ({"tempo": "5"}, "tempo"),     # out of range
    ({"bars": "lots"}, "bars"),
    ({"bars": "0"}, "bars"),       # out of range
    ({"seed": "abc"}, "seed"),
])
def test_normalize_preset_rejects_bad_input(bad, field):
    form = {"genre": "house", "key": "A", "scale": "minor",
            "tempo": "120", "bars": "16", "seed": ""}
    form.update(bad)
    with pytest.raises(ValueError):
        gui.normalize_preset(form)


def test_safe_name():
    assert gui._safe_name("House in F# minor") == "house_in_fs_minor"
    assert gui._safe_name("!!!") == "track"
