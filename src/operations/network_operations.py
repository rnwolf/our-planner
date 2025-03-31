"""
Network operations for Task Resource Manager.

This module contains business logic for network analysis, including
critical path calculations and other network-based operations.
"""

import networkx as nx
from datetime import datetime, timedelta


class NetworkOperations:
    """Operations related to network analysis of tasks."""

    def __init__(self, controller, model):
        """Initialize with controller and model references."""
        self.controller = controller
        self.model = model

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
        # Import networkx or return empty results if not available
        try:
            import networkx as nx
        except ImportError:
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
            task_id = task['task_id']
            duration = task['duration']

            # Add task as a node with its duration as weight
            G.add_node(task_id, duration=duration, task=task)

            # Add edges only for dependencies within the selected tasks
            selected_task_ids = [t['task_id'] for t in tasks]

            # Add edges for dependencies (successors)
            for successor_id in task.get('successors', []):
                # Only add edge if the successor is in the selected tasks
                if successor_id in selected_task_ids:
                    G.add_edge(task_id, successor_id)

        # Check if graph is empty or has no edges
        if not G.nodes:
            return [], 0, {}

        # If no explicit dependencies, each task is its own critical path
        if not G.edges:
            # Find the task with the longest duration
            max_duration_task = max(tasks, key=lambda t: t['duration'])
            max_task_id = max_duration_task['task_id']

            # Create a basic analysis for this task
            analysis = {
                max_task_id: {
                    'early_start': max_duration_task['col'],
                    'early_finish': max_duration_task['col']
                    + max_duration_task['duration'],
                    'late_start': max_duration_task['col'],
                    'late_finish': max_duration_task['col']
                    + max_duration_task['duration'],
                    'float': 0,
                }
            }

            return [max_task_id], max_duration_task['duration'], analysis

        # Check for cycles which would make critical path undefined
        try:
            cycles = list(nx.simple_cycles(G))
            if cycles:
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
            G.add_node('virtual_start', duration=0)
            G.add_node('virtual_end', duration=0)

            for node in root_nodes:
                G.add_edge('virtual_start', node)

            for node in leaf_nodes:
                G.add_edge(node, 'virtual_end')

            source = 'virtual_start'
            target = 'virtual_end'
        else:
            source = root_nodes[0] if root_nodes else None
            target = leaf_nodes[0] if leaf_nodes else None

        if source is None or target is None:
            return [], 0, {}

        # Calculate early start and early finish times
        early_times = {}

        # Initialize
        for node in nx.topological_sort(G):
            early_times[node] = {'early_start': 0, 'early_finish': 0}

        # Forward pass
        for node in nx.topological_sort(G):
            if node == source:
                early_times[node]['early_start'] = 0
            else:
                # Find maximum early finish of predecessors
                predecessors = list(G.predecessors(node))
                if predecessors:
                    early_times[node]['early_start'] = max(
                        early_times[pred]['early_finish'] for pred in predecessors
                    )

            # Calculate early finish
            duration = G.nodes[node].get('duration', 0)
            early_times[node]['early_finish'] = (
                early_times[node]['early_start'] + duration
            )

        # Initialize late times
        late_times = {}
        for node in G.nodes:
            late_times[node] = {'late_start': float('inf'), 'late_finish': float('inf')}

        # Backward pass
        project_duration = early_times[target]['early_finish']

        for node in reversed(list(nx.topological_sort(G))):
            if node == target:
                late_times[node]['late_finish'] = project_duration
            else:
                # Find minimum late start of successors
                successors = list(G.successors(node))
                if successors:
                    late_times[node]['late_finish'] = min(
                        late_times[succ]['late_start'] for succ in successors
                    )

            # Calculate late start
            duration = G.nodes[node].get('duration', 0)
            late_times[node]['late_start'] = late_times[node]['late_finish'] - duration

        # Calculate float and identify critical path
        critical_path_nodes = []
        network_analysis = {}

        for node in G.nodes:
            if node in ('virtual_start', 'virtual_end'):
                continue

            float_time = (
                late_times[node]['late_start'] - early_times[node]['early_start']
            )

            network_analysis[node] = {
                'early_start': early_times[node]['early_start'],
                'early_finish': early_times[node]['early_finish'],
                'late_start': late_times[node]['late_start'],
                'late_finish': late_times[node]['late_finish'],
                'float': float_time,
            }

            if float_time == 0:
                critical_path_nodes.append(node)

        # Order critical path nodes
        ordered_critical_path = []
        temp_graph = G.subgraph(critical_path_nodes).copy()

        # Remove virtual nodes from temp_graph
        for vnode in ['virtual_start', 'virtual_end']:
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
                    key=lambda n: early_times.get(n, {}).get('early_start', 0),
                )

        # Get calendar dates for tasks
        for task_id, analysis in network_analysis.items():
            task = self.model.get_task(task_id)
            if task:
                for key in ['early_start', 'early_finish', 'late_start', 'late_finish']:
                    if key in analysis:
                        day = analysis[key]
                        date = self.model.get_date_for_day(day)
                        analysis[f'{key}_date'] = date

        return ordered_critical_path, project_duration, network_analysis

    def tag_critical_path(self, critical_path):
        """Add 'CriticalPath' tag to tasks on the critical path.

        Args:
            critical_path: List of task IDs in the critical path

        Returns:
            int: Number of tasks tagged
        """
        if not critical_path:
            return 0

        # Add "CriticalPath" tag to each task in the critical path
        count = 0
        for task_id in critical_path:
            if self.model.add_tags_to_task(task_id, ['CriticalPath']):
                count += 1

        return count
