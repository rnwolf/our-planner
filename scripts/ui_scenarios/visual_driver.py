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

A blocking modal (simpledialog.askstring, a hand-built Toplevel with its
own wait_window()) still runs its own nested Tk loop - but that loop
still services root.after() timers, so a callback armed with
root.after() *before* triggering the action that opens the dialog can
find the real dialog, type into it, and click its real OK button, all
while it's genuinely on screen - no patching needed, unlike
driver.ScenarioDriver's fast path.

tkinter.messagebox.* (askyesno/showinfo/showerror) is the one exception:
confirmed by direct test that it never becomes discoverable via
winfo_children() on this system at all, meaning this Tk build renders it
as a native (GTK-integrated) dialog rather than a plain Tk Toplevel -
outside what Tk's own widget introspection can find or drive. Every
messagebox.* call this driver needs answered is patched instead, same as
driver.ScenarioDriver's fast path - the "no patching" rule above is
specifically about simpledialog and hand-built Toplevels.
"""

from __future__ import annotations

import time
import tkinter as tk
from tkinter import messagebox, scrolledtext
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

    def _arm_project_picker(
        self, expected_title: str, project_name: str | None, delay_ms: int = 350
    ):
        """Same idea as _arm_askstring, for
        CcpmOperations._pick_project's hand-built Toplevel (project
        listbox + OK/Cancel) - only shown when more than one project
        exists. Selects `project_name`'s row if given, otherwise leaves
        whatever's pre-selected (the model's default project) alone, then
        clicks OK."""

        def answer():
            dialog = self._find_toplevel(expected_title)
            if project_name is not None:
                listbox = self._find_widgets(dialog, tk.Listbox)[0]
                names = list(listbox.get(0, tk.END))
                listbox.selection_clear(0, tk.END)
                listbox.selection_set(names.index(project_name))
            time.sleep(self.pace / 2)
            self._find_button(dialog, 'OK').invoke()

        self.root.after(delay_ms, answer)

    def _dismiss_lingering_dialogs(self):
        """Closes any Toplevel left open after task creation (e.g.
        edit_task_resources, which pops non-modally and doesn't block like
        simpledialog does) - the way a user skipping it for now would.

        Calls .destroy() directly rather than simulating an <Escape>
        keypress: task creation used to pop edit_task_resources AND
        edit_task_tags together, and with two+ stacked grab_set() dialogs
        open, Tk's local grab doesn't nest - the second grab_set() shadows
        the first, and destroying the second leaves *no* window holding a
        grab at all rather than reverting to the first. In that state a
        synthetic <Escape> reliably fires on whichever dialog is still
        holding the grab, but not on one that used to hold it. Task
        creation only pops one dialog now, but this stays generic (and
        keeps using .destroy()) in case a future dialog stacks another one
        the same way - simulating the keypress was never the point here
        anyway, since these popups aren't part of what a scenario is
        narrating.
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
        search_entry, allocation_entry = self._find_widgets(dialog, tk.Entry)
        _assigned_listbox, available_listbox = self._find_widgets(dialog, tk.Listbox)

        search_entry.focus_set()
        self._beat(self.pace / 2)
        self._type_into(search_entry, resource['name'])
        self._beat(self.pace / 2)

        available_listbox.selection_clear(0, tk.END)
        available_listbox.selection_set(0)
        available_listbox.event_generate('<<ListboxSelect>>')
        self._beat(self.pace / 2)

        allocation_entry.focus_set()
        self._beat(self.pace / 3)
        self._type_into(allocation_entry, str(allocation))
        self._beat(self.pace / 2)
        self._find_button(dialog, 'Add / Update').invoke()
        self._beat()

        self._find_button(dialog, 'Save').invoke()
        self._beat()

    # -- projects ------------------------------------------------------

    def new_project(self):
        self.assert_menu_path_has('File', 'New')

        menu = self.app.ui.file_menu
        x, y = self.root.winfo_rootx() + 20, self.root.winfo_rooty() + 20
        menu.tk_popup(x, y)
        self._beat()

        # messagebox.askyesno's confirmation isn't a discoverable Toplevel
        # on this system (see module docstring) - patched, not driven for
        # real, unlike everything else in this method.
        with patch.object(messagebox, 'askyesno', return_value=True):
            menu.invoke('New')
        menu.unpost()
        self._beat()

    def add_project(self, name: str, url: str = '', set_as_default: bool = False):
        self.assert_menu_path_has('Projects', 'Manage Projects...')

        menu = self.app.ui.projects_menu
        x, y = self.root.winfo_rootx() + 20, self.root.winfo_rooty() + 20
        menu.tk_popup(x, y)
        self._beat()
        menu.invoke('Manage Projects...')
        menu.unpost()
        self._beat()

        dialog = self._find_toplevel('Manage Projects')
        name_entry, url_entry, *_fever_entries = self._find_widgets(dialog, tk.Entry)

        name_entry.focus_set()
        self._beat(self.pace / 2)
        self._type_into(name_entry, name)
        self._beat(self.pace / 2)

        if url:
            url_entry.focus_set()
            self._type_into(url_entry, url)
            self._beat(self.pace / 2)

        self._find_button(dialog, 'Add').invoke()
        self._beat()

        project = next((p for p in self.model.projects if p['name'] == name), None)
        assert project is not None, f'add_project({name!r}) did not add a project'

        if set_as_default:
            listbox = self._find_widgets(dialog, tk.Listbox)[0]
            listbox.selection_clear(0, tk.END)
            listbox.selection_set(tk.END)
            listbox.event_generate('<<ListboxSelect>>')
            self._beat(self.pace / 2)
            self._find_button(dialog, 'Set as Default').invoke()
            self._beat()

        self._find_button(dialog, 'Close').invoke()
        self._beat()
        return project

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

    def schedule_with_ccpm(self, project_name: str | None = None) -> str:
        """File -> Schedule with CCPM..., via a real, visible menu popup.
        The result is CcpmOperations._show_result_dialog - a hand-built
        Toplevel with grab_set() but no wait_window(), so the call returns
        as soon as it's built, not once it's closed - reads its real
        ScrolledText and clicks its real Close button, the same way
        assign_resource drives Edit Task Resources' real widgets. There's
        no messagebox call left in this path to patch (see driver.py's
        schedule_with_ccpm docstring for why: the result dialog used to be
        a messagebox, replaced by this scrollable Toplevel so long
        validation/error text isn't squeezed into a tall, narrow column).

        With more than one project, _pick_project pops its own real,
        blocking (wait_window()) chooser first - menu.invoke() below won't
        return until that's answered, so arm it before invoking, the same
        as every other real dialog this driver drives."""
        self.assert_menu_path_has('File', 'Schedule with CCPM...')

        menu = self.app.ui.file_menu
        x, y = self.root.winfo_rootx() + 20, self.root.winfo_rooty() + 20
        menu.tk_popup(x, y)
        self._beat()

        if len(self.model.projects) > 1:
            self._arm_project_picker('Schedule with CCPM', project_name)

        menu.invoke('Schedule with CCPM...')
        menu.unpost()
        self._beat()

        toplevels = {
            w.title(): w
            for w in self.root.winfo_children()
            if isinstance(w, tk.Toplevel) and w.winfo_exists()
        }

        def read_and_close(dialog):
            text = self._find_widgets(dialog, scrolledtext.ScrolledText)[0].get(
                '1.0', 'end-1c'
            )
            self._beat()
            self._find_button(dialog, 'Close').invoke()
            self._beat()
            return text

        for title in ('CCPM Error', 'CCPM Validation Failed'):
            if title in toplevels:
                text = read_and_close(toplevels[title])
                raise AssertionError(f'Schedule with CCPM failed: {title}: {text}')

        assert 'CCPM Schedule Created' in toplevels, (
            'Schedule with CCPM produced no result dialog'
        )
        return read_and_close(toplevels['CCPM Schedule Created'])
