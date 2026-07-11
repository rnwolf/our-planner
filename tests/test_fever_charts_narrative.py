"""Stage 12: the remaining fever chart hand-verification.

Permanent regression test for the day-by-day narrative hand-verified via
`scripts/stage12_walkthrough.py` (and cross-checked step-by-step against the
real running app). One small CCPM scenario, walked through 9 status
updates, covering everything Stage 12 was still missing after Stage 15:

- a full multi-update narrative asserting CPSL/PPF/Progress %/Consumption %/
  Zone at every step (not just one instant);
- a feeding buffer fully consumed with overflow onto the critical chain
  (Stage 7's push side) - step 5;
- cross-project isolation, checked after every single step, not just once -
  a second, unrelated "Control" project's buffer must never move.

Scenario: critical chain C1 -> C2 -> C3 -> Project Buffer (baseline 8),
feeding chain F1 -> Feeding Buffer (baseline 5) merging into C2.
"""
from unittest.mock import MagicMock

from src.model.task_resource_model import (
    TaskResourceModel,
    classify_fever_chart_zone,
    fever_chart_display_point,
)
from src.operations.task_operations import TaskOperations


class TestFeverChartsNarrative:
    def setup_method(self):
        self.model = TaskResourceModel()
        self.model.setdate = self.model.start_date

        self.controller = MagicMock()
        self.controller.model = self.model
        self.task_ops = TaskOperations(self.controller, self.model)

        # Drop the auto-seeded empty default project.
        self.model.remove_project(self.model.projects[0]['id'])

        project = self.model.add_project('Stage12 Demo')
        self.pid = project['id']
        self.project = project
        critical = self.model.get_chain_by_name('Critical')
        feeding = self.model.get_chain_by_name('Feeding-01')

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
            row=0, col=8, duration=5, description='C2',
            project_id=self.pid, chain_id=critical['id'],
        )
        self.c3 = self.model.add_task(
            row=0, col=13, duration=5, description='C3',
            project_id=self.pid, chain_id=critical['id'],
        )
        self.pb = self.model.add_task(
            row=0, col=18, duration=8, description='PB',
            project_id=self.pid, chain_id=critical['id'],
        )
        self.pb['type'] = 'project_buffer'

        self.model.add_predecessor(self.fb['task_id'], self.f1['task_id'], 'FS')
        self.model.add_predecessor(self.c2['task_id'], self.c1['task_id'], 'FS')
        self.model.add_predecessor(self.c2['task_id'], self.fb['task_id'], 'FB')
        self.model.add_predecessor(self.c3['task_id'], self.c2['task_id'], 'FS')
        self.model.add_predecessor(self.pb['task_id'], self.c3['task_id'], 'PB')

        # Unrelated, untouched control project - deliberately not on the
        # 'Critical' chain (chains are a single global registry shared
        # across every project - reusing 'Critical' here would visually
        # read as a second critical chain).
        control_project = self.model.add_project('Control')
        self.cpid = control_project['id']
        ctrl_chain = self.model.get_chain_by_name('Feeding-02')
        x1 = self.model.add_task(
            row=5, col=0, duration=4, description='X1',
            project_id=self.cpid, chain_id=ctrl_chain['id'],
        )
        self.ctrl_pb = self.model.add_task(
            row=5, col=4, duration=6, description='Control PB',
            project_id=self.cpid, chain_id=ctrl_chain['id'],
        )
        self.ctrl_pb['type'] = 'project_buffer'
        self.model.add_predecessor(self.ctrl_pb['task_id'], x1['task_id'], 'PB')

        self.model.capture_project_baseline(self.pid)
        self.model.set_project_phase(self.pid, 'execution')
        self.model.capture_project_baseline(self.cpid)
        self.model.set_project_phase(self.cpid, 'execution')
        self.model.capture_fever_chart_snapshot()

        self.control_pb_snapshot = self._buffer_snapshot(self.ctrl_pb)

    def _buffer_snapshot(self, buffer_task):
        entry = buffer_task['fever_chart_history'][-1]
        return dict(entry), buffer_task['col'], buffer_task['duration']

    def assert_control_untouched(self):
        """Cross-project isolation: a status update in 'Stage12 Demo' must
        never move anything in the unrelated 'Control' project - checked
        after every step, not just once."""
        entry, col, duration = self._buffer_snapshot(self.ctrl_pb)
        expected_entry, expected_col, expected_duration = self.control_pb_snapshot
        assert entry == expected_entry
        assert col == expected_col
        assert duration == expected_duration

    def record_status(self, day, task, remaining):
        from datetime import timedelta

        self.model.setdate = self.model.start_date + timedelta(days=day)
        self.model.record_remaining_duration(task['task_id'], remaining)
        self.task_ops.apply_dependency_cascade(task)
        self.model.capture_fever_chart_snapshot(project_id=self.pid)

    def point(self, buffer_task):
        """(progress_pct, consumption_pct, zone) for a buffer's latest
        fever chart point, using the exact production math."""
        entry = buffer_task['fever_chart_history'][-1]
        baseline = buffer_task.get('baseline')
        baseline_duration = baseline['duration'] if baseline else buffer_task['duration']
        progress_pct, consumption_pct = fever_chart_display_point(entry, baseline_duration)
        slope = self.project.get('fever_chart_slope', 0.55)
        yellow = self.project.get('fever_chart_yellow_intercept', 10.0)
        red = self.project.get('fever_chart_red_intercept', 27.0)
        zone = classify_fever_chart_zone(progress_pct, consumption_pct, slope, yellow, red)
        return progress_pct, consumption_pct, zone

    def test_day0_baseline_all_buffers_start_flat(self):
        for buffer_task in (self.fb, self.pb):
            progress_pct, consumption_pct, zone = self.point(buffer_task)
            assert progress_pct == 0.0
            assert consumption_pct == 0.0
            assert zone == 'green'
        self.assert_control_untouched()

    def test_full_narrative(self):
        # Step 1 (day 0): C1's first status update, on its real start day -
        # anchors actual_start_date/col to day 0 rather than collapsing to
        # whatever day it's first recorded on.
        self.record_status(0, self.c1, 5)
        assert (self.c1['col'], self.c1['duration']) == (0, 5)
        assert (self.fb['col'], self.fb['duration']) == (3, 2)
        progress_pct, consumption_pct, zone = self.point(self.fb)
        assert (progress_pct, consumption_pct, zone) == (0.0, 60.0, 'red')
        self.assert_control_untouched()

        # Step 2 (day 2): F1 on track, pure "no news" - nothing new moves.
        self.record_status(2, self.f1, 1)
        assert (self.f1['col'], self.f1['duration']) == (2, 1)
        self.assert_control_untouched()

        # Step 3 (day 2): C1 same-day check-in, still on track - no change.
        self.record_status(2, self.c1, 3)
        assert (self.c1['col'], self.c1['duration']) == (0, 5)
        self.assert_control_untouched()

        # Step 4 (day 5): C1 finishes on time. Its real 5-day footprint
        # (anchored at step 1) means the critical chain's frontier can now
        # advance past it - first time Progress % moves off 0% for PB.
        self.record_status(5, self.c1, 0)
        assert (self.c1['col'], self.c1['duration']) == (0, 5)
        progress_pct, consumption_pct, zone = self.point(self.pb)
        assert round(progress_pct, 1) == 33.3
        assert round(consumption_pct, 1) == -37.5
        assert zone == 'green'
        self.assert_control_untouched()

        # Step 5 (day 9): F1 finishes 6 days late - a 6-day slip the FB's
        # 5-day baseline can't absorb. Fully consumed (duration 0) with 1
        # day of overflow pushed onto the merge point C2 (Stage 7's push
        # side, fully consumed + overflow).
        self.record_status(9, self.f1, 0)
        assert (self.c2['col'], self.c2['duration']) == (9, 5)
        assert (self.fb['col'], self.fb['duration']) == (9, 0)
        fb_progress, fb_consumption, fb_zone = self.point(self.fb)
        assert (fb_progress, fb_consumption, fb_zone) == (100.0, 120.0, 'red')
        pb_progress, pb_consumption, pb_zone = self.point(self.pb)
        assert round(pb_progress, 1) == 26.3
        assert round(pb_consumption, 1) == 12.5
        assert pb_zone == 'green'
        self.assert_control_untouched()

        # Step 6 (day 9): routine, unrelated check-in on C2 - the merge
        # point the overflow just pushed must not get dragged anywhere else
        # by an ordinary cascade (Stage 15's max-across-all-paths rule
        # holding up inside a longer narrative).
        self.record_status(9, self.c2, 5)
        assert (self.c2['col'], self.c2['duration']) == (9, 5)
        self.assert_control_untouched()

        # Step 7 (day 14): C2 finishes on time, matching its own day-9
        # forecast. C3 is FS-dependent on C2, so completing C2 first keeps
        # the narrative honest. Completing C2 shifts the Progress Frontier
        # forward past its own span too, not just C1's.
        self.record_status(14, self.c2, 0)
        assert (self.c2['col'], self.c2['duration']) == (9, 5)
        progress_pct, consumption_pct, zone = self.point(self.pb)
        assert round(progress_pct, 1) == 73.7
        assert round(consumption_pct, 1) == 12.5
        assert zone == 'green'
        self.assert_control_untouched()

        # Step 8 (day 16): C3 reports a 2-day slip against its baseline
        # finish (day 18) - first sign of trouble for the project buffer.
        self.record_status(16, self.c3, 4)
        progress_pct, consumption_pct, zone = self.point(self.pb)
        assert round(progress_pct, 1) == 70.0
        assert round(consumption_pct, 1) == 25.0
        assert zone == 'green'
        self.assert_control_untouched()

        # Step 9 (day 22): C3 finishes, 5 days late overall against its
        # baseline (day 18) - the "trajectory" this narrative exists to
        # prove: Progress % climbing to 100% while Consumption % worsens
        # across several points on the same buffer's chart, not just one.
        self.record_status(22, self.c3, 0)
        assert (self.pb['col'], self.pb['duration']) == (22, 4)
        progress_pct, consumption_pct, zone = self.point(self.pb)
        assert (progress_pct, consumption_pct, zone) == (100.0, 50.0, 'green')
        self.assert_control_untouched()
