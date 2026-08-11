"""
Small shared Tkinter helpers used across dialogs.
"""

import tkinter as tk
from tkinter import ttk


def add_resize_handle(dialog: tk.Toplevel) -> None:
    """Add a visible resize handle to a dialog, and set its minimum size to
    what its content currently needs (measured, so font/theme-proof) - never
    allow shrinking below that."""
    ttk.Sizegrip(dialog).place(relx=1.0, rely=1.0, anchor='se')
    dialog.update_idletasks()
    dialog.minsize(dialog.winfo_reqwidth(), dialog.winfo_reqheight())
