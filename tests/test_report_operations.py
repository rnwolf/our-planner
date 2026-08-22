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


class TestResourceOverallocationReport:
    """Unlike Full-Kit Readiness/Status Update Log, this report is
    deliberately NOT project-scoped - a resource's real demand sums every
    project. Only the extractor half (compute_resource_overallocations/
    compute_tag_overallocations) is exercised here, same rationale as the
    other report classes in this file."""

    def setup_method(self):
        self.model = TaskResourceModel()
        self.controller = MagicMock()
        self.controller.model = self.model
        self.tag_ops = TagOperations(self.controller, self.model)
        self.controller.tag_ops = self.tag_ops
        self.report_ops = ReportOperations(self.controller, self.model)

    def test_cross_project_aggregation_is_one_combined_finding(self):
        """The one deliberate architectural difference from Full-Kit
        Readiness: two projects both loading the same resource the same
        day must produce ONE finding, not two."""
        resource = self.model.resources[0]
        p1 = self.model.add_project('Alpha')
        p2 = self.model.add_project('Beta')
        self.model.add_task(
            row=0,
            col=0,
            duration=1,
            description='A',
            project_id=p1['id'],
            resources={resource['id']: 0.6},
        )
        self.model.add_task(
            row=1,
            col=0,
            duration=1,
            description='B',
            project_id=p2['id'],
            resources={resource['id']: 0.9},
        )

        findings = self.report_ops.compute_resource_overallocations()

        assert len(findings) == 1
        assert findings[0]['key'] == resource['id']
        assert findings[0]['load'] == 1.5

    def test_respects_resource_load_scope_filtered(self):
        """resource_load_scope == 'filtered' narrows to the currently
        filtered tasks - the same wiring update_resource_loading() itself
        uses (task_manager.py) - not every task in the model."""
        resource = self.model.resources[0]
        p1 = self.model.add_project('Alpha')
        p2 = self.model.add_project('Beta')
        self.model.add_task(
            row=0,
            col=0,
            duration=1,
            description='A',
            project_id=p1['id'],
            resources={resource['id']: 1.5},
        )
        self.model.add_task(
            row=1,
            col=0,
            duration=1,
            description='B',
            project_id=p2['id'],
            resources={resource['id']: 1.5},
        )

        # Unfiltered (the 'all' default): both tasks count.
        findings = self.report_ops.compute_resource_overallocations()
        assert findings[0]['load'] == 3.0

        # Filtered to just project Alpha.
        self.tag_ops.resource_load_scope = 'filtered'
        self.tag_ops.task_project_filters = [p1['id']]
        findings = self.report_ops.compute_resource_overallocations()
        assert findings[0]['load'] == 1.5

    def test_by_tag_view_aggregates_across_resources(self):
        self.model.resources = [
            {
                'id': 1,
                'name': 'Alice',
                'capacity': [1.0] * self.model.days,
                'tags': ['dev'],
            },
            {
                'id': 2,
                'name': 'Bob',
                'capacity': [1.0] * self.model.days,
                'tags': ['dev'],
            },
        ]
        project = self.model.add_project('Alpha')
        self.model.add_task(
            row=0,
            col=0,
            duration=1,
            description='A',
            project_id=project['id'],
            resources={1: 1.0},
        )
        self.model.add_task(
            row=1,
            col=0,
            duration=1,
            description='B',
            project_id=project['id'],
            resources={2: 1.5},
        )

        findings = self.report_ops.compute_tag_overallocations()

        assert len(findings) == 1
        assert findings[0]['kind'] == 'tag'
        assert findings[0]['key'] == 'dev'
        assert findings[0]['load'] == 2.5


