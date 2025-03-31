import pytest
import os
import json
import tempfile
from unittest.mock import MagicMock, patch
import tkinter as tk

from src.model.task_resource_model import TaskResourceModel
from src.operations.task_operations import TaskOperations
from src.operations.file_operations import FileOperations


class TestScenarios:
    """Integration tests for common application scenarios."""

    def setup_method(self):
        """Set up the test environment with mock UI and controller."""
        # Create root and controller mocks
        self.root = MagicMock()
        self.controller = MagicMock()

        # Create a real model
        self.model = TaskResourceModel()
        self.controller.model = self.model

        # Set up task operations with mock controller
        self.task_ops = TaskOperations(self.controller, self.model)

        # Set up file operations with mock controller
        self.file_ops = FileOperations(self.controller, self.model)

    def test_create_save_tasks_with_dependencies(self):
        """
        Scenario: Create new file, tasks and saves to file.
        1 - Creates a new task grid
        2 - Adds some tasks
        3 - Add dependency between two tasks
        4 - Saves the tasks to file
        5 - checks that the saved file contains the expected task information.
        """
        # 1. Create a new task grid (reset the model)
        with patch('tkinter.messagebox.askyesno', return_value=True):
            self.file_ops.new_project()

        # Verify model was reset
        assert len(self.model.tasks) == 0

        # 2. Add some tasks
        task1 = self.model.add_task(
            row=0,  # 0-based index (displays as row 1 in UI)
            col=4,  # 0-based index (displays as column 5 in UI)
            duration=3,
            description='Task 1',
            resources={},
            tags=['test'],
        )

        task2 = self.model.add_task(
            row=1,  # 0-based index (displays as row 2 in UI)
            col=9,  # 0-based index (displays as column 10 in UI)
            duration=4,
            description='Task 2',
            resources={},
            tags=['test'],
        )

        # Verify tasks were added
        assert len(self.model.tasks) == 2
        assert task1['task_id'] == 1
        assert task2['task_id'] == 2

        # 3. Add dependency between the tasks
        self.model.add_predecessor(task2['task_id'], task1['task_id'])

        # Verify dependency was added
        assert task1['task_id'] in task2['predecessors']
        assert task2['task_id'] in task1['successors']

        # 4. Save the tasks to a temporary file
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as temp:
            temp_path = temp.name

        try:
            result = self.model.save_to_file(temp_path)
            assert result is True

            # 5. Check that the saved file contains the expected task information
            with open(temp_path, 'r') as f:
                saved_data = json.load(f)

            # Verify the saved data
            assert 'tasks' in saved_data
            assert len(saved_data['tasks']) == 2

            # Find the tasks in the saved data
            saved_task1 = None
            saved_task2 = None
            for task in saved_data['tasks']:
                if task['task_id'] == 1:
                    saved_task1 = task
                elif task['task_id'] == 2:
                    saved_task2 = task

            assert saved_task1 is not None, 'Task 1 not found in saved data'
            assert saved_task2 is not None, 'Task 2 not found in saved data'

            # Verify task details
            assert saved_task1['description'] == 'Task 1'
            assert saved_task1['row'] == 0  # 0-based index (displays as row 1 in UI)
            assert saved_task1['col'] == 4  # 0-based index (displays as column 5 in UI)
            assert saved_task1['duration'] == 3
            assert saved_task1['tags'] == ['test']
            assert saved_task1['successors'] == [2]

            assert saved_task2['description'] == 'Task 2'
            assert saved_task2['row'] == 1  # 0-based index (displays as row 2 in UI)
            assert (
                saved_task2['col'] == 9
            )  # 0-based index (displays as column 10 in UI)
            assert saved_task2['duration'] == 4
            assert saved_task2['tags'] == ['test']
            assert saved_task2['predecessors'] == [1]

        finally:
            # Clean up
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_task_shifting(self):
        """
        Scenario: Create new file, three tasks in a row, moves first one column and other tasks get shifted along.

        1 - Creates a new task grid
        2 - Adds three tasks in one row all next to each other
        3 - Move the first task to the right by one column
        4 - Check that tasks to the right of the first have shifted to the left
        """
        # 1. Create a new task grid (reset the model)
        with patch('tkinter.messagebox.askyesno', return_value=True):
            self.file_ops.new_project()

        # Verify model was reset
        assert len(self.model.tasks) == 0

        # 2. Add three tasks in one row all next to each other
        # Task at column 5 (0-based index 4), duration 3
        task1 = self.model.add_task(
            row=0,  # 0-based index (displays as row 1 in UI)
            col=4,  # 0-based index (displays as column 5 in UI)
            duration=3,
            description='Task A',
        )

        # Task at column 8 (0-based index 7) right after task1, duration 2
        task2 = self.model.add_task(
            row=0,  # 0-based index (displays as row 1 in UI)
            col=7,  # 0-based index (displays as column 8 in UI)
            duration=2,
            description='Task B',
        )

        # Task at column 10 (0-based index 9) right after task2, duration 4
        task3 = self.model.add_task(
            row=0,  # 0-based index (displays as row 1 in UI)
            col=9,  # 0-based index (displays as column 10 in UI)
            duration=4,
            description='Task C',
        )

        # Verify tasks were added in correct positions
        assert task1['col'] == 4  # 0-based index (displays as column 5 in UI)
        assert task1['duration'] == 3
        assert task2['col'] == 7  # 0-based index (displays as column 8 in UI)
        assert task2['duration'] == 2
        assert task3['col'] == 9  # 0-based index (displays as column 10 in UI)
        assert task3['duration'] == 4

        # Set up controller properties for UI calculations
        self.controller.cell_width = 45  # Assuming cell_width is 45
        self.controller.task_height = 30  # Assuming task_height is 30

        # Create UI elements for each task with proper details
        task1_ui = {
            'x1': task1['col'] * self.controller.cell_width,
            'y1': task1['row'] * self.controller.task_height,
            'x2': (task1['col'] + task1['duration']) * self.controller.cell_width,
            'y2': (task1['row'] + 1) * self.controller.task_height,
            'connector_x': (task1['col'] + task1['duration'])
            * self.controller.cell_width,
            'connector_y': (task1['row'] * self.controller.task_height) + 15,
            'box': MagicMock(),
            'left_edge': MagicMock(),
            'right_edge': MagicMock(),
            'text': MagicMock(),
            'connector': MagicMock(),
        }

        task2_ui = {
            'x1': task2['col'] * self.controller.cell_width,
            'y1': task2['row'] * self.controller.task_height,
            'x2': (task2['col'] + task2['duration']) * self.controller.cell_width,
            'y2': (task2['row'] + 1) * self.controller.task_height,
            'connector_x': (task2['col'] + task2['duration'])
            * self.controller.cell_width,
            'connector_y': (task2['row'] * self.controller.task_height) + 15,
            'box': MagicMock(),
            'left_edge': MagicMock(),
            'right_edge': MagicMock(),
            'text': MagicMock(),
            'connector': MagicMock(),
        }

        task3_ui = {
            'x1': task3['col'] * self.controller.cell_width,
            'y1': task3['row'] * self.controller.task_height,
            'x2': (task3['col'] + task3['duration']) * self.controller.cell_width,
            'y2': (task3['row'] + 1) * self.controller.task_height,
            'connector_x': (task3['col'] + task3['duration'])
            * self.controller.cell_width,
            'connector_y': (task3['row'] * self.controller.task_height) + 15,
            'box': MagicMock(),
            'left_edge': MagicMock(),
            'right_edge': MagicMock(),
            'text': MagicMock(),
            'connector': MagicMock(),
        }

        # Mock the controller's UI elements dictionary with complete task UI info
        self.controller.ui.task_ui_elements = {
            task1['task_id']: task1_ui,
            task2['task_id']: task2_ui,
            task3['task_id']: task3_ui,
        }

        # Define a mock implementation of get_task_ui_coordinates
        def mock_get_task_ui_coordinates(task):
            task_id = task['task_id']
            ui_elements = self.controller.ui.task_ui_elements.get(task_id)
            if ui_elements:
                return (
                    ui_elements['x1'],
                    ui_elements['y1'],
                    ui_elements['x2'],
                    ui_elements['y2'],
                )
            # Calculate coordinates if UI elements not found
            x1 = task['col'] * self.controller.cell_width
            y1 = task['row'] * self.controller.task_height
            x2 = (task['col'] + task['duration']) * self.controller.cell_width
            y2 = y1 + self.controller.task_height
            return x1, y1, x2, y2

        # Assign the mock method to the controller
        self.controller.get_task_ui_coordinates = mock_get_task_ui_coordinates

        # 3. Move task1 one column to the right to create a collision
        task1['col'] = 5  # Move one column to the right (from 4 to 5)

        # Update UI element positions to match
        task1_ui['x1'] = task1['col'] * self.controller.cell_width
        task1_ui['x2'] = (task1['col'] + task1['duration']) * self.controller.cell_width
        task1_ui['connector_x'] = task1_ui['x2']

        # Use the actual TaskOperations.handle_task_collisions method
        task_ops = TaskOperations(self.controller, self.model)
        task_ops.handle_task_collisions(
            task1, task1_ui['x1'], task1_ui['y1'], task1_ui['x2'], task1_ui['y2']
        )

        # 4. Verify the results
        # Refresh tasks from model
        task1 = self.model.get_task(task1['task_id'])
        task2 = self.model.get_task(task2['task_id'])
        task3 = self.model.get_task(task3['task_id'])

        # Task1 should still be at column 5
        assert task1['col'] == 5, f"Expected task1 column to be 5, got {task1['col']}"

        # Task2 should have shifted right to avoid overlap with task1
        # Original position was 7, but task1 now ends at col 8 (5+3), so task2 should start at col 8
        assert task2['col'] == 8, f"Expected task2 column to be 8, got {task2['col']}"

        # Task3 should have also shifted if task2 now overlaps with it
        # If task2 is at col 8 with duration 2, it ends at col 10, so task3 should be at col 10 or later
        if task2['col'] + task2['duration'] > task3['col']:
            assert (
                task3['col'] >= task2['col'] + task2['duration']
            ), f"Expected task3 column to be at least {task2['col'] + task2['duration']}, got {task3['col']}"
