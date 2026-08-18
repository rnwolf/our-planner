"""TypedDict shapes for the core entities TaskResourceModel stores.

Kept separate from task_resource_model.py so these can be imported by both
the model and (eventually) any other module that needs to describe the same
shapes precisely, without a circular import back into the model itself.
"""

from typing import List, NotRequired, Optional, TypedDict


class PredecessorLink(TypedDict):
    """One {id, type, lag} dependency link, as stored in a task's
    'predecessors' list. See dependency_notation.py."""

    id: int
    type: str
    lag: int


class NoteDict(TypedDict):
    timestamp: str
    text: str


class BaselineDict(TypedDict):
    """Snapshot of a task's col/duration captured by capture_project_baseline."""

    col: int
    duration: int
    realistic_duration: int
    captured_at: str


class BufferSizeHistoryEntry(TypedDict):
    """One execution-phase buffer size change, logged by
    record_buffer_size_change."""

    date: str
    duration: int
    reason: str
    trigger_task_id: int


class FeverChartPoint(TypedDict):
    """CPSL/PPF/forecast_lateness for a buffer, as computed by
    compute_fever_chart_point - the un-dated core of a FeverChartHistoryEntry."""

    cpsl: float
    ppf: float
    forecast_lateness: float


class FeverChartHistoryEntry(FeverChartPoint):
    """One fever chart point, logged by capture_fever_chart_snapshot."""

    date: str


class RemainingDurationHistoryEntry(TypedDict):
    """One remaining-duration estimate, logged by record_remaining_duration.

    reason/note are NotRequired: entries logged before this field existed
    (or written by a caller that doesn't pass one, e.g. existing tests)
    simply don't have the key, same pattern as ResourceDict.works_weekends.
    reason is expected to be one of REMAINING_DURATION_REASONS, but isn't
    typed as a Literal - it's user-facing text read back into a Combobox,
    not branched on in code, so a stricter type wouldn't buy correctness
    and would make loading an older or hand-edited save file needlessly
    fragile."""

    date: str
    remaining_duration: int
    reason: NotRequired[str]
    note: NotRequired[str]


class BufferUpdateReasonEntry(TypedDict):
    """One status update carrying a reason and/or note, attributed back to
    the task it was recorded against - as returned by
    get_buffer_update_reasons for display alongside a buffer's fever
    chart. Not itself stored on any task; assembled on read from the
    protected chain's remaining_duration_history entries."""

    date: str
    task_id: int
    task_description: str
    remaining_duration: int
    reason: NotRequired[str]
    note: NotRequired[str]


class StatusUpdateLogEntry(TypedDict):
    """One recorded status update, as returned by
    ReportOperations.compute_status_update_log for the Status Update Log
    report. Same shape as BufferUpdateReasonEntry but a distinct type: that
    one is filtered down to only entries carrying a reason/note, scoped to
    one buffer's protected chain; this is every update (reason/note or
    not) across whatever the Filter menu currently scopes to, so a team
    can review the complete record, not just the annotated subset."""

    date: str
    task_id: int
    task_description: str
    remaining_duration: int
    task_url: NotRequired[str]
    reason: NotRequired[str]
    note: NotRequired[str]


class SuccessorLink(TypedDict):
    """One outgoing link derived from a successor's predecessor entry, as
    returned by get_successor_links. Mirrors PredecessorLink but keyed by
    'task_id' (the successor) rather than 'id' (the predecessor)."""

    task_id: int
    type: str
    lag: int


class NoteWithTaskInfo(NoteDict):
    """A NoteDict enriched with the owning task's id/description/position in
    its task's notes list, as returned by get_all_notes_for_tasks."""

    task_id: int
    task_description: str
    original_index: int


class TaskDict(TypedDict):
    task_id: int
    row: int
    col: int
    duration: int
    description: str
    url: str
    resources: dict[int, float]
    predecessors: List[PredecessorLink]
    tags: List[str]
    color: str
    notes: List[NoteDict]
    project_id: Optional[int]
    chain_id: Optional[int]
    type: str  # 'task' | 'project_buffer' | 'feeding_buffer'
    state: str  # 'planning' | 'buffered' | 'done'
    realistic_duration: int
    optimal_duration: Optional[int]
    actual_start_date: Optional[str]
    actual_end_date: Optional[str]
    fullkit_date: Optional[str]
    remaining_duration_history: List[RemainingDurationHistoryEntry]
    baseline: Optional[BaselineDict]
    buffer_size_history: List[BufferSizeHistoryEntry]
    fever_chart_history: List[FeverChartHistoryEntry]


class ResourceDict(TypedDict):
    id: int
    name: str
    capacity: List[float]
    tags: List[str]
    url: str
    # Zero or more contact addresses as one comma/semicolon-separated string;
    # stored and edited as free text, not parsed into a list.
    emails: str
    # Absent on resources seeded in __init__ (pre-dates this field); present
    # on resources created via add_resource(). Readers use
    # resource.get('works_weekends', True).
    works_weekends: NotRequired[bool]


class ProjectDict(TypedDict):
    id: int
    name: str
    url: str
    phase: str  # 'planning' | 'execution'
    ccpm_method: str
    fever_chart_slope: float
    fever_chart_yellow_intercept: float
    fever_chart_red_intercept: float


class ChainDict(TypedDict):
    id: int
    name: str
    color: str
    is_critical: bool
