import tkinter as tk
from tkinter import messagebox, scrolledtext
import webbrowser


class HelpMenu:
    """Implementation of the Help menu for the Task Resource Manager."""

    def __init__(self, controller, root, menu_bar):
        """Initialize the help menu.

        Args:
            controller: The main application controller
            root: The root Tk window
            menu_bar: The main menu bar to add the Help menu to
        """
        self.controller = controller
        self.root = root

        # Create Help menu
        self.help_menu = tk.Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label="Help", menu=self.help_menu)

        # Add menu items
        self.help_menu.add_command(label="Website", command=self.open_website)
        self.help_menu.add_command(label="About", command=self.show_about)
        self.help_menu.add_command(label="Debug", command=self.show_debug)

    def open_website(self):
        """Open the project website in the default browser."""
        webbrowser.open("https://github.com/rnwolf/py_sequencer")

    def show_about(self):
        """Show the About dialog."""
        about_dialog = tk.Toplevel(self.root)
        about_dialog.title("About Task Resource Manager")
        about_dialog.transient(self.root)
        about_dialog.grab_set()

        # Make dialog modal
        about_dialog.focus_set()

        # Position the dialog
        about_dialog.geometry("400x200")

        # Center dialog on parent window
        about_dialog.update_idletasks()
        width = about_dialog.winfo_width()
        height = about_dialog.winfo_height()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - width) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - height) // 2
        about_dialog.geometry(f"+{x}+{y}")

        # Add content
        frame = tk.Frame(about_dialog, padx=20, pady=20)
        frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title_label = tk.Label(
            frame, text="Task Resource Manager", font=("Arial", 16, "bold")
        )
        title_label.pack(pady=(0, 10))

        # Author info
        author_label = tk.Label(frame, text="Created by R.N. Wolf", font=("Arial", 12))
        author_label.pack(pady=5)

        # Website link
        website_link = tk.Label(
            frame,
            text="www.tnwolf.net",
            fg="blue",
            cursor="hand2",
            font=("Arial", 12, "underline"),
        )
        website_link.pack(pady=5)
        website_link.bind(
            "<Button-1>", lambda e: webbrowser.open("https://www.tnwolf.net")
        )

        # Close button
        close_button = tk.Button(
            frame, text="Close", command=about_dialog.destroy, width=10
        )
        close_button.pack(pady=(20, 0))

        # Bind Escape key to close dialog
        about_dialog.bind("<Escape>", lambda e: about_dialog.destroy())

    def show_debug(self):
        """Show the Debug dialog with information about selected tasks."""
        debug_dialog = tk.Toplevel(self.root)
        debug_dialog.title("Debug Information")
        debug_dialog.transient(self.root)
        debug_dialog.grab_set()

        # Make dialog modal
        debug_dialog.focus_set()

        # Position the dialog
        debug_dialog.geometry("600x400")

        # Center dialog on parent window
        debug_dialog.update_idletasks()
        width = debug_dialog.winfo_width()
        height = debug_dialog.winfo_height()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - width) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - height) // 2
        debug_dialog.geometry(f"+{x}+{y}")

        # Add content
        frame = tk.Frame(debug_dialog, padx=20, pady=20)
        frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title_label = tk.Label(
            frame, text="Debug Information", font=("Arial", 14, "bold")
        )
        title_label.pack(pady=(0, 10))

        # Create scrolled text area
        text_area = scrolledtext.ScrolledText(frame, wrap=tk.WORD, width=70, height=15)
        text_area.pack(fill=tk.BOTH, expand=True, pady=10)

        # Insert debug info
        text_area.insert(tk.END, "Selected Tasks:\n\n")

        # Get selected tasks info
        selected_tasks = self.controller.selected_tasks
        if selected_tasks:
            for i, task in enumerate(selected_tasks):
                text_area.insert(tk.END, f"Task {i+1}:\n")
                text_area.insert(tk.END, f"  ID: {task['task_id']}\n")
                text_area.insert(tk.END, f"  Description: {task['description']}\n")
                text_area.insert(
                    tk.END, f"  Row: {task['row']}, Column: {task['col']}\n"
                )
                text_area.insert(tk.END, f"  Duration: {task['duration']}\n")

                # Calculate and show calendar dates
                start_date = self.controller.model.get_date_for_day(task["col"])
                end_date = self.controller.model.get_date_for_day(
                    task["col"] + task["duration"] - 1
                )
                text_area.insert(
                    tk.END, f"  Start Date: {start_date.strftime('%Y-%m-%d')}\n"
                )
                text_area.insert(
                    tk.END, f"  End Date: {end_date.strftime('%Y-%m-%d')}\n"
                )

                # Predecessors
                if "predecessors" in task and task["predecessors"]:
                    text_area.insert(
                        tk.END,
                        f"  Predecessors: {', '.join(map(str, task['predecessors']))}\n",
                    )
                else:
                    text_area.insert(tk.END, f"  Predecessors: None\n")

                # Successors
                if "successors" in task and task["successors"]:
                    text_area.insert(
                        tk.END,
                        f"  Successors: {', '.join(map(str, task['successors']))}\n",
                    )
                else:
                    text_area.insert(tk.END, f"  Successors: None\n")

                # Tags
                if "tags" in task and task["tags"]:
                    text_area.insert(tk.END, f"  Tags: {', '.join(task['tags'])}\n")
                else:
                    text_area.insert(tk.END, f"  Tags: None\n")

                # Resources
                if task["resources"]:
                    text_area.insert(tk.END, f"  Resources:\n")
                    for resource_id, allocation in task["resources"].items():
                        resource = self.controller.model.get_resource_by_id(
                            int(resource_id)
                        )
                        if resource:
                            text_area.insert(
                                tk.END, f"    {resource['name']}: {allocation}\n"
                            )
                else:
                    text_area.insert(tk.END, f"  Resources: None\n")

                text_area.insert(tk.END, "\n")
        else:
            text_area.insert(tk.END, "No tasks selected\n")

        # Add additional system info
        text_area.insert(tk.END, "\nSystem Information:\n")
        text_area.insert(tk.END, f"Current Date: {self.controller.model.setdate}\n")
        text_area.insert(tk.END, f"Zoom Level: {self.controller.zoom_level * 100}%\n")
        text_area.insert(tk.END, f"Total Tasks: {len(self.controller.model.tasks)}\n")
        text_area.insert(
            tk.END, f"Total Resources: {len(self.controller.model.resources)}\n"
        )

        # Make text area read-only
        text_area.config(state=tk.DISABLED)

        # Close button
        close_button = tk.Button(
            frame, text="Close", command=debug_dialog.destroy, width=10
        )
        close_button.pack(pady=(10, 0))

        # Refresh button
        refresh_button = tk.Button(
            frame,
            text="Refresh",
            command=lambda: self.refresh_debug_info(text_area),
            width=10,
        )
        refresh_button.pack(side=tk.LEFT, pady=(10, 0))

        # Bind Escape key to close dialog
        debug_dialog.bind("<Escape>", lambda e: debug_dialog.destroy())

    def refresh_debug_info(self, text_area):
        """Refresh the debug information in the text area."""
        # Enable editing
        text_area.config(state=tk.NORMAL)

        # Clear current content
        text_area.delete(1.0, tk.END)

        # Insert updated debug info
        text_area.insert(tk.END, "Selected Tasks:\n\n")

        # Get selected tasks info
        selected_tasks = self.controller.selected_tasks
        if selected_tasks:
            for i, task in enumerate(selected_tasks):
                text_area.insert(tk.END, f"Task {i+1}:\n")
                text_area.insert(tk.END, f"  ID: {task['task_id']}\n")
                text_area.insert(tk.END, f"  Description: {task['description']}\n")
                text_area.insert(
                    tk.END, f"  Row: {task['row']}, Column: {task['col']}\n"
                )
                text_area.insert(tk.END, f"  Duration: {task['duration']}\n")

                # Calculate and show calendar dates
                start_date = self.controller.model.get_date_for_day(task["col"])
                end_date = self.controller.model.get_date_for_day(
                    task["col"] + task["duration"] - 1
                )
                text_area.insert(
                    tk.END, f"  Start Date: {start_date.strftime('%Y-%m-%d')}\n"
                )
                text_area.insert(
                    tk.END, f"  End Date: {end_date.strftime('%Y-%m-%d')}\n"
                )

                # Predecessors
                if "predecessors" in task and task["predecessors"]:
                    text_area.insert(
                        tk.END,
                        f"  Predecessors: {', '.join(map(str, task['predecessors']))}\n",
                    )
                else:
                    text_area.insert(tk.END, f"  Predecessors: None\n")

                # Successors
                if "successors" in task and task["successors"]:
                    text_area.insert(
                        tk.END,
                        f"  Successors: {', '.join(map(str, task['successors']))}\n",
                    )
                else:
                    text_area.insert(tk.END, f"  Successors: None\n")

                # Tags
                if "tags" in task and task["tags"]:
                    text_area.insert(tk.END, f"  Tags: {', '.join(task['tags'])}\n")
                else:
                    text_area.insert(tk.END, f"  Tags: None\n")

                # Resources
                if task["resources"]:
                    text_area.insert(tk.END, f"  Resources:\n")
                    for resource_id, allocation in task["resources"].items():
                        resource = self.controller.model.get_resource_by_id(
                            int(resource_id)
                        )
                        if resource:
                            text_area.insert(
                                tk.END, f"    {resource['name']}: {allocation}\n"
                            )
                else:
                    text_area.insert(tk.END, f"  Resources: None\n")

                text_area.insert(tk.END, "\n")
        else:
            text_area.insert(tk.END, "No tasks selected\n")

        # Add additional system info
        text_area.insert(tk.END, "\nSystem Information:\n")
        text_area.insert(tk.END, f"Current Date: {self.controller.model.setdate}\n")
        text_area.insert(tk.END, f"Zoom Level: {self.controller.zoom_level * 100}%\n")
        text_area.insert(tk.END, f"Total Tasks: {len(self.controller.model.tasks)}\n")
        text_area.insert(
            tk.END, f"Total Resources: {len(self.controller.model.resources)}\n"
        )

        # Make text area read-only again
        text_area.config(state=tk.DISABLED)
