from tkinter import filedialog, messagebox, simpledialog
import csv
import os
import re
from typing import Dict, List, Optional, TypedDict, cast
from src.model.dependency_notation import VALID_LINK_TYPES, parse_predecessor_notation
from src.model.entities import PredecessorLink
from src.model.resource_notation import parse_resource_token
from src.model.resource_notation import (
    parse_resource_tokens as _parse_resource_tokens_str_keyed,
)
from src.model.task_resource_model import CRITICAL_CHAIN_COLOR, FEEDING_CHAIN_COLORS
from src.utils.app_settings import add_recent_file, remove_recent_file

# Matches a single predecessor token from a CCPM schedule.csv, e.g. 'K2',
# 'W3:FB', 'R6:SS+2' - alphanumeric ids (not our own model's plain-integer
# task ids), optionally followed by a link type and integer lag.
_CSV_PREDECESSOR_TOKEN_RE = re.compile(
    r'^([A-Za-z0-9_]+)(?::([A-Za-z]{2})([+-]\d+)?)?$'
)

# Matches a 'feeding-N' chain label from a CCPM schedule.csv.
_FEEDING_CHAIN_LABEL_RE = re.compile(r'^feeding-(\d+)$')


def _read_csv_rows(path):
    """csv.DictReader rows with whitespace-stripped header names - a header
    like 'resource_ids ' (trailing space, e.g. from a spreadsheet export)
    would otherwise silently make every `row.get('resource_ids')` return
    None instead of the real column, since dict lookup is exact-match. Used
    by the Import Network actions (import_resources/
    import_resource_calendars/import_tasks) - not import_ccpm_schedule's
    reader above, which is a separate, older code path."""
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        return [{(k.strip() if k else k): v for k, v in row.items()} for row in reader]


def _parse_resource_tokens(value) -> Dict[int, float]:
    """Parse a semicolon-separated resource_ids cell (Import Tasks...) into
    {resource_id: allocation}, with resource_id converted to our own
    internal int id (Import Network matches by id directly - see
    file_operations.py's "Import Network Data" section - so no
    resource_id_map indirection is needed here, unlike
    _import_schedule_tasks's ccpm-scheduler round trip below). A bare id
    defaults to allocation 1.0; 'id:allocation' is this app's own
    extension of ccpm-scheduler's own 'id:qty' notation
    (src/model/resource_notation.py has the shared parse/render logic).
    Raises ValueError on a malformed token."""
    return {
        int(rid): alloc
        for rid, alloc in _parse_resource_tokens_str_keyed(value).items()
    }


class ParsedTaskRow(TypedDict):
    """One validated tasks.csv row, staged by import_tasks before it's
    applied to the model (as a new task via add_task, or patched onto an
    existing one)."""

    name: str
    duration: int
    optimal_duration: Optional[int]
    resources: Dict[int, float]
    predecessors: List[PredecessorLink]
    url: str
    tags: List[str]
    colour: str


