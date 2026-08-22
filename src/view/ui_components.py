import os
import re
import subprocess
import textwrap
import tkinter as tk
from tkinter import messagebox, ttk
from tkinter import font as tkfont
from typing import Optional
import webbrowser
from datetime import datetime, timedelta
from src.view.menus.help_menu import HelpMenu
from src.utils.app_settings import load_settings
from src.utils.colors import (
    COLOR_NAMES,
    get_resource_load_color,
)
from src.utils.tk_helpers import add_resize_handle, mnemonic
from src.model.dependency_notation import (
    LINK_TYPES_ORDERED,
    BUFFER_LINK_TYPES,
    format_predecessor_notation,
)
from src.model.task_resource_model import (
    classify_fever_chart_zone,
    declutter_label_positions,
    fever_chart_display_point,
    fever_chart_title_lines,
    sorted_fever_chart_history,
)

# Wrap width for the task name at the top of the task tooltip - a plain
# character count (not pixels), tuned for this Label's default font.
TASK_NAME_TOOLTIP_WIDTH = 30


def wrap_task_name_for_tooltip(name, width=TASK_NAME_TOOLTIP_WIDTH, max_lines=2):
    """Wrap a task name to at most `max_lines` lines of `width` characters,
    truncating the last line with an ellipsis if it doesn't fit - so a long
    task name (whose centered label on the task box itself may be scrolled
    off-screen for a long-duration task) is still fully readable at a
    glance, without growing the tooltip unboundedly."""
    lines = textwrap.wrap(name, width=width) or ['']
    if len(lines) <= max_lines:
        return lines
    truncated = lines[:max_lines]
    ellipsis = '...'
    last = truncated[-1][: max(width - len(ellipsis), 0)].rstrip()
    truncated[-1] = last + ellipsis
    return truncated


class NoteFrame(tk.Frame):
    """A note item's container Frame, carrying the note's owning task id and
    its position in that task's notes list - stapled on at creation
    (_create_note_item) and read back by that note's delete button."""

    task_id: Optional[int]
    original_index: int
    display_index: int


