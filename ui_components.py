import tkinter as tk
from tkinter import ttk, simpledialog, messagebox


class UIComponents:
    def __init__(self, manager):
        self.manager = manager

    def create_menu_bar(self):
        """Create the menu bar with file operations"""
        self.manager.menu_bar = tk.Menu(self.manager.root)
        self.manager.root.config(menu=self.manager.menu_bar)

        # File menu
        self.file_menu = tk.Menu(self.manager.menu_bar, tearoff=0)
        self.manager.menu_bar.add_cascade(label="File", menu=self.file_menu)

        # File operations
        self.file_menu.add_command(
            label="New", command=self.manager.file_ops.new_project
        )
        self.file_menu.add_command(
            label="Open...", command=self.manager.file_ops.open_file
        )
        self.file_menu.add_command(
            label="Save", command=self.manager.file_ops.save_file
        )
        self.file_menu.add_command(
            label="Save As...", command=self.manager.file_ops.save_file_as
        )
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Exit", command=self.manager.root.quit)

        # Edit menu
        self.edit_menu = tk.Menu(self.manager.menu_bar, tearoff=0)
        self.manager.menu_bar.add_cascade(label="Edit", menu=self.edit_menu)

        # Edit operations
        self.edit_menu.add_command(
            label="Add Resource...", command=self.manager.task_ops.add_resource
        )
        self.edit_menu.add_command(
            label="Edit Resources...", command=self.manager.task_ops.edit_resources
        )
        self.edit_menu.add_separator()
        self.edit_menu.add_command(
            label="Project Settings...",
            command=self.manager.task_ops.edit_project_settings,
        )

    def create_timeline_frame(self):
        """Create the timeline canvas with horizontal scrolling (Canvas 1)"""
        self.manager.timeline_frame = tk.Frame(self.manager.main_frame)
        self.manager.timeline_frame.pack(fill=tk.X, pady=(0, 5))

        # Create a fixed label column on the left
        self.manager.timeline_label_frame = tk.Frame(
            self.manager.timeline_frame, width=100
        )
        self.manager.timeline_label_frame.pack(side=tk.LEFT, fill=tk.Y)
        self.manager.timeline_label_canvas = tk.Canvas(
            self.manager.timeline_label_frame,
            width=100,
            height=self.manager.timeline_height,
            bg="lightgray",
            highlightthickness=0,
        )
        self.manager.timeline_label_canvas.pack(fill=tk.BOTH)
        self.manager.timeline_label_canvas.create_text(
            50, self.manager.timeline_height / 2, text="Timeline", anchor="center"
        )

        # Create timeline canvas with horizontal scrollbar
        self.manager.timeline_scroll_frame = tk.Frame(self.manager.timeline_frame)
        self.manager.timeline_scroll_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.manager.timeline_canvas = tk.Canvas(
            self.manager.timeline_scroll_frame,
            height=self.manager.timeline_height,
            bg="white",
            highlightthickness=1,
            highlightbackground="gray",
        )
        self.manager.timeline_canvas.pack(side=tk.TOP, fill=tk.X)

        # Horizontal scrollbar for timeline - will be shared with task and resource canvases
        self.manager.h_scrollbar = ttk.Scrollbar(
            self.manager.main_frame,
            orient=tk.HORIZONTAL,
            command=self.sync_horizontal_scroll,
        )
        self.manager.h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)

        # Configure timeline canvas for scrolling
        self.manager.timeline_canvas.config(
            xscrollcommand=self.manager.h_scrollbar.set,
            scrollregion=(
                0,
                0,
                self.manager.cell_width * self.manager.days,
                self.manager.timeline_height,
            ),
        )

    def create_task_grid_frame(self):
        """Create the task grid canvas with both horizontal and vertical scrolling (Canvas 2)"""
        self.manager.task_frame = tk.Frame(
            self.manager.main_frame, height=self.manager.task_grid_height
        )
        self.manager.task_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
        self.manager.task_frame.pack_propagate(
            False
        )  # Prevent frame from shrinking to content size

        # Create a fixed label column on the left
        self.manager.task_label_frame = tk.Frame(self.manager.task_frame, width=100)
        self.manager.task_label_frame.pack(side=tk.LEFT, fill=tk.Y)
        self.manager.task_label_canvas = tk.Canvas(
            self.manager.task_label_frame,
            width=100,
            bg="lightgray",
            highlightthickness=0,
        )
        self.manager.task_label_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Create task canvas with vertical scrollbar
        self.manager.task_scroll_frame = tk.Frame(self.manager.task_frame)
        self.manager.task_scroll_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.manager.v_scrollbar = ttk.Scrollbar(
            self.manager.task_scroll_frame, orient=tk.VERTICAL
        )
        self.manager.v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.manager.task_canvas = tk.Canvas(
            self.manager.task_scroll_frame,
            bg="white",
            highlightthickness=1,
            highlightbackground="gray",
            yscrollcommand=self.manager.v_scrollbar.set,
        )
        self.manager.task_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Connect scrollbar to canvas
        self.manager.v_scrollbar.config(command=self.sync_vertical_scroll)

        # Configure task canvas for scrolling
        self.manager.task_canvas.config(
            xscrollcommand=self.manager.h_scrollbar.set,
            scrollregion=(
                0,
                0,
                self.manager.cell_width * self.manager.days,
                self.manager.max_tasks * self.manager.task_height,
            ),
        )

        # Bind mouse events for task manipulation
        self.manager.task_canvas.bind(
            "<ButtonPress-1>", self.manager.task_ops.on_task_press
        )
        self.manager.task_canvas.bind("<B1-Motion>", self.manager.task_ops.on_task_drag)
        self.manager.task_canvas.bind(
            "<ButtonRelease-1>", self.manager.task_ops.on_task_release
        )
        self.manager.task_canvas.bind("<Motion>", self.manager.task_ops.on_task_hover)
        self.manager.task_canvas.bind(
            "<ButtonPress-3>", self.manager.task_ops.on_right_click
        )

        # Create a rubberband rectangle for new task creation
        self.manager.rubberband = None

        # Create a resizer between task and resource grids
        self.manager.grid_resizer_frame = tk.Frame(
            self.manager.main_frame, height=5, bg="gray", cursor="sb_v_double_arrow"
        )
        self.manager.grid_resizer_frame.pack(fill=tk.X, pady=1)

        # Bind events for resizing
        self.manager.grid_resizer_frame.bind("<ButtonPress-1>", self.on_resizer_press)
        self.manager.grid_resizer_frame.bind("<B1-Motion>", self.on_resizer_drag)
        self.manager.grid_resizer_frame.bind(
            "<ButtonRelease-1>", self.on_resizer_release
        )

    def create_resource_grid_frame(self):
        """Create the resource loading grid canvas with both horizontal and vertical scrolling (Canvas 3)"""
        self.manager.resource_frame = tk.Frame(self.manager.main_frame)
        self.manager.resource_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

        # Create a fixed label column on the left
        self.manager.resource_label_frame = tk.Frame(
            self.manager.resource_frame, width=100
        )
        self.manager.resource_label_frame.pack(side=tk.LEFT, fill=tk.Y)
        self.manager.resource_label_canvas = tk.Canvas(
            self.manager.resource_label_frame,
            width=100,
            height=self.manager.resource_grid_height,
            bg="lightgray",
            highlightthickness=0,
        )
        self.manager.resource_label_canvas.pack(fill=tk.BOTH)

        # Create resource canvas with vertical scrollbar
        self.manager.resource_scroll_frame = tk.Frame(self.manager.resource_frame)
        self.manager.resource_scroll_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.manager.resource_vscrollbar = ttk.Scrollbar(
            self.manager.resource_scroll_frame, orient=tk.VERTICAL
        )
        self.manager.resource_vscrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.manager.resource_canvas = tk.Canvas(
            self.manager.resource_scroll_frame,
            height=self.manager.resource_grid_height,
            bg="white",
            highlightthickness=1,
            highlightbackground="gray",
            yscrollcommand=self.manager.resource_vscrollbar.set,
        )
        self.manager.resource_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Configure both resource canvases to have the same height
        self.manager.resource_canvas.config(height=self.manager.resource_grid_height)
        self.manager.resource_label_canvas.config(
            height=self.manager.resource_grid_height
        )

        # Connect scrollbar to canvas and sync labels with canvas
        self.manager.resource_vscrollbar.config(
            command=self.sync_resource_vertical_scroll
        )

        # Configure resource canvas for scrolling
        self.manager.resource_canvas.config(
            xscrollcommand=self.manager.h_scrollbar.set,
            scrollregion=(
                0,
                0,
                self.manager.cell_width * self.manager.days,
                len(self.manager.resources) * self.manager.task_height,
            ),
        )

    def create_context_menu(self):
        """Create right-click context menu for tasks"""
        self.manager.context_menu = tk.Menu(self.manager.root, tearoff=0)
        self.manager.context_menu.add_command(
            label="Edit Task Name", command=self.manager.task_ops.edit_task_name
        )
        self.manager.context_menu.add_command(
            label="Edit Task Url", command=self.manager.task_ops.edit_task_url
        )
        self.manager.context_menu.add_command(
            label="Edit Task Resources",
            command=self.manager.task_ops.edit_task_resources,
        )
        self.manager.context_menu.add_separator()
        self.manager.context_menu.add_command(
            label="Delete Task", command=self.manager.task_ops.delete_task
        )

    def sync_horizontal_scroll(self, *args):
        """Synchronize horizontal scrolling across all three canvases"""
        self.manager.timeline_canvas.xview(*args)
        self.manager.task_canvas.xview(*args)
        self.manager.resource_canvas.xview(*args)

    def sync_vertical_scroll(self, *args):
        """Synchronize vertical scrolling between task canvas and task labels"""
        self.manager.task_canvas.yview(*args)
        self.manager.task_label_canvas.yview(*args)

    def sync_resource_vertical_scroll(self, *args):
        """Synchronize vertical scrolling between resource canvas and resource labels"""
        self.manager.resource_canvas.yview(*args)
        self.manager.resource_label_canvas.yview(*args)

    def on_resizer_press(self, event):
        """Handle mouse press on the resizer bar"""
        self.manager.resizing_pane = True
        self.manager.resize_y = event.y_root

    def on_resizer_drag(self, event):
        """Handle dragging of the resizer bar"""
        if not self.manager.resizing_pane:
            return

        # Calculate change in height
        delta_y = event.y_root - self.manager.resize_y

        # Skip small movements to improve performance
        if abs(delta_y) < 2:
            return

        # Get current dimensions
        task_height = self.manager.task_frame.winfo_height()

        # Calculate new heights ensuring minimum sizes
        new_task_height = max(100, task_height + delta_y)  # Minimum 100px

        # Update the task frame height directly
        self.manager.task_frame.config(height=new_task_height)
        self.manager.task_grid_height = new_task_height

        # Update resource grid height based on available space
        available_height = (
            self.manager.main_frame.winfo_height()
            - new_task_height
            - self.manager.timeline_height
            - 15
        )
        new_resource_height = max(100, available_height)  # Minimum 100px
        self.manager.resource_grid_height = new_resource_height
        self.manager.resource_canvas.config(height=new_resource_height)
        self.manager.resource_label_canvas.config(height=new_resource_height)

        # Force layout update
        self.manager.root.update_idletasks()

        # Update the reference point
        self.manager.resize_y = event.y_root

    def on_resizer_release(self, event):
        """Handle release of the resizer bar"""
        self.manager.resizing_pane = False

        # Immediately recalculate resource loading
        self.manager.task_ops.calculate_resource_loading()

    def draw_timeline(self):
        """Draw the timeline with day numbers"""
        self.manager.timeline_canvas.delete("all")

        # Calculate width
        canvas_width = self.manager.cell_width * self.manager.days
        self.manager.timeline_canvas.config(
            scrollregion=(0, 0, canvas_width, self.manager.timeline_height)
        )

        # Draw the timeline grid
        for i in range(self.manager.days + 1):
            x = i * self.manager.cell_width
            self.manager.timeline_canvas.create_line(
                x, 0, x, self.manager.timeline_height, fill="gray"
            )

            if i < self.manager.days:
                self.manager.timeline_canvas.create_text(
                    x + self.manager.cell_width / 2,
                    self.manager.timeline_height / 2,
                    text=str(i + 1),
                )

    def draw_task_grid(self):
        """Draw the task grid"""
        self.manager.task_canvas.delete("all")
        self.manager.task_label_canvas.delete("all")

        # Calculate width and height
        canvas_width = self.manager.cell_width * self.manager.days
        canvas_height = self.manager.max_tasks * self.manager.task_height
        self.manager.task_canvas.config(
            scrollregion=(0, 0, canvas_width, canvas_height)
        )
        self.manager.task_label_canvas.config(scrollregion=(0, 0, 100, canvas_height))

        # Draw the grid lines
        for i in range(self.manager.days + 1):
            x = i * self.manager.cell_width
            self.manager.task_canvas.create_line(x, 0, x, canvas_height, fill="gray")

        for i in range(self.manager.max_tasks + 1):
            y = i * self.manager.task_height
            self.manager.task_canvas.create_line(0, y, canvas_width, y, fill="gray")

            # Draw row labels in the label canvas
            if i < self.manager.max_tasks:
                self.manager.task_label_canvas.create_line(0, y, 100, y, fill="gray")
                self.manager.task_label_canvas.create_text(
                    50,
                    y + self.manager.task_height / 2,
                    text=f"Row {i+1}",
                    anchor="center",
                )

        # Draw the bottom line in the label canvas
        self.manager.task_label_canvas.create_line(
            0, canvas_height, 100, canvas_height, fill="gray"
        )

        # Draw the tasks
        for task in self.manager.tasks:
            if "description" not in task:
                task["description"] = "No Description"  # Default description
            self.draw_task(task)

    def draw_resource_grid(self):
        """Draw the resource loading grid"""
        self.manager.resource_canvas.delete("all")
        self.manager.resource_label_canvas.delete("all")

        # Calculate width and height
        canvas_width = self.manager.cell_width * self.manager.days
        canvas_height = len(self.manager.resources) * self.manager.task_height
        self.manager.resource_canvas.config(
            scrollregion=(0, 0, canvas_width, canvas_height)
        )
        self.manager.resource_label_canvas.config(
            scrollregion=(0, 0, 100, canvas_height)
        )

        # Ensure the resource label canvas has the right height
        self.manager.resource_label_canvas.config(
            height=self.manager.resource_grid_height
        )

        # Draw column lines
        for i in range(self.manager.days + 1):
            x = i * self.manager.cell_width
            self.manager.resource_canvas.create_line(
                x, 0, x, canvas_height, fill="gray"
            )

        # Draw row lines and resource names
        for i, resource in enumerate(self.manager.resources):
            y = i * self.manager.task_height

            # Draw lines in resource canvas
            self.manager.resource_canvas.create_line(0, y, canvas_width, y, fill="gray")

            # Draw resource names in the label canvas
            self.manager.resource_label_canvas.create_line(0, y, 100, y, fill="gray")
            self.manager.resource_label_canvas.create_text(
                50, y + self.manager.task_height / 2, text=resource, anchor="center"
            )

        # Draw bottom line
        self.manager.resource_canvas.create_line(
            0, canvas_height, canvas_width, canvas_height, fill="gray"
        )
        self.manager.resource_label_canvas.create_line(
            0, canvas_height, 100, canvas_height, fill="gray"
        )

    def open_url(self, url):
        """Open a URL in the default web browser"""
        import webbrowser

        webbrowser.open(url)

    def draw_task(self, task):
        """Draw a single task box with its information"""
        row, col, duration = task["row"], task["col"], task["duration"]

        # Calculate position
        x1 = col * self.manager.cell_width
        y1 = row * self.manager.task_height
        x2 = x1 + duration * self.manager.cell_width
        y2 = y1 + self.manager.task_height

        # Store coordinates in task
        task["x1"], task["y1"], task["x2"], task["y2"] = x1, y1, x2, y2

        # Draw task box
        task["box"] = self.manager.task_canvas.create_rectangle(
            x1, y1, x2, y2, fill="lightblue", outline="black", width=1, tags=("task",)
        )

        # Draw left and right edges (for resizing)
        task["left_edge"] = self.manager.task_canvas.create_line(
            x1, y1, x1, y2, fill="black", width=2, tags=("task", "resize", "left")
        )

        task["right_edge"] = self.manager.task_canvas.create_line(
            x2, y1, x2, y2, fill="black", width=2, tags=("task", "resize", "right")
        )

        # Draw task description
        if task.get("url") and isinstance(task["url"], str) and task["url"].strip():
            # Make the description a clickable URL
            task["text"] = self.manager.task_canvas.create_text(
                (x1 + x2) / 2,
                (y1 + y2) / 2,
                text=task["description"],
                fill="blue",
                tags=("task", "url"),
            )
            # Bind click event to open the URL
            self.manager.task_canvas.tag_bind(
                task["text"],
                "<Button-1>",
                lambda e, url=task["url"]: self.open_url(url),
            )
        else:
            # Regular description
            task["text"] = self.manager.task_canvas.create_text(
                (x1 + x2) / 2, (y1 + y2) / 2, text=task["description"], tags=("task",)
            )
