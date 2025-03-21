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
        self.resources = ["Resource A", "Resource B", "Resource C"]
        self.cell_width = 45
        self.task_height = 30
        self.timeline_height = 30
        self.resource_grid_height = 150
        self.task_grid_height = 300  # Default height for task grid

        # Dragging state for resizing panes
        self.resizing_pane = False
        self.resize_y = 0

        # Data structures
        self.tasks = []
        self.selected_task = None
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.resize_edge = None
        self.new_task_in_progress = False
        self.new_task_start = None

        # Current file path for save/load operations
        self.current_file_path = None

        # Initialize the UI components handler
        self.ui = UIComponents(self)

        # Initialize file operations handler
        self.file_ops = FileOperations(self)

        # Initialize task operations handler
        self.task_ops = TaskOperations(self)

        # Create menu bar
        self.ui.create_menu_bar()

        # Create main container frame
        self.main_frame = tk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Create frames for our three main areas with scrollbars
        self.ui.create_timeline_frame()
        self.ui.create_task_grid_frame()
        self.ui.create_resource_grid_frame()

        # Create context menu for tasks
        self.ui.create_context_menu()

        # Create sample tasks
        self.create_sample_tasks()

        # Render initial state
        self.ui.draw_timeline()
        self.ui.draw_task_grid()
        self.ui.draw_resource_grid()
        self.task_ops.calculate_resource_loading()

    def create_sample_tasks(self):
        """Create sample tasks across the timeline to demonstrate scrolling"""
        sample_tasks = [
            {
                "row": 0,
                "col": 1,
                "duration": 3,
                "description": "Task 1",
                "resources": ["Resource A"],
            },
            {
                "row": 1,
                "col": 5,
                "duration": 4,
                "description": "Task 2",
                "resources": ["Resource B", "Resource C"],
            },
            {
                "row": 2,
                "col": 2,
                "duration": 5,
                "description": "Task 3",
                "resources": ["Resource A", "Resource B"],
            },
            {
                "row": 3,
                "col": 8,
                "duration": 2,
                "description": "Task 4",
                "resources": ["Resource C"],
            },
            {
                "row": 4,
                "col": 12,
                "duration": 6,
                "description": "Task 5",
                "resources": ["Resource A", "Resource B", "Resource C"],
            },
            # Add tasks further out in the timeline to demonstrate scrolling
            {
                "row": 6,
                "col": 25,
                "duration": 4,
                "description": "Task 6",
                "resources": ["Resource A"],
            },
            {
                "row": 8,
                "col": 40,
                "duration": 8,
                "description": "Task 7",
                "resources": ["Resource B"],
            },
            {
                "row": 10,
                "col": 70,
                "duration": 10,
                "description": "Task 8",
                "resources": ["Resource C"],
            },
            {
                "row": 15,
                "col": 90,
                "duration": 5,
                "description": "Task 9",
                "resources": ["Resource A", "Resource B"],
            },
            # Add tasks in different rows to demonstrate vertical scrolling
            {
                "row": 20,
                "col": 15,
                "duration": 7,
                "description": "Task 10",
                "resources": ["Resource A"],
            },
            {
                "row": 25,
                "col": 30,
                "duration": 6,
                "description": "Task 11",
                "resources": ["Resource B"],
            },
            {
                "row": 30,
                "col": 50,
                "duration": 8,
                "description": "Task 12",
                "resources": ["Resource C"],
            },
            {
                "row": 40,
                "col": 60,
                "duration": 9,
                "description": "Task 13",
                "resources": ["Resource A", "Resource C"],
            },
            {
                "row": 45,
                "col": 80,
                "duration": 4,
                "description": "Task 14",
                "resources": ["Resource B"],
            },
        ]

        for task_data in sample_tasks:
            self.tasks.append(task_data)
