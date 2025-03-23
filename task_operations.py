import tkinter as tk
from tkinter import simpledialog, messagebox


class TaskOperations:
    def __init__(self, controller, model):
        self.controller = controller
        self.model = model

    def on_task_hover(self, event):
        """Handle mouse hover to change cursor"""
        x, y = event.x, event.y

        # Convert canvas coordinates to account for scrolling
        canvas_x = self.controller.task_canvas.canvasx(x)
        canvas_y = self.controller.task_canvas.canvasy(y)

        # Check if we're over a task edge or body
        task_ui_elements = self.controller.ui.task_ui_elements

        for task_id, ui_elements in task_ui_elements.items():
            x1, y1, x2, y2, connector_x, connector_y = (
                ui_elements["x1"],
                ui_elements["y1"],
                ui_elements["x2"],
                ui_elements["y2"],
                ui_elements["connector_x"],
                ui_elements["connector_y"],
            )
            connector_radius = 5

            # Connector (for adding dependencies)
            if (
                connector_x - connector_radius
                < canvas_x
                < connector_x + connector_radius
                and connector_y - connector_radius
                < canvas_y
                < connector_y + connector_radius
            ):
                self.controller.task_canvas.config(cursor="hand2")
                return

            # Left edge (for resizing)
            if abs(canvas_x - x1) < 5 and y1 < canvas_y < y2:
                self.controller.task_canvas.config(cursor="sb_h_double_arrow")
                return

            # Right edge (for resizing)
            if abs(canvas_x - x2) < 5 and y1 < canvas_y < y2:
                self.controller.task_canvas.config(cursor="sb_h_double_arrow")
                return

            # Task body (for moving or URL hover)
            if x1 < canvas_x < x2 and y1 < canvas_y < y2:
                task = self.model.get_task(task_id)

                if task and task.get("url"):  # Check if task has a URL
                    text_bbox = self.controller.task_canvas.bbox(ui_elements["text"])
                    if (
                        text_bbox
                        and text_bbox[0] <= canvas_x <= text_bbox[2]
                        and text_bbox[1] <= canvas_y <= text_bbox[3]
                    ):
                        self.controller.task_canvas.config(cursor="hand2")
                        return

                self.controller.task_canvas.config(cursor="fleur")
                return

        # Reset cursor if not over a task
        self.controller.task_canvas.config(cursor="")

    def edit_task_name(self, parent=None, task=None):
        """Edit the name of the selected task"""
        if task is None:
            task = self.controller.selected_task

        if task:
            new_name = simpledialog.askstring(
                "Edit Task Name",
                "Enter new task name:",
                initialvalue=task["description"],
                parent=parent or self.controller.root,
            )
            if new_name:
                # Update the task description in model
                task["description"] = new_name

                # Update the displayed text in view
                task_id = task["task_id"]
                if task_id in self.controller.ui.task_ui_elements:
                    text_id = self.controller.ui.task_ui_elements[task_id]["text"]
                    self.controller.task_canvas.itemconfig(
                        text_id, text=f"{task_id} - {new_name}"
                    )

    def edit_task_url(self, task=None):
        """Edit the url of the selected task"""
        if task is None:
            task = self.controller.selected_task

        if task:
            # Ensure the task has a 'url' key with a default blank value
            task.setdefault("url", "")
            new_url = simpledialog.askstring(
                "Edit Task URL",
                "Enter new task URL:",
                initialvalue=task["url"],
                parent=self.controller.root,
            )
            if new_url is not None:
                # Update the task url in model
                task["url"] = new_url

                # Redraw the task to update the URL behavior
                self.controller.ui.draw_task_grid()

    def add_predecessor_dialog(self, task):
        """Add a predecessor to a task."""
        if not task:
            return

        predecessor_id = simpledialog.askinteger(
            "Add Predecessor",
            "Enter the ID of the predecessor task:",
            parent=self.controller.root,
        )
        if predecessor_id is not None:
            if self.model.add_predecessor(task["task_id"], predecessor_id):
                # Redraw to show dependencies
                self.controller.ui.draw_dependencies()
            else:
                messagebox.showerror("Error", "Predecessor task not found.")

    def add_successor(self, task, target_task):
        """Add a successor to a task."""
        if not task or not target_task:
            return

        if self.model.add_successor(task["task_id"], target_task["task_id"]):
            # Redraw to show dependencies
            self.controller.ui.draw_dependencies()
        else:
            messagebox.showerror("Error", "Successor task not found.")

    def add_successor_dialog(self, task):
        """Add a successor to a task using a dialog box."""
        if not task:
            return

        successor_id = simpledialog.askinteger(
            "Add Successor",
            "Enter the ID of the successor task:",
            parent=self.controller.root,
        )
        if successor_id is not None:
            if self.model.add_successor(task["task_id"], successor_id):
                # Redraw to show dependencies
                self.controller.ui.draw_dependencies()
            else:
                messagebox.showerror("Error", "Successor task not found.")

    def edit_task_resources(self, task=None):
        """Edit resources for the selected task"""
        if task is None:
            task = self.controller.selected_task

        if task:
            # Create a dialog for resource selection
            dialog = tk.Toplevel(self.controller.root)
            dialog.title("Edit Task Resources")
            dialog.geometry("300x200")
            dialog.transient(self.controller.root)
            dialog.grab_set()

            # Track selected resources
            resource_vars = {}

            # Create checkboxes for each resource
            tk.Label(dialog, text="Select resources for this task:").pack(pady=5)

            for resource in self.model.resources:
                var = tk.BooleanVar(value=(resource in task["resources"]))
                resource_vars[resource] = var
                tk.Checkbutton(dialog, text=resource, variable=var).pack(
                    anchor="w", padx=20
                )

            # Function to save selection and close dialog
            def save_resources():
                task["resources"] = [r for r, v in resource_vars.items() if v.get()]
                dialog.destroy()
                self.controller.update_resource_loading()

            # Add Save button
            tk.Button(dialog, text="Save", command=save_resources).pack(pady=10)

            # Center the dialog on the main window
            dialog.update_idletasks()
            x = (
                self.controller.root.winfo_x()
                + (self.controller.root.winfo_width() - dialog.winfo_width()) // 2
            )
            y = (
                self.controller.root.winfo_y()
                + (self.controller.root.winfo_height() - dialog.winfo_height()) // 2
            )
            dialog.geometry(f"+{x}+{y}")

    def delete_task(self):
        """Delete the selected task"""
        if self.controller.selected_task:
            task_id = self.controller.selected_task["task_id"]

            # Remove the task from the model
            if self.model.delete_task(task_id):
                # Clean up UI elements
                if task_id in self.controller.ui.task_ui_elements:
                    ui_elements = self.controller.ui.task_ui_elements[task_id]
                    for element_id in ui_elements.values():
                        if isinstance(
                            element_id, int
                        ):  # Check if it's a canvas item ID
                            self.controller.task_canvas.delete(element_id)

                    # Remove from UI elements tracking
                    del self.controller.ui.task_ui_elements[task_id]

                # Reset selected task
                self.controller.selected_task = None

                # Redraw dependencies
                self.controller.ui.draw_dependencies()

                # Update resource loading
                self.controller.update_resource_loading()

    def add_resource(self, parent=None):
        """Add a new resource to the project"""
        parent = parent or self.controller.root

        resource_name = simpledialog.askstring(
            "Add Resource", "Enter new resource name:", parent=parent
        )
        if resource_name:
            if self.model.add_resource(resource_name):
                self.controller.ui.draw_resource_grid()
                self.controller.update_resource_loading()
            else:
                messagebox.showinfo("Information", "Resource already exists.")

    def edit_resources(self, parent=None):
        """Edit the list of resources"""
        # Create a dialog for resource editing
        parent = parent or self.controller.root

        dialog = tk.Toplevel(parent)
        dialog.title("Edit Resources")
        # Position the dialog relative to the parent window
        x = parent.winfo_x() + 50
        y = parent.winfo_y() + 50
        dialog.geometry(f"400x300+{x}+{y}")
        dialog.transient(parent)
        dialog.grab_set()  # Important: Prevents interaction with the main window

        # Create a frame for the resource list
        list_frame = tk.Frame(dialog)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Scrollbar for the listbox
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Create a listbox to display resources
        resource_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set)
        resource_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=resource_listbox.yview)

        # Populate the listbox
        for resource in self.model.resources:
            resource_listbox.insert(tk.END, resource)

        # Create buttons for actions
        button_frame = tk.Frame(dialog)
        button_frame.pack(fill=tk.X, padx=10, pady=5)

        # Define button actions
        def add_resource_from_dialog():
            resource_name = simpledialog.askstring(
                "Add Resource", "Enter new resource name:", parent=dialog
            )
            if resource_name and resource_name not in self.model.resources:
                self.model.resources.append(resource_name)
                resource_listbox.insert(tk.END, resource_name)

        def remove_selected_resource():
            selected_indices = resource_listbox.curselection()
            if not selected_indices:
                return

            # Get the resource to remove
            index = selected_indices[0]
            resource = resource_listbox.get(index)

            # Confirm deletion
            if messagebox.askyesno(
                "Confirm Delete", f"Delete resource '{resource}'?", parent=dialog
            ):
                # Check if resource is used by any tasks
                used_by_tasks = []
                for task in self.model.tasks:
                    if resource in task["resources"]:
                        used_by_tasks.append(task["description"])

                if used_by_tasks:
                    # Resource is in use - ask what to do
                    message = f"Resource '{resource}' is used by {len(used_by_tasks)} tasks. Remove it from tasks too?"
                    if messagebox.askyesno("Resource in Use", message, parent=dialog):
                        # Remove resource using model method (will remove from tasks too)
                        self.model.remove_resource(resource)
                        resource_listbox.delete(index)
                    else:
                        # Cancel deletion
                        return
                else:
                    # Remove the resource
                    self.model.remove_resource(resource)
                    resource_listbox.delete(index)

        def save_resources():
            # Apply changes and close dialog
            dialog.destroy()
            # Redraw grids to reflect changes
            self.controller.ui.draw_resource_grid()
            self.controller.update_resource_loading()

        # Add buttons
        tk.Button(button_frame, text="Add...", command=add_resource_from_dialog).pack(
            side=tk.LEFT, padx=5
        )
        tk.Button(button_frame, text="Remove", command=remove_selected_resource).pack(
            side=tk.LEFT, padx=5
        )
        tk.Button(button_frame, text="Save", command=save_resources).pack(
            side=tk.RIGHT, padx=5
        )

    def edit_project_settings(self, parent=None):
        """Edit project settings like number of days"""
        # Create a dialog for project settings
        parent = parent or self.controller.root

        dialog = tk.Toplevel(parent)
        dialog.title("Project Settings")
        # Position the dialog relative to the parent window
        x = parent.winfo_x() + 50
        y = parent.winfo_y() + 50
        dialog.geometry(f"300x150+{x}+{y}")
        dialog.transient(parent)
        dialog.grab_set()  # Prevent interaction with the main window

        # Create form fields
        settings_frame = tk.Frame(dialog)
        settings_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Days setting
        tk.Label(settings_frame, text="Number of Days:").grid(
            row=0, column=0, sticky="w", pady=5
        )
        days_var = tk.IntVar(value=self.model.days)
        days_entry = tk.Entry(settings_frame, textvariable=days_var, width=10)
        days_entry.grid(row=0, column=1, sticky="w", pady=5)

        # Max tasks setting
        tk.Label(settings_frame, text="Maximum Tasks:").grid(
            row=1, column=0, sticky="w", pady=5
        )
        max_tasks_var = tk.IntVar(value=self.model.max_tasks)
        max_tasks_entry = tk.Entry(settings_frame, textvariable=max_tasks_var, width=10)
        max_tasks_entry.grid(row=1, column=1, sticky="w", pady=5)

        # Button frame
        button_frame = tk.Frame(dialog)
        button_frame.pack(fill=tk.X, pady=10)

        def save_settings():
            try:
                new_days = int(days_var.get())
                new_max_tasks = int(max_tasks_var.get())

                if new_days < 1:
                    messagebox.showerror(
                        "Invalid Value",
                        "Number of days must be at least 1.",
                        parent=dialog,
                    )
                    return

                if new_max_tasks < 1:
                    messagebox.showerror(
                        "Invalid Value",
                        "Maximum tasks must be at least 1.",
                        parent=dialog,
                    )
                    return

                # Check if any tasks would be outside the new bounds
                tasks_out_of_bounds = False
                for task in self.model.tasks:
                    if (
                        task["col"] + task["duration"] > new_days
                        or task["row"] >= new_max_tasks
                    ):
                        tasks_out_of_bounds = True
                        break

                if tasks_out_of_bounds:
                    if not messagebox.askyesno(
                        "Warning",
                        "Some tasks will be outside the new boundaries. These tasks may be lost or truncated. Continue?",
                        parent=dialog,
                    ):
                        return

                # Apply the settings
                self.model.days = new_days
                self.model.max_tasks = new_max_tasks

                # Update the UI
                self.controller.update_view()

                dialog.destroy()

            except ValueError:
                messagebox.showerror(
                    "Invalid Input", "Please enter valid numbers.", parent=dialog
                )

        # Add buttons
        tk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(
            side=tk.RIGHT, padx=5
        )
        tk.Button(button_frame, text="Save", command=save_settings).pack(
            side=tk.RIGHT, padx=5
        )

    def on_task_press(self, event):
        """Handle mouse press on tasks or grid"""
        x, y = event.x, event.y

        # Convert canvas coordinates to account for scrolling
        canvas_x = self.controller.task_canvas.canvasx(x)
        canvas_y = self.controller.task_canvas.canvasy(y)

        self.controller.drag_start_x = canvas_x
        self.controller.drag_start_y = canvas_y

        # Check if clicking on a task
        task_clicked = False
        task_ui_elements = self.controller.ui.task_ui_elements

        for task_id, ui_elements in task_ui_elements.items():
            x1, y1, x2, y2, connector_x, connector_y = (
                ui_elements["x1"],
                ui_elements["y1"],
                ui_elements["x2"],
                ui_elements["y2"],
                ui_elements["connector_x"],
                ui_elements["connector_y"],
            )
            connector_radius = 5

            if (
                connector_x - connector_radius
                < canvas_x
                < connector_x + connector_radius
                and connector_y - connector_radius
                < canvas_y
                < connector_y + connector_radius
            ):
                self.controller.selected_task = self.model.get_task(task_id)
                self.controller.dragging_connector = True
                self.controller.connector_line = (
                    self.controller.task_canvas.create_line(
                        connector_x,
                        connector_y,
                        connector_x,
                        connector_y,
                        fill="blue",
                        width=2,
                        tags=("connector_line",),
                    )
                )
                return

            # Check if clicking on left edge (for left resize)
            if abs(canvas_x - x1) < 5 and y1 < canvas_y < y2:
                self.controller.selected_task = self.model.get_task(task_id)
                self.controller.resize_edge = "left"
                task_clicked = True
                break

            # Check if clicking on right edge (for right resize)
            if abs(canvas_x - x2) < 5 and y1 < canvas_y < y2:
                self.controller.selected_task = self.model.get_task(task_id)
                self.controller.resize_edge = "right"
                task_clicked = True
                break

            # Check if clicking on task body (for moving)
            if x1 < canvas_x < x2 and y1 < canvas_y < y2:
                self.controller.selected_task = self.model.get_task(task_id)
                self.controller.resize_edge = None
                task_clicked = True
                break

        # If no task was clicked and we're in the grid area, start creating a new task
        if (
            not task_clicked
            and canvas_y >= 0
            and canvas_y <= self.model.max_tasks * self.controller.task_height
        ):
            # Snap to grid
            row, col = self.controller.convert_ui_to_model_coordinates(
                canvas_x, canvas_y
            )

            # Set starting point for new task
            self.controller.new_task_in_progress = True
            self.controller.new_task_start = (col, row)

            # Create rubberband rectangle for visual feedback
            x1 = col * self.controller.cell_width
            y1 = row * self.controller.task_height
            self.controller.rubberband = self.controller.task_canvas.create_rectangle(
                x1,
                y1,
                x1,
                y1 + self.controller.task_height,
                outline="blue",
                width=2,
                dash=(4, 4),
            )

    def on_task_drag(self, event):
        """Handle mouse drag to move, resize tasks or create new task"""
        x, y = event.x, event.y

        # Convert canvas coordinates to account for scrolling
        canvas_x = self.controller.task_canvas.canvasx(x)
        canvas_y = self.controller.task_canvas.canvasy(y)

        if self.controller.dragging_connector:
            task_id = self.controller.selected_task["task_id"]
            ui_elements = self.controller.ui.task_ui_elements.get(task_id)
            if ui_elements:  # Check if ui_elements exists for this task
                connector_x = ui_elements["connector_x"]
                connector_y = ui_elements["connector_y"]
                self.controller.task_canvas.coords(
                    self.controller.connector_line,
                    connector_x,
                    connector_y,
                    canvas_x,
                    canvas_y,
                )
            return

        if self.controller.selected_task:  # Existing task manipulation
            dx = canvas_x - self.controller.drag_start_x
            dy = canvas_y - self.controller.drag_start_y

            task = self.controller.selected_task
            task_id = task["task_id"]
            ui_elements = self.controller.ui.task_ui_elements.get(task_id)

            if not ui_elements:
                return

            if self.controller.resize_edge == "left":
                # Resize from left edge
                new_width = ui_elements["x2"] - (ui_elements["x1"] + dx)
                if new_width >= self.controller.cell_width:  # Minimum task width
                    self.controller.task_canvas.move(ui_elements["left_edge"], dx, 0)
                    self.controller.task_canvas.coords(
                        ui_elements["box"],
                        ui_elements["x1"] + dx,
                        ui_elements["y1"],
                        ui_elements["x2"],
                        ui_elements["y2"],
                    )
                    # Update stored coordinates
                    ui_elements["x1"] += dx

                    # Update text position
                    self.controller.task_canvas.coords(
                        ui_elements["text"],
                        (ui_elements["x1"] + ui_elements["x2"]) / 2,
                        (ui_elements["y1"] + ui_elements["y2"]) / 2,
                    )

            elif self.controller.resize_edge == "right":
                # Resize from right edge
                new_width = ui_elements["x2"] + dx - ui_elements["x1"]
                if new_width >= self.controller.cell_width:  # Minimum task width
                    self.controller.task_canvas.move(ui_elements["right_edge"], dx, 0)
                    self.controller.task_canvas.coords(
                        ui_elements["box"],
                        ui_elements["x1"],
                        ui_elements["y1"],
                        ui_elements["x2"] + dx,
                        ui_elements["y2"],
                    )
                    # Update stored coordinates
                    ui_elements["x2"] += dx

                    # Update connector position
                    ui_elements["connector_x"] += dx
                    self.controller.task_canvas.move(ui_elements["connector"], dx, 0)

                    # Update text position
                    self.controller.task_canvas.coords(
                        ui_elements["text"],
                        (ui_elements["x1"] + ui_elements["x2"]) / 2,
                        (ui_elements["y1"] + ui_elements["y2"]) / 2,
                    )

            else:
                # Move entire task
                self.controller.task_canvas.move(ui_elements["box"], dx, dy)
                self.controller.task_canvas.move(ui_elements["left_edge"], dx, dy)
                self.controller.task_canvas.move(ui_elements["right_edge"], dx, dy)
                self.controller.task_canvas.move(ui_elements["text"], dx, dy)

                # Update stored coordinates
                ui_elements["x1"] += dx
                ui_elements["y1"] += dy
                ui_elements["x2"] += dx
                ui_elements["y2"] += dy
                # Update connector position in UI elements dictionary
                ui_elements["connector_x"] += dx
                ui_elements["connector_y"] += dy

                # Update connector position on canvas
                self.controller.task_canvas.move(ui_elements["connector"], dx, dy)

            self.controller.drag_start_x = canvas_x
            self.controller.drag_start_y = canvas_y

        elif self.controller.new_task_in_progress:  # New task creation in progress
            # Update rubberband to show the task being created
            start_col, start_row = self.controller.new_task_start
            current_col = max(
                0, min(self.model.days - 1, int(canvas_x / self.controller.cell_width))
            )

            # Determine the left and right columns based on drag direction
            left_col = min(start_col, current_col)
            right_col = max(start_col, current_col)

            # Update rubberband rectangle
            x1 = left_col * self.controller.cell_width
            y1 = start_row * self.controller.task_height
            x2 = (right_col + 1) * self.controller.cell_width
            y2 = y1 + self.controller.task_height

            self.controller.task_canvas.coords(
                self.controller.rubberband, x1, y1, x2, y2
            )

    def on_task_release(self, event):
        """Handle mouse release to finalize task position/size or create new task"""
        x, y = event.x, event.y

        # Convert canvas coordinates to account for scrolling
        canvas_x = self.controller.task_canvas.canvasx(x)
        canvas_y = self.controller.task_canvas.canvasy(y)

        if self.controller.dragging_connector:
            # Check for collision with another task
            target_task = self.find_task_at(canvas_x, canvas_y)

            if target_task:
                self.add_successor(self.controller.selected_task, target_task)

            # Delete connector line
            self.controller.task_canvas.delete(self.controller.connector_line)
            self.controller.connector_line = None
            self.controller.dragging_connector = False
            return

        if self.controller.selected_task:  # Existing task manipulation
            task = self.controller.selected_task
            task_id = task["task_id"]
            ui_elements = self.controller.ui.task_ui_elements.get(task_id)

            if not ui_elements:
                return

            # Snap to grid
            if self.controller.resize_edge == "left":
                # Snap left edge
                grid_col = round(ui_elements["x1"] / self.controller.cell_width)
                new_x1 = grid_col * self.controller.cell_width
                dx = new_x1 - ui_elements["x1"]

                # Update visuals
                self.controller.task_canvas.move(ui_elements["left_edge"], dx, 0)
                self.controller.task_canvas.coords(
                    ui_elements["box"],
                    new_x1,
                    ui_elements["y1"],
                    ui_elements["x2"],
                    ui_elements["y2"],
                )

                # Update stored coordinates
                ui_elements["x1"] = new_x1

                # Update model
                task["col"] = grid_col
                task["duration"] = round(
                    (ui_elements["x2"] - ui_elements["x1"]) / self.controller.cell_width
                )

            elif self.controller.resize_edge == "right":
                # Snap right edge
                grid_col = round(ui_elements["x2"] / self.controller.cell_width)
                new_x2 = grid_col * self.controller.cell_width
                dx = new_x2 - ui_elements["x2"]

                # Update visuals
                self.controller.task_canvas.move(ui_elements["right_edge"], dx, 0)
                self.controller.task_canvas.coords(
                    ui_elements["box"],
                    ui_elements["x1"],
                    ui_elements["y1"],
                    new_x2,
                    ui_elements["y2"],
                )

                # Update stored coordinates
                ui_elements["x2"] = new_x2

                # Update model
                task["duration"] = round(
                    (ui_elements["x2"] - ui_elements["x1"]) / self.controller.cell_width
                )

            else:
                # Snap entire task
                grid_row = round(ui_elements["y1"] / self.controller.task_height)
                grid_col = round(ui_elements["x1"] / self.controller.cell_width)

                new_x1 = grid_col * self.controller.cell_width
                new_y1 = grid_row * self.controller.task_height
                new_x2 = new_x1 + task["duration"] * self.controller.cell_width
                new_y2 = new_y1 + self.controller.task_height

                # Keep task within bounds
                if grid_row >= self.model.max_tasks:
                    grid_row = self.model.max_tasks - 1
                    new_y1 = grid_row * self.controller.task_height
                    new_y2 = new_y1 + self.controller.task_height

                if grid_row < 0:
                    grid_row = 0
                    new_y1 = 0
                    new_y2 = self.controller.task_height

                if grid_col < 0:
                    grid_col = 0
                    new_x1 = 0
                    new_x2 = new_x1 + task["duration"] * self.controller.cell_width

                if grid_col + task["duration"] > self.model.days:
                    grid_col = self.model.days - task["duration"]
                    new_x1 = grid_col * self.controller.cell_width
                    new_x2 = new_x1 + task["duration"] * self.controller.cell_width

                # Update visuals
                self.controller.task_canvas.coords(
                    ui_elements["box"], new_x1, new_y1, new_x2, new_y2
                )
                self.controller.task_canvas.coords(
                    ui_elements["left_edge"], new_x1, new_y1, new_x1, new_y2
                )
                self.controller.task_canvas.coords(
                    ui_elements["right_edge"], new_x2, new_y1, new_x2, new_y2
                )
                self.controller.task_canvas.coords(
                    ui_elements["text"], (new_x1 + new_x2) / 2, (new_y1 + new_y2) / 2
                )

                # Update connector position AFTER snapping
                ui_elements["connector_x"] = new_x2
                ui_elements["connector_y"] = (new_y1 + new_y2) / 2
                self.controller.task_canvas.coords(
                    ui_elements["connector"],
                    ui_elements["connector_x"] - 5,
                    ui_elements["connector_y"] - 5,
                    ui_elements["connector_x"] + 5,
                    ui_elements["connector_y"] + 5,
                )

                # Update stored coordinates
                ui_elements["x1"], ui_elements["y1"] = new_x1, new_y1
                ui_elements["x2"], ui_elements["y2"] = new_x2, new_y2

                # Update model
                task["row"], task["col"] = grid_row, grid_col

            # Update text position
            self.controller.task_canvas.coords(
                ui_elements["text"],
                (ui_elements["x1"] + ui_elements["x2"]) / 2,
                (ui_elements["y1"] + ui_elements["y2"]) / 2,
            )

            # Reset selection
            self.controller.selected_task = None
            self.controller.resize_edge = None

            # Redraw dependencies
            self.controller.ui.draw_dependencies()

        elif self.controller.new_task_in_progress:  # New task creation
            # Get the start and end columns
            start_col, row = self.controller.new_task_start
            end_col = max(
                0, min(self.model.days - 1, int(canvas_x / self.controller.cell_width))
            )

            # Determine the left column and duration
            left_col = min(start_col, end_col)
            right_col = max(start_col, end_col)
            duration = right_col - left_col + 1

            # Only create task if it has a valid size
            if duration >= 1:
                # Create new task
                task_name = simpledialog.askstring(
                    "New Task", "Enter task name:", parent=self.controller.root
                )
                if task_name:
                    # Create a new task in the model
                    new_task = self.model.add_task(
                        row=row, col=left_col, duration=duration, description=task_name
                    )

                    # Draw the new task
                    self.controller.ui.draw_task(new_task)

                    # Prompt for resources
                    self.edit_task_resources(new_task)

            # Remove the rubberband
            if self.controller.rubberband:
                self.controller.task_canvas.delete(self.controller.rubberband)
                self.controller.rubberband = None

            # Reset new task flags
            self.controller.new_task_in_progress = False
            self.controller.new_task_start = None

        # Update resource loading
        self.controller.update_resource_loading()

    def on_right_click(self, event):
        """Handle right-click to show context menu"""
        x, y = event.x, event.y

        # Convert canvas coordinates to account for scrolling
        canvas_x = self.controller.task_canvas.canvasx(x)
        canvas_y = self.controller.task_canvas.canvasy(y)

        # Check if right-clicking on a task
        task_ui_elements = self.controller.ui.task_ui_elements

        for task_id, ui_elements in task_ui_elements.items():
            x1, y1, x2, y2 = (
                ui_elements["x1"],
                ui_elements["y1"],
                ui_elements["x2"],
                ui_elements["y2"],
            )

            if x1 < canvas_x < x2 and y1 < canvas_y < y2:
                self.controller.selected_task = self.model.get_task(task_id)
                # Show context menu
                self.controller.ui.context_menu.post(event.x_root, event.y_root)
                return

    def find_task_at(self, x, y):
        """Finds the task at the given coordinates."""
        for task_id, ui_elements in self.controller.ui.task_ui_elements.items():
            x1, y1, x2, y2 = (
                ui_elements["x1"],
                ui_elements["y1"],
                ui_elements["x2"],
                ui_elements["y2"],
            )
            if x1 < x < x2 and y1 < y < y2:
                return self.model.get_task(task_id)
        return None