class TestResourceScheduleReport:
    """Per-resource in-flight/upcoming schedule with relay-baton context.
    Only the extractor half (compute_resource_schedule) is exercised here,
    same rationale as the other report classes in this file."""

    def setup_method(self):
        self.model = TaskResourceModel()
        self.controller = MagicMock()
        self.controller.model = self.model
        self.tag_ops = TagOperations(self.controller, self.model)
        self.controller.tag_ops = self.tag_ops
        self.report_ops = ReportOperations(self.controller, self.model)

    def _bucket_for(self, buckets, resource_id):
        return next(b for b in buckets if b['resource_id'] == resource_id)

    def test_in_flight_vs_upcoming_split(self):
        project = self.model.add_project('Alpha')
        resource = self.model.resources[0]

        started = self.model.add_task(
            row=0,
            col=0,
            duration=5,
            description='Started',
            project_id=project['id'],
            resources={resource['id']: 1.0},
        )
        started['actual_start_date'] = self.model.setdate.isoformat()
        self.model.record_remaining_duration(started['task_id'], 2)

        self.model.add_task(
            row=1,
            col=5,
            duration=3,
            description='Not started',
            project_id=project['id'],
            resources={resource['id']: 1.0},
        )

        buckets = self.report_ops.compute_resource_schedule()

        assert len(buckets) == 1
        bucket = buckets[0]
        assert bucket['resource_id'] == resource['id']
        assert [r['task_description'] for r in bucket['in_flight']] == ['Started']
        assert bucket['in_flight'][0]['latest_remaining_duration'] == 2
        # Cross-checked against the model's own math rather than a
        # hardcoded percentage - record_remaining_duration also re-anchors
        # the task's duration to the latest estimate, so the "expected"
        # fraction isn't a fixed arithmetic result of the numbers above.
        expected_progress = round(
            self.model.get_task_progress_fraction(started['task_id']) * 100
        )
        assert bucket['in_flight'][0]['progress_pct'] == expected_progress
        assert [r['task_description'] for r in bucket['upcoming']] == ['Not started']

    def test_split_allocation_produces_one_row_per_task(self):
        """A resource spread across two simultaneous tasks (e.g. 0.5 +
        0.5) must show up as two rows, each carrying its own allocation -
        not merged into one, and not ambiguous about which task got how
        much."""
        project = self.model.add_project('Alpha')
        resource = self.model.resources[0]
        self.model.add_task(
            row=0,
            col=0,
            duration=3,
            description='Task1',
            project_id=project['id'],
            resources={resource['id']: 0.5},
        )
        self.model.add_task(
            row=1,
            col=0,
            duration=3,
            description='Task2',
            project_id=project['id'],
            resources={resource['id']: 0.5},
        )

        buckets = self.report_ops.compute_resource_schedule()

        upcoming = buckets[0]['upcoming']
        assert len(upcoming) == 2
        assert sorted(r['allocation'] for r in upcoming) == [0.5, 0.5]
        assert {r['task_description'] for r in upcoming} == {'Task1', 'Task2'}

    def _build_merge_scenario(self):
        """F1 (feeding, resourced) -> FB (feeding buffer) -> C2 (merge,
        resourced) - the same shape as test_fever_chart_merge_signal.py,
        used here to exercise baton resolution walking past the buffer."""
        project = self.model.add_project('Merge scenario')
        r_f1 = self.model.resources[0]
        r_c2 = self.model.resources[1]

        f1 = self.model.add_task(
            row=0,
            col=0,
            duration=3,
            description='F1',
            project_id=project['id'],
            resources={r_f1['id']: 1.0},
        )
        fb = self.model.add_task(
            row=1,
            col=3,
            duration=5,
            description='FB',
            project_id=project['id'],
        )
        fb['type'] = 'feeding_buffer'
        c2 = self.model.add_task(
            row=2,
            col=8,
            duration=5,
            description='C2',
            project_id=project['id'],
            resources={r_c2['id']: 1.0},
        )
        self.model.add_predecessor(fb['task_id'], f1['task_id'], 'FS')
        self.model.add_predecessor(c2['task_id'], fb['task_id'], 'FB')

        return project, r_f1, r_c2, f1, c2

    def test_baton_from_walks_past_feeding_buffer_to_terminal_task(self):
        project, r_f1, r_c2, f1, c2 = self._build_merge_scenario()

        buckets = self.report_ops.compute_resource_schedule()
        c2_row = self._bucket_for(buckets, r_c2['id'])['upcoming'][0]

        assert len(c2_row['baton_from']) == 1
        baton = c2_row['baton_from'][0]
        assert baton['needs_attention'] is False
        assert baton['task_id'] == f1['task_id']
        assert baton['resources'] == [
            {'resource_name': r_f1['name'], 'resource_email': ''}
        ]

    def test_baton_to_walks_past_feeding_buffer_to_merge_task(self):
        project, r_f1, r_c2, f1, c2 = self._build_merge_scenario()

        buckets = self.report_ops.compute_resource_schedule()
        f1_row = self._bucket_for(buckets, r_f1['id'])['upcoming'][0]

        assert len(f1_row['baton_to']) == 1
        baton = f1_row['baton_to'][0]
        assert baton['needs_attention'] is False
        assert baton['task_id'] == c2['task_id']
        assert baton['resources'] == [
            {'resource_name': r_c2['name'], 'resource_email': ''}
        ]

    def test_baton_to_project_buffer_is_end_of_project_not_a_flag(self):
        """A project buffer has no merge task by definition - it protects
        the project's finish date, not a merge into another chain - so a
        task whose only successor is the project buffer must NOT come back
        needs_attention (found live: get_buffer_merge_task legitimately
        returns None for a buffer with zero successors, and the generic
        buffer-resolution path was flagging that as if it were a broken/
        ambiguous merge)."""
        project = self.model.add_project('Alpha')
        resource = self.model.resources[0]
        last_task = self.model.add_task(
            row=0,
            col=0,
            duration=3,
            description='Last real task',
            project_id=project['id'],
            resources={resource['id']: 1.0},
        )
        pb = self.model.add_task(
            row=1,
            col=3,
            duration=5,
            description='Project buffer',
            project_id=project['id'],
        )
        pb['type'] = 'project_buffer'
        self.model.add_predecessor(pb['task_id'], last_task['task_id'], 'PB')

        buckets = self.report_ops.compute_resource_schedule()
        row = buckets[0]['upcoming'][0]

        assert len(row['baton_to']) == 1
        baton = row['baton_to'][0]
        assert baton['needs_attention'] is False
        assert baton['resources'] == []
        assert 'end of project' in baton['message'].lower()

    def test_flags_unassigned_predecessor_instead_of_skipping_it(self):
        project = self.model.add_project('Alpha')
        resource = self.model.resources[0]
        unassigned = self.model.add_task(
            row=0,
            col=0,
            duration=2,
            description='Unassigned pred',
            project_id=project['id'],
        )
        successor = self.model.add_task(
            row=1,
            col=2,
            duration=2,
            description='Has resource',
            project_id=project['id'],
            resources={resource['id']: 1.0},
        )
        self.model.add_predecessor(successor['task_id'], unassigned['task_id'], 'FS')

        buckets = self.report_ops.compute_resource_schedule()
        row = buckets[0]['upcoming'][0]

        assert len(row['baton_from']) == 1
        baton = row['baton_from'][0]
        assert baton['needs_attention'] is True
        assert baton['task_id'] == unassigned['task_id']
        assert 'no resource assigned' in baton['message']

    def test_respects_active_filter_menu_state(self):
        """Scoped by the currently active Filter menu selection, same as
        every other report in this module - exercised via the real
        get_filtered_tasks(), not bypassed."""
        project = self.model.add_project('Alpha')
        resource = self.model.resources[0]
        started = self.model.add_task(
            row=0,
            col=0,
            duration=3,
            description='Started',
            project_id=project['id'],
            resources={resource['id']: 1.0},
        )
        started['actual_start_date'] = self.model.setdate.isoformat()
        self.model.add_task(
            row=1,
            col=3,
            duration=3,
            description='Not started',
            project_id=project['id'],
            resources={resource['id']: 1.0},
        )

        self.tag_ops.task_state_filters = ['not_started']

        buckets = self.report_ops.compute_resource_schedule()

        bucket = buckets[0]
        assert bucket['in_flight'] == []
        assert [r['task_description'] for r in bucket['upcoming']] == ['Not started']

    def test_include_notes_option(self):
        project = self.model.add_project('Alpha')
        resource = self.model.resources[0]
        task = self.model.add_task(
            row=0,
            col=0,
            duration=2,
            description='Noted',
            project_id=project['id'],
            resources={resource['id']: 1.0},
        )
        self.model.add_note_to_task(task['task_id'], 'first note')
        self.model.add_note_to_task(task['task_id'], 'second note')

        without_notes = self.report_ops.compute_resource_schedule()
        row_without = without_notes[0]['upcoming'][0]
        assert 'notes' not in row_without

        with_notes = self.report_ops.compute_resource_schedule(include_notes=True)
        row_with = with_notes[0]['upcoming'][0]
        assert [n['text'] for n in row_with['notes']] == [
            'first note',
            'second note',
        ]

    def test_no_tasks_returns_no_buckets(self):
        self.model.add_project('Empty')
        buckets = self.report_ops.compute_resource_schedule()
        assert buckets == []

    def test_aggregates_across_all_projects_without_a_selector(self):
        """No project selector - a resource's schedule spans every
        project at once, same convention as Resource Over-Allocation."""
        p1 = self.model.add_project('Alpha')
        p2 = self.model.add_project('Beta')
        resource = self.model.resources[0]
        self.model.add_task(
            row=0,
            col=0,
            duration=3,
            description='Alpha task',
            project_id=p1['id'],
            resources={resource['id']: 1.0},
        )
        self.model.add_task(
            row=1,
            col=0,
            duration=3,
            description='Beta task',
            project_id=p2['id'],
            resources={resource['id']: 1.0},
        )

        buckets = self.report_ops.compute_resource_schedule()

        assert len(buckets) == 1
        upcoming = buckets[0]['upcoming']
        assert {r['task_description'] for r in upcoming} == {
            'Alpha task',
            'Beta task',
        }
        assert {r['project_name'] for r in upcoming} == {'Alpha', 'Beta'}

    def test_project_drops_out_once_all_its_tasks_are_done(self):
        """A project isn't dropped by any special-case bookkeeping - once
        every one of its tasks is 'complete' (get_task_state), none of them
        pass the in_progress/not_started filter any more, so the project
        simply stops contributing rows."""
        p1 = self.model.add_project('Alpha')
        p2 = self.model.add_project('Beta')
        resource = self.model.resources[0]
        done_task = self.model.add_task(
            row=0,
            col=0,
            duration=3,
            description='Alpha done',
            project_id=p1['id'],
            resources={resource['id']: 1.0},
        )
        done_task['actual_start_date'] = self.model.setdate.isoformat()
        done_task['actual_end_date'] = self.model.setdate.isoformat()
        self.model.add_task(
            row=1,
            col=0,
            duration=3,
            description='Beta task',
            project_id=p2['id'],
            resources={resource['id']: 1.0},
        )

        buckets = self.report_ops.compute_resource_schedule()

        rows = buckets[0]['in_flight'] + buckets[0]['upcoming']
        assert {r['task_description'] for r in rows} == {'Beta task'}
        assert {r['project_name'] for r in rows} == {'Beta'}
