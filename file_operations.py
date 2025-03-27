from tkinter import filedialog, messagebox
import os
from datetime import datetime


class FileOperations:
    def __init__(self, controller, model):
        self.controller = controller
        self.model = model

    def new_project(self):
        """Create a new project, clearing all current tasks"""
        if messagebox.askyesno(
            "New Project",
            "Are you sure you want to create a new project? All unsaved changes will be lost.",
        ):
            # Reset model data
            self.model.tasks = []
            self.model.current_file_path = None

            # Reset setdate to today
            self.model.setdate = datetime.now().replace(
                hour=0, minute=0, second=0, microsecond=0
            )

            # Update UI
            self.controller.update_window_title()
            self.controller.update_view()

    def open_file(self):
        """Open a task file"""
        file_path = filedialog.askopenfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Open Project",
        )

        if not file_path:
            return

        # Use model method to load data
        if self.model.load_from_file(file_path):
            # Update UI
            self.controller.update_window_title(file_path)
            self.controller.update_view()

            messagebox.showinfo(
                "Project Loaded", f"Project loaded from {os.path.basename(file_path)}"
            )
        else:
            messagebox.showerror(
                "Error", "Failed to open file. The file may be corrupted or invalid."
            )

    def save_file(self):
        """Save the current tasks to a file"""
        if self.model.current_file_path:
            if self.model.save_to_file(self.model.current_file_path):
                messagebox.showinfo(
                    "Save Successful",
                    f"Project saved to {os.path.basename(self.model.current_file_path)}",
                )
            else:
                messagebox.showerror("Error", "Failed to save file.")
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

        if self.model.save_to_file(file_path):
            self.controller.update_window_title(file_path)
            messagebox.showinfo(
                "Save Successful", f"Project saved to {os.path.basename(file_path)}"
            )
        else:
            messagebox.showerror("Error", "Failed to save file.")
