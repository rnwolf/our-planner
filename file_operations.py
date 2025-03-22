import os
import json
from tkinter import filedialog, messagebox


class FileOperations:
    def __init__(self, manager):
        self.manager = manager

    def new_project(self):
        """Create a new project, clearing all current tasks"""
        if messagebox.askyesno(
            "New Project",
            "Are you sure you want to create a new project? All unsaved changes will be lost.",
        ):
            self.manager.tasks = []
            self.manager.current_file_path = None
            self.manager.root.title("Task Resource Manager - New Project")
            self.manager.ui.draw_task_grid()
            self.manager.task_ops.calculate_resource_loading()

    def open_file(self):
        """Open a task file"""
        file_path = filedialog.askopenfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Open Project",
        )

        if not file_path:
            return

        try:
            with open(file_path, "r") as f:
                data = json.load(f)

            # Basic validation
            if "tasks" not in data or "resources" not in data or "days" not in data:
                messagebox.showerror(
                    "Invalid File", "The selected file is not a valid project file."
                )
                return

            # Load project data
            self.manager.tasks = data["tasks"]
            self.manager.resources = data["resources"]
            self.manager.days = data["days"]

            # Update UI with loaded data
            self.manager.current_file_path = file_path
            self.manager.root.title(
                f"Task Resource Manager - {os.path.basename(file_path)}"
            )

            # Clear any canvas items
            self.manager.task_canvas.delete("all")
            self.manager.resource_canvas.delete("all")

            # Update displayed data
            self.manager.ui.draw_timeline()
            self.manager.ui.draw_task_grid()
            self.manager.ui.draw_resource_grid()
            self.manager.task_ops.calculate_resource_loading()

            messagebox.showinfo(
                "Project Loaded", f"Project loaded from {os.path.basename(file_path)}"
            )

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open file: {str(e)}")

    def save_file(self):
        """Save the current tasks to a file"""
        if self.manager.current_file_path:
            self.save_to_file(self.manager.current_file_path)
        else:
            self.save_file_as()

    def save_file_as(self):
        """Save the current tasks to a new file"""
        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Save Project As",
        )

        if not file_path:
            return

        self.save_to_file(file_path)

    def save_to_file(self, file_path):
        """Save project data to the specified file"""
        try:
            # Prepare project data for saving
            project_data = {
                "tasks": self.serialize_tasks(),
                "resources": self.manager.resources,
                "days": self.manager.days,
            }

            with open(file_path, "w") as f:
                json.dump(project_data, f, indent=2)

            # Update current file path and window title
            self.manager.current_file_path = file_path
            self.manager.root.title(
                f"Task Resource Manager - {os.path.basename(file_path)}"
            )

            messagebox.showinfo(
                "Save Successful", f"Project saved to {os.path.basename(file_path)}"
            )

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save file: {str(e)}")

    def serialize_tasks(self):
        """Prepare tasks for saving (removing canvas-specific items)"""
        serialized_tasks = []

        for task in self.manager.tasks:
            # Create a copy of the task without canvas-specific items
            task_data = {
                "row": task["row"],
                "col": task["col"],
                "duration": task["duration"],
                "description": task.get("description", ""),
                "url": task.get("url", ""),
                "resources": task["resources"],
            }
            serialized_tasks.append(task_data)

        return serialized_tasks
