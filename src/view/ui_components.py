import tkinter as tk
from tkinter import ttk
import webbrowser
from datetime import datetime, timedelta
from src.view.menus.network_menu import NetworkMenu
from src.view.menus.help_menu import HelpMenu
from src.utils.colors import COLOR_NAMES, DEFAULT_TASK_COLOR


class UIComponents:
    def __init__(self, controller, model):
        self.controller = controller
        self.model = model
        self.create_context_menu()

        # Track UI-specific task data
        self.task_ui_elements = {}  # Maps task_id to UI elements

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

        # Tags menu (new)
        self.tags_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label='Tags', menu=self.tags_menu)

        # Tags operations
        self.tags_menu.add_command(
            label='Filter Tasks by Tags...',
            command=self.controller.tag_ops.filter_tasks_by_tags,
        )
        self.tags_menu.add_command(
            label='Filter Resources by Tags...',
            command=self.controller.tag_ops.filter_resources_by_tags,
        )
        self.tags_menu.add_separator()
        self.tags_menu.add_command(
            label='Select Tasks by Tags...',
            command=self.controller.tag_ops.select_tasks_by_tag,
        )
        self.tags_menu.add_command(
            label='Toggle Multi-Select Mode',
            command=self.controller.toggle_multi_select_mode,
        )
        self.tags_menu.add_separator()
        self.tags_menu.add_command(
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
        self.task_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
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
        self.controller.task_canvas.bind(
            '<ButtonPress-3>', self.controller.task_ops.on_right_click
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

        # For Linux, which uses Button-4 and Button-5 for scroll wheel
        self.controller.task_canvas.bind('<Button-4>', self.controller.on_zoom)
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

        # Add Ctrl+E for export
        self.controller.root.bind(
            '<Control-e>', lambda e: self.controller.export_ops.open_export_dialog()
        )

    def create_resource_grid_frame(self):
        """Create the resource loading grid canvas with wider label column"""
        self.resource_frame = tk.Frame(self.controller.main_frame)
        self.resource_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

        # Create a fixed label column on the left with wider width
        self.controller.resource_label_frame = tk.Frame(
            self.resource_frame, width=self.controller.label_column_width
        )
        self.controller.resource_label_frame.pack(side=tk.LEFT, fill=tk.Y)
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

    def update_menu_commands(self):
        """Update the commands in the menus after initialization"""
        # Update the multi-task menu to use the correct methods
        # Note: The indexing has changed because we added the color menu
        # Multi-task menu structure:
        # 0: Set Tasks Color (cascade menu)
        # 1: Separator
        # 2: Add Tag to Selected Tasks...
        # 3: Remove Tag from Selected Tasks...
        self.multi_task_menu.entryconfig(
            2,  # Third item (Add Tag)
            command=lambda: self.add_tag_to_selected_tasks(),
        )
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

        # Calculate new heights ensuring minimum sizes
        new_task_height = max(100, task_height + delta_y)  # Minimum 100px

        # Update the task frame height directly
        self.task_frame.config(height=new_task_height)
        self.controller.task_grid_height = new_task_height

        # Update resource grid height based on available space
        available_height = (
            self.controller.main_frame.winfo_height()
            - new_task_height
            - self.controller.timeline_height
            - 15
        )
        new_resource_height = max(100, available_height)  # Minimum 100px
        self.controller.resource_grid_height = new_resource_height
        self.controller.resource_canvas.config(height=new_resource_height)
        self.controller.resource_label_canvas.config(height=new_resource_height)

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

    def add_tag_tooltip(self, canvas, item_id, tooltip_text):
        """Add a tooltip to a canvas item."""
        tooltip_window = None

        def enter(event):
            nonlocal tooltip_window
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

        def leave(event):
            nonlocal tooltip_window
            if tooltip_window:
                tooltip_window.destroy()
                tooltip_window = None

        # Bind tooltip events
        canvas.tag_bind(item_id, '<Enter>', enter)
        canvas.tag_bind(item_id, '<Leave>', leave)

    def add_task_tooltips(self, task):
        """Add tooltips for task tags and resource information."""
        task_id = task['task_id']
        if task_id in self.task_ui_elements:
            ui_elements = self.task_ui_elements[task_id]
            box_id = ui_elements['box']

            # Create tooltip text with tags
            tooltip_parts = []

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

        # Then redraw all dependencies
        for task in self.model.tasks:
            # Draw links to successors
            for successor_id in task['successors']:
                successor = self.model.get_task(successor_id)
                if (
                    successor
                    and task['task_id'] in self.task_ui_elements
                    and successor_id in self.task_ui_elements
                ):
                    # Get task coordinates
                    task_ui = self.task_ui_elements[task['task_id']]
                    successor_ui = self.task_ui_elements[successor_id]

                    # Check for same row and adjacency AND predecessor-successor relationship
                    if (
                        task_ui['y1'] == successor_ui['y1']
                        and task_ui['x2'] == successor_ui['x1']
                        and successor_id in task['successors']
                    ):
                        continue  # Skip drawing the line if adjacent in same row and predecessor-successor

                    x1 = task_ui['x2']
                    y1 = (task_ui['y1'] + task_ui['y2']) / 2
                    x2 = successor_ui['x1']
                    y2 = (successor_ui['y1'] + successor_ui['y2']) / 2
                    self.draw_arrow(x1, y1, x2, y2, task, successor)

    def draw_arrow(self, x1, y1, x2, y2, task, successor):
        """Draw an arrow between tasks, coloring based on dependency direction."""

        # Calculate the end date of the predecessor and start date of the successor
        predecessor_end_date = task['col'] + task['duration']
        successor_start_date = successor['col']

        # Determine the color based on the dependency direction
        color = 'darkblue'  # Default to blue (forward dependency)
        if predecessor_end_date > successor_start_date:
            color = 'darkred'  # Red for backward dependency

        # Calculate control points for a curved line
        cp_x = (x1 + x2) / 2

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
            tags=('dependency',),
        )
        return arrow_id

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

        # Ensure the resource label canvas has the right height
        self.controller.resource_label_canvas.config(
            height=self.controller.resource_grid_height
        )

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

            # Bind right-click event to show context menu
            tag_y = y + self.controller.task_height / 2
            resource_id = resource['id']

            # Draw resource name centered in wider column
            name_id = self.controller.resource_label_canvas.create_text(
                self.controller.label_column_width / 2,  # Center in wider column
                tag_y,
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
            if 'tags' in resource and resource['tags'] and self.show_tags_var.get():
                tag_text = ', '.join(resource['tags'])
                tag_id = self.controller.resource_label_canvas.create_text(
                    self.controller.label_column_width / 2,  # Center in wider column
                    tag_y
                    + self.controller.tag_font_size
                    + 3,  # Scale the spacing with font
                    text=f'[{tag_text}]',
                    anchor='center',
                    font=('Arial', self.controller.tag_font_size),
                    tags=(f'resource_tags_{resource_id}',),
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

        # Draw task box
        box_id = self.controller.task_canvas.create_rectangle(
            x1, y1, x2, y2, fill=task_color, outline='black', width=1, tags=('task',)
        )

        # Draw left and right edges (for resizing)
        left_edge_id = self.controller.task_canvas.create_line(
            x1, y1, x1, y2, fill='black', width=2, tags=('task', 'resize', 'left')
        )

        right_edge_id = self.controller.task_canvas.create_line(
            x2, y1, x2, y2, fill='black', width=2, tags=('task', 'resize', 'right')
        )

        # Determine vertical position for text elements based on whether we show tags
        # Scale the offset based on font size
        text_y_offset = (
            -self.controller.task_font_size / 2
            if (self.show_tags_var.get() and 'tags' in task and task['tags'])
            else 0
        )

        # Draw task text
        if task.get('url') and isinstance(task['url'], str) and task['url'].strip():
            # Make the description a clickable URL
            text_id = self.controller.task_canvas.create_text(
                (x1 + x2) / 2,
                (y1 + y2) / 2 + text_y_offset,
                text=f'{task_id} - {description}',
                fill='blue',
                font=('Arial', self.controller.task_font_size),  # Use dynamic font size
                tags=('task', 'url', f'task_{task_id}'),
            )
            # Bind click event to open the URL
            self.controller.task_canvas.tag_bind(
                text_id,
                '<Button-1>',
                lambda e, url=task['url']: self.open_url(url),
            )
        else:
            # Regular task ID and description
            text_id = self.controller.task_canvas.create_text(
                (x1 + x2) / 2,
                (y1 + y2) / 2 + text_y_offset,
                text=f'{task_id} - {description}',
                font=('Arial', self.controller.task_font_size),  # Use dynamic font size
                tags=('task', 'task_text', f'task_{task_id}'),
            )

        # Draw tags if present and enabled with dynamic font size and position
        tag_id = None
        if 'tags' in task and task['tags'] and self.show_tags_var.get():
            tag_text = ', '.join(task['tags'])
            tag_id = self.controller.task_canvas.create_text(
                (x1 + x2) / 2,
                (y1 + y2) / 2
                + self.controller.task_font_size,  # Scale offset with font size
                text=f'[{tag_text}]',
                font=('Arial', self.controller.tag_font_size),  # Use dynamic font size
                tags=('task', 'task_tags', f'task_tags_{task_id}'),
            )

        # Add grab connector circle - scale the size with zoom
        connector_radius = max(
            4, min(8, 5 * self.controller.zoom_level / 2)
        )  # Scale with zoom, with min/max limits
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

        # Add tag element to UI elements if it exists
        if tag_id:
            self.task_ui_elements[task_id]['tag_text'] = tag_id

        # Add highlight to UI elements if it exists
        if highlight_id:
            self.task_ui_elements[task_id]['highlight'] = highlight_id

        # Add tooltips for tags
        if 'tags' in task and task['tags']:
            self.add_task_tooltips(task)

    def update_task_ui(self, task):
        """Updates the UI elements for a specific task."""
        task_id = task['task_id']
        if task_id in self.task_ui_elements:
            ui_elements = self.task_ui_elements[task_id]
            x1, y1, x2, y2 = self.controller.get_task_ui_coordinates(task)

            # Get the task color (default to Cyan if not set)
            task_color = task.get('color', 'Cyan')

            # Update box coordinates and color
            self.controller.task_canvas.coords(ui_elements['box'], x1, y1, x2, y2)
            self.controller.task_canvas.itemconfig(ui_elements['box'], fill=task_color)

            self.controller.task_canvas.coords(ui_elements['left_edge'], x1, y1, x1, y2)
            self.controller.task_canvas.coords(
                ui_elements['right_edge'], x2, y1, x2, y2
            )
            self.controller.task_canvas.coords(
                ui_elements['text'], (x1 + x2) / 2, (y1 + y2) / 2
            )

            # Update stored coordinates
            (
                ui_elements['x1'],
                ui_elements['y1'],
                ui_elements['x2'],
                ui_elements['y2'],
            ) = (
                x1,
                y1,
                x2,
                y2,
            )
            ui_elements['connector_x'] = x2
            ui_elements['connector_y'] = (y1 + y2) / 2
            self.controller.task_canvas.coords(
                ui_elements['connector'],
                ui_elements['connector_x'] - 5,
                ui_elements['connector_y'] - 5,
                ui_elements['connector_x'] + 5,
                ui_elements['connector_y'] + 5,
            )

            # Update highlight if this task is selected
            if 'highlight' in ui_elements:
                self.controller.task_canvas.coords(
                    ui_elements['highlight'], x1 - 2, y1 - 2, x2 + 2, y2 + 2
                )

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

        # Update status bar with selection count if in multi-select mode
        if (
            self.controller.multi_select_mode
            and len(self.controller.selected_tasks) > 0
        ):
            self.controller.filter_status.config(
                text=f'Multi-select mode: {len(self.controller.selected_tasks)} tasks selected'
            )

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

        # Update status if in multi-select mode
        if self.controller.multi_select_mode:
            self.controller.filter_status.config(
                text='Multi-select mode: ON - Use Ctrl+click to select multiple tasks'
            )

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
