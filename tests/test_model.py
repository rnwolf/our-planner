import pytest
from datetime import datetime, timedelta

from src.model.task_resource_model import TaskResourceModel


class TestTaskResourceModel:
    """Test cases for the TaskResourceModel class."""

    def setup_method(self):
        """Set up a fresh model instance for each test."""
        self.model = TaskResourceModel()

    def test_model_initialization(self):
        """Test that the model initializes with correct default values."""
        assert self.model.days == 100
        assert self.model.max_rows == 50
        assert isinstance(self.model.start_date, datetime)
        assert isinstance(self.model.setdate, datetime)
        assert len(self.model.resources) == 10  # Default resources
        assert len(self.model.tasks) == 0  # No tasks by default

    def test_add_task(self):
        """Test adding a task to the model."""
        # Add a simple task
        task = self.model.add_task(
            row=1,
            col=5,
            duration=3,
            description='Test Task',
            resources={},
            url='https://example.com',
            tags=['test', 'example'],
        )

        # Verify task was added correctly
        assert len(self.model.tasks) == 1
        assert task['task_id'] == 1
        assert task['row'] == 1
        assert task['col'] == 5
        assert task['duration'] == 3
        assert task['description'] == 'Test Task'
        assert task['url'] == 'https://example.com'
        assert task['tags'] == ['test', 'example']

        # Verify tags were added to the model's all_tags set
        assert 'test' in self.model.all_tags
        assert 'example' in self.model.all_tags

    def test_get_date_for_day(self):
        """Test that get_date_for_day returns the correct date."""
        # Set a specific start date for predictable testing
        self.model.start_date = datetime(2023, 1, 1)

        # Test day 0 (should be start date)
        assert self.model.get_date_for_day(0) == datetime(2023, 1, 1)

        # Test day 10
        assert self.model.get_date_for_day(10) == datetime(2023, 1, 11)

        # Test last day
        assert self.model.get_date_for_day(99) == datetime(2023, 4, 10)

    def test_delete_task(self):
        """Test deleting a task from the model."""
        # Add a task
        task = self.model.add_task(row=1, col=5, duration=3, description='Test Task')
        task_id = task['task_id']

        # Verify task was added
        assert len(self.model.tasks) == 1

        # Delete the task
        result = self.model.delete_task(task_id)

        # Verify task was deleted
        assert result is True
        assert len(self.model.tasks) == 0

        # Try to delete a non-existent task
        result = self.model.delete_task(999)
        assert result is False
