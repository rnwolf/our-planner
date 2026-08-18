"""Stage 10 Part B: the pluggable Reporting framework's first report type,
Full-Kit Readiness. Only the extractor half (compute_fullkit_readiness) is
exercised here - the renderer half is a plain Tkinter dialog with no
independent logic worth a headless test.
"""

from unittest.mock import MagicMock

from src.model.task_resource_model import TaskResourceModel
from src.operations.tag_operations import TagOperations
from src.operations.report_operations import ReportOperations


class TestFullKitReadinessReport:
    def setup_method(self):
        self.model = TaskResourceModel()
        self.controller = MagicMock()
        self.controller.model = self.model
        self.tag_ops = TagOperations(self.controller, self.model)
        self.controller.tag_ops = self.tag_ops
        self.report_ops = ReportOperations(self.controller, self.model)

    def test_counts_ready_vs_not_ready_scoped_to_project(self):
        p1 = self.model.add_project('Alpha')
        p2 = self.model.add_project('Beta')

        kitted = self.model.add_task(
            row=0, col=5, duration=3, description='Kitted', project_id=p1['id']
        )
        kitted['fullkit_date'] = self.model.setdate.isoformat()

        self.model.add_task(
            row=1, col=8, duration=3, description='Not kitted', project_id=p1['id']
        )
        # Different project - must not be counted.
        self.model.add_task(
            row=2, col=1, duration=3, description='Other project', project_id=p2['id']
        )

        tasks, ready_count, total = self.report_ops.compute_fullkit_readiness(p1)

        assert total == 2
        assert ready_count == 1
        assert [t['description'] for t in tasks] == ['Kitted', 'Not kitted']

    def test_excludes_buffer_tasks(self):
        project = self.model.add_project('Alpha')
        self.model.add_task(
            row=0, col=5, duration=3, description='Real task', project_id=project['id']
        )
        buffer_task = self.model.add_task(
            row=1, col=8, duration=3, description='Buffer', project_id=project['id']
        )
        buffer_task['type'] = 'project_buffer'

        tasks, ready_count, total = self.report_ops.compute_fullkit_readiness(project)

        assert total == 1
        assert tasks[0]['description'] == 'Real task'

    def test_sorted_soonest_start_first(self):
        project = self.model.add_project('Alpha')
        self.model.add_task(
            row=0, col=20, duration=3, description='Later', project_id=project['id']
        )
        self.model.add_task(
            row=1, col=5, duration=3, description='Sooner', project_id=project['id']
        )

        tasks, _, _ = self.report_ops.compute_fullkit_readiness(project)

        assert [t['description'] for t in tasks] == ['Sooner', 'Later']

    def test_respects_active_filter_menu_state(self):
        """Scoping to whatever's currently active on the Filter menu (Stage
        10's design intent) is exercised via the real get_filtered_tasks(),
        not bypassed by compute_fullkit_readiness reading model.tasks
        directly."""
        project = self.model.add_project('Alpha')
        started = self.model.add_task(
            row=0, col=5, duration=3, description='Started', project_id=project['id']
        )
        started['actual_start_date'] = self.model.setdate.isoformat()
        self.model.add_task(
            row=1,
            col=8,
            duration=3,
            description='Not started',
            project_id=project['id'],
        )

        self.tag_ops.task_state_filters = ['not_started']

        tasks, ready_count, total = self.report_ops.compute_fullkit_readiness(project)

        assert total == 1
        assert tasks[0]['description'] == 'Not started'

    def test_empty_project_returns_zero_counts(self):
        project = self.model.add_project('Empty')
        tasks, ready_count, total = self.report_ops.compute_fullkit_readiness(project)
        assert tasks == []
        assert ready_count == 0
        assert total == 0


