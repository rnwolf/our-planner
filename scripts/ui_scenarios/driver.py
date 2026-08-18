"""Fast, in-process driver for scripted UI scenarios.

Runs the real `TaskResourceManager` app - real Tk root, real canvas, real
context menus, real dialogs - so a scenario exercises the actual wiring
between a user action and the model, not just the model/operations layer
(that's already covered by tests/test_scenarios.py and
scripts/stage12_walkthrough.py, which build scenarios directly against a
MagicMock controller and never touch Tk).

The one thing this driver fakes is *answering* modal dialogs
(simpledialog.askstring, messagebox.*): those call `wait_window`, which
runs its own nested Tk loop, so a same-thread caller can't sequence
"trigger the action" then "answer the popped dialog" without either a
second thread or patching the dialog call itself. Patching is what
test_scenarios.py already does (`patch('tkinter.messagebox.askyesno', ...)`)
and is far more reliable than timing a second thread against a nested
mainloop, so this driver does the same, just generalized to route by the
dialog's title so a scenario can answer several different prompts across
one run.

For a narrated, on-screen video (real dialogs, real mouse movement) a
separate "visual" driver reuses the same coordinate math but drives via
ydotool + org.gnome.Shell.Screencast instead of calling handlers directly.
This module is the fast half only.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, simpledialog, ttk
from unittest.mock import patch

from src.controller.task_manager import TaskResourceManager


class SyntheticEvent:
    """A minimal stand-in for a real Tk event - just the attributes the
    canvas handlers actually read (event.x/y/state). The app itself
    already builds one of these for its own Ctrl-+/- zoom shortcut
    (TaskResourceManager.zoom_via_keyboard), so this isn't a workaround,
    it's the same technique the codebase already uses to drive its own
    handlers synthetically."""

    def __init__(self, x: float, y: float, state: int = 0):
        self.x = x
        self.y = y
        self.state = state


class ScenarioDriver:
    """Drives one real, in-process TaskResourceManager instance."""

    def __init__(self):
        self.root = tk.Tk()
        # Some dialogs (e.g. edit_task_resources) call wait_visibility() on
        # a Toplevel transient to root - that never fires if root itself is
        # withdrawn/unmapped, so the window has to actually be shown, not
        # hidden, even for the "fast" driver.
        self.app = TaskResourceManager(self.root)
        self.model = self.app.model
        # The app always seeds a default project with sample tasks
        # (model.create_sample_tasks(), called from TaskResourceManager
        # .__init__) - clear them so a scenario's CCPM run only ever sees
        # the tasks it explicitly created.
        for task in list(self.model.tasks):
            self.model.delete_task(task['task_id'])
        self.pump()

    def pump(self):
        """Process pending Tk events/redraws without blocking."""
        self.root.update()

    def close(self):
        self.root.destroy()

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.close()

    # -- generic widget-tree helpers (for dialogs that are hand-built
    # Toplevels rather than simpledialog/messagebox, so there's no single
    # call to patch - e.g. Edit Task Resources) ------------------------

    def _find_toplevel(self, title: str) -> tk.Toplevel:
        candidates = [
            w
            for w in self.root.winfo_children()
            if isinstance(w, tk.Toplevel) and w.title() == title
        ]
        assert candidates, f'no open {title!r} dialog found'
        return candidates[-1]

    def _find_widgets(self, parent, cls):
        found = []
        for child in parent.winfo_children():
            if isinstance(child, cls):
                found.append(child)
            found.extend(self._find_widgets(child, cls))
        return found

    def _find_button(self, parent, text: str):
        # tk.Button and ttk.Button are unrelated classes (ttk.Button does
        # not subclass tk.Button) - Tk's own messagebox dialogs use
        # ttk.Button on this build, hand-built dialogs elsewhere in this
        # app use plain tk.Button, so both need checking.
        for button in self._find_widgets(parent, (tk.Button, ttk.Button)):
            if button.cget('text') == text:
                return button
        raise AssertionError(f'no button labeled {text!r} found')

    # -- task grid -----------------------------------------------------

    def _canvas_xy(self, row: int, col: int) -> tuple[float, float]:
        """Viewport-relative (x, y) for a grid cell, for use as a
        SyntheticEvent's own .x/.y - on_task_press/drag/release convert
        those to canvas coordinates themselves via canvasx()/canvasy()
        (see SyntheticEvent's docstring), so this has to subtract the
        canvas's *current* scroll offset to stay viewport-relative once
        anything has scrolled. Confirmed live: VisualDriver.create_task
        (unlike the fast path) fires real on_task_drag events, which can
        auto-scroll the canvas mid-scenario - a task created past that
        point, computed without this offset, silently lands on whatever
        real task now sits at that stale viewport position (mistaken for
        a body-click, not creating anything new)."""
        canvas = self.app.task_canvas
        assert canvas is not None  # real by the time the app is built
        x = col * self.app.cell_width - canvas.canvasx(0)
        y = row * self.app.task_height + self.app.task_height / 2 - canvas.canvasy(0)
        return x, y

    def create_task(self, row: int, col: int, duration: int, name: str):
        """Drag-create a task on the real canvas, the same gesture a user
        performs (press on empty grid, drag to the end column, release) -
        then answer the two dialogs that follow release (name, resources)
        the way a scenario wants them answered."""
        start_x, y = self._canvas_xy(row, col)
        end_x, _ = self._canvas_xy(row, col + duration - 1)

        def fake_askstring(title, _prompt, **_kwargs):
            if title == 'New Task':
                return name
            raise AssertionError(f'unexpected askstring during create_task: {title!r}')

        with (
            patch.object(simpledialog, 'askstring', side_effect=fake_askstring),
            patch.object(
                self.app.task_ops, 'edit_task_resources', lambda *_a, **_k: None
            ),
        ):
            self.app.task_ops.on_task_press(SyntheticEvent(start_x, y))
            self.app.task_ops.on_task_release(SyntheticEvent(end_x, y))
        self.pump()

        task = next((t for t in self.model.tasks if t['description'] == name), None)
        assert task is not None, (
            f'create_task({name!r}) did not add a task to the model'
        )
        return task

    def add_resource(self, name: str):
        """Toolbar/menu 'Add Resource' - a plain simpledialog.askstring
        prompt, unlike the hand-built Toplevel dialogs elsewhere."""
        with patch.object(simpledialog, 'askstring', return_value=name):
            self.app.task_ops.add_resource()
        self.pump()
        resource = next((r for r in self.model.resources if r['name'] == name), None)
        assert resource is not None, f'add_resource({name!r}) did not add a resource'
        return resource

    def assign_resource(self, task, resource, allocation: float = 1.0):
        """Right-click task -> Edit Task Resources: a hand-built Toplevel
        (search box -> filtered results list -> allocation -> Add/Update),
        not a simpledialog - driven by finding those real widgets and
        using them, rather than patching a single call."""
        self.app.task_ops.edit_task_resources(task)
        self.pump()

        dialog = self._find_toplevel('Edit Task Resources')
        search_entry, allocation_entry = self._find_widgets(dialog, tk.Entry)
        _assigned_listbox, available_listbox = self._find_widgets(dialog, tk.Listbox)

        search_entry.delete(0, tk.END)
        search_entry.insert(0, resource['name'])
        self.pump()
        assert available_listbox.size() > 0, (
            f'no match for resource {resource["name"]!r} in the search results'
        )
        available_listbox.selection_clear(0, tk.END)
        available_listbox.selection_set(0)
        available_listbox.event_generate('<<ListboxSelect>>')
        self.pump()

        allocation_entry.delete(0, tk.END)
        allocation_entry.insert(0, str(allocation))
        self._find_button(dialog, 'Add / Update').invoke()
        self._find_button(dialog, 'Save').invoke()
        self.pump()

    def set_resource_capacities(self, capacities: dict[str, float]):
        """Edit -> Edit Resources... -> Capacity tab -> Set Capacity by
        Index: the only UI path to a resource's per-day capacity (the
        resource grid only ever displays load/capacity, it isn't
        editable). `capacities` maps resource name -> capacity, applied
        across the model's entire day range (0..model.days-1) so it holds
        for however long the scenario runs. Opens the dialog once and
        drives all of `capacities` in that one session rather than
        reopening per resource, the way a real user would.

        Both 'Set Capacity by Index' and 'Set Capacity by Date' share the
        literal button text 'Update Capacity' (see create_capacity_tab's
        own comment on this) - scoping every widget lookup to the
        Capacity tab's frame, not the whole dialog, still leaves two
        matches, but the index-based controls are built first so
        _find_button's first-match-wins search reliably finds them, not
        the date-based ones.

        Clicking Update Capacity pops a messagebox.showinfo confirmation -
        patched away like every other messagebox.* call this driver
        answers (see driver.new_project), since it's a real modal, not a
        hand-built Toplevel this driver could instead find and close."""
        self.app.task_ops.edit_resources(parent=self.app.root)
        self.pump()

        dialog = self._find_toplevel('Edit Resources')
        notebook = self._find_widgets(dialog, ttk.Notebook)[0]
        notebook.select(1)  # the Capacity tab
        self.pump()
        capacity_tab = notebook.nametowidget(notebook.tabs()[1])

        dropdown = self._find_widgets(capacity_tab, ttk.Combobox)[0]
        # ttk.Combobox is a subclass of tk.Entry, so _find_widgets(...,
        # tk.Entry)'s isinstance check also matches `dropdown` itself -
        # without filtering it out here it lands as entries[0], shifting
        # every entry after it by one (confirmed live: day/end_day/
        # capacity each got the next field's value, and the leftover
        # value spilled into a date-range field that can't parse it,
        # producing a real "Please enter valid numbers" warning).
        entries = [
            w for w in self._find_widgets(capacity_tab, tk.Entry) if type(w) is tk.Entry
        ]
        day_entry, end_day_entry, capacity_entry, *_date_entries = entries
        update_button = self._find_button(capacity_tab, 'Update Capacity')
        last_day = self.model.days - 1

        for name, capacity in capacities.items():
            resource = next(
                (r for r in self.model.resources if r['name'] == name), None
            )
            assert resource is not None, (
                f'set_resource_capacities: no resource named {name!r}'
            )

            # dropdown.set() alone is enough: update_capacity() below only
            # ever reads dropdown.get() directly, never listens for
            # <<ComboboxSelected>>. Firing that event synthetically is not
            # just unneeded here - confirmed live to hang on this Tk build
            # starting with the third resource in one dialog session,
            # almost certainly the readonly Combobox's own popdown
            # Toplevel finally realizing/grabbing on repeated synthetic
            # firings, a real Tk quirk unrelated to anything this driver
            # is trying to test.
            dropdown.set(f'{resource["id"]} - {resource["name"]}')
            self.pump()

            day_entry.delete(0, tk.END)
            day_entry.insert(0, '0')
            end_day_entry.delete(0, tk.END)
            end_day_entry.insert(0, str(last_day))
            capacity_entry.delete(0, tk.END)
            capacity_entry.insert(0, str(capacity))

            with patch.object(messagebox, 'showinfo', lambda *_a, **_k: None):
                update_button.invoke()
            self.pump()

            assert resource['capacity'][0] == capacity, (
                f'set_resource_capacities({name!r}, {capacity}) did not apply'
            )

        self._find_button(dialog, 'Close').invoke()
        self.pump()

    # -- menu wiring checks ----------------------------------------------
    #
    # The wiring check dogtail/AT-SPI would have given us (does this
    # command actually exist, under this label, in this menu?) done
    # directly against the real tk.Menu widgets instead - Tk never
    # exposes an accessibility tree for these, so this is the equivalent
    # check available to us.

    def assert_menu_has(self, menu: tk.Menu, label: str):
        """Confirms `menu` carries a real entry (command, cascade,
        checkbutton, ...) with this exact label."""
        try:
            menu.index(label)
        except tk.TclError as e:
            raise AssertionError(f'menu has no {label!r} entry: {e}') from e

    def assert_context_menu_has(self, label: str):
        """Confirms the real right-click context menu (the single reused
        tk.Menu built once in UIComponents.create_context_menu) carries a
        command with this label."""
        self.assert_menu_has(self.app.ui.context_menu, label)

    def get_submenu(self, menu: tk.Menu, cascade_label: str) -> tk.Menu:
        """The tk.Menu a cascade item labeled `cascade_label` opens."""
        self.assert_menu_has(menu, cascade_label)
        index = menu.index(cascade_label)
        assert index is not None  # assert_menu_has above already confirmed this
        entry_type = menu.type(index)
        assert entry_type == 'cascade', (
            f'{cascade_label!r} is a {entry_type!r} entry, not a cascade'
        )
        submenu_name = menu.entrycget(index, 'menu')
        return menu.nametowidget(submenu_name)

    def assert_menu_path_has(self, *path: str) -> tk.Menu:
        """Confirms a full menu-bar path exists and is wired up, e.g.
        `assert_menu_path_has('File', 'Import Network', 'Import Resources...')`
        walks menu_bar -> the 'File' cascade -> the 'Import Network'
        cascade -> asserts 'Import Resources...' is a real entry there.
        Returns the menu containing the final path segment, so a scenario
        can go on to invoke it (e.g. `.invoke(label)`) instead of calling
        the handler directly."""
        assert path, 'assert_menu_path_has() needs at least one label'
        menu = self.app.ui.menu_bar
        for cascade_label in path[:-1]:
            menu = self.get_submenu(menu, cascade_label)
        self.assert_menu_has(menu, path[-1])
        return menu

    # -- projects ----------------------------------------------------------

    def new_project(self):
        """File -> New: TaskResourceManager.file_ops.new_project() resets
        the model to a single, blank default project ('Sample Project', no
        tasks, resources trimmed to just the first one) - but only after
        confirming via a Yes/No messagebox, which this patches rather than
        shows (same technique as create_task's simpledialog patch, just for
        messagebox.askyesno instead)."""
        self.assert_menu_path_has('File', 'New')
        with patch.object(messagebox, 'askyesno', return_value=True):
            self.app.file_ops.new_project()
        self.pump()

    def add_project(self, name: str, url: str = '', set_as_default: bool = False):
        """Projects -> Manage Projects... -> Add: a hand-built Toplevel
        (project list -> name/URL/CCPM-method/fever-chart fields -> Add/
        Update/Remove/Set as Default/Toggle Phase/Close), driven the same
        way assign_resource drives Edit Task Resources - find the real
        widgets and use them, not a single call to patch. Only the Name
        and URL entries matter for adding a project (the fever-chart/CCPM-
        method fields only feed Update on an already-selected project).
        With set_as_default=True, also selects the newly added row in the
        project list and clicks Set as Default before closing - a second
        project doesn't become default on its own (only the very first
        project ever added does), so task creation would otherwise keep
        landing in whatever project already was default."""
        self.assert_menu_path_has('Projects', 'Manage Projects...')
        self.app.task_ops.manage_projects_dialog(parent=self.app.root)
        self.pump()

        dialog = self._find_toplevel('Manage Projects')
        name_entry, url_entry, *_fever_entries = self._find_widgets(dialog, tk.Entry)

        name_entry.delete(0, tk.END)
        name_entry.insert(0, name)
        url_entry.delete(0, tk.END)
        url_entry.insert(0, url)
        self._find_button(dialog, 'Add').invoke()
        self.pump()

        project = next((p for p in self.model.projects if p['name'] == name), None)
        assert project is not None, f'add_project({name!r}) did not add a project'

        if set_as_default:
            listbox = self._find_widgets(dialog, tk.Listbox)[0]
            listbox.selection_clear(0, tk.END)
            listbox.selection_set(tk.END)
            listbox.event_generate('<<ListboxSelect>>')
            self.pump()
            self._find_button(dialog, 'Set as Default').invoke()
            self.pump()

        self._find_button(dialog, 'Close').invoke()
        self.pump()
        return project

    # -- dependencies ----------------------------------------------------

    def add_predecessor(
        self, task, predecessor_task, link_type: str = 'FS', lag: int = 0
    ):
        """Wires `predecessor_task -> task` via the exact handler the
        context menu's 'Add Predecessor...' command invokes
        (task_ops.add_predecessor_dialog) - same code path a real
        right-click would run, only the popped text-entry dialog is faked."""
        self.app.ui.update_context_menu_for_task(task)
        self.assert_context_menu_has('Add Predecessor')

        token = str(predecessor_task['task_id'])
        if link_type != 'FS' or lag:
            token += f':{link_type}{"+" if lag >= 0 else ""}{lag}'

        with patch.object(simpledialog, 'askstring', return_value=token):
            self.app.task_ops.add_predecessor_dialog(task)
        self.pump()

    # -- CCPM --------------------------------------------------------------

    def schedule_with_ccpm(self, project_name: str | None = None) -> str:
        """File -> Schedule with CCPM.... Returns the result dialog's text
        (raises with it on failure) - schedule_with_ccpm shows its own
        scrollable Toplevel (CcpmOperations._show_result_dialog) rather
        than a plain messagebox, so this reads that dialog's ScrolledText
        and closes it instead of patching messagebox like the driver's
        other assertions do.

        With exactly one project, CcpmOperations._pick_project
        auto-selects it and no chooser ever appears. With more than one,
        it pops its own hand-built Toplevel (project listbox + OK/Cancel)
        and blocks via wait_window() - a real modal like messagebox/
        simpledialog, but not a single call this driver can patch away.
        wait_window()'s nested loop still services root.after() timers
        (confirmed working the same way in visual_driver.py's dialogs), so
        arm an answer that way rather than trying to patch it. Pass
        `project_name` to pick a specific row; left as None, whatever's
        already selected (the model's default project) is accepted as-is."""
        self.assert_menu_path_has('File', 'Schedule with CCPM...')

        if len(self.model.projects) > 1:

            def answer_picker():
                dialog = self._find_toplevel('Schedule with CCPM')
                if project_name is not None:
                    listbox = self._find_widgets(dialog, tk.Listbox)[0]
                    names = list(listbox.get(0, tk.END))
                    listbox.selection_clear(0, tk.END)
                    listbox.selection_set(names.index(project_name))
                self._find_button(dialog, 'OK').invoke()

            self.root.after(10, answer_picker)

        self.app.ccpm_ops.schedule_with_ccpm()
        self.pump()

        toplevels = {
            w.title(): w
            for w in self.root.winfo_children()
            if isinstance(w, tk.Toplevel)
        }

        def read_and_close(dialog):
            text = self._find_widgets(dialog, scrolledtext.ScrolledText)[0].get(
                '1.0', 'end-1c'
            )
            dialog.destroy()
            return text

        for title in ('CCPM Error', 'CCPM Validation Failed'):
            if title in toplevels:
                text = read_and_close(toplevels[title])
                raise AssertionError(f'Schedule with CCPM failed: {title}: {text}')

        assert 'CCPM Schedule Created' in toplevels, (
            'Schedule with CCPM produced no result dialog'
        )
        return read_and_close(toplevels['CCPM Schedule Created'])

    # -- file ----------------------------------------------------------

    def save_as(self, file_path: str) -> str:
        """File -> Save As...: filedialog.asksaveasfilename is a native
        OS file picker, not a Tk widget at all - same category as
        messagebox.* (see schedule_with_ccpm's own docstring history: the
        CCPM result dialog used to be a messagebox and got replaced
        specifically because messagebox.* never becomes discoverable via
        winfo_children() on this system) - so this patches it rather than
        trying to find/drive it, the only way to answer it from the same
        thread. The success/error messagebox that follows a save is
        patched for the same reason."""
        self.assert_menu_path_has('File', 'Save As...')
        with (
            patch.object(filedialog, 'asksaveasfilename', return_value=file_path),
            patch.object(messagebox, 'showinfo'),
            patch.object(messagebox, 'showerror'),
        ):
            self.app.file_ops.save_file_as()
        self.pump()

        assert self.model.current_file_path == file_path, (
            f'save_as({file_path!r}) did not update current_file_path'
        )
        return file_path
