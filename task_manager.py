import tkinter as tk
from tkinter import ttk, simpledialog, messagebox, filedialog
import json
import os

from ui_components import UIComponents
from file_operations import FileOperations
from task_operations import TaskOperations


class TaskResourceManager:
    def __init__(self, root):
        self.root = root
        self.root.title("Task Resource Manager")
        self.root.geometry("1000x600")

        # Configuration
        self.days = 100
        self.max_tasks = 50
        self.resources = [
            "Resource A",
            "Resource B",
            "Resource C",
            "Resource D",
            "Resource E",
            "Resource F",
            "Resource G",
            "Resource H",
            "Resource I",
            "Resource J",
        ]
        self.cell_width = 45
        self.task_height = 30
        self.timeline_height = 30
        self.resource_grid_height = 150
        self.task_grid_height = 300  # Default height for task grid
        self.task_id_counter = 0  # Initialize the task ID counter

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

        # Data structures
        self.tasks = []
        self.selected_task = None

        # Current file path for save/load operations
        self.current_file_path = None

        # Initialize handlers
        self.task_ops = TaskOperations(self)
        self.ui = UIComponents(self)
        self.file_ops = FileOperations(self)

        # Create main container frame
        self.main_frame = tk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Create UI elements
        self.ui.create_menu_bar()
        self.ui.create_timeline_frame()
        self.ui.create_task_grid_frame()
        self.ui.create_resource_grid_frame()

        # Create context menu for tasks
        # self.ui.create_context_menu()

        # Create sample tasks
        self.create_sample_tasks()

        # Render initial state
        self.ui.draw_timeline()
        self.ui.draw_task_grid()
        self.ui.draw_resource_grid()
        self.task_ops.calculate_resource_loading()

    def get_next_task_id(self):
        """Generate a unique task ID."""
        self.task_id_counter += 1
        return self.task_id_counter

    def create_sample_tasks(self):
        """Create some sample tasks."""
        task1 = {
            "task_id": self.get_next_task_id(),  # Assign a unique ID
            "description": "Task A",
            "url": "https://www.google.com",
            "row": 1,
            "col": 5,
            "duration": 5,
            "resources": ["Resource A", "Resource B"],
            "predecessors": [],  # Initialize predecessors list
            "successors": [],  # Initialize successors list
        }
        task2 = {
            "task_id": self.get_next_task_id(),
            "description": "Task B",
            "url": "https://www.google.com",
            "row": 2,
            "col": 12,
            "duration": 4,
            "resources": ["Resource A", "Resource B", "Resource C"],
            "predecessors": [],
            "successors": [],
        }
        task3 = {
            "task_id": self.get_next_task_id(),
            "description": "Task C",
            "url": "https://www.google.com",
            "row": 3,
            "col": 2,
            "duration": 3,
            "resources": ["Resource A"],
            "predecessors": [],
            "successors": [],
        }
        task4 = {
            "task_id": self.get_next_task_id(),
            "description": "Task D",
            "row": 4,
            "col": 1,
            "duration": 2,
            "resources": ["Resource A", "Resource D"],
            "predecessors": [],
            "successors": [],
        }
        self.tasks.extend([task1, task2, task3, task4])
