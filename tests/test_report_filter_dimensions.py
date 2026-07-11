"""Stage 10 Part A: derived filter dimensions (state, full-kit readiness,
planned start window) used by both the canvas Filter menu and the future
Reporting framework. All are computed from existing task fields, no new
stored field required.
"""
from datetime import timedelta
from unittest.mock import MagicMock

from src.model.task_resource_model import TaskResourceModel
from src.operations.tag_operations import TagOperations


class TestTaskState:
    def setup_method(self):
        self.model = TaskResourceModel()

    def test_not_started_by_default(self):
        task = self.model.add_task(row=0, col=5, duration=3, description='T1')
        assert self.model.get_task_state(task) == 'not_started'

    def test_in_progress_once_started(self):
        task = self.model.add_task(row=0, col=5, duration=3, description='T1')
        task['actual_start_date'] = self.model.setdate.isoformat()
        assert self.model.get_task_state(task) == 'in_progress'

    def test_complete_once_ended(self):
        task = self.model.add_task(row=0, col=5, duration=3, description='T1')
        task['actual_start_date'] = self.model.setdate.isoformat()
        task['actual_end_date'] = self.model.setdate.isoformat()
        assert self.model.get_task_state(task) == 'complete'

    def test_get_tasks_by_state_ors_within_dimension(self):
        t1 = self.model.add_task(row=0, col=5, duration=3, description='Not started')
        t2 = self.model.add_task(row=1, col=5, duration=3, description='In progress')
        t2['actual_start_date'] = self.model.setdate.isoformat()
        t3 = self.model.add_task(row=2, col=5, duration=3, description='Complete')
        t3['actual_start_date'] = self.model.setdate.isoformat()
        t3['actual_end_date'] = self.model.setdate.isoformat()

        result = self.model.get_tasks_by_state(['not_started', 'complete'])
        ids = {t['task_id'] for t in result}
        assert ids == {t1['task_id'], t3['task_id']}

    def test_empty_state_filter_returns_all(self):
        self.model.add_task(row=0, col=5, duration=3, description='T1')
        assert len(self.model.get_tasks_by_state([])) == 1


class TestFullKitReadiness:
    def setup_method(self):
        self.model = TaskResourceModel()

    def test_ready_vs_not_ready(self):
        ready = self.model.add_task(row=0, col=5, duration=3, description='Kitted')
        ready['fullkit_date'] = self.model.setdate.isoformat()
        not_ready = self.model.add_task(row=1, col=5, duration=3, description='Not kitted')

        assert [t['task_id'] for t in self.model.get_tasks_by_fullkit('ready')] == [
            ready['task_id']
        ]
        assert [t['task_id'] for t in self.model.get_tasks_by_fullkit('not_ready')] == [
            not_ready['task_id']
        ]

    def test_any_returns_all(self):
        self.model.add_task(row=0, col=5, duration=3, description='T1')
        self.model.add_task(row=1, col=5, duration=3, description='T2')
        assert len(self.model.get_tasks_by_fullkit('any')) == 2


class TestPlannedStartWindow:
    def setup_method(self):
        self.model = TaskResourceModel()

    def _task_at(self, days_from_today, description='T'):
        target_date = self.model.setdate + timedelta(days=days_from_today)
        col = self.model.get_day_for_date(target_date)
        return self.model.add_task(row=0, col=col, duration=1, description=description)

    def test_overdue(self):
        task = self._task_at(-5)
        assert self.model.get_task_start_window(task) == 'overdue'

    def test_week1(self):
        task = self._task_at(3)
        assert self.model.get_task_start_window(task) == 'week1'

    def test_week2(self):
        task = self._task_at(10)
        assert self.model.get_task_start_window(task) == 'week2'

    def test_month1(self):
        task = self._task_at(20)
        assert self.model.get_task_start_window(task) == 'month1'

    def test_month2(self):
        task = self._task_at(45)
        assert self.model.get_task_start_window(task) == 'month2'

    def test_later(self):
        task = self._task_at(90)
        assert self.model.get_task_start_window(task) == 'later'

    def test_boundaries_are_half_open(self):
        # Exactly on a boundary belongs to the later bucket, not the earlier one.
        assert self.model.get_task_start_window(self._task_at(0)) == 'week1'
        assert self.model.get_task_start_window(self._task_at(7)) == 'week2'
        assert self.model.get_task_start_window(self._task_at(14)) == 'month1'
        assert self.model.get_task_start_window(self._task_at(30)) == 'month2'
        assert self.model.get_task_start_window(self._task_at(60)) == 'later'

    def test_get_tasks_by_start_window_ors_within_dimension(self):
        overdue = self._task_at(-1, 'Overdue')
        soon = self._task_at(3, 'Soon')
        far = self._task_at(90, 'Far')

        result = self.model.get_tasks_by_start_window(['overdue', 'week1'])
        ids = {t['task_id'] for t in result}
        assert ids == {overdue['task_id'], soon['task_id']}
        assert far['task_id'] not in ids


class TestFilterCombination:
    """Every dimension ANDs against the others in get_filtered_tasks()."""

    def setup_method(self):
        self.model = TaskResourceModel()
        self.controller = MagicMock()
        self.controller.model = self.model
        self.tag_ops = TagOperations(self.controller, self.model)

    def test_state_and_project_and_fullkit_combine(self):
        p1 = self.model.add_project('Alpha')
        p2 = self.model.add_project('Beta')

        match = self.model.add_task(
            row=0, col=5, duration=3, description='Match', project_id=p1['id']
        )
        match['fullkit_date'] = self.model.setdate.isoformat()

        wrong_project = self.model.add_task(
            row=1, col=5, duration=3, description='WrongProject', project_id=p2['id']
        )
        wrong_project['fullkit_date'] = self.model.setdate.isoformat()

        not_kitted = self.model.add_task(
            row=2, col=5, duration=3, description='NotKitted', project_id=p1['id']
        )

        already_started = self.model.add_task(
            row=3, col=5, duration=3, description='Started', project_id=p1['id']
        )
        already_started['fullkit_date'] = self.model.setdate.isoformat()
        already_started['actual_start_date'] = self.model.setdate.isoformat()

        self.tag_ops.task_project_filters = [p1['id']]
        self.tag_ops.task_state_filters = ['not_started']
        self.tag_ops.task_fullkit_filter = 'ready'

        result = self.tag_ops.get_filtered_tasks()
        assert [t['task_id'] for t in result] == [match['task_id']]

    def test_clear_task_filters_resets_new_dimensions(self):
        self.tag_ops.task_state_filters = ['complete']
        self.tag_ops.task_fullkit_filter = 'ready'
        self.tag_ops.task_start_window_filters = ['overdue']

        self.tag_ops.clear_task_filters()

        assert self.tag_ops.task_state_filters == []
        assert self.tag_ops.task_fullkit_filter == 'any'
        assert self.tag_ops.task_start_window_filters == []

    def test_has_active_filters_covers_new_dimensions(self):
        assert not self.tag_ops.has_active_filters()

        self.tag_ops.task_state_filters = ['not_started']
        assert self.tag_ops.has_active_filters()
        self.tag_ops.task_state_filters = []

        self.tag_ops.task_fullkit_filter = 'not_ready'
        assert self.tag_ops.has_active_filters()
        self.tag_ops.task_fullkit_filter = 'any'

        self.tag_ops.task_start_window_filters = ['week1']
        assert self.tag_ops.has_active_filters()
        self.tag_ops.task_start_window_filters = []

        assert not self.tag_ops.has_active_filters()
