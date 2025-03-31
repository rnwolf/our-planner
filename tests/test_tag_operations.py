import pytest
from unittest.mock import MagicMock, patch

from src.model.task_resource_model import TaskResourceModel
from src.operations.tag_operations import TagOperations


class TestTagOperations:
    """Test cases for the TagOperations class."""

    def setup_method(self):
        """Set up a fresh model and mock controller for each test."""
        self.model = TaskResourceModel()
        self.controller = MagicMock()
        self.controller.model = self.model
        self.tag_ops = TagOperations(self.controller, self.model)

    def test_get_filtered_tasks_no_filters(self):
        """Test that get_filtered_tasks returns all tasks when no filters are active."""
        # Add a few sample tasks
        self.model.add_task(
            row=1, col=5, duration=3, description='Task 1', tags=['tag1', 'tag2']
        )
        self.model.add_task(
            row=2, col=10, duration=4, description='Task 2', tags=['tag2', 'tag3']
        )
        self.model.add_task(
            row=3, col=15, duration=5, description='Task 3', tags=['tag3', 'tag4']
        )

        # With no filters, should return all tasks
        filtered_tasks = self.tag_ops.get_filtered_tasks()
        assert len(filtered_tasks) == 3

    def test_get_filtered_tasks_with_filters(self):
        """Test that get_filtered_tasks correctly filters tasks by tags."""
        # Add a few sample tasks
        self.model.add_task(
            row=1, col=5, duration=3, description='Task 1', tags=['tag1', 'tag2']
        )
        self.model.add_task(
            row=2, col=10, duration=4, description='Task 2', tags=['tag2', 'tag3']
        )
        self.model.add_task(
            row=3, col=15, duration=5, description='Task 3', tags=['tag3', 'tag4']
        )

        # Set up filters
        self.tag_ops.task_tag_filters = ['tag2']
        self.tag_ops.task_match_all = False

        # Should return tasks with tag2
        filtered_tasks = self.tag_ops.get_filtered_tasks()
        assert len(filtered_tasks) == 2
        assert filtered_tasks[0]['description'] == 'Task 1'
        assert filtered_tasks[1]['description'] == 'Task 2'

        # Test with match_all=True
        self.tag_ops.task_tag_filters = ['tag2', 'tag3']
        self.tag_ops.task_match_all = True

        # Should return only tasks with both tag2 and tag3
        filtered_tasks = self.tag_ops.get_filtered_tasks()
        assert len(filtered_tasks) == 1
        assert filtered_tasks[0]['description'] == 'Task 2'

    def test_has_active_filters(self):
        """Test that has_active_filters returns the correct state."""
        # Initially no filters
        assert not self.tag_ops.has_active_filters()

        # Set task filters
        self.tag_ops.task_tag_filters = ['tag1']
        assert self.tag_ops.has_active_filters()

        # Clear task filters, set resource filters
        self.tag_ops.task_tag_filters = []
        self.tag_ops.resource_tag_filters = ['resource_tag']
        assert self.tag_ops.has_active_filters()

        # Clear all filters
        self.tag_ops.resource_tag_filters = []
        assert not self.tag_ops.has_active_filters()