class FileOperations:
    def __init__(self, controller, model):
        self.controller = controller
        self.model = model

    def new_project(self):
        """Create a new project, clearing all current tasks, resources,
        and tags back to the same blank-slate state a freshly started app
        begins with (see TaskResourceModel.reset), then trims the default
        resource pool down to just the first one - the other 9
        (Resource B..J) are startup sample data for a first-time user to
        explore, not something a genuine new project needs pre-seeded."""
        if messagebox.askyesno(
            'New Project',
            'Are you sure you want to create a new project? All unsaved changes will be lost.',
        ):
            self.model.reset()
            self.model.trim_to_first_resource()
            # A new blank project is never a versioned workspace, even if
            # the one just left behind was.
            self.controller.version_control_ops.detect_workspace(None)

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

        self._load_file(file_path)

    def open_recent_file(self, file_path):
        """File > Recent > <n> <filename>: reopen a file from the recently
        opened/saved list. A file that's been moved or deleted since it was
        listed is dropped from the list rather than left to fail the same
        way again next time."""
        if not os.path.isfile(file_path):
            messagebox.showerror(
                'File Not Found',
                f'{file_path}\n\nThis file no longer exists and has been '
                'removed from the Recent list.',
            )
            remove_recent_file(file_path)
            return

        self._load_file(file_path)

    def _load_file(self, file_path):
        """Shared by open_file (via the file picker) and open_recent_file
        (via File > Recent) - load `file_path` into the model, refresh the
        UI, and record it as the most recently used file."""
        if self.model.load_from_file(file_path):
            # Re-activates versioning if file_path is a versioned
            # workspace's tracked file, deactivates it otherwise.
            self.controller.version_control_ops.detect_workspace(file_path)

            # Update UI
            self.controller.update_window_title(file_path)
            self.controller.update_view()

            # Update notes panel if it exists
            if hasattr(self.controller.ui, 'update_notes_panel'):
                self.controller.ui.update_notes_panel()

            add_recent_file(file_path)

            messagebox.showinfo(
                'Project Loaded', f'Project loaded from {os.path.basename(file_path)}'
            )
        else:
            messagebox.showerror(
                'Error', 'Failed to open file. The file may be corrupted or invalid.'
            )

    def save_file(self):
        """Save the current tasks to a file"""
        # Safety net for any edit path the two autosave chokepoints (see
        # maybe_autosave_checkpoint's docstring) don't reach - captures a
        # pending edit no later than the next explicit Save. A no-op
        # unless the project is a versioned workspace.
        self.controller.version_control_ops.maybe_autosave_checkpoint()
        if self.model.current_file_path:
            if self.model.save_to_file(self.model.current_file_path):
                add_recent_file(self.model.current_file_path)
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
            # Save As always targets a specific path - re-derive versioning
            # from it, same rule as opening a file (only its own directory's
            # marker matters, never wherever the project was versioned before).
            self.controller.version_control_ops.detect_workspace(file_path)
            self.controller.update_window_title(file_path)
            add_recent_file(file_path)
            messagebox.showinfo(
                'Save Successful', f'Project saved to {os.path.basename(file_path)}'
            )
        else:
            messagebox.showerror('Error', 'Failed to save file.')

    def import_ccpm_schedule(self):
        """Import a CCPM schedule (a `schedule.csv` alongside a
        `resources.csv`, and optionally a `calendar.csv`) as a new project on
        the canvas - the output format produced by an external CCPM
        scheduling tool. See `docs/file-structure.md` for the
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
            f'Imported {task_count} tasks and {len(resource_rows)} resources '
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

            self.model.add_resource(
                name,
                url=(row.get('url') or '').strip(),
                emails=(row.get('emails') or '').strip(),
            )
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

            # ccpm-scheduler >= 0.11 (Phase 5) encodes a per-task quantity as
            # 'id:qty' in resource_ids (a bare id means 1.0) - parse it per
            # token rather than looking the whole token up in
            # resource_id_map, which only holds bare ids and would silently
            # drop e.g. '5:3' as an unresolvable key.
            resources = {}
            for token in (row.get('resource_ids') or '').split(';'):
                token = token.strip()
                if not token:
                    continue
                try:
                    rid, alloc = parse_resource_token(token)
                except ValueError:
                    continue
                mapped_id = resource_id_map.get(rid)
                if mapped_id is not None:
                    resources[mapped_id] = alloc

            new_task = self.model.add_task(
                row=start_row + i,
                col=int(row['start']),
                duration=int(row['duration']),
                description=(row.get('name') or csv_id).strip(),
                resources=resources,
                url=(row.get('url') or '').strip(),
                project_id=project_id,
            )

            # schedule.csv carries the task's realistic estimate since
            # ccpm-scheduler 0.7 - without it, add_task's default (a copy of
            # `duration`, i.e. the optimal value) would misrecord the
            # original estimate on imported CCPM tasks
            raw_realistic = row.get('realistic_duration')
            if isinstance(raw_realistic, str):
                raw_realistic = raw_realistic.strip()
            if raw_realistic not in (None, ''):
                new_task['realistic_duration'] = int(raw_realistic)

            if task_type != 'task':
                self.model.set_task_type(new_task['task_id'], task_type)

            if chain_label:
                chain_id = self._get_or_create_chain_for_label(chain_label)
                self.model.set_task_chain(new_task['task_id'], chain_id)

            # Stage 19: optional tags / colour columns (we write 'colour';
            # 'color' accepted as an alias on read).
            raw_tags = (row.get('tags') or '').strip()
            tags = [
                t.strip()
                for t in re.split(r'[;,]', raw_tags)
                if t.strip() and t.strip() != 'ccpm'
            ]
            self.model.set_task_tags(new_task['task_id'], tags)

            colour = (row.get('colour') or row.get('color') or '').strip()
            if colour:
                new_task['color'] = colour

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

    # -------------------------------------------------- Import Network Data
    #
    # Three separate, deliberately sequential actions (File > Import Network)
    # for round-tripping a *reference* network - one that may not be
    # CCPM-scheduled yet, so import_ccpm_schedule() above (which requires an
    # already-scheduled schedule.csv) doesn't fit. Unlike that importer,
    # which treats CSV ids as foreign/arbitrary strings and always creates
    # new tasks/resources via an id-remap table, these match an incoming row
    # to an existing task/resource BY ID directly - the assumption is that
    # the file's ids already correspond to this model's real ids (e.g. from
    # a previous CSV export, or a deliberately hand-numbered reference
    # file). A matched row only updates the fields the CSV format actually
    # carries; everything else (task state/notes/history, resource
    # capacity/tags) is left exactly as it is.

    def import_resources(self):
        """File > Import Network > Import Resources...: create or update
        resources from a resources.csv, matched by id. A brand-new id gets
        the imported capacity (default 1.0) as its starting per-day array.
        An id that already exists has name/url/emails updated (only for
        non-empty cells), and its capacity RESET to a flat per-day array of
        the CSV's value if the `capacity` cell is non-empty - a blank cell
        leaves whatever capacity configuration (including any per-day
        pattern) the resource already has untouched. tags/works_weekends are
        never touched by import either way."""
        path = filedialog.askopenfilename(
            defaultextension='.csv',
            filetypes=[
                ('resources.csv', 'resources.csv'),
                ('CSV files', '*.csv'),
                ('All files', '*.*'),
            ],
            title='Import Resources (select resources.csv)',
            parent=self.controller.root,
        )
        if not path:
            return

        try:
            rows = _read_csv_rows(path)
        except Exception as e:
            messagebox.showerror(
                'Import Error',
                f'Error reading resources.csv: {e}',
                parent=self.controller.root,
            )
            return

        # Validate everything up front - no partial imports on a bad row.
        problems = []
        parsed = []
        for row in rows:
            raw_id = (row.get('id') or '').strip()
            try:
                resource_id = int(raw_id)
            except ValueError:
                problems.append(
                    f"row with id '{raw_id or '(blank)'}': not a whole number"
                )
                continue

            # csv.DictReader dumps any fields past the last header into a
            # None-keyed overflow list rather than erroring - the signature
            # of an unquoted comma inside a cell (most likely `emails`,
            # which invites multiple comma-separated addresses) shifting
            # every later column on the row. Silently importing that would
            # misassign data instead of failing loudly, so reject it here.
            if row.get(None):
                problems.append(
                    f'resource {resource_id}: row has more columns than the '
                    f"header - check for an unquoted comma (e.g. in 'emails';"
                    f" use ';' to separate multiple addresses, or quote the "
                    f'cell)'
                )
                continue

            raw_capacity = (row.get('capacity') or '').strip()
            if raw_capacity:
                try:
                    float(raw_capacity)
                except ValueError:
                    problems.append(
                        f"resource {resource_id}: capacity '{raw_capacity}' is not a number"
                    )
                    continue

            parsed.append((resource_id, row))

        if problems:
            messagebox.showerror(
                'Import Error',
                'resources.csv has problem row(s) - fix these and try again '
                '(no changes made):\n\n'
                + '\n'.join(problems[:10])
                + (f'\n...and {len(problems) - 10} more' if len(problems) > 10 else ''),
                parent=self.controller.root,
            )
            return

        new_ids = [rid for rid, _ in parsed if not self.model.get_resource_by_id(rid)]
        existing_ids = [rid for rid, _ in parsed if self.model.get_resource_by_id(rid)]
        existing_with_capacity = [
            rid
            for rid, row in parsed
            if self.model.get_resource_by_id(rid)
            and (row.get('capacity') or '').strip()
        ]

        message = (
            f'{len(new_ids)} new resource(s) will be created.\n'
            f'{len(existing_ids)} existing resource(s) will have '
            f'name/url/emails updated where the CSV provides a value.\n'
            f'{len(existing_with_capacity)} of those will also have their '
            f'capacity RESET to the CSV value (replacing any existing '
            f'per-day pattern) - existing resources with a blank capacity '
            f'cell keep their current capacity unchanged. tags/weekend '
            f'settings are never changed by import.\n\nProceed?'
        )
        if not messagebox.askyesno(
            'Import Resources', message, parent=self.controller.root
        ):
            return

        created = 0
        updated = 0
        for resource_id, row in parsed:
            name = (row.get('name') or '').strip()
            url = (row.get('url') or '').strip()
            emails = (row.get('emails') or '').strip()
            raw_capacity = (row.get('capacity') or '').strip()
            existing = self.model.get_resource_by_id(resource_id)
            if existing:
                if name:
                    existing['name'] = name
                if url:
                    existing['url'] = url
                if emails:
                    existing['emails'] = emails
                if raw_capacity:
                    existing['capacity'] = [float(raw_capacity)] * self.model.days
                updated += 1
            else:
                capacity_value = float(raw_capacity) if raw_capacity else 1.0
                new_resource = self.model.add_resource(
                    name or f'Resource {resource_id}',
                    resource_id=resource_id,
                    url=url,
                    emails=emails,
                )
                if capacity_value != 1.0:
                    new_resource['capacity'] = [capacity_value] * self.model.days
                created += 1

        self.controller.update_view()
        messagebox.showinfo(
            'Import Complete',
            f'Created {created} new resource(s), updated {updated} existing '
            f'resource(s).',
            parent=self.controller.root,
        )

    def import_resource_calendars(self):
        """File > Import Network > Import Resource Calendars...: apply
        per-day capacity overrides from a calendar.csv (half-open
        `[from, to)` ranges, same shape import_ccpm_schedule's own
        calendar.csv uses) to resources that already exist. Resources must
        be imported first - aborts with no changes if any referenced
        resource_id doesn't exist yet, naming which ones."""
        path = filedialog.askopenfilename(
            defaultextension='.csv',
            filetypes=[
                ('calendar.csv', 'calendar.csv'),
                ('CSV files', '*.csv'),
                ('All files', '*.*'),
            ],
            title='Import Resource Calendars (select calendar.csv)',
            parent=self.controller.root,
        )
        if not path:
            return

        try:
            rows = _read_csv_rows(path)
        except Exception as e:
            messagebox.showerror(
                'Import Error',
                f'Error reading calendar.csv: {e}',
                parent=self.controller.root,
            )
            return

        problems = []
        parsed = []
        for row in rows:
            raw_id = (row.get('resource_id') or '').strip()
            try:
                resource_id = int(raw_id)
            except ValueError:
                problems.append(
                    f"row with resource_id '{raw_id or '(blank)'}': not a whole number"
                )
                continue

            if not self.model.get_resource_by_id(resource_id):
                problems.append(
                    f'resource_id {resource_id}: no such resource - import '
                    f'resources first'
                )
                continue

            try:
                from_day = int(row['from'])
                to_day = int(row['to'])
                capacity_value = float(row['capacity'])
            except (KeyError, ValueError):
                problems.append(
                    f"resource_id {resource_id}: 'from'/'to'/'capacity' must be numbers"
                )
                continue

            parsed.append((resource_id, from_day, to_day, capacity_value))

        if problems:
            messagebox.showerror(
                'Import Error',
                'calendar.csv has problem row(s) - fix these and try again '
                '(no changes made):\n\n'
                + '\n'.join(problems[:10])
                + (f'\n...and {len(problems) - 10} more' if len(problems) > 10 else ''),
                parent=self.controller.root,
            )
            return

        resource_count = len({rid for rid, *_ in parsed})
        message = (
            f'{len(parsed)} capacity override range(s) across '
            f'{resource_count} resource(s) will be applied.\n\nProceed?'
        )
        if not messagebox.askyesno(
            'Import Resource Calendars', message, parent=self.controller.root
        ):
            return

        for resource_id, from_day, to_day, capacity_value in parsed:
            resource = self.model.get_resource_by_id(resource_id)
            for day in range(from_day, min(to_day, len(resource['capacity']))):
                resource['capacity'][day] = capacity_value

        self.controller.update_view()
        messagebox.showinfo(
            'Import Complete',
            f'Applied {len(parsed)} capacity override range(s) across '
            f'{resource_count} resource(s).',
            parent=self.controller.root,
        )

    def import_tasks(self):
        """File > Import Network > Import Tasks...: create or update tasks
        from a tasks.csv, matched by id. A brand-new id is placed via a
        plain ASAP layout computed from predecessor links (no resource
        leveling, no CCPM buffers - this is a reference network, not a
        scheduled one); an id that already exists only has its
        description/duration/resources/predecessors updated in place, at
        its current row/col - state, notes, actual dates, baseline, and
        buffer/fever history are left untouched, since this minimal format
        doesn't carry them.

        Every referenced resource must already exist (Import Resources...
        first) and every predecessor must resolve to either another row in
        this file or an existing task - the whole import aborts with no
        changes if anything doesn't resolve, so a bad row can't leave a
        half-imported network.
        """
        path = filedialog.askopenfilename(
            defaultextension='.csv',
            filetypes=[
                ('tasks.csv', 'tasks.csv'),
                ('CSV files', '*.csv'),
                ('All files', '*.*'),
            ],
            title='Import Tasks (select tasks.csv)',
            parent=self.controller.root,
        )
        if not path:
            return

        try:
            rows = _read_csv_rows(path)
        except Exception as e:
            messagebox.showerror(
                'Import Error',
                f'Error reading tasks.csv: {e}',
                parent=self.controller.root,
            )
            return

        problems = []
        parsed: Dict[int, ParsedTaskRow] = {}
        order = []

        for row in rows:
            raw_id = (row.get('id') or '').strip()
            try:
                task_id = int(raw_id)
            except ValueError:
                problems.append(
                    f"row with id '{raw_id or '(blank)'}': not a whole number"
                )
                continue

            name = (row.get('name') or '').strip() or f'Task {task_id}'

            raw_duration = (row.get('realistic_duration') or '').strip()
            try:
                duration = int(raw_duration)
            except ValueError:
                problems.append(
                    f"task {task_id} ('{name}'): realistic_duration "
                    f"'{raw_duration}' is not a whole number"
                )
                continue

            raw_optimal = (row.get('optimal_duration') or '').strip()
            optimal_duration = None
            if raw_optimal:
                try:
                    optimal_duration = int(raw_optimal)
                except ValueError:
                    problems.append(
                        f"task {task_id} ('{name}'): optimal_duration "
                        f"'{raw_optimal}' is not a whole number"
                    )
                    continue

            try:
                resources = _parse_resource_tokens(row.get('resource_ids'))
            except ValueError:
                problems.append(
                    f"task {task_id} ('{name}'): couldn't parse resource_ids "
                    f"'{row.get('resource_ids')}'"
                )
                continue

            missing_resources = [
                rid for rid in resources if not self.model.get_resource_by_id(rid)
            ]
            if missing_resources:
                problems.append(
                    f"task {task_id} ('{name}'): references resource id(s) "
                    + ', '.join(str(r) for r in missing_resources)
                    + ' which do not exist - import resources first'
                )
                continue

            try:
                predecessors = cast(
                    List[PredecessorLink],
                    parse_predecessor_notation(row.get('predecessor_ids') or ''),
                )
            except ValueError as e:
                problems.append(f"task {task_id} ('{name}'): {e}")
                continue

            parsed[task_id] = {
                'name': name,
                'duration': duration,
                'optimal_duration': optimal_duration,
                'resources': resources,
                'predecessors': predecessors,
                'url': (row.get('url') or '').strip(),
                'tags': [
                    t.strip()
                    for t in re.split(r'[;,]', row.get('tags') or '')
                    if t.strip()
                ],
                'colour': (row.get('colour') or row.get('color') or '').strip(),
            }
            order.append(task_id)

        if problems:
            messagebox.showerror(
                'Import Error',
                'tasks.csv has problem row(s) - fix these and try again '
                '(no changes made):\n\n'
                + '\n'.join(problems[:10])
                + (f'\n...and {len(problems) - 10} more' if len(problems) > 10 else ''),
                parent=self.controller.root,
            )
            return

        # Predecessors must resolve to either another row in this file or
        # an existing task.
        unresolved = []
        for task_id, info in parsed.items():
            for entry in info['predecessors']:
                pred_id = entry['id']
                if pred_id not in parsed and not self.model.get_task(pred_id):
                    unresolved.append(
                        f"task {task_id} ('{info['name']}'): predecessor "
                        f'{pred_id} does not exist'
                    )
        if unresolved:
            messagebox.showerror(
                'Import Error',
                "tasks.csv references predecessor(s) that don't exist - fix "
                'these and try again (no changes made):\n\n'
                + '\n'.join(unresolved[:10])
                + (
                    f'\n...and {len(unresolved) - 10} more'
                    if len(unresolved) > 10
                    else ''
                ),
                parent=self.controller.root,
            )
            return

        new_ids = {tid for tid in parsed if not self.model.get_task(tid)}
        existing_ids = set(parsed) - new_ids

        # ASAP layout for new tasks only - existing (matched) tasks are
        # never repositioned, only their data fields update below.
        anchor_day = self.model.get_day_for_date(self.model.setdate)
        computed_col = {}
        visiting = set()

        def duration_of(tid):
            if tid in parsed:
                return parsed[tid]['duration']
            return self.model.get_task(tid)['duration']

        def start_of(tid):
            if tid not in new_ids:
                return self.model.get_task(tid)['col']
            if tid in computed_col:
                return computed_col[tid]
            if tid in visiting:
                raise ValueError(f'task {tid}: cyclic predecessor reference')
            visiting.add(tid)

            preds = parsed[tid]['predecessors']
            if not preds:
                start = anchor_day
            else:
                start = 0
                for entry in preds:
                    pred_id = entry['id']
                    pred_start = start_of(pred_id)
                    pred_duration = duration_of(pred_id)
                    link_type = entry['type']
                    lag = entry['lag']
                    this_duration = parsed[tid]['duration']
                    if link_type == 'SS':
                        candidate = pred_start + lag
                    elif link_type == 'FF':
                        candidate = pred_start + pred_duration - this_duration + lag
                    elif link_type == 'SF':
                        candidate = pred_start - this_duration + lag
                    else:  # FS (default), and PB/FB (not used pre-schedule)
                        candidate = pred_start + pred_duration + lag
                    start = max(start, candidate)

            visiting.discard(tid)
            computed_col[tid] = start
            return start

        try:
            for task_id in new_ids:
                start_of(task_id)
        except ValueError as e:
            messagebox.showerror(
                'Import Error',
                f'{e} - fix the network and try again (no changes made).',
                parent=self.controller.root,
            )
            return

        # Row assignment for new tasks: sequential fresh rows, file order -
        # same shape _import_schedule_tasks uses for its schedule.csv import.
        start_row = max((t['row'] for t in self.model.tasks), default=-1) + 2
        new_rows = {}
        i = 0
        for task_id in order:
            if task_id in new_ids:
                new_rows[task_id] = start_row + i
                i += 1
        end_row = start_row + i

        new_count = len(new_ids)
        updated_count = len(existing_ids)
        link_count = sum(len(info['predecessors']) for info in parsed.values())

        message_parts = [
            f'{new_count} new task(s) will be created.',
            f'{updated_count} existing task(s) will have name/duration/'
            f'resources/predecessors updated (state, notes, actual dates, '
            f'and history are never changed by import).',
            f'{link_count} predecessor link(s) will be set.',
        ]
        if new_count:
            start_date = self.model.get_date_for_day(
                min(computed_col[t] for t in new_ids)
            ).strftime('%Y-%m-%d')
            message_parts.append(
                f'New tasks will occupy rows {start_row}-{end_row - 1}, '
                f'starting around {start_date}.'
            )
        message_parts.append('Proceed?')

        if not messagebox.askyesno(
            'Import Tasks', '\n'.join(message_parts), parent=self.controller.root
        ):
            return

        if new_ids:
            max_finish = max(computed_col[t] + parsed[t]['duration'] for t in new_ids)
            self._ensure_model_days(max_finish + 5)
            if end_row > self.model.max_rows:
                self.model.max_rows = end_row + 5

        # Pass 1: create/update every task
        for task_id in order:
            info = parsed[task_id]
            if task_id in new_ids:
                task = self.model.add_task(
                    task_id=task_id,
                    row=new_rows[task_id],
                    col=computed_col[task_id],
                    duration=info['duration'],
                    description=info['name'],
                    resources=info['resources'],
                    url=info['url'],
                    project_id=self.model.default_project_id,
                )
                if info['optimal_duration'] is not None:
                    task['optimal_duration'] = info['optimal_duration']
                if info['tags']:
                    self.model.set_task_tags(task_id, info['tags'])
                if info['colour']:
                    task['color'] = info['colour']
            else:
                task = self.model.get_task(task_id)
                task['description'] = info['name']
                task['duration'] = info['duration']
                task['realistic_duration'] = info['duration']
                if info['optimal_duration'] is not None:
                    task['optimal_duration'] = info['optimal_duration']
                task['resources'] = info['resources']
                if info['url']:
                    task['url'] = info['url']
                if info['colour']:
                    task['color'] = info['colour']

        # Pass 2: wire predecessor links now that every id resolves
        for task_id, info in parsed.items():
            self.model.set_predecessors(task_id, info['predecessors'])

        self.controller.update_view()
        messagebox.showinfo(
            'Import Complete',
            f'Created {new_count} new task(s), updated {updated_count} '
            f'existing task(s), set {link_count} predecessor link(s).',
            parent=self.controller.root,
        )
