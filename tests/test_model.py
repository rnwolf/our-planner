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

    def test_delete_task_removes_dangling_predecessor_links(self):
        """Deleting a task must strip it from other tasks' predecessor lists."""
        a = self.model.add_task(row=1, col=1, duration=3, description='A')
        b = self.model.add_task(row=2, col=5, duration=3, description='B')
        c = self.model.add_task(row=3, col=9, duration=3, description='C')

        # B depends on A (plain FS) and C depends on both A (SS+2) and B
        self.model.add_predecessor(b['task_id'], a['task_id'])
        self.model.add_predecessor(c['task_id'], a['task_id'], link_type='SS', lag=2)
        self.model.add_predecessor(c['task_id'], b['task_id'])

        assert self.model.delete_task(a['task_id']) is True

        # No remaining task may still reference A
        assert self.model.get_predecessor_ids(b['task_id']) == []
        assert self.model.get_predecessor_ids(c['task_id']) == [b['task_id']]

        # Successor derivation stays consistent too
        assert self.model.get_successor_ids(b['task_id']) == [c['task_id']]
