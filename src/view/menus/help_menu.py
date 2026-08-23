"""
Help menu for Our-Planner.

This module contains the UI components for the Help menu.
"""

import tkinter as tk
from tkinter import scrolledtext, ttk
import webbrowser
from src.utils.version import get_version
from src.utils.tk_helpers import add_resize_handle, mnemonic
from src.model.dependency_notation import format_predecessor_notation


class HelpMenu:
    """Implementation of the Help menu for Our-Planner."""

    def __init__(self, controller, root, menu_bar):
        """Initialize the help menu.

        Args:
            controller: The main application controller
            root: The root Tk window
            menu_bar: The main menu bar to add the Help menu to
        """
        self.controller = controller
        self.root = root

        # Create Help menu
        self.help_menu = tk.Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label='Help', menu=self.help_menu, underline=0)

        # Add menu items
        self.help_menu.add_command(
            label='Documentation',
            underline=mnemonic('Documentation', 'Documentation'),
            command=self.show_documentation,
        )
        self.help_menu.add_command(
            label='Website',
            underline=mnemonic('Website', 'Website'),
            command=self.open_website,
        )
        self.help_menu.add_command(
            label='Report Issues',
            underline=mnemonic('Report Issues', 'Report'),
            command=self.open_report_issues,
        )
        self.help_menu.add_command(
            label='About',
            underline=mnemonic('About', 'About'),
            command=self.show_about,
        )
        self.help_menu.add_command(
            label='Debug',
            # 2nd letter - 'D' is already Documentation's mnemonic above
            underline=mnemonic('Debug', 'Debug', 'e'),
            command=self.show_debug,
        )

    def show_documentation(self):
        """Show the user documentation."""
        # Create a documentation dialog
        doc_dialog = tk.Toplevel(self.root)
        doc_dialog.title('Our-Planner Documentation')
        doc_dialog.transient(self.root)
        doc_dialog.grab_set()
        doc_dialog.geometry('700x500')

        # Center the dialog
        doc_dialog.update_idletasks()
        width = doc_dialog.winfo_width()
        height = doc_dialog.winfo_height()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - width) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - height) // 2
        doc_dialog.geometry(f'+{x}+{y}')

        # Create a frame with padding
        frame = tk.Frame(doc_dialog, padx=20, pady=20)
        frame.pack(fill=tk.BOTH, expand=True)

        # Add a title
        title_label = tk.Label(
            frame,
            text='Our-Planner Documentation',
            font=('Arial', 16, 'bold'),
        )
        title_label.pack(pady=(0, 15))

        # Create a scrolled text widget for the documentation
        text_area = scrolledtext.ScrolledText(
            frame, wrap=tk.WORD, width=80, height=20, font=('Arial', 10)
        )
        text_area.pack(fill=tk.BOTH, expand=True, pady=10)

        # Add documentation content
        documentation = """
# Our-Planner - User Guide

## Basic Operations

### Creating Tasks
- Click and drag on the task grid to create a new task
- Enter a task name when prompted
- You can edit task properties later by right-clicking on the task

### Moving Tasks
- Click and drag a task to move it to a new position
- Tasks will snap to the grid when released

### Resizing Tasks
- Click and drag the left or right edge of a task to resize it

### Adding Dependencies
- Right-click on a task and select "Add Predecessor" or "Add Successor"
- You can also drag from the connection point on the right edge of a task to another task

### Editing Task Properties
- Right-click on a task to access the context menu
- Options include:
  - Edit Task Name
  - Edit Task URL
  - Edit Task Resources
  - Edit Task Tags
  - Edit Task Duration... (type an exact number of days instead of
    dragging the task's edge - handy for long tasks or a zoomed-out view)
  - Edit Task Color
  - Add Predecessor/Successor
  - Delete Task
- The same commands (plus a version that applies to every selected task
  at once) are also on the Edit > Task menu, for editing without the mouse

## Working with Resources

- Resources are shown in the bottom grid
- You can add, edit, and remove resources from the Edit menu
- Resource loading is calculated based on task allocations
- Overallocated resources are highlighted in red

## Tags and Filtering

- You can add tags to tasks and resources for organization
- Use the Tags menu to filter tasks and resources by tags
- Toggle tag display using the View menu

## Scheduling with CCPM

### Schedule with CCPM...
Validates the project's network, builds a critical-chain schedule
in-process, and imports the result as a NEW project next to the
source - the source project is left untouched, so a hand-drawn plan
and the CCPM-scheduled version can be compared side by side.

Resources are shared across every project in the file, so a resource
being scheduled here may already be committed to tasks in OTHER
projects over the same days. Before scheduling, a CCPM Scheduling
Options dialog offers "Account for capacity already committed to
other projects", checked by default: with it on, each resource's
exported capacity is reduced by its load from every other project's
tasks first, so the new schedule doesn't plan against capacity
someone else already has a claim on - any resource actually reduced
this way is named in the result dialog's Notes. Uncheck it to
schedule against each resource's full nominal capacity instead,
ignoring other projects entirely (the previous behaviour, still
available for when a resource pool genuinely isn't shared, or for
comparing against the unconstrained plan).

See Reports > Resource Over-Allocation... for the read-only,
whole-portfolio view of the same cross-project contention this
option feeds directly into scheduling.

### Export CCPM Network...
Writes the same network as tasks.csv/resources.csv/calendar.csv for
the external ccpm-scheduler CLI - a manual round trip; bring the
result back with Import CCPM Schedule... below. Applies the same
other-projects capacity reduction unconditionally, since this flow
has no dialog step to offer the choice in.

## Importing Your Project

### Import CCPM Schedule...
Use this when you already have a SCHEDULED CCPM network - a
`schedule.csv` (with start/finish days already computed) produced by
the external ccpm-scheduler tool, alongside its `resources.csv` and
optional `calendar.csv`. It's brought in as a new project.

### Import Network (a reference network with no schedule yet)
Use Network > Import Network for a plain task/resource network that
hasn't been scheduled yet (no start/finish days) - e.g. bringing in a
reference network to look at, or to schedule from within our-planner.
This is THREE separate steps, and they must be run IN THIS ORDER:

1. **Import Resources...** (`resources.csv`)
   - Required column: `id`
   - Optional columns: `name`, `capacity` (defaults to 1), `url`
   - An `id` that doesn't exist yet is created with the given
     name/capacity/url.
   - An `id` that already exists has its name/url updated (only where
     the cell isn't blank), and its capacity RESET to a single flat
     value equal to the CSV's `capacity` cell (replacing any per-day
     pattern - weekends-off, one-off overrides, etc. - it already had)
     if that cell is non-empty. Leave the `capacity` cell blank to keep
     an existing resource's current capacity configuration untouched.
     tags and weekend settings are never changed by this import either
     way. For per-day overrides instead of a flat reset, use Import
     Resource Calendars... below (or edit the resource directly via
     Edit Resources...).

2. **Import Resource Calendars...** (`calendar.csv`) - optional
   - Required columns: `resource_id`, `from`, `to`, `capacity`
   - Applies a per-day capacity override for the half-open day range
     `[from, to)` (`from` included, `to` excluded) to a resource that
     already exists. Every `resource_id` must already have been
     imported - if any doesn't exist, the whole import is cancelled and
     nothing is changed.

3. **Import Tasks...** (`tasks.csv`)
   - Required columns: `id`, `realistic_duration`, `resource_ids`
   - Optional columns: `name`, `predecessor_ids`, `optimal_duration`,
     `url`, `tags`, `colour`
   - `resource_ids` and `predecessor_ids` are both semicolon-separated
     lists of tokens - one token per resource/predecessor a task needs.
   - A `resource_ids` token is `resource_id:allocation` - `allocation`
     is how many concurrent units of that resource this task uses per
     day (whole or fractional). A bare id with no `:` means 1 whole
     unit. For example `1:1;2:2` assigns 1 unit of resource 1 AND 2
     units of resource 2 to the same task; `1` alone means the same as
     `1:1`.
   - A `predecessor_ids` token can include a link type and lag, e.g.
     `3:SS+2` (Start-to-Start, 2 days' lag); a bare id means
     Finish-to-Start.
   - An `id` that doesn't exist yet is created and placed
     automatically: a task with no predecessors starts on the
     project's current date; everything else is placed
     as-soon-as-possible after its predecessors, in a fresh empty row.
     This is a plain placement, not a full CCPM schedule - no resource
     leveling or buffers are added; use Schedule with CCPM... afterward
     if you want that.
   - An `id` that already exists only has its
     name/duration/resources/predecessors updated, at its CURRENT
     position on the grid - its state, notes, actual dates, and history
     are never touched by import.
   - Every `resource_ids` reference must already exist (Import
     Resources... first) and every `predecessor_ids` reference must
     resolve to either another row in the same file or an existing
     task. If anything doesn't resolve, the whole import is cancelled
     and nothing is changed - the error names exactly which task and
     which missing id caused it, so a bad row can't leave you with a
     half-imported network.
   - Every import shows a summary of what will be created/updated and
     asks you to confirm before making any changes.

## Exporting Your Project

- Use the Network > Export menu to save your project in various formats:
  - PDF: Complete report with tasks, resources, and loading
  - PNG: Image of the current view
  - CSV: Spreadsheet-compatible data tables (the counterpart to Import
    Network above)
  - HTML: Interactive web report

## Recording Status Updates & Reason Codes

- Record Remaining Duration... (task right-click menu, or Tasks menu)
  captures a task's updated remaining-duration estimate together with:
  - Reason - a primary reason from a fixed list (On Time, Task
    Variability, Waiting for Full Kit, Waiting for Resource, No Early
    Start, Parkinson's Law, Multitasking, Waiting in Backlog, Unplanned
    Events, Other / Unexplained). On Time is the default.
  - Note (optional) - free text detail, in a multi-line box.
- The point isn't just the number - it's letting the team periodically
  review recorded reasons together to spot root-cause patterns (e.g.
  "most of our buffer consumption is Waiting for Resource") and improve
  delivery performance.
- Where to see it:
  - View Duration History... (task right-click menu) - one task's full
    history, reason and note included.
  - Fever Chart's "Show Status Update Reasons/Notes" toggle - the
    annotated updates for a buffer's protected chain.
  - Reports > Status Update Log... - every recorded update for a
    project, with a Task URL column linking back to that task's own
    page, an "only annotated" filter, and a Download Data (CSV)...
    export.

## Recent Files

- File > Recent lists the 5 most recently opened/saved files, numbered
  1-5, most recent first - open the submenu and press the number key
  to reopen one without using the file picker.

## Versioned Project Folders

There is no undo for a plain project file - a mistake sticks unless you
remembered to Save As under a new name first. File > New Versioned
Project... creates an opt-in alternative: a fresh, empty directory backed
by a real local git repository, giving fine-grained undo/redo plus
deliberate save points. A plain File > Open/Save project is completely
unaffected - versioning only ever applies to a directory you deliberately
create this way (or later reopen the tracked file from), never to a
folder the app decides to adopt on its own.

Once a project is versioned (the window title shows "[versioned]"):

- Every meaningful edit is autosaved automatically to a local "autosave"
  branch - nothing to remember to save. A pure display toggle never
  creates a commit, only a real change to the project does.
- Edit > Undo (Ctrl+Z) / Redo (Ctrl+Y) step one autosaved edit at a time,
  like a conventional editor. A new edit made after undoing discards
  whatever was undone past.
- Edit > Jump to Version... lists the autosave history with real
  timestamps and jumps straight to one, instead of stepping through Undo
  repeatedly.
- File > Save Version... is a deliberate checkpoint: it squashes every
  autosaved edit since the last checkpoint into one clean, optionally
  named commit on the "main" branch, keeping main's history a short list
  of real versions rather than every individual edit.

Disaster recovery is manual, by design - this app never pushes anywhere
on your behalf. To back up a versioned project, open a terminal in the
workspace folder and add a normal git remote yourself (`git remote add
origin <url>`, then `git push origin main`) - only main's checkpoints are
meant to be pushed, autosave is purely local scratch history.

If git isn't installed, or has no user.name/user.email configured, New
Versioned Project... says so up front rather than creating a half-working
workspace.

## Keyboard Shortcuts

- Ctrl+0: Reset zoom
- Ctrl+A: Select all tasks
- Esc: Clear selections
- Ctrl+E: Open export dialog
- Ctrl+Z / Ctrl+Y: Undo / Redo the last autosaved edit - versioned
  projects only
        """

        text_area.insert(tk.END, documentation)

        # Make the text area read-only
        text_area.config(state=tk.DISABLED)

        # Add a Close button
        close_button = tk.Button(
            frame, text='Close', command=doc_dialog.destroy, width=10
        )
        close_button.pack(pady=(10, 0))

        # Bind Escape key to close dialog
        doc_dialog.bind('<Escape>', lambda e: doc_dialog.destroy())

        add_resize_handle(doc_dialog)

    def open_website(self):
        """Open the project website in the default browser."""
        webbrowser.open('https://github.com/rnwolf/our-planner')

    def open_report_issues(self):
        """Open the GitHub issues page in the default browser, so users
        can report bugs or request features directly."""
        webbrowser.open('https://github.com/rnwolf/our-planner/issues')

    def show_about(self):
        """Show the About dialog."""
        about_dialog = tk.Toplevel(self.root)
        about_dialog.title('About Our-Planner')
        about_dialog.transient(self.root)
        about_dialog.grab_set()

        # Make dialog modal
        about_dialog.focus_set()

        # The dialog sizes itself to its content - a hard-coded WxH risks
        # clipping the bottom-packed Close button; it is centered on the
        # parent once every widget exists (see the end of this method)

        # Add content
        frame = tk.Frame(about_dialog, padx=20, pady=20)
        frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title_label = tk.Label(frame, text='Our-Planner', font=('Arial', 16, 'bold'))
        title_label.pack(pady=(0, 10))

        # Version information - get from utility function
        version_text = f'Version {get_version()}'
        version_label = tk.Label(frame, text=version_text, font=('Arial', 10))
        version_label.pack(pady=2)

        # Author info
        author_label = tk.Label(frame, text='Created by R.N. Wolf', font=('Arial', 12))
        author_label.pack(pady=5)

        # Website link
        website_link = tk.Label(
            frame,
            text='www.rnwolf.net',
            fg='blue',
            cursor='hand2',
            font=('Arial', 12, 'underline'),
        )
        website_link.pack(pady=5)
        website_link.bind(
            '<Button-1>', lambda e: webbrowser.open('https://www.rnwolf.net')
        )

        # GitHub link
        github_link = tk.Label(
            frame,
            text='our-planner on GitHub',
            fg='blue',
            cursor='hand2',
            font=('Arial', 12, 'underline'),
        )
        github_link.pack(pady=5)
        github_link.bind(
            '<Button-1>',
            lambda e: webbrowser.open('https://github.com/rnwolf/our-planner'),
        )

        # ccpm-scheduler credit - the critical-chain scheduling engine
        # behind Schedule with CCPM.../Export CCPM Network..., one of the
        # application's key features
        ccpm_scheduler_link = tk.Label(
            frame,
            text='Critical Chain scheduling powered by ccpm-scheduler',
            fg='blue',
            cursor='hand2',
            font=('Arial', 12, 'underline'),
        )
        ccpm_scheduler_link.pack(pady=5)
        ccpm_scheduler_link.bind(
            '<Button-1>',
            lambda e: webbrowser.open('https://github.com/rnwolf/ccpm-scheduler'),
        )

        # link to license
        license_link = tk.Label(
            frame,
            text='LICENCE.txt',
            fg='blue',
            cursor='hand2',
            font=('Arial', 12, 'underline'),
        )
        license_link.pack(pady=5)
        license_link.bind(
            '<Button-1>',
            lambda e: webbrowser.open(
                'https://github.com/rnwolf/our-planner/blob/main/LICENSE.txt'
            ),
        )

        # Close button - <Return> invokes it while it has focus, and
        # Alt+C works from anywhere in the dialog, same convention as the
        # Add Task Note / Edit Task Tags dialogs' Save/Cancel/Add buttons
        close_button = tk.Button(
            frame,
            text='Close',
            underline=0,
            command=about_dialog.destroy,
            width=10,
        )
        close_button.pack(pady=(20, 0))
        close_button.bind('<Return>', lambda e: close_button.invoke())
        about_dialog.bind('<Alt-c>', lambda e: about_dialog.destroy())
        about_dialog.bind('<Alt-C>', lambda e: about_dialog.destroy())

        # Bind Escape key to close dialog
        about_dialog.bind('<Escape>', lambda e: about_dialog.destroy())

        # Center on the parent using the measured (requested) size - the
        # window isn't mapped yet, so winfo_width would still report 1
        about_dialog.update_idletasks()
        width = about_dialog.winfo_reqwidth()
        height = about_dialog.winfo_reqheight()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - width) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - height) // 2
        about_dialog.geometry(f'+{x}+{y}')

        # Visible resize handle, and never allow shrinking below the size
        # the content actually needs (measured, so font/theme-proof)
        ttk.Sizegrip(about_dialog).place(relx=1.0, rely=1.0, anchor='se')
        about_dialog.minsize(width, height)

    def show_debug(self):
        """Show the Debug dialog with information about selected tasks."""
        debug_dialog = tk.Toplevel(self.root)
        debug_dialog.title('Debug Information')
        debug_dialog.transient(self.root)
        debug_dialog.grab_set()

        # Make dialog modal
        debug_dialog.focus_set()

        # Position the dialog
        debug_dialog.geometry('600x400')

        # Center dialog on parent window
        debug_dialog.update_idletasks()
        width = debug_dialog.winfo_width()
        height = debug_dialog.winfo_height()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - width) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - height) // 2
        debug_dialog.geometry(f'+{x}+{y}')

        # Add content
        frame = tk.Frame(debug_dialog, padx=20, pady=20)
        frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title_label = tk.Label(
            frame, text='Debug Information', font=('Arial', 14, 'bold')
        )
        title_label.pack(pady=(0, 10))

        # Create scrolled text area
        text_area = scrolledtext.ScrolledText(frame, wrap=tk.WORD, width=70, height=15)
        text_area.pack(fill=tk.BOTH, expand=True, pady=10)

        # Insert debug info
        text_area.insert(tk.END, 'Selected Tasks:\n\n')

        # Get selected tasks info
        selected_tasks = self.controller.selected_tasks
        if selected_tasks:
            for i, task in enumerate(selected_tasks):
                text_area.insert(tk.END, f'Task {i + 1}:\n')
                text_area.insert(tk.END, f'  ID: {task["task_id"]}\n')
                text_area.insert(tk.END, f'  Description: {task["description"]}\n')
                project = self.controller.model.get_project_by_id(
                    task.get('project_id')
                )
                if project:
                    text_area.insert(
                        tk.END,
                        f'  Project: {project["name"]} ({project["phase"].capitalize()})\n',
                    )
                else:
                    text_area.insert(tk.END, '  Project: None\n')
                text_area.insert(
                    tk.END, f'  Row: {task["row"]}, Column: {task["col"]}\n'
                )
                text_area.insert(tk.END, f'  Duration: {task["duration"]}\n')

                # Calculate and show calendar dates
                start_date = self.controller.model.get_date_for_day(task['col'])
                end_date = self.controller.model.get_date_for_day(
                    task['col'] + task['duration'] - 1
                )
                text_area.insert(
                    tk.END, f'  Start Date: {start_date.strftime("%Y-%m-%d")}\n'
                )
                text_area.insert(
                    tk.END, f'  End Date: {end_date.strftime("%Y-%m-%d")}\n'
                )

                # Predecessors
                if task.get('predecessors'):
                    text_area.insert(
                        tk.END,
                        f'  Predecessors: {format_predecessor_notation(task["predecessors"])}\n',
                    )
                else:
                    text_area.insert(tk.END, '  Predecessors: None\n')

                # Successors (derived from other tasks' predecessor links)
                successor_ids = self.controller.model.get_successor_ids(task['task_id'])
                if successor_ids:
                    text_area.insert(
                        tk.END,
                        f'  Successors: {", ".join(map(str, successor_ids))}\n',
                    )
                else:
                    text_area.insert(tk.END, '  Successors: None\n')

                # Tags
                if 'tags' in task and task['tags']:
                    text_area.insert(tk.END, f'  Tags: {", ".join(task["tags"])}\n')
                else:
                    text_area.insert(tk.END, '  Tags: None\n')

                # Resources
                if task['resources']:
                    text_area.insert(tk.END, '  Resources:\n')
                    for resource_id, allocation in task['resources'].items():
                        resource = self.controller.model.get_resource_by_id(
                            int(resource_id)
                            if isinstance(resource_id, str)
                            else resource_id
                        )
                        if resource:
                            text_area.insert(
                                tk.END, f'    {resource["name"]}: {allocation}\n'
                            )
                else:
                    text_area.insert(tk.END, '  Resources: None\n')

                text_area.insert(tk.END, '\n')
        else:
            text_area.insert(tk.END, 'No tasks selected\n')

        # Add additional system info
        text_area.insert(tk.END, '\nSystem Information:\n')
        text_area.insert(tk.END, f'Current Date: {self.controller.model.setdate}\n')
        text_area.insert(tk.END, f'Zoom Level: {self.controller.zoom_level * 100}%\n')
        text_area.insert(tk.END, f'Total Tasks: {len(self.controller.model.tasks)}\n')
        text_area.insert(
            tk.END, f'Total Resources: {len(self.controller.model.resources)}\n'
        )

        # Make text area read-only
        text_area.config(state=tk.DISABLED)

        # Close button
        close_button = tk.Button(
            frame, text='Close', command=debug_dialog.destroy, width=10
        )
        close_button.pack(pady=(10, 0))

        # Refresh button
        refresh_button = tk.Button(
            frame,
            text='Refresh',
            command=lambda: self.refresh_debug_info(text_area),
            width=10,
        )
        refresh_button.pack(side=tk.LEFT, pady=(10, 0))

        # Bind Escape key to close dialog
        debug_dialog.bind('<Escape>', lambda e: debug_dialog.destroy())

        add_resize_handle(debug_dialog)

    def refresh_debug_info(self, text_area):
        """Refresh the debug information in the text area."""
        # Enable editing
        text_area.config(state=tk.NORMAL)

        # Clear current content
        text_area.delete(1.0, tk.END)

        # Insert updated debug info
        text_area.insert(tk.END, 'Selected Tasks:\n\n')

        # Get selected tasks info
        selected_tasks = self.controller.selected_tasks
        if selected_tasks:
            for i, task in enumerate(selected_tasks):
                text_area.insert(tk.END, f'Task {i + 1}:\n')
                text_area.insert(tk.END, f'  ID: {task["task_id"]}\n')
                text_area.insert(tk.END, f'  Description: {task["description"]}\n')
                project = self.controller.model.get_project_by_id(
                    task.get('project_id')
                )
                if project:
                    text_area.insert(
                        tk.END,
                        f'  Project: {project["name"]} ({project["phase"].capitalize()})\n',
                    )
                else:
                    text_area.insert(tk.END, '  Project: None\n')
                text_area.insert(
                    tk.END, f'  Row: {task["row"]}, Column: {task["col"]}\n'
                )
                text_area.insert(tk.END, f'  Duration: {task["duration"]}\n')

                # Calculate and show calendar dates
                start_date = self.controller.model.get_date_for_day(task['col'])
                end_date = self.controller.model.get_date_for_day(
                    task['col'] + task['duration'] - 1
                )
                text_area.insert(
                    tk.END, f'  Start Date: {start_date.strftime("%Y-%m-%d")}\n'
                )
                text_area.insert(
                    tk.END, f'  End Date: {end_date.strftime("%Y-%m-%d")}\n'
                )

                # Predecessors
                if task.get('predecessors'):
                    text_area.insert(
                        tk.END,
                        f'  Predecessors: {format_predecessor_notation(task["predecessors"])}\n',
                    )
                else:
                    text_area.insert(tk.END, '  Predecessors: None\n')

                # Successors (derived from other tasks' predecessor links)
                successor_ids = self.controller.model.get_successor_ids(task['task_id'])
                if successor_ids:
                    text_area.insert(
                        tk.END,
                        f'  Successors: {", ".join(map(str, successor_ids))}\n',
                    )
                else:
                    text_area.insert(tk.END, '  Successors: None\n')

                # Tags
                if 'tags' in task and task['tags']:
                    text_area.insert(tk.END, f'  Tags: {", ".join(task["tags"])}\n')
                else:
                    text_area.insert(tk.END, '  Tags: None\n')

                # Resources
                if task['resources']:
                    text_area.insert(tk.END, '  Resources:\n')
                    for resource_id, allocation in task['resources'].items():
                        resource = self.controller.model.get_resource_by_id(
                            int(resource_id)
                            if isinstance(resource_id, str)
                            else resource_id
                        )
                        if resource:
                            text_area.insert(
                                tk.END, f'    {resource["name"]}: {allocation}\n'
                            )
                else:
                    text_area.insert(tk.END, '  Resources: None\n')

                text_area.insert(tk.END, '\n')
        else:
            text_area.insert(tk.END, 'No tasks selected\n')

        # Add additional system info
        text_area.insert(tk.END, '\nSystem Information:\n')
        text_area.insert(tk.END, f'Current Date: {self.controller.model.setdate}\n')
        text_area.insert(tk.END, f'Zoom Level: {self.controller.zoom_level * 100}%\n')
        text_area.insert(tk.END, f'Total Tasks: {len(self.controller.model.tasks)}\n')
        text_area.insert(
            tk.END, f'Total Resources: {len(self.controller.model.resources)}\n'
        )

        # Make text area read-only again
        text_area.config(state=tk.DISABLED)
