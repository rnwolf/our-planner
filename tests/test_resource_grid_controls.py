"""Stage 21 - resource grid at scale: load utilization summary, scoped
loading, project-membership resource filter, and display-order sorting."""

from unittest.mock import MagicMock

from src.controller.task_manager import TaskResourceManager
from src.model.task_resource_model import TaskResourceModel
from src.operations.tag_operations import TagOperations


def make_tag_ops():
    model = TaskResourceModel()
    controller = MagicMock()
    controller.model = model
    return model, TagOperations(controller, model)


class TestResourceUtilization:
    """calculate_resource_utilization: whole-horizon total load / total
    capacity per resource."""

    def setup_method(self):
        self.model = TaskResourceModel()

    def test_basic_ratio(self):
        # 10 days at allocation 1.0 against 100 days of capacity 1.0
        self.model.add_task(
            row=0, col=0, duration=10, description='T1', resources={1: 1.0}
        )
        loading = self.model.calculate_resource_loading()
        utilization = self.model.calculate_resource_utilization(loading)
        assert utilization[1] == 0.1
        # Unassigned resources report 0.0, not a missing key
        assert utilization[2] == 0.0

    def test_fractional_allocation_and_capacity(self):
        self.model.resources[0]['capacity'] = [0.5] * self.model.days
        self.model.add_task(
            row=0, col=0, duration=10, description='T1', resources={1: 0.5}
        )
        loading = self.model.calculate_resource_loading()
        utilization = self.model.calculate_resource_utilization(loading)
        assert utilization[1] == (10 * 0.5) / (100 * 0.5)

    def test_zero_capacity_idle_is_zero(self):
        self.model.resources[0]['capacity'] = [0.0] * self.model.days
        loading = self.model.calculate_resource_loading()
        utilization = self.model.calculate_resource_utilization(loading)
        assert utilization[1] == 0.0

    def test_zero_capacity_loaded_is_inf(self):
        # Overloaded by definition - must sort above every finite ratio
        self.model.resources[0]['capacity'] = [0.0] * self.model.days
        self.model.add_task(
            row=0, col=0, duration=5, description='T1', resources={1: 1.0}
        )
        loading = self.model.calculate_resource_loading()
        utilization = self.model.calculate_resource_utilization(loading)
        assert utilization[1] == float('inf')


class TestScopedLoading:
    """calculate_resource_loading(tasks=...) limits the sum to a subset -
    the 'Filtered tasks' load scope."""

    def setup_method(self):
        self.model = TaskResourceModel()
        self.t1 = self.model.add_task(
            row=0, col=0, duration=10, description='T1', resources={1: 1.0}
        )
        self.t2 = self.model.add_task(
            row=1, col=0, duration=10, description='T2', resources={2: 1.0}
        )

    def test_default_covers_all_tasks(self):
        loading = self.model.calculate_resource_loading()
        assert sum(loading[1]) == 10.0
        assert sum(loading[2]) == 10.0

    def test_subset_only_counts_given_tasks(self):
        loading = self.model.calculate_resource_loading(tasks=[self.t1])
        assert sum(loading[1]) == 10.0
        assert sum(loading[2]) == 0.0

    def test_empty_subset_is_all_zero(self):
        loading = self.model.calculate_resource_loading(tasks=[])
        assert all(sum(days) == 0.0 for days in loading.values())

    def test_scoped_equals_loading_of_filtered_tasks(self):
        # The controller wires get_filtered_tasks() into the tasks param -
        # scoped loading must equal computing over exactly that subset
        model, tag_ops = make_tag_ops()
        p2 = model.add_project('Project 2')
        model.add_task(row=0, col=0, duration=10, description='T1', resources={1: 1.0})
        model.add_task(
            row=1,
            col=0,
            duration=4,
            description='T2',
            resources={2: 1.0},
            project_id=p2['id'],
        )
        tag_ops.task_project_filters = [p2['id']]
        filtered = tag_ops.get_filtered_tasks()
        loading = model.calculate_resource_loading(tasks=filtered)
        assert sum(loading[1]) == 0.0
        assert sum(loading[2]) == 4.0


class TestAssignedResourceIds:
    """get_assigned_resource_ids: a resource 'belongs to' a project only
    via task assignments."""

    def setup_method(self):
        self.model = TaskResourceModel()
        self.p2 = self.model.add_project('Project 2')
        self.model.add_task(
            row=0, col=0, duration=5, description='T1', resources={1: 1.0}
        )
        # String resource keys, as they appear after JSON round-trips
        self.model.add_task(
            row=1,
            col=0,
            duration=5,
            description='T2',
            resources={'2': 0.5, '3': 0.5},
            project_id=self.p2['id'],
        )

    def test_membership_per_project(self):
        assert self.model.get_assigned_resource_ids([self.p2['id']]) == {2, 3}
        assert self.model.get_assigned_resource_ids(
            [self.model.default_project_id]
        ) == {1}

    def test_multiple_projects_union(self):
        ids = self.model.get_assigned_resource_ids(
            [self.model.default_project_id, self.p2['id']]
        )
        assert ids == {1, 2, 3}

    def test_no_projects_empty(self):
        assert self.model.get_assigned_resource_ids([]) == set()


