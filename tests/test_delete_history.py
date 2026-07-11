"""Stage 13: rolling timeline compaction ("Delete History..." / "Extend
Timeline...").

Covers the model-level mechanics (shift_task_position, compute_delete_
history_impact, delete_history, compute_safe_delete_cutoff, extend_timeline)
and, critically, that fever chart math stays correct across a compaction -
the concern that prompted extracting shift_task_position in the first place:
every buffer's forecast-lateness math compares a task's *current* col
against its own baseline col, so both must shift together or the numbers
silently drift.
"""
from unittest.mock import MagicMock

from src.model.task_resource_model import TaskResourceModel
from src.operations.task_operations import TaskOperations


class TestShiftTaskPosition:
    def setup_method(self):
        self.model = TaskResourceModel()

    def test_shifts_col_and_baseline_col_together(self):
        task = self.model.add_task(row=0, col=10, duration=3, description='T')
        task['baseline'] = {'col': 10, 'duration': 3, 'realistic_duration': 3}

        self.model.shift_task_position(task, 4)

        assert task['col'] == 6
        assert task['baseline']['col'] == 6

    def test_no_baseline_is_a_no_op_on_baseline(self):
        task = self.model.add_task(row=0, col=10, duration=3, description='T')
        assert task['baseline'] is None

        self.model.shift_task_position(task, 4)

        assert task['col'] == 6
        assert task['baseline'] is None


class TestDeleteHistoryImpact:
    def setup_method(self):
        self.model = TaskResourceModel()
        self.model.remove_project(self.model.projects[0]['id'])
        project = self.model.add_project('P')
        self.pid = project['id']
        chain = self.model.get_chain_by_name('Critical')

        self.t1 = self.model.add_task(
            row=0, col=0, duration=5, description='T1', project_id=self.pid, chain_id=chain['id']
        )
        self.t1['state'] = 'done'
        self.t2 = self.model.add_task(
            row=1, col=5, duration=5, description='T2', project_id=self.pid, chain_id=chain['id']
        )
        self.pb = self.model.add_task(
            row=2, col=10, duration=5, description='PB', project_id=self.pid, chain_id=chain['id']
        )
        self.pb['type'] = 'project_buffer'

        self.model.add_predecessor(self.t2['task_id'], self.t1['task_id'], 'FS')
        self.model.add_predecessor(self.pb['task_id'], self.t2['task_id'], 'PB')
        self.model.capture_project_baseline(self.pid)
        self.model.set_project_phase(self.pid, 'execution')

    def test_to_delete_only_includes_tasks_before_cutoff(self):
        impact = self.model.compute_delete_history_impact(5)
        assert [t['description'] for t in impact['to_delete']] == ['T1']

    def test_not_done_flags_incomplete_tasks_in_range(self):
        # T2 is not done and would fall in range at cutoff=6.
        impact = self.model.compute_delete_history_impact(6)
        assert 'T2' in [t['description'] for t in impact['not_done']]
        # T1 is done, so it should not be flagged.
        assert 'T1' not in [t['description'] for t in impact['not_done']]

    def test_blocking_when_terminal_task_would_be_deleted(self):
        # T2 is PB's terminal task - cutoff=6 would delete it.
        impact = self.model.compute_delete_history_impact(6)
        assert len(impact['blocking']) == 1
        assert impact['blocking'][0]['task']['description'] == 'T2'
        assert impact['blocking'][0]['role'] == 'terminal'

    def test_blocking_even_when_terminal_task_is_done(self):
        self.t2['state'] = 'done'
        impact = self.model.compute_delete_history_impact(6)
        # Still blocking - done-ness doesn't excuse deleting a buffer anchor.
        assert len(impact['blocking']) == 1

    def test_no_blocking_when_cutoff_excludes_structural_tasks(self):
        impact = self.model.compute_delete_history_impact(5)
        assert impact['blocking'] == []

    def test_blocking_on_merge_task(self):
        """A feeding buffer's merge task (T2, via an 'FB' link) must block
        too, not just a buffer's terminal task - mirrors Stage 15's
        F1 -> FB -> T2 merge-point shape."""
        chain = self.model.get_chain_by_name('Feeding-01')
        f1 = self.model.add_task(
            row=3, col=0, duration=2, description='F1', project_id=self.pid, chain_id=chain['id']
        )
        fb = self.model.add_task(
            row=4, col=2, duration=3, description='FB', project_id=self.pid, chain_id=chain['id']
        )
        fb['type'] = 'feeding_buffer'
        self.model.add_predecessor(fb['task_id'], f1['task_id'], 'FS')
        self.model.add_predecessor(self.t2['task_id'], fb['task_id'], 'FB')
        self.model.capture_project_baseline(self.pid)

        # At cutoff=1, F1 (FB's own terminal task) is already caught, but
        # T2 (FB's merge task) doesn't fall in range yet.
        impact = self.model.compute_delete_history_impact(1)
        assert {b['role'] for b in impact['blocking']} == {'terminal'}

        # At T2's own col: FB's merge-task role for T2 must be reported too.
        impact = self.model.compute_delete_history_impact(6)
        merge_entries = [b for b in impact['blocking'] if b['role'] == 'merge']
        assert len(merge_entries) == 1
        assert merge_entries[0]['task']['description'] == 'T2'
        assert merge_entries[0]['buffer']['description'] == 'FB'


