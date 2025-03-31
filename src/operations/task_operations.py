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

        # Keep track of selection rectangle for multi-select
        self.selection_rect = None
        self.selection_start_x = None
        self.selection_start_y = None

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

    def create_capacity_tab(self, capacity_tab, resource_dropdown):
        """Create an improved capacity tab with vertical scrollable list."""
        capacity_frame = tk.Frame(capacity_tab)
        capacity_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Resource selection for capacity editing
        tk.Label(capacity_frame, text="Select resource:").pack(anchor="w", pady=(0, 5))

        # Use the existing resource dropdown
        resource_dropdown.pack(fill=tk.X, pady=(0, 10))

        # Create main content frame with left and right sections
        content_frame = tk.Frame(capacity_frame)
        content_frame.pack(fill=tk.BOTH, expand=True)

        # ======= Left section: Vertical scrollable capacity list =======
        list_frame = tk.Frame(content_frame)
        list_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        tk.Label(list_frame, text="Capacity by Day").pack(anchor="w", pady=(0, 5))

        # Create frame for capacity list with headers
        headers_frame = tk.Frame(list_frame)
        headers_frame.pack(fill=tk.X, pady=(0, 5))

        # Create headers
        tk.Label(
            headers_frame, text="Index", width=8, anchor="w", font=("Arial", 10, "bold")
        ).pack(side=tk.LEFT)
        tk.Label(
            headers_frame, text="Date", width=15, anchor="w", font=("Arial", 10, "bold")
        ).pack(side=tk.LEFT)
        tk.Label(
            headers_frame,
            text="Capacity",
            width=10,
            anchor="w",
            font=("Arial", 10, "bold"),
        ).pack(side=tk.LEFT)

        # Create scrollable capacity list
        list_container = tk.Frame(list_frame)
        list_container.pack(fill=tk.BOTH, expand=True)

        capacity_scroll = tk.Scrollbar(list_container, orient="vertical")
        capacity_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        capacity_canvas = tk.Canvas(
            list_container, yscrollcommand=capacity_scroll.set, highlightthickness=0
        )
        capacity_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        capacity_scroll.config(command=capacity_canvas.yview)

        # Create a frame inside the canvas for the capacity items
        capacity_list_frame = tk.Frame(capacity_canvas)
        capacity_canvas.create_window(
            (0, 0), window=capacity_list_frame, anchor="nw", tags="capacity_frame"
        )

        # Function to update canvas scroll region when the list changes
        def update_scrollregion(event):
            capacity_canvas.configure(scrollregion=capacity_canvas.bbox("all"))

        capacity_list_frame.bind("<Configure>", update_scrollregion)
        capacity_canvas.bind(
            "<Configure>",
            lambda e: capacity_canvas.itemconfig("capacity_frame", width=e.width),
        )

        # ======= Right section: Capacity edit controls =======
        control_frame = tk.Frame(content_frame)
        control_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))

        # === Index-based capacity editing ===
        index_frame = tk.LabelFrame(
            control_frame, text="Set Capacity by Index", padx=10, pady=10
        )
        index_frame.pack(fill=tk.X, pady=(0, 15))

        # Day range
        day_frame = tk.Frame(index_frame)
        day_frame.pack(fill=tk.X, pady=5)

        tk.Label(day_frame, text="Day Index:").grid(row=0, column=0, padx=5, sticky="w")
        day_var = tk.StringVar()
        day_entry = tk.Entry(day_frame, textvariable=day_var, width=5)
        day_entry.grid(row=0, column=1, padx=5)

        tk.Label(day_frame, text="To Index:").grid(row=0, column=2, padx=5)
        end_day_var = tk.StringVar()
        end_day_entry = tk.Entry(day_frame, textvariable=end_day_var, width=5)
        end_day_entry.grid(row=0, column=3, padx=5)

        # Capacity entry
        capacity_frame = tk.Frame(index_frame)
        capacity_frame.pack(fill=tk.X, pady=5)

        tk.Label(capacity_frame, text="Capacity:").pack(side=tk.LEFT, padx=5)
        capacity_var = tk.StringVar()
        capacity_entry = tk.Entry(capacity_frame, textvariable=capacity_var, width=5)
        capacity_entry.pack(side=tk.LEFT, padx=5)

        # Update button
        update_button = tk.Button(
            index_frame, text="Update Capacity", command=lambda: update_capacity()
        )
        update_button.pack(anchor="e", pady=(5, 0))

        # === Date-based capacity editing ===
        date_frame = tk.LabelFrame(
            control_frame, text="Set Capacity by Date", padx=10, pady=10
        )
        date_frame.pack(fill=tk.X, pady=(0, 15))

        # Try to import tkcalendar
        try:
            from tkcalendar import DateEntry

            has_calendar = True
        except ImportError:
            has_calendar = False

        # Start date
        start_date_frame = tk.Frame(date_frame)
        start_date_frame.pack(fill=tk.X, pady=5)

        tk.Label(start_date_frame, text="Start Date:").pack(side=tk.LEFT, padx=5)

        if has_calendar:
            start_date_var = tk.StringVar()
            start_date_picker = DateEntry(
                start_date_frame,
                width=12,
                background="darkblue",
                foreground="white",
                borderwidth=2,
                date_pattern="yyyy-mm-dd",  # Specify YYYY-MM-DD format
                textvariable=start_date_var,
            )
            start_date_picker.pack(side=tk.LEFT, padx=5)
        else:
            start_date_var = tk.StringVar()
            start_date_entry = tk.Entry(
                start_date_frame, textvariable=start_date_var, width=10
            )
            start_date_entry.pack(side=tk.LEFT, padx=5)
            tk.Label(start_date_frame, text="(YYYY-MM-DD)").pack(side=tk.LEFT)

        # End date
        end_date_frame = tk.Frame(date_frame)
        end_date_frame.pack(fill=tk.X, pady=5)

        tk.Label(end_date_frame, text="End Date:").pack(side=tk.LEFT, padx=5)

        if has_calendar:
            end_date_var = tk.StringVar()
            end_date_picker = DateEntry(
                end_date_frame,
                width=12,
                background="darkblue",
                foreground="white",
                borderwidth=2,
                date_pattern="yyyy-mm-dd",  # Specify YYYY-MM-DD format
                textvariable=end_date_var,
            )
            end_date_picker.pack(side=tk.LEFT, padx=5)
        else:
            end_date_var = tk.StringVar()
            end_date_entry = tk.Entry(
                end_date_frame, textvariable=end_date_var, width=10
            )
            end_date_entry.pack(side=tk.LEFT, padx=5)
            tk.Label(end_date_frame, text="(YYYY-MM-DD)").pack(side=tk.LEFT)

        # Capacity for date range
        date_capacity_frame = tk.Frame(date_frame)
        date_capacity_frame.pack(fill=tk.X, pady=5)

        tk.Label(date_capacity_frame, text="Capacity:").pack(side=tk.LEFT, padx=5)
        date_capacity_var = tk.StringVar()
        date_capacity_entry = tk.Entry(
            date_capacity_frame, textvariable=date_capacity_var, width=5
        )
        date_capacity_entry.pack(side=tk.LEFT, padx=5)

        # Update button for date range
        update_date_button = tk.Button(
            date_frame,
            text="Update Capacity",
            command=lambda: update_capacity_by_date(),
        )
        update_date_button.pack(anchor="e", pady=(5, 0))

        # Functions for drawing and updating the capacity list
        def draw_capacity_list(resource_id):
            # Clear existing items
            for widget in capacity_list_frame.winfo_children():
                widget.destroy()

            resource = self.model.get_resource_by_id(resource_id)
            if not resource:
                return

            # Create capacity list entries
            for i, capacity in enumerate(resource["capacity"]):
                if i >= self.model.days:
                    break

                date = self.model.get_date_for_day(i)
                date_str = date.strftime("%Y-%m-%d")

                row_frame = tk.Frame(capacity_list_frame)
                row_frame.pack(fill=tk.X, pady=1)

                # Set alternating row color
                if i % 2 == 0:
                    row_frame.configure(bg="#f0f0f0")
                    bg_color = "#f0f0f0"
                else:
                    row_frame.configure(bg="#ffffff")
                    bg_color = "#ffffff"

                # Day index
                day_label = tk.Label(
                    row_frame, text=str(i), width=8, anchor="w", bg=bg_color
                )
                day_label.pack(side=tk.LEFT)

                # Date
                date_label = tk.Label(
                    row_frame, text=date_str, width=15, anchor="w", bg=bg_color
                )
                date_label.pack(side=tk.LEFT)

                # Capacity
                capacity_label = tk.Label(
                    row_frame, text=str(capacity), width=10, anchor="w", bg=bg_color
                )
                capacity_label.pack(side=tk.LEFT)

        # Function to update capacity by index
        def update_capacity():
            selected = resource_dropdown.get()
            if not selected:
                tk.messagebox.showwarning("Warning", "Please select a resource.")
                return

            resource_id = int(selected.split(" - ")[0])

            try:
                # Check if range or single day
                day = int(day_var.get())

                # Validate day
                if day < 0 or day >= self.model.days:
                    tk.messagebox.showwarning(
                        "Warning",
                        f"Day index must be between 0 and {self.model.days - 1}.",
                    )
                    return

                # Check for end day (range)
                if end_day_var.get().strip():
                    end_day = int(end_day_var.get())

                    # Validate end day
                    if end_day < day or end_day >= self.model.days:
                        tk.messagebox.showwarning(
                            "Warning",
                            f"End day index must be between {day} and {self.model.days - 1}.",
                        )
                        return

                    # Get capacity
                    capacity = float(capacity_var.get())
                    if capacity < 0:
                        tk.messagebox.showwarning(
                            "Warning", "Capacity cannot be negative."
                        )
                        return

                    # Update capacity for range
                    for i in range(day, end_day + 1):
                        self.model.update_resource_capacity(resource_id, i, capacity)

                    tk.messagebox.showinfo(
                        "Success", f"Capacity updated for days {day} to {end_day}."
                    )

                else:
                    # Single day update
                    capacity = float(capacity_var.get())
                    if capacity < 0:
                        tk.messagebox.showwarning(
                            "Warning", "Capacity cannot be negative."
                        )
                        return

                    # Update capacity
                    self.model.update_resource_capacity(resource_id, day, capacity)
                    tk.messagebox.showinfo(
                        "Success", f"Capacity updated for day {day}."
                    )

                # Redraw capacity list
                draw_capacity_list(resource_id)

            except ValueError:
                tk.messagebox.showwarning("Warning", "Please enter valid numbers.")
                return

        # Function to update capacity by date
        def update_capacity_by_date():
            selected = resource_dropdown.get()
            if not selected:
                tk.messagebox.showwarning("Warning", "Please select a resource.")
                return

            resource_id = int(selected.split(" - ")[0])

            try:
                # Parse dates
                from datetime import datetime

                start_date_str = start_date_var.get()
                end_date_str = end_date_var.get()

                try:
                    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
                except ValueError:
                    tk.messagebox.showwarning(
                        "Warning", "Start date must be in YYYY-MM-DD format."
                    )
                    return

                # For end date, if not provided, use start date
                if not end_date_str:
                    end_date = start_date
                else:
                    try:
                        end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
                    except ValueError:
                        tk.messagebox.showwarning(
                            "Warning", "End date must be in YYYY-MM-DD format."
                        )
                        return

                # Validate date range
                if end_date < start_date:
                    tk.messagebox.showwarning(
                        "Warning", "End date must be after start date."
                    )
                    return

                # Convert dates to day indices
                start_day = self.model.get_day_for_date(start_date)
                end_day = self.model.get_day_for_date(end_date)

                # Validate indices are within project range
                if start_day < 0 or start_day >= self.model.days:
                    tk.messagebox.showwarning(
                        "Warning", "Start date is outside the project timeline."
                    )
                    return

                if end_day < 0 or end_day >= self.model.days:
                    tk.messagebox.showwarning(
                        "Warning", "End date is outside the project timeline."
                    )
                    return

                # Get capacity
                capacity = float(date_capacity_var.get())
                if capacity < 0:
                    tk.messagebox.showwarning("Warning", "Capacity cannot be negative.")
                    return

                # Update capacity for date range
                for i in range(start_day, end_day + 1):
                    self.model.update_resource_capacity(resource_id, i, capacity)

                tk.messagebox.showinfo(
                    "Success",
                    f"Capacity updated for dates from {start_date_str} to {end_date_str}.",
                )

                # Redraw capacity list
                draw_capacity_list(resource_id)

            except ValueError as e:
                tk.messagebox.showwarning("Warning", f"Error: {str(e)}")
                return

        # Connect events
        def on_resource_select(event):
            """When a resource is selected, update the capacity list."""
            selected = resource_dropdown.get()
            if selected:
                resource_id = int(selected.split(" - ")[0])
                draw_capacity_list(resource_id)

        resource_dropdown.bind("<<ComboboxSelected>>", on_resource_select)

        # Initialize with the first resource if available
        if self.model.resources:
            resource_id = self.model.resources[0]["id"]
            draw_capacity_list(resource_id)

        return capacity_frame, day_var, end_day_var, capacity_var, update_capacity

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

            # Bind ESC key to close dialog
            dialog.bind("<Escape>", lambda e: dialog.destroy())

            # Ensure the dialog gets focus when opened
            dialog.focus_set()

            # Wait for the dialog to be visible before setting focus
            dialog.wait_visibility()

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
        dialog.geometry(f"700x500+{x}+{y}")
        dialog.transient(parent)
        dialog.grab_set()  # Important: Prevents interaction with the main window
        dialog.focus_set()  # Ensure dialog gets focus
        dialog.wait_visibility()  # Wait for dialog to be visible before proceeding

        # Bind ESC key to close dialog
        dialog.bind("<Escape>", lambda e: dialog.destroy())

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
        resource_management_frame = tk.Frame(resources_tab)
        resource_management_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Add a label for instructions
        tk.Label(
            resource_management_frame,
            text="Manage Resources:",
            font=("Helvetica", 10, "bold"),
        ).pack(anchor="w", pady=(0, 10))

        # Create frame for listbox and scrollbar
        listbox_frame = tk.Frame(resource_management_frame)
        listbox_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Scrollbar for the listbox
        scrollbar = tk.Scrollbar(listbox_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Create a listbox to display resources
        resource_listbox = tk.Listbox(
            listbox_frame, yscrollcommand=scrollbar.set, font=("Helvetica", 10)
        )
        resource_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=resource_listbox.yview)

        # Create a frame for resource details editing
        details_frame = tk.Frame(resource_management_frame)
        details_frame.pack(fill=tk.X, pady=10)

        # Resource name editing
        tk.Label(details_frame, text="Resource Name:").grid(
            row=0, column=0, sticky="w", padx=5, pady=5
        )
        resource_name_var = tk.StringVar()
        name_entry = tk.Entry(details_frame, textvariable=resource_name_var, width=30)
        name_entry.grid(row=0, column=1, sticky="w", padx=5, pady=5)

        # Populate the listbox
        def populate_resource_listbox():
            resource_listbox.delete(0, tk.END)
            for resource in self.model.resources:
                resource_listbox.insert(
                    tk.END, f"{resource['id']} - {resource['name']}"
                )

        populate_resource_listbox()

        # Create buttons for actions on resources
        button_frame = tk.Frame(resource_management_frame)
        button_frame.pack(fill=tk.X, pady=10)

        # Function to update selected resource
        def update_selected_resource():
            selected_indices = resource_listbox.curselection()
            if not selected_indices:
                messagebox.showwarning(
                    "No Selection", "Please select a resource to update.", parent=dialog
                )
                return

            # Get the resource to update
            index = selected_indices[0]
            resource_text = resource_listbox.get(index)
            resource_id = int(resource_text.split(" - ")[0])
            resource = self.model.get_resource_by_id(resource_id)

            if resource:
                new_name = resource_name_var.get().strip()
                if not new_name:
                    messagebox.showwarning(
                        "Invalid Name", "Resource name cannot be empty.", parent=dialog
                    )
                    return

                if new_name != resource["name"]:
                    if self.model.update_resource_name(resource_id, new_name):
                        # Update the listbox
                        resource_listbox.delete(index)
                        resource_listbox.insert(index, f"{resource_id} - {new_name}")
                        resource_listbox.selection_set(index)
                        messagebox.showinfo(
                            "Success",
                            f"Resource renamed to '{new_name}'.",
                            parent=dialog,
                        )

                        # Update the resource grid in the main UI
                        self.controller.ui.draw_resource_grid()
                        self.controller.update_resource_loading()
                    else:
                        messagebox.showwarning(
                            "Error",
                            "A resource with this name already exists.",
                            parent=dialog,
                        )

        # Define button actions for resources
        # For the add_resource_from_dialog function:
        def add_resource_from_dialog():
            resource_name = resource_name_var.get().strip()
            if not resource_name:
                messagebox.showwarning(
                    "Invalid Name", "Please enter a resource name.", parent=dialog
                )
                return

            if self.model.get_resource_by_name(resource_name):
                messagebox.showwarning(
                    "Duplicate Name",
                    "A resource with this name already exists.",
                    parent=dialog,
                )
                return

            self.model.add_resource(resource_name)
            # Refresh the listbox
            populate_resource_listbox()
            messagebox.showinfo(
                "Success", f"Resource '{resource_name}' added.", parent=dialog
            )
            resource_name_var.set("")  # Clear the entry field

            # Update the resource grid in the main UI
            self.controller.ui.draw_resource_grid()
            self.controller.update_resource_loading()

        # For the remove_selected_resource function:
        def remove_selected_resource():
            selected_indices = resource_listbox.curselection()
            if not selected_indices:
                messagebox.showwarning(
                    "No Selection", "Please select a resource to delete.", parent=dialog
                )
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
                        if (
                            str(resource_id) in task["resources"]
                            or resource_id in task["resources"]
                        ):
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
                            messagebox.showinfo(
                                "Success",
                                f"Resource '{resource['name']}' deleted.",
                                parent=dialog,
                            )

                            # Update the resource grid in the main UI
                            self.controller.ui.draw_resource_grid()
                            self.controller.update_resource_loading()
                        else:
                            # Cancel deletion
                            return
                    else:
                        # Remove the resource
                        self.model.remove_resource(resource_id)
                        resource_listbox.delete(index)
                        messagebox.showinfo(
                            "Success",
                            f"Resource '{resource['name']}' deleted.",
                            parent=dialog,
                        )

                        # Update the resource grid in the main UI
                        self.controller.ui.draw_resource_grid()
                        self.controller.update_resource_loading()

        def on_dialog_close():
            # Update the main UI when dialog closes
            self.controller.ui.draw_resource_grid()
            self.controller.update_resource_loading()
            dialog.destroy()

        def on_resource_select(event):
            """When a resource is selected, populate the name entry field"""
            selected_indices = resource_listbox.curselection()
            if selected_indices:
                index = selected_indices[0]
                resource_text = resource_listbox.get(index)
                resource_id = int(resource_text.split(" - ")[0])
                resource = self.model.get_resource_by_id(resource_id)
                if resource:
                    resource_name_var.set(resource["name"])

        # Bind selection event
        resource_listbox.bind("<<ListboxSelect>>", on_resource_select)

        # Add buttons for resource management
        tk.Button(
            button_frame, text="Add Resource", command=add_resource_from_dialog
        ).pack(side=tk.LEFT, padx=5)
        tk.Button(
            button_frame, text="Update Resource", command=update_selected_resource
        ).pack(side=tk.LEFT, padx=5)
        tk.Button(
            button_frame, text="Remove Resource", command=remove_selected_resource
        ).pack(side=tk.LEFT, padx=5)

        # ---- Capacity Tab ----
        # (Keep the capacity tab functionality as is)
        # ... rest of the capacity tab code from the original method ...
        # #######################
        # capacity_frame = tk.Frame(capacity_tab)
        # capacity_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # # Resource selection for capacity editing
        # tk.Label(capacity_frame, text="Select resource:").pack(anchor="w", pady=(0, 5))

        # # Dropdown for resource selection
        # resource_var = tk.StringVar()
        # resource_dropdown = tk.ttk.Combobox(
        #     capacity_frame, textvariable=resource_var, state="readonly"
        # )
        # resource_dropdown.pack(fill=tk.X, pady=(0, 10))

        # # Update dropdown values
        # def update_resource_dropdown():
        #     resources = [f"{r['id']} - {r['name']}" for r in self.model.resources]
        #     resource_dropdown["values"] = resources
        #     if resources:
        #         resource_dropdown.current(0)

        # update_resource_dropdown()

        # # Frame for capacity editing
        # capacity_edit_frame = tk.Frame(capacity_frame)
        # capacity_edit_frame.pack(fill=tk.BOTH, expand=True)

        # # Canvas for showing capacity over time
        # capacity_canvas_frame = tk.Frame(capacity_edit_frame)
        # capacity_canvas_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # # Scrollbar for canvas
        # capacity_scrollbar = tk.Scrollbar(capacity_canvas_frame, orient="horizontal")
        # capacity_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)

        # capacity_canvas = tk.Canvas(
        #     capacity_canvas_frame,
        #     height=100,
        #     xscrollcommand=capacity_scrollbar.set,
        #     bg="white",
        # )
        # capacity_canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        # capacity_scrollbar.config(command=capacity_canvas.xview)

        # # Frame for capacity editing controls
        # control_frame = tk.Frame(capacity_frame)
        # control_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=10)

        # # Entry fields for capacity editing
        # tk.Label(control_frame, text="Day:").grid(row=0, column=0, padx=5)
        # day_var = tk.StringVar()
        # day_entry = tk.Entry(control_frame, textvariable=day_var, width=5)
        # day_entry.grid(row=0, column=1, padx=5)

        # tk.Label(control_frame, text="To:").grid(row=0, column=2, padx=5)
        # end_day_var = tk.StringVar()
        # end_day_entry = tk.Entry(control_frame, textvariable=end_day_var, width=5)
        # end_day_entry.grid(row=0, column=3, padx=5)

        # tk.Label(control_frame, text="Capacity:").grid(row=0, column=4, padx=5)
        # capacity_var = tk.StringVar()
        # capacity_entry = tk.Entry(control_frame, textvariable=capacity_var, width=5)
        # capacity_entry.grid(row=0, column=5, padx=5)

        # # Function to draw capacity chart
        # def draw_capacity_chart():
        #     capacity_canvas.delete("all")

        #     selected = resource_dropdown.get()
        #     if not selected:
        #         return

        #     resource_id = int(selected.split(" - ")[0])
        #     resource = self.model.get_resource_by_id(resource_id)

        #     if not resource:
        #         return

        #     # Calculate dimensions
        #     cell_width = 30
        #     canvas_width = self.model.days * cell_width
        #     canvas_height = 100

        #     # Configure canvas
        #     capacity_canvas.config(scrollregion=(0, 0, canvas_width, canvas_height))

        #     # Draw day numbers
        #     for i in range(self.model.days):
        #         capacity_canvas.create_text(
        #             i * cell_width + cell_width / 2,
        #             15,
        #             text=str(i + 1),
        #             font=("Arial", 8),
        #         )

        #     # Draw capacity bars
        #     max_capacity = max(resource["capacity"]) if resource["capacity"] else 1.0
        #     bar_height_factor = 60 / max_capacity  # Scale to fit in canvas

        #     for i, cap in enumerate(resource["capacity"]):
        #         if i >= self.model.days:
        #             break

        #         bar_height = cap * bar_height_factor
        #         x1 = i * cell_width + 5
        #         y1 = canvas_height - 20 - bar_height
        #         x2 = (i + 1) * cell_width - 5
        #         y2 = canvas_height - 20

        #         capacity_canvas.create_rectangle(
        #             x1, y1, x2, y2, fill="green", outline="darkgreen"
        #         )

        #         # Capacity value
        #         capacity_canvas.create_text(
        #             i * cell_width + cell_width / 2,
        #             canvas_height - 20 - bar_height - 10,
        #             text=str(cap),
        #             font=("Arial", 8),
        #         )

        # # Event handler for resource selection
        # def on_resource_select(event):
        #     draw_capacity_chart()

        # resource_dropdown.bind("<<ComboboxSelected>>", on_resource_select)

        # # Function to update capacity
        # def update_capacity():
        #     selected = resource_dropdown.get()
        #     if not selected:
        #         messagebox.showwarning("Warning", "Please select a resource.")
        #         return

        #     resource_id = int(selected.split(" - ")[0])

        #     try:
        #         # Check if range or single day
        #         day = int(day_var.get())

        #         # Validate day
        #         if day < 1 or day > self.model.days:
        #             messagebox.showwarning(
        #                 "Warning", f"Day must be between 1 and {self.model.days}."
        #             )
        #             return

        #         # Check for end day (range)
        #         if end_day_var.get().strip():
        #             end_day = int(end_day_var.get())

        #             # Validate end day
        #             if end_day < day or end_day > self.model.days:
        #                 messagebox.showwarning(
        #                     "Warning",
        #                     f"End day must be between {day} and {self.model.days}.",
        #                 )
        #                 return

        #             # Get capacity
        #             capacity = float(capacity_var.get())
        #             if capacity < 0:
        #                 messagebox.showwarning(
        #                     "Warning", "Capacity cannot be negative."
        #                 )
        #                 return

        #             # Update capacity for range
        #             self.model.update_resource_capacity_range(
        #                 resource_id, day - 1, end_day, capacity
        #             )
        #             messagebox.showinfo(
        #                 "Success", f"Capacity updated for days {day} to {end_day}."
        #             )

        #         else:
        #             # Single day update
        #             capacity = float(capacity_var.get())
        #             if capacity < 0:
        #                 messagebox.showwarning(
        #                     "Warning", "Capacity cannot be negative."
        #                 )
        #                 return

        #             # Update capacity
        #             self.model.update_resource_capacity(resource_id, day - 1, capacity)
        #             messagebox.showinfo("Success", f"Capacity updated for day {day}.")

        #         # Redraw capacity chart
        #         draw_capacity_chart()

        #     except ValueError:
        #         messagebox.showwarning("Warning", "Please enter valid numbers.")
        #         return

        # # Update capacity button
        # update_button = tk.Button(
        #     control_frame, text="Update Capacity", command=update_capacity
        # )
        # update_button.grid(row=0, column=6, padx=10)

        ######################################

        # Create the dropdown for resource selection
        resource_var = tk.StringVar()
        resource_dropdown = tk.ttk.Combobox(
            capacity_tab, textvariable=resource_var, state="readonly"
        )

        # Create the capacity tab with our new implementation
        capacity_frame, day_var, end_day_var, capacity_var, update_capacity = (
            self.create_capacity_tab(capacity_tab, resource_dropdown)
        )

        # Update dropdown values
        def update_resource_dropdown():
            resources = [f"{r['id']} - {r['name']}" for r in self.model.resources]
            resource_dropdown["values"] = resources
            if resources:
                resource_dropdown.current(0)

        # Initialize the dropdown
        update_resource_dropdown()

        # Add "Close" button at the bottom
        close_button_frame = tk.Frame(dialog)
        close_button_frame.pack(fill=tk.X, padx=10, pady=10)

        # Get a reference to the Close button
        close_button = tk.Button(
            close_button_frame, text="Close", command=on_dialog_close, width=10
        )
        close_button.pack(side=tk.RIGHT)

        # Bind the Return/Enter key to the dialog globally
        dialog.bind("<Return>", lambda event: handle_enter_key(event))

        # Function to handle Enter key press
        def handle_enter_key(event):
            # Check if the Close button has focus
            if event.widget == close_button:
                on_dialog_close()
            # If in a text entry field, don't trigger close
            elif isinstance(event.widget, tk.Entry):
                return
            # For other widgets like buttons, simulate a click if they have focus
            elif isinstance(event.widget, tk.Button):
                event.widget.invoke()

        # Also update the protocol handler for window close (X button)
        dialog.protocol("WM_DELETE_WINDOW", on_dialog_close)

        # # Draw the initial capacity chart if a resource is selected
        # if self.model.resources:
        #     draw_capacity_chart()

        # Connect the notebook tabs to update functions
        def on_tab_changed(event):
            tab = event.widget.select()
            tab_text = event.widget.tab(tab, "text")
            if tab_text == "Resources":
                # Refresh resource list when switching to resources tab
                populate_resource_listbox()
            elif tab_text == "Capacity":
                # Refresh capacity dropdown when switching to capacity tab
                update_resource_dropdown()
                # Redraw capacity chart
                # draw_capacity_chart()

        notebook.bind("<<NotebookTabChanged>>", on_tab_changed)

    def edit_project_settings(self, parent=None):
        """Edit project settings like number of days and start date"""
        # Create a dialog for project settings
        parent = parent or self.controller.root

        dialog = tk.Toplevel(parent)
        dialog.title("Project Settings")
        # Position the dialog relative to the parent window
        x = parent.winfo_x() + 50
        y = parent.winfo_y() + 50
        dialog.geometry(f"400x250+{x}+{y}")
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

        # Max rows setting
        tk.Label(settings_frame, text="Maximum Rows:").grid(
            row=1, column=0, sticky="w", pady=5
        )
        max_rows_var = tk.IntVar(value=self.model.max_rows)
        max_rows_entry = tk.Entry(settings_frame, textvariable=max_rows_var, width=10)
        max_rows_entry.grid(row=1, column=1, sticky="w", pady=5)

        # Start date setting
        tk.Label(settings_frame, text="Start Date:").grid(
            row=2, column=0, sticky="w", pady=5
        )

        date_frame = tk.Frame(settings_frame)
        date_frame.grid(row=2, column=1, sticky="w", pady=5)

        # Create separate entry fields for year, month, day
        year_var = tk.StringVar(value=str(self.model.start_date.year))
        month_var = tk.StringVar(value=str(self.model.start_date.month))
        day_var = tk.StringVar(value=str(self.model.start_date.day))

        year_entry = tk.Entry(date_frame, textvariable=year_var, width=5)
        year_entry.pack(side=tk.LEFT, padx=(0, 5))
        tk.Label(date_frame, text="-").pack(side=tk.LEFT)

        month_entry = tk.Entry(date_frame, textvariable=month_var, width=3)
        month_entry.pack(side=tk.LEFT, padx=(5, 5))
        tk.Label(date_frame, text="-").pack(side=tk.LEFT)

        day_entry = tk.Entry(date_frame, textvariable=day_var, width=3)
        day_entry.pack(side=tk.LEFT, padx=(5, 0))

        # Date format explanation
        tk.Label(settings_frame, text="Format: YYYY-MM-DD", fg="gray").grid(
            row=3, column=1, sticky="w", pady=(0, 10)
        )

        # Calendar picker button
        def open_calendar_dialog():
            from tkcalendar import Calendar

            try:
                cal_dialog = tk.Toplevel(dialog)
                cal_dialog.title("Select Start Date")
                cal_dialog.geometry(
                    f"+{dialog.winfo_rootx()+50}+{dialog.winfo_rooty()+50}"
                )
                cal_dialog.transient(dialog)
                cal_dialog.grab_set()

                # Create calendar widget initialized with current start date
                cal = Calendar(
                    cal_dialog,
                    selectmode="day",
                    year=int(year_var.get()),
                    month=int(month_var.get()),
                    day=int(day_var.get()),
                )
                cal.pack(padx=10, pady=10)

                def set_date():
                    selected_date = cal.selection_get()
                    year_var.set(str(selected_date.year))
                    month_var.set(str(selected_date.month))
                    day_var.set(str(selected_date.day))
                    cal_dialog.destroy()

                tk.Button(cal_dialog, text="Select", command=set_date).pack(pady=10)
            except ImportError:
                messagebox.showwarning(
                    "Calendar Not Available",
                    "The tkcalendar package is not installed. Please enter the date manually.",
                    parent=dialog,
                )

        tk.Button(
            settings_frame, text="Pick Date...", command=open_calendar_dialog
        ).grid(row=2, column=2, padx=5, pady=5, sticky="w")

        # Button frame
        button_frame = tk.Frame(dialog)
        button_frame.pack(fill=tk.X, pady=10)

        def save_settings():
            try:
                new_days = int(days_var.get())
                new_max_rows = int(max_rows_var.get())

                # Validate days and rows
                if new_days < 1:
                    messagebox.showerror(
                        "Invalid Value",
                        "Number of days must be at least 1.",
                        parent=dialog,
                    )
                    return

                if new_max_rows < 1:
                    messagebox.showerror(
                        "Invalid Value",
                        "Maximum rows must be at least 1.",
                        parent=dialog,
                    )
                    return

                # Validate date
                try:
                    year = int(year_var.get())
                    month = int(month_var.get())
                    day = int(day_var.get())

                    from datetime import datetime

                    new_start_date = datetime(year, month, day)
                except ValueError:
                    messagebox.showerror(
                        "Invalid Date",
                        "Please enter a valid date in format YYYY-MM-DD.",
                        parent=dialog,
                    )
                    return

                # Check if any tasks would be outside the new bounds
                tasks_out_of_bounds = False
                for task in self.model.tasks:
                    if (
                        task["col"] + task["duration"] > new_days
                        or task["row"] >= new_max_rows
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
                self.model.max_rows = new_max_rows
                self.model.start_date = new_start_date

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

        # Track if Ctrl key is pressed for multi-select
        ctrl_pressed = event.state & 0x4  # Check for Control key

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
                task = self.model.get_task(task_id)
                self.controller.selected_task = task

                # If not multi-selecting, clear previous selections
                if not (ctrl_pressed and self.controller.multi_select_mode):
                    self.controller.selected_tasks = [task]
                elif task not in self.controller.selected_tasks:
                    self.controller.selected_tasks.append(task)

                # Update highlighting
                self.controller.ui.highlight_selected_tasks()

                self.controller.resize_edge = "left"
                task_clicked = True
                break

            # Check if clicking on right edge (for right resize)
            if abs(canvas_x - x2) < 5 and y1 < canvas_y < y2:
                task = self.model.get_task(task_id)
                self.controller.selected_task = task

                # If not multi-selecting, clear previous selections
                if not (ctrl_pressed and self.controller.multi_select_mode):
                    self.controller.selected_tasks = [task]
                elif task not in self.controller.selected_tasks:
                    self.controller.selected_tasks.append(task)

                # Update highlighting
                self.controller.ui.highlight_selected_tasks()

                self.controller.resize_edge = "right"
                task_clicked = True
                break

            # Check if clicking on task body (for moving or selecting)
            if x1 < canvas_x < x2 and y1 < canvas_y < y2:
                task = self.model.get_task(task_id)

                # Handle multi-select with Ctrl key
                if ctrl_pressed and self.controller.multi_select_mode:
                    # Toggle task selection without affecting other selected tasks
                    if task in self.controller.selected_tasks:
                        self.controller.selected_tasks.remove(task)
                    else:
                        self.controller.selected_tasks.append(task)

                    # Also update the single selected task
                    self.controller.selected_task = task
                else:
                    # Single task selection - clear previous selections if not Ctrl+click
                    if not ctrl_pressed:
                        self.controller.selected_tasks = [task]
                    else:
                        # Add to multi-select list if not already there
                        if task not in self.controller.selected_tasks:
                            self.controller.selected_tasks.append(task)

                    self.controller.selected_task = task

                # Update highlighting for all tasks
                self.controller.ui.highlight_selected_tasks()

                # Only set resize_edge to None if we're just selecting, not for edge resizing
                self.controller.resize_edge = None
                task_clicked = True
                break

        # If no task was clicked and we're in the grid area, start creating a new task
        if (
            not task_clicked
            and canvas_y >= 0
            and canvas_y <= self.model.max_rows * self.controller.task_height
        ):
            # Clear selections when clicking on empty space
            if not ctrl_pressed:
                self.controller.selected_tasks = []
                self.controller.ui.remove_task_selections()

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
                # Resize from left edge - only affects the single task being resized
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

                    # Update tag text position if it exists
                    if ui_elements.get("tag_text"):
                        self.controller.task_canvas.coords(
                            ui_elements["tag_text"],
                            (ui_elements["x1"] + ui_elements["x2"]) / 2,
                            (ui_elements["y1"] + ui_elements["y2"]) / 2 + 8,
                        )

                    # Update highlight position if it exists
                    if ui_elements.get("highlight"):
                        self.controller.task_canvas.coords(
                            ui_elements["highlight"],
                            ui_elements["x1"] - 2,
                            ui_elements["y1"] - 2,
                            ui_elements["x2"] + 2,
                            ui_elements["y2"] + 2,
                        )

            elif self.controller.resize_edge == "right":
                # Resize from right edge - only affects the single task being resized
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

                    # Update tag text position if it exists
                    if ui_elements.get("tag_text"):
                        self.controller.task_canvas.coords(
                            ui_elements["tag_text"],
                            (ui_elements["x1"] + ui_elements["x2"]) / 2,
                            (ui_elements["y1"] + ui_elements["y2"]) / 2 + 8,
                        )

                    # Update highlight position if it exists
                    if ui_elements.get("highlight"):
                        self.controller.task_canvas.coords(
                            ui_elements["highlight"],
                            ui_elements["x1"] - 2,
                            ui_elements["y1"] - 2,
                            ui_elements["x2"] + 2,
                            ui_elements["y2"] + 2,
                        )

            else:
                # Moving tasks - check if multiple tasks are selected
                if (
                    len(self.controller.selected_tasks) > 1
                    and task in self.controller.selected_tasks
                ):
                    # Move all selected tasks together
                    for selected_task in self.controller.selected_tasks:
                        selected_task_id = selected_task["task_id"]
                        selected_ui_elements = self.controller.ui.task_ui_elements.get(
                            selected_task_id
                        )

                        if not selected_ui_elements:
                            continue

                        # Move all UI elements for this task
                        self.controller.task_canvas.move(
                            selected_ui_elements["box"], dx, dy
                        )
                        self.controller.task_canvas.move(
                            selected_ui_elements["left_edge"], dx, dy
                        )
                        self.controller.task_canvas.move(
                            selected_ui_elements["right_edge"], dx, dy
                        )
                        self.controller.task_canvas.move(
                            selected_ui_elements["text"], dx, dy
                        )
                        self.controller.task_canvas.move(
                            selected_ui_elements["connector"], dx, dy
                        )

                        # Move tag text if it exists
                        if selected_ui_elements.get("tag_text"):
                            self.controller.task_canvas.move(
                                selected_ui_elements["tag_text"], dx, dy
                            )

                        # Move highlight if it exists
                        if selected_ui_elements.get("highlight"):
                            self.controller.task_canvas.move(
                                selected_ui_elements["highlight"], dx, dy
                            )

                        # Update stored coordinates
                        selected_ui_elements["x1"] += dx
                        selected_ui_elements["y1"] += dy
                        selected_ui_elements["x2"] += dx
                        selected_ui_elements["y2"] += dy
                        selected_ui_elements["connector_x"] += dx
                        selected_ui_elements["connector_y"] += dy
                else:
                    # Move just the single selected task
                    self.controller.task_canvas.move(ui_elements["box"], dx, dy)
                    self.controller.task_canvas.move(ui_elements["left_edge"], dx, dy)
                    self.controller.task_canvas.move(ui_elements["right_edge"], dx, dy)
                    self.controller.task_canvas.move(ui_elements["text"], dx, dy)

                    # Move tag text if it exists
                    if ui_elements.get("tag_text"):
                        self.controller.task_canvas.move(
                            ui_elements["tag_text"], dx, dy
                        )

                    # Move highlight if it exists
                    if ui_elements.get("highlight"):
                        self.controller.task_canvas.move(
                            ui_elements["highlight"], dx, dy
                        )

                    # Update connector
                    self.controller.task_canvas.move(ui_elements["connector"], dx, dy)

                    # Update stored coordinates
                    ui_elements["x1"] += dx
                    ui_elements["y1"] += dy
                    ui_elements["x2"] += dx
                    ui_elements["y2"] += dy
                    ui_elements["connector_x"] += dx
                    ui_elements["connector_y"] += dy

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
                # Snap left edge - only for single task
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
                # Snap right edge - only for single task
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
                # Moving tasks - check if multiple tasks are selected
                if (
                    len(self.controller.selected_tasks) > 1
                    and task in self.controller.selected_tasks
                ):
                    # Handle snapping for all selected tasks
                    for selected_task in self.controller.selected_tasks:
                        selected_task_id = selected_task["task_id"]
                        selected_ui = self.controller.ui.task_ui_elements.get(
                            selected_task_id
                        )

                        if not selected_ui:
                            continue

                        # Snap individual task to grid
                        grid_row = round(
                            selected_ui["y1"] / self.controller.task_height
                        )
                        grid_col = round(selected_ui["x1"] / self.controller.cell_width)

                        new_x1 = grid_col * self.controller.cell_width
                        new_y1 = grid_row * self.controller.task_height
                        new_x2 = (
                            new_x1
                            + selected_task["duration"] * self.controller.cell_width
                        )
                        new_y2 = new_y1 + self.controller.task_height

                        # Keep task within bounds
                        if grid_row >= self.model.max_rows:
                            grid_row = self.model.max_rows - 1
                            new_y1 = grid_row * self.controller.task_height
                            new_y2 = new_y1 + self.controller.task_height

                        if grid_row < 0:
                            grid_row = 0
                            new_y1 = 0
                            new_y2 = self.controller.task_height

                        if grid_col < 0:
                            grid_col = 0
                            new_x1 = 0
                            new_x2 = (
                                new_x1
                                + selected_task["duration"] * self.controller.cell_width
                            )

                        if grid_col + selected_task["duration"] > self.model.days:
                            grid_col = self.model.days - selected_task["duration"]
                            new_x1 = grid_col * self.controller.cell_width
                            new_x2 = (
                                new_x1
                                + selected_task["duration"] * self.controller.cell_width
                            )

                        # Update visuals
                        self.controller.task_canvas.coords(
                            selected_ui["box"], new_x1, new_y1, new_x2, new_y2
                        )
                        self.controller.task_canvas.coords(
                            selected_ui["left_edge"], new_x1, new_y1, new_x1, new_y2
                        )
                        self.controller.task_canvas.coords(
                            selected_ui["right_edge"], new_x2, new_y1, new_x2, new_y2
                        )

                        # Update text positions
                        self.controller.task_canvas.coords(
                            selected_ui["text"],
                            (new_x1 + new_x2) / 2,
                            (new_y1 + new_y2) / 2 - 8,
                        )

                        # Update tag text position if it exists
                        if selected_ui.get("tag_text"):
                            self.controller.task_canvas.coords(
                                selected_ui["tag_text"],
                                (new_x1 + new_x2) / 2,
                                (new_y1 + new_y2) / 2 + 8,
                            )

                        # Update connector position
                        selected_ui["connector_x"] = new_x2
                        selected_ui["connector_y"] = (new_y1 + new_y2) / 2
                        self.controller.task_canvas.coords(
                            selected_ui["connector"],
                            selected_ui["connector_x"] - 5,
                            selected_ui["connector_y"] - 5,
                            selected_ui["connector_x"] + 5,
                            selected_ui["connector_y"] + 5,
                        )

                        # Update stored coordinates
                        selected_ui["x1"], selected_ui["y1"] = new_x1, new_y1
                        selected_ui["x2"], selected_ui["y2"] = new_x2, new_y2

                        # Update model
                        selected_task["row"], selected_task["col"] = grid_row, grid_col

                    # Handle collisions for all tasks after positioning
                    for selected_task in self.controller.selected_tasks:
                        selected_ui = self.controller.ui.task_ui_elements.get(
                            selected_task["task_id"]
                        )
                        if selected_ui:
                            self.handle_task_collisions(
                                selected_task,
                                selected_ui["x1"],
                                selected_ui["y1"],
                                selected_ui["x2"],
                                selected_ui["y2"],
                            )
                else:
                    # Snap single task
                    grid_row = round(ui_elements["y1"] / self.controller.task_height)
                    grid_col = round(ui_elements["x1"] / self.controller.cell_width)

                    new_x1 = grid_col * self.controller.cell_width
                    new_y1 = grid_row * self.controller.task_height
                    new_x2 = new_x1 + task["duration"] * self.controller.cell_width
                    new_y2 = new_y1 + self.controller.task_height

                    # Keep task within bounds
                    if grid_row >= self.model.max_rows:
                        grid_row = self.model.max_rows - 1
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
                        (new_y1 + new_y2) / 2 - 8,
                    )

                    # Update tag text position if it exists
                    if ui_elements.get("tag_text"):
                        self.controller.task_canvas.coords(
                            ui_elements["tag_text"],
                            (new_x1 + new_x2) / 2,
                            (new_y1 + new_y2) / 2 + 8,
                        )

                    # Update highlight position if it exists
                    if "highlight" in ui_elements:
                        self.controller.task_canvas.coords(
                            ui_elements["highlight"],
                            new_x1 - 2,
                            new_y1 - 2,
                            new_x2 + 2,
                            new_y2 + 2,
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

            # Call handle_task_collisions for single task resize operations
            if (
                self.controller.resize_edge == "left"
                or self.controller.resize_edge == "right"
            ):
                x1, y1, x2, y2 = (
                    ui_elements["x1"],
                    ui_elements["y1"],
                    ui_elements["x2"],
                    ui_elements["y2"],
                )
                self.handle_task_collisions(task, x1, y1, x2, y2)

            # Note: We don't clear selected_task here when in multi-select mode
            # This keeps the task selected after manipulation
            if not self.controller.multi_select_mode:
                self.controller.selected_task = None

            self.controller.resize_edge = None

            # Redraw dependencies
            self.controller.ui.draw_dependencies()

            # Important: Re-highlight selected tasks to ensure orange border is correctly positioned
            # This regenerates all highlights to ensure they match the final grid-snapped positions
            self.controller.ui.remove_task_selections()
            self.controller.ui.highlight_selected_tasks()

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
                        tags=[],  # Add empty tags list
                    )

                    # Draw the new task
                    self.controller.ui.draw_task(new_task)

                    # Prompt for resources
                    self.edit_task_resources(new_task)

                    # Optionally prompt for tags
                    self.controller.tag_ops.edit_task_tags(new_task)

                    # Select the newly created task
                    self.controller.selected_task = new_task
                    self.controller.selected_tasks = [new_task]
                    self.controller.ui.highlight_selected_tasks()

            # Remove the rubberband
            if self.controller.rubberband:
                self.controller.task_canvas.delete

            # Reset new task flags
            self.controller.new_task_in_progress = False
            self.controller.new_task_start = None

        # Update resource loading
        self.controller.update_resource_loading()

    def on_right_click(self, event):
        """Handle right-click to show context menu without changing selection"""
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
                task = self.model.get_task(task_id)

                # Don't change selection, just set selected_task for context menu operations
                self.controller.selected_task = task

                # Check if we have multiple tasks selected and the right-clicked task is among them
                if (
                    len(self.controller.selected_tasks) > 1
                    and task in self.controller.selected_tasks
                ):
                    # Show the multi-task context menu
                    self.controller.ui.multi_task_menu.post(event.x_root, event.y_root)
                else:
                    # Show single task context menu
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

                # Get UI elements for this task
                task_id = other_task["task_id"]
                ui_elements = self.controller.ui.task_ui_elements.get(task_id)

                if ui_elements:
                    # Calculate new positions
                    new_x1 = grid_col * self.controller.cell_width
                    new_x2 = (
                        new_x1 + other_task["duration"] * self.controller.cell_width
                    )

                    # Update box position
                    self.controller.task_canvas.coords(
                        ui_elements["box"],
                        new_x1,
                        ui_elements["y1"],
                        new_x2,
                        ui_elements["y2"],
                    )

                    # Update edge positions
                    self.controller.task_canvas.coords(
                        ui_elements["left_edge"],
                        new_x1,
                        ui_elements["y1"],
                        new_x1,
                        ui_elements["y2"],
                    )

                    self.controller.task_canvas.coords(
                        ui_elements["right_edge"],
                        new_x2,
                        ui_elements["y1"],
                        new_x2,
                        ui_elements["y2"],
                    )

                    # Update text position
                    self.controller.task_canvas.coords(
                        ui_elements["text"],
                        (new_x1 + new_x2) / 2,
                        (ui_elements["y1"] + ui_elements["y2"]) / 2 - 8,
                    )

                    # Update tag text position if it exists
                    if "tag_text" in ui_elements:
                        self.controller.task_canvas.coords(
                            ui_elements["tag_text"],
                            (new_x1 + new_x2) / 2,
                            (ui_elements["y1"] + ui_elements["y2"]) / 2 + 8,
                        )

                    # Update connector position
                    connector_x = new_x2
                    connector_y = (ui_elements["y1"] + ui_elements["y2"]) / 2
                    self.controller.task_canvas.coords(
                        ui_elements["connector"],
                        connector_x - 5,
                        connector_y - 5,
                        connector_x + 5,
                        connector_y + 5,
                    )

                    # Update highlight position if it exists
                    if "highlight" in ui_elements:
                        self.controller.task_canvas.coords(
                            ui_elements["highlight"],
                            new_x1 - 2,
                            ui_elements["y1"] - 2,
                            new_x2 + 2,
                            ui_elements["y2"] + 2,
                        )

                    # Update stored coordinates
                    ui_elements["x1"] = new_x1
                    ui_elements["x2"] = new_x2
                    ui_elements["connector_x"] = connector_x
                    ui_elements["connector_y"] = connector_y

                # For the next iteration, this shifted task becomes the one that might cause collisions
                x1 = grid_col * self.controller.cell_width
                x2 = x1 + other_task["duration"] * self.controller.cell_width
                y1 = other_y1
                y2 = other_y2
                task = other_task

            # Redraw dependencies after all shifts are complete
            self.controller.ui.draw_dependencies()
