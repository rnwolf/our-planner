"""Tests for the CCPM round trip (Stage 16): export a project network in the
external ccpm-scheduler's input format, and the in-process 'Schedule with
CCPM' flow that validates, schedules, and imports the result as a new
project.

The scenario mirrors the scheduler's own worked example (6 tasks, one
resource conflict), so the expected numbers — critical chain length 30,
project buffer 15, promised completion day 45 — are independently documented
in that repo's references/worked-example.md.
"""

from datetime import datetime
from unittest.mock import MagicMock

from src.model.task_resource_model import TaskResourceModel
from src.operations.ccpm_operations import CcpmOperations


def make_worked_example():
    """A=Spec r1, B=Build r2, C=Design r1, D=Integrate r1, E=Test rig r2,
    F=Commission r3; realistic durations 10/20/10/20/10/10."""
    model = TaskResourceModel()
    project_id = model.projects[0]['id']

    def add(desc, dur, preds, rid):
        task = model.add_task(
            row=1, col=0, duration=dur, description=desc,
            resources={rid: 1.0},
            predecessors=[{'id': p, 'type': 'FS', 'lag': 0} for p in preds],
            project_id=project_id)
        return task['task_id']

    a = add('Spec', 10, [], 1)
    b = add('Build', 20, [a], 2)
    c = add('Design', 10, [a], 1)
    d = add('Integrate', 20, [b], 1)
    e = add('Test rig', 10, [c], 2)
    f = add('Commission', 10, [d, e], 3)
    ids = dict(A=a, B=b, C=c, D=d, E=e, F=f)

    controller = MagicMock()
    controller.model = model
    return model, project_id, ids, CcpmOperations(controller, model)


class TestBuildNetworkData:
    def test_maps_worked_example(self):
        model, project_id, ids, ops = make_worked_example()
        data, warnings = ops.build_network_data(project_id)
        assert warnings == []
        assert len(data['tasks']) == 6
        by_name = {t['name']: t for t in data['tasks']}
        assert by_name['Spec']['realistic_duration'] == 10
        assert by_name['Spec']['optimal_duration'] is None
        assert by_name['Commission']['predecessors'] == [
            {'id': str(ids['D']), 'type': 'FS', 'lag': 0},
            {'id': str(ids['E']), 'type': 'FS', 'lag': 0}]
        assert by_name['Build']['resources'] == {'2': 1.0}
        assert {r['name'] for r in data['resources']} == \
            {'Resource A', 'Resource B', 'Resource C'}
        assert 'calendar' not in data  # uniform capacity -> no windows

    def test_excludes_buffers_and_complete_tasks(self):
        model, project_id, ids, ops = make_worked_example()
        model.set_task_type(ids['E'], 'feeding_buffer')
        done = next(t for t in model.tasks if t['task_id'] == ids['C'])
        done['actual_start_date'] = done['actual_end_date'] = datetime(2026, 7, 1)
        data, warnings = ops.build_network_data(project_id)
        names = {t['name'] for t in data['tasks']}
        assert 'Test rig' not in names and 'Design' not in names
        # links into the excluded tasks were dropped with warnings
        by_name = {t['name']: t for t in data['tasks']}
        assert by_name['Commission']['predecessors'] == [
            {'id': str(ids['D']), 'type': 'FS', 'lag': 0}]
        assert any('buffer' in w for w in warnings)
        assert any('complete' in w for w in warnings)

    def test_capacity_encoding(self):
        _, _, _, ops = make_worked_example()
        base, windows = ops._encode_capacity(
            [1.0, 1.0, 0.0, 0.0, 2.0, 1.0, 1.0])
        assert base == 1
        assert windows == [(2, 4, 0), (4, 5, 2)]

    def test_calendar_windows_exported(self):
        model, project_id, ids, ops = make_worked_example()
        model.get_resource_by_id(2)['capacity'][2:4] = [0.0, 0.0]
        data, _ = ops.build_network_data(project_id)
        assert data['calendar'] == [
            {'resource_id': '2', 'from': 2, 'to': 4, 'capacity': 0}]


