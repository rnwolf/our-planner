"""File > Import Network (Import Resources... / Import Resource
Calendars... / Import Tasks...): round-tripping a plain, unscheduled
reference network, matched by id rather than name/foreign-string
remapping (unlike the older Import CCPM Schedule... path). See
file_operations.py's "Import Network Data" section and
src/view/menus/help_menu.py's "Importing Your Project" docs for the
full behavioral contract this covers.
"""

import csv
from unittest.mock import MagicMock, patch

from src.model.task_resource_model import TaskResourceModel
from src.operations.file_operations import FileOperations, _parse_resource_tokens


def write_csv(path, header, rows):
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(header)
        for r in rows:
            w.writerow(r)


def make_file_ops():
    model = TaskResourceModel()
    controller = MagicMock()
    controller.model = model
    controller.default_project_id = model.default_project_id
    file_ops = FileOperations(controller, model)
    return model, controller, file_ops


def run_import(file_ops, method_name, csv_path, confirm=True):
    """Invoke one of the three import methods with filedialog/messagebox
    mocked - askopenfilename returns csv_path, askyesno returns `confirm`.
    Returns the list of (title, message) pairs passed to showerror, so
    tests can assert on abort behavior without a real popup."""
    errors = []
    with (
        patch(
            'src.operations.file_operations.filedialog.askopenfilename',
            return_value=csv_path,
        ),
        patch(
            'src.operations.file_operations.messagebox.askyesno', return_value=confirm
        ),
        patch('src.operations.file_operations.messagebox.showinfo'),
        patch(
            'src.operations.file_operations.messagebox.showerror',
            side_effect=lambda title, msg, **k: errors.append((title, msg)),
        ),
    ):
        getattr(file_ops, method_name)()
    return errors


class TestParseResourceTokens:
    def test_bare_id_defaults_to_allocation_one(self):
        assert _parse_resource_tokens('5') == {5: 1.0}

    def test_explicit_allocation(self):
        assert _parse_resource_tokens('1:1;2:2') == {1: 1.0, 2: 2.0}

    def test_mixed_bare_and_explicit(self):
        assert _parse_resource_tokens('1;2:2;3') == {1: 1.0, 2: 2.0, 3: 1.0}

    def test_blank_is_empty(self):
        assert _parse_resource_tokens('') == {}
        assert _parse_resource_tokens(None) == {}


