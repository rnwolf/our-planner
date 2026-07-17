"""CCPM round trip with the external ccpm-scheduler engine (Stage 16).

Two flows over one export mapping:

- **Export CCPM Network...** writes a chosen project's tasks/resources/
  calendar as the CSV input files the external `ccpm-scheduler` CLI consumes
  (see `docs/file-structure.md`), for the manual round trip:
  export, schedule outside, bring the result back with the already-built
  `File → Import CCPM Schedule...`.

- **Schedule with CCPM...** does the whole trip in-process using the
  `ccpm_scheduler` library: build the network, validate (structured issues
  with machine codes shown to the user on failure), build the schedule, and
  import it as a NEW project next to the original — manual and automated
  plans compare side by side, per the Stage 16 strategy in planning.md.

Export mapping decisions (Stage 16's open questions, resolved):
- scope: the whole selected project; tasks whose state is 'done' are
  excluded (the scheduler plans remaining work), and links to excluded or
  cross-project tasks are dropped with a warning.
- existing project_buffer/feeding_buffer tasks are never exported — the
  scheduler computes its own buffers from the realistic/optimal gap.
- optimal_duration is exported only when the user captured one; otherwise
  the scheduler applies its classic 50% cut to realistic_duration.
- day axis: the schedule is ANCHORED at the first day of the project's
  earliest task. The scheduler itself always plans from its own day 0 (the
  ALAP pass packs the project against 0), so calendar windows are exported
  shifted to anchor-relative days — the scheduler sees future availability
  exactly as it falls relative to the project — and the in-process flow
  shifts the imported schedule back to the timeline (+anchor). The CSV
  export uses the same anchor-relative days; its day 0 = the anchor day.
- fractional resource allocations cannot be represented (the engine
  schedules whole resources in v1): the in-process flow surfaces the
  engine's E_FRACTIONAL_ALLOCATION error; the CSV export warns and exports
  the assignment as a whole resource.
"""

import csv
import os
import tkinter as tk
from collections import Counter
from tkinter import filedialog, messagebox

from src.model.task_resource_model import BUFFER_TASK_TYPES
from src.operations.file_operations import FileOperations


