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
from tkinter import scrolledtext, simpledialog, ttk
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
        x = col * self.app.cell_width
        y = row * self.app.task_height + self.app.task_height / 2
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

    def schedule_with_ccpm(self) -> str:
        """File -> Schedule with CCPM... against whatever single project
        exists (only one project means CcpmOperations._pick_project
        auto-selects it, no list dialog to answer). Returns the result
        dialog's text (raises with it on failure) - schedule_with_ccpm
        shows its own scrollable Toplevel (CcpmOperations.
        _show_result_dialog) rather than a plain messagebox, so this reads
        that dialog's ScrolledText and closes it instead of patching
        messagebox like the driver's other assertions do."""
        self.assert_menu_path_has('File', 'Schedule with CCPM...')

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