class TestImportResources:
    def test_creates_new_resource_with_capacity_and_url(self, tmp_path):
        model, controller, file_ops = make_file_ops()
        path = tmp_path / 'resources.csv'
        write_csv(
            path,
            ['id', 'name', 'capacity', 'url'],
            [[500, 'Widget Line', 3, 'http://example.com/widget']],
        )

        run_import(file_ops, 'import_resources', str(path))

        r = model.get_resource_by_id(500)
        assert r is not None
        assert r['name'] == 'Widget Line'
        assert r['url'] == 'http://example.com/widget'
        assert r['capacity'][0] == 3.0

    def test_existing_resource_name_and_url_updated_only_when_nonempty(self, tmp_path):
        model, controller, file_ops = make_file_ops()
        existing_id = model.resources[0]['id']
        model.resources[0]['url'] = 'http://old.example'

        path = tmp_path / 'resources.csv'
        write_csv(
            path, ['id', 'name', 'url'], [[existing_id, 'Renamed', '']]
        )  # url blank -> unchanged

        run_import(file_ops, 'import_resources', str(path))

        r = model.get_resource_by_id(existing_id)
        assert r['name'] == 'Renamed'
        assert r['url'] == 'http://old.example'

    def test_existing_resource_capacity_reset_when_provided(self, tmp_path):
        model, controller, file_ops = make_file_ops()
        r = model.resources[0]
        # Give it a weekend-off per-day pattern first.
        for day in range(model.days):
            if model.get_date_for_day(day).weekday() >= 5:
                r['capacity'][day] = 0.0
        pattern_before = list(r['capacity'])

        path = tmp_path / 'resources.csv'
        write_csv(path, ['id', 'name', 'capacity'], [[r['id'], '', 4]])
        run_import(file_ops, 'import_resources', str(path))

        assert all(c == 4.0 for c in r['capacity'])
        assert r['capacity'] != pattern_before

    def test_existing_resource_capacity_untouched_when_blank(self, tmp_path):
        model, controller, file_ops = make_file_ops()
        r = model.resources[1]
        before = list(r['capacity'])

        path = tmp_path / 'resources.csv'
        write_csv(path, ['id', 'name', 'capacity'], [[r['id'], '', '']])
        run_import(file_ops, 'import_resources', str(path))

        assert r['capacity'] == before

    def test_bad_id_aborts_with_no_changes(self, tmp_path):
        model, controller, file_ops = make_file_ops()
        count_before = len(model.resources)

        path = tmp_path / 'resources.csv'
        write_csv(path, ['id', 'name'], [['not-a-number', 'Bad']])
        errors = run_import(file_ops, 'import_resources', str(path))

        assert errors, 'expected an error popup'
        assert len(model.resources) == count_before

    def test_header_whitespace_is_tolerated(self, tmp_path):
        """Regression: a header like 'capacity ' (trailing space, as seen
        from a spreadsheet export) must not silently drop the column."""
        model, controller, file_ops = make_file_ops()
        path = tmp_path / 'resources.csv'
        with open(path, 'w', newline='', encoding='utf-8') as f:
            f.write('id,name,capacity \n')
            f.write('501,Padded Header,7\n')

        run_import(file_ops, 'import_resources', str(path))
        r = model.get_resource_by_id(501)
        assert r is not None
        assert r['capacity'][0] == 7.0


class TestImportResourceCalendars:
    def test_applies_override_to_existing_resource(self, tmp_path):
        model, controller, file_ops = make_file_ops()
        r = model.resources[0]

        path = tmp_path / 'calendar.csv'
        write_csv(path, ['resource_id', 'from', 'to', 'capacity'], [[r['id'], 2, 4, 0]])
        run_import(file_ops, 'import_resource_calendars', str(path))

        assert r['capacity'][2] == 0.0
        assert r['capacity'][3] == 0.0
        assert r['capacity'][4] != 0.0  # half-open: day 4 untouched

    def test_missing_resource_aborts_with_no_changes(self, tmp_path):
        model, controller, file_ops = make_file_ops()
        before = [list(r['capacity']) for r in model.resources]

        path = tmp_path / 'calendar.csv'
        write_csv(path, ['resource_id', 'from', 'to', 'capacity'], [[999999, 0, 2, 0]])
        errors = run_import(file_ops, 'import_resource_calendars', str(path))

        assert errors
        after = [list(r['capacity']) for r in model.resources]
        assert before == after


