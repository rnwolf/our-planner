"""
Small shared Tkinter helpers used across dialogs.
"""

import tkinter as tk
from tkinter import ttk


def mnemonic(label: str, word: str, char: str | None = None) -> int:
    """Index into `label` for a menu item's `underline=`, anchored to
    `word` (a substring of `label`) rather than searched across the whole
    label - so a mnemonic letter that also happens to occur earlier in a
    shared prefix (e.g. the 'r' in "Import" before "Import Resources...")
    can't silently underline the wrong character. `char` defaults to
    `word`'s first letter; pass a later letter of `word` instead to pick a
    different mnemonic (e.g. word='Select', char='e' for its 2nd letter,
    when 'S' is already taken by a sibling menu item).
    """
    lower_label = label.lower()
    word_start = lower_label.index(word.lower())
    char = char or word[0]
    return lower_label.index(char.lower(), word_start)


def add_resize_handle(dialog: tk.Toplevel) -> None:
    """Add a visible resize handle to a dialog, and set its minimum size to
    what its content currently needs (measured, so font/theme-proof) - never
    allow shrinking below that."""
    ttk.Sizegrip(dialog).place(relx=1.0, rely=1.0, anchor='se')
    dialog.update_idletasks()
    dialog.minsize(dialog.winfo_reqwidth(), dialog.winfo_reqheight())
