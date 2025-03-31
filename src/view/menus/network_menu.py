"""
Network menu for Task Resource Manager.

This module contains the UI components for the Network menu.
"""

import tkinter as tk
from tkinter import messagebox, scrolledtext
import webbrowser


class NetworkMenu:
    """Implementation of the Network menu for the Task Resource Manager."""

    def __init__(self, controller, root, menu_bar):
        """Initialize the network menu.

        Args:
            controller: The main application controller
            root: The root Tk window
            menu_bar: The main menu bar to add the Network menu to
        """
        self.controller = controller
        self.root = root

        # Create Network menu
        self.network_menu = tk.Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label='Network', menu=self.network_menu)

        # Add menu items
        self.network_menu.add_command(
            label='Critical Path', command=self.show_critical_path
        )

    def show_critical_path(self):
        """Show the Critical Path dialog with analysis of the project network."""
        try:
            # Check if there are selected tasks
            selected_tasks = self.controller.selected_tasks

            # If no tasks are selected, show a message
            if not selected_tasks:
                messagebox.showinfo(
                    'No Tasks Selected',
                    'Please select tasks for critical path analysis.\n\n'
                    'You can select multiple tasks using Ctrl+click or by enabling multi-select mode.',
                )
                return

            # Create a dialog to display critical path information
            cp_dialog = tk.Toplevel(self.root)
            cp_dialog.title('Critical Path Analysis')
            cp_dialog.transient(self.root)
            cp_dialog.grab_set()

            # Make dialog modal
            cp_dialog.focus_set()

            # Position the dialog
            cp_dialog.geometry('700x600')

            # Center dialog on parent window
            cp_dialog.update_idletasks()
            width = cp_dialog.winfo_width()
            height = cp_dialog.winfo_height()
            x = self.root.winfo_rootx() + (self.root.winfo_width() - width) // 2
            y = self.root.winfo_rooty() + (self.root.winfo_height() - height) // 2
            cp_dialog.geometry(f'+{x}+{y}')

            # Add content
            frame = tk.Frame(cp_dialog, padx=20, pady=20)
            frame.pack(fill=tk.BOTH, expand=True)

            # Title
            title_label = tk.Label(
                frame, text='Critical Path Analysis', font=('Arial', 16, 'bold')
            )
            title_label.pack(pady=(0, 15))

            # Create scrolled text area for results
            text_area = scrolledtext.ScrolledText(
                frame, wrap=tk.WORD, width=80, height=25
            )
            text_area.pack(fill=tk.BOTH, expand=True, pady=10)

            # Insert info about number of tasks analyzed
            text_area.insert(
                tk.END, f'Analyzing {len(selected_tasks)} selected tasks\n\n'
            )

            # Use the network operations to calculate critical path
            network_ops = self.controller.network_ops
            critical_path, path_length, network_analysis = (
                network_ops.calculate_critical_path(selected_tasks)
            )

            if critical_path:
                # Insert basic critical path info
                text_area.insert(tk.END, 'Critical Path:\n\n')
                text_area.insert(tk.END, f'Path Length: {path_length} days\n\n')
                text_area.insert(tk.END, 'Path: ')

                # Format the path with task descriptions
                path_items = []
                for task_id in critical_path:
                    task = self.controller.model.get_task(task_id)
                    if task:
                        path_items.append(f"Task {task_id} ({task['description']})")
                    else:
                        path_items.append(f'Task {task_id}')

                text_area.insert(tk.END, ' → '.join(path_items) + '\n\n')

                # Insert detailed task analysis
                text_area.insert(tk.END, 'Detailed Task Analysis:\n\n')
                for task_id in critical_path:
                    task = self.controller.model.get_task(task_id)
                    if task:
                        task_info = network_analysis.get(task_id, {})

                        text_area.insert(
                            tk.END, f"Task {task_id}: {task['description']}\n"
                        )
                        text_area.insert(
                            tk.END, f"  Duration: {task['duration']} days\n"
                        )

                        # Start and end dates
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

                        # Early/Late start/finish
                        if 'early_start' in task_info:
                            early_start_date = self.controller.model.get_date_for_day(
                                task_info['early_start']
                            )
                            text_area.insert(
                                tk.END,
                                f"  Early Start: Day {task_info['early_start']} ({early_start_date.strftime('%Y-%m-%d')})\n",
                            )

                        if 'early_finish' in task_info:
                            early_finish_date = self.controller.model.get_date_for_day(
                                task_info['early_finish']
                            )
                            text_area.insert(
                                tk.END,
                                f"  Early Finish: Day {task_info['early_finish']} ({early_finish_date.strftime('%Y-%m-%d')})\n",
                            )

                        if 'late_start' in task_info:
                            late_start_date = self.controller.model.get_date_for_day(
                                task_info['late_start']
                            )
                            text_area.insert(
                                tk.END,
                                f"  Late Start: Day {task_info['late_start']} ({late_start_date.strftime('%Y-%m-%d')})\n",
                            )

                        if 'late_finish' in task_info:
                            late_finish_date = self.controller.model.get_date_for_day(
                                task_info['late_finish']
                            )
                            text_area.insert(
                                tk.END,
                                f"  Late Finish: Day {task_info['late_finish']} ({late_finish_date.strftime('%Y-%m-%d')})\n",
                            )

                        if 'float' in task_info:
                            text_area.insert(
                                tk.END, f"  Float: {task_info['float']} days\n"
                            )

                        text_area.insert(tk.END, '\n')
            else:
                text_area.insert(
                    tk.END, 'No critical path found in the selected tasks.\n\n'
                )
                text_area.insert(tk.END, 'Possible reasons:\n')
                text_area.insert(
                    tk.END, '- No dependencies between the selected tasks\n'
                )
                text_area.insert(
                    tk.END, '- Circular dependencies in the selected tasks\n'
                )
                text_area.insert(tk.END, '- Missing key tasks in the selection\n\n')
                text_area.insert(
                    tk.END,
                    "To define task dependencies, right-click on a task and select 'Add Predecessor' or 'Add Successor'.\n",
                )
                text_area.insert(
                    tk.END,
                    'To select multiple tasks, use Ctrl+click or enable multi-select mode from the Tags menu.',
                )

            # Make text area read-only
            text_area.config(state=tk.DISABLED)

            # Button frame to hold both buttons
            button_frame = tk.Frame(frame)
            button_frame.pack(pady=(10, 0))

            # Function to tag critical path tasks
            def tag_critical_path():
                if critical_path:
                    count = network_ops.tag_critical_path(critical_path)

                    # Show confirmation message
                    tk.messagebox.showinfo(
                        'Critical Path Tagged',
                        f"Added 'CriticalPath' tag to {count} tasks.",
                        parent=cp_dialog,
                    )

                    # Update view to refresh task display with new tags
                    self.controller.update_view()

            # Tag Critical Path button
            tag_button = tk.Button(
                button_frame,
                text='Tag Critical Path',
                command=tag_critical_path,
                width=15,
            )
            tag_button.pack(side=tk.LEFT, padx=5)

            # Close button
            close_button = tk.Button(
                button_frame, text='Close', command=cp_dialog.destroy, width=10
            )
            close_button.pack(side=tk.LEFT, padx=5)

            # Bind Escape key to close dialog
            cp_dialog.bind('<Escape>', lambda e: cp_dialog.destroy())

        except Exception as e:
            messagebox.showerror(
                'Critical Path Error', f'Error analyzing critical path: {str(e)}'
            )