class TestResourceFilterComposition:
    """get_filtered_resources: project filter ANDs against the tag filter."""

    def setup_method(self):
        self.model, self.tag_ops = make_tag_ops()
        self.p2 = self.model.add_project('Project 2')
        # Resources 1 and 2 work on Project 2; resource 1 also tagged
        self.model.set_resource_tags(1, ['dev'])
        self.model.add_task(
            row=0,
            col=0,
            duration=5,
            description='T1',
            resources={1: 1.0, 2: 1.0},
            project_id=self.p2['id'],
        )

    def test_project_filter_alone(self):
        self.tag_ops.resource_project_filters = [self.p2['id']]
        assert [r['id'] for r in self.tag_ops.get_filtered_resources()] == [1, 2]

    def test_project_and_tag_filters_and_together(self):
        self.tag_ops.resource_project_filters = [self.p2['id']]
        self.tag_ops.resource_tag_filters = ['dev']
        assert [r['id'] for r in self.tag_ops.get_filtered_resources()] == [1]

    def test_clear_resets_project_filter_but_not_sort(self):
        self.tag_ops.resource_project_filters = [self.p2['id']]
        self.tag_ops.resource_sort_key = 'load'
        self.tag_ops.clear_resource_filters()
        assert self.tag_ops.resource_project_filters == []
        # Sort/scope are display choices, not filters - they survive
        assert self.tag_ops.resource_sort_key == 'load'

    def test_has_active_filters_sees_project_filter(self):
        assert not self.tag_ops.has_active_filters()
        self.tag_ops.resource_project_filters = [self.p2['id']]
        assert self.tag_ops.has_active_filters()


class TestDisplayOrder:
    """get_display_resources: the single row-ordering source for the grid."""

    def setup_method(self):
        self.model, self.tag_ops = make_tag_ops()
        # Keep only the first five of the model's default resources so
        # expected orders stay literal (ids 1..5, names Resource A..E)
        del self.model.resources[5:]

    def ids(self, utilization=None):
        return [r['id'] for r in self.tag_ops.get_display_resources(utilization)]

    def test_default_is_model_order(self):
        assert self.ids() == [1, 2, 3, 4, 5]

    def test_sort_by_id_desc(self):
        self.tag_ops.resource_sort_key = 'id'
        self.tag_ops.resource_sort_desc = True
        assert self.ids() == [5, 4, 3, 2, 1]

    def test_sort_by_name_is_case_insensitive(self):
        self.model.resources[0]['name'] = 'zebra'
        self.model.resources[1]['name'] = 'Aardvark'
        self.tag_ops.resource_sort_key = 'name'
        assert self.ids() == [2, 3, 4, 5, 1]

    def test_sort_by_load_descending_finds_the_drum(self):
        self.tag_ops.resource_sort_key = 'load'
        self.tag_ops.resource_sort_desc = True
        utilization = {1: 0.1, 2: 0.5, 3: 0.2, 4: 0.0, 5: 0.3}
        assert self.ids(utilization) == [2, 5, 3, 1, 4]

    def test_sort_by_load_missing_ids_default_to_zero(self):
        self.tag_ops.resource_sort_key = 'load'
        self.tag_ops.resource_sort_desc = True
        assert self.ids({3: 0.4}) == [3, 1, 2, 4, 5]

    def test_default_order_respects_direction(self):
        self.tag_ops.resource_sort_desc = True
        assert self.ids() == [5, 4, 3, 2, 1]

    def test_sorting_does_not_mutate_model_order(self):
        self.tag_ops.resource_sort_key = 'id'
        self.tag_ops.resource_sort_desc = True
        self.ids()
        assert [r['id'] for r in self.model.resources] == [1, 2, 3, 4, 5]


class TestUpdateResourceLoadingFlow:
    """update_resource_loading computes loading BEFORE drawing (row order
    and label % depend on it), then draws grid, cells, and bar - the
    Stage 21 sequencing contract."""

    def make_controller(self):
        controller = TaskResourceManager.__new__(TaskResourceManager)
        controller.model = TaskResourceModel()
        controller.ui = MagicMock()
        tag_ops_controller = MagicMock()
        tag_ops_controller.model = controller.model
        controller.tag_ops = TagOperations(tag_ops_controller, controller.model)
        controller.resource_loading = {}
        controller.resource_utilization = {}
        return controller

    def test_draw_order_and_stored_state(self):
        controller = self.make_controller()
        controller.model.add_task(
            row=0, col=0, duration=10, description='T1', resources={1: 1.0}
        )

        TaskResourceManager.update_resource_loading(controller)

        assert sum(controller.resource_loading[1]) == 10.0
        assert controller.resource_utilization[1] == 0.1
        called = [name for name, args, kwargs in controller.ui.method_calls]
        assert called == [
            'draw_resource_grid',
            'display_resource_loading',
            'update_resource_control_bar',
        ]

    def test_filtered_scope_uses_filtered_tasks(self):
        controller = self.make_controller()
        p2 = controller.model.add_project('Project 2')
        controller.model.add_task(
            row=0, col=0, duration=10, description='T1', resources={1: 1.0}
        )
        controller.model.add_task(
            row=1,
            col=0,
            duration=4,
            description='T2',
            resources={2: 1.0},
            project_id=p2['id'],
        )
        controller.tag_ops.resource_load_scope = 'filtered'
        controller.tag_ops.task_project_filters = [p2['id']]

        TaskResourceManager.update_resource_loading(controller)

        assert sum(controller.resource_loading[1]) == 0.0
        assert sum(controller.resource_loading[2]) == 4.0
        assert controller.resource_utilization[2] == 0.04

    def test_get_display_resources_uses_stored_utilization(self):
        controller = self.make_controller()
        controller.model.add_task(
            row=0, col=0, duration=10, description='T1', resources={3: 1.0}
        )
        controller.tag_ops.resource_sort_key = 'load'
        controller.tag_ops.resource_sort_desc = True

        TaskResourceManager.update_resource_loading(controller)
        ordered = TaskResourceManager.get_display_resources(controller)

        assert ordered[0]['id'] == 3
