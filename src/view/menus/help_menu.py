"""
Help menu for Task Resource Manager.

This module contains the UI components for the Help menu.
"""

import tkinter as tk
from tkinter import messagebox, scrolledtext
import webbrowser
from src.utils.version import get_version


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
        menu_bar.add_cascade(label='Help', menu=self.help_menu)

        # Add menu items
        self.help_menu.add_command(
            label='Documentation', command=self.show_documentation
        )
        self.help_menu.add_command(label='Website', command=self.open_website)
        self.help_menu.add_command(label='About', command=self.show_about)
        self.help_menu.add_command(label='Debug', command=self.show_debug)

    def show_documentation(self):
        """Show the user documentation."""
        # Create a documentation dialog
        doc_dialog = tk.Toplevel(self.root)
        doc_dialog.title('Task Resource Manager Documentation')
        doc_dialog.transient(self.root)
        doc_dialog.grab_set()
        doc_dialog.geometry('700x500')

        # Center the dialog
        doc_dialog.update_idletasks()
        width = doc_dialog.winfo_width()
        height = doc_dialog.winfo_height()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - width) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - height) // 2
        doc_dialog.geometry(f'+{x}+{y}')

        # Create a frame with padding
        frame = tk.Frame(doc_dialog, padx=20, pady=20)
        frame.pack(fill=tk.BOTH, expand=True)

        # Add a title
        title_label = tk.Label(
            frame,
            text='Task Resource Manager Documentation',
            font=('Arial', 16, 'bold'),
        )
        title_label.pack(pady=(0, 15))

        # Create a scrolled text widget for the documentation
        text_area = scrolledtext.ScrolledText(
            frame, wrap=tk.WORD, width=80, height=20, font=('Arial', 10)
        )
        text_area.pack(fill=tk.BOTH, expand=True, pady=10)

        # Add documentation content
        documentation = """
# Task Resource Manager - User Guide

## Basic Operations

### Creating Tasks
- Click and drag on the task grid to create a new task
- Enter a task name when prompted
- You can edit task properties later by right-clicking on the task

### Moving Tasks
- Click and drag a task to move it to a new position
- Tasks will snap to the grid when released

### Resizing Tasks
- Click and drag the left or right edge of a task to resize it

### Adding Dependencies
- Right-click on a task and select "Add Predecessor" or "Add Successor"
- You can also drag from the connection point on the right edge of a task to another task

### Editing Task Properties
- Right-click on a task to access the context menu
- Options include:
  - Edit Task Name
  - Edit Task URL
  - Edit Task Resources
  - Edit Task Tags
  - Set Task Color
  - Add Predecessor/Successor
  - Delete Task

## Working with Resources

- Resources are shown in the bottom grid
- You can add, edit, and remove resources from the Edit menu
- Resource loading is calculated based on task allocations
- Overallocated resources are highlighted in red

## Tags and Filtering

- You can add tags to tasks and resources for organization
- Use the Tags menu to filter tasks and resources by tags
- Toggle tag display using the View menu

## Critical Path Analysis

- Select tasks using Ctrl+click or enable multi-select mode
- Use the Network menu to run Critical Path Analysis
- The critical path shows the shortest possible project duration

## Exporting Your Project

- Use the File > Export menu to save your project in various formats:
  - PDF: Complete report with tasks, resources, and loading
  - PNG: Image of the current view
  - CSV: Spreadsheet-compatible data tables
  - HTML: Interactive web report

## Keyboard Shortcuts

- Ctrl+0: Reset zoom
- Ctrl+A: Select all tasks
- Esc: Clear selections
- Ctrl+E: Open export dialog
        """

        text_area.insert(tk.END, documentation)

        # Make the text area read-only
        text_area.config(state=tk.DISABLED)

        # Add a Close button
        close_button = tk.Button(
            frame, text='Close', command=doc_dialog.destroy, width=10
        )
        close_button.pack(pady=(10, 0))

        # Bind Escape key to close dialog
        doc_dialog.bind('<Escape>', lambda e: doc_dialog.destroy())

    def open_website(self):
        """Open the project website in the default browser."""
        webbrowser.open('https://github.com/rnwolf/py_sequencer')

    def show_about(self):
        """Show the About dialog."""
        about_dialog = tk.Toplevel(self.root)
        about_dialog.title('About Task Resource Manager')
        about_dialog.transient(self.root)
        about_dialog.grab_set()

        # Make dialog modal
        about_dialog.focus_set()

        # Position the dialog
        about_dialog.geometry('400x300')

        # Center dialog on parent window
        about_dialog.update_idletasks()
        width = about_dialog.winfo_width()
        height = about_dialog.winfo_height()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - width) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - height) // 2
        about_dialog.geometry(f'+{x}+{y}')

        # Add content
        frame = tk.Frame(about_dialog, padx=20, pady=20)
        frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title_label = tk.Label(
            frame, text='Task Resource Manager', font=('Arial', 16, 'bold')
        )
        title_label.pack(pady=(0, 10))

        # Version information - get from the package
        try:
            import toml

            with open('pyproject.toml', 'r') as f:
                pyproject_data = toml.load(f)
            __version__ = pyproject_data.get('project', {}).get('version', '0.1.0')

            version_text = f'Version {__version__}'
        except ImportError:
            version_text = 'Version 0.1.0'

        # Version information - get from utility function
        version_text = f'Version {get_version()}'
        version_label = tk.Label(frame, text=version_text, font=('Arial', 10))
        version_label.pack(pady=2)

        # Author info
        author_label = tk.Label(frame, text='Created by R.N. Wolf', font=('Arial', 12))
        author_label.pack(pady=5)

        # Website link
        website_link = tk.Label(
            frame,
            text='www.rnwolf.net',
            fg='blue',
            cursor='hand2',
            font=('Arial', 12, 'underline'),
        )
        website_link.pack(pady=5)
        website_link.bind(
            '<Button-1>', lambda e: webbrowser.open('https://www.rnwolf.net')
        )

        # link to license
        license_link = tk.Label(
            frame,
            text='LICENCE.txt',
            fg='blue',
            cursor='hand2',
            font=('Arial', 12, 'underline'),
        )
        license_link.pack(pady=5)
        license_link.bind(
            '<Button-1>',
            lambda e: webbrowser.open(
                'https://github.com/rnwolf/our-planner/blob/main/LICENSE.txt'
            ),
        )

        # Close button
        close_button = tk.Button(
            frame, text='Close', command=about_dialog.destroy, width=10
        )
        close_button.pack(pady=(20, 0))

        # Bind Escape key to close dialog
        about_dialog.bind('<Escape>', lambda e: about_dialog.destroy())

    def show_debug(self):
        """Show the Debug dialog with information about selected tasks."""
        debug_dialog = tk.Toplevel(self.root)
        debug_dialog.title('Debug Information')
        debug_dialog.transient(self.root)
        debug_dialog.grab_set()

        # Make dialog modal
        debug_dialog.focus_set()

        # Position the dialog
        debug_dialog.geometry('600x400')

        # Center dialog on parent window
        debug_dialog.update_idletasks()
        width = debug_dialog.winfo_width()
        height = debug_dialog.winfo_height()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - width) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - height) // 2
        debug_dialog.geometry(f'+{x}+{y}')

        # Add content
        frame = tk.Frame(debug_dialog, padx=20, pady=20)
        frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title_label = tk.Label(
            frame, text='Debug Information', font=('Arial', 14, 'bold')
        )
        title_label.pack(pady=(0, 10))

        # Create scrolled text area
        text_area = scrolledtext.ScrolledText(frame, wrap=tk.WORD, width=70, height=15)
        text_area.pack(fill=tk.BOTH, expand=True, pady=10)

        # Insert debug info
        text_area.insert(tk.END, 'Selected Tasks:\n\n')

        # Get selected tasks info
        selected_tasks = self.controller.selected_tasks
        if selected_tasks:
            for i, task in enumerate(selected_tasks):
                text_area.insert(tk.END, f'Task {i+1}:\n')
                text_area.insert(tk.END, f"  ID: {task['task_id']}\n")
                text_area.insert(tk.END, f"  Description: {task['description']}\n")
                text_area.insert(
                    tk.END, f"  Row: {task['row']}, Column: {task['col']}\n"
                )
                text_area.insert(tk.END, f"  Duration: {task['duration']}\n")

                # Calculate and show calendar dates
                start_date = self.controller.model.get_date_for_day(task['col'])
                end_date = self.controller.model.get_date_for_day(
                    task['col'] + task['duration'] - 1
                )
                text_area.insert(
                    tk.END, f"  Start Date: {start_date.strftime('%Y-%m-%d')}\n"
                )
                text_area.insert(
                    tk.END, f"  End Date: {end_date.strftime('%Y-%m-%d')}\n"
                )

                # Predecessors
                if 'predecessors' in task and task['predecessors']:
                    text_area.insert(
                        tk.END,
                        f"  Predecessors: {', '.join(map(str, task['predecessors']))}\n",
                    )
                else:
                    text_area.insert(tk.END, f'  Predecessors: None\n')

                # Successors
                if 'successors' in task and task['successors']:
                    text_area.insert(
                        tk.END,
                        f"  Successors: {', '.join(map(str, task['successors']))}\n",
                    )
                else:
                    text_area.insert(tk.END, f'  Successors: None\n')

                # Tags
                if 'tags' in task and task['tags']:
                    text_area.insert(tk.END, f"  Tags: {', '.join(task['tags'])}\n")
                else:
                    text_area.insert(tk.END, f'  Tags: None\n')

                # Resources
                if task['resources']:
                    text_area.insert(tk.END, f'  Resources:\n')
                    for resource_id, allocation in task['resources'].items():
                        resource = self.controller.model.get_resource_by_id(
                            int(resource_id)
                            if isinstance(resource_id, str)
                            else resource_id
                        )
                        if resource:
                            text_area.insert(
                                tk.END, f"    {resource['name']}: {allocation}\n"
                            )
                else:
                    text_area.insert(tk.END, f'  Resources: None\n')

                text_area.insert(tk.END, '\n')
        else:
            text_area.insert(tk.END, 'No tasks selected\n')

        # Add additional system info
        text_area.insert(tk.END, '\nSystem Information:\n')
        text_area.insert(tk.END, f'Current Date: {self.controller.model.setdate}\n')
        text_area.insert(tk.END, f'Zoom Level: {self.controller.zoom_level * 100}%\n')
        text_area.insert(tk.END, f'Total Tasks: {len(self.controller.model.tasks)}\n')
        text_area.insert(
            tk.END, f'Total Resources: {len(self.controller.model.resources)}\n'
        )

        # Make text area read-only
        text_area.config(state=tk.DISABLED)

        # Close button
        close_button = tk.Button(
            frame, text='Close', command=debug_dialog.destroy, width=10
        )
        close_button.pack(pady=(10, 0))

        # Refresh button
        refresh_button = tk.Button(
            frame,
            text='Refresh',
            command=lambda: self.refresh_debug_info(text_area),
            width=10,
        )
        refresh_button.pack(side=tk.LEFT, pady=(10, 0))

        # Bind Escape key to close dialog
        debug_dialog.bind('<Escape>', lambda e: debug_dialog.destroy())

    def refresh_debug_info(self, text_area):
        """Refresh the debug information in the text area."""
        # Enable editing
        text_area.config(state=tk.NORMAL)

        # Clear current content
        text_area.delete(1.0, tk.END)

        # Insert updated debug info
        text_area.insert(tk.END, 'Selected Tasks:\n\n')

        # Get selected tasks info
        selected_tasks = self.controller.selected_tasks
        if selected_tasks:
            for i, task in enumerate(selected_tasks):
                text_area.insert(tk.END, f'Task {i+1}:\n')
                text_area.insert(tk.END, f"  ID: {task['task_id']}\n")
                text_area.insert(tk.END, f"  Description: {task['description']}\n")
                text_area.insert(
                    tk.END, f"  Row: {task['row']}, Column: {task['col']}\n"
                )
                text_area.insert(tk.END, f"  Duration: {task['duration']}\n")

                # Calculate and show calendar dates
                start_date = self.controller.model.get_date_for_day(task['col'])
                end_date = self.controller.model.get_date_for_day(
                    task['col'] + task['duration'] - 1
                )
                text_area.insert(
                    tk.END, f"  Start Date: {start_date.strftime('%Y-%m-%d')}\n"
                )
                text_area.insert(
                    tk.END, f"  End Date: {end_date.strftime('%Y-%m-%d')}\n"
                )

                # Predecessors
                if 'predecessors' in task and task['predecessors']:
                    text_area.insert(
                        tk.END,
                        f"  Predecessors: {', '.join(map(str, task['predecessors']))}\n",
                    )
                else:
                    text_area.insert(tk.END, f'  Predecessors: None\n')

                # Successors
                if 'successors' in task and task['successors']:
                    text_area.insert(
                        tk.END,
                        f"  Successors: {', '.join(map(str, task['successors']))}\n",
                    )
                else:
                    text_area.insert(tk.END, f'  Successors: None\n')

                # Tags
                if 'tags' in task and task['tags']:
                    text_area.insert(tk.END, f"  Tags: {', '.join(task['tags'])}\n")
                else:
                    text_area.insert(tk.END, f'  Tags: None\n')

                # Resources
                if task['resources']:
                    text_area.insert(tk.END, f'  Resources:\n')
                    for resource_id, allocation in task['resources'].items():
                        resource = self.controller.model.get_resource_by_id(
                            int(resource_id)
                            if isinstance(resource_id, str)
                            else resource_id
                        )
                        if resource:
                            text_area.insert(
                                tk.END, f"    {resource['name']}: {allocation}\n"
                            )
                else:
                    text_area.insert(tk.END, f'  Resources: None\n')

                text_area.insert(tk.END, '\n')
        else:
            text_area.insert(tk.END, 'No tasks selected\n')

        # Add additional system info
        text_area.insert(tk.END, '\nSystem Information:\n')
        text_area.insert(tk.END, f'Current Date: {self.controller.model.setdate}\n')
        text_area.insert(tk.END, f'Zoom Level: {self.controller.zoom_level * 100}%\n')
        text_area.insert(tk.END, f'Total Tasks: {len(self.controller.model.tasks)}\n')
        text_area.insert(
            tk.END, f'Total Resources: {len(self.controller.model.resources)}\n'
        )

        # Make text area read-only again
        text_area.config(state=tk.DISABLED)
