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
            row=1, col=8, duration=3, description='Not started', project_id=project['id']
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
