from unittest.mock import MagicMock
from datetime import datetime, timedelta

from src.model.task_resource_model import TaskResourceModel
from src.operations.task_operations import TaskOperations
from src.utils.colors import get_resource_load_color

YELLOW = '#ffffcc'  # high usage, 80% up to and including capacity
RED = '#ffcccc'  # genuinely over capacity


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
        self.model.add_task(
            row=0,
            col=0,
            duration=3,
            description='Task 1',
            resources={1: 0.5},  # Resource 1 with 0.5 allocation
        )

        # Task 2: days 1-3 with 0.7 allocation (overlapping with Task 1 on day 1-2)
        self.model.add_task(
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


class TestPooledResourceOverload:
    """Pooled resources (capacity > 1) and the overload-finding helpers -
    no existing test exercised capacity > 1 before this (test_resource_
    capacity.py and test_resource_load_color.py only ever used capacity
    1.0 or fractional allocations against a capacity-1 resource)."""

    def setup_method(self):
        self.model = TaskResourceModel()
        self.model.resources = []

    def _add_resource(self, name, capacity, tags=None):
        resource = {
            'id': len(self.model.resources) + 1,
            'name': name,
            'capacity': [capacity] * self.model.days,
            'tags': tags or [],
        }
        self.model.resources.append(resource)
        return resource

    def test_pooled_resource_load_sums_across_tasks(self):
        pool = self._add_resource('Developers', 3.0)
        self.model.add_task(
            row=0, col=0, duration=2, description='A', resources={pool['id']: 2.0}
        )
        self.model.add_task(
            row=1, col=0, duration=2, description='B', resources={pool['id']: 1.5}
        )
        loading = self.model.calculate_resource_loading()
        assert loading[pool['id']][0] == 3.5

    def test_pooled_resource_over_capacity_is_red(self):
        pool = self._add_resource('Developers', 3.0)
        self.model.add_task(
            row=0, col=0, duration=2, description='A', resources={pool['id']: 2.0}
        )
        self.model.add_task(
            row=1, col=0, duration=2, description='B', resources={pool['id']: 2.0}
        )
        loading = self.model.calculate_resource_loading()
        assert get_resource_load_color(loading[pool['id']][0], 3.0) == RED

    def test_pooled_resource_exactly_at_capacity_is_not_overloaded(self):
        pool = self._add_resource('Developers', 3.0)
        self.model.add_task(
            row=0, col=0, duration=2, description='A', resources={pool['id']: 3.0}
        )
        loading = self.model.calculate_resource_loading()
        assert get_resource_load_color(loading[pool['id']][0], 3.0) == YELLOW

    def test_calculate_tag_loading_sums_across_resources_sharing_tag(self):
        a = self._add_resource('Alice', 1.0, tags=['dev'])
        b = self._add_resource('Bob', 1.0, tags=['dev'])
        self.model.add_task(
            row=0, col=0, duration=1, description='A', resources={a['id']: 1.0}
        )
        self.model.add_task(
            row=1, col=0, duration=1, description='B', resources={b['id']: 0.5}
        )
        tag_loading = self.model.calculate_tag_loading()
        assert tag_loading['dev'][0] == 1.5

    def test_tag_fan_out_is_not_split_between_a_resources_tags(self):
        # A resource carrying two tags contributes its FULL load/capacity
        # to each tag independently - there's no "primary role" to divide
        # between them.
        person = self._add_resource('Alice', 1.0, tags=['dev', 'senior'])
        self.model.add_task(
            row=0, col=0, duration=1, description='A', resources={person['id']: 0.8}
        )
        tag_loading = self.model.calculate_tag_loading()
        tag_capacity = self.model.calculate_tag_capacity()
        assert tag_loading['dev'][0] == 0.8
        assert tag_loading['senior'][0] == 0.8
        assert tag_capacity['dev'][0] == 1.0
        assert tag_capacity['senior'][0] == 1.0

    def test_find_resource_overallocations_flags_only_overloaded_days(self):
        pool = self._add_resource('Developers', 2.0)
        self.model.add_task(
            row=0, col=0, duration=1, description='A', resources={pool['id']: 3.0}
        )
        self.model.add_task(
            row=1, col=1, duration=1, description='B', resources={pool['id']: 2.0}
        )
        findings = self.model.find_resource_overallocations()
        days = {f['day'] for f in findings}
        assert days == {0}  # day 1 is exactly at capacity, not over
        finding = findings[0]
        assert finding['kind'] == 'resource'
        assert finding['key'] == pool['id']
        assert finding['load'] == 3.0
        assert finding['capacity'] == 2.0

    def test_tag_overload_is_not_dependent_on_a_single_resource(self):
        # An organisation isn't dependent on just one named resource: two
        # people share a tag, only one is individually overloaded, but
        # the ROLE as a whole still has spare capacity - no tag-level
        # finding should fire.
        a = self._add_resource('Alice', 1.0, tags=['dev'])
        b = self._add_resource('Bob', 1.0, tags=['dev'])
        self.model.add_task(
            row=0,
            col=0,
            duration=1,
            description='Overloads Alice',
            resources={a['id']: 1.5},
        )
        assert self.model.find_resource_overallocations()  # Alice alone is over
        assert self.model.find_tag_overallocations() == []  # dev pool (2.0) isn't

        # Now genuinely saturate the whole pool.
        self.model.add_task(
            row=1,
            col=0,
            duration=1,
            description='Loads Bob too',
            resources={b['id']: 1.0},
        )
        tag_findings = self.model.find_tag_overallocations()
        assert len(tag_findings) == 1
        assert tag_findings[0]['key'] == 'dev'
        assert tag_findings[0]['load'] == 2.5

    def test_get_contributing_tasks_for_a_resource(self):
        pool = self._add_resource('Developers', 2.0)
        t1 = self.model.add_task(
            row=0, col=0, duration=1, description='A', resources={pool['id']: 1.5}
        )
        self.model.add_task(
            row=1, col=1, duration=1, description='B', resources={pool['id']: 1.0}
        )
        contributing = self.model.get_contributing_tasks('resource', pool['id'], 0)
        assert len(contributing) == 1
        assert contributing[0]['task_id'] == t1['task_id']
        assert contributing[0]['allocation'] == 1.5
        assert contributing[0]['resource_id'] == pool['id']

    def test_get_contributing_tasks_for_a_tag_attributes_each_resource(self):
        a = self._add_resource('Alice', 1.0, tags=['dev'])
        b = self._add_resource('Bob', 1.0, tags=['dev'])
        self.model.add_task(
            row=0, col=0, duration=1, description='A', resources={a['id']: 1.0}
        )
        self.model.add_task(
            row=1, col=0, duration=1, description='B', resources={b['id']: 1.0}
        )
        contributing = self.model.get_contributing_tasks('tag', 'dev', 0)
        resource_ids = {c['resource_id'] for c in contributing}
        assert resource_ids == {a['id'], b['id']}

    def test_is_critical_tri_state(self):
        pool = self._add_resource('Developers', 1.0)
        critical = self.model.add_task(
            row=0,
            col=0,
            duration=1,
            description='Critical',
            chain_id=1,
            resources={pool['id']: 0.3},
        )
        non_critical = self.model.add_task(
            row=1,
            col=0,
            duration=1,
            description='Feeding',
            chain_id=2,
            resources={pool['id']: 0.3},
        )
        unscheduled = self.model.add_task(
            row=2,
            col=0,
            duration=1,
            description='Backlog',
            resources={pool['id']: 0.3},
        )
        contributing = self.model.get_contributing_tasks('resource', pool['id'], 0)
        by_id = {c['task_id']: c for c in contributing}
        assert by_id[critical['task_id']]['is_critical'] is True
        assert by_id[non_critical['task_id']]['is_critical'] is False
        assert by_id[unscheduled['task_id']]['is_critical'] is None
