import tkinter as tk
from tkinter import ttk


class DraggableRectangleApp:
    def __init__(self, master):
        self.master = master
        master.title("Task Scheduler with Resource Loading")

        # Grid parameters
        self.grid_rows = 30
        self.grid_cols = 20
        self.cell_width = 20  # Initial cell width
        self.cell_height = 15  # Initial cell height

        # Resources
        self.resources = ["Resource A", "Resource B", "Resource C", "Resource D"]
        self.resource_rows = len(self.resources)

        # Create the main frame
        self.main_frame = ttk.Frame(master)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # Create the canvas frame
        self.canvas_frame = ttk.Frame(self.main_frame)
        self.canvas_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Create the canvas
        self.canvas = tk.Canvas(self.canvas_frame, bg="white")
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Create the resource frame
        self.resource_frame = ttk.Frame(self.main_frame)
        self.resource_frame.pack(side=tk.BOTTOM, fill=tk.X)

        # Create the resource canvas
        self.resource_canvas = tk.Canvas(self.resource_frame, bg="lightgray")
        self.resource_canvas.pack(fill=tk.X)

        # List to store rectangle data
        self.rectangles = []

        # Draw the grids
        self.draw_grid()
        self.draw_resource_grid()

        # Create some initial rectangles
        self.add_rectangle(5, 3, 10, 4, "Task A", ["Resource A", "Resource B"])
        self.add_rectangle(
            12, 5, 16, 6, "Task B", ["Resource A", "Resource B", "Resource C"]
        )
        self.add_rectangle(2, 10, 5, 11, "Task C", ["Resource A"])
        self.add_rectangle(1, 1, 3, 2, "Task D", ["Resource A", "Resource D"])

        # Bind mouse events
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Motion>", self.on_motion)  # Bind mouse motion
        self.canvas.bind("<Configure>", self.on_resize)

        # Dragging state
        self.dragging = False
        self.resizing_left = False
        self.resizing_right = False
        self.drag_data = {
            "x": 0,
            "y": 0,
            "rectangle": None,
        }  # Store the current rectangle

        # Configure the main frame to expand the canvas frame
        self.main_frame.columnconfigure(0, weight=1)

    def draw_grid(self):
        """Draws the background grid on the canvas."""
        self.canvas.delete("grid")  # Remove existing grid lines
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()

        # Calculate cell dimensions based on canvas size
        self.cell_width = width / self.grid_cols
        self.cell_height = height / self.grid_rows

        # Draw vertical lines
        for i in range(self.grid_cols + 1):
            x = i * self.cell_width
            self.canvas.create_line(x, 0, x, height, fill="lightgray", tags="grid")

        # Draw horizontal lines
        for i in range(self.grid_rows + 1):
            y = i * self.cell_height
            self.canvas.create_line(0, y, width, y, fill="lightgray", tags="grid")

    def draw_resource_grid(self):
        """Draws the resource grid on the resource canvas."""
        self.resource_canvas.delete("resource_grid")
        width = self.resource_canvas.winfo_width()
        height = self.resource_rows * self.cell_height

        self.resource_canvas.config(height=height)

        # Draw vertical lines
        for i in range(self.grid_cols + 1):
            x = i * self.cell_width
            self.resource_canvas.create_line(
                x, 0, x, height, fill="darkgray", tags="resource_grid"
            )

        # Draw horizontal lines and resource labels
        for i in range(self.resource_rows):
            y = i * self.cell_height
            self.resource_canvas.create_line(
                0, y, width, y, fill="darkgray", tags="resource_grid"
            )
            self.resource_canvas.create_text(
                5,
                y + self.cell_height / 2,
                text=self.resources[i],
                anchor="w",
                tags="resource_grid",
            )
        self.update_resource_loading()

    def add_rectangle(
        self, start_col, start_row, end_col, end_row, description, resources
    ):
        """Adds a new rectangle to the canvas and the rectangles list."""
        x1 = start_col * self.cell_width
        y1 = start_row * self.cell_height
        x2 = end_col * self.cell_width
        y2 = end_row * self.cell_height

        # Create the main body of the rectangle
        rectangle_body_id = self.canvas.create_rectangle(
            x1 + 3, y1, x2 - 3, y2, fill="lightblue", tags=("rect", "body")
        )
        # Create the left resize handle
        rectangle_left_handle_id = self.canvas.create_rectangle(
            x1, y1, x1 + 3, y2, fill="darkblue", tags=("rect", "left_handle")
        )
        # Create the right resize handle
        rectangle_right_handle_id = self.canvas.create_rectangle(
            x2 - 3, y1, x2, y2, fill="darkblue", tags=("rect", "right_handle")
        )

        # Add task description as text inside the rectangle
        text_x = (x1 + x2) / 2
        text_y = (y1 + y2) / 2
        text_id = self.canvas.create_text(
            text_x,
            text_y,
            text=description,
            fill="black",
            font=("Arial", 8),
            tags=("rect", "text"),
            anchor="center",
        )

        self.rectangles.append(
            {
                "id": rectangle_body_id,
                "left_handle_id": rectangle_left_handle_id,
                "right_handle_id": rectangle_right_handle_id,
                "x1": x1,
                "y1": y1,
                "x2": x2,
                "y2": y2,
                "start_col": start_col,
                "start_row": start_row,
                "end_col": end_col,
                "end_row": end_row,
                "description": description,
                "text_id": text_id,
                "resources": resources,
            }
        )

    def on_click(self, event):
        """Handle mouse click event."""
        item = self.canvas.find_closest(event.x, event.y)
        if "rect" in self.canvas.gettags(item):
            self.dragging = True
            self.drag_data["x"] = event.x
            self.drag_data["y"] = event.y
            # Find the rectangle data that was clicked
            for rect in self.rectangles:
                if (
                    rect["id"] == item[0]
                    or rect["left_handle_id"] == item[0]
                    or rect["right_handle_id"] == item[0]
                    or rect["text_id"] == item[0]
                ):
                    self.drag_data["rectangle"] = rect
                    break

            # Check if the click is near the left or right edge
            if "left_handle" in self.canvas.gettags(item):
                self.resizing_left = True
                self.canvas.config(cursor="sb_h_double_arrow")
            elif "right_handle" in self.canvas.gettags(item):
                self.resizing_right = True
                self.canvas.config(cursor="sb_h_double_arrow")
            elif "body" in self.canvas.gettags(
                self.canvas.find_closest(event.x, event.y)
            ):
                self.canvas.config(cursor="hand2")
            else:
                self.resizing_left = False
                self.resizing_right = False

    def on_drag(self, event):
        """Handle mouse drag event."""
        if self.dragging and self.drag_data["rectangle"]:
            rect = self.drag_data["rectangle"]
            if self.resizing_left:
                # Resize from the left
                rect["x1"] = event.x
                rect["start_col"] = round(rect["x1"] / self.cell_width)
                rect["x1"] = rect["start_col"] * self.cell_width
            elif self.resizing_right:
                # Resize from the right
                rect["x2"] = event.x
                rect["end_col"] = round(rect["x2"] / self.cell_width)
                rect["x2"] = rect["end_col"] * self.cell_width
            else:
                # Move the entire rectangle
                delta_x = event.x - self.drag_data["x"]
                delta_y = event.y - self.drag_data["y"]

                # Update the rectangle's coordinates
                rect["x1"] += delta_x
                rect["x2"] += delta_x
                rect["y1"] += delta_y
                rect["y2"] += delta_y

            # Ensure rectangle height is always one grid row
            rect["y2"] = rect["y1"] + self.cell_height
            rect["end_row"] = rect["start_row"] + 1

            # Update the rectangle's coordinates on the canvas
            self.canvas.coords(
                rect["id"], rect["x1"] + 3, rect["y1"], rect["x2"] - 3, rect["y2"]
            )
            self.canvas.coords(
                rect["left_handle_id"],
                rect["x1"],
                rect["y1"],
                rect["x1"] + 3,
                rect["y2"],
            )
            self.canvas.coords(
                rect["right_handle_id"],
                rect["x2"] - 3,
                rect["y1"],
                rect["x2"],
                rect["y2"],
            )
            self.update_label_position(rect)

            self.drag_data["x"] = event.x
            self.drag_data["y"] = event.y

    def on_release(self, event):
        """Handle mouse release event."""
        if self.dragging and self.drag_data["rectangle"]:
            rect = self.drag_data["rectangle"]
            # Snap to grid
            rect["start_col"] = round(rect["x1"] / self.cell_width)
            rect["end_col"] = round(rect["x2"] / self.cell_width)
            rect["start_row"] = round(rect["y1"] / self.cell_height)
            rect["end_row"] = rect["start_row"] + 1

            rect["x1"] = rect["start_col"] * self.cell_width
            rect["x2"] = rect["end_col"] * self.cell_width
            rect["y1"] = rect["start_row"] * self.cell_height
            rect["y2"] = rect["end_row"] * self.cell_height

            # Update the rectangle's coordinates on the canvas
            self.canvas.coords(
                rect["id"], rect["x1"] + 3, rect["y1"], rect["x2"] - 3, rect["y2"]
            )
            self.canvas.coords(
                rect["left_handle_id"],
                rect["x1"],
                rect["y1"],
                rect["x1"] + 3,
                rect["y2"],
            )
            self.canvas.coords(
                rect["right_handle_id"],
                rect["x2"] - 3,
                rect["y1"],
                rect["x2"],
                rect["y2"],
            )
            self.update_label_position(rect)
            self.update_resource_loading()

        self.dragging = False
        self.resizing_left = False
        self.resizing_right = False
        self.drag_data["rectangle"] = None
        self.canvas.config(cursor="")  # Reset the cursor

    def on_motion(self, event):
        """Handle mouse motion event (for cursor changes)."""
        item = self.canvas.find_closest(event.x, event.y)
        if "left_handle" in self.canvas.gettags(item):
            self.canvas.config(cursor="sb_h_double_arrow")  # Left-right arrow
        elif "right_handle" in self.canvas.gettags(item):
            self.canvas.config(cursor="sb_h_double_arrow")  # Left-right arrow
        elif "body" in self.canvas.gettags(item):
            self.canvas.config(cursor="fleur")
        else:
            self.canvas.config(cursor="")  # Default cursor

    def on_resize(self, event):
        """Handle canvas resize event."""
        self.draw_grid()
        self.draw_resource_grid()
        for rect in self.rectangles:
            rect["x1"] = rect["start_col"] * self.cell_width
            rect["x2"] = rect["end_col"] * self.cell_width
            rect["y1"] = rect["start_row"] * self.cell_height
            rect["y2"] = rect["end_row"] * self.cell_height
            self.canvas.coords(
                rect["id"], rect["x1"] + 3, rect["y1"], rect["x2"] - 3, rect["y2"]
            )
            self.canvas.coords(
                rect["left_handle_id"],
                rect["x1"],
                rect["y1"],
                rect["x1"] + 3,
                rect["y2"],
            )
            self.canvas.coords(
                rect["right_handle_id"],
                rect["x2"] - 3,
                rect["y1"],
                rect["x2"],
                rect["y2"],
            )
            self.update_label_position(rect)
        self.update_resource_loading()

    def update_label_position(self, rect):
        """Updates the position of a single task label."""
        text_x = (rect["x1"] + rect["x2"]) / 2
        text_y = (rect["y1"] + rect["y2"]) / 2
        self.canvas.coords(rect["text_id"], text_x, text_y)

    def update_resource_loading(self):
        """Updates the resource loading display."""
        self.resource_canvas.delete("resource_loading")
        resource_loading = [[0] * self.grid_cols for _ in range(self.resource_rows)]

        for rect in self.rectangles:
            for col in range(rect["start_col"], rect["end_col"]):
                for resource in rect["resources"]:
                    resource_index = self.resources.index(resource)
                    resource_loading[resource_index][col] += 1

        for row in range(self.resource_rows):
            for col in range(self.grid_cols):
                x = (col + 0.5) * self.cell_width
                y = (row + 0.5) * self.cell_height
                self.resource_canvas.create_text(
                    x,
                    y,
                    text=str(resource_loading[row][col]),
                    tags="resource_loading",
                )


if __name__ == "__main__":
    root = tk.Tk()
    app = DraggableRectangleApp(root)
    root.mainloop()