class TestDeleteHistory:
    def setup_method(self):
        self.model = TaskResourceModel()
        self.model.remove_project(self.model.projects[0]['id'])
        project = self.model.add_project('P')
        self.pid = project['id']
        chain = self.model.get_chain_by_name('Critical')

        self.t1 = self.model.add_task(
            row=0, col=0, duration=5, description='T1', project_id=self.pid, chain_id=chain['id']
        )
        self.t1['state'] = 'done'
        self.t2 = self.model.add_task(
            row=1, col=5, duration=5, description='T2', project_id=self.pid, chain_id=chain['id']
        )
        self.pb = self.model.add_task(
            row=2, col=10, duration=5, description='PB', project_id=self.pid, chain_id=chain['id']
        )
        self.pb['type'] = 'project_buffer'
        self.model.add_predecessor(self.t2['task_id'], self.t1['task_id'], 'FS')
        self.model.add_predecessor(self.pb['task_id'], self.t2['task_id'], 'PB')
        self.model.capture_project_baseline(self.pid)
        self.model.set_project_phase(self.pid, 'execution')

        self.model.add_resource('R1')
        self.resource = self.model.get_resource_by_name('R1')

    def test_returns_false_for_non_positive_cutoff(self):
        assert self.model.delete_history(0) is False
        assert self.model.delete_history(-3) is False
        assert self.model.get_task(self.t1['task_id']) is not None

    def test_returns_false_and_no_op_when_blocking(self):
        days_before = self.model.days
        result = self.model.delete_history(6)  # would delete T2, PB's terminal
        assert result is False
        assert self.model.get_task(self.t2['task_id']) is not None
        assert self.model.days == days_before

    def test_deletes_and_shifts_correctly(self):
        original_start = self.model.start_date
        original_cap_len = len(self.resource['capacity'])
        original_days = self.model.days

        result = self.model.delete_history(5)

        assert result is True
        assert self.model.get_task(self.t1['task_id']) is None
        assert self.model.get_task(self.t2['task_id']) is not None
        assert self.t2['col'] == 0
        assert self.t2['baseline']['col'] == 0
        assert self.pb['col'] == 5
        assert self.pb['baseline']['col'] == 5
        assert self.model.days == original_days - 5
        assert len(self.resource['capacity']) == original_cap_len - 5
        assert self.model.start_date == original_start.replace(
            day=original_start.day + 5
        )

    def test_fever_chart_math_unaffected_by_compaction(self):
        """The whole point of shift_task_position: if a compaction's cutoff
        only removes history *outside* a buffer's own chain (a separate,
        unrelated, already-done project - this app's day-axis is shared
        across every concurrent project), that buffer's CPSL/PPF/forecast
        lateness must read identically before and after - only the shared
        coordinate system moved, nothing about the buffer's own schedule
        did. (Deleting a task that's actually *part of* the buffer's own
        chain is a different, legitimate case - it changes Progress % on
        purpose, since some of the certainty being counted was just
        discarded - not tested here.)
        """
        # An unrelated, already-done task in a separate project, entirely
        # before T1/T2/PB - this is what the cutoff will actually remove.
        junk_project = self.model.add_project('Junk')
        junk = self.model.add_task(
            row=8, col=0, duration=2, description='Junk', project_id=junk_project['id']
        )
        junk['state'] = 'done'

        # Shift the main scenario right to make room for Junk, and re-baseline
        # at these positions (T1 col 3, T2 col 8, PB col 13 - same relative
        # layout as setup_method, just +3).
        self.t1['col'] = 3
        self.t2['col'] = 8
        self.pb['col'] = 13
        self.model.capture_project_baseline(self.pid)

        # Now apply a genuine 2-day slip against that baseline.
        self.t2['col'] = 10

        point_before = self.model.compute_fever_chart_point(self.pb['task_id'])

        # Cutoff exactly at T1's col: only Junk (col 0) is removed.
        result = self.model.delete_history(3)
        assert result is True
        assert self.model.get_task(junk['task_id']) is None
        assert self.model.get_task(self.t1['task_id']) is not None

        point_after = self.model.compute_fever_chart_point(self.pb['task_id'])
        assert point_after == point_before