class CcpmOperations:
    def __init__(self, controller, model):
        self.controller = controller
        self.model = model
        # own instance: only the private _import_* helpers are used, which
        # touch the model, not the UI
        self._file_ops = FileOperations(controller, model)

    # ------------------------------------------------------------ mapping

    def build_network_data(self, project_id):
        """Map one project onto the ccpm-scheduler JSON exchange format.

        Returns (data, warnings, anchor): `data` is the dict `ccpm_scheduler.
        network_from_json` accepts; `warnings` are human-readable notes about
        anything the mapping had to drop or approximate; `anchor` is the
        timeline day the export is anchored on (the earliest exported task's
        start) — calendar windows in `data` are anchor-relative, and a
        schedule built from `data` must be shifted by +anchor to land back
        on the timeline.
        """
        warnings = []
        exported = {}  # task_id -> task
        for task in self.model.tasks:
            if task.get('project_id') != project_id:
                continue
            if task.get('type') in BUFFER_TASK_TYPES:
                warnings.append(
                    f"buffer task '{task['description']}' not exported - the "
                    f"scheduler computes its own buffers"
                )
                continue
            if self.model.get_task_state(task) == 'complete':
                warnings.append(
                    f"task '{task['description']}' is complete - excluded "
                    f"(the scheduler plans remaining work)"
                )
                continue
            exported[task['task_id']] = task

        tasks_out = []
        resource_ids = set()
        for task in exported.values():
            links = []
            for entry in task.get('predecessors') or []:
                if entry['id'] in exported:
                    links.append({'id': str(entry['id']),
                                  'type': entry['type'], 'lag': entry['lag']})
                else:
                    warnings.append(
                        f"task '{task['description']}': predecessor link to "
                        f"task id {entry['id']} dropped (done, buffer, or "
                        f"outside this project)"
                    )
            allocations = {str(rid): float(alloc)
                           for rid, alloc in (task.get('resources') or {}).items()}
            resource_ids.update(task.get('resources') or {})
            realistic = task.get('realistic_duration')
            if realistic in (None, ''):
                realistic = task.get('duration')
            optimal = task.get('optimal_duration')
            tasks_out.append({
                'id': str(task['task_id']),
                'name': task['description'],
                'realistic_duration': realistic,
                'optimal_duration': optimal if optimal not in (None, '') else None,
                'predecessors': links,
                'resources': allocations,
                'url': task.get('url', '') or '',
                # Stage 19: carried for the CSV export / round trip; the
                # scheduler's network_from_json reads known keys only, so
                # these are ignored on the in-process JSON path
                'tags': list(task.get('tags') or []),
                'colour': task.get('color', '') or '',
            })

        anchor = min((t['col'] for t in exported.values()), default=0)

        resources_out, calendar_out = [], []
        for rid in sorted(resource_ids):
            resource = self.model.get_resource_by_id(rid)
            if resource is None:
                continue
            base, windows = self._encode_capacity(resource['capacity'])
            resources_out.append({'id': str(rid), 'name': resource['name'],
                                  'capacity': base})
            for start, end, value in windows:
                # shift to anchor-relative days; windows entirely before the
                # anchor are in the past for this project and don't apply
                if end - anchor <= 0:
                    continue
                calendar_out.append({'resource_id': str(rid),
                                     'from': max(start - anchor, 0),
                                     'to': end - anchor, 'capacity': value})

        data = {'tasks': tasks_out, 'resources': resources_out}
        if calendar_out:
            data['calendar'] = calendar_out
        # Stage 20: the project's buffer-sizing method rides along in the
        # JSON exchange; ccpm-scheduler >= 0.9 reads it in network_from_json
        project = self.model.get_project_by_id(project_id)
        if project:
            data['buffer_method'] = project.get('ccpm_method', 'cap')
        return data, warnings, anchor

    @staticmethod
    def _encode_capacity(vector):
        """Collapse a per-day capacity array into (base_capacity, windows):
        base is the most common value, windows are the half-open [from, to)
        runs that differ from it. Whole-number floats become ints."""
        def norm(v):
            return int(v) if isinstance(v, float) and v.is_integer() else v

        values = [norm(v) for v in vector] or [1]
        base = Counter(values).most_common(1)[0][0]
        windows = []
        run_start = None
        for day, value in enumerate(values):
            if value != base and run_start is None:
                run_start = day
            elif run_start is not None and (value == base
                                            or value != values[run_start]):
                windows.append((run_start, day, values[run_start]))
                run_start = day if value != base else None
        if run_start is not None:
            windows.append((run_start, len(values), values[run_start]))
        return base, windows

    # ------------------------------------------------------------ core flows

    def schedule_project_core(self, project_id, new_project_name=None):
        """Validate + schedule one project and import the result as a new
        project. Returns a dict:
          ok False -> {'ok', 'issues': [{'code','message',...}], 'warnings'}
          ok True  -> {'ok', 'project', 'stats', 'task_count', 'warnings'}
        No UI - the dialogs live in schedule_with_ccpm()."""
        from ccpm_scheduler import (CcpmError, build_schedule, check_schedule,
                                    network_from_json, validate_network)

        data, warnings, anchor = self.build_network_data(project_id)
        if not data['tasks']:
            return {'ok': False, 'warnings': warnings, 'issues': [{
                'code': 'E_EMPTY_PROJECT',
                'message': 'no schedulable tasks in this project '
                           '(buffers and done tasks are excluded)'}]}

        network = network_from_json(data)
        report = validate_network(network)
        warnings.extend(w.message for w in report.warnings)
        if not report.ok:
            return {'ok': False, 'warnings': warnings,
                    'issues': [i.to_json() for i in report.errors]}

        source = self.model.get_project_by_id(project_id)
        title = new_project_name or f"{source['name']} (CCPM)"
        try:
            result = build_schedule(network, title)
        except CcpmError as e:
            return {'ok': False, 'warnings': warnings, 'issues': [
                {'code': 'E_UNSCHEDULABLE', 'message': str(e)}]}
        verify = check_schedule(result.schedule, network)
        if not verify.ok:  # engine bug guard - should never happen
            return {'ok': False, 'warnings': warnings,
                    'issues': [i.to_json() for i in verify.errors]}

        name = title
        n = 2
        while self.model.get_project_by_name(name):
            name = f'{title} ({n})'
            n += 1
        project = self.model.add_project(name)
        # the CCPM copy keeps the source project's buffer-sizing method, so
        # rescheduling the copy reproduces the same buffer arithmetic
        project['ccpm_method'] = source.get('ccpm_method', 'cap')

        max_finish = max(r.finish for r in result.schedule.rows)
        self._file_ops._ensure_model_days(anchor + max_finish + 5)
        resource_rows = [{'id': r['id'], 'name': r['name'],
                          'capacity': r['capacity']}
                         for r in data['resources']]
        resource_id_map = self._file_ops._import_resources(resource_rows)
        # no calendar pass: every exported resource already exists by name,
        # so _import_resources reuses it with its capacity array intact
        schedule_rows = [r.to_csv_dict() for r in result.schedule.rows]
        task_count = self._file_ops._import_schedule_tasks(
            schedule_rows, resource_id_map, project['id'])

        new_tasks = [t for t in self.model.tasks
                     if t['project_id'] == project['id']]
        self._place_beside_source(new_tasks, project_id)
        source_by_id = {t['task_id']: t for t in self.model.tasks
                        if t['project_id'] == project_id}
        for row_dict, task in zip(schedule_rows, new_tasks):
            # back onto the timeline: the schedule was built anchor-relative
            task['col'] += anchor
            # the schedule's task ids ARE the source task ids - carry the
            # descriptive metadata across so the CCPM copy can replace the
            # hand-drawn network without losing color/tags/notes
            source = None
            if row_dict['id'].isdigit():
                source = source_by_id.get(int(row_dict['id']))
            tags = ['ccpm']
            if source is not None:
                task['color'] = source['color']
                task['notes'] = [dict(n) for n in source.get('notes') or []]
                tags += [t for t in source.get('tags') or [] if t != 'ccpm']
            # 'ccpm' on every created row (buffers too) so the whole
            # generated network is selectable via the tag filter
            self.model.set_task_tags(task['task_id'], tags)

        return {'ok': True, 'project': project, 'task_count': task_count,
                'anchor': anchor, 'stats': result.stats, 'warnings': warnings}

    def _place_beside_source(self, new_tasks, source_project_id):
        """Move the freshly imported rows to start two rows below the source
        project (so the two networks compare at a glance) - but only when no
        other task occupies that space; otherwise leave them where the
        importer put them (below everything)."""
        if not new_tasks:
            return
        new_ids = {t['task_id'] for t in new_tasks}
        source_rows = [t['row'] for t in self.model.tasks
                       if t['project_id'] == source_project_id
                       and t['task_id'] not in new_ids]
        if not source_rows:
            return
        desired = max(source_rows) + 2
        current = min(t['row'] for t in new_tasks)
        if desired >= current:
            return
        occupied = any(t['row'] >= desired for t in self.model.tasks
                       if t['task_id'] not in new_ids
                       and t['project_id'] != source_project_id)
        if occupied:
            return
        shift = current - desired
        for t in new_tasks:
            t['row'] -= shift

    def export_network_core(self, project_id, folder):
        """Write tasks.csv / resources.csv / calendar.csv for one project in
        the external scheduler's input format. Returns (files, warnings,
        anchor) — the CSVs' day 0 is timeline day `anchor`."""
        data, warnings, anchor = self.build_network_data(project_id)
        for task in data['tasks']:
            for rid, alloc in task['resources'].items():
                if alloc != 1:
                    warnings.append(
                        f"task '{task['name']}': allocation {alloc} of "
                        f"resource {rid} exported as a whole resource (CSV "
                        f"cannot express allocations; the scheduler uses "
                        f"whole resources)"
                    )

        os.makedirs(folder, exist_ok=True)
        files = []

        path = os.path.join(folder, 'tasks.csv')
        with open(path, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(['id', 'name', 'realistic_duration', 'optimal_duration',
                        'predecessor_ids', 'resource_ids', 'url', 'tags',
                        'colour'])
            for t in data['tasks']:
                w.writerow([
                    t['id'], t['name'], t['realistic_duration'],
                    t['optimal_duration'] if t['optimal_duration'] is not None else '',
                    ';'.join(self._link_token(e) for e in t['predecessors']),
                    ';'.join(t['resources']),
                    t['url'],
                    ','.join(t['tags']),
                    t['colour'],
                ])
        files.append(path)

        path = os.path.join(folder, 'resources.csv')
        with open(path, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(['id', 'name', 'capacity'])
            for r in data['resources']:
                w.writerow([r['id'], r['name'], r['capacity']])
        files.append(path)

        if data.get('calendar'):
            path = os.path.join(folder, 'calendar.csv')
            with open(path, 'w', newline='', encoding='utf-8') as f:
                w = csv.writer(f)
                w.writerow(['resource_id', 'from', 'to', 'capacity'])
                for c in data['calendar']:
                    w.writerow([c['resource_id'], c['from'], c['to'],
                                c['capacity']])
            files.append(path)

        # Notes go to a file, not the completion dialog: with many warnings
        # a messagebox can outgrow a laptop screen and hide its OK button.
        if warnings:
            path = os.path.join(folder, 'notes.txt')
            with open(path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(f'- {w}' for w in warnings) + '\n')
            files.append(path)

        return files, warnings, anchor

    @staticmethod
    def _link_token(entry):
        token = entry['id']
        if entry['type'] != 'FS' or entry['lag']:
            token += f":{entry['type']}"
            if entry['lag']:
                token += f"{entry['lag']:+d}"
        return token

    # ------------------------------------------------------------ UI flows

    def export_ccpm_network(self):
        """File → Export CCPM Network... : pick a project and a folder, write
        the scheduler's input CSVs there."""
        project = self._pick_project('Export CCPM Network')
        if not project:
            return
        folder = filedialog.askdirectory(
            title=f"Folder for '{project['name']}' CCPM input files",
            parent=self.controller.root)
        if not folder:
            return
        try:
            files, warnings, anchor = self.export_network_core(
                project['id'], folder)
        except Exception as e:
            messagebox.showerror('Export Error', f'Export failed: {e}')
            return
        note = ''
        if warnings:
            note = (f'\n\n{len(warnings)} note(s) about the export written '
                    f'to notes.txt.')
        has_calendar = any(os.path.basename(p) == 'calendar.csv'
                           for p in files)
        method = project.get('ccpm_method', 'cap')
        messagebox.showinfo(
            'Export Complete',
            f"Wrote {', '.join(os.path.basename(p) for p in files)} to "
            f'{folder}.\n\nDay 0 in these files = timeline day {anchor} '
            f"(the project's earliest task).\n\nSchedule it with:\n"
            f'  ccpm-scheduler build tasks.csv resources.csv'
            + (' --calendar calendar.csv' if has_calendar else '')
            + f' --buffer-method {method}'
            + ' --out-dir plan\n\nthen bring the result back via '
            "'File → Import CCPM Schedule...'." + note)

    def schedule_with_ccpm(self):
        """File → Schedule with CCPM... : validate + schedule the picked
        project in-process and import the result as a new project."""
        project = self._pick_project('Schedule with CCPM')
        if not project:
            return
        try:
            result = self.schedule_project_core(project['id'])
        except Exception as e:
            messagebox.showerror('CCPM Error', f'Scheduling failed: {e}')
            return

        if not result['ok']:
            lines = [f"- {i['message']}" for i in result['issues']]
            messagebox.showerror(
                'CCPM Validation Failed',
                f"'{project['name']}' cannot be scheduled yet:\n\n"
                + '\n'.join(lines)
                + '\n\nFix the network and try again.')
            return

        self.controller.update_view()
        stats = result['stats']
        note = ''
        if result['warnings']:
            # Cap the notes so the messagebox can't outgrow the screen and
            # hide its OK button (the export flow writes notes.txt instead,
            # but this in-process flow has no output folder).
            shown = result['warnings'][:10]
            note = '\n\nNotes:\n' + '\n'.join(f'- {w}' for w in shown)
            remaining = len(result['warnings']) - len(shown)
            if remaining:
                note += f'\n... and {remaining} more'
        messagebox.showinfo(
            'CCPM Schedule Created',
            f"Created project '{result['project']['name']}' with "
            f"{result['task_count']} rows (tagged 'ccpm'), anchored at "
            f"timeline day {result['anchor']}.\n\n"
            f"Critical chain: {' → '.join(stats.critical_chain)} "
            f'({stats.critical_chain_length} days)\n'
            f'Project buffer: {stats.project_buffer} days\n'
            f"Promised completion: timeline day "
            f"{result['anchor'] + stats.promise_day}" + note)

    def _pick_project(self, title):
        """Choose a project: the only one silently, else a list dialog."""
        projects = self.model.projects
        if not projects:
            messagebox.showerror(title, 'No projects in this plan.')
            return None
        if len(projects) == 1:
            return projects[0]

        dialog = tk.Toplevel(self.controller.root)
        dialog.title(title)
        dialog.transient(self.controller.root)
        dialog.grab_set()
        tk.Label(dialog, text='Project:').pack(padx=10, pady=(10, 2),
                                               anchor='w')
        listbox = tk.Listbox(dialog, height=min(len(projects), 12), width=40)
        for p in projects:
            listbox.insert(tk.END, p['name'])
        listbox.pack(padx=10, fill='both', expand=True)
        default = self.model.get_default_project()
        listbox.selection_set(
            next((i for i, p in enumerate(projects)
                  if default and p['id'] == default['id']), 0))

        chosen = []

        def ok(_event=None):
            sel = listbox.curselection()
            if sel:
                chosen.append(projects[sel[0]])
            dialog.destroy()

        listbox.bind('<Double-Button-1>', ok)
        buttons = tk.Frame(dialog)
        buttons.pack(pady=8)
        tk.Button(buttons, text='OK', width=8, command=ok).pack(
            side='left', padx=4)
        tk.Button(buttons, text='Cancel', width=8,
                  command=dialog.destroy).pack(side='left', padx=4)
        dialog.wait_window()
        return chosen[0] if chosen else None
