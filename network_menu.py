import tkinter as tk
from tkinter import messagebox, scrolledtext
import webbrowser
import networkx as nx
from datetime import datetime, timedelta


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
        menu_bar.add_cascade(label="Network", menu=self.network_menu)

        # Add menu items
        self.network_menu.add_command(
            label="Critical Path", command=self.show_critical_path
        )

    def show_critical_path(self):
        """Show the Critical Path dialog with analysis of the project network."""
        try:
            # Check if there are selected tasks
            selected_tasks = self.controller.selected_tasks

            # If no tasks are selected, show a message
            if not selected_tasks:
                messagebox.showinfo(
                    "No Tasks Selected",
                    "Please select tasks for critical path analysis.\n\n"
                    "You can select multiple tasks using Ctrl+click or by enabling multi-select mode.",
                )
                return

            # Create a dialog to display critical path information
            cp_dialog = tk.Toplevel(self.root)
            cp_dialog.title("Critical Path Analysis")
            cp_dialog.transient(self.root)
            cp_dialog.grab_set()

            # Make dialog modal
            cp_dialog.focus_set()

            # Position the dialog
            cp_dialog.geometry("700x600")

            # Center dialog on parent window
            cp_dialog.update_idletasks()
            width = cp_dialog.winfo_width()
            height = cp_dialog.winfo_height()
            x = self.root.winfo_rootx() + (self.root.winfo_width() - width) // 2
            y = self.root.winfo_rooty() + (self.root.winfo_height() - height) // 2
            cp_dialog.geometry(f"+{x}+{y}")

            # Add content
            frame = tk.Frame(cp_dialog, padx=20, pady=20)
            frame.pack(fill=tk.BOTH, expand=True)

            # Title
            title_label = tk.Label(
                frame, text="Critical Path Analysis", font=("Arial", 16, "bold")
            )
            title_label.pack(pady=(0, 15))

            # Create scrolled text area for results
            text_area = scrolledtext.ScrolledText(
                frame, wrap=tk.WORD, width=80, height=25
            )
            text_area.pack(fill=tk.BOTH, expand=True, pady=10)

            # Insert info about number of tasks analyzed
            text_area.insert(
                tk.END, f"Analyzing {len(selected_tasks)} selected tasks\n\n"
            )

            # Calculate critical path and display results
            critical_path, path_length, network_analysis = self.calculate_critical_path(
                selected_tasks
            )

            if critical_path:
                # Insert basic critical path info
                text_area.insert(tk.END, "Critical Path:\n\n")
                text_area.insert(tk.END, f"Path Length: {path_length} days\n\n")
                text_area.insert(tk.END, "Path: ")

                # Format the path with task descriptions
                path_items = []
                for task_id in critical_path:
                    task = self.controller.model.get_task(task_id)
                    if task:
                        path_items.append(f"Task {task_id} ({task['description']})")
                    else:
                        path_items.append(f"Task {task_id}")

                text_area.insert(tk.END, " → ".join(path_items) + "\n\n")

                # Insert detailed task analysis
                text_area.insert(tk.END, "Detailed Task Analysis:\n\n")
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

                        # Early/Late start/finish
                        if "early_start" in task_info:
                            early_start_date = self.controller.model.get_date_for_day(
                                task_info["early_start"]
                            )
                            text_area.insert(
                                tk.END,
                                f"  Early Start: Day {task_info['early_start']} ({early_start_date.strftime('%Y-%m-%d')})\n",
                            )

                        if "early_finish" in task_info:
                            early_finish_date = self.controller.model.get_date_for_day(
                                task_info["early_finish"]
                            )
                            text_area.insert(
                                tk.END,
                                f"  Early Finish: Day {task_info['early_finish']} ({early_finish_date.strftime('%Y-%m-%d')})\n",
                            )

                        if "late_start" in task_info:
                            late_start_date = self.controller.model.get_date_for_day(
                                task_info["late_start"]
                            )
                            text_area.insert(
                                tk.END,
                                f"  Late Start: Day {task_info['late_start']} ({late_start_date.strftime('%Y-%m-%d')})\n",
                            )

                        if "late_finish" in task_info:
                            late_finish_date = self.controller.model.get_date_for_day(
                                task_info["late_finish"]
                            )
                            text_area.insert(
                                tk.END,
                                f"  Late Finish: Day {task_info['late_finish']} ({late_finish_date.strftime('%Y-%m-%d')})\n",
                            )

                        if "float" in task_info:
                            text_area.insert(
                                tk.END, f"  Float: {task_info['float']} days\n"
                            )

                        text_area.insert(tk.END, "\n")
            else:
                text_area.insert(
                    tk.END, "No critical path found in the selected tasks.\n\n"
                )
                text_area.insert(tk.END, "Possible reasons:\n")
                text_area.insert(
                    tk.END, "- No dependencies between the selected tasks\n"
                )
                text_area.insert(
                    tk.END, "- Circular dependencies in the selected tasks\n"
                )
                text_area.insert(tk.END, "- Missing key tasks in the selection\n\n")
                text_area.insert(
                    tk.END,
                    "To define task dependencies, right-click on a task and select 'Add Predecessor' or 'Add Successor'.\n",
                )
                text_area.insert(
                    tk.END,
                    "To select multiple tasks, use Ctrl+click or enable multi-select mode from the Tags menu.",
                )

            # Make text area read-only
            text_area.config(state=tk.DISABLED)

            # # Close button
            # close_button = tk.Button(
            #     frame, text="Close", command=cp_dialog.destroy, width=10
            # )
            # close_button.pack(pady=(10, 0))

            # Button frame to hold both buttons
            button_frame = tk.Frame(frame)
            button_frame.pack(pady=(10, 0))

            # Function to tag critical path tasks
            def tag_critical_path():
                if critical_path:
                    # Add "CriticalPath" tag to each task in the critical path
                    for task_id in critical_path:
                        self.controller.model.add_tags_to_task(
                            task_id, ["CriticalPath"]
                        )

                    # Show confirmation message
                    tk.messagebox.showinfo(
                        "Critical Path Tagged",
                        f"Added 'CriticalPath' tag to {len(critical_path)} tasks.",
                        parent=cp_dialog,
                    )

                    # Update view to refresh task display with new tags
                    self.controller.update_view()

            # Tag Critical Path button
            tag_button = tk.Button(
                button_frame,
                text="Tag Critical Path",
                command=tag_critical_path,
                width=15,
            )
            tag_button.pack(side=tk.LEFT, padx=5)

            # Close button
            close_button = tk.Button(
                button_frame, text="Close", command=cp_dialog.destroy, width=10
            )
            close_button.pack(side=tk.LEFT, padx=5)

            # Bind Escape key to close dialog
            cp_dialog.bind("<Escape>", lambda e: cp_dialog.destroy())

        except Exception as e:
            messagebox.showerror(
                "Critical Path Error", f"Error analyzing critical path: {str(e)}"
            )

    def calculate_critical_path(self, selected_tasks=None):
        """Calculate the critical path using networkx.

        Args:
            selected_tasks: List of task dictionaries to analyze. If None, uses all tasks.

        Returns:
            tuple: (critical_path, path_length, network_analysis)
                critical_path: List of task IDs in the critical path
                path_length: Length of the critical path in days
                network_analysis: Dictionary with analysis results for each task
        """
        # Import networkx or display an error message if not available
        try:
            import networkx as nx
        except ImportError:
            messagebox.showwarning(
                "Missing Dependency",
                "NetworkX library is not installed. Please install it with 'pip install networkx'.",
            )
            return [], 0, {}

        # Get tasks to analyze
        tasks = (
            selected_tasks
            if selected_tasks is not None
            else self.controller.tag_ops.get_filtered_tasks()
        )
        if not tasks:
            return [], 0, {}

        # Create a directed graph
        G = nx.DiGraph()

        # Add nodes and edges
        for task in tasks:
            task_id = task["task_id"]
            duration = task["duration"]

            # Add task as a node with its duration as weight
            G.add_node(task_id, duration=duration, task=task)

            # Add edges only for dependencies within the selected tasks
            selected_task_ids = [t["task_id"] for t in tasks]

            # Add edges for dependencies (successors)
            for successor_id in task.get("successors", []):
                # Only add edge if the successor is in the selected tasks
                if successor_id in selected_task_ids:
                    G.add_edge(task_id, successor_id)

        # Check if graph is empty or has no edges
        # if not G.nodes or not G.edges:
        #     return [], 0, {}
        if not G.nodes:  # or not G.edges:
            return [], 0, {}

        # If no explicit dependencies, each task is its own critical path
        if not G.edges:
            # Find the task with the longest duration
            max_duration_task = max(tasks, key=lambda t: t["duration"])
            max_task_id = max_duration_task["task_id"]

            # Create a basic analysis for this task
            analysis = {
                max_task_id: {
                    "early_start": max_duration_task["col"],
                    "early_finish": max_duration_task["col"]
                    + max_duration_task["duration"],
                    "late_start": max_duration_task["col"],
                    "late_finish": max_duration_task["col"]
                    + max_duration_task["duration"],
                    "float": 0,
                }
            }

            return [max_task_id], max_duration_task["duration"], analysis

        # Check for cycles which would make critical path undefined
        try:
            cycles = list(nx.simple_cycles(G))
            if cycles:
                messagebox.showwarning(
                    "Circular Dependencies",
                    "The selected tasks contain circular dependencies, which makes critical path analysis impossible.",
                )
                return [], 0, {}
        except nx.NetworkXNoCycle:
            # No cycles detected, this is good
            pass

        # Find all root nodes (nodes with no predecessors)
        root_nodes = [node for node in G.nodes if G.in_degree(node) == 0]

        # Find all leaf nodes (nodes with no successors)
        leaf_nodes = [node for node in G.nodes if G.out_degree(node) == 0]

        # Add a virtual start and end node if multiple root/leaf nodes
        if len(root_nodes) > 1 or len(leaf_nodes) > 1:
            G.add_node("virtual_start", duration=0)
            G.add_node("virtual_end", duration=0)

            for node in root_nodes:
                G.add_edge("virtual_start", node)

            for node in leaf_nodes:
                G.add_edge(node, "virtual_end")

            source = "virtual_start"
            target = "virtual_end"
        else:
            source = root_nodes[0] if root_nodes else None
            target = leaf_nodes[0] if leaf_nodes else None

        if source is None or target is None:
            return [], 0, {}

        # Calculate early start and early finish times
        early_times = {}

        # Initialize
        for node in nx.topological_sort(G):
            early_times[node] = {"early_start": 0, "early_finish": 0}

        # Forward pass
        for node in nx.topological_sort(G):
            if node == source:
                early_times[node]["early_start"] = 0
            else:
                # Find maximum early finish of predecessors
                predecessors = list(G.predecessors(node))
                if predecessors:
                    early_times[node]["early_start"] = max(
                        early_times[pred]["early_finish"] for pred in predecessors
                    )

            # Calculate early finish
            duration = G.nodes[node].get("duration", 0)
            early_times[node]["early_finish"] = (
                early_times[node]["early_start"] + duration
            )

        # Initialize late times
        late_times = {}
        for node in G.nodes:
            late_times[node] = {"late_start": float("inf"), "late_finish": float("inf")}

        # Backward pass
        project_duration = early_times[target]["early_finish"]

        for node in reversed(list(nx.topological_sort(G))):
            if node == target:
                late_times[node]["late_finish"] = project_duration
            else:
                # Find minimum late start of successors
                successors = list(G.successors(node))
                if successors:
                    late_times[node]["late_finish"] = min(
                        late_times[succ]["late_start"] for succ in successors
                    )

            # Calculate late start
            duration = G.nodes[node].get("duration", 0)
            late_times[node]["late_start"] = late_times[node]["late_finish"] - duration

        # Calculate float and identify critical path
        critical_path_nodes = []
        network_analysis = {}

        for node in G.nodes:
            if node in ("virtual_start", "virtual_end"):
                continue

            float_time = (
                late_times[node]["late_start"] - early_times[node]["early_start"]
            )

            network_analysis[node] = {
                "early_start": early_times[node]["early_start"],
                "early_finish": early_times[node]["early_finish"],
                "late_start": late_times[node]["late_start"],
                "late_finish": late_times[node]["late_finish"],
                "float": float_time,
            }

            if float_time == 0:
                critical_path_nodes.append(node)

        # Order critical path nodes
        ordered_critical_path = []
        temp_graph = G.subgraph(critical_path_nodes).copy()

        # Remove virtual nodes from temp_graph
        for vnode in ["virtual_start", "virtual_end"]:
            if vnode in temp_graph:
                temp_graph.remove_node(vnode)

        # Find the actual path order
        if critical_path_nodes:
            try:
                ordered_critical_path = list(nx.topological_sort(temp_graph))
            except nx.NetworkXUnfeasible:
                # In case there are disjoint critical paths
                ordered_critical_path = sorted(
                    critical_path_nodes,
                    key=lambda n: early_times.get(n, {}).get("early_start", 0),
                )

        # Get calendar dates for tasks
        for task_id, analysis in network_analysis.items():
            task = self.controller.model.get_task(task_id)
            if task:
                for key in ["early_start", "early_finish", "late_start", "late_finish"]:
                    if key in analysis:
                        day = analysis[key]
                        date = self.controller.model.get_date_for_day(day)
                        analysis[f"{key}_date"] = date

        return ordered_critical_path, project_duration, network_analysis