class TestSafeDeleteCutoff:
    def setup_method(self):
        self.model = TaskResourceModel()
        self.model.remove_project(self.model.projects[0]['id'])
        project = self.model.add_project('P')
        self.pid = project['id']
        chain = self.model.get_chain_by_name('Critical')

        self.t1 = self.model.add_task(
            row=0, col=0, duration=5, description='T1', project_id=self.pid, chain_id=chain['id']
        )
        self.t1['state'] = 'done'
        self.t2 = self.model.add_task(
            row=1, col=5, duration=5, description='T2', project_id=self.pid, chain_id=chain['id']
        )
        self.model.add_predecessor(self.t2['task_id'], self.t1['task_id'], 'FS')
        self.model.capture_project_baseline(self.pid)
        self.model.set_project_phase(self.pid, 'execution')

    def test_bounded_by_earliest_not_done_task(self):
        assert self.model.compute_safe_delete_cutoff() == 5  # T2's col

    def test_zero_when_nothing_left_to_protect(self):
        self.t2['state'] = 'done'
        assert self.model.compute_safe_delete_cutoff() == 0

    def test_bounded_by_buffer_terminal_task_even_when_done(self):
        self.t2['state'] = 'done'
        pb = self.model.add_task(
            row=2, col=10, duration=5, description='PB', project_id=self.pid,
            chain_id=self.model.get_chain_by_name('Critical')['id'],
        )
        pb['type'] = 'project_buffer'
        self.model.add_predecessor(pb['task_id'], self.t2['task_id'], 'PB')
        self.model.capture_project_baseline(self.pid)

        assert self.model.compute_safe_delete_cutoff() == 5  # T2's col, via its role


class TestDeleteHistoryDialogConfirmation:
    """Headless coverage of the controller-level confirmation flow, mirroring
    the pattern in test_project_start_date.py."""

    def setup_method(self):
        self.model = TaskResourceModel()
        self.model.remove_project(self.model.projects[0]['id'])
        self.controller = MagicMock()
        self.controller.model = self.model
        self.task_ops = TaskOperations(self.controller, self.model)

        project = self.model.add_project('P')
        self.pid = project['id']
        chain = self.model.get_chain_by_name('Critical')
        self.t1 = self.model.add_task(
            row=0, col=0, duration=5, description='T1', project_id=self.pid, chain_id=chain['id']
        )
        self.t1['state'] = 'done'
        self.t2 = self.model.add_task(
            row=1, col=5, duration=5, description='T2', project_id=self.pid, chain_id=chain['id']
        )
        self.pb = self.model.add_task(
            row=2, col=10, duration=5, description='PB', project_id=self.pid, chain_id=chain['id']
        )
        self.pb['type'] = 'project_buffer'
        self.model.add_predecessor(self.t2['task_id'], self.t1['task_id'], 'FS')
        self.model.add_predecessor(self.pb['task_id'], self.t2['task_id'], 'PB')
        self.model.capture_project_baseline(self.pid)
        self.model.set_project_phase(self.pid, 'execution')

    def _cutoff_date(self, col):
        return self.model.get_date_for_day(col)

    def test_reclaims_empty_leading_space_with_no_tasks_to_delete(self):
        """Regression: a cutoff with cutoff_col > 0 but zero tasks in range
        (e.g. genuinely empty leading space before the earliest task) must
        still proceed and shift/shrink - not be treated as a no-op just
        because nothing was deleted."""
        import tkinter.messagebox as messagebox
        from unittest.mock import patch

        empty_model = TaskResourceModel()
        empty_model.remove_project(empty_model.projects[0]['id'])
        project = empty_model.add_project('Gap')
        pid = project['id']
        chain = empty_model.get_chain_by_name('Critical')
        # Earliest task starts at col 10 - cols 0-9 are genuinely empty.
        empty_model.add_task(
            row=0, col=10, duration=5, description='T1', project_id=pid, chain_id=chain['id']
        )
        controller = MagicMock()
        controller.model = empty_model
        task_ops = TaskOperations(controller, empty_model)

        days_before = empty_model.days
        start_before = empty_model.start_date
        cutoff = empty_model.get_date_for_day(5)  # squarely in the empty gap

        with patch.object(messagebox, 'askyesno', return_value=True) as mock_confirm, \
             patch.object(messagebox, 'showinfo') as mock_info:
            task_ops._delete_history_confirm(cutoff)

        mock_confirm.assert_called_once()
        mock_info.assert_called_once()
        assert empty_model.days == days_before - 5
        assert empty_model.start_date == start_before.replace(
            day=start_before.day + 5
        )
        controller.update_view.assert_called_once()

    def test_blocking_cutoff_shows_error_and_does_not_delete(self):
        import tkinter.messagebox as messagebox
        from unittest.mock import patch

        with patch.object(messagebox, 'showerror') as mock_error, \
             patch.object(messagebox, 'askyesno') as mock_confirm:
            self.task_ops._delete_history_confirm(self._cutoff_date(6))

        mock_error.assert_called_once()
        mock_confirm.assert_not_called()
        assert self.model.get_task(self.t2['task_id']) is not None

    def test_confirmed_cutoff_deletes_and_updates_view(self):
        import tkinter.messagebox as messagebox
        from unittest.mock import patch

        with patch.object(messagebox, 'askyesno', return_value=True), \
             patch.object(messagebox, 'showinfo') as mock_info:
            self.task_ops._delete_history_confirm(self._cutoff_date(5))

        assert self.model.get_task(self.t1['task_id']) is None
        assert self.t2['col'] == 0
        self.controller.update_view.assert_called_once()
        mock_info.assert_called_once()

    def test_declined_confirmation_makes_no_changes(self):
        import tkinter.messagebox as messagebox
        from unittest.mock import patch

        with patch.object(messagebox, 'askyesno', return_value=False):
            self.task_ops._delete_history_confirm(self._cutoff_date(5))

        assert self.model.get_task(self.t1['task_id']) is not None
        self.controller.update_view.assert_not_called()

    def test_cutoff_before_start_is_a_no_op(self):
        import tkinter.messagebox as messagebox
        from unittest.mock import patch

        with patch.object(messagebox, 'showinfo') as mock_info:
            self.task_ops._delete_history_confirm(self.model.start_date)

        mock_info.assert_called_once()
        assert self.model.get_task(self.t1['task_id']) is not None


