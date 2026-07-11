from tkinter import filedialog, messagebox, simpledialog
import csv
import os
import re
from datetime import datetime
from src.model.dependency_notation import VALID_LINK_TYPES
from src.model.task_resource_model import CRITICAL_CHAIN_COLOR, FEEDING_CHAIN_COLORS

# Matches a single predecessor token from a CCPM schedule.csv, e.g. 'K2',
# 'W3:FB', 'R6:SS+2' - alphanumeric ids (not our own model's plain-integer
# task ids), optionally followed by a link type and integer lag.
_CSV_PREDECESSOR_TOKEN_RE = re.compile(r'^([A-Za-z0-9_]+)(?::([A-Za-z]{2})([+-]\d+)?)?$')

# Matches a 'feeding-N' chain label from a CCPM schedule.csv.
_FEEDING_CHAIN_LABEL_RE = re.compile(r'^feeding-(\d+)$')


class FileOperations:
    def __init__(self, controller, model):
        self.controller = controller
        self.model = model

    def new_project(self):
        """Create a new project, clearing all current tasks"""
        if messagebox.askyesno(
            'New Project',
            'Are you sure you want to create a new project? All unsaved changes will be lost.',
        ):
            # Reset model data
            self.model.tasks = []
            self.model.current_file_path = None

            # Reset setdate to today
            self.model.setdate = datetime.now().replace(
                hour=0, minute=0, second=0, microsecond=0
            )

            # Update UI
            self.controller.update_window_title()
            self.controller.update_view()

            # Update notes panel if it exists
            if hasattr(self.controller.ui, 'update_notes_panel'):
                self.controller.ui.update_notes_panel()

    def open_file(self):
        """Open a task file"""
        file_path = filedialog.askopenfilename(
            defaultextension='.json',
            filetypes=[('JSON files', '*.json'), ('All files', '*.*')],
            title='Open Project',
        )

        if not file_path:
            return

        # Use model method to load data
        if self.model.load_from_file(file_path):
            # Update UI
            self.controller.update_window_title(file_path)
            self.controller.update_view()

            # Update notes panel if it exists
            if hasattr(self.controller.ui, 'update_notes_panel'):
                self.controller.ui.update_notes_panel()

            messagebox.showinfo(
                'Project Loaded', f'Project loaded from {os.path.basename(file_path)}'
            )
        else:
            messagebox.showerror(
                'Error', 'Failed to open file. The file may be corrupted or invalid.'
            )

    def save_file(self):
        """Save the current tasks to a file"""
        if self.model.current_file_path:
            if self.model.save_to_file(self.model.current_file_path):
                messagebox.showinfo(
                    'Save Successful',
                    f'Project saved to {os.path.basename(self.model.current_file_path)}',
                )
            else:
                messagebox.showerror('Error', 'Failed to save file.')
        else:
            self.save_file_as()

    def save_file_as(self):
        """Save the current tasks to a new file"""
        file_path = filedialog.asksaveasfilename(
            defaultextension='.json',
            filetypes=[('JSON files', '*.json'), ('All files', '*.*')],
            title='Save Project As',
        )

        if not file_path:
            return

        if self.model.save_to_file(file_path):
            self.controller.update_window_title(file_path)
            messagebox.showinfo(
                'Save Successful', f'Project saved to {os.path.basename(file_path)}'
            )
        else:
            messagebox.showerror('Error', 'Failed to save file.')

    def import_ccpm_schedule(self):
        """Import a CCPM schedule (a `schedule.csv` alongside a
        `resources.csv`, and optionally a `calendar.csv`) as a new project on
        the canvas - the output format produced by an external CCPM
        scheduling tool. See `sample-ccpm-projects/file-structure.md` for the
        format this expects.
        """
        schedule_path = filedialog.askopenfilename(
            defaultextension='.csv',
            filetypes=[
                ('schedule.csv', 'schedule.csv'),
                ('CSV files', '*.csv'),
                ('All files', '*.*'),
            ],
            title='Import CCPM Schedule (select schedule.csv)',
        )
        if not schedule_path:
            return

        folder = os.path.dirname(schedule_path)
        resources_path = os.path.join(folder, 'resources.csv')
        calendar_path = os.path.join(folder, 'calendar.csv')

        if not os.path.isfile(resources_path):
            messagebox.showerror(
                'Import Error',
                f'Could not find resources.csv alongside '
                f'{os.path.basename(schedule_path)} - both files are expected '
                'in the same folder.',
            )
            return

        default_name = os.path.basename(folder) or 'Imported Project'
        project_name = simpledialog.askstring(
            'Import CCPM Schedule',
            'Name for the imported project:',
            initialvalue=default_name,
            parent=self.controller.root,
        )
        if not project_name:
            return

        if self.model.get_project_by_name(project_name):
            messagebox.showerror(
                'Import Error', f"A project named '{project_name}' already exists."
            )
            return

        try:
            with open(resources_path, newline='', encoding='utf-8') as f:
                resource_rows = list(csv.DictReader(f))

            with open(schedule_path, newline='', encoding='utf-8') as f:
                schedule_rows = list(csv.DictReader(f))

            calendar_rows = []
            if os.path.isfile(calendar_path):
                with open(calendar_path, newline='', encoding='utf-8') as f:
                    calendar_rows = list(csv.DictReader(f))
        except Exception as e:
            messagebox.showerror('Import Error', f'Error reading CSV files: {e}')
            return

        try:
            project = self.model.add_project(project_name)

            # Make sure the timeline is long enough for the imported schedule
            # before creating any resources/tasks, so their capacity arrays
            # and positions are sized correctly from the start.
            max_finish = max(
                (int(row['finish']) for row in schedule_rows if row.get('finish')),
                default=0,
            )
            self._ensure_model_days(max_finish + 5)

            resource_id_map = self._import_resources(resource_rows)
            self._import_calendar_overrides(calendar_rows, resource_id_map)
            task_count = self._import_schedule_tasks(
                schedule_rows, resource_id_map, project['id']
            )
        except Exception as e:
            messagebox.showerror('Import Error', f'Error importing schedule: {e}')
            return

        self.controller.update_view()
        messagebox.showinfo(
            'Import Complete',
            f"Imported {task_count} tasks and {len(resource_rows)} resources "
            f"into new project '{project_name}'.",
        )

    def _ensure_model_days(self, min_days):
        """Extend the timeline (and every resource's capacity array to
        match) if the schedule being imported needs more days than currently
        exist. Thin wrapper around model.extend_timeline (Stage 13) so import
        and manual "Extend Timeline..." can't drift apart on how new days'
        default capacity is generated."""
        if min_days <= self.model.days:
            return

        self.model.extend_timeline(min_days - self.model.days)

    def _import_resources(self, resource_rows):
        """Import resources.csv rows, reusing an existing resource by name
        rather than duplicating it - resources are a shared team pool across
        projects in this app's rolling-wave planning model. Returns a map of
        the CSV's own string resource id to the model's integer resource id.
        """
        resource_id_map = {}
        for row in resource_rows:
            name = row['name'].strip()
            existing = self.model.get_resource_by_name(name)
            if existing:
                resource_id_map[row['id'].strip()] = existing['id']
                continue

            self.model.add_resource(name)
            created = self.model.get_resource_by_name(name)
            capacity_value = float(row.get('capacity') or 1)
            if capacity_value != 1.0:
                created['capacity'] = [capacity_value] * self.model.days
            resource_id_map[row['id'].strip()] = created['id']

        return resource_id_map

    def _import_calendar_overrides(self, calendar_rows, resource_id_map):
        """Apply calendar.csv's half-open `[from, to)` capacity overrides to
        the already-imported resources' capacity arrays."""
        for row in calendar_rows:
            resource_id = resource_id_map.get(row['resource_id'].strip())
            if resource_id is None:
                continue

            resource = self.model.get_resource_by_id(resource_id)
            from_day = int(row['from'])
            to_day = int(row['to'])
            capacity_value = float(row['capacity'])
            for day in range(from_day, min(to_day, len(resource['capacity']))):
                resource['capacity'][day] = capacity_value

    def _import_schedule_tasks(self, schedule_rows, resource_id_map, project_id):
        """Create tasks/buffers from schedule.csv rows (pass 1), then wire up
        predecessor links once every task exists so ids can be translated
        (pass 2) - schedule.csv's own ids are arbitrary alphanumeric strings
        (e.g. 'K2', 'W3'), not this model's plain-integer task ids.

        Returns the number of tasks created.
        """
        start_row = max((t['row'] for t in self.model.tasks), default=-1) + 2
        end_row = start_row + len(schedule_rows)
        if end_row > self.model.max_rows:
            self.model.max_rows = end_row + 5

        task_id_map = {}

        for i, row in enumerate(schedule_rows):
            csv_id = row['id'].strip()
            task_type = (row.get('type') or 'task').strip() or 'task'
            chain_label = (row.get('chain') or '').strip()

            resources = {}
            for token in (row.get('resource_ids') or '').split(';'):
                token = token.strip()
                if not token:
                    continue
                mapped_id = resource_id_map.get(token)
                if mapped_id is not None:
                    resources[mapped_id] = 1.0

            new_task = self.model.add_task(
                row=start_row + i,
                col=int(row['start']),
                duration=int(row['duration']),
                description=(row.get('name') or csv_id).strip(),
                resources=resources,
                url=(row.get('url') or '').strip(),
                project_id=project_id,
            )

            if task_type != 'task':
                self.model.set_task_type(new_task['task_id'], task_type)

            if chain_label:
                chain_id = self._get_or_create_chain_for_label(chain_label)
                self.model.set_task_chain(new_task['task_id'], chain_id)

            task_id_map[csv_id] = new_task['task_id']

        for row in schedule_rows:
            csv_id = row['id'].strip()
            predecessor_text = (row.get('predecessor_ids') or '').strip()
            if not predecessor_text:
                continue

            entries = []
            for token in re.split(r'[;\s]+', predecessor_text):
                if not token:
                    continue

                match = _CSV_PREDECESSOR_TOKEN_RE.match(token)
                if not match:
                    messagebox.showwarning(
                        'Import Warning',
                        f"Task '{csv_id}': couldn't parse predecessor token "
                        f"'{token}' - skipped.",
                    )
                    continue

                pred_id_str, link_type, lag_str = match.groups()
                mapped_id = task_id_map.get(pred_id_str)
                if mapped_id is None:
                    messagebox.showwarning(
                        'Import Warning',
                        f"Task '{csv_id}': unknown predecessor id "
                        f"'{pred_id_str}' - skipped.",
                    )
                    continue

                link_type = (link_type or 'FS').upper()
                if link_type not in VALID_LINK_TYPES:
                    link_type = 'FS'

                entries.append(
                    {
                        'id': mapped_id,
                        'type': link_type,
                        'lag': int(lag_str) if lag_str else 0,
                    }
                )

            if entries:
                self.model.set_predecessors(task_id_map[csv_id], entries)

        return len(schedule_rows)

    def _get_or_create_chain_for_label(self, label):
        """Map a schedule.csv chain label ('critical', 'feeding-1', ...) to a
        chain_id, creating a new chain if one doesn't already exist for it."""
        label_lower = label.strip().lower()

        if label_lower == 'critical':
            chain = self.model.get_critical_chain()
            if chain:
                return chain['id']
            return self.model.add_chain(
                'Critical', CRITICAL_CHAIN_COLOR, is_critical=True
            )['id']

        match = _FEEDING_CHAIN_LABEL_RE.match(label_lower)
        if match:
            name = f'Feeding-{int(match.group(1)):02d}'
            chain = self.model.get_chain_by_name(name)
            if chain:
                return chain['id']
            used_colors = {c['color'] for c in self.model.chains}
            color = next(
                (c for c in FEEDING_CHAIN_COLORS if c not in used_colors), '#888888'
            )
            return self.model.add_chain(name, color)['id']

        # Unrecognized label - use/create a chain with this literal name
        # rather than silently dropping the classification.
        chain = self.model.get_chain_by_name(label)
        if chain:
            return chain['id']
        return self.model.add_chain(label, '#888888')['id']
