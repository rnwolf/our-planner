"""Tests for the general CSV export (Stage 19 rework): snake_case columns
aligned with the ccpm-scheduler vocabulary, one `resource_ids` column with
`id:allocation` tokens instead of Resources/Resource Allocations, identity-only
resources CSV (derived stats live in the per-day loading CSV), and tags/colour
carried."""

import csv
from unittest.mock import MagicMock

from src.model.task_resource_model import TaskResourceModel
from src.operations.export_operations import ExportOperations, _resource_token


def make_export_ops():
    model = TaskResourceModel()
    controller = MagicMock()
    controller.model = model
    controller.tag_ops.get_filtered_tasks.side_effect = lambda: model.tasks
    controller.tag_ops.get_filtered_resources.side_effect = lambda: model.resources
    return model, ExportOperations(controller, model)


def read_csv(path):
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        return reader.fieldnames, list(reader)


class TestResourceToken:
    def test_token_forms(self):
        assert _resource_token(5, 1.0) == '5'
        assert _resource_token(5, 2.0) == '5:2'
        assert _resource_token(3, 0.5) == '3:0.5'


class TestWriteCsvExport:
    def test_tasks_columns_and_values(self, tmp_path):
        model, ops = make_export_ops()
        project_id = model.projects[0]['id']
        a = model.add_task(
            row=1, col=5, duration=4, description='Spec',
            resources={1: 1.0, 2: 2.0, 3: 0.5},
            tags=['alpha', 'beta'], url='https://example.com',
            project_id=project_id)
        a['color'] = 'salmon'
        a['optimal_duration'] = 2
        model.add_task(
            row=2, col=9, duration=3, description='Build',
            resources={2: 1.0},
            predecessors=[{'id': a['task_id'], 'type': 'SS', 'lag': 2}],
            project_id=project_id)

        tasks_file, resources_file, loading_file = ops._write_csv_export(
            str(tmp_path))
        fieldnames, rows = read_csv(tasks_file)

        assert fieldnames == [
            'id', 'name', 'project', 'chain', 'row', 'start_day',
            'start_date', 'end_date', 'duration', 'realistic_duration',
            'optimal_duration', 'predecessor_ids', 'resource_ids', 'tags',
            'colour', 'url']

        by_name = {r['name']: r for r in rows}
        spec = by_name['Spec']
        assert spec['id'] == str(a['task_id'])
        assert spec['start_day'] == '5'  # absolute timeline day (= col)
        assert spec['row'] == '1'
        assert spec['duration'] == '4'
        assert spec['optimal_duration'] == '2'
        assert spec['resource_ids'] == '1;2:2;3:0.5'
        assert spec['tags'] == 'alpha,beta'
        assert spec['colour'] == 'salmon'
        assert spec['project'] == model.projects[0]['name']
        assert spec['url'] == 'https://example.com'

        build = by_name['Build']
        assert build['predecessor_ids'] == f"{a['task_id']}:SS+2"
        assert build['resource_ids'] == '2'
        assert build['optimal_duration'] == ''

    def test_resources_identity_only(self, tmp_path):
        model, ops = make_export_ops()
        model.get_resource_by_id(2)['capacity'] = [2.0] * model.days
        model.get_resource_by_id(2)['tags'] = ['team-a']

        _, resources_file, _ = ops._write_csv_export(str(tmp_path))
        fieldnames, rows = read_csv(resources_file)

        # Derived stats (Total Capacity/Loading, Average/Peak Utilization)
        # are gone; shape aligns with the CCPM resources.csv plus tags
        assert fieldnames == ['id', 'name', 'capacity', 'tags']
        by_id = {r['id']: r for r in rows}
        assert by_id['1']['capacity'] == '1'
        assert by_id['2']['capacity'] == '2'
        assert by_id['2']['tags'] == 'team-a'

    def test_loading_csv_unchanged(self, tmp_path):
        model, ops = make_export_ops()
        _, _, loading_file = ops._write_csv_export(str(tmp_path))
        fieldnames, rows = read_csv(loading_file)
        assert fieldnames[:2] == ['Resource ID', 'Resource Name']
        assert len(rows) == len(model.resources)

    def test_predecessor_ids_parse_back(self, tmp_path):
        """The semicolon-joined predecessor tokens must round-trip through
        the shared notation parser (same contract as the CCPM files)."""
        from src.model.dependency_notation import parse_predecessor_notation

        model, ops = make_export_ops()
        a = model.add_task(row=1, col=0, duration=2, description='A')
        model.add_task(
            row=2, col=2, duration=2, description='B',
            predecessors=[{'id': a['task_id'], 'type': 'FS', 'lag': 0},
                          {'id': a['task_id'], 'type': 'FF', 'lag': -1}])
        tasks_file, _, _ = ops._write_csv_export(str(tmp_path))
        _, rows = read_csv(tasks_file)
        b_row = next(r for r in rows if r['name'] == 'B')
        assert ';' in b_row['predecessor_ids']
        parsed = parse_predecessor_notation(b_row['predecessor_ids'])
        assert {(e['id'], e['type'], e['lag']) for e in parsed} == {
            (a['task_id'], 'FS', 0), (a['task_id'], 'FF', -1)}
