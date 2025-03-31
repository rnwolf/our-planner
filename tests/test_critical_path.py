import pytest
from unittest.mock import MagicMock, patch
import networkx as nx

from src.model.task_resource_model import TaskResourceModel
from src.operations.network_operations import NetworkOperations


class TestCriticalPath:
    """Tests for critical path analysis."""

    def setup_method(self):
        """Set up the test environment."""
        self.model = TaskResourceModel()
        self.controller = MagicMock()
        self.controller.model = self.model
        self.controller.tag_ops = MagicMock()

        # Create the network operations instance instead of network menu
        self.network_ops = NetworkOperations(self.controller, self.model)

    def test_calculate_critical_path_simple_chain(self):
        """Test critical path calculation for a simple chain of tasks."""
        # Set up a simple project with sequential tasks
        task1 = self.model.add_task(row=0, col=0, duration=2, description='Task 1')
        task2 = self.model.add_task(row=1, col=2, duration=3, description='Task 2')
        task3 = self.model.add_task(row=2, col=5, duration=4, description='Task 3')

        # Set up dependencies: 1 -> 2 -> 3
        self.model.add_successor(task1['task_id'], task2['task_id'])
        self.model.add_successor(task2['task_id'], task3['task_id'])

        # Create list of selected tasks
        selected_tasks = [task1, task2, task3]

        # Calculate critical path with the selected tasks
        path, length, analysis = self.network_ops.calculate_critical_path(
            selected_tasks
        )

        # The critical path should include all tasks
        assert len(path) == 3
        assert task1['task_id'] in path
        assert task2['task_id'] in path
        assert task3['task_id'] in path

        # The path length should be the sum of durations
        assert length == 9  # 2 + 3 + 4 = 9

        # Check that analysis contains data for all tasks
        assert len(analysis) == 3
        assert task1['task_id'] in analysis
        assert task2['task_id'] in analysis
        assert task3['task_id'] in analysis

        # Check float is 0 for all tasks in critical path
        assert analysis[task1['task_id']]['float'] == 0
        assert analysis[task2['task_id']]['float'] == 0
        assert analysis[task3['task_id']]['float'] == 0

    def test_calculate_critical_path_with_parallel_tasks(self):
        """Test critical path calculation with parallel tasks."""
        # Create a project with parallel paths
        # A -> B -> D
        # A -> C -> D
        # where B has duration 5 and C has duration 3

        task_a = self.model.add_task(row=0, col=0, duration=2, description='Task A')
        task_b = self.model.add_task(row=1, col=2, duration=5, description='Task B')
        task_c = self.model.add_task(row=2, col=2, duration=3, description='Task C')
        task_d = self.model.add_task(row=3, col=7, duration=4, description='Task D')

        # Set up dependencies
        self.model.add_successor(task_a['task_id'], task_b['task_id'])
        self.model.add_successor(task_a['task_id'], task_c['task_id'])
        self.model.add_successor(task_b['task_id'], task_d['task_id'])
        self.model.add_successor(task_c['task_id'], task_d['task_id'])

        # Create list of selected tasks
        selected_tasks = [task_a, task_b, task_c, task_d]

        # Calculate critical path with the selected tasks
        path, length, analysis = self.network_ops.calculate_critical_path(
            selected_tasks
        )

        # Critical path should be A -> B -> D (longer path)
        assert len(path) == 3
        assert task_a['task_id'] in path
        assert (
            task_b['task_id'] in path
        )  # B is on critical path as it's the longer path
        assert task_d['task_id'] in path
        assert task_c['task_id'] not in path  # C is not on critical path

        # Length should be sum of durations on critical path
        assert length == 11  # 2 + 5 + 4 = 11

        # Check float values
        assert analysis[task_a['task_id']]['float'] == 0  # A is on critical path
        assert analysis[task_b['task_id']]['float'] == 0  # B is on critical path
        assert analysis[task_c['task_id']]['float'] == 2  # C has float = (5-3) = 2
        assert analysis[task_d['task_id']]['float'] == 0  # D is on critical path

    def test_calculate_critical_path_no_dependencies(self):
        """Test critical path calculation when there are no dependencies."""
        # Create tasks without dependencies
        task1 = self.model.add_task(row=0, col=0, duration=2, description='Task 1')
        task2 = self.model.add_task(
            row=1,
            col=2,
            duration=5,
            description='Task 2',  # Longest duration
        )
        task3 = self.model.add_task(row=2, col=5, duration=3, description='Task 3')

        # Create list of selected tasks
        selected_tasks = [task1, task2, task3]

        # Calculate critical path
        path, length, analysis = self.network_ops.calculate_critical_path(
            selected_tasks
        )

        # With no dependencies, the critical path should be the longest task
        assert len(path) == 1
        assert task2['task_id'] in path  # Task 2 has the longest duration
        assert length == 5  # Duration of Task 2
