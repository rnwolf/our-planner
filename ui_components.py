import tkinter as tk
from tkinter import ttk
import webbrowser


class UIComponents:
    def __init__(self, controller, model):
        self.controller = controller
        self.model = model
        self.create_context_menu()

        # Track UI-specific task data
        self.task_ui_elements = {}  # Maps task_id to UI elements

    def create_menu_bar(self):
        """Create the menu bar with file operations"""
        self.menu_bar = tk.Menu(self.controller.root)
        self.controller.root.config(menu=self.menu_bar)

        # File menu
        self.file_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="File", menu=self.file_menu)

        # File operations
        self.file_menu.add_command(
            label="New", command=self.controller.file_ops.new_project
        )
        self.file_menu.add_command(
            label="Open...", command=self.controller.file_ops.open_file
        )
        self.file_menu.add_command(
            label="Save", command=self.controller.file_ops.save_file
        )
        self.file_menu.add_command(
            label="Save As...", command=self.controller.file_ops.save_file_as
        )
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Exit", command=self.controller.root.quit)

        # Edit menu
        self.edit_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="Edit", menu=self.edit_menu)

        # Edit operations
        self.edit_menu.add_command(
            label="Add Resource...",
            command=lambda: self.controller.task_ops.add_resource(
                parent=self.controller.root
            ),
        )
        self.edit_menu.add_command(
            label="Edit Resources...",
            command=lambda: self.controller.task_ops.edit_resources(
                parent=self.controller.root
            ),
        )
        self.edit_menu.add_separator()
        self.edit_menu.add_command(
            label="Project Settings...",
            command=lambda: self.controller.task_ops.edit_project_settings(
                parent=self.controller.root
            ),
        )

    def create_timeline_frame(self):
        """Create the timeline canvas with horizontal scrolling"""
        self.timeline_frame = tk.Frame(self.controller.main_frame)
        self.timeline_frame.pack(fill=tk.X, pady=(0, 5))

        # Create a fixed label column on the left
        self.timeline_label_frame = tk.Frame(self.timeline_frame, width=100)
        self.timeline_label_frame.pack(side=tk.LEFT, fill=tk.Y)
        self.timeline_label_canvas = tk.Canvas(
            self.timeline_label_frame,
            width=100,
            height=self.controller.timeline_height,
            bg="lightgray",
            highlightthickness=0,
        )
        self.timeline_label_canvas.pack(fill=tk.BOTH)
        self.timeline_label_canvas.create_text(
            50, self.controller.timeline_height / 2, text="Timeline", anchor="center"
        )

        # Create timeline canvas with horizontal scrollbar
        self.timeline_scroll_frame = tk.Frame(self.timeline_frame)
        self.timeline_scroll_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.controller.timeline_canvas = tk.Canvas(
            self.timeline_scroll_frame,
            height=self.controller.timeline_height,
            bg="white",
            highlightthickness=1,
            highlightbackground="gray",
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
        """Create the task grid canvas with both horizontal and vertical scrolling"""
        self.task_frame = tk.Frame(
            self.controller.main_frame, height=self.controller.task_grid_height
        )
        self.task_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
        self.task_frame.pack_propagate(False)  # Prevent frame from shrinking

        # Create a fixed label column on the left
        self.task_label_frame = tk.Frame(self.task_frame, width=100)
        self.task_label_frame.pack(side=tk.LEFT, fill=tk.Y)
        self.controller.task_label_canvas = tk.Canvas(
            self.task_label_frame, width=100, bg="lightgray", highlightthickness=0
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
            bg="white",
            highlightthickness=1,
            highlightbackground="gray",
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
            "<ButtonPress-1>", self.controller.task_ops.on_task_press
        )
        self.controller.task_canvas.bind(
            "<B1-Motion>", self.controller.task_ops.on_task_drag
        )
        self.controller.task_canvas.bind(
            "<ButtonRelease-1>", self.controller.task_ops.on_task_release
        )
        self.controller.task_canvas.bind(
            "<Motion>", self.controller.task_ops.on_task_hover
        )
        self.controller.task_canvas.bind(
            "<ButtonPress-3>", self.controller.task_ops.on_right_click
        )

        # Create a resizer between task and resource grids
        self.grid_resizer_frame = tk.Frame(
            self.controller.main_frame, height=5, bg="gray", cursor="sb_v_double_arrow"
        )
        self.grid_resizer_frame.pack(fill=tk.X, pady=1)

        # Bind events for resizing
        self.grid_resizer_frame.bind("<ButtonPress-1>", self.on_resizer_press)
        self.grid_resizer_frame.bind("<B1-Motion>", self.on_resizer_drag)
        self.grid_resizer_frame.bind("<ButtonRelease-1>", self.on_resizer_release)

    def create_resource_grid_frame(self):
        """Create the resource loading grid canvas"""
        self.resource_frame = tk.Frame(self.controller.main_frame)
        self.resource_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

        # Create a fixed label column on the left
        self.resource_label_frame = tk.Frame(self.resource_frame, width=100)
        self.resource_label_frame.pack(side=tk.LEFT, fill=tk.Y)
        self.controller.resource_label_canvas = tk.Canvas(
            self.resource_label_frame,
            width=100,
            height=self.controller.resource_grid_height,
            bg="lightgray",
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
            bg="white",
            highlightthickness=1,
            highlightbackground="gray",
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
            label="Edit Task Name",
            command=lambda: self.controller.task_ops.edit_task_name(
                parent=self.controller.root
            ),
        )
        self.context_menu.add_command(
            label="Edit Task URL", command=self.controller.task_ops.edit_task_url
        )
        self.context_menu.add_command(
            label="Edit Task Resources",
            command=lambda: self.controller.task_ops.edit_task_resources(
                self.controller.selected_task
            ),
        )
        self.context_menu.add_command(
            label="Add Predecessor",
            command=lambda: self.controller.task_ops.add_predecessor_dialog(
                self.controller.selected_task
            ),
        )
        self.context_menu.add_command(
            label="Add Successor",
            command=lambda: self.controller.task_ops.add_successor_dialog(
                self.controller.selected_task
            ),
        )
        self.context_menu.add_command(
            label="Delete Task", command=self.controller.task_ops.delete_task
        )
        self.context_menu.add_separator()
        self.context_menu.add_command(
            label="Edit Resources",
            command=lambda: self.controller.task_ops.edit_resources(
                parent=self.controller.root
            ),
        )
        self.context_menu.add_command(
            label="Edit Project Settings",
            command=lambda: self.controller.task_ops.edit_project_settings(
                parent=self.controller.root
            ),
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
        """Draw the timeline with day numbers"""
        self.controller.timeline_canvas.delete("all")

        # Calculate width
        canvas_width = self.controller.cell_width * self.model.days
        self.controller.timeline_canvas.config(
            scrollregion=(0, 0, canvas_width, self.controller.timeline_height)
        )

        # Draw the timeline grid
        for i in range(self.model.days + 1):
            x = i * self.controller.cell_width
            self.controller.timeline_canvas.create_line(
                x, 0, x, self.controller.timeline_height, fill="gray"
            )

            if i < self.model.days:
                self.controller.timeline_canvas.create_text(
                    x + self.controller.cell_width / 2,
                    self.controller.timeline_height / 2,
                    text=str(i + 1),
                )

    def draw_task_grid(self):
        """Draw the task grid"""
        self.controller.task_canvas.delete("all")
        self.controller.task_label_canvas.delete("all")

        # Clear task UI elements tracking
        self.task_ui_elements = {}

        # Calculate width and height
        canvas_width = self.controller.cell_width * self.model.days
        canvas_height = self.model.max_rows * self.controller.task_height
        self.controller.task_canvas.config(
            scrollregion=(0, 0, canvas_width, canvas_height)
        )
        self.controller.task_label_canvas.config(
            scrollregion=(0, 0, 100, canvas_height)
        )

        # Draw the grid lines
        for i in range(self.model.days + 1):
            x = i * self.controller.cell_width
            self.controller.task_canvas.create_line(x, 0, x, canvas_height, fill="gray")

        for i in range(self.model.max_rows + 1):
            y = i * self.controller.task_height
            self.controller.task_canvas.create_line(0, y, canvas_width, y, fill="gray")

            # Draw row labels in the label canvas
            if i < self.model.max_rows:
                self.controller.task_label_canvas.create_line(0, y, 100, y, fill="gray")
                self.controller.task_label_canvas.create_text(
                    50,
                    y + self.controller.task_height / 2,
                    text=f"Row {i+1}",
                    anchor="center",
                )

        # Draw the bottom line in the label canvas
        self.controller.task_label_canvas.create_line(
            0, canvas_height, 100, canvas_height, fill="gray"
        )

        # Draw the tasks
        for task in self.model.tasks:
            self.draw_task(task)

        # Draw dependencies
        self.draw_dependencies()

    def draw_dependencies(self):
        """Draw arrows for task dependencies"""
        # First delete all existing dependency arrows
        self.controller.task_canvas.delete("dependency")

        # Then redraw all dependencies
        for task in self.model.tasks:
            # Draw links to successors
            for successor_id in task["successors"]:
                successor = self.model.get_task(successor_id)
                if (
                    successor
                    and task["task_id"] in self.task_ui_elements
                    and successor_id in self.task_ui_elements
                ):
                    # Get task coordinates
                    task_ui = self.task_ui_elements[task["task_id"]]
                    successor_ui = self.task_ui_elements[successor_id]

                    # Check for same row and adjacency AND predecessor-successor relationship
                    if (
                        task_ui["y1"] == successor_ui["y1"]
                        and task_ui["x2"] == successor_ui["x1"]
                        and successor_id in task["successors"]
                    ):
                        continue  # Skip drawing the line if adjacent in same row and predecessor-successor

                    x1 = task_ui["x2"]
                    y1 = (task_ui["y1"] + task_ui["y2"]) / 2
                    x2 = successor_ui["x1"]
                    y2 = (successor_ui["y1"] + successor_ui["y2"]) / 2
                    self.draw_arrow(x1, y1, x2, y2, task, successor)

    def draw_arrow(self, x1, y1, x2, y2, task, successor):
        """Draw an arrow between tasks, coloring based on dependency direction."""

        # Calculate the end date of the predecessor and start date of the successor
        predecessor_end_date = task["col"] + task["duration"]
        successor_start_date = successor["col"]

        # Determine the color based on the dependency direction
        color = "darkblue"  # Default to blue (forward dependency)
        if predecessor_end_date > successor_start_date:
            color = "darkred"  # Red for backward dependency

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
            tags=("dependency",),
        )
        return arrow_id

    def draw_resource_grid(self):
        """Draw the resource loading grid"""
        self.controller.resource_canvas.delete("all")
        self.controller.resource_label_canvas.delete("all")

        # Calculate width and height
        canvas_width = self.controller.cell_width * self.model.days
        canvas_height = len(self.model.resources) * self.controller.task_height
        self.controller.resource_canvas.config(
            scrollregion=(0, 0, canvas_width, canvas_height)
        )
        self.controller.resource_label_canvas.config(
            scrollregion=(0, 0, 100, canvas_height)
        )

        # Ensure the resource label canvas has the right height
        self.controller.resource_label_canvas.config(
            height=self.controller.resource_grid_height
        )

        # Draw column lines
        for i in range(self.model.days + 1):
            x = i * self.controller.cell_width
            self.controller.resource_canvas.create_line(
                x, 0, x, canvas_height, fill="gray"
            )

        # Draw row lines and resource names
        for i, resource in enumerate(self.model.resources):
            y = i * self.controller.task_height

            # Draw lines in resource canvas
            self.controller.resource_canvas.create_line(
                0, y, canvas_width, y, fill="gray"
            )

            # Draw resource names in the label canvas
            self.controller.resource_label_canvas.create_line(0, y, 100, y, fill="gray")
            self.controller.resource_label_canvas.create_text(
                50,
                y + self.controller.task_height / 2,
                text=resource["name"],  # Use resource["name"] instead of resource
                anchor="center",
            )

        # Draw bottom line
        self.controller.resource_canvas.create_line(
            0, canvas_height, canvas_width, canvas_height, fill="gray"
        )
        self.controller.resource_label_canvas.create_line(
            0, canvas_height, 100, canvas_height, fill="gray"
        )

    def display_resource_loading(self, resource_loading):
        """Display resource loading based on data from the model"""
        # Clear previous loading display
        self.controller.resource_canvas.delete("loading")

        # Display resource loading
        for i, resource in enumerate(self.model.resources):
            resource_id = resource[
                "id"
            ]  # Get the resource ID which is the key in resource_loading

            for day in range(self.model.days):
                # Get resource capacity and loading
                capacity = resource["capacity"][day]
                load = resource_loading[resource_id][day]  # Use resource_id as the key

                # Calculate usage percentage
                usage_pct = (load / capacity) if capacity > 0 else float("inf")

                x = day * self.controller.cell_width
                y = i * self.controller.task_height

                # Choose color based on load vs capacity
                if usage_pct == 0:  # No usage
                    color = "white"
                elif usage_pct < 0.8:  # Normal usage (< 80%)
                    intensity = min(int(usage_pct * 200), 200)
                    color = f"#{255-intensity:02x}{255-intensity:02x}ff"  # Bluish color
                elif usage_pct < 1.0:  # High usage (80-99%)
                    color = "#ffffcc"  # Light yellow
                else:  # Overloaded (>= 100%)
                    color = "#ffcccc"  # Light red

                # Create cell
                self.controller.resource_canvas.create_rectangle(
                    x,
                    y,
                    x + self.controller.cell_width,
                    y + self.controller.task_height,
                    fill=color,
                    outline="gray",
                    tags="loading",
                )

                # Display load number if there is any loading
                if load > 0:
                    # Format load to show decimals only if needed
                    load_text = f"{load:.1f}" if load != int(load) else str(int(load))

                    # Show as fraction of capacity
                    display_text = f"{load_text}/{capacity}"

                    self.controller.resource_canvas.create_text(
                        x + self.controller.cell_width / 2,
                        y + self.controller.task_height / 2,
                        text=display_text,
                        tags="loading",
                        font=("Arial", 8),  # Smaller font to fit more text
                    )

    def open_url(self, url):
        """Open a URL in the default web browser"""
        webbrowser.open(url)

    def draw_task(self, task):
        """Draw a single task box with its information"""
        task_id = task["task_id"]
        row, col, duration = task["row"], task["col"], task["duration"]
        description = task.get("description", "No Description")

        # Calculate position
        x1, y1, x2, y2 = self.controller.get_task_ui_coordinates(task)

        # Draw task box
        box_id = self.controller.task_canvas.create_rectangle(
            x1, y1, x2, y2, fill="lightblue", outline="black", width=1, tags=("task",)
        )

        # Draw left and right edges (for resizing)
        left_edge_id = self.controller.task_canvas.create_line(
            x1, y1, x1, y2, fill="black", width=2, tags=("task", "resize", "left")
        )

        right_edge_id = self.controller.task_canvas.create_line(
            x2, y1, x2, y2, fill="black", width=2, tags=("task", "resize", "right")
        )

        # Draw task text
        if task.get("url") and isinstance(task["url"], str) and task["url"].strip():
            # Make the description a clickable URL
            text_id = self.controller.task_canvas.create_text(
                (x1 + x2) / 2,
                (y1 + y2) / 2,
                text=f"{task_id} - {description}",
                fill="blue",
                tags=("task", "url", f"task_{task_id}"),
            )
            # Bind click event to open the URL
            self.controller.task_canvas.tag_bind(
                text_id,
                "<Button-1>",
                lambda e, url=task["url"]: self.open_url(url),
            )
        else:
            # Regular task ID and description
            text_id = self.controller.task_canvas.create_text(
                (x1 + x2) / 2,
                (y1 + y2) / 2,
                text=f"{task_id} - {description}",
                tags=("task", "task_text", f"task_{task_id}"),
            )

        # Add grab connector circle
        connector_radius = 5
        connector_x = x2
        connector_y = (y1 + y2) / 2
        connector_id = self.controller.task_canvas.create_oval(
            connector_x - connector_radius,
            connector_y - connector_radius,
            connector_x + connector_radius,
            connector_y + connector_radius,
            fill="lightgray",
            outline="black",
            width=1,
            tags=("task", "connector", f"connector_{task_id}"),
        )

        # Update UI elements dictionary
        # self.task_ui_elements[task_id]["connector"] = connector_id
        # self.task_ui_elements[task_id]["connector_x"] = connector_x
        # self.task_ui_elements[task_id]["connector_y"] = connector_y

        # Store UI elements for this task
        self.task_ui_elements[task_id] = {
            "box": box_id,
            "left_edge": left_edge_id,
            "right_edge": right_edge_id,
            "text": text_id,
            "x1": x1,
            "y1": y1,
            "x2": x2,
            "y2": y2,
            "connector": connector_id,
            "connector_x": connector_x,
            "connector_y": connector_y,
        }

    def update_task_ui(self, task):
        """Updates the UI elements for a specific task."""
        task_id = task["task_id"]
        if task_id in self.task_ui_elements:
            ui_elements = self.task_ui_elements[task_id]
            x1, y1, x2, y2 = self.controller.get_task_ui_coordinates(task)
            self.controller.task_canvas.coords(ui_elements["box"], x1, y1, x2, y2)
            self.controller.task_canvas.coords(ui_elements["left_edge"], x1, y1, x1, y2)
            self.controller.task_canvas.coords(
                ui_elements["right_edge"], x2, y1, x2, y2
            )
            self.controller.task_canvas.coords(
                ui_elements["text"], (x1 + x2) / 2, (y1 + y2) / 2
            )
            (
                ui_elements["x1"],
                ui_elements["y1"],
                ui_elements["x2"],
                ui_elements["y2"],
            ) = (
                x1,
                y1,
                x2,
                y2,
            )
            ui_elements["connector_x"] = x2
            ui_elements["connector_y"] = (y1 + y2) / 2
            self.controller.task_canvas.coords(
                ui_elements["connector"],
                ui_elements["connector_x"] - 5,
                ui_elements["connector_y"] - 5,
                ui_elements["connector_x"] + 5,
                ui_elements["connector_y"] + 5,
            )
