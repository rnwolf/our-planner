import tkinter as tk
from model import TaskResourceModel
from ui_components import UIComponents
from file_operations import FileOperations
from task_operations import TaskOperations


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
        self.timeline_height = 30
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

        # Create main container frame
        self.main_frame = tk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Initialize canvas references (will be populated by UI component)
        self.timeline_canvas = None
        self.task_canvas = None
        self.resource_canvas = None
        self.task_label_canvas = None
        self.resource_label_canvas = None
        self.h_scrollbar = None
        self.v_scrollbar = None

        # Initialize handlers
        self.task_ops = TaskOperations(self, self.model)
        self.ui = UIComponents(self, self.model)
        self.file_ops = FileOperations(self, self.model)

        # Create UI elements
        self.ui.create_menu_bar()
        self.ui.create_timeline_frame()
        self.ui.create_task_grid_frame()
        self.ui.create_resource_grid_frame()

        # Create sample tasks in the model
        self.model.create_sample_tasks()

        # Render initial state
        self.update_view()

    def update_view(self):
        """Update all view components to reflect current model state."""
        self.ui.draw_timeline()
        self.ui.draw_task_grid()
        self.ui.draw_resource_grid()
        self.update_resource_loading()

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