class TestExtendTimeline:
    """Stage 13's "growing the right side" half - the counterpart to Delete
    History, needed so rolling-wave planning can keep scheduling further
    into the future."""

    def setup_method(self):
        self.model = TaskResourceModel()

    def test_extends_days_and_capacity(self):
        days_before = self.model.days
        self.model.add_resource('R1')
        resource = self.model.get_resource_by_name('R1')
        cap_len_before = len(resource['capacity'])

        result = self.model.extend_timeline(30)

        assert result is True
        assert self.model.days == days_before + 30
        assert len(resource['capacity']) == cap_len_before + 30

    def test_new_days_default_to_full_capacity(self):
        self.model.add_resource('R1')
        resource = self.model.get_resource_by_name('R1')
        days_before = self.model.days

        self.model.extend_timeline(10)

        assert all(c == 1.0 for c in resource['capacity'][days_before:])

    def test_new_days_respect_works_weekends(self):
        self.model.add_resource('WeekendOff', works_weekends=False)
        resource = self.model.get_resource_by_name('WeekendOff')
        days_before = self.model.days

        self.model.extend_timeline(14)

        for day in range(days_before, self.model.days):
            expected = (
                0.0 if self.model.get_date_for_day(day).weekday() >= 5 else 1.0
            )
            assert resource['capacity'][day] == expected

    def test_existing_days_untouched(self):
        self.model.add_resource('R1')
        resource = self.model.get_resource_by_name('R1')
        resource['capacity'][3] = 0.5

        self.model.extend_timeline(10)

        assert resource['capacity'][3] == 0.5

    def test_returns_false_for_non_positive_additional_days(self):
        days_before = self.model.days
        assert self.model.extend_timeline(0) is False
        assert self.model.extend_timeline(-5) is False
        assert self.model.days == days_before


class TestExtendTimelineDialog:
    def setup_method(self):
        self.model = TaskResourceModel()
        self.controller = MagicMock()
        self.controller.model = self.model
        self.task_ops = TaskOperations(self.controller, self.model)

    def test_confirmed_extends_and_updates_view(self):
        import tkinter.simpledialog as simpledialog
        import tkinter.messagebox as messagebox
        from unittest.mock import patch

        days_before = self.model.days
        with patch.object(simpledialog, 'askinteger', return_value=20), \
             patch.object(messagebox, 'showinfo') as mock_info:
            self.task_ops.extend_timeline_dialog()

        assert self.model.days == days_before + 20
        self.controller.update_view.assert_called_once()
        mock_info.assert_called_once()

    def test_cancelled_dialog_makes_no_changes(self):
        import tkinter.simpledialog as simpledialog
        from unittest.mock import patch

        days_before = self.model.days
        with patch.object(simpledialog, 'askinteger', return_value=None):
            self.task_ops.extend_timeline_dialog()

        assert self.model.days == days_before
        self.controller.update_view.assert_not_called()