class TestImportTasks:
    def _setup_with_resource(self):
        model, controller, file_ops = make_file_ops()
        resource_id = model.resources[0]['id']
        return model, controller, file_ops, resource_id

    def test_new_task_gets_resource_allocation(self, tmp_path):
        model, controller, file_ops, rid = self._setup_with_resource()
        path = tmp_path / 'tasks.csv'
        write_csv(
            path,
            ['id', 'name', 'realistic_duration', 'predecessor_ids', 'resource_ids'],
            [[100, 'Task A', 5, '', f'{rid}:1']],
        )
        run_import(file_ops, 'import_tasks', str(path))

        t = model.get_task(100)
        assert t is not None
        assert t['resources'] == {rid: 1.0}
        assert t['duration'] == 5
        assert t['realistic_duration'] == 5

    def test_bare_multi_resource_tokens_default_to_allocation_one(self, tmp_path):
        model, controller, file_ops = make_file_ops()
        ids = [r['id'] for r in model.resources[:3]]
        path = tmp_path / 'tasks.csv'
        write_csv(
            path,
            ['id', 'name', 'realistic_duration', 'predecessor_ids', 'resource_ids'],
            [[101, 'All hands', 5, '', ';'.join(str(i) for i in ids)]],
        )
        run_import(file_ops, 'import_tasks', str(path))

        t = model.get_task(101)
        assert t['resources'] == {i: 1.0 for i in ids}

    def test_fs_link_places_successor_at_predecessor_finish(self, tmp_path):
        model, controller, file_ops, rid = self._setup_with_resource()
        model.add_task(row=0, col=10, duration=5, description='Anchor', task_id=800)
        path = tmp_path / 'tasks.csv'
        write_csv(
            path,
            ['id', 'name', 'realistic_duration', 'predecessor_ids', 'resource_ids'],
            [[801, 'FS child', 4, '800', str(rid)]],
        )
        run_import(file_ops, 'import_tasks', str(path))

        assert model.get_task(801)['col'] == 15  # 10 + 5

    def test_ss_link_places_successor_at_predecessor_start_plus_lag(self, tmp_path):
        model, controller, file_ops, rid = self._setup_with_resource()
        model.add_task(row=0, col=10, duration=5, description='Anchor', task_id=800)
        path = tmp_path / 'tasks.csv'
        write_csv(
            path,
            ['id', 'name', 'realistic_duration', 'predecessor_ids', 'resource_ids'],
            [[802, 'SS child', 3, '800:SS+1', str(rid)]],
        )
        run_import(file_ops, 'import_tasks', str(path))

        assert model.get_task(802)['col'] == 11  # 10 + 1

    def test_ff_link_places_successor_finish_relative_to_predecessor_finish(
        self, tmp_path
    ):
        model, controller, file_ops, rid = self._setup_with_resource()
        model.add_task(row=0, col=10, duration=6, description='Anchor', task_id=700)
        path = tmp_path / 'tasks.csv'
        write_csv(
            path,
            ['id', 'name', 'realistic_duration', 'predecessor_ids', 'resource_ids'],
            [[701, 'FF child', 3, '700:FF+1', str(rid)]],
        )
        run_import(file_ops, 'import_tasks', str(path))

        # pred finish (10+6) - own duration (3) + lag (1) = 14
        assert model.get_task(701)['col'] == 14

    def test_sf_link_places_successor_finish_relative_to_predecessor_start(
        self, tmp_path
    ):
        model, controller, file_ops, rid = self._setup_with_resource()
        model.add_task(row=0, col=10, duration=6, description='Anchor', task_id=700)
        path = tmp_path / 'tasks.csv'
        write_csv(
            path,
            ['id', 'name', 'realistic_duration', 'predecessor_ids', 'resource_ids'],
            [[702, 'SF child', 4, '700:SF', str(rid)]],
        )
        run_import(file_ops, 'import_tasks', str(path))

        # pred start (10) - own duration (4) + lag (0) = 6
        assert model.get_task(702)['col'] == 6

    def test_root_task_anchored_at_current_project_date(self, tmp_path):
        model, controller, file_ops, rid = self._setup_with_resource()
        path = tmp_path / 'tasks.csv'
        write_csv(
            path,
            ['id', 'name', 'realistic_duration', 'predecessor_ids', 'resource_ids'],
            [[900, 'Root', 2, '', str(rid)]],
        )
        run_import(file_ops, 'import_tasks', str(path))

        expected = model.get_day_for_date(model.setdate)
        assert model.get_task(900)['col'] == expected

    def test_new_tasks_get_distinct_fresh_rows(self, tmp_path):
        model, controller, file_ops, rid = self._setup_with_resource()
        path = tmp_path / 'tasks.csv'
        write_csv(
            path,
            ['id', 'name', 'realistic_duration', 'predecessor_ids', 'resource_ids'],
            [
                [910, 'A', 2, '', str(rid)],
                [911, 'B', 2, '', str(rid)],
                [912, 'C', 2, '', str(rid)],
            ],
        )
        run_import(file_ops, 'import_tasks', str(path))

        rows = {model.get_task(i)['row'] for i in (910, 911, 912)}
        assert len(rows) == 3

    def test_missing_resource_aborts_with_no_task_created(self, tmp_path):
        model, controller, file_ops = make_file_ops()
        path = tmp_path / 'tasks.csv'
        write_csv(
            path,
            ['id', 'name', 'realistic_duration', 'predecessor_ids', 'resource_ids'],
            [[950, 'Bad', 2, '', '999999']],
        )
        errors = run_import(file_ops, 'import_tasks', str(path))

        assert errors
        assert model.get_task(950) is None

    def test_missing_predecessor_aborts_with_no_task_created(self, tmp_path):
        model, controller, file_ops, rid = self._setup_with_resource()
        path = tmp_path / 'tasks.csv'
        write_csv(
            path,
            ['id', 'name', 'realistic_duration', 'predecessor_ids', 'resource_ids'],
            [[951, 'Bad', 2, '424242', str(rid)]],
        )
        errors = run_import(file_ops, 'import_tasks', str(path))

        assert errors
        assert model.get_task(951) is None

    def test_cyclic_predecessor_aborts_with_no_task_created(self, tmp_path):
        model, controller, file_ops, rid = self._setup_with_resource()
        path = tmp_path / 'tasks.csv'
        write_csv(
            path,
            ['id', 'name', 'realistic_duration', 'predecessor_ids', 'resource_ids'],
            [[960, 'A', 2, '961', str(rid)], [961, 'B', 2, '960', str(rid)]],
        )
        errors = run_import(file_ops, 'import_tasks', str(path))

        assert errors
        assert model.get_task(960) is None
        assert model.get_task(961) is None

    def test_reimport_updates_existing_task_without_duplicating(self, tmp_path):
        model, controller, file_ops, rid = self._setup_with_resource()
        path = tmp_path / 'tasks.csv'
        write_csv(
            path,
            ['id', 'name', 'realistic_duration', 'predecessor_ids', 'resource_ids'],
            [[970, 'Original name', 3, '', str(rid)]],
        )
        run_import(file_ops, 'import_tasks', str(path))
        original_row = model.get_task(970)['row']
        original_col = model.get_task(970)['col']
        count_before = len(model.tasks)

        # Re-import the same id with a changed name/duration.
        write_csv(
            path,
            ['id', 'name', 'realistic_duration', 'predecessor_ids', 'resource_ids'],
            [[970, 'Renamed', 9, '', str(rid)]],
        )
        run_import(file_ops, 'import_tasks', str(path))

        assert len(model.tasks) == count_before
        t = model.get_task(970)
        assert t['description'] == 'Renamed'
        assert t['duration'] == 9
        assert t['row'] == original_row  # never repositioned
        assert t['col'] == original_col

    def test_existing_task_state_and_notes_untouched_by_reimport(self, tmp_path):
        model, controller, file_ops, rid = self._setup_with_resource()
        path = tmp_path / 'tasks.csv'
        write_csv(
            path,
            ['id', 'name', 'realistic_duration', 'predecessor_ids', 'resource_ids'],
            [[980, 'Task', 3, '', str(rid)]],
        )
        run_import(file_ops, 'import_tasks', str(path))

        t = model.get_task(980)
        t['state'] = 'done'
        t['notes'] = [{'timestamp': 'x', 'text': 'important note'}]

        run_import(file_ops, 'import_tasks', str(path))  # re-import, no data change

        t = model.get_task(980)
        assert t['state'] == 'done'
        assert t['notes'] == [{'timestamp': 'x', 'text': 'important note'}]

    def test_declining_confirmation_makes_no_changes(self, tmp_path):
        model, controller, file_ops, rid = self._setup_with_resource()
        path = tmp_path / 'tasks.csv'
        write_csv(
            path,
            ['id', 'name', 'realistic_duration', 'predecessor_ids', 'resource_ids'],
            [[990, 'Task', 3, '', str(rid)]],
        )
        run_import(file_ops, 'import_tasks', str(path), confirm=False)

        assert model.get_task(990) is None
