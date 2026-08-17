"""Paced, in-process driver for narrated/recorded UI walkthroughs.

Same real, running TaskResourceManager app as driver.ScenarioDriver (same
canvas, same widgets, same model) - the difference is what happens at each
step: nothing is patched away here. Dialogs pop for real and are answered
by finding and driving their real widgets (Entry.insert, Button.invoke,
Menu.tk_popup/invoke), with a deliberate pause between actions so a human
watching a screen recording can follow along.

This intentionally does NOT drive the OS-level mouse/keyboard (originally
planned via ydotool + org.gnome.Shell.Screencast). On this system neither
held up under test: ydotool's synthetic input isn't honored by this
Wayland/Mutter session at all (uinput events report success but never
move the pointer or reach the app, even after a clean daemon restart),
and org.gnome.Shell.Screencast no longer exists in this GNOME Shell
version (only the session-negotiated org.gnome.Mutter.ScreenCast/
RemoteDesktop portal remains, which is a materially bigger integration).
So: real widget state changes, real dialogs, real Tk rendering - just
triggered in-process rather than via a physically-moving OS cursor. Start
your own screen recorder (e.g. GNOME's Ctrl+Alt+Shift+R) before running a
scenario against this driver; it doesn't control recording itself.

A blocking modal (simpledialog.askstring, messagebox.*) still runs its
own nested Tk loop via wait_window() - but that loop still services
root.after() timers, so a callback armed with root.after() *before*
triggering the action that opens the dialog can find the real dialog,
type into it, and click its real OK button, all while it's genuinely on
screen - no patching needed, unlike driver.ScenarioDriver's fast path.
"""

from __future__ import annotations

import time
import tkinter as tk
from tkinter import messagebox
from unittest.mock import patch

from scripts.ui_scenarios.driver import ScenarioDriver, SyntheticEvent


