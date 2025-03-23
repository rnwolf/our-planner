import tkinter as tk
from tkinter import simpledialog, messagebox
import math


class FloatEntryDialog(simpledialog.Dialog):
    """Custom dialog for entering float values."""

    def __init__(
        self, parent, title, prompt, initialvalue=None, minvalue=0.0, maxvalue=None
    ):
        self.prompt = prompt
        self.initialvalue = initialvalue
        self.minvalue = minvalue
        self.maxvalue = maxvalue
        self.result = None
        super().__init__(parent, title)

    def body(self, master):
        tk.Label(master, text=self.prompt).grid(
            row=0, column=0, padx=5, pady=5, sticky="w"
        )
        self.entry = tk.Entry(master)
        self.entry.grid(row=0, column=1, padx=5, pady=5, sticky="we")
        if self.initialvalue is not None:
            self.entry.insert(0, str(self.initialvalue))
        self.entry.selection_range(0, tk.END)
        return self.entry

    def validate(self):
        try:
            value = float(self.entry.get())
            if self.minvalue is not None and value < self.minvalue:
                messagebox.showerror(
                    "Error", f"Value must be at least {self.minvalue}."
                )
                return False
            if self.maxvalue is not None and value > self.maxvalue:
                messagebox.showerror(
                    "Error", f"Value must be no greater than {self.maxvalue}."
                )
                return False
            self.result = value
            return True
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid number.")
            return False


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
        """Edit resources for the selected task with fractional allocations"""
        if task is None:
            task = self.controller.selected_task

        if task:
            # Create a dialog for resource selection
            dialog = tk.Toplevel(self.controller.root)
            dialog.title("Edit Task Resources")
            dialog.geometry("300x400")
            dialog.transient(self.controller.root)
            dialog.grab_set()

            # Create a frame with scrollbar for the resource list
            resource_frame = tk.Frame(dialog)
            resource_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # Add scrollbar
            scrollbar = tk.Scrollbar(resource_frame)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            # Create a canvas to hold the resource list
            canvas = tk.Canvas(resource_frame, yscrollcommand=scrollbar.set)
            canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.config(command=canvas.yview)

            # Frame inside canvas for resources
            inner_frame = tk.Frame(canvas)
            canvas.create_window((0, 0), window=inner_frame, anchor="nw")

            # Label for the dialog
            tk.Label(
                inner_frame,
                text="Specify resource allocations:",
                font=("Helvetica", 10, "bold"),
            ).pack(pady=5)

            # Dictionary to store resource allocation entries
            resource_entries = {}

            # Create entry fields for each resource
            for i, resource in enumerate(self.model.resources):
                resource_id = resource["id"]
                resource_name = resource["name"]

                # Create a frame for each resource
                resource_row = tk.Frame(inner_frame)
                resource_row.pack(fill=tk.X, padx=5, pady=2)

                # Resource name label
                tk.Label(resource_row, text=resource_name, width=15, anchor="w").pack(
                    side=tk.LEFT
                )

                # Resource allocation entry
                allocation = task["resources"].get(resource_id, 0.0)
                var = tk.StringVar(value=str(allocation) if allocation > 0 else "")
                entry = tk.Entry(resource_row, textvariable=var, width=8)
                entry.pack(side=tk.LEFT, padx=5)

                resource_entries[resource_id] = var

            # Function to save resource allocations and close dialog
            def save_resources():
                # Clear existing resources
                task["resources"] = {}

                # Add new resource allocations
                for resource_id, var in resource_entries.items():
                    try:
                        value = var.get().strip()
                        if value:  # Only process non-empty entries
                            allocation = float(value)
                            if allocation > 0:
                                task["resources"][resource_id] = allocation
                    except ValueError:
                        # Skip invalid entries
                        messagebox.showwarning(
                            "Warning",
                            f"Invalid allocation for resource {self.model.get_resource_by_id(resource_id)['name']}. Skipping.",
                        )

                dialog.destroy()
                self.controller.update_resource_loading()

            # Add buttons
            button_frame = tk.Frame(dialog)
            button_frame.pack(fill=tk.X, pady=10)

            tk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(
                side=tk.RIGHT, padx=5
            )
            tk.Button(button_frame, text="Save", command=save_resources).pack(
                side=tk.RIGHT, padx=5
            )

            # Configure the canvas scrolling
            inner_frame.update_idletasks()
            canvas.config(scrollregion=canvas.bbox("all"))

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
        dialog.geometry(f"500x400+{x}+{y}")
        dialog.transient(parent)
        dialog.grab_set()  # Important: Prevents interaction with the main window

        # Create a frame for the resource list
        list_frame = tk.Frame(dialog)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Create notebook for resource tabs
        notebook = tk.ttk.Notebook(list_frame)
        notebook.pack(fill=tk.BOTH, expand=True)

        # Resources tab
        resources_tab = tk.Frame(notebook)
        notebook.add(resources_tab, text="Resources")

        # Capacity tab
        capacity_tab = tk.Frame(notebook)
        notebook.add(capacity_tab, text="Capacity")

        # ---- Resources Tab ----
        # Scrollbar for the listbox
        scrollbar = tk.Scrollbar(resources_tab)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Create a listbox to display resources
        resource_listbox = tk.Listbox(resources_tab, yscrollcommand=scrollbar.set)
        resource_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=resource_listbox.yview)

        # Populate the listbox
        for resource in self.model.resources:
            resource_listbox.insert(tk.END, f"{resource['id']} - {resource['name']}")

        # ---- Capacity Tab ----
        capacity_frame = tk.Frame(capacity_tab)
        capacity_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Resource selection for capacity editing
        tk.Label(capacity_frame, text="Select resource:").pack(anchor="w", pady=(0, 5))

        # Dropdown for resource selection
        resource_var = tk.StringVar()
        resource_dropdown = tk.ttk.Combobox(
            capacity_frame, textvariable=resource_var, state="readonly"
        )
        resource_dropdown.pack(fill=tk.X, pady=(0, 10))

        # Update dropdown values
        def update_resource_dropdown():
            resources = [f"{r['id']} - {r['name']}" for r in self.model.resources]
            resource_dropdown["values"] = resources
            if resources:
                resource_dropdown.current(0)

        update_resource_dropdown()

        # Frame for capacity editing
        capacity_edit_frame = tk.Frame(capacity_frame)
        capacity_edit_frame.pack(fill=tk.BOTH, expand=True)

        # Canvas for showing capacity over time
        capacity_canvas_frame = tk.Frame(capacity_edit_frame)
        capacity_canvas_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Scrollbar for canvas
        capacity_scrollbar = tk.Scrollbar(capacity_canvas_frame, orient="horizontal")
        capacity_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)

        capacity_canvas = tk.Canvas(
            capacity_canvas_frame,
            height=100,
            xscrollcommand=capacity_scrollbar.set,
            bg="white",
        )
        capacity_canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        capacity_scrollbar.config(command=capacity_canvas.xview)

        # Frame for capacity editing controls
        control_frame = tk.Frame(capacity_frame)
        control_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=10)

        # Entry fields for capacity editing
        tk.Label(control_frame, text="Day:").grid(row=0, column=0, padx=5)
        day_var = tk.StringVar()
        day_entry = tk.Entry(control_frame, textvariable=day_var, width=5)
        day_entry.grid(row=0, column=1, padx=5)

        tk.Label(control_frame, text="To:").grid(row=0, column=2, padx=5)
        end_day_var = tk.StringVar()
        end_day_entry = tk.Entry(control_frame, textvariable=end_day_var, width=5)
        end_day_entry.grid(row=0, column=3, padx=5)

        tk.Label(control_frame, text="Capacity:").grid(row=0, column=4, padx=5)
        capacity_var = tk.StringVar()
        capacity_entry = tk.Entry(control_frame, textvariable=capacity_var, width=5)
        capacity_entry.grid(row=0, column=5, padx=5)

        # Function to draw capacity chart
        def draw_capacity_chart():
            capacity_canvas.delete("all")

            selected = resource_dropdown.get()
            if not selected:
                return

            resource_id = int(selected.split(" - ")[0])
            resource = self.model.get_resource_by_id(resource_id)

            if not resource:
                return

            # Calculate dimensions
            cell_width = 30
            canvas_width = self.model.days * cell_width
            canvas_height = 100

            # Configure canvas
            capacity_canvas.config(scrollregion=(0, 0, canvas_width, canvas_height))

            # Draw day numbers
            for i in range(self.model.days):
                capacity_canvas.create_text(
                    i * cell_width + cell_width / 2,
                    15,
                    text=str(i + 1),
                    font=("Arial", 8),
                )

            # Draw capacity bars
            max_capacity = max(resource["capacity"]) if resource["capacity"] else 1.0
            bar_height_factor = 60 / max_capacity  # Scale to fit in canvas

            for i, cap in enumerate(resource["capacity"]):
                if i >= self.model.days:
                    break

                bar_height = cap * bar_height_factor
                x1 = i * cell_width + 5
                y1 = canvas_height - 20 - bar_height
                x2 = (i + 1) * cell_width - 5
                y2 = canvas_height - 20

                capacity_canvas.create_rectangle(
                    x1, y1, x2, y2, fill="green", outline="darkgreen"
                )

                # Capacity value
                capacity_canvas.create_text(
                    i * cell_width + cell_width / 2,
                    canvas_height - 20 - bar_height - 10,
                    text=str(cap),
                    font=("Arial", 8),
                )

        # Event handler for resource selection
        def on_resource_select(event):
            draw_capacity_chart()

        resource_dropdown.bind("<<ComboboxSelected>>", on_resource_select)

        # Function to update capacity
        def update_capacity():
            selected = resource_dropdown.get()
            if not selected:
                messagebox.showwarning("Warning", "Please select a resource.")
                return

            resource_id = int(selected.split(" - ")[0])

            try:
                # Check if range or single day
                day = int(day_var.get())

                # Validate day
                if day < 1 or day > self.model.days:
                    messagebox.showwarning(
                        "Warning", f"Day must be between 1 and {self.model.days}."
                    )
                    return

                # Check for end day (range)
                if end_day_var.get().strip():
                    end_day = int(end_day_var.get())

                    # Validate end day
                    if end_day < day or end_day > self.model.days:
                        messagebox.showwarning(
                            "Warning",
                            f"End day must be between {day} and {self.model.days}.",
                        )
                        return

                    # Get capacity
                    capacity = float(capacity_var.get())
                    if capacity < 0:
                        messagebox.showwarning(
                            "Warning", "Capacity cannot be negative."
                        )
                        return

                    # Update capacity for range
                    self.model.update_resource_capacity_range(
                        resource_id, day - 1, end_day, capacity
                    )
                    messagebox.showinfo(
                        "Success", f"Capacity updated for days {day} to {end_day}."
                    )

                else:
                    # Single day update
                    capacity = float(capacity_var.get())
                    if capacity < 0:
                        messagebox.showwarning(
                            "Warning", "Capacity cannot be negative."
                        )
                        return

                    # Update capacity
                    self.model.update_resource_capacity(resource_id, day - 1, capacity)
                    messagebox.showinfo("Success", f"Capacity updated for day {day}.")

                # Redraw capacity chart
                draw_capacity_chart()

            except ValueError:
                messagebox.showwarning("Warning", "Please enter valid numbers.")
                return

        # Update capacity button
        update_button = tk.Button(
            control_frame, text="Update Capacity", command=update_capacity
        )
        update_button.grid(row=0, column=6, padx=10)

        # Create buttons for actions on resources tab
        button_frame = tk.Frame(resources_tab)
        button_frame.pack(fill=tk.X, padx=10, pady=5)

        # Define button actions for resources
        def add_resource_from_dialog():
            resource_name = simpledialog.askstring(
                "Add Resource", "Enter new resource name:", parent=dialog
            )
            if resource_name and not self.model.get_resource_by_name(resource_name):
                self.model.add_resource(resource_name)
                # Refresh the listbox
                resource_listbox.delete(0, tk.END)
                for resource in self.model.resources:
                    resource_listbox.insert(
                        tk.END, f"{resource['id']} - {resource['name']}"
                    )

        def remove_selected_resource():
            selected_indices = resource_listbox.curselection()
            if not selected_indices:
                return

            # Get the resource to remove
            index = selected_indices[0]
            resource_text = resource_listbox.get(index)
            resource_id = int(resource_text.split(" - ")[0])
            resource = self.model.get_resource_by_id(resource_id)

            if resource:
                # Confirm deletion
                if messagebox.askyesno(
                    "Confirm Delete",
                    f"Delete resource '{resource['name']}'?",
                    parent=dialog,
                ):
                    # Check if resource is used by any tasks
                    used_by_tasks = []
                    for task in self.model.tasks:
                        if resource_id in task["resources"]:
                            used_by_tasks.append(task["description"])

                    if used_by_tasks:
                        # Resource is in use - ask what to do
                        message = f"Resource '{resource['name']}' is used by {len(used_by_tasks)} tasks. Remove it from tasks too?"
                        if messagebox.askyesno(
                            "Resource in Use", message, parent=dialog
                        ):
                            # Remove resource using model method (will remove from tasks too)
                            self.model.remove_resource(resource_id)
                            resource_listbox.delete(index)
                        else:
                            # Cancel deletion
                            return
                    else:
                        # Remove the resource
                        self.model.remove_resource(resource_id)
                        resource_listbox.delete(index)

        def rename_selected_resource():
            selected_indices = resource_listbox.curselection()
            if not selected_indices:
                return

            # Get the resource to rename
            index = selected_indices[0]
            resource_text = resource_listbox.get(index)
            resource_id = int(resource_text.split(" - ")[0])
            resource = self.model.get_resource_by_id(resource_id)

            if resource:
                new_name = simpledialog.askstring(
                    "Rename Resource",
                    "Enter new resource name:",
                    initialvalue=resource["name"],
                    parent=dialog,
                )
                if new_name and new_name != resource["name"]:
                    if self.model.update_resource_name(resource_id, new_name):
                        # Update the listbox
                        resource_listbox.delete(index)
                        resource_listbox.insert(index, f"{resource_id} - {new_name}")
                        resource_listbox.selection_set(index)
                    else:
                        messagebox.showwarning(
                            "Warning", "A resource with this name already exists."
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

                # Update resource capacities to match new days if needed
                for resource in self.model.resources:
                    if len(resource["capacity"]) < new_days:
                        # Extend capacities with default values
                        resource["capacity"].extend(
                            [1.0] * (new_days - len(resource["capacity"]))
                        )
                    elif len(resource["capacity"]) > new_days:
                        # Truncate capacities
                        resource["capacity"] = resource["capacity"][:new_days]

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
                        (ui_elements["y1"] + ui_elements["y2"]) / 2 - 8,
                    )

                    # Update resource text position if it exists
                    if ui_elements.get("resource_text"):
                        self.controller.task_canvas.coords(
                            ui_elements["resource_text"],
                            (ui_elements["x1"] + ui_elements["x2"]) / 2,
                            (ui_elements["y1"] + ui_elements["y2"]) / 2 + 8,
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
                        (ui_elements["y1"] + ui_elements["y2"]) / 2 - 8,
                    )

                    # Update resource text position if it exists
                    if ui_elements.get("resource_text"):
                        self.controller.task_canvas.coords(
                            ui_elements["resource_text"],
                            (ui_elements["x1"] + ui_elements["x2"]) / 2,
                            (ui_elements["y1"] + ui_elements["y2"]) / 2 + 8,
                        )

            else:
                # Move entire task
                self.controller.task_canvas.move(ui_elements["box"], dx, dy)
                self.controller.task_canvas.move(ui_elements["left_edge"], dx, dy)
                self.controller.task_canvas.move(ui_elements["right_edge"], dx, dy)
                self.controller.task_canvas.move(ui_elements["text"], dx, dy)

                # Move resource text if it exists
                if ui_elements.get("resource_text"):
                    self.controller.task_canvas.move(
                        ui_elements["resource_text"], dx, dy
                    )

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

                # Update connector position to match the new right edge position
                ui_elements["connector_x"] = new_x2
                self.controller.task_canvas.coords(
                    ui_elements["connector"],
                    new_x2 - 5,
                    ui_elements["connector_y"] - 5,
                    new_x2 + 5,
                    ui_elements["connector_y"] + 5,
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

                # Update text positions
                self.controller.task_canvas.coords(
                    ui_elements["text"],
                    (new_x1 + new_x2) / 2,
                    (new_y1 + new_y2) / 2
                    - (8 if ui_elements.get("resource_text") else 0),
                )

                # Update resource text position if it exists
                if ui_elements.get("resource_text"):
                    self.controller.task_canvas.coords(
                        ui_elements["resource_text"],
                        (new_x1 + new_x2) / 2,
                        (new_y1 + new_y2) / 2 + 8,
                    )

                # Collision detection and task shifting
                x1, y1, x2, y2 = new_x1, new_y1, new_x2, new_y2
                self.handle_task_collisions(task, new_x1, new_y1, new_x2, new_y2)

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

            # Call handle_task_collisions with correct coordinates based on operation type
            if self.controller.resize_edge == "left":
                x1, y1, x2, y2 = (
                    ui_elements["x1"],
                    ui_elements["y1"],
                    ui_elements["x2"],
                    ui_elements["y2"],
                )
                self.handle_task_collisions(task, x1, y1, x2, y2)
            elif self.controller.resize_edge == "right":
                x1, y1, x2, y2 = (
                    ui_elements["x1"],
                    ui_elements["y1"],
                    ui_elements["x2"],
                    ui_elements["y2"],
                )
                self.handle_task_collisions(task, x1, y1, x2, y2)
            else:  # Move operation
                self.handle_task_collisions(task, new_x1, new_y1, new_x2, new_y2)

            # Update text position
            self.controller.task_canvas.coords(
                ui_elements["text"],
                (ui_elements["x1"] + ui_elements["x2"]) / 2,
                (ui_elements["y1"] + ui_elements["y2"]) / 2 - 8,
            )

            # Update resource text position if it exists
            if ui_elements.get("resource_text"):
                self.controller.task_canvas.coords(
                    ui_elements["resource_text"],
                    (ui_elements["x1"] + ui_elements["x2"]) / 2,
                    (ui_elements["y1"] + ui_elements["y2"]) / 2 + 8,
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
                    # Create a new task in the model with empty resources dictionary
                    new_task = self.model.add_task(
                        row=row,
                        col=left_col,
                        duration=duration,
                        description=task_name,
                        resources={},
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

    def handle_task_collisions(self, task, x1, y1, x2, y2):
        """Handles collisions between tasks, shifting existing tasks as needed."""
        # Keep track of which tasks have been processed to avoid infinite loops
        processed_tasks = set([task["task_id"]])

        # Continue shifting tasks until no more collisions are detected
        while True:
            # Find all tasks that need to be shifted in this iteration
            tasks_to_shift = []

            for other_task in self.model.tasks:
                # Skip the original task and already processed tasks
                if other_task["task_id"] in processed_tasks:
                    continue

                # Get UI coordinates for the other task
                other_x1, other_y1, other_x2, other_y2 = (
                    self.controller.get_task_ui_coordinates(other_task)
                )

                # Check for overlap (same row and overlapping columns)
                if (
                    x1 < other_x2
                    and x2 > other_x1
                    and y1 < other_y2
                    and y2 > other_y1
                    and other_task["row"] == task["row"]
                ):
                    tasks_to_shift.append(
                        (other_task, other_x1, other_y1, other_x2, other_y2)
                    )

            # If no tasks need shifting, we're done
            if not tasks_to_shift:
                break

            # Process all tasks that need shifting in this iteration
            for other_task, other_x1, other_y1, other_x2, other_y2 in tasks_to_shift:
                # Mark this task as processed
                processed_tasks.add(other_task["task_id"])

                # Calculate shift amount (move past the right edge of the current task)
                shift_amount = x2 - other_x1 + 5  # Small buffer

                # Calculate new column position
                grid_col = max(
                    0, (other_x1 + shift_amount) // self.controller.cell_width
                )

                # Ensure task stays within bounds
                if grid_col + other_task["duration"] > self.model.days:
                    grid_col = self.model.days - other_task["duration"]

                # Update the model
                other_task["col"] = grid_col

                # Update UI position
                self.controller.ui.update_task_ui(other_task)

                # For the next iteration, this shifted task becomes the one that might cause collisions
                x1 = grid_col * self.controller.cell_width
                x2 = x1 + other_task["duration"] * self.controller.cell_width
                y1 = other_y1
                y2 = other_y2
                task = other_task

        # Redraw dependencies after all shifts are complete
        self.controller.ui.draw_dependencies()
