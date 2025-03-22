import tkinter as tk
from tkinter import simpledialog, messagebox


class TaskOperations:
    def __init__(self, manager):
        self.manager = manager

    def calculate_resource_loading(self):
        """Calculate and display resource loading based on task positions"""
        # Initialize resource loading grid
        resource_loading = {}
        for resource in self.manager.resources:
            resource_loading[resource] = [0] * self.manager.days

        # Calculate resource usage for each day based on tasks
        for task in self.manager.tasks:
            col = task["col"]
            duration = task["duration"]
            for resource in task["resources"]:
                for day in range(duration):
                    if 0 <= col + day < self.manager.days:  # Ensure we're within bounds
                        resource_loading[resource][col + day] += 1

        # Clear previous loading display
        self.manager.resource_canvas.delete("loading")

        # Display resource loading
        for i, resource in enumerate(self.manager.resources):
            for day in range(self.manager.days):
                load = resource_loading[resource][day]
                x = day * self.manager.cell_width
                y = i * self.manager.task_height

                # Choose color based on load
                color = "white"
                if load > 0:
                    intensity = min(load * 50, 200)  # Cap intensity
                    color = f"#{255-intensity:02x}{255-intensity:02x}ff"  # Bluish color

                # Create cell
                self.manager.resource_canvas.create_rectangle(
                    x,
                    y,
                    x + self.manager.cell_width,
                    y + self.manager.task_height,
                    fill=color,
                    outline="gray",
                    tags="loading",
                )

                # Display load number
                if load > 0:
                    self.manager.resource_canvas.create_text(
                        x + self.manager.cell_width / 2,
                        y + self.manager.task_height / 2,
                        text=str(load),
                        tags="loading",
                    )

    def on_task_hover(self, event):
        """Handle mouse hover to change cursor"""
        x, y = event.x, event.y

        # Convert canvas coordinates to account for scrolling
        canvas_x = self.manager.task_canvas.canvasx(x)
        canvas_y = self.manager.task_canvas.canvasy(y)

        # Check if we're over a task edge (for resizing)
        for task in self.manager.tasks:
            if "x1" not in task:
                continue

            # Left edge
            if abs(canvas_x - task["x1"]) < 5 and task["y1"] < canvas_y < task["y2"]:
                self.manager.task_canvas.config(cursor="sb_h_double_arrow")
                return

            # Right edge
            if abs(canvas_x - task["x2"]) < 5 and task["y1"] < canvas_y < task["y2"]:
                self.manager.task_canvas.config(cursor="sb_h_double_arrow")
                return

            # Task body (for moving or URL hover)
            if (
                task["x1"] < canvas_x < task["x2"]
                and task["y1"] < canvas_y < task["y2"]
            ):
                if "text" in task:  # Check if hovering over the task description text
                    text_bbox = self.manager.task_canvas.bbox(task["text"])
                    if (
                        text_bbox
                        and text_bbox[0] <= canvas_x <= text_bbox[2]
                        and text_bbox[1] <= canvas_y <= text_bbox[3]
                    ):
                        if "url" in task and task["url"]:  # Check if task has a URL
                            self.manager.task_canvas.config(cursor="hand2")
                            return
                self.manager.task_canvas.config(cursor="fleur")
                return
            if (
                task["x1"] < canvas_x < task["x2"]
                and task["y1"] < canvas_y < task["y2"]
            ):
                self.manager.task_canvas.config(cursor="fleur")
                return

        # Reset cursor if not over a task
        self.manager.task_canvas.config(cursor="")

    def on_task_press(self, event):
        """Handle mouse press on tasks or grid"""
        x, y = event.x, event.y

        # Convert canvas coordinates to account for scrolling
        canvas_x = self.manager.task_canvas.canvasx(x)
        canvas_y = self.manager.task_canvas.canvasy(y)

        self.manager.drag_start_x = canvas_x
        self.manager.drag_start_y = canvas_y

        # Check if clicking on a task
        task_clicked = False
        for task in self.manager.tasks:
            if "x1" not in task:
                continue

            # Check if clicking on left edge (for left resize)
            if abs(canvas_x - task["x1"]) < 5 and task["y1"] < canvas_y < task["y2"]:
                self.manager.selected_task = task
                self.manager.resize_edge = "left"
                task_clicked = True
                break

            # Check if clicking on right edge (for right resize)
            if abs(canvas_x - task["x2"]) < 5 and task["y1"] < canvas_y < task["y2"]:
                self.manager.selected_task = task
                self.manager.resize_edge = "right"
                task_clicked = True
                break

            # Check if clicking on task body (for moving)
            if (
                task["x1"] < canvas_x < task["x2"]
                and task["y1"] < canvas_y < task["y2"]
            ):
                self.manager.selected_task = task
                self.manager.resize_edge = None
                task_clicked = True
                break

        # If no task was clicked and we're in the grid area, start creating a new task
        if (
            not task_clicked
            and canvas_y >= 0
            and canvas_y <= self.manager.max_tasks * self.manager.task_height
        ):
            # Snap to grid
            col = int(canvas_x / self.manager.cell_width)
            row = int(canvas_y / self.manager.task_height)

            # Set starting point for new task
            self.manager.new_task_in_progress = True
            self.manager.new_task_start = (col, row)

            # Create rubberband rectangle for visual feedback
            x1 = col * self.manager.cell_width
            y1 = row * self.manager.task_height
            self.manager.rubberband = self.manager.task_canvas.create_rectangle(
                x1,
                y1,
                x1,
                y1 + self.manager.task_height,
                outline="blue",
                width=2,
                dash=(4, 4),
            )

    def on_task_drag(self, event):
        """Handle mouse drag to move, resize tasks or create new task"""
        x, y = event.x, event.y

        # Convert canvas coordinates to account for scrolling
        canvas_x = self.manager.task_canvas.canvasx(x)
        canvas_y = self.manager.task_canvas.canvasy(y)

        if self.manager.selected_task:  # Existing task manipulation
            dx = canvas_x - self.manager.drag_start_x
            dy = canvas_y - self.manager.drag_start_y

            task = self.manager.selected_task

            if self.manager.resize_edge == "left":
                # Resize from left edge
                new_width = task["x2"] - (task["x1"] + dx)
                if new_width >= self.manager.cell_width:  # Minimum task width
                    self.manager.task_canvas.move(task["left_edge"], dx, 0)
                    self.manager.task_canvas.coords(
                        task["box"], task["x1"] + dx, task["y1"], task["x2"], task["y2"]
                    )
                    # Update stored coordinates
                    task["x1"] += dx

                    # Update text position
                    self.manager.task_canvas.coords(
                        task["text"],
                        (task["x1"] + task["x2"]) / 2,
                        (task["y1"] + task["y2"]) / 2,
                    )

            elif self.manager.resize_edge == "right":
                # Resize from right edge
                new_width = task["x2"] + dx - task["x1"]
                if new_width >= self.manager.cell_width:  # Minimum task width
                    self.manager.task_canvas.move(task["right_edge"], dx, 0)
                    self.manager.task_canvas.coords(
                        task["box"], task["x1"], task["y1"], task["x2"] + dx, task["y2"]
                    )
                    # Update stored coordinates
                    task["x2"] += dx

                    # Update text position
                    self.manager.task_canvas.coords(
                        task["text"],
                        (task["x1"] + task["x2"]) / 2,
                        (task["y1"] + task["y2"]) / 2,
                    )

            else:
                # Move entire task
                self.manager.task_canvas.move(task["box"], dx, dy)
                self.manager.task_canvas.move(task["left_edge"], dx, dy)
                self.manager.task_canvas.move(task["right_edge"], dx, dy)
                self.manager.task_canvas.move(task["text"], dx, dy)

                # Update stored coordinates
                task["x1"] += dx
                task["y1"] += dy
                task["x2"] += dx
                task["y2"] += dy

            self.manager.drag_start_x = canvas_x
            self.manager.drag_start_y = canvas_y

        elif self.manager.new_task_in_progress:  # New task creation in progress
            # Update rubberband to show the task being created
            start_col, start_row = self.manager.new_task_start
            current_col = max(
                0, min(self.manager.days - 1, int(canvas_x / self.manager.cell_width))
            )

            # Determine the left and right columns based on drag direction
            left_col = min(start_col, current_col)
            right_col = max(start_col, current_col)

            # Update rubberband rectangle
            x1 = left_col * self.manager.cell_width
            y1 = start_row * self.manager.task_height
            x2 = (right_col + 1) * self.manager.cell_width
            y2 = y1 + self.manager.task_height

            self.manager.task_canvas.coords(self.manager.rubberband, x1, y1, x2, y2)

    def on_task_release(self, event):
        """Handle mouse release to finalize task position/size or create new task"""
        x, y = event.x, event.y

        # Convert canvas coordinates to account for scrolling
        canvas_x = self.manager.task_canvas.canvasx(x)
        canvas_y = self.manager.task_canvas.canvasy(y)

        if self.manager.selected_task:  # Existing task manipulation
            task = self.manager.selected_task

            # Snap to grid
            if self.manager.resize_edge == "left":
                # Snap left edge
                grid_col = round(task["x1"] / self.manager.cell_width)
                new_x1 = grid_col * self.manager.cell_width
                dx = new_x1 - task["x1"]

                # Update visuals
                self.manager.task_canvas.move(task["left_edge"], dx, 0)
                self.manager.task_canvas.coords(
                    task["box"], new_x1, task["y1"], task["x2"], task["y2"]
                )

                # Update stored coordinates
                task["x1"] = new_x1
                task["col"] = grid_col
                task["duration"] = round(
                    (task["x2"] - task["x1"]) / self.manager.cell_width
                )

            elif self.manager.resize_edge == "right":
                # Snap right edge
                grid_col = round(task["x2"] / self.manager.cell_width)
                new_x2 = grid_col * self.manager.cell_width
                dx = new_x2 - task["x2"]

                # Update visuals
                self.manager.task_canvas.move(task["right_edge"], dx, 0)
                self.manager.task_canvas.coords(
                    task["box"], task["x1"], task["y1"], new_x2, task["y2"]
                )

                # Update stored coordinates
                task["x2"] = new_x2
                task["duration"] = round(
                    (task["x2"] - task["x1"]) / self.manager.cell_width
                )

            else:
                # Snap entire task
                grid_row = round(task["y1"] / self.manager.task_height)
                grid_col = round(task["x1"] / self.manager.cell_width)

                new_x1 = grid_col * self.manager.cell_width
                new_y1 = grid_row * self.manager.task_height
                new_x2 = new_x1 + task["duration"] * self.manager.cell_width
                new_y2 = new_y1 + self.manager.task_height

                # Keep task within bounds
                if grid_row >= self.manager.max_tasks:
                    grid_row = self.manager.max_tasks - 1
                    new_y1 = grid_row * self.manager.task_height
                    new_y2 = new_y1 + self.manager.task_height

                if grid_row < 0:
                    grid_row = 0
                    new_y1 = 0
                    new_y2 = self.manager.task_height

                if grid_col < 0:
                    grid_col = 0
                    new_x1 = 0
                    new_x2 = new_x1 + task["duration"] * self.manager.cell_width

                if grid_col + task["duration"] > self.manager.days:
                    grid_col = self.manager.days - task["duration"]
                    new_x1 = grid_col * self.manager.cell_width
                    new_x2 = new_x1 + task["duration"] * self.manager.cell_width

                # Update visuals
                self.manager.task_canvas.coords(
                    task["box"], new_x1, new_y1, new_x2, new_y2
                )
                self.manager.task_canvas.coords(
                    task["left_edge"], new_x1, new_y1, new_x1, new_y2
                )
                self.manager.task_canvas.coords(
                    task["right_edge"], new_x2, new_y1, new_x2, new_y2
                )
                self.manager.task_canvas.coords(
                    task["text"], (new_x1 + new_x2) / 2, (new_y1 + new_y2) / 2
                )

                # Update stored coordinates
                task["x1"], task["y1"] = new_x1, new_y1
                task["x2"], task["y2"] = new_x2, new_y2
                task["row"], task["col"] = grid_row, grid_col

            # Update text position
            self.manager.task_canvas.coords(
                task["text"],
                (task["x1"] + task["x2"]) / 2,
                (task["y1"] + task["y2"]) / 2,
            )

            # Reset selection
            self.manager.selected_task = None
            self.manager.resize_edge = None

        elif self.manager.new_task_in_progress:  # New task creation
            # Get the start and end columns
            start_col, row = self.manager.new_task_start
            end_col = max(
                0, min(self.manager.days - 1, int(canvas_x / self.manager.cell_width))
            )

            # Determine the left column and duration
            left_col = min(start_col, end_col)
            right_col = max(start_col, end_col)
            duration = right_col - left_col + 1

            # Only create task if it has a valid size
            if duration >= 1:
                # Create new task
                task_name = simpledialog.askstring("New Task", "Enter task name:")
                if task_name:
                    # Create a new task dictionary
                    new_task = {
                        "row": row,
                        "col": left_col,
                        "duration": duration,
                        "description": task_name,
                        "resources": [],  # Default empty resources
                    }

                    # Add to tasks list
                    self.manager.tasks.append(new_task)

                    # Draw the new task
                    self.manager.ui.draw_task(new_task)

                    # Prompt for resources
                    self.edit_task_resources(new_task)

            # Remove the rubberband
            if self.manager.rubberband:
                self.manager.task_canvas.delete(self.manager.rubberband)
                self.manager.rubberband = None

            # Reset new task flags
            self.manager.new_task_in_progress = False
            self.manager.new_task_start = None

        # Update resource loading
        self.calculate_resource_loading()

    def on_right_click(self, event):
        """Handle right-click to show context menu"""
        x, y = event.x, event.y

        # Convert canvas coordinates to account for scrolling
        canvas_x = self.manager.task_canvas.canvasx(x)
        canvas_y = self.manager.task_canvas.canvasy(y)

        # Check if right-clicking on a task
        for task in self.manager.tasks:
            if "x1" not in task:
                continue

            if (
                task["x1"] < canvas_x < task["x2"]
                and task["y1"] < canvas_y < task["y2"]
            ):
                self.manager.selected_task = task
                # Show context menu
                self.manager.context_menu.post(event.x_root, event.y_root)
                return

    def edit_task_name(self, task=None):
        """Edit the name of the selected task"""
        if task is None:
            task = self.manager.selected_task

        if task:
            new_name = simpledialog.askstring(
                "Edit Task Name",
                "Enter new task name:",
                initialvalue=task["description"],
            )
            if new_name:
                # Update the task description
                task["description"] = new_name

                # Update the displayed text
                if "text" in task:
                    self.manager.task_canvas.itemconfig(task["text"], text=new_name)

    def edit_task_url(self, task=None):
        """Edit the url of the selected task"""
        if task is None:
            task = self.manager.selected_task

        if task:
            # Ensure the task has a 'url' key with a default blank value
            task.setdefault("url", "")
            new_url = simpledialog.askstring(
                "Edit Task URL",
                "Enter new task URL:",
                initialvalue=task["url"],
            )
            if new_url is not None:
                # Update the task description
                task["url"] = new_url

                # Update the displayed text
                if "url" in task:
                    self.manager.task_canvas.itemconfig(task["url"], text=new_url)

    def edit_task_resources(self, task=None):
        """Edit resources for the selected task"""
        if task is None:
            task = self.manager.selected_task

        if task:
            # Create a dialog for resource selection
            dialog = tk.Toplevel(self.manager.root)
            dialog.title("Edit Task Resources")
            dialog.geometry("300x200")
            dialog.transient(self.manager.root)
            dialog.grab_set()

            # Track selected resources
            resource_vars = {}

            # Create checkboxes for each resource
            tk.Label(dialog, text="Select resources for this task:").pack(pady=5)

            for resource in self.manager.resources:
                var = tk.BooleanVar(value=(resource in task["resources"]))
                resource_vars[resource] = var
                tk.Checkbutton(dialog, text=resource, variable=var).pack(
                    anchor="w", padx=20
                )

            # Function to save selection and close dialog
            def save_resources():
                task["resources"] = [r for r, v in resource_vars.items() if v.get()]
                dialog.destroy()
                self.calculate_resource_loading()

            # Add Save button
            tk.Button(dialog, text="Save", command=save_resources).pack(pady=10)

            # Center the dialog on the main window
            dialog.update_idletasks()
            x = (
                self.manager.root.winfo_x()
                + (self.manager.root.winfo_width() - dialog.winfo_width()) // 2
            )
            y = (
                self.manager.root.winfo_y()
                + (self.manager.root.winfo_height() - dialog.winfo_height()) // 2
            )
            dialog.geometry(f"+{x}+{y}")

    def delete_task(self):
        """Delete the selected task"""
        if self.manager.selected_task:
            # Remove task canvas items
            for key in ["box", "left_edge", "right_edge", "text"]:
                if key in self.manager.selected_task:
                    self.manager.task_canvas.delete(self.manager.selected_task[key])

            # Remove from tasks list
            self.manager.tasks.remove(self.manager.selected_task)
            self.manager.selected_task = None

            # Update resource loading
            self.calculate_resource_loading()

    def add_resource(self):
        """Add a new resource to the project"""
        resource_name = simpledialog.askstring(
            "Add Resource", "Enter new resource name:"
        )
        if resource_name and resource_name not in self.manager.resources:
            self.manager.resources.append(resource_name)
            self.manager.ui.draw_resource_grid()
            self.calculate_resource_loading()

    def edit_resources(self):
        """Edit the list of resources"""
        # Create a dialog for resource editing
        dialog = tk.Toplevel(self.manager.root)
        dialog.title("Edit Resources")
        dialog.geometry("400x300")
        dialog.transient(self.manager.root)
        dialog.grab_set()

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
        for resource in self.manager.resources:
            resource_listbox.insert(tk.END, resource)

        # Create buttons for actions
        button_frame = tk.Frame(dialog)
        button_frame.pack(fill=tk.X, padx=10, pady=5)

        # Define button actions
        def add_resource_from_dialog():
            resource_name = simpledialog.askstring(
                "Add Resource", "Enter new resource name:", parent=dialog
            )
            if resource_name and resource_name not in self.manager.resources:
                self.manager.resources.append(resource_name)
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
                for task in self.manager.tasks:
                    if resource in task["resources"]:
                        used_by_tasks.append(task["description"])

                if used_by_tasks:
                    # Resource is in use - ask what to do
                    message = f"Resource '{resource}' is used by {len(used_by_tasks)} tasks. Remove it from tasks too?"
                    if messagebox.askyesno("Resource in Use", message, parent=dialog):
                        # Remove from tasks
                        for task in self.manager.tasks:
                            if resource in task["resources"]:
                                task["resources"].remove(resource)
                    else:
                        # Cancel deletion
                        return

                # Remove the resource
                self.manager.resources.remove(resource)
                resource_listbox.delete(index)

        def save_resources():
            # Apply changes and close dialog
            dialog.destroy()
            # Redraw grids to reflect changes
            self.manager.ui.draw_resource_grid()
            self.calculate_resource_loading()

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

    def edit_project_settings(self):
        """Edit project settings like number of days"""
        # Create a dialog for project settings
        dialog = tk.Toplevel(self.manager.root)
        dialog.title("Project Settings")
        dialog.geometry("300x150")
        dialog.transient(self.manager.root)
        dialog.grab_set()

        # Create form fields
        settings_frame = tk.Frame(dialog)
        settings_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Days setting
        tk.Label(settings_frame, text="Number of Days:").grid(
            row=0, column=0, sticky="w", pady=5
        )
        days_var = tk.IntVar(value=self.manager.days)
        days_entry = tk.Entry(settings_frame, textvariable=days_var, width=10)
        days_entry.grid(row=0, column=1, sticky="w", pady=5)

        # Max tasks setting
        tk.Label(settings_frame, text="Maximum Tasks:").grid(
            row=1, column=0, sticky="w", pady=5
        )
        max_tasks_var = tk.IntVar(value=self.manager.max_tasks)
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
                for task in self.manager.tasks:
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
                self.manager.days = new_days
                self.manager.max_tasks = new_max_tasks

                # Update the UI
                self.manager.ui.draw_timeline()
                self.manager.ui.draw_task_grid()
                self.manager.ui.draw_resource_grid()
                self.calculate_resource_loading()

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