class TestStatusUpdateLogReport:
    def setup_method(self):
        self.model = TaskResourceModel()
        self.controller = MagicMock()
        self.controller.model = self.model
        self.tag_ops = TagOperations(self.controller, self.model)
        self.controller.tag_ops = self.tag_ops
        self.report_ops = ReportOperations(self.controller, self.model)

    def test_includes_every_update_not_just_annotated_ones(self):
        """The whole point of this report over get_buffer_update_reasons
        (which filters to reason/note-bearing entries only) is reviewing
        the complete record."""
        project = self.model.add_project('Alpha')
        task = self.model.add_task(
            row=0, col=0, duration=5, description='C1', project_id=project['id']
        )
        self.model.record_remaining_duration(task['task_id'], 5)  # no reason
        self.model.record_remaining_duration(
            task['task_id'], 2, reason='Task Variability', note='Edge cases'
        )

        entries, with_reason_or_note = self.report_ops.compute_status_update_log(
            project
        )

        assert len(entries) == 2
        assert with_reason_or_note == 1
        assert 'reason' not in entries[0]
        assert entries[1]['reason'] == 'Task Variability'
        assert entries[1]['note'] == 'Edge cases'
        assert entries[1]['task_description'] == 'C1'
        assert entries[1]['remaining_duration'] == 2

    def test_task_url_included_when_set_omitted_when_blank(self):
        """The task's URL is where a reader is meant to navigate to
        collaborate on interventions - included when the task has one,
        left out (not an empty string) otherwise, same convention as
        reason/note."""
        project = self.model.add_project('Alpha')
        with_url = self.model.add_task(
            row=0, col=0, duration=5, description='Has URL', project_id=project['id']
        )
        with_url['url'] = 'https://wiki.example.com/tasks/has-url'
        without_url = self.model.add_task(
            row=1, col=0, duration=5, description='No URL', project_id=project['id']
        )

        self.model.record_remaining_duration(with_url['task_id'], 3, reason='On Time')
        self.model.record_remaining_duration(
            without_url['task_id'], 3, reason='On Time'
        )

        entries, _ = self.report_ops.compute_status_update_log(project)

        by_description = {e['task_description']: e for e in entries}
        assert (
            by_description['Has URL']['task_url']
            == 'https://wiki.example.com/tasks/has-url'
        )
        assert 'task_url' not in by_description['No URL']

    def test_scoped_to_project(self):
        p1 = self.model.add_project('Alpha')
        p2 = self.model.add_project('Beta')
        t1 = self.model.add_task(
            row=0, col=0, duration=5, description='In scope', project_id=p1['id']
        )
        t2 = self.model.add_task(
            row=1, col=0, duration=5, description='Other project', project_id=p2['id']
        )
        self.model.record_remaining_duration(t1['task_id'], 3, reason='On Time')
        self.model.record_remaining_duration(t2['task_id'], 3, reason='On Time')

        entries, _ = self.report_ops.compute_status_update_log(p1)

        assert len(entries) == 1
        assert entries[0]['task_description'] == 'In scope'

    def test_respects_active_filter_menu_state(self):
        project = self.model.add_project('Alpha')
        started = self.model.add_task(
            row=0, col=5, duration=3, description='Started', project_id=project['id']
        )
        self.model.record_remaining_duration(started['task_id'], 1, reason='On Time')
        self.model.add_task(
            row=1,
            col=8,
            duration=3,
            description='Not started',
            project_id=project['id'],
        )

        self.tag_ops.task_state_filters = ['not_started']

        entries, _ = self.report_ops.compute_status_update_log(project)

        assert entries == []

    def test_sorted_oldest_first(self):
        from datetime import timedelta

        project = self.model.add_project('Alpha')
        task = self.model.add_task(
            row=0, col=0, duration=5, description='C1', project_id=project['id']
        )
        self.model.setdate = self.model.start_date + timedelta(days=5)
        self.model.record_remaining_duration(task['task_id'], 3, reason='On Time')
        self.model.setdate = self.model.start_date
        self.model.record_remaining_duration(task['task_id'], 5, reason='On Time')

        entries, _ = self.report_ops.compute_status_update_log(project)

        assert [e['remaining_duration'] for e in entries] == [5, 3]

    def test_empty_project_returns_no_entries(self):
        project = self.model.add_project('Empty')
        entries, with_reason_or_note = self.report_ops.compute_status_update_log(
            project
        )
        assert entries == []
        assert with_reason_or_note == 0
