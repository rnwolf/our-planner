import json
from typing import List, Dict, Any, Optional, Tuple, Set
from datetime import datetime, timedelta

from src.model.dependency_notation import (
    DEFAULT_LINK_TYPE,
    VALID_LINK_TYPES,
    normalize_predecessor_entries,
)

TASK_TYPES = ['task', 'project_buffer', 'feeding_buffer']
BUFFER_TASK_TYPES = {'project_buffer', 'feeding_buffer'}

PROJECT_PHASES = ['planning', 'execution']

# Buffer-sizing methods offered by the external ccpm-scheduler (>= 0.9);
# stored per project and passed through both CCPM round-trip flows. See
# the scheduler's docs/buffer-sizing.md for formulas and trade-offs.
CCPM_METHODS = ['cap', 'hchain', 'rsem']
DEFAULT_CCPM_METHOD = 'cap'

CRITICAL_CHAIN_COLOR = '#E53935'  # red
# Default colors for the seeded Feeding-01..04 chains - mutually distinguishable
# at a glance; all freely editable afterward via Manage Chains, and more chains
# can be added there if a plan needs more than 4 feeding chains.
FEEDING_CHAIN_COLORS = [
    '#1E88E5',  # blue
    '#D81B60',  # magenta
    '#8E24AA',  # purple
    '#F4511E',  # deep orange
]

# Fever chart (Stage 8) zone boundary defaults, approximated from a reference
# CCPM fever chart - see planning.md. Per-project, editable via update_project.
DEFAULT_FEVER_CHART_SLOPE = 0.55
DEFAULT_FEVER_CHART_YELLOW_INTERCEPT = 10.0
DEFAULT_FEVER_CHART_RED_INTERCEPT = 27.0


def classify_fever_chart_zone(
    progress_pct: float,
    consumption_pct: float,
    slope: float,
    yellow_intercept: float,
    red_intercept: float,
) -> str:
    """Classify a fever chart point into 'green' | 'yellow' | 'red', using the
    sloped zone boundaries `y = slope*x + intercept` (Stage 8). Both inputs
    and the boundaries are in percent (0-100).
    """
    yellow_boundary = slope * progress_pct + yellow_intercept
    red_boundary = slope * progress_pct + red_intercept

    if consumption_pct >= red_boundary:
        return 'red'
    if consumption_pct >= yellow_boundary:
        return 'yellow'
    return 'green'


def fever_chart_display_point(
    entry: Dict[str, Any], buffer_baseline_duration: float
) -> Tuple[float, float]:
    """Turn one `fever_chart_history` entry (cpsl/ppf/forecast_lateness, as
    logged by `capture_fever_chart_snapshot`) into (progress_pct,
    consumption_pct) - the two values every fever chart renderer plots.

    Pulled into one place because this exact math used to be hand-copied
    identically into three call sites (the on-screen chart, the PNG export,
    and the CSV export) with no shared test coverage.
    """
    cpsl = entry['cpsl']
    progress_pct = (entry['ppf'] / cpsl * 100) if cpsl > 0 else 0.0
    consumption_pct = (
        (entry['forecast_lateness'] / buffer_baseline_duration * 100)
        if buffer_baseline_duration > 0
        else 0.0
    )
    return progress_pct, consumption_pct


