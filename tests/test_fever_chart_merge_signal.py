"""Regression tests for the merge-task cascade and the feeding buffer's
shock-absorber fever chart signal.

The scenario (hand-verifiable): C1 (critical, day 0-5) and F1 -> FB
(feeding task day 0-3, buffer day 3-8, baseline 5d) both feed the merge
task C2 (planned day 8-13). Recording a routine "on track" status update
on C1 must:

- pull C2 to the relay-runner start, the MAX across all its incoming
  paths (never whichever single link cascaded last - the original bug
  yanked C2 in front of the feeding path's work);
- compress the feeding buffer against the feeding work's finish (5d -> 2d),
  logged to buffer_size_history - the protection genuinely available to
  the feeding chain has shrunk, whichever side the shock came from;
- leave every BASELINE untouched (the yardstick the fever chart divides
  by);
- ring the alarm on the feeding buffer's fever chart: effective lateness
  3 of baseline 5 = 60% consumption at that exact status update;
- be idempotent: recording the same status twice changes nothing further.
"""

from unittest.mock import MagicMock

from src.model.task_resource_model import TaskResourceModel
from src.operations.task_operations import TaskOperations


class TestFeverChartMergeSignal:
    def setup_method(self):
        self.controller = MagicMock()
        self.model = TaskResourceModel()
        self.controller.model = self.model
        self.task_ops = TaskOperations(self.controller, self.model)

        # Day-column 0 == the model's setdate (both default to today), so
        # recording a remaining duration "as of now" anchors at col 0.
        self.model.setdate = self.model.start_date

        project = self.model.add_project('Merge scenario')
        self.pid = project['id']
        critical = self.model.add_chain('critical chain', '#cc3333', is_critical=True)
        feeding = self.model.add_chain('feeding chain', '#33aa55')

        self.c1 = self.model.add_task(
            row=0, col=0, duration=5, description='C1',
            project_id=self.pid, chain_id=critical['id'],
        )
        self.f1 = self.model.add_task(
            row=1, col=0, duration=3, description='F1',
            project_id=self.pid, chain_id=feeding['id'],
        )
        self.fb = self.model.add_task(
            row=2, col=3, duration=5, description='FB',
            project_id=self.pid, chain_id=feeding['id'],
        )
        self.fb['type'] = 'feeding_buffer'
        self.c2 = self.model.add_task(
            row=3, col=8, duration=5, description='C2',
            project_id=self.pid, chain_id=critical['id'],
        )

        self.model.add_predecessor(self.fb['task_id'], self.f1['task_id'], 'FS')
        self.model.add_predecessor(self.c2['task_id'], self.c1['task_id'], 'FS')
        self.model.add_predecessor(self.c2['task_id'], self.fb['task_id'], 'FB')

        self.model.capture_project_baseline(self.pid)
        self.model.set_project_phase(self.pid, 'execution')

    def record_status(self, task, remaining):
        """The status-update flow: record, cascade, snapshot (mirrors
        update_remaining_duration in task_operations, minus the dialog)."""
        self.model.record_remaining_duration(task['task_id'], remaining)
        self.task_ops.apply_dependency_cascade(task)
        self.model.capture_fever_chart_snapshot(project_id=self.pid)

    def positions(self):
        return {
            t['description']: (t['col'], t['duration'])
            for t in self.model.tasks
        }

    def test_on_track_update_pulls_merge_and_rings_alarm(self):
        # Routine "on track, no change" status on C1: remaining = 5.
        self.record_status(self.c1, 5)

        # Relay-runner pull: C2 lines up at the max across BOTH paths -
        # max(C1 finish 5, feeding work finish 3) = 5.
        assert self.c2['col'] == 5

        # The buffer stays glued to the merge point but may not overlap the
        # work feeding it: compressed to [3, 5) = 2d, and the shrink is on
        # the record - not silent.
        assert (self.fb['col'], self.fb['duration']) == (3, 2)
        assert self.fb['buffer_size_history'][-1]['reason'] == 'merge_pulled_earlier'

        # Baselines are the yardstick and must never move under status.
        assert self.fb['baseline']['duration'] == 5
        assert self.c2['baseline']['col'] == 8

        # The alarm: 3 of the baseline 5 days are no longer available ->
        # the fever chart plots 3/5 = 60% consumption at this update.
        point = self.fb['fever_chart_history'][-1]
        assert point['forecast_lateness'] == 3

    def test_status_updates_are_idempotent(self):
        self.record_status(self.c1, 5)
        first_positions = self.positions()
        first_point = dict(self.fb['fever_chart_history'][-1])

        self.record_status(self.c1, 5)

        assert self.positions() == first_positions
        second_point = self.fb['fever_chart_history'][-1]
        for key in ('cpsl', 'ppf', 'forecast_lateness'):
            assert second_point[key] == first_point[key]

    def test_pull_never_jumps_the_feeding_work(self):
        # The original bug's worst case: the feeding path slips FIRST, then
        # a status update on the other branch fires the cascade - the
        # single-link pull would drag C2 in front of F1's unfinished work.
        self.record_status(self.f1, 7)  # F1 now forecasts finish day 7
        self.record_status(self.c1, 5)  # routine update on the other branch

        # C2 respects the slower path: max(C1 finish 5, F1 finish 7) = 7.
        assert self.c2['col'] == 7
        # Buffer fully consumed - none of the 5 baseline days remain.
        assert self.fb['duration'] == 0
        point = self.fb['fever_chart_history'][-1]
        assert point['forecast_lateness'] == 5  # 100% consumption

    def test_push_side_signal_unchanged(self):
        # The classic push shock: F1 slips 2 days, critical chain untouched.
        # C2 keeps its planned start; the buffer absorbs from the left.
        self.record_status(self.f1, 5)  # F1 now forecasts finish day 5

        assert self.c2['col'] == 8
        assert (self.fb['col'], self.fb['duration']) == (5, 3)
        point = self.fb['fever_chart_history'][-1]
        assert point['forecast_lateness'] == 2  # 2/5 = 40%, as before
