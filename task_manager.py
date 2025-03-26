import tkinter as tk
from model import TaskResourceModel
from ui_components import UIComponents
from file_operations import FileOperations
from task_operations import TaskOperations
from tag_operations import TagOperations


class TaskResourceManager:
    """Controller class that connects the model and view components."""

    def __init__(self, root):
        self.root = root
        self.root.title("Task Resource Manager")
        self.root.geometry("1000x600")

        # Initialize the model
        self.model = TaskResourceModel()

        # UI configuration constants
        self.cell_width = 45
        self.task_height = 30
        self.timeline_height = 60
        self.resource_grid_height = 150
        self.task_grid_height = 300

        # Dragging state for resizing panes
        self.dragging_task = None
        self.resizing_pane = False
        self.resize_y = 0
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.resize_edge = None
        self.new_task_in_progress = False
        self.new_task_start = None
        self.rubberband = None
        self.selected_task = None
        self.selected_tasks = []
        self.dragging_connector = False
        self.connector_line = None

        # Task selection mode
        self.multi_select_mode = False

        # Create main container frame
        self.main_frame = tk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Initialize canvas references (will be populated by UI component)
        self.timeline_canvas = None
        self.task_canvas = None
        self.timeline_canvas = None
        self.resource_canvas = None
        self.task_label_canvas = None
        self.resource_label_canvas = None
        self.h_scrollbar = None
        self.v_scrollbar = None

        # Initialize handlers
        self.task_ops = TaskOperations(self, self.model)
        self.tag_ops = TagOperations(self, self.model)
        self.ui = UIComponents(self, self.model)
        self.file_ops = FileOperations(self, self.model)

        # Create UI elements
        self.ui.create_menu_bar()
        self.ui.create_timeline_frame()
        self.ui.create_task_grid_frame()
        self.ui.create_resource_grid_frame()

        # Add status bar for showing filter information
        self.create_status_bar()

        # Create sample tasks in the model
        self.model.create_sample_tasks()

        # After UI creation but before update_view
        self.ui.update_menu_commands()

        # Render initial state
        self.update_view()

    def create_status_bar(self):
        """Create a status bar at the bottom of the window."""
        self.status_bar = tk.Frame(self.root, height=25, relief=tk.SUNKEN, bd=1)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # Status message for filters
        self.filter_status = tk.Label(
            self.status_bar, text="No filters active", anchor=tk.W, padx=5
        )
        self.filter_status.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Clear filters button
        self.clear_filters_btn = tk.Button(
            self.status_bar,
            text="Clear All Filters",
            command=self.clear_all_filters,
            state=tk.DISABLED,
        )
        self.clear_filters_btn.pack(side=tk.RIGHT, padx=5, pady=2)

    def clear_all_filters(self):
        """Clear all active filters."""
        self.tag_ops.clear_task_filters()
        self.tag_ops.clear_resource_filters()
        self.update_filter_status()

    def update_filter_status(self):
        """Update the filter status display in the status bar."""
        task_filters = self.tag_ops.task_tag_filters
        resource_filters = self.tag_ops.resource_tag_filters

        if not task_filters and not resource_filters:
            self.filter_status.config(text="No filters active")
            self.clear_filters_btn.config(state=tk.DISABLED)
        else:
            status_text = []
            if task_filters:
                match_type = "ALL" if self.tag_ops.task_match_all else "ANY"
                status_text.append(
                    f"Tasks: {match_type} of [{', '.join(task_filters)}]"
                )

            if resource_filters:
                match_type = "ALL" if self.tag_ops.resource_match_all else "ANY"
                status_text.append(
                    f"Resources: {match_type} of [{', '.join(resource_filters)}]"
                )

            self.filter_status.config(text=" | ".join(status_text))
            self.clear_filters_btn.config(state=tk.NORMAL)

    def update_view(self):
        """Update all view components to reflect current model state."""
        self.ui.draw_timeline()
        self.ui.draw_task_grid()
        self.ui.draw_resource_grid()
        self.update_resource_loading()
        self.update_filter_status()

    def update_resource_loading(self):
        """Calculate resource loading and update display."""
        # Get loading data from model
        resource_loading = self.model.calculate_resource_loading()
        # Pass to UI to display
        self.ui.display_resource_loading(resource_loading)

    def update_window_title(self, file_path=None):
        """Update the window title based on current file path."""
        import os

        if file_path:
            self.root.title(f"Task Resource Manager - {os.path.basename(file_path)}")
        else:
            self.root.title("Task Resource Manager - New Project")

    def get_task_ui_coordinates(self, task):
        """Convert task data model coordinates to UI coordinates."""
        x1 = task["col"] * self.cell_width
        y1 = task["row"] * self.task_height
        x2 = x1 + task["duration"] * self.cell_width
        y2 = y1 + self.task_height
        return x1, y1, x2, y2

    def convert_ui_to_model_coordinates(self, x, y):
        """Convert UI coordinates to model coordinates (row, col)."""
        col = int(x / self.cell_width)
        row = int(y / self.task_height)
        return row, col

    def toggle_multi_select_mode(self):
        """Toggle multiple task selection mode."""
        self.multi_select_mode = not self.multi_select_mode

        # Update cursor to indicate mode
        if self.multi_select_mode:
            self.task_canvas.config(cursor="crosshair")
        else:
            self.task_canvas.config(cursor="")

        # Clear selected tasks when disabling multi-select
        if not self.multi_select_mode:
            self.selected_tasks = []
            self.ui.remove_task_selections()
