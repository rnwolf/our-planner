import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta

from src.model.task_resource_model import TaskResourceModel
from src.operations.task_operations import TaskOperations


class TestProjectStartDateUpdate:
    """Tests for project start date update functionality."""

    def setup_method(self):
        """Set up the test environment."""
        self.model = TaskResourceModel()
        self.controller = MagicMock()
        self.controller.model = self.model
        self.task_ops = TaskOperations(self.controller, self.model)

        # Set a fixed start date for testing
        self.model.start_date = datetime(2023, 1, 1)  # January 1, 2023

        # Create some test tasks
        # Task at column 0 (day 0 - Jan 1, 2023)
        self.task1 = self.model.add_task(
            row=0, col=0, duration=3, description='Task at start'
        )

        # Task at column 5 (day 5 - Jan 6, 2023)
        self.task2 = self.model.add_task(
            row=1, col=5, duration=5, description='Task in middle'
        )

        # Task at column 20 (day 20 - Jan 21, 2023)
        self.task3 = self.model.add_task(
            row=2, col=20, duration=10, description='Task at end'
        )

        # Add resource with custom capacities
        self.resource1 = {
            'id': 1,
            'name': 'Resource 1',
            'capacity': [1.0] * self.model.days,
            'tags': [],
            'works_weekends': True,
        }

        self.resource2 = {
            'id': 2,
            'name': 'Weekend Off Resource',
            'capacity': [1.0] * self.model.days,
            'tags': [],
            'works_weekends': False,
        }

        # Set some custom capacities
        self.resource1['capacity'][5] = 0.5  # Day 5 has 0.5 capacity
        self.resource1['capacity'][10] = 0.8  # Day 10 has 0.8 capacity

        # Set weekend capacities for resource 2
        for day in range(self.model.days):
            date = self.model.get_date_for_day(day)
            if date.weekday() >= 5:  # 5=Saturday, 6=Sunday
                self.resource2['capacity'][day] = 0.0

        # Replace model resources
        self.model.resources = [self.resource1, self.resource2]

    @patch('tkinter.messagebox.askyesno')
    def test_start_date_no_change(self, mock_askyesno):
        """Test when the start date doesn't change."""
        # Test with the same date - no change
        same_date = datetime(2023, 1, 1)
        result = self.task_ops.update_project_start_date(same_date)

        # Should return True and not prompt the user
        assert result is True
        mock_askyesno.assert_not_called()

        # Tasks should be unchanged
        assert self.model.get_task(self.task1['task_id'])['col'] == 0
        assert self.model.get_task(self.task2['task_id'])['col'] == 5
        assert self.model.get_task(self.task3['task_id'])['col'] == 20

    @patch('tkinter.messagebox.askyesno')
    def test_no_task_shift_when_user_declines(self, mock_askyesno):
        """Test when user chooses not to shift tasks."""
        # User selects "No" to adjusting tasks
        mock_askyesno.return_value = False

        # Move date forward by 5 days
        new_date = datetime(2023, 1, 6)  # January 6, 2023
        result = self.task_ops.update_project_start_date(new_date)

        # Should return True and only update the start date
        assert result is True
        mock_askyesno.assert_called_once()
        assert self.model.start_date == new_date

        # Tasks should remain in their original column positions
        assert self.model.get_task(self.task1['task_id'])['col'] == 0
        assert self.model.get_task(self.task2['task_id'])['col'] == 5
        assert self.model.get_task(self.task3['task_id'])['col'] == 20

    @patch('tkinter.messagebox.askyesno')
    def test_shift_tasks_forward(self, mock_askyesno):
        """Test shifting tasks when date moves forward."""
        # User selects "Yes" to adjusting tasks and "Yes" to deleting tasks
        mock_askyesno.return_value = True

        # Move date forward by 5 days
        new_date = datetime(2023, 1, 6)  # January 6, 2023
        result = self.task_ops.update_project_start_date(new_date)

        # Should return True and update start date
        assert result is True
        assert self.model.start_date == new_date

        # Tasks should be shifted left by 5 columns
        # First task should be deleted as it would be before the new start date
        assert self.model.get_task(self.task1['task_id']) is None

        # Second task should now be at col 0 (5 - 5)
        assert self.model.get_task(self.task2['task_id'])['col'] == 0

        # Third task should now be at col 15 (20 - 5)
        assert self.model.get_task(self.task3['task_id'])['col'] == 15

    @patch('tkinter.messagebox.askyesno')
    def test_shift_tasks_backward(self, mock_askyesno):
        """Test shifting tasks when date moves backward."""
        # User selects "Yes" to adjusting tasks
        mock_askyesno.return_value = True

        # Move date backward by 5 days
        new_date = datetime(2022, 12, 27)  # December 27, 2022
        result = self.task_ops.update_project_start_date(new_date)

        # Should return True and update start date
        assert result is True
        assert self.model.start_date == new_date

        # Tasks should be shifted right by 5 columns
        # First task should now be at col 5 (0 + 5)
        assert self.model.get_task(self.task1['task_id'])['col'] == 5

        # Second task should now be at col 10 (5 + 5)
        assert self.model.get_task(self.task2['task_id'])['col'] == 10

        # Third task should now be at col 25 (20 + 5)
        assert self.model.get_task(self.task3['task_id'])['col'] == 25

    @patch('tkinter.messagebox.askyesno')
    def test_resource_capacity_shift_forward(self, mock_askyesno):
        """Test resource capacity shifting when date moves forward."""
        # User selects "Yes" to adjusting tasks
        mock_askyesno.return_value = True

        # Original capacity values to check
        original_day5_capacity = self.resource1['capacity'][5]  # 0.5
        original_day10_capacity = self.resource1['capacity'][10]  # 0.8

        # Move date forward by 5 days
        new_date = datetime(2023, 1, 6)  # January 6, 2023
        self.task_ops.update_project_start_date(new_date)

        # Resource capacities should shift left by 5 days
        # Day 5 capacity (0.5) should now be at day 0
        assert self.resource1['capacity'][0] == original_day5_capacity

        # Day 10 capacity (0.8) should now be at day 5
        assert self.resource1['capacity'][5] == original_day10_capacity

    @patch('tkinter.messagebox.askyesno')
    def test_resource_capacity_shift_backward(self, mock_askyesno):
        """Test resource capacity shifting when date moves backward."""
        # User selects "Yes" to adjusting tasks
        mock_askyesno.return_value = True

        # Original capacity values to check
        original_day5_capacity = self.resource1['capacity'][5]  # 0.5
        original_day10_capacity = self.resource1['capacity'][10]  # 0.8

        # Move date backward by 5 days
        new_date = datetime(2022, 12, 27)  # December 27, 2022
        self.task_ops.update_project_start_date(new_date)

        # Resource capacities should shift right by 5 days
        # Day 5 capacity (0.5) should now be at day 10
        assert self.resource1['capacity'][10] == original_day5_capacity

        # Day 10 capacity (0.8) should now be at day 15
        assert self.resource1['capacity'][15] == original_day10_capacity

    @patch('tkinter.messagebox.askyesno')
    def test_weekend_resource_capacity_generation(self, mock_askyesno):
        """Test weekend capacity handling for resources that don't work weekends."""
        # User selects "Yes" to adjusting tasks
        mock_askyesno.return_value = True

        # Move date backward to ensure we generate new days
        new_date = datetime(2022, 12, 27)  # December 27, 2022
        self.task_ops.update_project_start_date(new_date)

        # Check the first 5 days (Dec 27-31, 2022) which are newly generated
        # Dec 31, 2022 is a Saturday (weekday 5)
        saturday_index = 4  # Dec 31 is 4 days after Dec 27

        # Resource 1 works weekends, so capacity should be 1.0
        assert self.resource1['capacity'][saturday_index] == 1.0

        # Resource 2 doesn't work weekends, so capacity should be 0.0
        assert self.resource2['capacity'][saturday_index] == 0.0

        # Check a regular weekday
        weekday_index = 2  # Dec 29 is a Thursday
        assert self.resource2['capacity'][weekday_index] == 1.0

    @patch('tkinter.messagebox.askyesno')
    def test_task_deletion_cancellation(self, mock_askyesno):
        """Test cancellation when a task would be deleted."""
        # First "Yes" for shifting tasks, then "No" for deleting a task
        mock_askyesno.side_effect = [True, False]

        # Move date forward by 5 days
        new_date = datetime(2023, 1, 6)  # January 6, 2023
        result = self.task_ops.update_project_start_date(new_date)

        # Should return False as user cancelled task deletion
        assert result is False

        # Start date and tasks should remain unchanged
        assert self.model.start_date == datetime(2023, 1, 1)
        assert self.model.get_task(self.task1['task_id'])['col'] == 0
        assert self.model.get_task(self.task2['task_id'])['col'] == 5
        assert self.model.get_task(self.task3['task_id'])['col'] == 20

    @patch('tkinter.messagebox.askyesno')
    def test_task_truncation_choice(self, mock_askyesno):
        """Test task truncation when they would extend beyond timeline."""
        # Set up askyesno to return: Yes for shifting tasks, Yes for truncating task
        mock_askyesno.side_effect = [True, True]

        # First move tasks near the edge, then decrease timeline days
        self.model.days = 30  # Limit the timeline to 30 days

        # Move date backward by 5 days, pushing task3 to edge
        new_date = datetime(2022, 12, 27)  # December 27, 2022
        result = self.task_ops.update_project_start_date(new_date)

        # Should return True and update start date
        assert result is True

        # Task3 would go from col 20 to col 25 with duration 10,
        # which would exceed the timeline (col 25+10 = 35 > 30)
        # Since we chose to truncate, it should be shortened
        task3 = self.model.get_task(self.task3['task_id'])
        assert task3['col'] == 25
        assert task3['duration'] == 5  # Truncated to fit within timeline