class TestScheduleProjectCore:
    def test_schedules_and_imports_as_new_project(self):
        model, project_id, ids, ops = make_worked_example()
        n_resources = len(model.resources)
        result = ops.schedule_project_core(project_id)
        assert result['ok'], result
        stats = result['stats']
        assert stats.critical_chain == [str(ids[k]) for k in 'ABDF']
        assert stats.critical_chain_length == 30
        assert stats.project_buffer == 15
        assert stats.promise_day == 45

        project = result['project']
        assert project['name'] == 'Sample Project (CCPM)'
        new_tasks = [t for t in model.tasks
                     if t['project_id'] == project['id']]
        assert len(new_tasks) == result['task_count'] == 8  # 6 tasks + FB + PB
        by_type = {}
        for t in new_tasks:
            by_type.setdefault(t['type'], []).append(t)
        assert len(by_type['project_buffer']) == 1
        assert len(by_type['feeding_buffer']) == 1
        pb = by_type['project_buffer'][0]
        assert (pb['col'], pb['duration']) == (30, 15)

        # critical chain tasks got the critical chain assigned
        critical = model.get_critical_chain()
        cc_tasks = [t for t in new_tasks if t['chain_id'] == critical['id']
                    and t['type'] == 'task']
        assert {t['description'] for t in cc_tasks} == \
            {'Spec', 'Build', 'Integrate', 'Commission'}

        # shared resource pool: reused by name, none duplicated
        assert len(model.resources) == n_resources
        # source project untouched
        assert all(t['col'] == 0 for t in model.tasks
                   if t['project_id'] == project_id)

    def test_validation_failure_reports_coded_issues(self):
        model, project_id, ids, ops = make_worked_example()
        task = next(t for t in model.tasks if t['task_id'] == ids['B'])
        task['resources'] = {}
        n_projects = len(model.projects)
        result = ops.schedule_project_core(project_id)
        assert not result['ok']
        assert 'E_NO_RESOURCE' in {i['code'] for i in result['issues']}
        assert len(model.projects) == n_projects  # nothing created

    def test_fractional_allocation_rejected(self):
        model, project_id, ids, ops = make_worked_example()
        task = next(t for t in model.tasks if t['task_id'] == ids['B'])
        task['resources'] = {2: 0.5}
        result = ops.schedule_project_core(project_id)
        assert not result['ok']
        assert 'E_FRACTIONAL_ALLOCATION' in {i['code'] for i in result['issues']}

    def test_empty_project(self):
        model, _, _, ops = make_worked_example()
        empty = model.add_project('Empty')
        result = ops.schedule_project_core(empty['id'])
        assert not result['ok']
        assert result['issues'][0]['code'] == 'E_EMPTY_PROJECT'

    def test_duplicate_name_gets_suffix(self):
        model, project_id, _, ops = make_worked_example()
        model.add_project('Sample Project (CCPM)')
        result = ops.schedule_project_core(project_id)
        assert result['ok']
        assert result['project']['name'] == 'Sample Project (CCPM) (2)'


class TestExportNetworkCore:
    def test_export_accepted_by_scheduler(self, tmp_path):
        """The exported CSVs must be valid input for the external tool."""
        from ccpm_scheduler import load_network, validate_network, build_schedule

        model, project_id, ids, ops = make_worked_example()
        model.get_resource_by_id(2)['capacity'][2:4] = [0.0, 0.0]
        files, warnings = ops.export_network_core(project_id, tmp_path)
        assert [f.split('/')[-1] for f in files] == \
            ['tasks.csv', 'resources.csv', 'calendar.csv']

        net = load_network(tmp_path / 'tasks.csv', tmp_path / 'resources.csv',
                           tmp_path / 'calendar.csv')
        report = validate_network(net)
        assert report.ok, [i.message for i in report.errors]
        result = build_schedule(net, 'export-roundtrip')
        assert result.stats.critical_chain == [str(ids[k]) for k in 'ABDF']

    def test_fractional_allocation_warns(self, tmp_path):
        model, project_id, ids, ops = make_worked_example()
        task = next(t for t in model.tasks if t['task_id'] == ids['B'])
        task['resources'] = {2: 0.5}
        _, warnings = ops.export_network_core(project_id, tmp_path)
        assert any('allocation 0.5' in w for w in warnings)