class TaskResourceModel:
    def __init__(self):
        # Configuration
        self.days = 100
        self.max_rows = 50
        self.start_date = datetime.now().replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        # Set date for tracking task status
        self.setdate = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        # Resource management with IDs
        self.resource_id_counter = 0
        self.resources = [
            {
                'id': self._get_next_resource_id(),
                'name': 'Resource A',
                'capacity': [1.0] * 100,
                'tags': [],  # Add tags list to resources
            },
            {
                'id': self._get_next_resource_id(),
                'name': 'Resource B',
                'capacity': [1.0] * 100,
                'tags': [],
            },
            {
                'id': self._get_next_resource_id(),
                'name': 'Resource C',
                'capacity': [1.0] * 100,
                'tags': [],
            },
            {
                'id': self._get_next_resource_id(),
                'name': 'Resource D',
                'capacity': [1.0] * 100,
                'tags': [],
            },
            {
                'id': self._get_next_resource_id(),
                'name': 'Resource E',
                'capacity': [1.0] * 100,
                'tags': [],
            },
            {
                'id': self._get_next_resource_id(),
                'name': 'Resource F',
                'capacity': [1.0] * 100,
                'tags': [],
            },
            {
                'id': self._get_next_resource_id(),
                'name': 'Resource G',
                'capacity': [1.0] * 100,
                'tags': [],
            },
            {
                'id': self._get_next_resource_id(),
                'name': 'Resource H',
                'capacity': [1.0] * 100,
                'tags': [],
            },
            {
                'id': self._get_next_resource_id(),
                'name': 'Resource I',
                'capacity': [1.0] * 100,
                'tags': [],
            },
            {
                'id': self._get_next_resource_id(),
                'name': 'Resource J',
                'capacity': [1.0] * 100,
                'tags': [],
            },
        ]

        # Data structures
        self.tasks = []
        self.task_id_counter = 0

        # File path
        self.current_file_path = None

        # All tags in the system for easy reference and autocomplete
        self.all_tags = set()

        # Project management, for rolling-wave planning across multiple
        # projects sharing the same resource pool on one canvas
        self.project_id_counter = 0
        self.projects: List[Dict[str, Any]] = []
        self.default_project_id: Optional[int] = None
        # Seed a default project so a fresh plan (and its sample tasks) isn't unassigned
        self.add_project('Sample Project')

        # Chain classification (critical chain / feeding chains), global across
        # the whole plan - a task's chain_id references one of these
        self.chain_id_counter = 0
        self.chains: List[Dict[str, Any]] = []
        # Seed the critical chain plus 10 feeding chains with distinguishable
        # default colors - hand-picking that many good colors is hard, so the
        # tool supplies a reasonable starting palette, fully editable afterward
        self.add_chain('Critical', CRITICAL_CHAIN_COLOR, is_critical=True)
        for i, color in enumerate(FEEDING_CHAIN_COLORS, start=1):
            self.add_chain(f'Feeding-{i:02d}', color)

    def _get_next_resource_id(self) -> int:
        """Generate a unique resource ID."""
        self.resource_id_counter += 1
        return self.resource_id_counter

    def _get_next_project_id(self) -> int:
        """Generate a unique project ID."""
        self.project_id_counter += 1
        return self.project_id_counter

    def get_project_by_id(self, project_id: int) -> Optional[Dict[str, Any]]:
        """Find a project by its ID."""
        for project in self.projects:
            if project['id'] == project_id:
                return project
        return None

    def get_project_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Find a project by its name."""
        for project in self.projects:
            if project['name'] == name:
                return project
        return None

    def add_project(self, name: str, url: str = '') -> Optional[Dict[str, Any]]:
        """Add a new project. The first project added becomes the default."""
        if self.get_project_by_name(name):
            return None

        project = {
            'id': self._get_next_project_id(),
            'name': name,
            'url': url,
            'phase': 'planning',  # 'planning' or 'execution'
            'ccpm_method': DEFAULT_CCPM_METHOD,  # buffer sizing (Stage 20)
            # Fever chart (Stage 8) zone boundary settings: two sloped lines
            # y = slope*x + yellow_intercept (green/yellow boundary) and
            # y = slope*x + red_intercept (yellow/red boundary), x/y in percent.
            # Defaults approximated from a reference CCPM fever chart.
            'fever_chart_slope': DEFAULT_FEVER_CHART_SLOPE,
            'fever_chart_yellow_intercept': DEFAULT_FEVER_CHART_YELLOW_INTERCEPT,
            'fever_chart_red_intercept': DEFAULT_FEVER_CHART_RED_INTERCEPT,
        }
        self.projects.append(project)

        if self.default_project_id is None:
            self.default_project_id = project['id']

        return project

    def update_project(
        self,
        project_id: int,
        name: str = None,
        url: str = None,
        ccpm_method: str = None,
        fever_chart_slope: float = None,
        fever_chart_yellow_intercept: float = None,
        fever_chart_red_intercept: float = None,
    ) -> bool:
        """Update a project's name, url, CCPM buffer-sizing method, and/or
        fever chart zone settings."""
        project = self.get_project_by_id(project_id)
        if not project:
            return False

        if name is not None:
            if name != project['name'] and self.get_project_by_name(name):
                return False  # Another project already has this name
            project['name'] = name

        if url is not None:
            project['url'] = url

        if ccpm_method is not None:
            if ccpm_method not in CCPM_METHODS:
                return False
            project['ccpm_method'] = ccpm_method

        if fever_chart_slope is not None:
            project['fever_chart_slope'] = fever_chart_slope

        if fever_chart_yellow_intercept is not None:
            project['fever_chart_yellow_intercept'] = fever_chart_yellow_intercept

        if fever_chart_red_intercept is not None:
            project['fever_chart_red_intercept'] = fever_chart_red_intercept

        return True

    def remove_project(self, project_id: int) -> bool:
        """Remove a project. Tasks that referenced it become unassigned."""
        project = self.get_project_by_id(project_id)
        if not project:
            return False

        self.projects.remove(project)

        for task in self.tasks:
            if task.get('project_id') == project_id:
                task['project_id'] = None

        if self.default_project_id == project_id:
            self.default_project_id = self.projects[0]['id'] if self.projects else None

        return True

    def set_default_project(self, project_id: Optional[int]) -> bool:
        """Set which project new tasks are automatically assigned to."""
        if project_id is not None and not self.get_project_by_id(project_id):
            return False
        self.default_project_id = project_id
        return True

    def get_default_project(self) -> Optional[Dict[str, Any]]:
        """Return the current default project, if any."""
        if self.default_project_id is None:
            return None
        return self.get_project_by_id(self.default_project_id)

    def _get_next_chain_id(self) -> int:
        """Generate a unique chain ID."""
        self.chain_id_counter += 1
        return self.chain_id_counter

    def get_chain_by_id(self, chain_id: int) -> Optional[Dict[str, Any]]:
        """Find a chain by its ID."""
        for chain in self.chains:
            if chain['id'] == chain_id:
                return chain
        return None

    def get_chain_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Find a chain by its name."""
        for chain in self.chains:
            if chain['name'] == name:
                return chain
        return None

    def add_chain(
        self, name: str, color: str, is_critical: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Add a new chain (the critical chain, or a feeding chain).

        Only one chain may be critical at a time - adding a new critical chain
        unmarks any existing one.
        """
        if self.get_chain_by_name(name):
            return None

        if is_critical:
            for chain in self.chains:
                chain['is_critical'] = False

        chain = {
            'id': self._get_next_chain_id(),
            'name': name,
            'color': color,
            'is_critical': is_critical,
        }
        self.chains.append(chain)
        return chain

    def update_chain(
        self, chain_id: int, name: str = None, color: str = None
    ) -> bool:
        """Update a chain's name and/or color."""
        chain = self.get_chain_by_id(chain_id)
        if not chain:
            return False

        if name is not None:
            if name != chain['name'] and self.get_chain_by_name(name):
                return False  # Another chain already has this name
            chain['name'] = name

        if color is not None:
            chain['color'] = color

        return True

    def remove_chain(self, chain_id: int) -> bool:
        """Remove a chain. Tasks that referenced it become unassigned."""
        chain = self.get_chain_by_id(chain_id)
        if not chain:
            return False

        self.chains.remove(chain)

        for task in self.tasks:
            if task.get('chain_id') == chain_id:
                task['chain_id'] = None

        return True

    def set_critical_chain(self, chain_id: int) -> bool:
        """Mark a chain as THE critical chain, unmarking any other chain."""
        chain = self.get_chain_by_id(chain_id)
        if not chain:
            return False

        for c in self.chains:
            c['is_critical'] = c['id'] == chain_id

        return True

    def get_critical_chain(self) -> Optional[Dict[str, Any]]:
        """Return the chain currently flagged as critical, if any."""
        for chain in self.chains:
            if chain.get('is_critical'):
                return chain
        return None

    def set_task_chain(self, task_id: int, chain_id: Optional[int]) -> bool:
        """Assign a task (or buffer) to a chain, or None to unassign."""
        task = self.get_task(task_id)
        if not task:
            return False

        if chain_id is not None and not self.get_chain_by_id(chain_id):
            return False

        task['chain_id'] = chain_id
        return True

    def set_project_phase(self, project_id: int, phase: str) -> bool:
        """Set a project's phase ('planning' or 'execution').

        Does not itself capture a buffer baseline - see capture_project_baseline.
        """
        if phase not in PROJECT_PHASES:
            return False

        project = self.get_project_by_id(project_id)
        if not project:
            return False

        project['phase'] = phase
        return True

    def project_has_baseline(self, project_id: int) -> bool:
        """Return True if any task in the project already has a baseline."""
        return any(
            task.get('baseline') is not None
            for task in self.tasks
            if task.get('project_id') == project_id
        )

    def capture_project_baseline(self, project_id: int) -> int:
        """Snapshot every task's col/duration in a project as its baseline.

        Captures the whole signed-off plan (not just buffer sizes), so it can
        later be compared against how execution actually unfolded.

        Overwrites any existing baseline - callers should confirm with the user
        first if project_has_baseline() is already True.

        Returns the number of tasks captured, or -1 if the project doesn't
        exist. A return of 0 means the project has no tasks assigned to it yet.
        """
        if not self.get_project_by_id(project_id):
            return -1

        captured_at = self.setdate.isoformat()
        count = 0
        for task in self.tasks:
            if task.get('project_id') == project_id:
                task['baseline'] = {
                    'col': task['col'],
                    'duration': task['duration'],
                    'realistic_duration': task.get(
                        'realistic_duration', task['duration']
                    ),
                    'captured_at': captured_at,
                }
                count += 1

        return count

    def shift_task_position(self, task: Dict[str, Any], delta_days: int) -> None:
        """Shift a task's `col` by `delta_days`, and its `baseline['col']` by
        the exact same amount if a baseline has been captured (Stage 1/4).

        Both must move together - every buffer's forecast-lateness math
        (`compute_fever_chart_point`) compares a task's *current* `col`
        against its own `baseline['col']`. Shifting only the live `col` (the
        bug this method fixes - `update_project_start_date` used to do
        exactly that) silently corrupts every subsequent Progress %/
        Consumption % calculation for that buffer by the shifted amount, for
        the rest of the project's life. Used by both
        `update_project_start_date` and Stage 13's "Delete History..."
        compaction, so the two code paths can never drift apart on this
        again.
        """
        task['col'] -= delta_days
        baseline = task.get('baseline')
        if baseline:
            baseline['col'] -= delta_days

    def compute_delete_history_impact(self, cutoff_col: int) -> Dict[str, Any]:
        """Compute what a "Delete History" cutoff would affect, without
        mutating anything - the impact preview for its bulk confirmation
        dialog (Stage 13). Tasks with `col < cutoff_col` fall in the chopped
        region, matching `update_project_start_date`'s existing left-edge
        semantics.

        Returns:
            'to_delete': every task that would be deleted
            'not_done': the subset of to_delete whose state isn't 'done' -
                warn, but overridable (losing track of an incomplete task)
            'blocking': a list of {'buffer', 'task', 'role'} for any buffer
                whose terminal or merge task would be deleted, regardless of
                that task's own done state - never overridable, since it
                would permanently disable that buffer's fever chart
                (`compute_fever_chart_point` has no terminal/merge task left
                to anchor to) for the rest of the project's life.
        """
        to_delete = [t for t in self.tasks if t['col'] < cutoff_col]
        to_delete_ids = {t['task_id'] for t in to_delete}
        not_done = [t for t in to_delete if t.get('state') != 'done']

        blocking = []
        for buffer_task in self.tasks:
            if buffer_task.get('type') not in BUFFER_TASK_TYPES:
                continue
            for role, getter in (
                ('terminal', self.get_buffer_terminal_task),
                ('merge', self.get_buffer_merge_task),
            ):
                role_task = getter(buffer_task['task_id'])
                if role_task and role_task['task_id'] in to_delete_ids:
                    blocking.append(
                        {'buffer': buffer_task, 'task': role_task, 'role': role}
                    )

        return {'to_delete': to_delete, 'not_done': not_done, 'blocking': blocking}

    def delete_history(self, cutoff_col: int) -> bool:
        """Delete every task before `cutoff_col`, shift everything else (and
        every resource's capacity array) left by `cutoff_col`, and shrink
        `self.days` by `cutoff_col` (Stage 13's "Delete History...").

        Unlike `update_project_start_date` (which re-anchors `start_date`
        within a *constant-size* window), this actually reclaims space -
        the whole point is to stop `self.days` growing indefinitely as
        completed history piles up.

        Returns False (no-op, nothing changed) if `cutoff_col <= 0` or any
        buffer's terminal/merge task would be deleted - callers should check
        `compute_delete_history_impact()` first to show the user why, but
        this is re-checked here as a safety net against calling it directly.
        """
        if cutoff_col <= 0:
            return False

        impact = self.compute_delete_history_impact(cutoff_col)
        if impact['blocking']:
            return False

        for task in impact['to_delete']:
            self.delete_task(task['task_id'])

        for task in self.tasks:
            self.shift_task_position(task, cutoff_col)

        for resource in self.resources:
            resource['capacity'] = resource['capacity'][cutoff_col:]

        self.start_date = self.start_date + timedelta(days=cutoff_col)
        self.days -= cutoff_col

        return True

    def compute_safe_delete_cutoff(self) -> int:
        """The largest cutoff_col for which compute_delete_history_impact()
        would report zero not-done tasks and zero blocking buffers - exactly
        the region the grid's "safe to delete" background shading (Stage 13)
        highlights. 0 if nothing is safe to delete (or there's nothing to
        protect against in the first place, e.g. an empty model).

        A task only constrains the cutoff if it's either not yet done, or
        is some buffer's terminal/merge task (see compute_delete_history_
        impact's 'blocking') - an ordinary done task imposes no constraint
        of its own.
        """
        protected_cols = [t['col'] for t in self.tasks if t.get('state') != 'done']

        for buffer_task in self.tasks:
            if buffer_task.get('type') not in BUFFER_TASK_TYPES:
                continue
            for getter in (self.get_buffer_terminal_task, self.get_buffer_merge_task):
                role_task = getter(buffer_task['task_id'])
                if role_task:
                    protected_cols.append(role_task['col'])

        return min(protected_cols) if protected_cols else 0

    def extend_timeline(self, additional_days: int) -> bool:
        """Add `additional_days` to the right end of the timeline
        (`self.days`), extending every resource's `capacity` array to match -
        Stage 13's "growing the right side" half, needed so rolling-wave
        planning can keep scheduling further into the future once older
        history has been deleted (or just because the plan is running long).

        New days get the same weekend-aware default capacity a brand new
        resource gets from `add_resource` (1.0, or 0.0 on Sat/Sun for a
        resource with `works_weekends=False`) - not a blind 1.0 fill for
        every resource regardless of schedule, which would make a weekend-off
        resource look available on newly-added Saturdays.

        Returns False (no-op) if `additional_days <= 0`.
        """
        if additional_days <= 0:
            return False

        old_days = self.days
        self.days += additional_days

        for resource in self.resources:
            works_weekends = resource.get('works_weekends', True)
            new_capacity = []
            for day in range(old_days, self.days):
                if not works_weekends and self.get_date_for_day(day).weekday() >= 5:
                    new_capacity.append(0.0)
                else:
                    new_capacity.append(1.0)
            resource['capacity'] = resource['capacity'] + new_capacity

        return True

    def get_next_task_id(self) -> int:
        """Generate a unique task ID."""
        self.task_id_counter += 1
        return self.task_id_counter

    def get_date_for_day(self, day: int) -> datetime:
        """Get the calendar date for a specific day in the timeline."""
        return self.start_date + timedelta(days=day)

    def get_day_for_date(self, date: datetime) -> int:
        """Get the day index in the timeline for a specific calendar date."""
        delta = date - self.start_date
        return delta.days

    def get_month_ranges(self) -> List[Dict[str, Any]]:
        """Get a list of month ranges for the timeline."""
        month_ranges = []
        current_month = None
        start_col = 0
        month_format = '%Y-%m (%b)'

        for day in range(self.days):
            date = self.get_date_for_day(day)
            month_key = date.strftime('%Y-%m')  # Year-Month as key

            if month_key != current_month:
                # If there was a previous month, add it to the ranges
                if current_month is not None:
                    month_ranges.append(
                        {
                            'label': self.get_date_for_day(start_col).strftime(
                                month_format
                            ),
                            'start': start_col,
                            'end': day - 1,
                        }
                    )

                # Start a new month
                current_month = month_key
                start_col = day

        # Add the last month
        if current_month is not None:
            month_ranges.append(
                {
                    'label': self.get_date_for_day(start_col).strftime(month_format),
                    'start': start_col,
                    'end': self.days - 1,
                }
            )

        return month_ranges

    def add_task(
        self,
        row: int,
        col: int,
        duration: int,
        description: str,
        resources: Dict[int, float] = None,  # Changed to Dict[resource_id, allocation]
        url: str = '',
        predecessors: List[Any] = None,  # List of {id, type, lag} link entries
        tags: List[str] = None,  # Add tags parameter
        color: str = None,  # Add color parameter with None default
        project_id: int = None,  # Defaults to the current default project
        chain_id: int = None,  # Which chain (critical/feeding-NN) this task belongs to
    ) -> Dict[str, Any]:
        """Add a new task to the model."""
        tags = tags or []  # Default to empty list if None
        color = color or 'Cyan'  # Default color if None
        if project_id is None:
            project_id = self.default_project_id

        # Update all_tags with any new tags
        for tag in tags:
            self.all_tags.add(tag)

        task = {
            'task_id': self.get_next_task_id(),
            'row': row,
            'col': col,
            'duration': duration,
            'description': description,
            'url': url,
            'resources': resources or {},  # Changed to Dict[resource_id, allocation]
            # 'successors' is not stored - it is derived (see get_successor_ids)
            'predecessors': normalize_predecessor_entries(predecessors),
            'tags': tags,  # Add tags to task dictionary
            'color': color,  # Add color to task dictionary
            'notes': [],  # Initialize empty notes list
            'project_id': project_id,  # Which project this task belongs to
            'chain_id': chain_id,  # Which chain (critical/feeding-NN), if any
            # New CCPM-related properties
            'type': 'task',  # 'task', 'project_buffer', or 'feeding_buffer'
            'state': 'planning',  # Initial state: 'planning', 'buffered', or 'done'
            # Realistic = Optimal + Contingency. `duration` (above) is the
            # task's current, active, schedulable duration - it starts as a
            # copy of the Realistic estimate (what's naturally captured
            # first, before any buffer-cutting), but may later be reduced to
            # the Optimal estimate once a (not yet built) buffer-cutting
            # step pools the stripped contingency into that chain's buffer -
            # so `realistic_duration` is a permanent record of the original
            # estimate, since `duration` itself can't be trusted to still
            # hold it after that happens.
            'realistic_duration': duration,  # Initially set to the provided duration
            'optimal_duration': None,  # "If everything went perfectly" estimate (if set)
            'actual_start_date': None,  # When work actually started
            'actual_end_date': None,  # When work was completed
            'fullkit_date': None,  # When all prerequisites were ready
            'remaining_duration_history': [],  # Track history of remaining duration estimates
            'baseline': None,  # {'col', 'duration', 'realistic_duration', 'captured_at'} snapshot,
            # set for every task in a project when it moves from planning to execution
            'buffer_size_history': [],  # For buffer tasks: {'date', 'duration', 'reason',
            # 'trigger_task_id'} log of every execution-phase size change (Stage 7)
            'fever_chart_history': [],  # For buffer tasks: {'date', 'cpsl', 'ppf',
            # 'forecast_lateness'} log captured on every status update (Stage 8)
        }
        self.tasks.append(task)
        return task

    def add_tags_to_task(self, task_id: int, tags: List[str]) -> bool:
        """Add tags to a task."""
        task = self.get_task(task_id)
        if not task:
            return False

        # Make sure task has a tags list
        if 'tags' not in task:
            task['tags'] = []

        # Add new tags that aren't already present
        for tag in tags:
            if tag not in task['tags']:
                task['tags'].append(tag)
                self.all_tags.add(tag)

        return True

    def remove_tags_from_task(self, task_id: int, tags: List[str]) -> bool:
        """Remove tags from a task."""
        task = self.get_task(task_id)
        if not task or 'tags' not in task:
            return False

        # Remove specified tags
        task['tags'] = [tag for tag in task['tags'] if tag not in tags]
        return True

    def set_task_tags(self, task_id: int, tags: List[str]) -> bool:
        """Replace all tags for a task."""
        task = self.get_task(task_id)
        if not task:
            return False

        # Update all_tags
        for tag in tags:
            self.all_tags.add(tag)

        # Set the tags
        task['tags'] = tags
        return True

    def add_tags_to_resource(self, resource_id: int, tags: List[str]) -> bool:
        """Add tags to a resource."""
        resource = self.get_resource_by_id(resource_id)
        if not resource:
            return False

        # Make sure resource has a tags list
        if 'tags' not in resource:
            resource['tags'] = []

        # Add new tags that aren't already present
        for tag in tags:
            if tag not in resource['tags']:
                resource['tags'].append(tag)
                self.all_tags.add(tag)

        return True

    def remove_tags_from_resource(self, resource_id: int, tags: List[str]) -> bool:
        """Remove tags from a resource."""
        resource = self.get_resource_by_id(resource_id)
        if not resource or 'tags' not in resource:
            return False

        # Remove specified tags
        resource['tags'] = [tag for tag in resource['tags'] if tag not in tags]
        return True

    def set_resource_tags(self, resource_id: int, tags: List[str]) -> bool:
        """Replace all tags for a resource."""
        resource = self.get_resource_by_id(resource_id)
        if not resource:
            return False

        # Update all_tags
        for tag in tags:
            self.all_tags.add(tag)

        # Set the tags
        resource['tags'] = tags
        return True

    def get_tasks_by_tags(
        self, tags: List[str], match_all: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get tasks that match the specified tags.

        Args:
            tags: List of tags to match
            match_all: If True, task must have all specified tags. If False, task must have at least one.

        Returns:
            List of matching tasks
        """
        if not tags:
            return self.tasks.copy()

        matching_tasks = []
        for task in self.tasks:
            # Skip tasks without tags
            if 'tags' not in task or not task['tags']:
                continue

            # Check for tag matches
            if match_all:
                # Task must have all specified tags
                if all(tag in task['tags'] for tag in tags):
                    matching_tasks.append(task)
            else:
                # Task must have at least one of the specified tags
                if any(tag in task['tags'] for tag in tags):
                    matching_tasks.append(task)

        return matching_tasks

    def get_resources_by_tags(
        self, tags: List[str], match_all: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get resources that match the specified tags.

        Args:
            tags: List of tags to match
            match_all: If True, resource must have all specified tags. If False, resource must have at least one.

        Returns:
            List of matching resources
        """
        if not tags:
            return self.resources.copy()

        matching_resources = []
        for resource in self.resources:
            # Skip resources without tags
            if 'tags' not in resource or not resource['tags']:
                continue

            # Check for tag matches
            if match_all:
                # Resource must have all specified tags
                if all(tag in resource['tags'] for tag in tags):
                    matching_resources.append(resource)
            else:
                # Resource must have at least one of the specified tags
                if any(tag in resource['tags'] for tag in tags):
                    matching_resources.append(resource)

        return matching_resources

    def get_task_state(self, task: Dict[str, Any]) -> str:
        """Derive a task's execution state from its actual date fields (Stage
        10 Part A) - no separate stored field, so it can never drift out of
        sync with actual_start_date/actual_end_date."""
        if task.get('actual_end_date'):
            return 'complete'
        if task.get('actual_start_date'):
            return 'in_progress'
        return 'not_started'

    def get_tasks_by_state(self, states: List[str]) -> List[Dict[str, Any]]:
        """Get tasks whose derived state (see get_task_state) is one of
        `states` - OR logic among the selected states, matching the Project
        filter's checkbox pattern."""
        if not states:
            return self.tasks.copy()
        return [t for t in self.tasks if self.get_task_state(t) in states]

    def get_tasks_by_fullkit(self, value: str) -> List[Dict[str, Any]]:
        """Get tasks matching a full-kit readiness value: 'ready' (fullkit_date
        set) or 'not_ready' (fullkit_date not set)."""
        if value == 'ready':
            return [t for t in self.tasks if t.get('fullkit_date')]
        if value == 'not_ready':
            return [t for t in self.tasks if not t.get('fullkit_date')]
        return self.tasks.copy()

    def get_task_start_window(self, task: Dict[str, Any]) -> str:
        """Bucket a task's planned start date (its `col`, converted to a
        calendar date) relative to the current setdate ("today" in the app's
        own simulated timeline, not wall-clock time - consistent with the rest
        of the app's status-date-driven design). Buckets are mutually
        exclusive so they behave like the other OR-checkbox filters:

        - 'overdue': planned start already passed
        - 'week1': within the next 7 days
        - 'week2': 7-14 days out
        - 'month1': 14-30 days out
        - 'month2': 30-60 days out
        - 'later': 60+ days out
        """
        planned_start = self.get_date_for_day(task['col'])
        delta_days = (planned_start - self.setdate).days

        if delta_days < 0:
            return 'overdue'
        if delta_days < 7:
            return 'week1'
        if delta_days < 14:
            return 'week2'
        if delta_days < 30:
            return 'month1'
        if delta_days < 60:
            return 'month2'
        return 'later'

    def get_tasks_by_start_window(self, windows: List[str]) -> List[Dict[str, Any]]:
        """Get tasks whose derived planned-start window (see
        get_task_start_window) is one of `windows` - OR logic among the
        selected windows."""
        if not windows:
            return self.tasks.copy()
        return [t for t in self.tasks if self.get_task_start_window(t) in windows]

    def get_all_tags(self) -> List[str]:
        """Get all tags used in the project."""
        return sorted(list(self.all_tags))

    def refresh_all_tags(self) -> None:
        """Rebuild the all_tags set by scanning all tasks and resources."""
        self.all_tags = set()

        # Collect tags from tasks
        for task in self.tasks:
            if 'tags' in task:
                for tag in task['tags']:
                    self.all_tags.add(tag)

        # Collect tags from resources
        for resource in self.resources:
            if 'tags' in resource:
                for tag in resource['tags']:
                    self.all_tags.add(tag)

    def delete_task(self, task_id: int) -> bool:
        """Delete a task by its ID, removing any dependency links that
        pointed at it from other tasks' predecessor lists."""
        for i, task in enumerate(self.tasks):
            if task['task_id'] == task_id:
                del self.tasks[i]
                for other in self.tasks:
                    other['predecessors'] = [
                        entry
                        for entry in other.get('predecessors', [])
                        if entry['id'] != task_id
                    ]
                return True
        return False

    def update_task(self, task_id: int, **updates) -> bool:
        """Update task properties."""
        for task in self.tasks:
            if task['task_id'] == task_id:
                for key, value in updates.items():
                    task[key] = value
                return True
        return False

    def get_task(self, task_id: int) -> Optional[Dict[str, Any]]:
        """Get a task by its ID."""
        for task in self.tasks:
            if task['task_id'] == task_id:
                return task
        return None

    def move_task(self, task_id: int, row: int, col: int) -> bool:
        """Move a task to a new position."""
        return self.update_task(task_id, row=row, col=col)

    def resize_task(self, task_id: int, duration: int) -> bool:
        """Resize a task (change duration)."""
        return self.update_task(task_id, duration=duration)

    def calculate_resource_loading(
        self, tasks: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[int, List[float]]:
        """Calculate resource loading based on task positions.

        `tasks` limits the calculation to a subset (e.g. the currently
        filtered tasks, for the resource grid's 'Filtered tasks' load
        scope); default is every task in the model.
        """
        resource_loading = {}

        # Initialize dictionary with resource IDs as keys
        for resource in self.resources:
            resource_id = resource['id']
            resource_loading[resource_id] = [0.0] * self.days

        # Calculate loading for each resource on each day
        for task in self.tasks if tasks is None else tasks:
            col = task['col']
            duration = task['duration']

            # For each resource allocation in the task
            for resource_id_str, allocation in task['resources'].items():
                # Convert string resource_id to integer
                resource_id = int(resource_id_str)

                for day in range(duration):
                    if 0 <= col + day < self.days:
                        resource_loading[resource_id][col + day] += allocation

        return resource_loading

    def calculate_resource_utilization(
        self, resource_loading: Dict[int, List[float]]
    ) -> Dict[int, float]:
        """Whole-horizon utilization per resource: total load / total
        capacity over all days. This is the CCPM capacity-constrained-
        resource measure the resource grid's load sort uses (Stage 21).
        A zero-capacity resource reports inf when loaded (overloaded by
        definition) and 0.0 when idle, so the ordering stays total.
        """
        utilization = {}
        for resource in self.resources:
            resource_id = resource['id']
            total_capacity = sum(resource['capacity'][: self.days])
            total_load = sum(resource_loading.get(resource_id, ()))
            if total_capacity > 0:
                utilization[resource_id] = total_load / total_capacity
            else:
                utilization[resource_id] = float('inf') if total_load > 0 else 0.0
        return utilization

    def get_assigned_resource_ids(self, project_ids) -> set:
        """Resource ids assigned to at least one task of the given projects.

        Resources don't belong to projects - they're linked only through
        task assignments - so this is the membership test behind the
        resource grid's project filter.
        """
        wanted = set(project_ids)
        assigned = set()
        for task in self.tasks:
            if task.get('project_id') in wanted:
                for resource_id_str in task.get('resources', {}):
                    assigned.add(int(resource_id_str))
        return assigned

    def get_resource_by_id(self, resource_id: int) -> Optional[Dict[str, Any]]:
        """Find a resource by its ID."""
        for resource in self.resources:
            if resource['id'] == resource_id:
                return resource
        return None

    def get_resource_by_name(self, resource_name: str) -> Optional[Dict[str, Any]]:
        """Find a resource by its name."""
        for resource in self.resources:
            if resource['name'] == resource_name:
                return resource
        return None

    def add_resource(self, resource_name, works_weekends=True):
        """Add a new resource with default capacity."""
        if self.get_resource_by_name(resource_name):
            return False

        # Create new resource with default capacity
        default_capacity = [1.0] * self.days

        # If resource doesn't work weekends, set weekend capacity to 0
        if not works_weekends:
            for day in range(self.days):
                date = self.get_date_for_day(day)
                if date.weekday() >= 5:  # 5=Saturday, 6=Sunday
                    default_capacity[day] = 0.0

        new_resource = {
            'id': self._get_next_resource_id(),
            'name': resource_name,
            'capacity': default_capacity,
            'tags': [],
            'works_weekends': works_weekends,
        }

        self.resources.append(new_resource)
        return True

    def remove_resource(self, resource_id: int) -> bool:
        """Remove a resource and update tasks."""
        resource = self.get_resource_by_id(resource_id)
        if not resource:
            return False

        # Remove resource from all tasks
        for task in self.tasks:
            if resource_id in task['resources']:
                del task['resources'][resource_id]

        # Remove from resources list
        self.resources = [r for r in self.resources if r['id'] != resource_id]
        return True

    def update_resource_name(self, resource_id: int, new_name: str) -> bool:
        """Update the name of a resource."""
        # Check if the new name already exists
        if self.get_resource_by_name(new_name):
            return False

        resource = self.get_resource_by_id(resource_id)
        if resource:
            resource['name'] = new_name
            return True
        return False

    def _is_weekend(self, day_index, start_date=None):
        """Determine if a day index is a weekend based on a given start date."""
        # Use provided start date or the model's current start date
        start = start_date if start_date is not None else self.model.start_date
        date = start + timedelta(days=day_index)
        # Print for debugging (you can remove this later)
        print(
            f"Day {day_index}: {date.strftime('%Y-%m-%d')} is weekday {date.weekday()}"
        )
        return date.weekday() >= 5  # 5=Saturday, 6=Sunday

    def _update_resource_capacities_for_date_change(self, delta_days):
        """Update resource capacities when the start date changes."""
        # Calculate the new start date
        new_start_date = self.model.start_date + timedelta(days=-delta_days)

        # For each resource
        for resource in self.model.resources:
            works_weekends = resource.get('works_weekends', True)
            new_capacity = [1.0] * self.model.days

            if delta_days > 0:
                # Moving start date forward, shift capacities left
                for day in range(self.model.days - delta_days):
                    if day + delta_days < len(resource['capacity']):
                        # Copy existing capacity if available
                        new_capacity[day] = resource['capacity'][day + delta_days]

            elif delta_days < 0:
                # Moving start date backward, shift capacities right
                abs_delta = abs(delta_days)
                for day in range(abs_delta, self.model.days):
                    if day - abs_delta < len(resource['capacity']):
                        # Copy existing capacity if available
                        new_capacity[day] = resource['capacity'][day - abs_delta]

            # Check all days for weekend status using the new start date
            if not works_weekends:
                for day in range(self.model.days):
                    if self._is_weekend(day, new_start_date):
                        new_capacity[day] = 0.0

            # Update the resource capacity
            resource['capacity'] = new_capacity

    def update_resource_capacity(
        self, resource_id: int, day: int, capacity: float
    ) -> bool:
        """Update the capacity of a resource for a specific day."""
        resource = self.get_resource_by_id(resource_id)
        if resource and 0 <= day < self.days:
            resource['capacity'][day] = max(0.0, capacity)  # Ensure non-negative
            return True
        return False

    def update_resource_capacity_range(
        self, resource_id: int, start_day: int, end_day: int, capacity: float
    ) -> bool:
        """Update the capacity of a resource for a range of days."""
        resource = self.get_resource_by_id(resource_id)
        if not resource:
            return False

        start = max(0, start_day)
        end = min(self.days, end_day)

        for day in range(start, end):
            resource['capacity'][day] = max(0.0, capacity)  # Ensure non-negative

        return True

    def update_task_resource_allocation(
        self, task_id: int, resource_id: int, allocation: float
    ) -> bool:
        """Update the allocation of a resource for a task."""
        task = self.get_task(task_id)
        if not task:
            return False

        if allocation <= 0:
            # Remove the resource if allocation is zero or negative
            if resource_id in task['resources']:
                del task['resources'][resource_id]
        else:
            # Add or update the resource allocation
            task['resources'][resource_id] = allocation

        return True

    def add_predecessor(
        self,
        task_id: int,
        predecessor_id: int,
        link_type: str = DEFAULT_LINK_TYPE,
        lag: int = 0,
    ) -> bool:
        """Add or update a predecessor link (task_id depends on predecessor_id).

        `successors` is derived from predecessor links (see get_successor_ids),
        so only the dependent task's `predecessors` list needs updating.
        """
        if task_id == predecessor_id:
            return False  # Prevent self-linking

        if link_type not in VALID_LINK_TYPES:
            return False

        task = self.get_task(task_id)
        predecessor = self.get_task(predecessor_id)

        if not task or not predecessor:
            return False

        for entry in task['predecessors']:
            if entry['id'] == predecessor_id:
                entry['type'] = link_type
                entry['lag'] = lag
                return True

        task['predecessors'].append(
            {'id': predecessor_id, 'type': link_type, 'lag': lag}
        )
        return True

    def add_successor(
        self,
        task_id: int,
        successor_id: int,
        link_type: str = DEFAULT_LINK_TYPE,
        lag: int = 0,
    ) -> bool:
        """Add or update a successor link (successor_id depends on task_id)."""
        if task_id == successor_id:
            return False  # Prevent self-linking
        return self.add_predecessor(successor_id, task_id, link_type, lag)

    def remove_predecessor(self, task_id: int, predecessor_id: int) -> bool:
        """Remove a predecessor link from a task."""
        task = self.get_task(task_id)
        if not task:
            return False
        original_len = len(task['predecessors'])
        task['predecessors'] = [
            entry for entry in task['predecessors'] if entry['id'] != predecessor_id
        ]
        return len(task['predecessors']) < original_len

    def set_predecessors(self, task_id: int, entries: List[Any]) -> bool:
        """Replace a task's full predecessor list, e.g. from parsed notation text.

        Validates the whole list before committing, so a bad entry doesn't
        leave the task with a partially-applied set of links.
        """
        task = self.get_task(task_id)
        if not task:
            return False

        normalized = normalize_predecessor_entries(entries)
        for entry in normalized:
            if entry['id'] == task_id:
                return False  # Prevent self-linking
            if not self.get_task(entry['id']):
                return False  # Unknown predecessor task id

        task['predecessors'] = normalized
        return True

    def get_predecessor_ids(self, task_id: int) -> List[int]:
        """Return the ids of a task's predecessors."""
        task = self.get_task(task_id)
        if not task:
            return []
        return [entry['id'] for entry in task.get('predecessors', [])]

    def get_successor_ids(self, task_id: int) -> List[int]:
        """Return ids of tasks that declare `task_id` as a predecessor.

        Derived by scanning all tasks rather than stored, so it can never
        drift out of sync with the predecessor links that define it.
        """
        return [
            t['task_id']
            for t in self.tasks
            if any(entry['id'] == task_id for entry in t.get('predecessors', []))
        ]

    def get_successor_links(self, task_id: int) -> List[Dict[str, Any]]:
        """Return this task's outgoing links, derived from successors' predecessor lists.

        Each entry is `{'task_id': successor_id, 'type': str, 'lag': int}`, mirroring
        the predecessor entry on the successor task that points back at `task_id`.
        """
        links = []
        for t in self.tasks:
            for entry in t.get('predecessors', []):
                if entry['id'] == task_id:
                    links.append(
                        {
                            'task_id': t['task_id'],
                            'type': entry['type'],
                            'lag': entry.get('lag', 0),
                        }
                    )
        return links

    def load_from_file(self, file_path: str) -> bool:
        """Load project data from a file."""
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)

            # Basic validation
            if 'tasks' not in data or 'resources' not in data or 'days' not in data:
                return False

            # Load project data
            self.tasks = data['tasks']
            self.resources = data['resources']
            self.days = data['days']

            # After loading tasks, ensure each task has a notes field for backward complatability
            # After loading tasks, ensure each task has a notes field with the expected structure
            for task in self.tasks:
                if 'notes' not in task:
                    task['notes'] = []
                else:
                    # Ensure each note has the expected structure
                    for note in task['notes']:
                        if not isinstance(note, dict):
                            # Convert to proper format if needed
                            task['notes'] = []
                            break

                        # Ensure timestamp and text fields exist
                        if 'timestamp' not in note or 'text' not in note:
                            # If note is missing key fields, reset notes
                            task['notes'] = []
                            break
                    # Add CCPM fields if they don't exist

                if 'state' not in task:
                    task['state'] = 'planning'

                if 'type' not in task:
                    task['type'] = 'task'

                if 'project_id' not in task:
                    task['project_id'] = None

                if 'chain_id' not in task:
                    task['chain_id'] = None

                if 'baseline' not in task:
                    task['baseline'] = None

                if 'buffer_size_history' not in task:
                    task['buffer_size_history'] = []

                if 'fever_chart_history' not in task:
                    task['fever_chart_history'] = []

                # Add fields if they don't exist fir backward compatability
                if 'realistic_duration' not in task:
                    task['realistic_duration'] = task['duration']

                if 'optimal_duration' not in task:
                    task['optimal_duration'] = None

                if 'actual_start_date' not in task:
                    task['actual_start_date'] = None

                if 'actual_end_date' not in task:
                    task['actual_end_date'] = None

                if 'fullkit_date' not in task:
                    task['fullkit_date'] = None

                if 'remaining_duration_history' not in task:
                    task['remaining_duration_history'] = []

                # Predecessors carry link type/lag now; older saves stored plain
                # ids (implicit Finish-to-Start). successors is derived, not
                # loaded, so drop any stale copy from older saves.
                task['predecessors'] = normalize_predecessor_entries(
                    task.get('predecessors')
                )
                task.pop('successors', None)

                # JSON object keys are always strings, but everywhere else the
                # allocation dict is keyed by the integer resource id - convert
                # back so loaded and freshly-created tasks behave identically
                task['resources'] = {
                    int(rid) if isinstance(rid, str) and rid.isdigit() else rid: alloc
                    for rid, alloc in (task.get('resources') or {}).items()
                }
            # Load start_date if available
            if 'start_date' in data:
                try:
                    self.start_date = datetime.fromisoformat(data['start_date'])
                except ValueError:
                    # If there's an error parsing the date, use the current date
                    self.start_date = datetime.now().replace(
                        hour=0, minute=0, second=0, microsecond=0
                    )

            # Load setdate if available
            if 'setdate' in data:
                try:
                    self.setdate = datetime.fromisoformat(data['setdate'])
                except ValueError:
                    # If there's an error parsing the date, use the current date
                    self.setdate = datetime.now().replace(
                        hour=0, minute=0, second=0, microsecond=0
                    )

            # Load max_rows (previously max_tasks)
            if 'max_rows' in data:
                self.max_rows = data['max_rows']
            elif 'max_tasks' in data:  # For backward compatibility
                self.max_rows = data['max_tasks']

            # Ensure resource capacity arrays are proper length
            for resource in self.resources:
                if 'works_weekends' not in resource:
                    resource['works_weekends'] = True

                if 'capacity' not in resource or len(resource['capacity']) != self.days:
                    resource['capacity'] = [1.0] * self.days

                # Ensure resources have tags field
                if 'tags' not in resource:
                    resource['tags'] = []

            # Ensure resources have IDs
            for resource in self.resources:
                if 'id' not in resource:
                    resource['id'] = self._get_next_resource_id()

            # Find highest task ID to update counter
            max_task_id = 0
            for task in self.tasks:
                if task['task_id'] > max_task_id:
                    max_task_id = task['task_id']
            self.task_id_counter = max_task_id

            # Find highest resource ID to update counter
            max_resource_id = 0
            for resource in self.resources:
                if resource['id'] > max_resource_id:
                    max_resource_id = resource['id']
            self.resource_id_counter = max_resource_id

            # Load projects (older saves won't have this at all)
            self.projects = data.get('projects', [])
            for project in self.projects:
                if 'phase' not in project:
                    project['phase'] = 'planning'
                if 'url' not in project:
                    project['url'] = ''
                if 'ccpm_method' not in project:
                    project['ccpm_method'] = DEFAULT_CCPM_METHOD
                if 'fever_chart_slope' not in project:
                    project['fever_chart_slope'] = DEFAULT_FEVER_CHART_SLOPE
                if 'fever_chart_yellow_intercept' not in project:
                    project['fever_chart_yellow_intercept'] = (
                        DEFAULT_FEVER_CHART_YELLOW_INTERCEPT
                    )
                if 'fever_chart_red_intercept' not in project:
                    project['fever_chart_red_intercept'] = (
                        DEFAULT_FEVER_CHART_RED_INTERCEPT
                    )

            self.default_project_id = data.get('default_project_id')

            # Find highest project ID to update counter
            max_project_id = 0
            for project in self.projects:
                if project['id'] > max_project_id:
                    max_project_id = project['id']
            self.project_id_counter = max_project_id

            # Load chains (older saves won't have this at all - left empty
            # rather than re-seeding defaults, consistent with how projects
            # are handled above)
            self.chains = data.get('chains', [])
            for chain in self.chains:
                if 'color' not in chain:
                    chain['color'] = CRITICAL_CHAIN_COLOR
                if 'is_critical' not in chain:
                    chain['is_critical'] = False

            # Find highest chain ID to update counter
            max_chain_id = 0
            for chain in self.chains:
                if chain['id'] > max_chain_id:
                    max_chain_id = chain['id']
            self.chain_id_counter = max_chain_id

            # Rebuild all_tags
            self.refresh_all_tags()

            self.current_file_path = file_path

            return True
        except Exception as e:
            print(f'Error loading file: {e}')
            return False

    def save_to_file(self, file_path: str) -> bool:
        """Save project data to a file."""
        try:
            project_data = {
                'tasks': self.tasks,
                'resources': self.resources,
                'days': self.days,
                'max_rows': self.max_rows,
                'start_date': self.start_date.isoformat(),
                'setdate': self.setdate.isoformat(),
                'projects': self.projects,
                'default_project_id': self.default_project_id,
                'chains': self.chains,
            }

            with open(file_path, 'w') as f:
                json.dump(project_data, f, indent=2)

            self.current_file_path = file_path
            return True
        except Exception as e:
            print(f'Error saving file: {e}')
            return False

    # Add tags to existing tasks during sample creation
    def create_sample_tasks(self) -> None:
        """Create some sample tasks for demo purposes."""
        # Get resource IDs for easier reference
        resource_a_id = self.resources[0]['id']  # Resource A
        resource_b_id = self.resources[1]['id']  # Resource B
        resource_c_id = self.resources[2]['id']  # Resource C
        resource_d_id = self.resources[3]['id']  # Resource D

        # Add tasks with fractional resource allocations, tags, and colors
        self.add_task(
            row=1,
            col=5,
            duration=5,
            description='Task A',
            resources={resource_a_id: 0.5, resource_b_id: 1.5},
            url='https://www.google.com',
            tags=['important', 'phase1'],
            color='LightBlue',  # Add color attribute
        )
        self.add_task(
            row=2,
            col=12,
            duration=4,
            description='Task B',
            resources={resource_a_id: 1.0, resource_b_id: 0.75, resource_c_id: 0.25},
            url='https://www.google.com',
            tags=['phase1'],
            color='LightGreen',  # Add color attribute
        )
        self.add_task(
            row=3,
            col=2,
            duration=3,
            description='Task C',
            resources={resource_a_id: 2.0},
            url='https://www.google.com',
            tags=['phase2', 'critical'],
            color='Salmon',  # Add color attribute
        )
        self.add_task(
            row=4,
            col=1,
            duration=2,
            description='Task D',
            resources={resource_a_id: 0.5, resource_d_id: 0.5},
            tags=['phase2'],
            color='Gold',  # Add color attribute
        )

        # Add tags to resources as well
        self.set_resource_tags(resource_a_id, ['team1', 'developer'])
        self.set_resource_tags(resource_b_id, ['team1', 'designer'])
        self.set_resource_tags(resource_c_id, ['team2', 'developer'])
        self.set_resource_tags(resource_d_id, ['team2', 'qa'])

        # Make sure all_tags is updated
        self.refresh_all_tags()

    def set_task_color(self, task_id: int, color: str) -> bool:
        """Set the color for a specific task.

        Args:
            task_id: ID of the task to update
            color: Color name to set (must be a valid web color name)

        Returns:
            bool: True if successful, False if task not found
        """
        task = self.get_task(task_id)
        if not task:
            return False

        task['color'] = color
        return True

    def set_task_colors(self, task_ids: List[int], color: str) -> int:
        """Set the color for multiple tasks.

        Args:
            task_ids: List of task IDs to update
            color: Color name to set (must be a valid web color name)

        Returns:
            int: Number of tasks successfully updated
        """
        count = 0
        for task_id in task_ids:
            if self.set_task_color(task_id, color):
                count += 1
        return count

    def add_note_to_task(self, task_id: int, note_text: str) -> bool:
        """Add a timestamped note to a task.

        Args:
            task_id: ID of the task to add the note to
            note_text: Content of the note

        Returns:
            bool: True if successful, False if task not found
        """
        task = self.get_task(task_id)
        if not task:
            return False

        # Ensure task has a notes list
        if 'notes' not in task:
            task['notes'] = []

        # Create the note with timestamp
        note = {'timestamp': datetime.now().isoformat(), 'text': note_text}

        # Add the note to the task
        task['notes'].append(note)
        return True

    def get_task_notes(self, task_id: int) -> List[Dict[str, Any]]:
        """Get all notes for a specific task.

        Args:
            task_id: ID of the task

        Returns:
            List of note dictionaries, each with 'timestamp' and 'text' fields
        """
        task = self.get_task(task_id)
        if not task or 'notes' not in task:
            return []

        # Sort notes by timestamp, newest first
        return sorted(task['notes'], key=lambda note: note['timestamp'], reverse=True)

    def delete_note_from_task(self, task_id: int, note_index: int) -> bool:
        """Delete a note from a task.

        Args:
            task_id: ID of the task
            note_index: Index of the note in the task's notes list

        Returns:
            bool: True if successful, False if task or note not found
        """
        task = self.get_task(task_id)
        if not task or 'notes' not in task:
            return False

        # Ensure the index is valid
        if note_index < 0 or note_index >= len(task['notes']):
            return False

        # Remove the note
        task['notes'].pop(note_index)
        return True

    def get_all_notes_for_tasks(self, task_ids: List[int]) -> List[Dict[str, Any]]:
        """Get all notes for a list of tasks, sorted by timestamp.

        Args:
            task_ids: List of task IDs to get notes for

        Returns:
            List of note dictionaries with additional 'task_id' and 'original_index' fields
        """
        all_notes = []

        for task_id in task_ids:
            task = self.get_task(task_id)
            if not task or 'notes' not in task:
                continue

            # Add task_id and original_index to each note for reference
            for i, note in enumerate(task['notes']):
                note_with_task = note.copy()
                note_with_task['task_id'] = task_id
                note_with_task['task_description'] = task.get(
                    'description', f'Task {task_id}'
                )
                note_with_task['original_index'] = i  # Store the original index
                all_notes.append(note_with_task)

        # Sort all notes by timestamp, newest first
        return sorted(all_notes, key=lambda note: note['timestamp'], reverse=True)

    def record_remaining_duration(self, task_id: int, remaining_duration: int) -> bool:
        """Record a new remaining duration estimate for a task on the current setdate.

        Also anchors and re-estimates the task's visual position:
        - The first call snaps `col` to the setdate's day-column (the "anchor") -
          the bar's left edge jumps to where work actually started, which may
          be earlier or later than originally planned. The original plan is
          only recoverable from the project's baseline snapshot.
        - Every call (including the first) recomputes `duration` so the bar's
          right edge reflects the most recent estimate on record - i.e.
          `col + duration` becomes `(day-column of the latest estimate's date)
          + its remaining_duration`. This is keyed off the latest entry *by
          date*, not insertion order, so a backdated correction is handled
          the same way `get_latest_remaining_duration` already sorts.

        Args:
            task_id: ID of the task
            remaining_duration: Estimated remaining duration in days

        Returns:
            bool: True if successful, False if task not found
        """
        task = self.get_task(task_id)
        if not task:
            return False

        # Create record with current setdate
        record = {
            'date': self.setdate.isoformat(),
            'remaining_duration': remaining_duration,
        }

        # Initialize the history list if not present (for backward compatibility)
        if 'remaining_duration_history' not in task:
            task['remaining_duration_history'] = []

        # Add the record
        task['remaining_duration_history'].append(record)

        # If this is the first record, anchor the actual start
        if not task.get('actual_start_date'):
            task['actual_start_date'] = self.setdate.isoformat()
            task['col'] = self.get_day_for_date(self.setdate)

        # Re-estimate the finish from the latest entry on record (by date)
        latest_entry = self._get_latest_remaining_duration_entry(task_id)
        entry_col = self.get_day_for_date(datetime.fromisoformat(latest_entry['date']))
        task['duration'] = max(
            0, entry_col + latest_entry['remaining_duration'] - task['col']
        )

        # If remaining duration is 0, set the actual end date and mark as done
        if remaining_duration == 0:
            task['actual_end_date'] = self.setdate.isoformat()
            task['state'] = 'done'

        return True

    def get_remaining_duration_history(self, task_id: int) -> List[Dict[str, Any]]:
        """Get the history of remaining duration estimates for a task.

        Args:
            task_id: ID of the task

        Returns:
            List of dictionaries with date and remaining_duration fields
        """
        task = self.get_task(task_id)
        if not task or 'remaining_duration_history' not in task:
            return []

        return task['remaining_duration_history']

    def _get_latest_remaining_duration_entry(
        self, task_id: int
    ) -> Optional[Dict[str, Any]]:
        """Get the most recent remaining duration history entry.

        "Most recent" is by date, then by recording order for entries sharing
        the same date - so recording an update more than once in the same day
        keeps the last one entered, not silently keeping the first (a plain
        stable sort on date alone would tie-break in insertion order, always
        favoring the first entry of the day).
        """
        history = self.get_remaining_duration_history(task_id)
        if not history:
            return None

        return max(
            enumerate(history), key=lambda indexed: (indexed[1]['date'], indexed[0])
        )[1]

    def get_latest_remaining_duration(self, task_id: int) -> Optional[int]:
        """Get the most recent remaining duration estimate for a task.

        Args:
            task_id: ID of the task

        Returns:
            The most recent remaining duration estimate, or None if no estimates exist
        """
        entry = self._get_latest_remaining_duration_entry(task_id)
        return entry['remaining_duration'] if entry else None

    def get_task_progress_fraction(self, task_id: int) -> Optional[float]:
        """Get how much of a started task is done, as of its latest estimate.

        Returns None if the task hasn't started (no status update recorded
        yet) - callers should skip drawing a progress indicator in that case.
        Otherwise returns a value in [0.0, 1.0]: 1.0 once `state` is 'done',
        otherwise `(duration - latest_remaining_duration) / duration`, i.e.
        how much of the current best-estimate span had already elapsed as of
        the most recent status update.
        """
        task = self.get_task(task_id)
        if not task or not task.get('actual_start_date'):
            return None

        if task.get('state') == 'done':
            return 1.0

        latest_remaining = self.get_latest_remaining_duration(task_id)
        if latest_remaining is None:
            return None

        total = task['duration']
        if total <= 0:
            return 1.0

        return min(1.0, max(0.0, (total - latest_remaining) / total))

    def record_buffer_size_change(
        self, buffer_task_id: int, duration: int, reason: str, trigger_task_id: int
    ) -> bool:
        """Log an execution-phase buffer size change, for later fever-chart
        reporting (Stage 7). Does not itself change col/duration - callers
        are responsible for that; this only records the history trail.

        Args:
            buffer_task_id: ID of the buffer task whose size just changed
            duration: the buffer's new duration after this change
            reason: 'encroachment' | 'fully_consumed' | 'slack_growth'
            trigger_task_id: ID of the PB/FB predecessor task whose movement
                caused this change - recorded so it's possible to later figure
                out what happened, not just that the buffer changed size
        """
        task = self.get_task(buffer_task_id)
        if not task:
            return False

        if 'buffer_size_history' not in task:
            task['buffer_size_history'] = []

        task['buffer_size_history'].append(
            {
                'date': self.setdate.isoformat(),
                'duration': duration,
                'reason': reason,
                'trigger_task_id': trigger_task_id,
            }
        )
        return True

    def get_chain_tasks(self, chain_id: int, project_id: int) -> List[Dict[str, Any]]:
        """Return a chain's ordinary (non-buffer) tasks, sorted by start
        (`col`). Includes every task tagged with this chain, regardless of
        whether they form a single strand or branching/parallel feeder
        paths that later merge - callers that need a completion-certainty
        ordering (Protected Progress Frontier) should sort by finish instead,
        see `compute_fever_chart_point`.
        """
        tasks = [
            t
            for t in self.tasks
            if t.get('chain_id') == chain_id
            and t.get('project_id') == project_id
            and t.get('type') not in BUFFER_TASK_TYPES
        ]
        return sorted(tasks, key=lambda t: t['col'])

    def get_buffer_terminal_task(
        self, buffer_task_id: int
    ) -> Optional[Dict[str, Any]]:
        """Return the one ordinary task that is a buffer's own direct
        predecessor - the "terminal protected task" in Stage 8's fever chart
        calculations (the last work task before the buffer).
        """
        buffer_task = self.get_task(buffer_task_id)
        if not buffer_task:
            return None

        for entry in buffer_task.get('predecessors', []):
            predecessor = self.get_task(entry['id'])
            if predecessor and predecessor.get('type') not in BUFFER_TASK_TYPES:
                return predecessor

        return None

    def get_buffer_merge_task(
        self, buffer_task_id: int
    ) -> Optional[Dict[str, Any]]:
        """Return the one ordinary task on a buffer's successor side - the
        merge point it protects. Returns None unless exactly one such
        successor exists: a buffer with several merge successors is
        ambiguous (the open question flagged in planning.md), so callers
        must fall back to buffer-local math rather than guess.
        """
        merge_tasks = []
        for link in self.get_successor_links(buffer_task_id):
            if link['type'] not in ('FS', 'FB', 'PB'):
                continue
            successor = self.get_task(link['task_id'])
            if successor and successor.get('type') not in BUFFER_TASK_TYPES:
                merge_tasks.append(successor)
        return merge_tasks[0] if len(merge_tasks) == 1 else None

    def compute_fever_chart_point(
        self, buffer_task_id: int
    ) -> Optional[Dict[str, Any]]:
        """Compute Stage 8's CPSL/PPF/forecast_lateness for a buffer, as of now.

        Returns None if not computable: not actually a buffer, no terminal
        task found (see `get_buffer_terminal_task`), or its project isn't in
        execution - the fever chart only means something once a project is
        being executed.
        """
        buffer_task = self.get_task(buffer_task_id)
        if not buffer_task or buffer_task.get('type') not in BUFFER_TASK_TYPES:
            return None

        project = self.get_project_by_id(buffer_task.get('project_id'))
        if not project or project['phase'] != 'execution':
            return None

        terminal_task = self.get_buffer_terminal_task(buffer_task_id)
        if not terminal_task:
            return None

        chain_tasks = self.get_chain_tasks(
            terminal_task.get('chain_id'), terminal_task.get('project_id')
        )
        if not chain_tasks:
            return None

        chain_start = min(task['col'] for task in chain_tasks)

        # Protected Progress Frontier: every protected activity *scheduled to
        # finish* before the frontier must be confirmed complete - so walk
        # the chain's tasks in finish order (not start order), regardless of
        # which parallel/feeder path each is on, and stop at the first task
        # that isn't done. A later-finishing task on a different path being
        # done already doesn't let the frontier skip past an earlier
        # incomplete one (see fever-chart-considerations.md).
        frontier = chain_start
        for task in sorted(chain_tasks, key=lambda t: t['col'] + t['duration']):
            if task.get('state') == 'done':
                frontier = max(frontier, task['col'] + task['duration'])
            else:
                break

        forecast_finish = terminal_task['col'] + terminal_task['duration']
        cpsl = forecast_finish - chain_start
        ppf = frontier - chain_start

        terminal_baseline = terminal_task.get('baseline')
        if terminal_baseline:
            baseline_finish = (
                terminal_baseline['col'] + terminal_baseline['duration']
            )
        else:
            # No baseline on record for the terminal task (e.g. added to the
            # chain after the planning->execution transition) - treat now as
            # the reference point, so lateness starts at 0 rather than being
            # unknowable.
            baseline_finish = forecast_finish

        forecast_lateness = forecast_finish - baseline_finish

        if buffer_task.get('type') == 'feeding_buffer':
            buffer_baseline = buffer_task.get('baseline')
            if buffer_baseline:
                # Shock-absorber accounting for feeding buffers: consumption
                # measures how much of the originally agreed protection is
                # no longer available, regardless of which side the shock
                # came from - the feeding chain slipping into the buffer
                # (push, Stage 7's absorb) or the merge point being pulled
                # earlier by the relay-runner cascade on the critical chain
                # (pull, Stage 3's glue). Both already land in the buffer's
                # LIVE duration, so:
                #
                #   effective lateness = baseline size - live size + overflow
                #
                # where overflow is how far the merge point has been pushed
                # past its own baseline once the buffer is fully consumed
                # (>100% consumption = forecast breach, matching the
                # push-only formula this generalizes). Consumers divide by
                # the baseline buffer size, giving e.g. (5-2)/5 = 60% the
                # moment a routine on-track update on the critical chain
                # pulls the merge point early - the fever chart's job is to
                # tell the feeding team the race has changed.
                overflow = 0
                merge_task = self.get_buffer_merge_task(buffer_task_id)
                if merge_task:
                    merge_baseline = merge_task.get('baseline')
                    if merge_baseline:
                        overflow = max(
                            0, merge_task['col'] - merge_baseline['col']
                        )
                forecast_lateness = (
                    buffer_baseline['duration']
                    - buffer_task['duration']
                    + overflow
                )

        return {'cpsl': cpsl, 'ppf': ppf, 'forecast_lateness': forecast_lateness}

    def capture_fever_chart_snapshot(self, project_id: int = None) -> int:
        """Recompute and log a fever chart point for every buffer that
        currently supports one (Stage 8) - meant to be called after every
        status update, since a buffer's numbers can only reliably be
        captured live, not reconstructed after the fact (see planning.md).

        Args:
            project_id: if given, only recompute buffers belonging to this
                project (the project of whichever task was just updated) -
                this app supports multiple concurrent projects (rolling-wave
                planning), and a status update in one project must not log a
                redundant, unrelated point onto another project's buffers.
                If None, recomputes every buffer in the whole model.

        Returns the number of buffers a point was captured for.
        """
        captured_at = self.setdate.isoformat()
        count = 0
        for task in self.tasks:
            if task.get('type') not in BUFFER_TASK_TYPES:
                continue

            if project_id is not None and task.get('project_id') != project_id:
                continue

            point = self.compute_fever_chart_point(task['task_id'])
            if point is None:
                continue

            if 'fever_chart_history' not in task:
                task['fever_chart_history'] = []

            task['fever_chart_history'].append(
                {
                    'date': captured_at,
                    'cpsl': point['cpsl'],
                    'ppf': point['ppf'],
                    'forecast_lateness': point['forecast_lateness'],
                }
            )
            count += 1

        return count

    def set_task_state(self, task_id: int, state: str) -> bool:
        """Set the state of a task.

        Args:
            task_id: ID of the task
            state: New state ('planning', 'buffered', 'done')

        Returns:
            bool: True if successful, False if task not found or invalid state
        """
        valid_states = ['planning', 'buffered', 'done']
        if state not in valid_states:
            return False

        task = self.get_task(task_id)
        if not task:
            return False

        task['state'] = state
        return True

    def set_task_type(self, task_id: int, task_type: str) -> bool:
        """Set the type of a task.

        Args:
            task_id: ID of the task
            task_type: New type ('task', 'project_buffer', 'feeding_buffer')

        Returns:
            bool: True if successful, False if task not found or invalid type
        """
        if task_type not in TASK_TYPES:
            return False

        task = self.get_task(task_id)
        if not task:
            return False

        task['type'] = task_type
        return True

    def set_task_project(self, task_id: int, project_id: Optional[int]) -> bool:
        """Reassign a task to a different project (or None to unassign).

        Args:
            task_id: ID of the task
            project_id: ID of the project, or None to unassign

        Returns:
            bool: True if successful, False if task not found or project not found
        """
        if project_id is not None and not self.get_project_by_id(project_id):
            return False

        task = self.get_task(task_id)
        if not task:
            return False

        task['project_id'] = project_id
        return True

    def set_optimal_duration(self, task_id: int, duration: int) -> bool:
        """Set the optimal duration for a task - "if everything went
        perfectly, no disruptions, best case" (see Realistic = Optimal +
        Contingency in planning.md).

        Args:
            task_id: ID of the task
            duration: The optimal duration in days

        Returns:
            bool: True if successful, False if task not found
        """
        task = self.get_task(task_id)
        if not task:
            return False

        task['optimal_duration'] = duration
        return True

    def set_realistic_duration(self, task_id: int, duration: int) -> bool:
        """Set the realistic duration for a task - "how long will this
        actually take", including normal everyday contingency (see
        Realistic = Optimal + Contingency in planning.md).

        Args:
            task_id: ID of the task
            duration: The realistic duration in days

        Returns:
            bool: True if successful, False if task not found
        """
        task = self.get_task(task_id)
        if not task:
            return False

        task['realistic_duration'] = duration
        return True

    def set_fullkit_date(self, task_id: int) -> bool:
        """Set the full kit date to the current setdate.

        Args:
            task_id: ID of the task

        Returns:
            bool: True if successful, False if task not found
        """
        task = self.get_task(task_id)
        if not task:
            return False

        task['fullkit_date'] = self.setdate.isoformat()
        return True