class VisualDriver(ScenarioDriver):
    """Drives one real, in-process TaskResourceManager instance, paced for
    a human (and a screen recorder) to follow."""

    def __init__(self, pace: float = 0.6, type_delay: float = 0.04):
        super().__init__()
        self.pace = pace
        self.type_delay = type_delay

    def _beat(self, seconds: float | None = None):
        """Let Tk actually redraw, then pause - time.sleep() alone doesn't
        flush pending redraws, so without the update() a recorder would
        just see the last-drawn frame freeze for the sleep's duration."""
        self.pump()
        time.sleep(self.pace if seconds is None else seconds)
        self.pump()

    def _canvas_screen_xy(self, canvas: tk.Canvas, canvas_x: float, canvas_y: float):
        """Absolute screen position for a point given in `canvas`'s own
        (scrollable) coordinate space - needed for tk_popup(), which takes
        real screen coordinates, unlike on_task_press/release's event.x/y
        which are viewport-relative and get canvasx()/canvasy()-adjusted
        internally by the handlers themselves."""
        x = canvas.winfo_rootx() + (canvas_x - canvas.canvasx(0))
        y = canvas.winfo_rooty() + (canvas_y - canvas.canvasy(0))
        return int(x), int(y)

    def _type_into(self, entry: tk.Entry, text: str):
        entry.delete(0, tk.END)
        for ch in text:
            entry.insert(tk.END, ch)
            entry.update()
            time.sleep(self.type_delay)

    def _arm_askstring(self, expected_title: str, text: str, delay_ms: int = 350):
        """Schedules the real simpledialog.askstring popup (titled
        `expected_title`) to be typed into and submitted shortly after it
        appears - the caller triggers the action that opens it right
        after arming this."""

        def answer():
            dialog = self._find_toplevel(expected_title)
            entry = self._find_widgets(dialog, tk.Entry)[0]
            entry.focus_set()
            self._type_into(entry, text)
            time.sleep(self.pace / 2)
            self._find_button(dialog, 'OK').invoke()

        self.root.after(delay_ms, answer)

    def _dismiss_lingering_dialogs(self):
        """Closes any Toplevel left open (e.g. edit_task_resources/
        edit_task_tags, which pop non-modally and don't block like
        simpledialog does) - the way a user skipping them for now would.

        Calls .destroy() directly rather than simulating an <Escape>
        keypress: with two+ stacked grab_set() dialogs open (both
        edit_task_resources and edit_task_tags call it), Tk's local grab
        doesn't nest - the second grab_set() shadows the first, and
        destroying the second leaves *no* window holding a grab at all
        rather than reverting to the first. In that state a synthetic
        <Escape> reliably fires on whichever dialog is still holding the
        grab, but not on one that used to hold it - simulating the keypress
        isn't the point here (these popups aren't part of what a scenario
        is narrating), so just closing them directly sidesteps that
        entirely.
        """
        for dialog in [
            w for w in self.root.winfo_children() if isinstance(w, tk.Toplevel)
        ]:
            if dialog.winfo_exists():
                self._beat(self.pace / 2)
                dialog.destroy()
        self._beat(self.pace / 3)

    # -- task grid -------------------------------------------------------

    def create_task(self, row: int, col: int, duration: int, name: str):
        start_x, y = self._canvas_xy(row, col)
        end_x, _ = self._canvas_xy(row, col + duration - 1)

        self.app.task_ops.on_task_press(SyntheticEvent(start_x, y))
        self._beat(self.pace / 2)
        mid_x = (start_x + end_x) / 2
        self.app.task_ops.on_task_drag(SyntheticEvent(mid_x, y))
        self._beat(self.pace / 3)
        self.app.task_ops.on_task_drag(SyntheticEvent(end_x, y))
        self._beat(self.pace / 3)

        self._arm_askstring('New Task', name)
        self.app.task_ops.on_task_release(SyntheticEvent(end_x, y))
        self._beat()

        task = next((t for t in self.model.tasks if t['description'] == name), None)
        assert task is not None, (
            f'create_task({name!r}) did not add a task to the model'
        )

        self._dismiss_lingering_dialogs()
        return task

    def add_resource(self, name: str):
        self._arm_askstring('Add Resource', name)
        self.app.task_ops.add_resource()
        self._beat()
        resource = next((r for r in self.model.resources if r['name'] == name), None)
        assert resource is not None, f'add_resource({name!r}) did not add a resource'
        return resource

    def assign_resource(self, task, resource, allocation: float = 1.0):
        self.app.task_ops.edit_task_resources(task)
        self._beat()

        dialog = self._find_toplevel('Edit Task Resources')
        entries = self._find_widgets(dialog, tk.Entry)
        index = self.model.resources.index(resource)
        entry = entries[index]
        entry.focus_set()
        self._beat(self.pace / 2)
        self._type_into(entry, str(allocation))
        self._beat(self.pace / 2)
        self._find_button(dialog, 'Save').invoke()
        self._beat()

    # -- dependencies ------------------------------------------------------

    def add_predecessor(
        self, task, predecessor_task, link_type: str = 'FS', lag: int = 0
    ):
        # The context menu's commands are closures over
        # controller.selected_task, not whatever task update_context_menu_
        # for_task was passed - a real right-click sets this via
        # on_right_click before popping the menu, so tk_popup()+invoke()
        # needs the same to actually act on `task` rather than whatever
        # was selected last.
        self.app.selected_task = task
        self.app.ui.update_context_menu_for_task(task)
        self.assert_context_menu_has('Add Predecessor')

        assert self.app.task_canvas is not None  # real by the time the app is built
        ui = self.app.ui.task_ui_elements[task['task_id']]
        cx = (ui['x1'] + ui['x2']) / 2
        cy = (ui['y1'] + ui['y2']) / 2
        screen_x, screen_y = self._canvas_screen_xy(self.app.task_canvas, cx, cy)

        menu = self.app.ui.context_menu
        menu.tk_popup(screen_x, screen_y)
        self._beat()

        token = str(predecessor_task['task_id'])
        if link_type != 'FS' or lag:
            token += f':{link_type}{"+" if lag >= 0 else ""}{lag}'

        self._arm_askstring('Add Predecessor', token)
        menu.invoke('Add Predecessor')
        menu.unpost()
        self._beat()

    # -- CCPM --------------------------------------------------------------

    def schedule_with_ccpm(self) -> str:
        """File -> Schedule with CCPM..., via a real, visible menu popup -
        only the resulting messagebox is patched rather than shown for
        real (unlike every other dialog this driver drives): confirmed by
        direct test that tkinter.messagebox.* never becomes discoverable
        via winfo_children() on this system at all, in or out of CCPM,
        meaning this Tk build likely renders it as a native (GTK-
        integrated) dialog rather than a plain Tk Toplevel - outside what
        Tk's own widget introspection can find or drive, unlike
        simpledialog/hand-built dialogs which are provably fine."""
        self.assert_menu_path_has('File', 'Schedule with CCPM...')

        menu = self.app.ui.file_menu
        x, y = self.root.winfo_rootx() + 20, self.root.winfo_rooty() + 20
        menu.tk_popup(x, y)
        self._beat()

        captured: dict[str, str] = {}

        def fake_showinfo(_title, message, **_kwargs):
            captured['info'] = message

        def fake_showerror(title, message, **_kwargs):
            captured['error'] = f'{title}: {message}'

        with (
            patch.object(messagebox, 'showinfo', side_effect=fake_showinfo),
            patch.object(messagebox, 'showerror', side_effect=fake_showerror),
        ):
            menu.invoke('Schedule with CCPM...')
        menu.unpost()
        self._beat()

        if 'error' in captured:
            raise AssertionError(f'Schedule with CCPM failed: {captured["error"]}')
        assert 'info' in captured, 'Schedule with CCPM produced no confirmation dialog'
        return captured['info']
