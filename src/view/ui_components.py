import tkinter as tk
from tkinter import ttk
from tkinter import font as tkfont
import webbrowser
from datetime import datetime, timedelta
from src.view.menus.network_menu import NetworkMenu
from src.view.menus.help_menu import HelpMenu
from src.utils.colors import COLOR_NAMES, DEFAULT_TASK_COLOR
from src.model.dependency_notation import (
    LINK_TYPES_ORDERED,
    BUFFER_LINK_TYPES,
    format_predecessor_notation,
)
from src.model.task_resource_model import classify_fever_chart_zone


class UIComponents:
    def __init__(self, controller, model):
        self.controller = controller
        self.model = model
        self.create_context_menu()

        # Track UI-specific task data
        self.task_ui_elements = {}  # Maps task_id to UI elements
        self.dependency_link_map = {}  # Maps arrow canvas item id to (predecessor_id, successor_id)

        # Reference to network menu
        self.network_menu = None
        # Reference to help menu
        self.help_menu = None

    def is_setdate_in_range(self):
        """Check if the setdate is within the visible timeline range"""
        timeline_end_date = self.model.start_date + timedelta(days=self.model.days - 1)
        return self.model.start_date <= self.model.setdate <= timeline_end_date

    def update_setdate_display(self):
        """Update the setdate display in the top-left corner with wider column"""
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
            cal.pack(padx=10, pady=10)

            def set_date():
                selected_date = cal.selection_get()
                # Update model setdate
                self.model.setdate = datetime(
                    selected_date.year, selected_date.month, selected_date.day
                )
                # Update display
                self.update_setdate_display()
                # Update timeline view to highlight the date if in range
                self.draw_timeline()
                cal_dialog.destroy()

            # Add buttons
            button_frame = tk.Frame(cal_dialog)
            button_frame.pack(pady=10)

            tk.Button(button_frame, text='Set Date', command=set_date).pack(
                side=tk.LEFT, padx=5
            )
            tk.Button(button_frame, text='Cancel', command=cal_dialog.destroy).pack(
                side=tk.LEFT, padx=5
            )

        except ImportError:
            # If tkcalendar is not available, use a simple date entry dialog
            self._manual_date_entry_dialog()

    def _manual_date_entry_dialog(self):
        """Fallback method for date entry if tkcalendar is not available"""
        dialog = tk.Toplevel(self.controller.root)
        dialog.title('Set Current Date')
        dialog.transient(self.controller.root)
        dialog.grab_set()

        # Center dialog on parent window
        x = self.controller.root.winfo_rootx() + 50
        y = self.controller.root.winfo_rooty() + 50
        dialog.geometry(f'300x150+{x}+{y}')

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
                tk.messagebox.showerror(
                    'Invalid Date Format',
                    'Please enter a valid date in YYYY-MM-DD format.',
                    parent=dialog,
                )

        # Add buttons
        button_frame = tk.Frame(frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        tk.Button(button_frame, text='Set Date', command=set_date).pack(
            side=tk.RIGHT, padx=5
        )
        tk.Button(button_frame, text='Cancel', command=dialog.destroy).pack(
            side=tk.RIGHT, padx=5
        )

        # Bind Enter key
        dialog.bind('<Return>', lambda e: set_date())

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

        # File menu
        self.file_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label='File', menu=self.file_menu)

        # File operations
        self.file_menu.add_command(
            label='New', command=self.controller.file_ops.new_project
        )
        self.file_menu.add_command(
            label='Open...', command=self.controller.file_ops.open_file
        )
        self.file_menu.add_command(
            label='Save', command=self.controller.file_ops.save_file
        )
        self.file_menu.add_command(
            label='Save As...', command=self.controller.file_ops.save_file_as
        )
        self.file_menu.add_separator()
        self.file_menu.add_command(
            label='Import CCPM Schedule...',
            command=self.controller.file_ops.import_ccpm_schedule,
        )
        self.file_menu.add_separator()
        self.file_menu.add_command(label='Exit', command=self.controller.root.quit)

        # Add separator and export commands
        self.file_menu.add_separator()
        self.file_menu.add_command(
            label='Export...', command=self.controller.export_ops.open_export_dialog
        )

        # Edit menu
        self.edit_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label='Edit', menu=self.edit_menu)

        # Edit operations
        self.edit_menu.add_command(
            label='Add Resource...',
            command=lambda: self.controller.task_ops.add_resource(
                parent=self.controller.root
            ),
        )
        self.edit_menu.add_command(
            label='Edit Resources...',
            command=lambda: self.controller.task_ops.edit_resources(
                parent=self.controller.root
            ),
        )
        self.edit_menu.add_separator()
        self.edit_menu.add_command(
            label='Project Settings...',
            command=lambda: self.controller.task_ops.edit_project_settings(
                parent=self.controller.root
            ),
        )

        # Tasks menu (new)
        self.tasks_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label='Tasks', menu=self.tasks_menu)

        self.auto_scheduling_var = tk.BooleanVar(value=False)
        self.tasks_menu.add_checkbutton(
            label='Auto Scheduling',
            variable=self.auto_scheduling_var,
            command=self.controller.toggle_auto_scheduling,
        )

        # Filter menu (Stage 11 - renamed from 'Tags' now that project-based
        # filtering sits alongside tag-based filtering; 'Tags' no longer
        # described what this menu does)
        self.filter_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label='Filter', menu=self.filter_menu)

        self.filter_menu.add_command(
            label='Filter Tasks by Tags...',
            command=self.controller.tag_ops.filter_tasks_by_tags,
        )
        self.filter_menu.add_command(
            label='Filter Tasks by Project...',
            command=self.controller.tag_ops.filter_tasks_by_project,
        )
        self.filter_menu.add_command(
            label='Filter Resources by Tags...',
            command=self.controller.tag_ops.filter_resources_by_tags,
        )
        self.filter_menu.add_separator()
        self.filter_menu.add_command(
            label='Select Tasks by Tags...',
            command=self.controller.tag_ops.select_tasks_by_tag,
        )
        self.filter_menu.add_command(
            label='Toggle Multi-Select Mode',
            command=self.controller.toggle_multi_select_mode,
        )
        self.filter_menu.add_separator()
        self.filter_menu.add_command(
            label='Clear All Filters', command=self.controller.clear_all_filters
        )

        # View menu (new)
        self.view_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label='View', menu=self.view_menu)

        # View options for tags
        self.show_tags_var = tk.BooleanVar(value=True)
        self.view_menu.add_checkbutton(
            label='Show Tags on Tasks',
            variable=self.show_tags_var,
            command=self.controller.update_view,
        )

        # Add notes panel toggle to the View menu
        self.view_menu.add_separator()
        self.view_menu.add_command(
            label='Toggle Notes Panel', command=self.controller.toggle_notes_panel
        )

        # Add zoom options
        self.view_menu.add_separator()
        self.view_menu.add_command(
            label='Reset Zoom (Ctrl+0)', command=self.controller.reset_zoom
        )

        # Date menu
        self.date_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label='Date', menu=self.date_menu)

        # Date operations
        self.date_menu.add_command(
            label='Set Current Date...', command=self.edit_setdate
        )
        self.date_menu.add_command(
            label='Reset to Today', command=self.reset_setdate_to_today
        )

        # Projects menu
        self.projects_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label='Projects', menu=self.projects_menu)

        self.projects_menu.add_command(
            label='Manage Projects...',
            command=lambda: self.controller.task_ops.manage_projects_dialog(
                parent=self.controller.root
            ),
        )
        self.projects_menu.add_command(
            label='Project Fever Charts...',
            command=lambda: self.controller.task_ops.view_project_fever_charts(),
        )

        # Chains menu
        self.chains_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label='Chains', menu=self.chains_menu)

        self.chains_menu.add_command(
            label='Manage Chains...',
            command=lambda: self.controller.task_ops.manage_chains_dialog(
                parent=self.controller.root
            ),
        )

        # Add Network menu
        self.network_menu = NetworkMenu(
            self.controller, self.controller.root, self.menu_bar
        )

        # Add Help menu
        self.help_menu = HelpMenu(self.controller, self.controller.root, self.menu_bar)

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
        self.controller.timeline_label_canvas.create_text(
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
        # Right-click directly on a dependency arrow to edit its type/lag
        self.controller.task_canvas.tag_bind(
            'dependency', '<ButtonPress-3>', self.controller.task_ops.on_dependency_right_click
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

        # Measure (rather than guess) how much of main_frame's height is
        # consumed by everything other than task_frame/resource_frame -
        # timeline_frame, h_scrollbar, the resizer bar, and every pady
        # between them. Nothing here has settled its real geometry yet at
        # window resize time, and a guessed constant was consistently a bit
        # short, which was enough for main_frame's real requirement to
        # exceed its actual size and starve the status bar packed below it
        # on root. This is measured once, right after creation with the
        # frames still at their startup default heights, and stays valid
        # since none of these other pieces change size afterwards.
        self.controller.root.update_idletasks()
        self._pane_overhead = (
            self.controller.main_frame.winfo_height()
            - self.task_frame.winfo_height()
            - self.resource_frame.winfo_height()
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

        total_available = event.height - self._pane_overhead
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
        content_height = (
            len(self.controller.tag_ops.get_filtered_resources())
            * self.controller.task_height
        )
        resource_height = (
            min(ideal_resource_height, content_height)
            if content_height > 0
            else ideal_resource_height
        )
        resource_height = max(100, resource_height)
        task_height = max(100, ideal_task_height + (ideal_resource_height - resource_height))

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

        # Add color selection submenu
        self.color_menu = tk.Menu(self.context_menu, tearoff=0)
        self.context_menu.add_cascade(label='Set Task Color', menu=self.color_menu)

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
        self.context_menu.add_command(
            label='View Buffer History...',
            command=lambda: self.controller.task_ops.view_buffer_history(),
        )
        self.context_menu.add_command(
            label='View Fever Chart...',
            command=lambda: self.controller.task_ops.view_fever_chart(),
        )

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
        self.context_menu.add_separator()
        self.context_menu.add_command(
            label='Edit Resources',
            command=lambda: self.controller.task_ops.edit_resources(
                parent=self.controller.root
            ),
        )
        self.context_menu.add_command(
            label='Edit Project Settings',
            command=lambda: self.controller.task_ops.edit_project_settings(
                parent=self.controller.root
            ),
        )

        # Create resource context menu (new)
        self.resource_context_menu = tk.Menu(self.controller.root, tearoff=0)
        self.resource_context_menu.add_command(
            label='Edit Resource Tags',
            command=lambda: self.controller.tag_ops.edit_resource_tags(
                self.selected_resource_id
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
        total_available = self.controller.main_frame.winfo_height() - self._pane_overhead

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
            weekday_letters = ['M', 'T', 'W', 'T', 'F', 'S', 'S']
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
        return (
            (truncated + '...' + suffix) if truncated else ('...' + suffix)
        ), True

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
            tooltip_window.wm_geometry(f'+{x+10}+{y+10}')

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

            # Add state
            state = task.get('state', 'planning')
            tooltip_parts.append(f'Task state: {state}')

            # Add task type (task/project_buffer/feeding_buffer) - distinct from
            # Task state above; shown here so it's obvious at a glance whether a
            # task intended as a buffer was actually set as one via Set Task Type
            task_type = task.get('type', 'task')
            tooltip_parts.append(f"Task type: {task_type.replace('_', ' ').title()}")

            # Add project (name and its own planning/execution phase - not to be
            # confused with the task's own Task state above, a separate concept)
            project = self.controller.model.get_project_by_id(task.get('project_id'))
            if project:
                tooltip_parts.append(
                    f"Project: {project['name']} ({project['phase'].capitalize()})"
                )
            else:
                tooltip_parts.append('Project: None')

            # Add chain (critical/feeding-NN classification)
            chain = self.controller.model.get_chain_by_id(task.get('chain_id'))
            if chain:
                tooltip_parts.append(f"Chain: {chain['name']}")
            else:
                tooltip_parts.append('Chain: None')

            # Add predecessors/successors (compact link notation) - makes it
            # possible to follow/untangle feeding chains by hovering, without
            # having to open Help > task details for the same information.
            predecessor_text = format_predecessor_notation(task.get('predecessors', []))
            tooltip_parts.append(f"Predecessors: {predecessor_text or 'None'}")

            successor_ids = self.controller.model.get_successor_ids(task_id)
            successor_text = ', '.join(map(str, successor_ids))
            tooltip_parts.append(f"Successors: {successor_text or 'None'}")

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
                command=lambda t=link_type: self.controller.task_ops.set_dependency_type(
                    predecessor_id, successor_id, t
                ),
            )
        menu.add_cascade(label=f"Link Type ({link['type']})", menu=type_menu)

        menu.add_command(
            label=f"Set Lag... (current: {link['lag']})",
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

        menu.tk_popup(event.x_root, event.y_root)

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

        history = buffer_task.get('fever_chart_history', [])
        baseline = buffer_task.get('baseline')
        buffer_baseline_duration = (
            baseline['duration'] if baseline else buffer_task['duration']
        )

        points = []
        for entry in history:
            cpsl = entry['cpsl']
            progress_pct = (entry['ppf'] / cpsl * 100) if cpsl > 0 else 0.0
            consumption_pct = (
                (entry['forecast_lateness'] / buffer_baseline_duration * 100)
                if buffer_baseline_duration > 0
                else 0.0
            )
            points.append((entry['date'], progress_pct, consumption_pct))

        # y-axis range: at least 0-100%, extended if any point exceeds 100%
        # (consumption is never clamped for storage/calculation - only the
        # display floors negative values at 0, per the design notes).
        max_consumption = max([p[2] for p in points] + [100.0])
        y_max = max(100.0, ((max_consumption // 20) + 2) * 20)

        chart_x0, chart_y0 = x0 + 50, y0 + 34
        chart_w, chart_h = width - 70, height - 74

        def to_px(progress_pct, consumption_pct):
            px = chart_x0 + (progress_pct / 100.0) * chart_w
            clamped = max(0.0, min(y_max, consumption_pct))
            py = chart_y0 + (1 - clamped / y_max) * chart_h
            return px, py

        def boundary(x_pct, intercept):
            return max(0.0, min(y_max, slope * x_pct + intercept))

        # Title
        title = f'{buffer_task["task_id"]} - {buffer_task["description"]}'
        canvas.create_text(
            x0 + width / 2, y0, text=title, font=('Arial', 10, 'bold'), anchor='n'
        )

        # Zone bands (green / yellow / red), as three filled quadrilaterals
        # spanning the full 0-100% progress width.
        y_at_0 = boundary(0, yellow_intercept)
        y_at_100 = boundary(100, yellow_intercept)
        canvas.create_polygon(
            *to_px(0, 0), *to_px(100, 0), *to_px(100, y_at_100), *to_px(0, y_at_0),
            fill='#C8E6C9', outline='',
        )

        r_at_0 = boundary(0, red_intercept)
        r_at_100 = boundary(100, red_intercept)
        canvas.create_polygon(
            *to_px(0, y_at_0), *to_px(100, y_at_100), *to_px(100, r_at_100),
            *to_px(0, r_at_0),
            fill='#FFF59D', outline='',
        )

        canvas.create_polygon(
            *to_px(0, r_at_0), *to_px(100, r_at_100), *to_px(100, y_max),
            *to_px(0, y_max),
            fill='#EF9A9A', outline='',
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
            x0 + width / 2, y0 + height - 8,
            text='% of protected chain complete', font=('Arial', 8),
        )
        canvas.create_text(
            x0 + 10, y0 + 22, text='% buffer consumed', font=('Arial', 8),
            anchor='nw',
        )

        if not points:
            canvas.create_text(
                chart_x0 + chart_w / 2, chart_y0 + chart_h / 2,
                text='No status updates recorded yet', font=('Arial', 9), fill='#777777',
            )
            return

        # Trajectory: connect points in order, color each dot by its zone
        prev_px = None
        for date_str, progress_pct, consumption_pct in points:
            px, py = to_px(progress_pct, max(0.0, consumption_pct))
            if prev_px is not None:
                canvas.create_line(prev_px[0], prev_px[1], px, py, fill='black', width=1.5)
            zone = classify_fever_chart_zone(
                progress_pct, consumption_pct, slope, yellow_intercept, red_intercept
            )
            dot_color = {'green': '#2E7D32', 'yellow': '#F9A825', 'red': '#C62828'}[zone]
            canvas.create_oval(
                px - 4, py - 4, px + 4, py + 4, fill=dot_color, outline='black'
            )
            date_label = datetime.fromisoformat(date_str).strftime('%m-%d')
            canvas.create_text(px, py - 10, text=date_label, font=('Arial', 7))
            prev_px = (px, py)

    def draw_resource_grid(self):
        """Draw the resource loading grid with wider label column"""
        self.controller.resource_canvas.delete('all')
        self.controller.resource_label_canvas.delete('all')

        # Get filtered resources if filters are active
        resources_to_draw = self.controller.tag_ops.get_filtered_resources()

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

            # Create resource name with tag indicators
            resource_text = resource['name']
            resource_id = resource['id']

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
            if has_tags:
                name_y = y + self.controller.task_height / 4
                tag_y = y + self.controller.task_height * 3 / 4
            else:
                name_y = y + self.controller.task_height / 2

            # Draw resource name centered in wider column
            name_id = self.controller.resource_label_canvas.create_text(
                self.controller.label_column_width / 2,  # Center in wider column
                name_y,
                text=resource_text,
                anchor='center',
                font=(
                    'Arial',
                    self.controller.resource_font_size,
                ),  # Use dynamic font size
                tags=(f'resource_{resource_id}',),
            )

            # Bind event to the resource name
            self.controller.resource_label_canvas.tag_bind(
                f'resource_{resource_id}',
                '<ButtonPress-3>',
                lambda e, rid=resource_id: self.show_resource_context_menu(e, rid),
            )

            # Draw tags if present - centered in wider column
            if has_tags:
                tag_text = ', '.join(resource['tags'])
                full_text = f'[{tag_text}]'
                tag_font = tkfont.Font(family='Arial', size=self.controller.tag_font_size)
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

        # Get filtered resources
        filtered_resources = self.controller.tag_ops.get_filtered_resources()

        # Display resource loading for filtered resources
        for i, resource in enumerate(filtered_resources):
            resource_id = resource[
                'id'
            ]  # Get the resource ID which is the key in resource_loading

            for day in range(self.model.days):
                # Get resource capacity and loading
                capacity = resource['capacity'][day]
                load = resource_loading[resource_id][day]  # Use resource_id as the key

                # Calculate usage percentage
                usage_pct = (load / capacity) if capacity > 0 else float('inf')

                x = day * self.controller.cell_width
                y = i * self.controller.task_height

                # Choose color based on load vs capacity
                if usage_pct == 0:  # No usage
                    color = 'white'
                elif usage_pct < 0.8:  # Normal usage (< 80%)
                    intensity = min(int(usage_pct * 200), 200)
                    color = f'#{255-intensity:02x}{255-intensity:02x}ff'  # Bluish color
                elif usage_pct < 1.0:  # High usage (80-99%)
                    color = '#ffffcc'  # Light yellow
                else:  # Overloaded (>= 100%)
                    color = '#ffcccc'  # Light red

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

    def show_resource_context_menu(self, event, resource_id):
        """Show the context menu for a resource."""
        self.selected_resource_id = resource_id
        self.resource_context_menu.post(event.x_root, event.y_root)

    def open_url(self, url):
        """Open a URL in the default web browser"""
        webbrowser.open(url)

    def draw_task(self, task):
        """Draw a single task box with its information, accounting for dynamic row height"""
        task_id = task['task_id']
        row, col, duration = task['row'], task['col'], task['duration']
        description = task.get('description', 'No Description')

        # Get task color, default to Cyan if not set
        task_color = task.get('color', 'Cyan')

        # Get task state, default to 'planning' if not set
        task_state = task.get('state', 'planning')

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
        display_text = f'{task_id} - {description}'

        if remaining_duration is not None and task_state != 'done':
            display_text = (
                f'{task_id} - {description} ({remaining_duration}/{task["duration"]})'
            )

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

            # Bind click event to open the URL
            self.controller.task_canvas.tag_bind(
                text_id,
                '<Button-1>',
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

    def update_task_ui(self, task):
        """Updates the UI elements for a specific task."""
        task_id = task['task_id']
        if task_id in self.task_ui_elements:
            # We need to completely redraw the task to reflect any state changes
            # First, delete all current UI elements
            for key, element_id in self.task_ui_elements[task_id].items():
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

    def remove_task_selections(self):
        """Remove highlighting from all tasks"""
        # Delete all selection highlights
        self.controller.task_canvas.delete('selection_highlight')

        # Remove highlight references from UI elements
        for task_id, ui_elements in self.task_ui_elements.items():
            if 'highlight' in ui_elements:
                del ui_elements['highlight']

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
                tk.messagebox.showerror(
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
            tk.messagebox.showinfo('No Tags', "The selected tasks don't have any tags.")
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

    def delete_selected_tasks(self):
        """Delete all selected tasks"""
        if not self.controller.selected_tasks:
            return

        # Confirm deletion
        count = len(self.controller.selected_tasks)
        if not tk.messagebox.askyesno(
            'Confirm Delete',
            f"Are you sure you want to delete {count} selected task{'s' if count > 1 else ''}?",
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
        """Update the notes panel content."""
        if not hasattr(self, 'notes_container'):
            return

        # Clear existing notes
        for widget in self.notes_container.winfo_children():
            widget.destroy()

        # Update filter label
        if task_ids:
            if len(task_ids) == 1:
                task = self.controller.model.get_task(task_ids[0])
                if task:
                    self.filter_label.config(
                        text=f"Showing notes for Task {task_ids[0]}: {task['description']}"
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
        note_frame = tk.Frame(
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
            tk.messagebox.showerror(
                'Error', f'Task {task_id} not found or has no notes.'
            )
            return False

        # Make sure the index is valid for this specific task
        if original_index < 0 or original_index >= len(task['notes']):
            tk.messagebox.showerror(
                'Error',
                f"Invalid note index: {original_index}. Task {task_id} has {len(task['notes'])} notes.",
            )
            return False

        # Get the note text for the confirmation message
        note_text = task['notes'][original_index].get('text', '').strip()
        if len(note_text) > 50:
            note_text = note_text[:47] + '...'

        confirm_message = (
            f"Are you sure you want to delete this note?\n\n"
            f"Task ID: {task_id}\n"
            f"Task Description: {task.get('description', 'Unknown')}\n"
            f"Note Text: {note_text}"
        )

        if tk.messagebox.askyesno('Confirm Delete', confirm_message):
            # Delete the note directly from the task's notes array
            if self.controller.model.delete_note_from_task(task_id, original_index):
                self.update_notes_panel()
                return True
            else:
                tk.messagebox.showerror(
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