class UIComponents:
    def __init__(self, controller, model):
        self.controller = controller
        self.model = model
        self.create_context_menu()

        # Track UI-specific task data
        self.task_ui_elements = {}  # Maps task_id to UI elements
        self.dependency_link_map = {}  # Maps arrow canvas item id to (predecessor_id, successor_id)

        # Reference to network menu
        # Reference to help menu
        self.help_menu = None

    def is_setdate_in_range(self):
        """Check if the setdate is within the visible timeline range"""
        timeline_end_date = self.model.start_date + timedelta(days=self.model.days - 1)
        return self.model.start_date <= self.model.setdate <= timeline_end_date

    def update_setdate_display(self):
        """Update the setdate display in the top-left corner with wider column"""
        # Update the "Current Date" label's font too - it's otherwise only
        # ever set once, at creation, so without this it stayed frozen at
        # its original size regardless of later font/zoom/base-font-size
        # changes, unlike the date text right below it.
        self.controller.timeline_label_canvas.itemconfig(
            self.setdate_label,
            font=('Arial', self.controller.timeline_font_size, 'bold'),
        )

        # Update the text with dynamic font size
        self.controller.timeline_label_canvas.itemconfig(
            self.setdate_text,
            text=self.model.setdate.strftime('%Y-%m-%d'),
            font=('Arial', self.controller.timeline_font_size + 1, 'bold'),
        )

        # Update the background color based on whether the date is in range
        in_range = self.is_setdate_in_range()
        self.controller.timeline_label_canvas.itemconfig(
            self.setdate_bg, fill='lightgreen' if in_range else 'red'
        )

        # Make sure the background rectangle covers the entire wider column
        self.controller.timeline_label_canvas.coords(
            self.setdate_bg,
            0,
            0,
            self.controller.label_column_width,
            self.controller.timeline_height,
        )

        # Re-center both text items too - their position is also derived
        # from label_column_width/timeline_height, which can change
        # independently of this method being called.
        self.controller.timeline_label_canvas.coords(
            self.setdate_label,
            self.controller.label_column_width / 2,
            self.controller.timeline_height / 3,
        )
        self.controller.timeline_label_canvas.coords(
            self.setdate_text,
            self.controller.label_column_width / 2,
            self.controller.timeline_height * 2 / 3,
        )

    def edit_setdate(self):
        """Open dialog to edit the setdate"""
        try:
            # Try to import tkcalendar for date selection
            from tkcalendar import Calendar

            # Create calendar dialog
            cal_dialog = tk.Toplevel(self.controller.root)
            cal_dialog.title('Set Current Date')
            cal_dialog.transient(self.controller.root)
            cal_dialog.grab_set()
            cal_dialog.bind('<Escape>', lambda e: cal_dialog.destroy())

            # Center dialog on parent window
            x = self.controller.root.winfo_rootx() + 50
            y = self.controller.root.winfo_rooty() + 50
            cal_dialog.geometry(f'+{x}+{y}')

            # Create calendar widget initialized with current setdate
            cal = Calendar(
                cal_dialog,
                selectmode='day',
                year=self.model.setdate.year,
                month=self.model.setdate.month,
                day=self.model.setdate.day,
            )
            cal.pack(padx=10, pady=(10, 5))

            # Keyboard-friendly alternative to clicking a day on the
            # calendar: tkcalendar.Calendar only ever binds <1> (mouse
            # click) on its day cells, nothing keyboard-driven at all
            # (confirmed directly against its source) - so this entry is
            # the only way to pick or confirm a date without a mouse.
            # Clicking the calendar keeps it in sync (below), and Set
            # Date/Enter always reads from here, not the calendar
            # directly, so either input method ends up in the same place.
            entry_frame = tk.Frame(cal_dialog)
            entry_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
            tk.Label(entry_frame, text='Date (YYYY-MM-DD):').pack(side=tk.LEFT)
            date_var = tk.StringVar(value=self.model.setdate.strftime('%Y-%m-%d'))
            date_entry = tk.Entry(entry_frame, textvariable=date_var, width=12)
            date_entry.pack(side=tk.LEFT, padx=5)

            def on_calendar_selected(event=None):
                date_var.set(cal.selection_get().strftime('%Y-%m-%d'))

            cal.bind('<<CalendarSelected>>', on_calendar_selected)

            def set_date():
                try:
                    year, month, day = map(int, date_var.get().strip().split('-'))
                    new_date = datetime(year, month, day)
                except (ValueError, IndexError):
                    messagebox.showerror(
                        'Invalid Date Format',
                        'Please enter a valid date in YYYY-MM-DD format.',
                        parent=cal_dialog,
                    )
                    return
                # Update model setdate
                self.model.setdate = new_date
                # Update display
                self.update_setdate_display()
                # Update timeline view to highlight the date if in range
                self.draw_timeline()
                cal_dialog.destroy()

            # Add buttons
            button_frame = tk.Frame(cal_dialog)
            button_frame.pack(pady=(0, 10))

            set_button = tk.Button(
                button_frame,
                text='Set Date',
                underline=mnemonic('Set Date', 'Set'),
                command=set_date,
            )
            set_button.pack(side=tk.LEFT, padx=5)
            cancel_button = tk.Button(
                button_frame,
                text='Cancel',
                underline=mnemonic('Cancel', 'Cancel'),
                command=cal_dialog.destroy,
            )
            cancel_button.pack(side=tk.LEFT, padx=5)

            # Alt-<letter> shortcuts, and <Return> bound directly on each
            # button since a plain tk.Button only binds <space> to invoke
            # itself by default, not <Return> (see e.g.
            # task_operations.edit_task_resources for the same fix).
            cal_dialog.bind('<Alt-s>', lambda e: set_date())
            cal_dialog.bind('<Alt-c>', lambda e: cal_dialog.destroy())
            for button in (set_button, cancel_button):
                button.bind('<Return>', lambda e, b=button: b.invoke())
            date_entry.bind('<Return>', lambda e: set_date())

            date_entry.focus_set()
            date_entry.select_range(0, tk.END)

            add_resize_handle(cal_dialog)

        except ImportError:
            # If tkcalendar is not available, use a simple date entry dialog
            self._manual_date_entry_dialog()

    def _manual_date_entry_dialog(self):
        """Fallback method for date entry if tkcalendar is not available"""
        dialog = tk.Toplevel(self.controller.root)
        dialog.title('Set Current Date')
        dialog.transient(self.controller.root)
        dialog.grab_set()
        dialog.bind('<Escape>', lambda e: dialog.destroy())

        # Center dialog on parent window
        x = self.controller.root.winfo_rootx() + 50
        y = self.controller.root.winfo_rooty() + 50
        # Position only - sized to content, with a measured minsize below
        dialog.geometry(f'+{x}+{y}')

        # Create form fields
        frame = tk.Frame(dialog, padx=20, pady=20)
        frame.pack(fill=tk.BOTH, expand=True)

        # Instruction
        tk.Label(frame, text='Enter date (YYYY-MM-DD):').pack(anchor='w', pady=(0, 10))

        # Date entry
        date_var = tk.StringVar(value=self.model.setdate.strftime('%Y-%m-%d'))
        date_entry = tk.Entry(frame, textvariable=date_var, width=15)
        date_entry.pack(fill=tk.X, pady=5)
        date_entry.select_range(0, tk.END)
        date_entry.focus_set()

        def set_date():
            try:
                # Parse date from string
                date_str = date_var.get().strip()
                year, month, day = map(int, date_str.split('-'))
                new_date = datetime(year, month, day)

                # Update model setdate
                self.model.setdate = new_date
                # Update display
                self.update_setdate_display()
                # Update timeline view to highlight the date if in range
                self.draw_timeline()
                dialog.destroy()
            except (ValueError, IndexError):
                messagebox.showerror(
                    'Invalid Date Format',
                    'Please enter a valid date in YYYY-MM-DD format.',
                    parent=dialog,
                )

        # Add buttons
        button_frame = tk.Frame(frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        set_button = tk.Button(
            button_frame,
            text='Set Date',
            underline=mnemonic('Set Date', 'Set'),
            command=set_date,
        )
        set_button.pack(side=tk.RIGHT, padx=5)
        cancel_button = tk.Button(
            button_frame,
            text='Cancel',
            underline=mnemonic('Cancel', 'Cancel'),
            command=dialog.destroy,
        )
        cancel_button.pack(side=tk.RIGHT, padx=5)

        # Bind Enter key - a dialog-wide catch is enough here (unlike
        # dialogs with more than one meaningful action) since a plain
        # tk.Button doesn't consume <Return> itself by default, so it
        # still bubbles up to this binding even when a button has focus.
        dialog.bind('<Return>', lambda e: set_date())
        dialog.bind('<Alt-s>', lambda e: set_date())
        dialog.bind('<Alt-c>', lambda e: dialog.destroy())

        add_resize_handle(dialog)

    def reset_setdate_to_today(self):
        """Reset the setdate to today's date"""
        self.model.setdate = datetime.now().replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        self.update_setdate_display()
        # Update timeline view to highlight the date if in range
        self.draw_timeline()

    def create_menu_bar(self):
        """Create the menu bar with file operations"""
        self.menu_bar = tk.Menu(self.controller.root)
        self.controller.root.config(menu=self.menu_bar)

        # File menu (Alt+F)
        self.file_menu = tk.Menu(
            self.menu_bar, tearoff=0, postcommand=self.refresh_file_menu_state
        )
        self.menu_bar.add_cascade(label='File', menu=self.file_menu, underline=0)

        # File operations - accelerator= is display-only in Tk, so each of
        # these also needs the matching root.bind() below to actually work.
        self.file_menu.add_command(
            label='New',
            underline=mnemonic('New', 'New'),
            accelerator='Ctrl+N',
            command=self.controller.file_ops.new_project,
        )
        self.file_menu.add_command(
            label='Open...',
            underline=mnemonic('Open...', 'Open'),
            accelerator='Ctrl+O',
            command=self.controller.file_ops.open_file,
        )

        # Rebuilt just before it's shown (postcommand) rather than kept in
        # sync from every open/save call site - so it can never drift out
        # of date with ~/.our-planner/settings.json's recent_files list.
        self.recent_files_menu = tk.Menu(
            self.file_menu, tearoff=0, postcommand=self.refresh_recent_files_menu
        )
        self.file_menu.add_cascade(
            label='Recent',
            menu=self.recent_files_menu,
            underline=mnemonic('Recent', 'Recent'),
        )

        self.file_menu.add_command(
            label='Save',
            underline=mnemonic('Save', 'Save'),
            accelerator='Ctrl+S',
            command=self.controller.file_ops.save_file,
        )
        self.file_menu.add_command(
            label='Save As...',
            underline=mnemonic('Save As...', 'As'),
            accelerator='Ctrl+Shift+S',
            command=self.controller.file_ops.save_file_as,
        )
        self.file_menu.add_separator()
        self.file_menu.add_command(
            label='New Versioned Project...',
            # 'V' is Save Version's mnemonic below - anchor to 'Project'
            # instead so the two don't collide.
            underline=mnemonic('New Versioned Project...', 'Project'),
            command=self.controller.version_control_ops.new_versioned_project,
        )
        self.file_menu.add_command(
            label='Save Version...',
            underline=mnemonic('Save Version...', 'Version'),
            command=self.controller.version_control_ops.save_version,
        )
        self.file_menu.add_separator()
        self.file_menu.add_command(
            label='Import CCPM Schedule...',
            underline=mnemonic('Import CCPM Schedule...', 'Import'),
            command=self.controller.file_ops.import_ccpm_schedule,
        )

        # Import Network: a plain, unscheduled reference network (tasks with
        # predecessor_ids/resource_ids, no start/finish yet) - Import CCPM
        # Schedule above needs an already-scheduled schedule.csv, which this
        # doesn't have. Three deliberately separate steps, in the order they
        # must run: resources, then their calendars, then tasks (each task's
        # resource_ids must already exist).
        self.import_network_menu = tk.Menu(self.file_menu, tearoff=0)
        self.file_menu.add_cascade(
            label='Import Network',
            menu=self.import_network_menu,
            # the 'w' - 'I' is already Import CCPM Schedule's mnemonic above
            underline=mnemonic('Import Network', 'Network', 'w'),
        )
        self.import_network_menu.add_command(
            label='Import Resources...',
            underline=mnemonic('Import Resources...', 'Resources'),
            command=self.controller.file_ops.import_resources,
        )
        self.import_network_menu.add_command(
            label='Import Resource Calendars...',
            underline=mnemonic('Import Resource Calendars...', 'Calendars'),
            command=self.controller.file_ops.import_resource_calendars,
        )
        self.import_network_menu.add_command(
            label='Import Tasks...',
            underline=mnemonic('Import Tasks...', 'Tasks'),
            command=self.controller.file_ops.import_tasks,
        )

        self.file_menu.add_command(
            label='Export CCPM Network...',
            underline=mnemonic('Export CCPM Network...', 'CCPM'),
            command=self.controller.ccpm_ops.export_ccpm_network,
        )
        self.file_menu.add_command(
            label='Schedule with CCPM...',
            # 'S' is Save's mnemonic above - use 'h' instead so File's
            # underlines don't collide.
            underline=mnemonic('Schedule with CCPM...', 'Schedule', 'h'),
            command=self.controller.ccpm_ops.schedule_with_ccpm,
        )
        self.file_menu.add_separator()
        self.file_menu.add_command(
            label='Exit',
            underline=mnemonic('Exit', 'Exit', 'x'),  # 'E' is Export's mnemonic below
            command=self.controller.root.quit,
        )

        # Add separator and export commands
        self.file_menu.add_separator()
        self.file_menu.add_command(
            label='Export...',
            underline=mnemonic('Export...', 'Export'),
            command=self.controller.export_ops.open_export_dialog,
        )

        # Edit menu (Alt+E)
        self.edit_menu = tk.Menu(
            self.menu_bar, tearoff=0, postcommand=self.refresh_edit_menu_state
        )
        self.menu_bar.add_cascade(label='Edit', menu=self.edit_menu, underline=0)

        # Undo/Redo (versioned projects only - see refresh_edit_menu_state):
        # git-backed, stepping one autosave commit at a time. At the top,
        # above Task, matching the universal convention.
        self.edit_menu.add_command(
            label='Undo',
            underline=mnemonic('Undo', 'Undo'),
            accelerator='Ctrl+Z',
            command=self.controller.version_control_ops.undo,
        )
        self.edit_menu.add_command(
            label='Redo',
            # 'R' is Edit Resources...'s mnemonic below - anchor to the
            # 2nd letter instead so the two don't collide.
            underline=mnemonic('Redo', 'Redo', 'd'),
            accelerator='Ctrl+Y',
            command=self.controller.version_control_ops.redo,
        )
        self.edit_menu.add_command(
            label='Jump to Version...',
            underline=mnemonic('Jump to Version...', 'Jump'),
            command=self.controller.version_control_ops.jump_to_version,
        )
        self.edit_menu.add_separator()

        # Task submenu (Alt+E, T) - keyboard access to the same "Edit Task
        # ..." commands the right-click context menu offers, for editing
        # whatever task is currently selected without needing the mouse.
        self.edit_task_menu = tk.Menu(self.edit_menu, tearoff=0)
        self.edit_menu.add_cascade(label='Task', menu=self.edit_task_menu, underline=0)

        self.edit_task_menu.add_command(
            label='Edit Task Name',
            underline=10,  # the N
            command=lambda: self.controller.task_ops.edit_task_name(
                parent=self.controller.root
            ),
        )
        self.edit_task_menu.add_command(
            label='Edit Task URL',
            underline=10,  # the U
            command=self.controller.task_ops.edit_task_url,
        )
        self.edit_task_menu.add_command(
            label='Edit Task Project...',
            underline=10,  # the P
            command=lambda: self.controller.task_ops.edit_task_project(
                self.controller.selected_task
            ),
        )
        self.edit_task_menu.add_command(
            label='Edit Task Chain...',
            underline=10,  # the C
            command=lambda: self.controller.task_ops.edit_task_chain(
                self.controller.selected_task
            ),
        )
        self.edit_task_menu.add_command(
            label='Edit Task Resources',
            underline=10,  # the R
            command=lambda: self.controller.task_ops.edit_task_resources(
                self.controller.selected_task
            ),
        )
        self.edit_task_menu.add_command(
            label='Edit Task Tags',
            underline=10,  # the T
            command=lambda: self.controller.tag_ops.edit_task_tags(
                self.controller.selected_task
            ),
        )
        self.edit_task_menu.add_command(
            label='Edit Task Duration...',
            underline=10,  # the D
            command=lambda: self.controller.task_ops.edit_task_duration(
                [self.controller.selected_task]
            ),
        )

        # Color submenu, same web-color list as the context menu's
        self.edit_task_color_menu = tk.Menu(self.edit_task_menu, tearoff=0)
        self.edit_task_menu.add_cascade(
            label='Edit Task Color',
            menu=self.edit_task_color_menu,
            underline=11,  # the O - the C is already Chain's mnemonic above
        )
        for color_name in COLOR_NAMES:
            self.edit_task_color_menu.add_command(
                label=color_name,
                command=lambda c=color_name: self.set_selected_task_color(c),
                background=color_name,
            )

        self.edit_menu.add_separator()

        # Edit operations
        self.edit_menu.add_command(
            label='Add Resource...',
            underline=mnemonic('Add Resource...', 'Add'),
            command=lambda: self.controller.task_ops.add_resource(
                parent=self.controller.root
            ),
        )
        self.edit_menu.add_command(
            label='Edit Resources...',
            underline=mnemonic('Edit Resources...', 'Resources'),
            command=lambda: self.controller.task_ops.edit_resources(
                parent=self.controller.root
            ),
        )
        self.edit_menu.add_separator()
        self.edit_menu.add_command(
            label='Project Settings...',
            underline=mnemonic('Project Settings...', 'Project'),
            command=lambda: self.controller.task_ops.edit_project_settings(
                parent=self.controller.root
            ),
        )

        # Tasks menu (Alt+T)
        self.tasks_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label='Tasks', menu=self.tasks_menu, underline=0)

        # Keyboard-only status-update flow: Alt+T, S -> type id, Enter
        # (grid scrolls to the task and selects it), then Alt+T, R ->
        # enter the remaining days. No mouse required.
        self.tasks_menu.add_command(
            label='Select Task by ID...',
            underline=0,
            command=lambda: self.controller.task_ops.select_task_by_id(
                parent=self.controller.root
            ),
        )
        self.tasks_menu.add_command(
            label='Record Remaining Duration...',
            underline=0,
            command=lambda: self.controller.task_ops.record_remaining_duration(),
        )
        self.tasks_menu.add_command(
            label='Add Note...',
            underline=4,  # the N - Alt+T, N
            command=lambda: self.controller.task_ops.add_note_to_task(),
        )
        self.tasks_menu.add_separator()

        self.auto_scheduling_var = tk.BooleanVar(value=False)
        self.tasks_menu.add_checkbutton(
            label='Auto Scheduling',
            underline=mnemonic('Auto Scheduling', 'Auto'),
            variable=self.auto_scheduling_var,
            command=self.controller.toggle_auto_scheduling,
        )
        self.tasks_menu.add_separator()
        self.tasks_menu.add_command(
            label='Delete Selected',
            underline=0,
            accelerator='Del',
            command=self.controller.task_ops.delete_selected_tasks,
        )

        # Filter menu (Stage 11 - renamed from 'Tags' now that project-based
        # filtering sits alongside tag-based filtering; 'Tags' no longer
        # described what this menu does)
        # (Alt+I - 'F' is taken by the File menu, so the mnemonic is the 'i')
        self.filter_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label='Filter', menu=self.filter_menu, underline=1)

        self.filter_menu.add_command(
            label='Filter Tasks by Tags...',
            underline=mnemonic('Filter Tasks by Tags...', 'Tags'),
            command=self.controller.tag_ops.filter_tasks_by_tags,
        )
        self.filter_menu.add_command(
            label='Filter Tasks by Project...',
            underline=mnemonic('Filter Tasks by Project...', 'Project'),
            command=self.controller.tag_ops.filter_tasks_by_project,
        )
        self.filter_menu.add_command(
            label='Filter Tasks by State...',
            underline=mnemonic('Filter Tasks by State...', 'State'),
            command=self.controller.tag_ops.filter_tasks_by_state,
        )
        self.filter_menu.add_command(
            label='Filter Tasks by Full-Kit Readiness...',
            underline=mnemonic('Filter Tasks by Full-Kit Readiness...', 'Full-Kit'),
            command=self.controller.tag_ops.filter_tasks_by_fullkit,
        )
        self.filter_menu.add_command(
            label='Filter Tasks by Planned Start...',
            # the 'l' - 'P' is already "...by Project..." above, 'S' is
            # already "...by State..." above
            underline=mnemonic('Filter Tasks by Planned Start...', 'Planned', 'l'),
            command=self.controller.tag_ops.filter_tasks_by_start_window,
        )
        self.filter_menu.add_command(
            label='Filter Resources by Tags...',
            underline=mnemonic('Filter Resources by Tags...', 'Resources'),
            command=self.controller.tag_ops.filter_resources_by_tags,
        )
        self.filter_menu.add_command(
            label='Filter Resources by Project...',
            # the 2nd letter of "Project" - 'P' is taken by the Resources
            # mnemonic just above reading differently ('R'), but 'Project'
            # itself would repeat "...Tasks by Project..."'s 'P' above
            underline=mnemonic('Filter Resources by Project...', 'Project', 'r'),
            command=self.controller.tag_ops.filter_resources_by_project,
        )
        self.filter_menu.add_separator()
        self.filter_menu.add_command(
            label='Select Tasks by Tags...',
            # the 2nd letter of "Select" - 'S' is "...by State..." above,
            # 'T' is "...by Tags..." above
            underline=mnemonic('Select Tasks by Tags...', 'Select', 'e'),
            command=self.controller.tag_ops.select_tasks_by_tag,
        )
        self.filter_menu.add_command(
            label='Toggle Multi-Select Mode',
            # 'Multi' - 'T' is already "...by Tags..." above
            underline=mnemonic('Toggle Multi-Select Mode', 'Multi'),
            command=self.controller.toggle_multi_select_mode,
        )
        self.filter_menu.add_separator()
        self.filter_menu.add_command(
            label='Clear All Filters',
            underline=mnemonic('Clear All Filters', 'Clear'),
            command=self.controller.clear_all_filters,
        )

        # View menu (new)
        self.view_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label='View', menu=self.view_menu, underline=0)

        # View options for tags
        self.show_tags_var = tk.BooleanVar(value=True)
        self.view_menu.add_checkbutton(
            label='Show Tags on Tasks',
            underline=mnemonic('Show Tags on Tasks', 'Show'),
            variable=self.show_tags_var,
            command=self.controller.update_view,
        )

        # A long description routinely overflows a short-duration task's own
        # box - the box itself stays the click/drag/resize target (see
        # draw_task), so that overflowing text just looks clickable without
        # being it. Hiding the description (keeping the id, which is short
        # enough to always fit) is the direct fix; off by default would
        # equally direct-fix it but silently drops information most users
        # want, so this defaults on like Show Tags on Tasks does.
        self.show_task_names_var = tk.BooleanVar(value=True)
        self.view_menu.add_checkbutton(
            label='Show Task Names',
            underline=mnemonic('Show Task Names', 'Task'),
            variable=self.show_task_names_var,
            command=self.controller.update_view,
        )

        # Add notes panel toggle to the View menu
        self.view_menu.add_separator()
        self.view_menu.add_command(
            label='Toggle Notes Panel',
            underline=mnemonic('Toggle Notes Panel', 'Notes'),
            command=self.controller.toggle_notes_panel,
        )

        # Add zoom options
        self.view_menu.add_separator()
        self.view_menu.add_command(
            label='Reset Zoom (Ctrl+0)',
            underline=mnemonic('Reset Zoom (Ctrl+0)', 'Reset'),
            command=self.controller.reset_zoom,
        )

        # Date menu
        self.date_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label='Date', menu=self.date_menu, underline=0)

        # Date operations
        self.date_menu.add_command(
            label='Set Current Date...',
            underline=mnemonic('Set Current Date...', 'Set'),
            command=self.edit_setdate,
        )
        self.date_menu.add_command(
            label='Reset to Today',
            underline=mnemonic('Reset to Today', 'Reset'),
            command=self.reset_setdate_to_today,
        )
        self.date_menu.add_separator()
        self.date_menu.add_command(
            label='Extend Timeline...',
            underline=mnemonic('Extend Timeline...', 'Extend'),
            command=self.controller.task_ops.extend_timeline_dialog,
        )
        self.date_menu.add_command(
            label='Delete History...',
            underline=mnemonic('Delete History...', 'Delete'),
            command=self.controller.task_ops.delete_history_dialog,
        )

        # Projects menu
        self.projects_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(
            label='Projects', menu=self.projects_menu, underline=0
        )

        self.projects_menu.add_command(
            label='Manage Projects...',
            underline=mnemonic('Manage Projects...', 'Manage'),
            command=lambda: self.controller.task_ops.manage_projects_dialog(
                parent=self.controller.root
            ),
        )

        # Reports menu (Stage 10 Part B) - a single home for every report
        # type, old and new. Fever Charts (Stage 8) moved here unchanged;
        # Full-Kit Readiness is the first report built against the new
        # framework, reusing whatever the Filter menu currently selects.
        self.reports_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label='Reports', menu=self.reports_menu, underline=0)

        self.reports_menu.add_command(
            label='Project Fever Charts...',
            underline=mnemonic('Project Fever Charts...', 'Fever'),
            command=lambda: self.controller.task_ops.view_project_fever_charts(),
        )
        self.reports_menu.add_command(
            label='Full-Kit Readiness...',
            # 'Readiness' - 'F' is already the Fever Charts mnemonic above
            underline=mnemonic('Full-Kit Readiness...', 'Readiness'),
            command=lambda: self.controller.report_ops.view_fullkit_readiness_report(),
        )
        self.reports_menu.add_command(
            label='Status Update Log...',
            underline=mnemonic('Status Update Log...', 'Status'),
            command=lambda: self.controller.report_ops.view_status_update_log(),
        )
        self.reports_menu.add_command(
            label='Resource Over-Allocation...',
            underline=mnemonic('Resource Over-Allocation...', 'Over-Allocation'),
            command=lambda: (
                self.controller.report_ops.view_resource_overallocation_report()
            ),
        )
        self.reports_menu.add_command(
            label='Resource Schedule...',
            underline=mnemonic('Resource Schedule...', 'Schedule'),
            command=lambda: self.controller.report_ops.view_resource_schedule_report(),
        )

        # Network Graph (Stage 18) - the interactive dependency-graph view
        # from the external ccpm-scheduler, for any set of tasks
        self.network_graph_menu = tk.Menu(self.reports_menu, tearoff=0)
        self.reports_menu.add_cascade(
            label='Network Graph', menu=self.network_graph_menu
        )
        self.network_graph_menu.add_command(
            label='Selected Tasks',
            command=lambda: self.controller.report_ops.view_network_graph_selected(),
        )
        self.network_graph_menu.add_command(
            label='Project...',
            command=lambda: self.controller.report_ops.view_network_graph_project(),
        )

        # Add Help menu
        self.help_menu = HelpMenu(self.controller, self.controller.root, self.menu_bar)

    def refresh_edit_menu_state(self):
        """Edit menu's own postcommand: Undo/Redo are enabled only while
        the open project is versioned AND there's actually somewhere for
        them to go (not already at the oldest/newest autosave commit).
        Jump to Version... only needs the project to be versioned at all."""
        vc_ops = self.controller.version_control_ops
        versioned = self.controller.version_control is not None
        self.edit_menu.entryconfig(
            'Undo', state=tk.NORMAL if vc_ops.can_undo() else tk.DISABLED
        )
        self.edit_menu.entryconfig(
            'Redo', state=tk.NORMAL if vc_ops.can_redo() else tk.DISABLED
        )
        self.edit_menu.entryconfig(
            'Jump to Version...', state=tk.NORMAL if versioned else tk.DISABLED
        )

    def refresh_file_menu_state(self):
        """File menu's own postcommand: enables Save Version... only while
        the open project is a versioned workspace - save_version() itself
        also no-ops when it isn't, but a visibly disabled item is clearer
        than a silently inert click."""
        state = (
            tk.NORMAL if self.controller.version_control is not None else tk.DISABLED
        )
        self.file_menu.entryconfig('Save Version...', state=state)

    def refresh_recent_files_menu(self):
        """File > Recent's postcommand: rebuild its entries from
        ~/.our-planner/settings.json right before the submenu is shown, so
        it always reflects the latest open/save regardless of how it
        changed (this session, or a previous one). Each entry is labeled
        with its position ('1 plan.json', '2 other.json', ...) and
        underlined on that digit, so once the submenu is open, the digit
        key alone opens that file - no mouse needed."""
        self.recent_files_menu.delete(0, 'end')
        recent_files = load_settings()['recent_files']
        if not recent_files:
            self.recent_files_menu.add_command(
                label='(No recent files)', state=tk.DISABLED
            )
            return
        for index, path in enumerate(recent_files, start=1):
            self.recent_files_menu.add_command(
                label=f'{index} {os.path.basename(path)}',
                underline=0,
                command=lambda p=path: self.controller.file_ops.open_recent_file(p),
            )

    def create_timeline_frame(self):
        """Create the timeline canvas with horizontal scrolling and wider label column"""
        self.timeline_frame = tk.Frame(self.controller.main_frame)
        self.timeline_frame.pack(fill=tk.X, pady=(0, 5))

        # Create a fixed label column on the left with wider width
        self.controller.timeline_label_frame = tk.Frame(
            self.timeline_frame, width=self.controller.label_column_width
        )
        self.controller.timeline_label_frame.pack(side=tk.LEFT, fill=tk.Y)
        self.controller.timeline_label_canvas = tk.Canvas(
            self.controller.timeline_label_frame,
            width=self.controller.label_column_width,
            height=self.controller.timeline_height,
            bg='lightgray',
            highlightthickness=0,
        )
        self.controller.timeline_label_canvas.pack(fill=tk.BOTH)

        # Create setdate display with initial background
        self.setdate_bg = self.controller.timeline_label_canvas.create_rectangle(
            0,
            0,
            self.controller.label_column_width,
            self.controller.timeline_height,
            fill='green' if self.is_setdate_in_range() else 'red',
            outline='',
        )

        # Add "Current Date" label with dynamic font size
        self.setdate_label = self.controller.timeline_label_canvas.create_text(
            self.controller.label_column_width / 2,
            self.controller.timeline_height / 3,
            text='Current Date',
            anchor='center',
            font=('Arial', self.controller.timeline_font_size, 'bold'),
        )

        # Add the actual date with dynamic font size
        self.setdate_text = self.controller.timeline_label_canvas.create_text(
            self.controller.label_column_width / 2,
            self.controller.timeline_height * 2 / 3,
            text=self.model.setdate.strftime('%Y-%m-%d'),
            anchor='center',
            font=('Arial', self.controller.timeline_font_size + 1, 'bold'),
        )

        # Create timeline canvas with horizontal scrollbar
        self.timeline_scroll_frame = tk.Frame(self.timeline_frame)
        self.timeline_scroll_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.controller.timeline_canvas = tk.Canvas(
            self.timeline_scroll_frame,
            height=self.controller.timeline_height,
            bg='white',
            highlightthickness=1,
            highlightbackground='gray',
        )
        self.controller.timeline_canvas.pack(side=tk.TOP, fill=tk.X)

        # Horizontal scrollbar for timeline
        self.controller.h_scrollbar = ttk.Scrollbar(
            self.controller.main_frame,
            orient=tk.HORIZONTAL,
            command=self.sync_horizontal_scroll,
        )
        self.controller.h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)

        # Configure timeline canvas for scrolling
        self.controller.timeline_canvas.config(
            xscrollcommand=self.controller.h_scrollbar.set,
            scrollregion=(
                0,
                0,
                self.controller.cell_width * self.model.days,
                self.controller.timeline_height,
            ),
        )

    def create_task_grid_frame(self):
        """Create the task grid canvas with both horizontal and vertical scrolling and wider label column"""
        self.task_frame = tk.Frame(
            self.controller.main_frame, height=self.controller.task_grid_height
        )
        # No expand=True: the split between this frame and resource_frame is
        # driven entirely by on_main_frame_configure/on_resizer_drag, which
        # explicitly set both frames' heights - letting Tk's own pack expand
        # also compete for space here caused unpredictable equal-split
        # behavior between the two frames that fought against those explicit
        # heights.
        self.task_frame.pack(fill=tk.BOTH, pady=(0, 5))
        self.task_frame.pack_propagate(False)  # Prevent frame from shrinking

        # Create a fixed label column on the left with wider width
        self.controller.task_label_frame = tk.Frame(
            self.task_frame, width=self.controller.label_column_width
        )
        self.controller.task_label_frame.pack(side=tk.LEFT, fill=tk.Y)
        self.controller.task_label_canvas = tk.Canvas(
            self.controller.task_label_frame,
            width=self.controller.label_column_width,
            bg='lightgray',
            highlightthickness=0,
        )
        self.controller.task_label_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Create task canvas with vertical scrollbar
        self.task_scroll_frame = tk.Frame(self.task_frame)
        self.task_scroll_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.controller.v_scrollbar = ttk.Scrollbar(
            self.task_scroll_frame, orient=tk.VERTICAL
        )
        self.controller.v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.controller.task_canvas = tk.Canvas(
            self.task_scroll_frame,
            bg='white',
            highlightthickness=1,
            highlightbackground='gray',
            yscrollcommand=self.controller.v_scrollbar.set,
        )
        self.controller.task_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Connect scrollbar to canvas
        self.controller.v_scrollbar.config(command=self.sync_vertical_scroll)

        # Configure task canvas for scrolling
        self.controller.task_canvas.config(
            xscrollcommand=self.controller.h_scrollbar.set,
            scrollregion=(
                0,
                0,
                self.controller.cell_width * self.model.days,
                self.model.max_rows * self.controller.task_height,
            ),
        )

        # Bind mouse events for task manipulation
        self.controller.task_canvas.bind(
            '<ButtonPress-1>', self.controller.task_ops.on_task_press
        )
        self.controller.task_canvas.bind(
            '<B1-Motion>', self.controller.task_ops.on_task_drag
        )
        self.controller.task_canvas.bind(
            '<ButtonRelease-1>', self.controller.task_ops.on_task_release
        )
        self.controller.task_canvas.bind(
            '<Motion>', self.controller.task_ops.on_task_hover
        )
        # <Motion> only fires while the cursor is inside the canvas, so
        # moving off a task straight out of the canvas entirely (rather
        # than via empty grid space first) never re-triggered on_task_hover
        # to reset the cursor/hover-status label - <Leave> fires
        # specifically for "cursor exited this widget" and closes that gap.
        self.controller.task_canvas.bind(
            '<Leave>', self.controller.task_ops.reset_hover_state
        )
        self.controller.task_canvas.bind(
            '<ButtonPress-3>', self.controller.task_ops.on_right_click
        )

        # Arrow-key grid navigation - the scrollbars are thin and fiddly to
        # grab precisely, especially once zoomed in. Bound on root rather
        # than task_canvas specifically: root.bind() only needs the *window*
        # to have OS-level keyboard focus (true as soon as the user clicks
        # anywhere in it), whereas binding to one specific child widget
        # depends on that widget holding Tk's internal focus too - a much
        # more fragile, window-manager-dependent thing that isn't
        # guaranteed to follow a plain click on every platform/WM. Every
        # text-entry widget in this app (date entry, tag entry, etc.) lives
        # inside a grab_set()'d dialog, so a dialog's own arrow-key use
        # (cursor movement, list navigation) still can't be interfered with
        # here - a dialog's local grab blocks root-level bindings entirely
        # while it's open.
        self.controller.root.bind(
            '<Left>', lambda e: self.controller.scroll_task_grid(dx_cells=-1)
        )
        self.controller.root.bind(
            '<Right>', lambda e: self.controller.scroll_task_grid(dx_cells=1)
        )
        self.controller.root.bind(
            '<Up>', lambda e: self.controller.scroll_task_grid(dy_rows=-1)
        )
        self.controller.root.bind(
            '<Down>', lambda e: self.controller.scroll_task_grid(dy_rows=1)
        )
        # Home: re-center on "today" (setdate) - the arrow keys above only
        # move one cell/row at a time, tedious for finding today again once
        # scrolled far away. Page Up/Page Down: half a viewport's worth of
        # rows at once, a bigger jump than Up/Down's single row.
        self.controller.root.bind('<Home>', lambda e: self.controller.center_on_today())
        self.controller.root.bind('<Prior>', lambda e: self.controller.scroll_page(-1))
        self.controller.root.bind('<Next>', lambda e: self.controller.scroll_page(1))

        # Create a resizer between task and resource grids
        self.grid_resizer_frame = tk.Frame(
            self.controller.main_frame, height=5, bg='gray', cursor='sb_v_double_arrow'
        )
        self.grid_resizer_frame.pack(fill=tk.X, pady=1)

        # Add keyboard shortcuts for multi-select
        # Bind Ctrl+A to select all tasks
        self.controller.root.bind('<Control-a>', lambda e: self.select_all_tasks())

        # Bind Escape to clear selections
        self.controller.root.bind('<Escape>', lambda e: self.clear_selections())

        # Delete key deletes the selected tasks. Safe as a root-level
        # binding for the same reason as the arrow keys above: every
        # text-entry widget lives in a grab_set()'d dialog.
        self.controller.root.bind(
            '<Delete>', lambda e: self.controller.task_ops.delete_selected_tasks()
        )

        # Bind events for resizing
        self.grid_resizer_frame.bind('<ButtonPress-1>', self.on_resizer_press)
        self.grid_resizer_frame.bind('<B1-Motion>', self.on_resizer_drag)
        self.grid_resizer_frame.bind('<ButtonRelease-1>', self.on_resizer_release)

        """Bind zoom-related events to the task canvas"""
        # Bind Ctrl+mousewheel for zoom
        self.controller.task_canvas.bind('<MouseWheel>', self.controller.on_zoom)

        # For Linux, which uses Button-4 and Button-5 for scroll wheel.
        # These events have no `delta` attribute, so synthesize one:
        # Button-4 (scroll up) should zoom in, Button-5 (scroll down) should zoom out.
        self.controller.task_canvas.bind(
            '<Button-4>',
            lambda e: self.controller.on_zoom(
                type(
                    'event',
                    (),
                    {'delta': 120, 'x': e.x, 'y': e.y, 'state': e.state},
                )
            ),
        )
        self.controller.task_canvas.bind(
            '<Button-5>',
            lambda e: self.controller.on_zoom(
                type(
                    'event',
                    (),
                    {'delta': -120, 'x': e.x, 'y': e.y, 'state': e.state},
                )
            ),
        )

        # Add Ctrl+0 keyboard shortcut to reset zoom
        self.controller.root.bind('<Control-0>', lambda e: self.controller.reset_zoom())

        # Keyboard zoom shortcuts, equivalent to Ctrl+mousewheel. '+' and '='
        # are the same physical key on most keyboards (shifted/unshifted),
        # as are '-' and '_' - bind both of each pair so neither zoom
        # direction requires remembering whether shift is needed.
        for key in ('<Control-plus>', '<Control-equal>', '<Control-KP_Add>'):
            self.controller.root.bind(
                key, lambda e: self.controller.zoom_via_keyboard(1)
            )
        for key in ('<Control-minus>', '<Control-underscore>', '<Control-KP_Subtract>'):
            self.controller.root.bind(
                key, lambda e: self.controller.zoom_via_keyboard(-1)
            )

        # Add Ctrl+E for export
        self.controller.root.bind(
            '<Control-e>', lambda e: self.controller.export_ops.open_export_dialog()
        )

        # File menu accelerators (Ctrl+N/O/S, Ctrl+Shift+S) - the menu's
        # accelerator= text is display-only in Tk, it doesn't bind a key on
        # its own.
        self.controller.root.bind(
            '<Control-n>', lambda e: self.controller.file_ops.new_project()
        )
        self.controller.root.bind(
            '<Control-o>', lambda e: self.controller.file_ops.open_file()
        )
        self.controller.root.bind(
            '<Control-s>', lambda e: self.controller.file_ops.save_file()
        )
        self.controller.root.bind(
            '<Control-Shift-S>', lambda e: self.controller.file_ops.save_file_as()
        )

        # Undo/Redo (Ctrl+Z/Ctrl+Y) - both no-ops when the project isn't a
        # versioned workspace, or already at the oldest/newest commit (see
        # VersionControlOperations.undo/redo).
        self.controller.root.bind(
            '<Control-z>', lambda e: self.controller.version_control_ops.undo()
        )
        self.controller.root.bind(
            '<Control-y>', lambda e: self.controller.version_control_ops.redo()
        )

    def create_resource_grid_frame(self):
        """Create the resource loading grid canvas with wider label column"""
        self.resource_frame = tk.Frame(
            self.controller.main_frame, height=self.controller.resource_grid_height
        )
        # No expand=True, matching task_frame - see the comment there. Also
        # needs its own pack_propagate(False) + explicit height so its size
        # is fully controlled by on_main_frame_configure/on_resizer_drag
        # rather than being derived from its children's requested sizes.
        self.resource_frame.pack(fill=tk.BOTH, pady=(0, 5))
        self.resource_frame.pack_propagate(False)

        # Resource control bar (Stage 21) - packed BOTTOM before the
        # label/canvas frames claim the LEFT sides, so it spans the full
        # panel width. Lives inside resource_frame's height budget;
        # _fit_resource_pane accounts for its height when fitting the pane
        # to content.
        self.create_resource_control_bar()

        # Create a fixed label column on the left with wider width
        self.controller.resource_label_frame = tk.Frame(
            self.resource_frame, width=self.controller.label_column_width
        )
        self.controller.resource_label_frame.pack(side=tk.LEFT, fill=tk.Y)
        # Without this, the frame auto-inflates its own requested size to
        # match whatever height we later explicitly set on the label canvas
        # (see on_resource_frame_configure), and that inflation cascades
        # all the way up through resource_frame/main_frame/
        # horizontal_layout_frame to root - eventually squeezing the status
        # bar (packed on root, after this whole tree) down to nothing.
        # task_frame already guards against this the same way.
        self.controller.resource_label_frame.pack_propagate(False)
        self.controller.resource_label_canvas = tk.Canvas(
            self.controller.resource_label_frame,
            width=self.controller.label_column_width,
            height=self.controller.resource_grid_height,
            bg='lightgray',
            highlightthickness=0,
        )
        self.controller.resource_label_canvas.pack(fill=tk.BOTH)

        # Create resource canvas with vertical scrollbar
        self.resource_scroll_frame = tk.Frame(self.resource_frame)
        self.resource_scroll_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        # Same reasoning as resource_label_frame above - resource_canvas's
        # explicit height gets bumped in several places below, and without
        # this the frame would inflate its own requested size to match.
        self.resource_scroll_frame.pack_propagate(False)

        self.resource_vscrollbar = ttk.Scrollbar(
            self.resource_scroll_frame, orient=tk.VERTICAL
        )
        self.resource_vscrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.controller.resource_canvas = tk.Canvas(
            self.resource_scroll_frame,
            height=self.controller.resource_grid_height,
            bg='white',
            highlightthickness=1,
            highlightbackground='gray',
            yscrollcommand=self.resource_vscrollbar.set,
        )
        self.controller.resource_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Configure both resource canvases to have the same height
        self.controller.resource_canvas.config(
            height=self.controller.resource_grid_height
        )
        self.controller.resource_label_canvas.config(
            height=self.controller.resource_grid_height
        )

        # Keep both panes' heights in sync with the window's actual size -
        # see on_main_frame_configure for why this can't just rely on Tk's
        # own pack fill/expand.
        self.controller.main_frame.bind('<Configure>', self.on_main_frame_configure)

        # Connect scrollbar to canvas and sync labels with canvas
        self.resource_vscrollbar.config(command=self.sync_resource_vertical_scroll)

        # Configure resource canvas for scrolling
        self.controller.resource_canvas.config(
            xscrollcommand=self.controller.h_scrollbar.set,
            scrollregion=(
                0,
                0,
                self.controller.cell_width * self.model.days,
                len(self.model.resources) * self.controller.task_height,
            ),
        )

    # Combobox label <-> internal sort key (order matters: it's the
    # combobox's value order)
    RESOURCE_SORT_CHOICES = (
        ('Default order', 'default'),
        ('ID', 'id'),
        ('Name', 'name'),
        ('Load %', 'load'),
    )

    def create_resource_control_bar(self):
        """Create the resource grid's control bar (Stage 21): sort key and
        direction, project filter, tag filter, load scope, shown-count,
        and a clear button scoped to resource filters only (the status
        bar's global 'Clear All Filters' already exists)."""
        bar_font = ('Arial', 9)
        bar = tk.Frame(self.resource_frame, bd=1, relief=tk.GROOVE)
        bar.pack(side=tk.BOTTOM, fill=tk.X)
        self.resource_control_bar = bar

        tk.Label(bar, text='Sort:', font=bar_font).pack(side=tk.LEFT, padx=(4, 2))
        self.resource_sort_combo = ttk.Combobox(
            bar,
            state='readonly',
            width=11,
            font=bar_font,
            values=[label for label, _ in self.RESOURCE_SORT_CHOICES],
        )
        self.resource_sort_combo.current(0)
        self.resource_sort_combo.pack(side=tk.LEFT)
        self.resource_sort_combo.bind(
            '<<ComboboxSelected>>', self.on_resource_sort_selected
        )

        self.resource_sort_dir_btn = tk.Button(
            bar,
            text='↑',
            width=1,
            font=bar_font,
            command=self.toggle_resource_sort_direction,
        )
        self.resource_sort_dir_btn.pack(side=tk.LEFT, padx=(2, 8))

        tk.Label(bar, text='Project:', font=bar_font).pack(side=tk.LEFT, padx=(0, 2))
        self.resource_project_combo = ttk.Combobox(
            bar, state='readonly', width=14, font=bar_font
        )
        self.resource_project_combo.pack(side=tk.LEFT, padx=(0, 8))
        self.resource_project_combo.bind(
            '<<ComboboxSelected>>', self.on_resource_project_selected
        )

        self.resource_tags_btn = tk.Button(
            bar,
            text='Tags...',
            font=bar_font,
            command=self.controller.tag_ops.filter_resources_by_tags,
        )
        self.resource_tags_btn.pack(side=tk.LEFT, padx=(0, 8))

        tk.Label(bar, text='Load scope:', font=bar_font).pack(side=tk.LEFT, padx=(0, 2))
        self.resource_scope_combo = ttk.Combobox(
            bar,
            state='readonly',
            width=11,
            font=bar_font,
            values=('All tasks', 'Filtered tasks'),
        )
        self.resource_scope_combo.current(0)
        self.resource_scope_combo.pack(side=tk.LEFT)
        self.resource_scope_combo.bind(
            '<<ComboboxSelected>>', self.on_resource_scope_selected
        )

        self.resource_clear_btn = tk.Button(
            bar,
            text='Clear',
            font=bar_font,
            state=tk.DISABLED,
            command=self.controller.tag_ops.clear_resource_filters,
        )
        self.resource_clear_btn.pack(side=tk.RIGHT, padx=4)
        self.resource_count_label = tk.Label(bar, text='', font=bar_font)
        self.resource_count_label.pack(side=tk.RIGHT, padx=4)

    def on_resource_sort_selected(self, event=None):
        label = self.resource_sort_combo.get()
        key = dict(self.RESOURCE_SORT_CHOICES)[label]
        tag_ops = self.controller.tag_ops
        tag_ops.resource_sort_key = key
        # Load sort defaults to most-loaded-first (that's the drum you're
        # looking for); the others to ascending. The arrow button toggles
        # from there.
        tag_ops.resource_sort_desc = key == 'load'
        self.resource_sort_combo.selection_clear()
        self.controller.update_resource_loading()

    def toggle_resource_sort_direction(self):
        tag_ops = self.controller.tag_ops
        tag_ops.resource_sort_desc = not tag_ops.resource_sort_desc
        self.controller.update_resource_loading()

    def on_resource_project_selected(self, event=None):
        index = self.resource_project_combo.current()
        # index 0 is 'All projects'; -1 means the transient 'Multiple...'
        # text is showing (set via .set(), not a real value) - ignore that
        if index < 0:
            return
        project_ids = [] if index == 0 else [self._resource_project_bar_ids[index - 1]]
        self.resource_project_combo.selection_clear()
        self.controller.tag_ops.apply_resource_project_filter(project_ids)

    def on_resource_scope_selected(self, event=None):
        scope = (
            'filtered' if self.resource_scope_combo.get() == 'Filtered tasks' else 'all'
        )
        self.controller.tag_ops.resource_load_scope = scope
        self.resource_scope_combo.selection_clear()
        self.controller.update_resource_loading()

    def update_resource_control_bar(self):
        """Sync the control bar's widgets with the current filter/sort
        state - filters can also change via the Filter menu dialogs, so
        the bar can't assume it's the only writer."""
        if not hasattr(self, 'resource_control_bar'):
            return
        tag_ops = self.controller.tag_ops

        for index, (_, key) in enumerate(self.RESOURCE_SORT_CHOICES):
            if key == tag_ops.resource_sort_key:
                self.resource_sort_combo.current(index)
                break
        self.resource_sort_dir_btn.config(
            text='↓' if tag_ops.resource_sort_desc else '↑'
        )

        projects = self.model.projects
        self._resource_project_bar_ids = [p['id'] for p in projects]
        self.resource_project_combo.config(
            values=['All projects'] + [p['name'] for p in projects]
        )
        selected = tag_ops.resource_project_filters
        if not selected:
            self.resource_project_combo.current(0)
        elif len(selected) == 1 and selected[0] in self._resource_project_bar_ids:
            self.resource_project_combo.current(
                1 + self._resource_project_bar_ids.index(selected[0])
            )
        else:
            # Multi-select via the Filter menu dialog - not a combobox value
            self.resource_project_combo.set('Multiple...')

        tag_count = len(tag_ops.resource_tag_filters)
        self.resource_tags_btn.config(
            text=f'Tags ({tag_count})...' if tag_count else 'Tags...'
        )

        self.resource_scope_combo.current(
            1 if tag_ops.resource_load_scope == 'filtered' else 0
        )

        shown = len(tag_ops.get_filtered_resources())
        total = len(self.model.resources)
        self.resource_count_label.config(text=f'{shown}/{total} shown')
        self.resource_clear_btn.config(
            state=tk.NORMAL
            if (tag_ops.resource_tag_filters or tag_ops.resource_project_filters)
            else tk.DISABLED
        )

    def _pane_overhead(self):
        """How much of main_frame's height is consumed by everything other
        than the task/resource panes - timeline_frame, the resizer bar,
        h_scrollbar, and every pack pady among the five stacked widgets.

        Computed from live widget geometry on every call rather than
        measured once at startup: the old one-shot measurement
        (main_frame minus the two panes, taken right after creation) ran
        before the window had settled at its real geometry, and whatever
        mismatch existed at that instant - ~40px in practice - was baked
        in forever as phantom overhead. Every later resize then handed
        out that much less height than main_frame actually had, and the
        undistributed remainder sat as a permanent grey band between the
        resource panel and h_scrollbar.
        """

        def pady_total(widget):
            pady = widget.pack_info().get('pady', 0)
            if isinstance(pady, (tuple, list)):
                return sum(int(str(v)) for v in pady)
            return 2 * int(str(pady))

        fixed_height = (
            self.timeline_frame.winfo_reqheight()
            + self.grid_resizer_frame.winfo_reqheight()
            + self.controller.h_scrollbar.winfo_reqheight()
        )
        padding = sum(
            pady_total(widget)
            for widget in (
                self.timeline_frame,
                self.task_frame,
                self.grid_resizer_frame,
                self.resource_frame,
                self.controller.h_scrollbar,
            )
        )
        return fixed_height + padding

    def on_main_frame_configure(self, event):
        """Split main_frame's actual available height between task_frame and
        resource_frame whenever it changes (window resize/maximize) -
        preserving whatever ratio between the two is currently in effect
        (the startup default, or whatever the user last dragged the
        splitter to), rather than task_frame silently keeping the extra
        space for itself.

        This intentionally doesn't rely on Tk's own pack fill/expand to do
        this split (task_frame/resource_frame both have expand=True
        removed): with both frames expand=True, Tk divides *extra* space
        equally between them regardless of their current sizes, and a
        Canvas widget doesn't auto-track a parent's growth once given an
        explicit height anyway - between the two, the split becomes
        unpredictable and, combined with the resource panel's
        `pack_propagate(False)` frames reporting a near-zero natural size,
        could even end up starving resource_frame down to its 100px floor
        with no way to drag it back. Driving both heights explicitly here
        avoids all of that.

        Skipped mid-drag: on_resizer_drag already does this same update
        explicitly every motion step; doing it twice per step roughly
        doubled the layout cost of every drag motion.
        """
        if self.controller.resizing_pane:
            return

        total_available = event.height - self._pane_overhead()
        if total_available <= 0:
            return

        current_total = (
            self.controller.task_grid_height
            + self.controller.resource_grid_ideal_height
        )
        if current_total <= 0:
            return

        task_ratio = self.controller.task_grid_height / current_total
        ideal_task_height = max(100, int(total_available * task_ratio))
        ideal_resource_height = max(100, total_available - ideal_task_height)

        self._fit_resource_pane(ideal_task_height, ideal_resource_height)

    def _fit_resource_pane(self, ideal_task_height, ideal_resource_height):
        """Apply a task/resource height split, but let resource_frame give
        back any part of its share that its actual content doesn't need
        (fewer/shorter resource rows than the panel has room for) to
        task_frame instead - otherwise that space just sits as blank canvas
        background below the last resource row. `ideal_resource_height` -
        the ceiling the panel is allowed to grow back up to as content
        grows - is tracked separately as `resource_grid_ideal_height` so
        repeated calls (e.g. every redraw) don't compound the shrinkage.
        """
        rows_height = (
            len(self.controller.tag_ops.get_filtered_resources())
            * self.controller.task_height
        )
        # The control bar lives inside resource_frame's height budget, so
        # "the height this content needs" is rows plus the bar - without
        # this the bar would eat the last visible row
        bar_height = self.resource_control_bar.winfo_reqheight()
        resource_height = (
            min(ideal_resource_height, rows_height + bar_height)
            if rows_height > 0
            else ideal_resource_height
        )
        resource_height = max(100, resource_height)
        task_height = max(
            100, ideal_task_height + (ideal_resource_height - resource_height)
        )

        self.controller.resource_grid_ideal_height = ideal_resource_height

        if (
            task_height == self.controller.task_grid_height
            and resource_height == self.controller.resource_grid_height
        ):
            return

        self.controller.task_grid_height = task_height
        self.controller.resource_grid_height = resource_height
        self.task_frame.config(height=task_height)
        self.resource_frame.config(height=resource_height)
        self.controller.resource_canvas.config(height=resource_height)
        self.controller.resource_label_canvas.config(height=resource_height)

    def create_context_menu(self):
        """Create the right-click context menu."""
        self.context_menu = tk.Menu(self.controller.root, tearoff=0)
        self.context_menu.add_command(
            label='Edit Task Name',
            command=lambda: self.controller.task_ops.edit_task_name(
                parent=self.controller.root
            ),
        )
        self.context_menu.add_command(
            label='Edit Task URL', command=self.controller.task_ops.edit_task_url
        )
        self.context_menu.add_command(
            label='Edit Task Project...',
            command=lambda: self.controller.task_ops.edit_task_project(
                self.controller.selected_task
            ),
        )
        self.context_menu.add_command(
            label='Edit Task Chain...',
            command=lambda: self.controller.task_ops.edit_task_chain(
                self.controller.selected_task
            ),
        )
        self.context_menu.add_command(
            label='Edit Task Resources',
            command=lambda: self.controller.task_ops.edit_task_resources(
                self.controller.selected_task
            ),
        )
        # Add tag editing menu item
        self.context_menu.add_command(
            label='Edit Task Tags',
            command=lambda: self.controller.tag_ops.edit_task_tags(
                self.controller.selected_task
            ),
        )
        self.context_menu.add_command(
            label='Edit Task Duration...',
            command=lambda: self.controller.task_ops.edit_task_duration(
                [self.controller.selected_task]
            ),
        )

        # Add color selection submenu
        self.color_menu = tk.Menu(self.context_menu, tearoff=0)
        self.context_menu.add_cascade(label='Edit Task Color', menu=self.color_menu)

        # Populate color menu with all web colors
        for color_name in COLOR_NAMES:
            self.color_menu.add_command(
                label=color_name,
                command=lambda c=color_name: self.set_selected_task_color(c),
                background=color_name,
            )

        # Add note-related menu items to the regular task context menu
        self.context_menu.add_separator()
        self.context_menu.add_command(
            label='Add Note',
            command=lambda: self.controller.task_ops.add_note_to_task(
                self.controller.selected_task
            ),
        )
        self.context_menu.add_command(
            label='View Notes',
            command=lambda: self.controller.task_ops.view_task_notes(
                self.controller.selected_task
            ),
        )

        self.context_menu.add_separator()

        # CCPM-related menu items
        self.context_menu.add_command(
            label='Set Optimal Duration...',
            command=lambda: self.controller.task_ops.set_optimal_duration(),
        )
        self.context_menu.add_command(
            label='Record Remaining Duration...',
            command=lambda: self.controller.task_ops.record_remaining_duration(),
        )
        self.context_menu.add_command(
            label='Set Full Kit Done',
            command=lambda: self.controller.task_ops.set_fullkit_done(),
        )
        self.context_menu.add_command(
            label='View Duration History...',
            command=lambda: self.controller.task_ops.view_duration_history(),
        )
        # 'View Buffer History...' and 'View Fever Chart...' are inserted
        # here dynamically by update_context_menu_for_task() - they only
        # apply to buffer tasks, so they stay hidden for ordinary tasks.

        # Add state submenu
        self.state_menu = tk.Menu(self.context_menu, tearoff=0)
        self.context_menu.add_cascade(label='Set Task State', menu=self.state_menu)

        # Populate state menu options
        self.state_menu.add_command(
            label='Planning',
            command=lambda: self.controller.task_ops.set_task_state('planning'),
        )
        self.state_menu.add_command(
            label='Buffered',
            command=lambda: self.controller.task_ops.set_task_state('buffered'),
        )
        self.state_menu.add_command(
            label='Done',
            command=lambda: self.controller.task_ops.set_task_state('done'),
        )

        # Add type submenu
        self.type_menu = tk.Menu(self.context_menu, tearoff=0)
        self.context_menu.add_cascade(label='Set Task Type', menu=self.type_menu)

        # Populate type menu options
        self.type_menu.add_command(
            label='Task',
            command=lambda: self.controller.task_ops.set_task_type('task'),
        )
        self.type_menu.add_command(
            label='Project Buffer',
            command=lambda: self.controller.task_ops.set_task_type('project_buffer'),
        )
        self.type_menu.add_command(
            label='Feeding Buffer',
            command=lambda: self.controller.task_ops.set_task_type('feeding_buffer'),
        )

        self.context_menu.add_separator()
        self.context_menu.add_command(
            label='Add Predecessor',
            command=lambda: self.controller.task_ops.add_predecessor_dialog(
                self.controller.selected_task
            ),
        )
        self.context_menu.add_command(
            label='Add Successor',
            command=lambda: self.controller.task_ops.add_successor_dialog(
                self.controller.selected_task
            ),
        )
        self.context_menu.add_command(
            label='Edit Predecessors...',
            command=lambda: self.controller.task_ops.edit_predecessors_dialog(
                self.controller.selected_task
            ),
        )
        self.context_menu.add_separator()
        self.context_menu.add_command(
            label='Delete Task', command=self.controller.task_ops.delete_task
        )

        # Create resource context menu (new)
        self.resource_context_menu = tk.Menu(self.controller.root, tearoff=0)
        self.resource_context_menu.add_command(
            label='Edit Resource Tags',
            # Opens the Tags tab of Edit Resources, not a standalone
            # dialog - that tab works even when this resource has no tags
            # yet to right-click on the grid in the first place (or Show
            # Tags on Tasks is off), which a canvas-item-bound entry point
            # never could.
            command=lambda: self.controller.task_ops.edit_resources(
                initial_resource_id=self.selected_resource_id, initial_tab='Tags'
            ),
        )

        # Create multiple task selection context menu (new)
        self.multi_task_menu = tk.Menu(self.controller.root, tearoff=0)

        # Add color selection submenu for multiple tasks
        self.multi_color_menu = tk.Menu(self.multi_task_menu, tearoff=0)
        self.multi_task_menu.add_cascade(
            label='Set Tasks Color', menu=self.multi_color_menu
        )

        # Populate color menu with all web colors
        for color_name in COLOR_NAMES:
            self.multi_color_menu.add_command(
                label=color_name,
                command=lambda c=color_name: self.set_selected_tasks_color(c),
                background=color_name,
            )

        self.multi_task_menu.add_separator()

        # Add the other multi-task menu items
        self.multi_task_menu.add_command(
            label='Add Tag to Selected Tasks...',
            command=lambda: None,  # Placeholder to be updated
        )
        self.multi_task_menu.add_command(
            label='Remove Tag from Selected Tasks...',
            command=lambda: None,  # Placeholder to be updated
        )

        # Also add note option to the multi-task menu
        # After the tag-related items
        self.multi_task_menu.add_separator()
        self.multi_task_menu.add_command(
            label='Add Note to Selected Tasks',
            command=self.controller.task_ops.add_note_to_selected_tasks,
        )

        self.multi_task_menu.add_separator()
        self.multi_task_menu.add_command(
            label='Edit Task Duration...',
            command=lambda: self.controller.task_ops.edit_task_duration(
                self.controller.selected_tasks
            ),
        )

    def update_context_menu_for_task(self, task):
        """Adapt the task context menu to the task being right-clicked.

        Buffer-report entries ('View Buffer History...', 'View Fever
        Chart...') only make sense on project/feeding buffer tasks, so they
        are removed and re-inserted per click rather than shown always.
        """
        buffer_only_entries = (
            (
                'View Buffer History...',
                lambda: self.controller.task_ops.view_buffer_history(),
            ),
            (
                'View Fever Chart...',
                lambda: self.controller.task_ops.view_fever_chart(),
            ),
        )

        for label, _ in buffer_only_entries:
            try:
                # A missing label raises TclError (caught below) rather than
                # index() returning None - it's never actually None here.
                index = self.context_menu.index(label)
                assert index is not None
                self.context_menu.delete(index)
            except tk.TclError:
                pass  # Entry not currently present

        is_buffer = (task or {}).get('type') in ('project_buffer', 'feeding_buffer')
        if is_buffer:
            anchor = self.context_menu.index('View Duration History...')
            # 'View Duration History...' is a permanent entry, always present.
            assert anchor is not None
            for offset, (label, command) in enumerate(buffer_only_entries, start=1):
                self.context_menu.insert_command(
                    anchor + offset, label=label, command=command
                )

    def update_menu_commands(self):
        """Update the commands in the menus after initialization"""
        # First check if the multi-task menu has enough items
        menu_length = self.multi_task_menu.index('end')
        if menu_length is not None:  # Check if menu has any items
            # Update the third item (index 2) if it exists
            if menu_length >= 2:
                self.multi_task_menu.entryconfig(
                    2,  # Third item (Add Tag)
                    command=lambda: self.add_tag_to_selected_tasks(),
                )

            # Update the fourth item (index 3) if it exists
            if menu_length >= 3:
                self.multi_task_menu.entryconfig(
                    3,  # Fourth item (Remove Tag)
                    command=lambda: self.remove_tag_from_selected_tasks(),
                )

    def sync_horizontal_scroll(self, *args):
        """Synchronize horizontal scrolling across all three canvases"""
        self.controller.timeline_canvas.xview(*args)
        self.controller.task_canvas.xview(*args)
        self.controller.resource_canvas.xview(*args)

    def sync_vertical_scroll(self, *args):
        """Synchronize vertical scrolling between task canvas and task labels"""
        self.controller.task_canvas.yview(*args)
        self.controller.task_label_canvas.yview(*args)

    def sync_resource_vertical_scroll(self, *args):
        """Synchronize vertical scrolling between resource canvas and resource labels"""
        self.controller.resource_canvas.yview(*args)
        self.controller.resource_label_canvas.yview(*args)

    def on_resizer_press(self, event):
        """Handle mouse press on the resizer bar"""
        self.controller.resizing_pane = True
        self.controller.resize_y = event.y_root

    def on_resizer_drag(self, event):
        """Handle dragging of the resizer bar"""
        if not self.controller.resizing_pane:
            return

        # Calculate change in height
        delta_y = event.y_root - self.controller.resize_y

        # Skip small movements to improve performance
        if abs(delta_y) < 2:
            return

        # Get current dimensions
        task_height = self.task_frame.winfo_height()
        total_available = (
            self.controller.main_frame.winfo_height() - self._pane_overhead()
        )

        # Calculate new heights ensuring minimum sizes - task_frame is also
        # capped so it can never grow into resource_frame's 100px floor
        # (uncapped, a big enough drag could leave less than 100px for
        # resource_frame, which then cascades into main_frame needing more
        # room than it actually has).
        new_task_height = max(100, min(total_available - 100, task_height + delta_y))

        # Ideal resource height based on available space - _fit_resource_pane
        # applies it, but gives back anything the current resource count
        # doesn't need to task_frame instead of leaving it blank.
        available_height = total_available - new_task_height
        ideal_resource_height = max(100, available_height)  # Minimum 100px
        self._fit_resource_pane(new_task_height, ideal_resource_height)

        # Force layout update
        self.controller.root.update_idletasks()

        # Update the reference point
        self.controller.resize_y = event.y_root

    def on_resizer_release(self, event):
        """Handle release of the resizer bar"""
        self.controller.resizing_pane = False
        # Update resource loading display
        self.controller.update_resource_loading()

    def draw_timeline(self):
        """Draw the timeline with calendar dates and day numbers, with alternating week colors"""
        self.controller.timeline_canvas.delete('all')

        # Calculate width
        canvas_width = self.controller.cell_width * self.model.days

        # Increase timeline height to accommodate three rows of information
        timeline_height = self.controller.timeline_height  # This should now be taller

        # Configure canvas scrollregion
        # Ensure the timeline canvas has the correct scrollregion size
        self.controller.timeline_canvas.config(
            scrollregion=(0, 0, canvas_width, self.controller.timeline_height)
        )

        # Calculate row heights (divide the total height into 3 rows)
        month_row_height = timeline_height * 0.33
        date_row_height = timeline_height * 0.33
        day_row_height = timeline_height * 0.34

        # Draw horizontal dividers for the three rows
        self.controller.timeline_canvas.create_line(
            0, month_row_height, canvas_width, month_row_height, fill='gray'
        )
        self.controller.timeline_canvas.create_line(
            0,
            month_row_height + date_row_height,
            canvas_width,
            month_row_height + date_row_height,
            fill='gray',
        )

        # Draw the vertical grid lines
        for i in range(self.model.days + 1):
            x = i * self.controller.cell_width
            self.controller.timeline_canvas.create_line(
                x, 0, x, timeline_height, fill='gray'
            )

        # Draw day numbers (bottom row)
        for i in range(self.model.days):
            x = i * self.controller.cell_width
            day_center_x = x + self.controller.cell_width / 2
            day_center_y = month_row_height + date_row_height + day_row_height / 2

            self.controller.timeline_canvas.create_text(
                day_center_x,
                day_center_y,
                text=str(i),
                anchor='center',
                font=('Arial', self.controller.timeline_font_size),
            )

        # Draw calendar dates (middle row) with alternating week backgrounds
        current_week_is_odd = False  # Start with even week
        last_weekday = None

        for i in range(self.model.days):
            date = self.model.get_date_for_day(i)
            weekday = date.weekday()  # 0 = Monday, 6 = Sunday

            # Highlight current setdate if it matches this day
            current_date = self.model.start_date + timedelta(days=i)
            is_setdate = (
                current_date.year == self.model.setdate.year
                and current_date.month == self.model.setdate.month
                and current_date.day == self.model.setdate.day
            )

            # Check if we're starting a new week (Monday)
            if weekday == 0 or last_weekday is None:
                current_week_is_odd = not current_week_is_odd

            last_weekday = weekday

            # Determine cell background color based on week parity
            if current_week_is_odd:
                bg_color = '#e6e6e6'  # Light gray for odd weeks
            else:
                bg_color = '#f8f8f8'  # Very light gray for even weeks

            # Draw the cell background for the date row
            x1 = i * self.controller.cell_width
            y1 = month_row_height
            x2 = (i + 1) * self.controller.cell_width
            y2 = month_row_height + date_row_height

            self.controller.timeline_canvas.create_rectangle(
                x1, y1, x2, y2, fill=bg_color, outline='gray'
            )

            # Add special color for weekends (Saturday and Sunday)
            if weekday >= 5:  # 5 = Saturday, 6 = Sunday
                self.controller.timeline_canvas.create_rectangle(
                    x1,
                    y1,
                    x2,
                    y2,
                    fill='#ffe6e6',  # Light red for weekends
                    outline='gray',
                )

            if is_setdate:
                # Highlight the current setdate with green background
                self.controller.timeline_canvas.create_rectangle(
                    x1,
                    y1,
                    x2,
                    y2,
                    fill='green',  # Green highlight for setdate
                    outline='darkgreen',
                    stipple='gray50',  # Use stipple for semi-transparency
                )

            # Display date in day format
            date_center_x = x1 + self.controller.cell_width / 2
            date_center_y = month_row_height + date_row_height / 2

            # Add weekday letter as a hint
            date_text = f'{date.day}'  # Remove day of week indicator
            # date_text = f"{date.day}\n{weekday_letters[weekday]}"

            self.controller.timeline_canvas.create_text(
                date_center_x,
                date_center_y,
                text=date_text,
                anchor='center',
                font=(
                    'Arial',
                    self.controller.timeline_font_size,
                ),  # Smaller font for dates
            )

        # Draw month headers (top row with merged cells)
        month_ranges = self.model.get_month_ranges()
        for month_range in month_ranges:
            start_x = month_range['start'] * self.controller.cell_width
            end_x = (month_range['end'] + 1) * self.controller.cell_width
            month_center_x = (start_x + end_x) / 2
            month_center_y = month_row_height / 2

            # Draw month background to visually separate months
            fill_color = '#f0f0f0' if month_range['start'] % 2 == 0 else '#e0e0e0'
            self.controller.timeline_canvas.create_rectangle(
                start_x, 0, end_x, month_row_height, fill=fill_color, outline='gray'
            )

            # Draw month label
            self.controller.timeline_canvas.create_text(
                month_center_x,
                month_center_y,
                text=month_range['label'],
                anchor='center',
                font=(
                    'Arial',
                    self.controller.timeline_font_size,
                    'bold',
                ),  # Make month headers bold
            )

    def draw_task_grid(self):
        """Draw the task grid with wider label column"""
        # Clean up any active tooltips
        self.cleanup_tooltips()

        # Clear the task canvas and label canvas
        self.controller.task_canvas.delete('all')
        self.controller.task_label_canvas.delete('all')

        # Clear task UI elements tracking
        self.task_ui_elements = {}

        # Calculate width and height with dynamic row height
        canvas_width = self.controller.cell_width * self.model.days
        canvas_height = self.model.max_rows * self.controller.task_height

        # Configure canvas scrollregions
        self.controller.task_canvas.config(
            scrollregion=(0, 0, canvas_width, canvas_height)
        )
        self.controller.task_label_canvas.config(
            scrollregion=(0, 0, self.controller.label_column_width, canvas_height)
        )

        # Shade the "safe to delete" region (Stage 13) - columns Delete
        # History could remove today with zero warnings/blocks - behind
        # everything else, so grid lines and tasks still draw on top.
        safe_cutoff_col = self.model.compute_safe_delete_cutoff()
        if safe_cutoff_col > 0:
            self.controller.task_canvas.create_rectangle(
                0,
                0,
                safe_cutoff_col * self.controller.cell_width,
                canvas_height,
                fill='#e8e8e8',
                outline='',
                tags=('safe_delete_region',),
            )

        # Draw the grid lines with dynamic row height
        for i in range(self.model.days + 1):
            x = i * self.controller.cell_width
            self.controller.task_canvas.create_line(x, 0, x, canvas_height, fill='gray')

        for i in range(self.model.max_rows + 1):
            y = i * self.controller.task_height
            self.controller.task_canvas.create_line(0, y, canvas_width, y, fill='gray')

            # Draw row labels in the label canvas
            if i < self.model.max_rows:
                self.controller.task_label_canvas.create_line(
                    0, y, self.controller.label_column_width, y, fill='gray'
                )
                self.controller.task_label_canvas.create_text(
                    self.controller.label_column_width / 2,  # Center in wider column
                    y + self.controller.task_height / 2,
                    text=f'Row {i}',
                    anchor='center',
                    font=(
                        'Arial',
                        self.controller.resource_font_size,
                    ),  # Use dynamic font size
                )

        # Draw the bottom line in the label canvas
        self.controller.task_label_canvas.create_line(
            0,
            canvas_height,
            self.controller.label_column_width,
            canvas_height,
            fill='gray',
        )

        # Get filtered tasks if filters are active
        tasks_to_draw = self.controller.tag_ops.get_filtered_tasks()

        # Draw the tasks
        for task in tasks_to_draw:
            self.draw_task(task)

        # Draw dependencies
        self.draw_dependencies()

    def _truncate_text_to_width(self, text, font, max_width, suffix=''):
        """Truncate `text` with a trailing ellipsis (before `suffix`, e.g. a
        closing bracket that should survive truncation) so `text + suffix`
        fits within `max_width` pixels for the given font, shrinking `text`
        from the end until `text + '...' + suffix` fits. Returns
        `(display_text, was_truncated)` - callers use `was_truncated` to
        decide whether a tooltip with the full text is worth adding.
        """
        if font.measure(text + suffix) <= max_width:
            return text + suffix, False

        truncated = text
        while truncated and font.measure(truncated + '...' + suffix) > max_width:
            truncated = truncated[:-1]
        return ((truncated + '...' + suffix) if truncated else ('...' + suffix)), True

    def add_tag_tooltip(self, canvas, item_id, tooltip_text):
        """Add a tooltip to a canvas item with better tracking."""
        # Create a class attribute to track active tooltips if it doesn't exist
        if not hasattr(self, 'active_tooltips'):
            self.active_tooltips = {}

        def enter(event):
            x, y = event.x_root, event.y_root

            # Create tooltip window
            tooltip_window = tk.Toplevel(self.controller.root)
            tooltip_window.wm_overrideredirect(True)
            tooltip_window.wm_geometry(f'+{x + 10}+{y + 10}')

            # Create tooltip content
            label = tk.Label(
                tooltip_window,
                text=tooltip_text,
                justify=tk.LEFT,
                background='#ffffe0',
                relief=tk.SOLID,
                borderwidth=1,
                padx=3,
                pady=2,
            )
            label.pack()

            # Store this tooltip in our tracking dictionary with canvas item as key
            self.active_tooltips[item_id] = tooltip_window

        def leave(event):
            # Get the tooltip window for this item
            tooltip_window = self.active_tooltips.get(item_id)
            if tooltip_window:
                tooltip_window.destroy()
                # Remove from tracking dictionary
                if item_id in self.active_tooltips:
                    del self.active_tooltips[item_id]

        # Bind tooltip events
        canvas.tag_bind(item_id, '<Enter>', enter)
        canvas.tag_bind(item_id, '<Leave>', leave)

    def cleanup_tooltips(self):
        """Clean up all active tooltips."""
        if hasattr(self, 'active_tooltips'):
            # Destroy all active tooltip windows
            for tooltip_window in self.active_tooltips.values():
                if tooltip_window.winfo_exists():
                    tooltip_window.destroy()
            # Clear the dictionary
            self.active_tooltips = {}

    def add_task_tooltips(self, task):
        """Add tooltips for task tags and resource information."""
        task_id = task['task_id']
        if task_id in self.task_ui_elements:
            ui_elements = self.task_ui_elements[task_id]
            box_id = ui_elements['box']

            # Create tooltip text with all relevant information
            tooltip_parts = []

            # Task name first - for a long-duration task, its centered label
            # on the task box itself can be scrolled off-screen, so the
            # tooltip is the only reliable place to read it. Wrapped/
            # truncated to keep the popup from growing unboundedly wide.
            task_name = task.get('description', 'No Description')
            tooltip_parts.extend(wrap_task_name_for_tooltip(task_name))

            # Add state
            state = task.get('state', 'planning')
            tooltip_parts.append(f'Task state: {state}')

            # Add task type (task/project_buffer/feeding_buffer) - distinct from
            # Task state above; shown here so it's obvious at a glance whether a
            # task intended as a buffer was actually set as one via Set Task Type
            task_type = task.get('type', 'task')
            tooltip_parts.append(f'Task type: {task_type.replace("_", " ").title()}')

            # Add project (name and its own planning/execution phase - not to be
            # confused with the task's own Task state above, a separate concept)
            project = self.controller.model.get_project_by_id(task.get('project_id'))
            if project:
                tooltip_parts.append(
                    f'Project: {project["name"]} ({project["phase"].capitalize()})'
                )
            else:
                tooltip_parts.append('Project: None')

            # Add chain (critical/feeding-NN classification)
            chain = self.controller.model.get_chain_by_id(task.get('chain_id'))
            if chain:
                tooltip_parts.append(f'Chain: {chain["name"]}')
            else:
                tooltip_parts.append('Chain: None')

            # Add predecessors/successors (compact link notation) - makes it
            # possible to follow/untangle feeding chains by hovering, without
            # having to open Help > task details for the same information.
            predecessor_text = format_predecessor_notation(task.get('predecessors', []))
            tooltip_parts.append(f'Predecessors: {predecessor_text or "None"}')

            successor_ids = self.controller.model.get_successor_ids(task_id)
            successor_text = ', '.join(map(str, successor_ids))
            tooltip_parts.append(f'Successors: {successor_text or "None"}')

            # Add durations
            tooltip_parts.append(f'Duration: {task["duration"]} days')

            if task.get('optimal_duration'):
                tooltip_parts.append(
                    f'Optimal Duration: {task["optimal_duration"]} days'
                )

            if (
                task.get('realistic_duration')
                and task.get('realistic_duration') != task['duration']
            ):
                tooltip_parts.append(
                    f'Realistic Duration: {task["realistic_duration"]} days'
                )

            # Add remaining duration if available
            remaining_duration = self.controller.model.get_latest_remaining_duration(
                task_id
            )
            if remaining_duration is not None:
                tooltip_parts.append(f'Remaining: {remaining_duration} days')

            # Add dates if available
            if task.get('actual_start_date'):
                start_date = datetime.fromisoformat(task['actual_start_date']).strftime(
                    '%Y-%m-%d'
                )
                tooltip_parts.append(f'Started: {start_date}')

            if task.get('actual_end_date'):
                end_date = datetime.fromisoformat(task['actual_end_date']).strftime(
                    '%Y-%m-%d'
                )
                tooltip_parts.append(f'Completed: {end_date}')

            if task.get('fullkit_date'):
                fullkit_date = datetime.fromisoformat(task['fullkit_date']).strftime(
                    '%Y-%m-%d'
                )
                tooltip_parts.append(f'Full Kit: {fullkit_date}')

            # Add tags section if task has tags
            if 'tags' in task and task['tags']:
                tooltip_parts.append('Tags: ' + ', '.join(task['tags']))

            # Add resource section if task has resources
            if 'resources' in task and task['resources']:
                tooltip_parts.append('Resources:')
                # Sort resources by allocation (highest first) for better readability
                sorted_resources = []
                for resource_id_str, allocation in task['resources'].items():
                    resource_id = (
                        int(resource_id_str)
                        if isinstance(resource_id_str, str)
                        else resource_id_str
                    )
                    resource = self.controller.model.get_resource_by_id(resource_id)
                    if resource:
                        sorted_resources.append((allocation, resource['name']))

                # Sort by allocation (highest first)
                sorted_resources.sort(reverse=True)

                # Add each resource to tooltip
                for allocation, name in sorted_resources:
                    tooltip_parts.append(f'  {allocation} × {name}')

            # Join all parts to create the complete tooltip text
            tooltip_text = '\n'.join(tooltip_parts)

            # Only add tooltip if we have content
            if tooltip_text:
                # Add tooltip to the task box
                self.add_tag_tooltip(self.controller.task_canvas, box_id, tooltip_text)

    def draw_dependencies(self):
        """Draw arrows for task dependencies"""
        # First delete all existing dependency arrows
        self.controller.task_canvas.delete('dependency')

        # Maps a dependency arrow's canvas item id to its (predecessor_id,
        # successor_id), so a right-click on the line can look up which link
        # it represents. Rebuilt on every redraw alongside the arrows.
        self.dependency_link_map = {}

        # Then redraw all dependencies, drawing each link from its predecessor
        # to the current task (successors are derived, not stored on the task)
        for task in self.model.tasks:
            for link in task.get('predecessors', []):
                predecessor = self.model.get_task(link['id'])
                if (
                    predecessor
                    and link['id'] in self.task_ui_elements
                    and task['task_id'] in self.task_ui_elements
                ):
                    # Get task coordinates
                    predecessor_ui = self.task_ui_elements[link['id']]
                    task_ui = self.task_ui_elements[task['task_id']]

                    # Check for same row and adjacency
                    if (
                        predecessor_ui['y1'] == task_ui['y1']
                        and predecessor_ui['x2'] == task_ui['x1']
                    ):
                        continue  # Skip drawing the line if adjacent in same row and predecessor-successor

                    x1 = predecessor_ui['x2']
                    y1 = (predecessor_ui['y1'] + predecessor_ui['y2']) / 2
                    x2 = task_ui['x1']
                    y2 = (task_ui['y1'] + task_ui['y2']) / 2
                    arrow_id = self.draw_arrow(
                        x1, y1, x2, y2, predecessor, task, link['type']
                    )
                    self.dependency_link_map[arrow_id] = (
                        link['id'],
                        task['task_id'],
                    )

    def show_dependency_link_menu(self, event, predecessor_id, successor_id):
        """Build and show a context menu to edit or remove a dependency link."""
        link = self.controller.task_ops._find_predecessor_link(
            predecessor_id, successor_id
        )
        if not link:
            return

        menu = tk.Menu(self.controller.root, tearoff=0)

        type_menu = tk.Menu(menu, tearoff=0)
        for link_type in LINK_TYPES_ORDERED:
            marker = ' (current)' if link_type == link['type'] else ''
            type_menu.add_command(
                label=f'{link_type}{marker}',
                command=lambda t=link_type: (
                    self.controller.task_ops.set_dependency_type(
                        predecessor_id, successor_id, t
                    )
                ),
            )
        menu.add_cascade(label=f'Link Type ({link["type"]})', menu=type_menu)

        menu.add_command(
            label=f'Set Lag... (current: {link["lag"]})',
            command=lambda: self.controller.task_ops.set_dependency_lag_dialog(
                predecessor_id, successor_id
            ),
        )
        menu.add_separator()
        menu.add_command(
            label='Remove Link',
            command=lambda: self.controller.task_ops.remove_dependency(
                predecessor_id, successor_id
            ),
        )

        self.popup_menu(menu, event.x_root, event.y_root)

    def draw_arrow(self, x1, y1, x2, y2, task, successor, link_type='FS'):
        """Draw an arrow between tasks, coloring based on dependency direction.
        Buffer links (PB/FB) are drawn dashed so they read differently from
        ordinary CPM dependencies."""

        # Calculate the end date of the predecessor and start date of the successor
        predecessor_end_date = task['col'] + task['duration']
        successor_start_date = successor['col']

        # Determine the color based on the dependency direction
        color = 'darkblue'  # Default to blue (forward dependency)
        if predecessor_end_date > successor_start_date:
            color = 'darkred'  # Red for backward dependency

        # Calculate control points for a curved line
        cp_x = (x1 + x2) / 2

        dash = (6, 3) if link_type in BUFFER_LINK_TYPES else None

        # Draw the arrow line
        arrow_id = self.controller.task_canvas.create_line(
            x1,
            y1,
            cp_x,
            y1,
            cp_x,
            y2,
            x2,
            y2,
            smooth=True,
            arrow=tk.LAST,
            fill=color,
            width=1.5,
            dash=dash,
            tags=('dependency',),
        )
        return arrow_id

    def draw_fever_chart(
        self, canvas, buffer_task, project, x0=10, y0=10, width=460, height=340
    ):
        """Draw a single buffer's fever chart (Stage 8) into a rectangular
        region of `canvas` - progress % (x-axis, 0-100) against buffer
        consumption % (y-axis, sloped green/yellow/red zones), trajectory
        connected point-to-point and colored by zone, from
        `buffer_task['fever_chart_history']`.
        """
        slope = project.get('fever_chart_slope', 0.55)
        yellow_intercept = project.get('fever_chart_yellow_intercept', 10.0)
        red_intercept = project.get('fever_chart_red_intercept', 27.0)

        history = sorted_fever_chart_history(buffer_task)
        baseline = buffer_task.get('baseline')
        buffer_baseline_duration = (
            baseline['duration'] if baseline else buffer_task['duration']
        )

        points = []
        for entry in history:
            progress_pct, consumption_pct = fever_chart_display_point(
                entry, buffer_baseline_duration
            )
            points.append((entry['date'], progress_pct, consumption_pct))

        # y-axis range: at least 0-100%, extended if any point exceeds 100%
        # (consumption is never clamped for storage/calculation - only the
        # display floors negative values at 0, per the design notes).
        max_consumption = max([p[2] for p in points] + [100.0])
        y_max = max(100.0, ((max_consumption // 20) + 2) * 20)

        chart_x0, chart_y0 = x0 + 50, y0 + 47
        chart_w, chart_h = width - 70, height - 87

        def to_px(progress_pct, consumption_pct):
            px = chart_x0 + (progress_pct / 100.0) * chart_w
            clamped = max(0.0, min(y_max, consumption_pct))
            py = chart_y0 + (1 - clamped / y_max) * chart_h
            return px, py

        def boundary(x_pct, intercept):
            return max(0.0, min(y_max, slope * x_pct + intercept))

        # Title - project name above the buffer name, so a chart saved to
        # disk is self-identifying (Stage 22)
        project_name, buffer_title = fever_chart_title_lines(buffer_task, project)
        canvas.create_text(
            x0 + width / 2, y0, text=project_name, font=('Arial', 8), anchor='n'
        )
        canvas.create_text(
            x0 + width / 2,
            y0 + 13,
            text=buffer_title,
            font=('Arial', 10, 'bold'),
            anchor='n',
        )

        # Zone bands (green / yellow / red), as three filled quadrilaterals
        # spanning the full 0-100% progress width.
        y_at_0 = boundary(0, yellow_intercept)
        y_at_100 = boundary(100, yellow_intercept)
        canvas.create_polygon(
            *to_px(0, 0),
            *to_px(100, 0),
            *to_px(100, y_at_100),
            *to_px(0, y_at_0),
            fill='#C8E6C9',
            outline='',
        )

        r_at_0 = boundary(0, red_intercept)
        r_at_100 = boundary(100, red_intercept)
        canvas.create_polygon(
            *to_px(0, y_at_0),
            *to_px(100, y_at_100),
            *to_px(100, r_at_100),
            *to_px(0, r_at_0),
            fill='#FFF59D',
            outline='',
        )

        canvas.create_polygon(
            *to_px(0, r_at_0),
            *to_px(100, r_at_100),
            *to_px(100, y_max),
            *to_px(0, y_max),
            fill='#EF9A9A',
            outline='',
        )

        # Axes + tick labels every 25% (x) / 20% (y, scaled to y_max)
        canvas.create_rectangle(
            chart_x0, chart_y0, chart_x0 + chart_w, chart_y0 + chart_h, outline='black'
        )
        for x_pct in (0, 25, 50, 75, 100):
            px, _ = to_px(x_pct, 0)
            canvas.create_text(
                px, chart_y0 + chart_h + 10, text=f'{x_pct}%', font=('Arial', 7)
            )
        y_step = y_max / 5
        for i in range(6):
            y_pct = i * y_step
            _, py = to_px(0, y_pct)
            canvas.create_text(
                chart_x0 - 15, py, text=f'{y_pct:.0f}%', font=('Arial', 7)
            )
        canvas.create_text(
            x0 + width / 2,
            y0 + height - 8,
            text='% of protected chain complete',
            font=('Arial', 8),
        )
        canvas.create_text(
            x0 + 10,
            chart_y0 - 12,
            text='% buffer consumed',
            font=('Arial', 8),
            anchor='nw',
        )

        if not points:
            canvas.create_text(
                chart_x0 + chart_w / 2,
                chart_y0 + chart_h / 2,
                text='No status updates recorded yet',
                font=('Arial', 9),
                fill='#777777',
            )
            return

        # Trajectory: connect points in order, color each dot by its zone
        pixel_points = []
        for date_str, progress_pct, consumption_pct in points:
            px, py = to_px(progress_pct, max(0.0, consumption_pct))
            zone = classify_fever_chart_zone(
                progress_pct, consumption_pct, slope, yellow_intercept, red_intercept
            )
            pixel_points.append((date_str, progress_pct, consumption_pct, px, py, zone))

        # Dates are chronological (sorted_fever_chart_history) but can still
        # land close together in pixel space - declutter the labels
        # independently of the dots/line, which keep their true positions.
        label_anchors = [(px, py - 10) for _, _, _, px, py, _ in pixel_points]
        label_positions = declutter_label_positions(label_anchors, box_w=32, box_h=11)

        prev_px = None
        for (date_str, progress_pct, consumption_pct, px, py, zone), (lx, ly) in zip(
            pixel_points, label_positions, strict=True
        ):
            if prev_px is not None:
                canvas.create_line(
                    prev_px[0], prev_px[1], px, py, fill='black', width=1.5
                )
            dot_color = {'green': '#2E7D32', 'yellow': '#F9A825', 'red': '#C62828'}[
                zone
            ]
            dot_id = canvas.create_oval(
                px - 4, py - 4, px + 4, py + 4, fill=dot_color, outline='black'
            )
            date_label = datetime.fromisoformat(date_str).strftime('%m-%d')
            canvas.create_text(lx, ly, text=date_label, font=('Arial', 7))
            canvas.tag_bind(
                dot_id,
                '<Button-1>',
                lambda event, d=date_str, p=progress_pct, c=consumption_pct, z=zone: (
                    self._show_fever_chart_point_detail(buffer_task, d, p, c, z)
                ),
            )
            prev_px = (px, py)

    def _show_fever_chart_point_detail(
        self, buffer_task, date_str, progress_pct, consumption_pct, zone
    ):
        """Click handler for a fever chart dot - shows the date, its
        Progress %/Consumption %/Zone, and whichever reason/note (if any)
        was recorded against this buffer's own protected chain on that
        date, since most fever_chart_history points come from project-wide
        recomputes with no reason attributable to this specific buffer.
        """
        date_label = datetime.fromisoformat(date_str).strftime('%Y-%m-%d')
        reasons = self.model.get_buffer_update_reasons(buffer_task['task_id'])
        matching = [entry for entry in reasons if entry['date'] == date_str]

        lines = [
            f'Date: {date_label}',
            f'Progress: {progress_pct:.1f}%',
            f'Consumption: {consumption_pct:.1f}%',
            f'Zone: {zone}',
            '',
        ]
        if matching:
            for entry in matching:
                lines.append(
                    f'{entry["task_description"]}: {entry["remaining_duration"]}d remaining'
                )
                if entry.get('reason'):
                    lines.append(f'  Reason: {entry["reason"]}')
                if entry.get('note'):
                    lines.append(f'  Note: {entry["note"]}')
        else:
            lines.append(
                'No status update with a reason/note was recorded against '
                "this buffer's own chain on this date - this point comes "
                'from a project-wide recompute triggered elsewhere.'
            )

        messagebox.showinfo(
            'Fever Chart Point',
            '\n'.join(lines),
            parent=self.controller.root,
        )

    def draw_resource_grid(self):
        """Draw the resource loading grid with wider label column"""
        self.controller.resource_canvas.delete('all')
        self.controller.resource_label_canvas.delete('all')

        # Filtered resources in display order (sorting applied) - must
        # match display_resource_loading's ordering, hence the shared
        # controller method
        resources_to_draw = self.controller.get_display_resources()

        # Calculate width and height
        canvas_width = self.controller.cell_width * self.model.days
        canvas_height = len(resources_to_draw) * self.controller.task_height

        # Configure canvas scrollregions
        self.controller.resource_canvas.config(
            scrollregion=(0, 0, canvas_width, canvas_height)
        )
        self.controller.resource_label_canvas.config(
            scrollregion=(0, 0, self.controller.label_column_width, canvas_height)
        )

        # Re-fit the panel split in case the resource count/filter/zoom
        # changed since the last resize or drag (e.g. resources added, a
        # filter applied, or zoom changing row height) - reconstructed from
        # the current actual total plus the ideal ceiling, so this can both
        # reclaim space back from task_frame (content grew back toward the
        # ceiling) and give more back to it (content shrank further).
        total_available = (
            self.controller.task_grid_height + self.controller.resource_grid_height
        )
        ideal_resource_height = self.controller.resource_grid_ideal_height
        ideal_task_height = max(100, total_available - ideal_resource_height)
        self._fit_resource_pane(ideal_task_height, ideal_resource_height)

        # Draw column lines
        for i in range(self.model.days + 1):
            x = i * self.controller.cell_width
            self.controller.resource_canvas.create_line(
                x, 0, x, canvas_height, fill='gray'
            )

        # Draw row lines and resource names
        for i, resource in enumerate(resources_to_draw):
            y = i * self.controller.task_height

            # Draw lines in resource canvas
            self.controller.resource_canvas.create_line(
                0, y, canvas_width, y, fill='gray'
            )

            # Draw resource names and tags in the label canvas
            self.controller.resource_label_canvas.create_line(
                0, y, self.controller.label_column_width, y, fill='gray'
            )

            resource_id = resource['id']

            # ID always visible (it's what the CSV exports key by); the
            # utilization % is appended when load-sorted so the row order
            # is legible rather than driven by an invisible number
            resource_text = f'#{resource_id} {resource["name"]}'
            if self.controller.tag_ops.resource_sort_key == 'load':
                util = self.controller.resource_utilization.get(resource_id, 0.0)
                pct = '∞' if util == float('inf') else f'{util * 100:.0f}%'
                resource_text = f'{resource_text} · {pct}'

            # Split the row into two independent, non-overlapping zones
            # when a tag will also be shown - name in the upper half, tag
            # in the lower half - rather than centering the name and
            # positioning the tag as an offset *from* it. That older
            # formula coupled the tag's position to tag_font_size itself,
            # so the two could grow to overlap each other even though each
            # individually still fit within the row's own outer boundary.
            has_tags = (
                bool(resource.get('tags'))
                and self.show_tags_var.get()
                and self.controller.resource_tag_zone_fits()
            )
            tag_y = None
            if has_tags:
                name_y = y + self.controller.task_height / 4
                tag_y = y + self.controller.task_height * 3 / 4
            else:
                name_y = y + self.controller.task_height / 2

            # Draw resource name centered in wider column, truncated with a
            # tooltip if the id/name/% combination outgrows the column
            name_font = tkfont.Font(
                family='Arial', size=self.controller.resource_font_size
            )
            display_name, name_truncated = self._truncate_text_to_width(
                resource_text, name_font, self.controller.label_column_width - 10
            )
            # Same URL affordance as a task box's name (draw_task): blue
            # text, click to open in the browser - only when the resource
            # actually has one.
            resource_url = resource.get('url')
            has_url = bool(
                resource_url and isinstance(resource_url, str) and resource_url.strip()
            )
            name_id = self.controller.resource_label_canvas.create_text(
                self.controller.label_column_width / 2,  # Center in wider column
                name_y,
                text=display_name,
                anchor='center',
                fill='blue' if has_url else 'black',
                font=(
                    'Arial',
                    self.controller.resource_font_size,
                ),  # Use dynamic font size
                tags=(f'resource_{resource_id}',),
            )
            if name_truncated:
                self.add_tag_tooltip(
                    self.controller.resource_label_canvas, name_id, resource_text
                )

            # Bind event to the resource name
            self.controller.resource_label_canvas.tag_bind(
                f'resource_{resource_id}',
                '<ButtonPress-3>',
                lambda e, rid=resource_id: self.show_resource_context_menu(e, rid),
            )
            if has_url:
                self.controller.resource_label_canvas.tag_bind(
                    f'resource_{resource_id}',
                    '<Button-1>',
                    lambda e, url=resource_url: self.open_url(url),
                )

            # Draw tags if present - centered in wider column
            if has_tags:
                tag_text = ', '.join(resource['tags'])
                full_text = f'[{tag_text}]'
                tag_font = tkfont.Font(
                    family='Arial', size=self.controller.tag_font_size
                )
                display_text, was_truncated = self._truncate_text_to_width(
                    f'[{tag_text}',
                    tag_font,
                    self.controller.label_column_width - 10,
                    suffix=']',
                )
                tag_id = self.controller.resource_label_canvas.create_text(
                    self.controller.label_column_width / 2,  # Center in wider column
                    tag_y,
                    text=display_text,
                    anchor='center',
                    font=('Arial', self.controller.tag_font_size),
                    tags=(f'resource_tags_{resource_id}',),
                )
                if was_truncated:
                    self.add_tag_tooltip(
                        self.controller.resource_label_canvas, tag_id, full_text
                    )

                # Right-click on the tag text itself should reach the same
                # "Edit Resource Tags" menu as right-clicking the name above
                # it - previously only the name had this binding, so
                # right-clicking directly on the tags (the natural thing to
                # try when you want to edit them) silently did nothing.
                self.controller.resource_label_canvas.tag_bind(
                    f'resource_tags_{resource_id}',
                    '<ButtonPress-3>',
                    lambda e, rid=resource_id: self.show_resource_context_menu(e, rid),
                )

        # Draw bottom line
        self.controller.resource_canvas.create_line(
            0, canvas_height, canvas_width, canvas_height, fill='gray'
        )
        self.controller.resource_label_canvas.create_line(
            0,
            canvas_height,
            self.controller.label_column_width,
            canvas_height,
            fill='gray',
        )

    def display_resource_loading(self, resource_loading):
        """Display resource loading based on data from the model with dynamic row height"""
        # Clear previous loading display
        self.controller.resource_canvas.delete('loading')

        # Filtered resources in display order - same ordering as
        # draw_resource_grid, so cells line up with their labels
        filtered_resources = self.controller.get_display_resources()

        # Display resource loading for filtered resources
        for i, resource in enumerate(filtered_resources):
            resource_id = resource[
                'id'
            ]  # Get the resource ID which is the key in resource_loading

            for day in range(self.model.days):
                # Get resource capacity and loading
                capacity = resource['capacity'][day]
                load = resource_loading[resource_id][day]  # Use resource_id as the key

                x = day * self.controller.cell_width
                y = i * self.controller.task_height

                # Choose color based on load vs capacity (tolerant: a
                # load that equals capacity is full, not overloaded)
                color = get_resource_load_color(load, capacity)

                # Create cell
                self.controller.resource_canvas.create_rectangle(
                    x,
                    y,
                    x + self.controller.cell_width,
                    y + self.controller.task_height,
                    fill=color,
                    outline='gray',
                    tags='loading',
                )

                # Display load number if there is any loading
                if load > 0:
                    # Format load to show decimals only if needed
                    load_text = f'{load:.1f}' if load != int(load) else str(int(load))

                    # Show as fraction of capacity
                    display_text = f'{load_text}/{capacity}'

                    self.controller.resource_canvas.create_text(
                        x + self.controller.cell_width / 2,
                        y + self.controller.task_height / 2,
                        text=display_text,
                        tags='loading',
                        font=(
                            'Arial',
                            self.controller.resource_font_size,
                        ),  # Use dynamic font size
                    )

    def _monitor_bounds(self, x, y):
        """Bounds (x, y, width, height) of the physical monitor containing
        the point, falling back to the whole virtual screen. Tk only knows
        the virtual screen, which is the bounding box of all monitors - on
        a mixed-height setup (e.g. a 1080-tall laptop panel beside a
        1440-tall external), clamping to the virtual bottom still leaves a
        menu 360px off the bottom of the shorter panel. Per-monitor
        geometry comes from xrandr on X11; on Windows/macOS the native
        menu code clamps per-monitor by itself, so the fallback is fine
        there. Parsed once and cached - monitor layout rarely changes
        mid-session, and a stale read only degrades to the virtual-screen
        clamp."""
        if not hasattr(self, '_monitor_geometries'):
            self._monitor_geometries = []
            try:
                out = subprocess.run(
                    ['xrandr', '--listmonitors'],
                    capture_output=True,
                    text=True,
                    timeout=2,
                ).stdout
                # " 0: +*eDP-1 1920/310x1080/170+0+0  eDP-1"
                for w, h, mx, my in re.findall(
                    r'(\d+)/\d+x(\d+)/\d+\+(\d+)\+(\d+)', out
                ):
                    self._monitor_geometries.append((int(mx), int(my), int(w), int(h)))
            except (OSError, subprocess.SubprocessError):
                pass
        for mx, my, mw, mh in self._monitor_geometries:
            if mx <= x < mx + mw and my <= y < my + mh:
                return mx, my, mw, mh
        root = self.controller.root
        return 0, 0, root.winfo_screenwidth(), root.winfo_screenheight()

    def popup_menu(self, menu, x_root, y_root):
        """Post a context menu fully visible on the monitor under the
        cursor. A menu posted at the raw position runs off the bottom (or
        right) edge when invoked near it - the tall task context menu was
        the worst case, with its lower entries unreachable - and Tk's own
        clamping only respects the virtual screen, not the physical
        monitor (see _monitor_bounds). If the menu is somehow taller than
        the monitor, it pins to the top edge so the first entries show.
        """
        menu.update_idletasks()
        mx, my, mw, mh = self._monitor_bounds(x_root, y_root)
        x = min(x_root, mx + mw - menu.winfo_reqwidth())
        y = min(y_root, my + mh - menu.winfo_reqheight())
        menu.tk_popup(max(mx, x), max(my, y))

    def show_resource_context_menu(self, event, resource_id):
        """Show the context menu for a resource."""
        self.selected_resource_id = resource_id
        self.popup_menu(self.resource_context_menu, event.x_root, event.y_root)

    def open_url(self, url):
        """Open a URL in the default web browser"""
        webbrowser.open(url)

    def draw_task(self, task):
        """Draw a single task box with its information, accounting for dynamic row height"""
        task_id = task['task_id']
        description = task.get('description', 'No Description')

        # Get task color, default to Cyan if not set
        task_color = task.get('color', 'Cyan')

        # Get task state, default to 'planning' if not set
        task_state = task.get('state', 'planning')

        # A near-zero-duration buffer (Stage 7's fully-consumed case) has
        # its render width floored (get_task_ui_coordinates), which can
        # genuinely overlap a neighbouring task's own box in the
        # timeline - tracked here so hit-testing (on_task_press/
        # on_right_click/on_task_hover) can give the buffer priority
        # in that overlap, and so this task's own redraw (below) can
        # re-raise any already-drawn buffer above it.
        is_buffer = task.get('type') in ('project_buffer', 'feeding_buffer')

        # Calculate position with dynamic row height
        x1, y1, x2, y2 = self.controller.get_task_ui_coordinates(task)

        # Check if this task is selected and should have a highlight
        is_selected = task in self.controller.selected_tasks

        # Draw highlight first if task is selected (so it appears behind the task)
        highlight_id = None
        if is_selected:
            highlight_id = self.controller.task_canvas.create_rectangle(
                x1 - 2,
                y1 - 2,
                x2 + 2,
                y2 + 2,
                outline='orange',
                width=2,
                tags=('selection_highlight',),
            )

        # Keep the original task color for the box background
        fill_color = task_color

        # Draw task box
        box_id = self.controller.task_canvas.create_rectangle(
            x1, y1, x2, y2, fill=fill_color, outline='black', width=1, tags=('task',)
        )

        # Draw left and right edges (for resizing)
        left_edge_id = self.controller.task_canvas.create_line(
            x1, y1, x1, y2, fill='black', width=2, tags=('task', 'resize', 'left')
        )

        right_edge_id = self.controller.task_canvas.create_line(
            x2, y1, x2, y2, fill='black', width=2, tags=('task', 'resize', 'right')
        )

        # Progress stripe along the bottom edge: how much of the task is done
        # as of its latest status update, once work has started.
        progress_stripe_id = None
        progress_fraction = self.controller.model.get_task_progress_fraction(task_id)
        if progress_fraction is not None and x2 > x1:
            stripe_height = 4
            stripe_x2 = x1 + (x2 - x1) * progress_fraction
            progress_stripe_id = self.controller.task_canvas.create_rectangle(
                x1,
                y2 - stripe_height,
                stripe_x2,
                y2,
                fill='#1F4E79',
                outline='',
                tags=('task', 'progress_stripe'),
            )

        # Chain stripe along the top edge: which chain (critical/feeding-NN)
        # this task belongs to, if assigned. Kept separate from the task's own
        # free-form `color` fill so assigning a chain doesn't take over a
        # user's existing color-coding for unrelated purposes.
        chain_stripe_id = None
        chain = self.controller.model.get_chain_by_id(task.get('chain_id'))
        if chain:
            stripe_height = 4
            chain_stripe_id = self.controller.task_canvas.create_rectangle(
                x1,
                y1,
                x2,
                y1 + stripe_height,
                fill=chain['color'],
                outline='',
                tags=('task', 'chain_stripe'),
            )

        # Full Kit indicator: a small glance-able badge in the top-left corner,
        # present once the task has been marked full-kit-done. Informational
        # only - not a gate on recording remaining duration - but needs to be
        # visible without hovering so upcoming tasks can be scanned at a glance.
        fullkit_indicator_id = None
        if task.get('fullkit_date'):
            badge_radius = 5
            badge_x = x1 + badge_radius + 2
            badge_y = y1 + badge_radius + 2
            fullkit_indicator_id = self.controller.task_canvas.create_oval(
                badge_x - badge_radius,
                badge_y - badge_radius,
                badge_x + badge_radius,
                badge_y + badge_radius,
                fill='#2E8B57',
                outline='black',
                width=1,
                tags=('task', 'fullkit_indicator'),
            )

        # Determine vertical position for text elements based on whether we show tags
        # Scale the offset based on font size
        text_y_offset = (
            -self.controller.task_font_size / 2
            if (self.show_tags_var.get() and 'tags' in task and task['tags'])
            else 0
        )

        # Create a text background based on task state
        text_bg = None
        text_color = 'black'  # Default text color

        if task_state == 'buffered':
            # Dark gray background for buffered tasks
            text_bg = '#777777'  # Slightly lighter than #555555 for better contrast
            text_color = 'white'  # White text for contrast
        elif task_state == 'done':
            # Green background for completed tasks
            text_bg = '#90EE90'  # Light green
            text_color = 'black'  # Black text for contrast

        # Show remaining duration if available (for non-completed tasks)
        remaining_duration = self.controller.model.get_latest_remaining_duration(
            task['task_id']
        )
        base_text = (
            f'{task_id} - {description}'
            if self.show_task_names_var.get()
            else f'{task_id}'
        )
        display_text = base_text

        if remaining_duration is not None and task_state != 'done':
            display_text = f'{base_text} ({remaining_duration}/{task["duration"]})'

        # Variables to store IDs
        text_id = None
        text_bg_id = None
        tag_id = None
        tag_bg_id = None

        # For URL text, use blue color but maintain the background color for state indication
        if task.get('url') and isinstance(task['url'], str) and task['url'].strip():
            # First create background rectangle if needed
            if text_bg:
                # Get text dimensions first by creating and measuring the text
                temp_text_id = self.controller.task_canvas.create_text(
                    (x1 + x2) / 2,
                    (y1 + y2) / 2 + text_y_offset,
                    text=display_text,
                    fill='blue' if text_color == 'black' else text_color,
                    font=('Arial', self.controller.task_font_size),
                    tags=('task_temp',),
                )

                # Get text bounds
                bbox = self.controller.task_canvas.bbox(temp_text_id)
                # Delete the temporary text
                self.controller.task_canvas.delete(temp_text_id)

                # Create background with padding
                padding = 3
                text_bg_id = self.controller.task_canvas.create_rectangle(
                    bbox[0] - padding,
                    bbox[1] - padding,
                    bbox[2] + padding,
                    bbox[3] + padding,
                    fill=text_bg,
                    outline='',
                    tags=('task', 'text_bg', f'text_bg_{task_id}'),
                )

            # Create the text (a URL)
            text_id = self.controller.task_canvas.create_text(
                (x1 + x2) / 2,
                (y1 + y2) / 2 + text_y_offset,
                text=display_text,
                fill='blue'
                if text_color == 'black'
                else text_color,  # Blue for URLs, unless contrast needed
                font=('Arial', self.controller.task_font_size),
                tags=('task', 'url', f'task_{task_id}'),
            )

            # Double-click (not a plain click) opens the URL: task_canvas
            # already has an unconditional, canvas-wide <ButtonPress-1>
            # binding for select/drag/resize (on_task_press), which fires
            # for every click regardless of what item is under it. A plain
            # <Button-1> tag_bind here would fire *in addition* to that on
            # every single click of this text - not instead of it - so a
            # single click on a URL task would always launch a browser
            # alongside whatever selection/drag it was actually meant to
            # start. Double-click has no such competing binding on
            # task_canvas, so it's free to mean "open" the same way it
            # conventionally does for a hyperlink elsewhere (Ctrl+Click was
            # not an option - it already means multi-select here).
            self.controller.task_canvas.tag_bind(
                text_id,
                '<Double-Button-1>',
                lambda e, url=task['url']: self.open_url(url),
            )
        else:
            # Regular task ID and description (non-URL)
            # First create background rectangle if needed
            if text_bg:
                # Get text dimensions first by creating and measuring the text
                temp_text_id = self.controller.task_canvas.create_text(
                    (x1 + x2) / 2,
                    (y1 + y2) / 2 + text_y_offset,
                    text=display_text,
                    fill=text_color,
                    font=('Arial', self.controller.task_font_size),
                    tags=('task_temp',),
                )

                # Get text bounds
                bbox = self.controller.task_canvas.bbox(temp_text_id)
                # Delete the temporary text
                self.controller.task_canvas.delete(temp_text_id)

                # Create background with padding
                padding = 3
                text_bg_id = self.controller.task_canvas.create_rectangle(
                    bbox[0] - padding,
                    bbox[1] - padding,
                    bbox[2] + padding,
                    bbox[3] + padding,
                    fill=text_bg,
                    outline='',
                    tags=('task', 'text_bg', f'text_bg_{task_id}'),
                )

            # Create the text
            text_id = self.controller.task_canvas.create_text(
                (x1 + x2) / 2,
                (y1 + y2) / 2 + text_y_offset,
                text=display_text,
                fill=text_color,
                font=('Arial', self.controller.task_font_size),
                tags=('task', 'task_text', f'task_{task_id}'),
            )

        # Draw tags if present and enabled with dynamic font size and position
        if 'tags' in task and task['tags'] and self.show_tags_var.get():
            tag_text = ', '.join(task['tags'])

            # First create background rectangle if needed
            if text_bg:
                # Create a temporary tag text to measure it
                temp_tag_id = self.controller.task_canvas.create_text(
                    (x1 + x2) / 2,
                    (y1 + y2) / 2 + self.controller.task_font_size,
                    text=f'[{tag_text}]',
                    font=('Arial', self.controller.tag_font_size),
                    tags=('task_temp',),
                )

                # Get text bounds
                bbox = self.controller.task_canvas.bbox(temp_tag_id)
                # Delete the temporary text
                self.controller.task_canvas.delete(temp_tag_id)

                # Create background with padding
                padding = 2
                tag_bg_id = self.controller.task_canvas.create_rectangle(
                    bbox[0] - padding,
                    bbox[1] - padding,
                    bbox[2] + padding,
                    bbox[3] + padding,
                    fill=text_bg,
                    outline='',
                    tags=('task', 'tag_bg', f'tag_bg_{task_id}'),
                )

            # Create the tag text
            tag_id = self.controller.task_canvas.create_text(
                (x1 + x2) / 2,
                (y1 + y2) / 2
                + self.controller.task_font_size,  # Scale offset with font size
                text=f'[{tag_text}]',
                font=('Arial', self.controller.tag_font_size),  # Use dynamic font size
                fill=text_color,  # Use same color as main text
                tags=('task', 'task_tags', f'task_tags_{task_id}'),
            )

        # Add grab connector circle - scale the size with zoom. Shared with
        # the hit-test in on_task_press/on_task_hover so drawn size and
        # clickable size can never drift apart.
        connector_radius = self.controller.connector_hit_radius()
        connector_x = x2
        connector_y = (y1 + y2) / 2
        connector_id = self.controller.task_canvas.create_oval(
            connector_x - connector_radius,
            connector_y - connector_radius,
            connector_x + connector_radius,
            connector_y + connector_radius,
            fill='lightgray',
            outline='black',
            width=1,
            tags=('task', 'connector', f'connector_{task_id}'),
        )

        # Store UI elements for this task
        self.task_ui_elements[task_id] = {
            'box': box_id,
            'left_edge': left_edge_id,
            'right_edge': right_edge_id,
            'text': text_id,
            'x1': x1,
            'y1': y1,
            'x2': x2,
            'y2': y2,
            # A string, not a bool: several call sites iterate this dict's
            # *values* with `isinstance(element_id, int)` to find canvas
            # item ids to delete/raise - and bool is a subclass of int in
            # Python, so a stored True/False would be picked up as if it
            # were itself a real (and likely colliding) canvas item id.
            'task_type': task.get('type'),
            'connector': connector_id,
            'connector_x': connector_x,
            'connector_y': connector_y,
        }

        # Add task background element to UI elements if it exists
        if text_bg_id:
            self.task_ui_elements[task_id]['text_bg'] = text_bg_id

        # Add tag element to UI elements if it exists
        if tag_id:
            self.task_ui_elements[task_id]['tag_text'] = tag_id

        # Add tag background element if it exists
        if tag_bg_id:
            self.task_ui_elements[task_id]['tag_bg'] = tag_bg_id

        # Add highlight to UI elements if it exists
        if highlight_id:
            self.task_ui_elements[task_id]['highlight'] = highlight_id

        # Add progress stripe / full kit indicator / chain stripe to UI elements
        # if they exist
        if progress_stripe_id:
            self.task_ui_elements[task_id]['progress_stripe'] = progress_stripe_id
        if fullkit_indicator_id:
            self.task_ui_elements[task_id]['fullkit_indicator'] = fullkit_indicator_id
        if chain_stripe_id:
            self.task_ui_elements[task_id]['chain_stripe'] = chain_stripe_id

        # Add tooltips for all task properties
        self.add_task_tooltips(task)

        # Newly-created canvas items always land on top of the existing
        # stack, regardless of any positional overlap - so drawing an
        # ordinary task after an already-drawn buffer (e.g. a drag/resize
        # release redrawing just the moved task, or simply a later task in
        # a full grid redraw) would otherwise bury that buffer's box/text
        # under the new one, hiding it entirely even though nothing about
        # the buffer itself changed. Re-raise every already-drawn buffer's
        # items back above whatever was just drawn, every time - cheap
        # relative to a redraw, and the alternative (finding and fixing
        # every call site that might redraw a task near a buffer) is far
        # more fragile.
        if not is_buffer:
            for other_id, other_elements in self.task_ui_elements.items():
                if other_id == task_id or other_elements.get('task_type') not in (
                    'project_buffer',
                    'feeding_buffer',
                ):
                    continue
                for element_id in other_elements.values():
                    if isinstance(element_id, int):
                        self.controller.task_canvas.tag_raise(element_id)

    def update_task_ui(self, task):
        """Updates the UI elements for a specific task."""
        task_id = task['task_id']
        if task_id in self.task_ui_elements:
            # We need to completely redraw the task to reflect any state changes
            # First, delete all current UI elements
            for element_id in self.task_ui_elements[task_id].values():
                if isinstance(element_id, int):  # Check if it's a canvas item ID
                    self.controller.task_canvas.delete(element_id)

            # Now redraw the task
            self.draw_task(task)

    def highlight_selected_tasks(self):
        """Highlight all selected tasks with an orange border"""
        # First remove any existing highlights
        self.remove_task_selections()

        # Highlight all tasks in the selected_tasks list
        for task in self.controller.selected_tasks:
            task_id = task['task_id']
            if task_id in self.task_ui_elements:
                ui_elements = self.task_ui_elements[task_id]
                x1, y1, x2, y2 = (
                    ui_elements['x1'],
                    ui_elements['y1'],
                    ui_elements['x2'],
                    ui_elements['y2'],
                )

                # Create orange highlight border (slightly larger than the task)
                highlight_id = self.controller.task_canvas.create_rectangle(
                    x1 - 2,
                    y1 - 2,
                    x2 + 2,
                    y2 + 2,
                    outline='orange',
                    width=2,
                    tags=('selection_highlight',),
                )

                # Store the highlight ID in the UI elements dictionary
                ui_elements['highlight'] = highlight_id

                # Ensure the highlight is behind the task
                self.controller.task_canvas.tag_lower(highlight_id)

        self.controller.update_multi_select_status()
        self._sync_notes_panel_to_selection()

    def remove_task_selections(self):
        """Remove highlighting from all tasks"""
        # Delete all selection highlights
        self.controller.task_canvas.delete('selection_highlight')

        # Remove highlight references from UI elements
        for ui_elements in self.task_ui_elements.values():
            if 'highlight' in ui_elements:
                del ui_elements['highlight']

        self._sync_notes_panel_to_selection()

    def _sync_notes_panel_to_selection(self):
        """Refresh the notes panel to follow the current selection, if the
        panel is open. Called from the two selection-visual updaters
        (highlight/remove), which every selection change funnels through -
        selected_tasks is always updated before they run. No-ops when the
        shown selection hasn't changed, so the highlight path's
        remove-then-highlight sequence rebuilds the panel once, not twice.
        """
        if not getattr(self, 'notes_panel_visible', False):
            return
        ids = [t['task_id'] for t in self.controller.selected_tasks]
        if ids == getattr(self, '_notes_panel_selection', None):
            return
        self.update_notes_panel()

    def select_all_tasks(self):
        """Select all visible tasks"""
        if not self.controller.multi_select_mode:
            # Enable multi-select mode if not already enabled
            self.controller.toggle_multi_select_mode()

        # Get the filtered tasks (visible tasks)
        visible_tasks = self.controller.tag_ops.get_filtered_tasks()

        # Set as selected tasks
        self.controller.selected_tasks = visible_tasks.copy()

        # Update highlighting
        self.highlight_selected_tasks()

    def clear_selections(self):
        """Clear all task selections"""
        self.controller.selected_tasks = []
        self.remove_task_selections()
        self.controller.update_multi_select_status()

    def add_tag_to_selected_tasks(self):
        """Add a tag to all selected tasks with improved tag selection dialog"""
        if not self.controller.selected_tasks:
            return

        # Create a custom dialog for tag selection
        dialog = tk.Toplevel(self.controller.root)
        dialog.title('Add Tag to Selected Tasks')
        dialog.transient(self.controller.root)
        dialog.grab_set()

        # Position the dialog
        x = self.controller.root.winfo_rootx() + 50
        y = self.controller.root.winfo_rooty() + 50
        dialog.geometry(f'400x400+{x}+{y}')

        # Main frame with padding
        main_frame = tk.Frame(dialog, padx=10, pady=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Instruction label
        tk.Label(
            main_frame,
            text=f'Add tag to {len(self.controller.selected_tasks)} selected tasks:',
            anchor='w',
        ).pack(fill=tk.X, pady=(0, 10))

        # Create frame for entry and suggestions
        entry_frame = tk.Frame(main_frame)
        entry_frame.pack(fill=tk.X, pady=5)

        # Input for new tag
        tk.Label(entry_frame, text='Tag:', anchor='w').pack(side=tk.LEFT, padx=(0, 5))
        tag_var = tk.StringVar()
        tag_entry = tk.Entry(entry_frame, textvariable=tag_var)
        tag_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tag_entry.focus_set()

        # Function to validate and add tag
        def add_tag():
            tag = tag_var.get().strip()
            if not tag:
                return

            # Validate tag (only letters, numbers, underscore, hyphen, no spaces)
            import re

            if not re.match(r'^[\w\-]+$', tag):
                messagebox.showerror(
                    'Invalid Tag',
                    'Tags can only contain letters, numbers, underscores, and hyphens.',
                    parent=dialog,
                )
                return

            # Add tag to all selected tasks
            for task in self.controller.selected_tasks:
                self.controller.model.add_tags_to_task(task['task_id'], [tag])

            # Refresh the view
            self.controller.update_view()
            dialog.destroy()

        # Suggestions section
        suggestion_frame = tk.Frame(main_frame)
        suggestion_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        tk.Label(
            suggestion_frame, text='Or select from existing tags:', anchor='w'
        ).pack(fill=tk.X)

        # Create scrollable frame for existing tags
        suggestion_scroll_frame = tk.Frame(suggestion_frame)
        suggestion_scroll_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        scroll_y = ttk.Scrollbar(suggestion_scroll_frame, orient='vertical')
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)

        # Listbox for tag suggestions
        existing_tags = sorted(self.controller.model.get_all_tags())
        tag_listbox = tk.Listbox(suggestion_scroll_frame, yscrollcommand=scroll_y.set)
        tag_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll_y.config(command=tag_listbox.yview)

        # Populate listbox with existing tags
        for tag in existing_tags:
            tag_listbox.insert(tk.END, tag)

        # Handle selection from listbox
        def on_tag_select(event):
            # Get selected tag from listbox
            if tag_listbox.curselection():
                selected_tag = tag_listbox.get(tag_listbox.curselection()[0])
                tag_var.set(selected_tag)

        tag_listbox.bind('<<ListboxSelect>>', on_tag_select)

        # Double-click to select and close
        def on_tag_double_click(event):
            on_tag_select(event)
            add_tag()

        tag_listbox.bind('<Double-1>', on_tag_double_click)

        # Button frame
        button_frame = tk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        # Add buttons
        tk.Button(button_frame, text='Cancel', command=dialog.destroy).pack(
            side=tk.RIGHT, padx=5
        )
        tk.Button(button_frame, text='Add Tag', command=add_tag).pack(
            side=tk.RIGHT, padx=5
        )

        # Bind Enter key to add_tag function
        dialog.bind('<Return>', lambda e: add_tag())

        # Make sure dialog is centered
        dialog.update_idletasks()
        width = dialog.winfo_width()
        height = dialog.winfo_height()
        x = (
            self.controller.root.winfo_rootx()
            + (self.controller.root.winfo_width() - width) // 2
        )
        y = (
            self.controller.root.winfo_rooty()
            + (self.controller.root.winfo_height() - height) // 2
        )
        dialog.geometry(f'+{x}+{y}')

        add_resize_handle(dialog)

    def remove_tag_from_selected_tasks(self):
        """Remove a tag from all selected tasks"""
        if not self.controller.selected_tasks:
            return

        # Collect all unique tags from selected tasks
        all_tags = set()
        for task in self.controller.selected_tasks:
            if 'tags' in task and task['tags']:
                for tag in task['tags']:
                    all_tags.add(tag)

        if not all_tags:
            messagebox.showinfo('No Tags', "The selected tasks don't have any tags.")
            return

        # Create a dialog to choose which tag to remove
        dialog = tk.Toplevel(self.controller.root)
        dialog.title('Remove Tag')
        dialog.transient(self.controller.root)
        dialog.grab_set()

        # Position the dialog
        x = self.controller.root.winfo_rootx() + 50
        y = self.controller.root.winfo_rooty() + 50
        dialog.geometry(f'300x300+{x}+{y}')

        tk.Label(dialog, text='Select tag to remove:').pack(pady=10)

        listbox = tk.Listbox(dialog)
        listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        for tag in sorted(all_tags):
            listbox.insert(tk.END, tag)

        button_frame = tk.Frame(dialog)
        button_frame.pack(fill=tk.X, pady=10)

        def on_remove():
            selected_indices = listbox.curselection()
            if not selected_indices:
                return

            tag = listbox.get(selected_indices[0])

            # Remove tag from all selected tasks
            for task in self.controller.selected_tasks:
                self.controller.model.remove_tags_from_task(task['task_id'], [tag])

            # Refresh the view
            self.controller.update_view()
            dialog.destroy()

        tk.Button(button_frame, text='Remove', command=on_remove).pack(
            side=tk.RIGHT, padx=10
        )
        tk.Button(button_frame, text='Cancel', command=dialog.destroy).pack(
            side=tk.RIGHT
        )

        add_resize_handle(dialog)

    def delete_selected_tasks(self):
        """Delete all selected tasks"""
        if not self.controller.selected_tasks:
            return

        # Confirm deletion
        count = len(self.controller.selected_tasks)
        if not messagebox.askyesno(
            'Confirm Delete',
            f'Are you sure you want to delete {count} selected task{"s" if count > 1 else ""}?',
            parent=self.controller.root,
        ):
            return

        # Delete tasks
        for task in self.controller.selected_tasks.copy():
            self.controller.model.delete_task(task['task_id'])

        # Clear selection and update view
        self.controller.selected_tasks = []
        self.controller.selected_task = None
        self.controller.update_view()

    def set_selected_task_color(self, color):
        """Set the color of the selected task."""
        if not self.controller.selected_task:
            return

        task_id = self.controller.selected_task['task_id']

        # Update the model
        self.controller.model.set_task_color(task_id, color)

        # Update the UI element
        if task_id in self.task_ui_elements:
            box_id = self.task_ui_elements[task_id]['box']
            self.controller.task_canvas.itemconfig(box_id, fill=color)

            # Update the task's color in the model
            self.controller.selected_task['color'] = color

    def set_selected_tasks_color(self, color):
        """Set the color of all selected tasks."""
        if not self.controller.selected_tasks:
            return

        # Get the IDs of all selected tasks
        task_ids = [task['task_id'] for task in self.controller.selected_tasks]

        # Update the model
        self.controller.model.set_task_colors(task_ids, color)

        # Update the UI elements
        for task in self.controller.selected_tasks:
            task_id = task['task_id']
            if task_id in self.task_ui_elements:
                box_id = self.task_ui_elements[task_id]['box']
                self.controller.task_canvas.itemconfig(box_id, fill=color)

                # Update the task's color in the model
                task['color'] = color

    # In src/view/ui_components.py
    # Update the create_notes_panel method

    def create_notes_panel(self):
        """Create the collapsible notes panel on the right side."""
        # Create the panel frame
        self.notes_panel_visible = False
        self.notes_panel_width = 300  # Default width

        # Main notes panel frame
        self.notes_panel_frame = tk.Frame(
            self.controller.horizontal_layout_frame,
            width=self.notes_panel_width,
            bg='#f0f0f0',
        )

        # Header frame with title and close button
        header_frame = tk.Frame(self.notes_panel_frame, bg='#e0e0e0', padx=5, pady=5)
        header_frame.pack(fill=tk.X)

        # Title and close button
        tk.Label(
            header_frame, text='Task Notes', font=('Arial', 11, 'bold'), bg='#e0e0e0'
        ).pack(side=tk.LEFT)
        close_button = tk.Button(
            header_frame,
            text='×',
            command=self.toggle_notes_panel,
            font=('Arial', 12),
            bd=0,
            bg='#e0e0e0',
            padx=5,
        )
        close_button.pack(side=tk.RIGHT)

        # Notes filter options
        filter_frame = tk.Frame(self.notes_panel_frame, bg='#f0f0f0', padx=5, pady=5)
        filter_frame.pack(fill=tk.X)

        # Label for filter status
        self.filter_label = tk.Label(
            filter_frame,
            text='Showing all notes',
            font=('Arial', 9),
            bg='#f0f0f0',
            anchor='w',
        )
        self.filter_label.pack(fill=tk.X, pady=(0, 5))

        # Notes content area with scrollbar
        notes_content_frame = tk.Frame(self.notes_panel_frame)
        notes_content_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        notes_scrollbar = ttk.Scrollbar(notes_content_frame)
        notes_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Canvas for scrolling
        self.notes_canvas = tk.Canvas(
            notes_content_frame,
            yscrollcommand=notes_scrollbar.set,
            bg='white',
            highlightthickness=0,
        )
        self.notes_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        notes_scrollbar.config(command=self.notes_canvas.yview)

        # Frame inside canvas for notes
        self.notes_container = tk.Frame(self.notes_canvas, bg='white')
        self.notes_canvas_window = self.notes_canvas.create_window(
            (0, 0), window=self.notes_container, anchor='nw', tags='notes_container'
        )

        # Update canvas scroll region when the size changes
        self.notes_container.bind(
            '<Configure>',
            lambda e: self.notes_canvas.configure(
                scrollregion=self.notes_canvas.bbox('all')
            ),
        )

        # Bind the canvas to update the width of the container when its size changes
        self.notes_canvas.bind(
            '<Configure>',
            lambda e: self.notes_canvas.itemconfig(
                self.notes_canvas_window, width=e.width
            ),
        )

        # Don't pack the frame yet - we'll do that in toggle_notes_panel

    def toggle_notes_panel(self):
        """Toggle the visibility of the notes panel."""
        if not hasattr(self, 'notes_panel_frame'):
            # First time, create the panel
            self.create_notes_panel()
            # Initially hidden, so make it visible
            self.notes_panel_frame.pack(side=tk.RIGHT, fill=tk.Y)
            self.notes_panel_visible = True
            # Update the panel content
            self.update_notes_panel()
            # Allow the UI to update and properly draw everything
            self.controller.root.update_idletasks()
            return

        if self.notes_panel_visible:
            # Hide the panel
            self.notes_panel_frame.pack_forget()
            self.notes_panel_visible = False
        else:
            # Show the panel
            self.notes_panel_frame.pack(side=tk.RIGHT, fill=tk.Y)
            self.notes_panel_visible = True
            # Update notes display
            self.update_notes_panel()

    def show_notes_panel(self, task_ids=None):
        """Show the notes panel and focus on specified task(s)."""
        if not hasattr(self, 'notes_panel_frame'):
            self.create_notes_panel()

        # Make sure the panel is visible
        if not self.notes_panel_visible:
            self.notes_panel_frame.pack(side=tk.RIGHT, fill=tk.Y)
            self.notes_panel_visible = True

        # Update the panel with focus on specified tasks
        self.update_notes_panel(task_ids)

    def update_notes_panel(self, task_ids=None):
        """Update the notes panel content. Without explicit `task_ids`,
        the panel follows the current selection: notes for the selected
        task(s) when there is one, every note when nothing is selected -
        so all three lookups (all / one / several) come from the same
        panel, driven by what's selected on the grid."""
        if not hasattr(self, 'notes_container'):
            return

        if task_ids is None and self.controller.selected_tasks:
            task_ids = [t['task_id'] for t in self.controller.selected_tasks]

        # Remember what's shown so selection-driven refreshes can no-op
        # when the selection hasn't actually changed
        self._notes_panel_selection = list(task_ids) if task_ids else []

        # Clear existing notes
        for widget in self.notes_container.winfo_children():
            widget.destroy()

        # Update filter label
        if task_ids:
            if len(task_ids) == 1:
                task = self.controller.model.get_task(task_ids[0])
                if task:
                    self.filter_label.config(
                        text=f'Showing notes for Task {task_ids[0]}: {task["description"]}'
                    )
                else:
                    self.filter_label.config(
                        text=f'Showing notes for Task {task_ids[0]}'
                    )
            else:
                self.filter_label.config(
                    text=f'Showing notes for {len(task_ids)} selected tasks'
                )
        else:
            self.filter_label.config(text='Showing all notes')

        # Get notes from the model
        notes = self.controller.get_notes_for_display(task_ids)

        # Display message if no notes
        if not notes:
            no_notes_label = tk.Label(
                self.notes_container,
                text='No notes found',
                fg='gray',
                bg='white',
                pady=20,
            )
            no_notes_label.pack(fill=tk.X)
            return

        # Add each note to the container
        for i, note in enumerate(notes):
            # Store the original index in the task's notes array
            note['original_index'] = note.get('original_index', i)
            self._create_note_item(note, i)

        # Update the canvas scroll region
        self.notes_canvas.update_idletasks()
        self.notes_canvas.configure(scrollregion=self.notes_canvas.bbox('all'))

    # In src/view/ui_components.py
    # Update the _create_note_item method

    def _create_note_item(self, note, display_index):
        """Create a UI element for a single note."""
        # Create a frame for the note with a border
        note_frame = NoteFrame(
            self.notes_container, bd=1, relief=tk.SOLID, padx=8, pady=8
        )
        note_frame.pack(fill=tk.X, padx=5, pady=5)

        # Store reference information directly in the frame using attributes
        note_frame.task_id = note.get('task_id')
        note_frame.original_index = note.get('original_index', 0)
        note_frame.display_index = display_index

        # Header with task info and timestamp
        header_frame = tk.Frame(note_frame)
        header_frame.pack(fill=tk.X, pady=(0, 5))

        # Format timestamp
        try:
            timestamp = datetime.fromisoformat(note['timestamp'])
            formatted_time = timestamp.strftime('%Y-%m-%d %H:%M:%S')
        except (ValueError, TypeError):
            formatted_time = note.get('timestamp', 'Unknown time')

        # Task info
        task_id = note.get('task_id', 'Unknown')
        task_desc = note.get('task_description', f'Task {task_id}')

        # Task link (clickable to select the task)
        task_link = tk.Label(
            header_frame,
            text=f'Task {task_id}: {task_desc}',
            fg='blue',
            cursor='hand2',
            font=('Arial', 9, 'underline'),
        )
        task_link.pack(side=tk.LEFT)

        # Bind click event to select the task
        task_link.bind(
            '<Button-1>', lambda e, tid=task_id: self._select_task_from_note(tid)
        )

        # Timestamp
        time_label = tk.Label(
            header_frame, text=formatted_time, fg='gray', font=('Arial', 8)
        )
        time_label.pack(side=tk.RIGHT)

        # Note content
        note_text = note.get('text', '').strip()
        text_frame = tk.Frame(note_frame)
        text_frame.pack(fill=tk.X, pady=5)

        content_label = tk.Label(
            text_frame,
            text=note_text,
            justify=tk.LEFT,
            wraplength=self.notes_panel_width - 40,
            anchor='w',
        )
        content_label.pack(fill=tk.X)

        # Footer with delete button
        footer_frame = tk.Frame(note_frame)
        footer_frame.pack(fill=tk.X, pady=(5, 0))

        # Delete button that passes the stored task_id and original_index
        delete_button = tk.Button(
            footer_frame,
            text='Delete',
            command=lambda f=note_frame: self._delete_note(f.task_id, f.original_index),
            font=('Arial', 8),
            padx=5,
            pady=0,
        )
        delete_button.pack(side=tk.RIGHT)

    def _select_task_from_note(self, task_id):
        """Select a task when its link is clicked in a note."""
        task = self.controller.model.get_task(task_id)
        if task:
            # Clear current selections
            self.controller.selected_tasks = []
            self.remove_task_selections()

            # Select this task
            self.controller.selected_task = task
            self.controller.selected_tasks = [task]

            # Highlight the task
            self.highlight_selected_tasks()

            # Scroll to make the task visible
            if task_id in self.task_ui_elements:
                ui_elements = self.task_ui_elements[task_id]
                x1, y1 = ui_elements['x1'], ui_elements['y1']

                # Calculate scroll fractions
                canvas_width = self.controller.task_canvas.winfo_width()
                canvas_height = self.controller.task_canvas.winfo_height()
                total_width = self.controller.cell_width * self.controller.model.days
                total_height = (
                    self.controller.task_height * self.controller.model.max_rows
                )

                x_fraction = max(0, min(1, (x1 - canvas_width / 4) / total_width))
                y_fraction = max(0, min(1, (y1 - canvas_height / 4) / total_height))

                # Scroll to show the task
                self.controller.task_canvas.xview_moveto(x_fraction)
                self.controller.task_canvas.yview_moveto(y_fraction)

    # In src/view/ui_components.py
    # Update the _delete_note method

    def _delete_note(self, task_id, original_index):
        """Delete a note directly using task_id and original_index.

        Args:
            task_id: The ID of the task containing the note
            original_index: The original index of the note within the task's notes array
        """
        task = self.controller.model.get_task(task_id)
        if not task or 'notes' not in task:
            messagebox.showerror('Error', f'Task {task_id} not found or has no notes.')
            return False

        # Make sure the index is valid for this specific task
        if original_index < 0 or original_index >= len(task['notes']):
            messagebox.showerror(
                'Error',
                f'Invalid note index: {original_index}. Task {task_id} has {len(task["notes"])} notes.',
            )
            return False

        # Get the note text for the confirmation message
        note_text = task['notes'][original_index].get('text', '').strip()
        if len(note_text) > 50:
            note_text = note_text[:47] + '...'

        confirm_message = (
            f'Are you sure you want to delete this note?\n\n'
            f'Task ID: {task_id}\n'
            f'Task Description: {task.get("description", "Unknown")}\n'
            f'Note Text: {note_text}'
        )

        if messagebox.askyesno('Confirm Delete', confirm_message):
            # Delete the note directly from the task's notes array
            if self.controller.model.delete_note_from_task(task_id, original_index):
                self.update_notes_panel()
                return True
            else:
                messagebox.showerror(
                    'Error',
                    'Failed to delete note. This may be due to a data inconsistency.',
                )
                return False

    def _darken_color(self, color_name):
        """Returns a darker version of the given color."""
        from src.utils.colors import WEB_COLORS

        # Get the hex value for the color
        hex_color = WEB_COLORS.get(color_name, '#CCCCCC')

        # Convert hex to RGB
        r = int(hex_color[1:3], 16)
        g = int(hex_color[3:5], 16)
        b = int(hex_color[5:7], 16)

        # Darken the color by a factor
        factor = 0.7  # 70% of original brightness
        r = int(r * factor)
        g = int(g * factor)
        b = int(b * factor)

        # Convert back to hex
        return f'#{r:02x}{g:02x}{b:02x}'
