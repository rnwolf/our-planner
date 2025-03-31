import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta

from src.model.task_resource_model import TaskResourceModel
from src.operations.task_operations import TaskOperations


class TestResourceCapacity:
    """Tests for resource capacity functionality."""

    def setup_method(self):
        """Set up the test environment."""
        self.model = TaskResourceModel()
        self.controller = MagicMock()
        self.controller.model = self.model
        self.task_ops = TaskOperations(self.controller, self.model)

    def test_resource_capacity_initialization(self):
        """Test that resource capacities are initialized correctly."""
        # Check default resources
        assert len(self.model.resources) > 0

        # Verify each resource has capacity array of correct length
        for resource in self.model.resources:
            assert 'capacity' in resource
            assert len(resource['capacity']) == self.model.days

            # Default capacity should be 1.0
            assert resource['capacity'][0] == 1.0
            assert resource['capacity'][-1] == 1.0

    def test_update_resource_capacity_single_day(self):
        """Test updating capacity for a single day."""
        # Get the first resource
        resource = self.model.resources[0]
        resource_id = resource['id']

        # Update capacity for day 5
        new_capacity = 2.5
        day_index = 5

        result = self.model.update_resource_capacity(
            resource_id, day_index, new_capacity
        )
        assert result is True

        # Verify the capacity was updated
        updated_resource = self.model.get_resource_by_id(resource_id)
        assert updated_resource['capacity'][day_index] == new_capacity

        # Other days should remain unchanged
        assert updated_resource['capacity'][day_index - 1] == 1.0
        assert updated_resource['capacity'][day_index + 1] == 1.0

    def test_update_resource_capacity_range(self):
        """Test updating capacity for a range of days."""
        # Get the first resource
        resource = self.model.resources[0]
        resource_id = resource['id']

        # Update capacity for days 10-15
        new_capacity = 0.5
        start_day = 10
        end_day = 15

        result = self.model.update_resource_capacity_range(
            resource_id, start_day, end_day, new_capacity
        )
        assert result is True

        # Verify the capacity was updated for all days in the range
        updated_resource = self.model.get_resource_by_id(resource_id)
        for day in range(start_day, end_day):
            assert updated_resource['capacity'][day] == new_capacity

        # Days outside the range should remain unchanged
        assert updated_resource['capacity'][start_day - 1] == 1.0
        assert updated_resource['capacity'][end_day] == 1.0  # end_day is exclusive

    def test_calculate_resource_loading(self):
        """Test calculation of resource loading based on task assignments."""
        # Create a resource
        self.model.resources = []
        resource = {
            'id': 1,
            'name': 'Test Resource',
            'capacity': [1.0] * self.model.days,
            'tags': [],
        }
        self.model.resources.append(resource)

        # Create tasks with resource assignments
        # Task 1: days 0-2 with 0.5 allocation
        task1 = self.model.add_task(
            row=0,
            col=0,
            duration=3,
            description='Task 1',
            resources={1: 0.5},  # Resource 1 with 0.5 allocation
        )

        # Task 2: days 1-3 with 0.7 allocation (overlapping with Task 1 on day 1-2)
        task2 = self.model.add_task(
            row=1,
            col=1,
            duration=3,
            description='Task 2',
            resources={1: 0.7},  # Resource 1 with 0.7 allocation
        )

        # Calculate resource loading
        loading = self.model.calculate_resource_loading()

        # Verify loading calculations
        assert 1 in loading  # Resource ID 1 should be in the results
        assert len(loading[1]) == self.model.days  # Should have values for all days

        # Day 0: Only Task 1 with 0.5 allocation
        assert loading[1][0] == 0.5

        # Days 1-2: Both Task 1 and Task 2 (0.5 + 0.7 = 1.2)
        assert loading[1][1] == 1.2
        assert loading[1][2] == 1.2

        # Day 3: Only Task 2 with 0.7 allocation
        assert loading[1][3] == 0.7

        # Day 4 onwards: No tasks, so loading should be 0
        assert loading[1][4] == 0.0

    def test_get_date_for_day(self):
        """Test conversion between day indices and calendar dates."""
        # Set a specific start date
        start_date = datetime(2023, 1, 1)
        self.model.start_date = start_date

        # Test various conversions
        assert self.model.get_date_for_day(0) == start_date
        assert self.model.get_date_for_day(1) == datetime(2023, 1, 2)
        assert self.model.get_date_for_day(10) == datetime(2023, 1, 11)
        assert self.model.get_date_for_day(31) == datetime(2023, 2, 1)  # Next month

    def test_get_day_for_date(self):
        """Test getting the day index for a specific date."""
        # Set a specific start date
        start_date = datetime(2023, 1, 1)
        self.model.start_date = start_date

        # Test conversions
        assert self.model.get_day_for_date(start_date) == 0
        assert self.model.get_day_for_date(datetime(2023, 1, 2)) == 1
        assert self.model.get_day_for_date(datetime(2023, 1, 11)) == 10
        assert self.model.get_day_for_date(datetime(2023, 2, 1)) == 31  # Next month

        # Test dates before the start date (should return negative indices)
        assert self.model.get_day_for_date(datetime(2022, 12, 31)) == -1

        # Test dates far in the future (beyond project timeline)
        future_date = start_date + timedelta(days=self.model.days + 10)
        assert self.model.get_day_for_date(future_date) == self.model.days + 10
