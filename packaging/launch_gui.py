#!/usr/bin/env python3
"""Entry point for the bundled FL Auto Bot GUI executable.

PyInstaller packages this single script (plus the ``flautobot`` package and its
dependencies) into a standalone app. Kept tiny on purpose: it just launches the
GUI and, in a windowed build with no console, shows any startup error in a
dialog instead of vanishing silently.
"""

import sys


def main() -> int:
    from flautobot.gui import GuiError, run

    try:
        return run()
    except GuiError as exc:
        # Windowed builds have no console -- try to show the message in a dialog.
        try:
            import tkinter as tk
            from tkinter import messagebox

            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("FL Auto Bot", str(exc))
            root.destroy()
        except Exception:
            print(exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
