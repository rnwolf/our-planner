#!/usr/bin/env python3
"""Generate a large, realistic sample save file for our-planner.

Builds a ~30-person organisation's project portfolio directly at the
model/operations layer (no Tk at all - the same style tests/
test_scenarios.py and scripts/stage12_walkthrough.py already use), then
writes it out via TaskResourceModel.save_to_file() so it can be opened
in the real app with File > Open.

The operating model this simulates, per the brief: most work is
triaged into small, CCPM-scheduled "mini-projects" with a team kept
constant for the life of the project; the rest sits in a prioritised
backlog and gets pulled off ad hoc (roughly a quarter of all work at
any point in time). The data spans roughly three months in the past
through one month in the future from today, so the file exercises a
realistic mix of completed, in-progress, and not-yet-started work
simultaneously - exactly the shape a real user's file would have.

Mini-projects are built as an ordinary rolling-wave task network first,
then scheduled for real via CcpmOperations.schedule_project_core() (the
same core the UI's File > Schedule with CCPM... calls) so buffer sizes
and the critical chain are genuine scheduler output, not hand-faked
numbers. The rolling-wave draft is then deleted, leaving only the
scheduled "<name> (CCPM)" project.

Usage:
    uv run python sample-app-file/generate_sample_app_file.py
"""

from __future__ import annotations

import random
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from unittest.mock import MagicMock

from src.model.task_resource_model import TaskResourceModel
from src.operations.ccpm_operations import CcpmOperations
from src.operations.task_operations import TaskOperations

RNG_SEED = 20260819
OUTPUT_PATH = Path(__file__).resolve().parent / 'realistic-portfolio.json'

PAST_DAYS = 90
FUTURE_DAYS = 30
DAYS_MARGIN = 25  # headroom past the window for buffers/slippage

# -- organisation roster -----------------------------------------------
# (name, role) - 30 people. Only dev/qa/designer/ba/devops are drawn on
# by the mini-project task shapes below; lead/architect/data mostly pick
# up backlog work, the way senior/specialist roles often do in practice.
ROSTER = [
    ('Priya Nair', 'dev'),
    ('Tom Whitfield', 'dev'),
    ('Aisha Rahman', 'dev'),
    ('Ben Carter', 'dev'),
    ('Yuki Tanaka', 'dev'),
    ('Liam O’Connor', 'dev'),
    ('Fatima Al-Sayed', 'dev'),
    ('Marcus Webb', 'dev'),
    ('Elena Popescu', 'qa'),
    ('Noah Fischer', 'qa'),
    ('Grace Okafor', 'qa'),
    ('Ravi Deshmukh', 'qa'),
    ('Sofia Rossi', 'designer'),
    ('Owen Bennett', 'designer'),
    ('Mei Lin', 'designer'),
    ('Hassan Farouk', 'devops'),
    ('Ingrid Larsen', 'devops'),
    ('Cody Nguyen', 'devops'),
    ('Dana Kowalski', 'ba'),
    ('Ahmed Siddiqui', 'ba'),
    ('Rosa Martinez', 'ba'),
    ('Jack Sullivan', 'ba'),
    ('Helen Zhao', 'lead'),
    ('Victor Adeyemi', 'lead'),
    ('Claire Dubois', 'lead'),
    ('Samuel Osei', 'architect'),
    ('Nina Petrova', 'architect'),
    ('Leo Fontaine', 'data'),
    ('Amara Chukwu', 'data'),
    ('Piotr Nowak', 'data'),
]
assert len(ROSTER) == 30

# Ops/on-call style roles keep weekend capacity; everyone else is a
# standard Mon-Fri office worker.
WEEKEND_ROLES = {'devops'}

ROLE_COLOR = {
    'dev': 'LightBlue',
    'qa': 'LightGreen',
    'designer': 'MediumOrchid',
    'ba': 'Khaki',
    'devops': 'Orange',
    'lead': 'Gold',
    'architect': 'CornflowerBlue',
    'data': 'LightSalmon',
}
BACKLOG_COLOR = 'LightYellow'

# -- mini-project shapes -------------------------------------------------
# (task name, role, [predecessor names], (min_duration, max_duration), lane)
# `lane` is the task's swimlane *within its own project* (0 = the main
# sequential thread; 1/2 = a parallel branch that needs its own row so it
# doesn't overlap the thread it's running alongside) - not a row number
# itself. assign_project_rows() below turns a project's lane count into
# a compact, reusable block of real rows. Every shape has at least one
# merge point, so every scheduled project contributes at least one
# feeding buffer, not just a project buffer.
PROJECT_SHAPES = {
    'small': [
        ('Analysis', 'ba', [], (2, 4), 0),
        ('Build', 'dev', ['Analysis'], (3, 6), 0),
        ('Review', 'qa', ['Analysis'], (1, 2), 1),
        ('Test', 'qa', ['Build', 'Review'], (2, 3), 0),
        ('Deploy', 'devops', ['Test'], (1, 2), 0),
    ],
    'medium': [
        ('Design', 'designer', [], (2, 4), 0),
        ('Build-A', 'dev', ['Design'], (4, 7), 0),
        ('Build-B', 'dev', ['Design'], (3, 6), 1),
        ('Integration', 'dev', ['Build-A', 'Build-B'], (2, 4), 0),
        ('Test', 'qa', ['Integration'], (2, 4), 0),
        ('UAT', 'ba', ['Test'], (2, 3), 0),
        ('Deploy', 'devops', ['UAT'], (1, 2), 0),
    ],
    'large': [
        ('Discovery', 'ba', [], (2, 4), 0),
        ('Design', 'designer', ['Discovery'], (3, 5), 0),
        ('Build-A', 'dev', ['Design'], (5, 8), 0),
        ('Build-B', 'dev', ['Design'], (4, 7), 1),
        ('Build-C', 'dev', ['Design'], (4, 7), 2),
        ('Integration', 'dev', ['Build-A', 'Build-B', 'Build-C'], (2, 4), 0),
        ('Security Review', 'qa', ['Integration'], (2, 3), 1),
        ('Test', 'qa', ['Integration'], (3, 5), 0),
        ('UAT', 'ba', ['Security Review', 'Test'], (2, 4), 0),
        ('Deploy', 'devops', ['UAT'], (1, 2), 0),
    ],
}
TEAM_REQS = {
    'small': {'ba': 1, 'dev': 1, 'qa': 1, 'devops': 1},
    'medium': {'designer': 1, 'dev': 2, 'qa': 1, 'ba': 1, 'devops': 1},
    'large': {'ba': 1, 'designer': 1, 'dev': 3, 'qa': 2, 'devops': 1},
}

PROJECT_NAMES = [
    'Customer Portal Refresh',
    'Invoice Automation',
    'Warehouse Mobile App',
    'Payments Gateway Upgrade',
    'Onboarding Redesign',
    'Fleet Tracking Rollout',
    'Supplier Data Migration',
    'Loyalty Programme Revamp',
    'Returns Workflow',
    'Store Inventory Sync',
    'HR Self-Service Portal',
    'Contract Renewal Tool',
    'Pricing Engine Update',
    'Field Service App',
    'Compliance Reporting Suite',
    'Order Tracking Redesign',
    'Vendor Onboarding Flow',
    'Analytics Dashboard V2',
]

# Business area each project belongs to - applied as a tag to every task
# in it, so "filter the task grid to everything touching compliance"
# (or any other area) works across the whole portfolio, not just within
# one project. Curated by hand to match what each project name actually
# implies, rather than assigned at random.
PROJECT_DOMAINS = {
    'Customer Portal Refresh': 'customer',
    'Invoice Automation': 'finance',
    'Warehouse Mobile App': 'operations',
    'Payments Gateway Upgrade': 'finance',
    'Onboarding Redesign': 'customer',
    'Fleet Tracking Rollout': 'operations',
    'Supplier Data Migration': 'operations',
    'Loyalty Programme Revamp': 'customer',
    'Returns Workflow': 'operations',
    'Store Inventory Sync': 'operations',
    'HR Self-Service Portal': 'internal',
    'Contract Renewal Tool': 'internal',
    'Pricing Engine Update': 'finance',
    'Field Service App': 'operations',
    'Compliance Reporting Suite': 'compliance',
    'Order Tracking Redesign': 'customer',
    'Vendor Onboarding Flow': 'operations',
    'Analytics Dashboard V2': 'internal',
}
assert set(PROJECT_DOMAINS) == set(PROJECT_NAMES)


def working_capacity(role: str) -> bool:
    return role in WEEKEND_ROLES


# example.com/.net/.org are IANA-reserved for documentation (RFC 2606) - a
# real domain that resolves to nothing meaningful, so these URLs are safe
# placeholders that still exercise the exact same "task/resource text
# becomes a clickable hyperlink" rendering and click-through path a real
# tracker/directory link would.
TRACKER_URL = 'https://tracker.example.com/browse/PORT-{n}'
DIRECTORY_URL = 'https://directory.example.com/people/{slug}'
EMAIL_ADDRESS = '{slug}@example.com'


def slugify_name(name: str) -> str:
    """A stable, URL-safe slug for a resource's directory-page URL -
    lowercase, hyphen-joined, punctuation (apostrophes included) stripped
    rather than percent-encoded, so "Liam O'Connor" reads as liam-oconnor."""
    cleaned = re.sub(r'[^a-z0-9\s-]', '', name.lower())
    return re.sub(r'\s+', '-', cleaned.strip())


def email_local_part(name: str) -> str:
    """A dot-joined variant of slugify_name for an email address's local
    part, so "Liam O'Connor" reads as liam.oconnor rather than
    liam-oconnor - matches the usual firstname.lastname convention."""
    return slugify_name(name).replace('-', '.')


def build_roster(model: TaskResourceModel) -> dict[str, list[int]]:
    """Adds all 30 resources, returns role -> [resource_id, ...]."""
    by_role: dict[str, list[int]] = {}
    for name, role in ROSTER:
        resource = model.add_resource(
            name,
            works_weekends=working_capacity(role),
            url=DIRECTORY_URL.format(slug=slugify_name(name)),
            emails=EMAIL_ADDRESS.format(slug=email_local_part(name)),
        )
        assert resource is not None, f'duplicate resource name {name!r}'
        resource['tags'] = [role]
        by_role.setdefault(role, []).append(resource['id'])
    return by_role


def pick_team(by_role: dict[str, list[int]], shape_name: str, rng: random.Random):
    """Samples a fixed team for one project - same people for every task
    in it wherever a role needs more than one person, drawn without
    replacement so e.g. Build-A/Build-B in 'medium' land on two
    different developers, matching a team that stays constant."""
    team: dict[str, list[int]] = {}
    for role, count in TEAM_REQS[shape_name].items():
        pool = by_role[role]
        team[role] = rng.sample(pool, k=min(count, len(pool)))
    return team


def build_draft_network(
    model: TaskResourceModel,
    project_id: int,
    shape_name: str,
    team: dict[str, list[int]],
    start_col: int,
    domain: str,
    rng: random.Random,
) -> list[int]:
    """Creates one rolling-wave draft network for `shape_name`, wired
    with real predecessor links and resource assignments. Returns the
    created task ids in shape order (topological, since every shape
    lists a task after all of its own predecessors). `row` is a
    placeholder (0) throughout - the draft is deleted right after
    scheduling, see assign_project_rows() for the rows that matter.

    Each task is tagged with its own role and the project's business
    domain (see PROJECT_DOMAINS) - both survive the delete-and-reschedule
    round trip the same way url does (schedule_project_core carries a
    source task's tags across onto its scheduled replacement), so a
    scheduled project's tasks are already tag-filterable by discipline or
    business area without any further tagging pass."""
    name_to_id: dict[str, int] = {}
    role_cursor: dict[str, int] = {}
    task_ids = []
    col = start_col
    for task_name, role, preds, (dmin, dmax), _lane in PROJECT_SHAPES[shape_name]:
        duration = rng.randint(dmin, dmax)
        pool = team[role]
        idx = role_cursor.get(role, 0) % len(pool)
        role_cursor[role] = role_cursor.get(role, 0) + 1
        resource_id = pool[idx]

        task = model.add_task(
            row=0,
            col=col,
            duration=duration,
            description=task_name,
            resources={resource_id: 1.0},
            predecessors=[{'id': name_to_id[p], 'type': 'FS', 'lag': 0} for p in preds],
            color=ROLE_COLOR[role],
            project_id=project_id,
            tags=[role, domain],
        )
        # Set post-creation (task_id isn't known until add_task returns) -
        # this url string survives the draft's own delete-and-reschedule
        # round trip (schedule_project_core exports it to the scheduler's
        # own tasks.csv format and imports it straight back onto the new
        # scheduled task), so this is the *only* place a mini-project
        # task's url needs to be set, even though the object it's set on
        # here gets thrown away.
        task['url'] = TRACKER_URL.format(n=task['task_id'])
        name_to_id[task_name] = task['task_id']
        task_ids.append(task['task_id'])
        col += duration + 1

    return task_ids


# At least this many blank rows between two projects that are actually
# concurrent (their blocks would otherwise sit directly against each
# other) - room to add a task or two mid-execution without immediately
# encroaching on whichever project happens to be stacked next to it, and
# a clearer visual break when a team's own project needs picking out
# from neighbours that are also currently in execution.
ROW_GAP = 3

# A little breathing room below the very last row a task actually uses,
# once the grid gets grown to fit at main()'s end - see the comment
# there for why the grid can otherwise end up too short in the first
# place (build_backlog's per-resource lanes are the usual culprit).
GRID_ROW_MARGIN = 2


def pack_rows(
    row_occupied: dict[int, list[tuple[int, int]]],
    lanes_needed: int,
    span_start: int,
    span_end: int,
) -> list[int]:
    """First-fit packing: finds `lanes_needed` consecutive rows all free
    across [span_start, span_end), reusing rows once an earlier
    project's block has finished there rather than growing the row
    count with every new project - keeps every project's own footprint
    compact *and* keeps the whole mini-project region reasonably small,
    since the backlog's own rows start right below wherever this ends up
    finishing (see main()'s backlog_row_start).

    Reserves ROW_GAP rows of padding above and below the block, for the
    same span, so a *concurrent* project's own search skips straight
    past them - the gap only ever costs real row space between projects
    that overlap in time; a later, non-overlapping project is still
    free to reuse exactly these rows once this span has passed."""
    row = 0
    while True:
        candidate = range(row, row + lanes_needed)
        if all(
            all(
                not (span_start < end and start < span_end)
                for start, end in row_occupied[r]
            )
            for r in candidate
        ):
            padded = range(max(0, row - ROW_GAP), row + lanes_needed + ROW_GAP)
            for r in padded:
                row_occupied[r].append((span_start, span_end))
            return list(candidate)
        row += 1


def assign_project_rows(
    model: TaskResourceModel,
    project_id: int,
    shape_name: str,
    row_occupied: dict[int, list[tuple[int, int]]],
    start_col_actual: int,
    end_col_actual: int,
):
    """Places a just-scheduled project's tasks - including its buffers -
    on a compact, adjacent block of rows, instead of the scheduler's own
    _place_beside_source placement (which stacks each newly-scheduled
    project fresh at the bottom of the whole grid, scattering feeding
    buffers far from the chain they protect once several projects have
    been through it). Each buffer is put on the same row as the one
    task it directly follows (every buffer has exactly one predecessor -
    confirmed against real scheduler output), so a project's whole
    picture - main thread, parallel branches, and their buffers - reads
    as one contiguous group."""
    lane_by_name = {
        name: lane for name, _role, _preds, _dur, lane in PROJECT_SHAPES[shape_name]
    }
    lanes_needed = max(lane_by_name.values()) + 1
    block = pack_rows(row_occupied, lanes_needed, start_col_actual, end_col_actual)

    tasks = [t for t in model.tasks if t['project_id'] == project_id]
    row_by_task_id: dict[int, int] = {}
    for task in tasks:
        if task['type'] == 'task':
            row = block[lane_by_name[task['description']]]
            task['row'] = row
            row_by_task_id[task['task_id']] = row
    for task in tasks:
        if task['type'] != 'task':
            predecessor_id = task['predecessors'][0]['id']
            task['row'] = row_by_task_id[predecessor_id]


def record_status(
    model: TaskResourceModel,
    task_ops: TaskOperations,
    task,
    remaining: int,
    reason: str,
):
    """One status-update event: record, cascade, snapshot - mirrors
    TaskOperations.record_remaining_duration's own real flow (task_
    operations.py) minus the dialog, so every recorded remaining-duration
    change also logs a real fever_chart_history point for its project's
    buffers, computed by the same compute_fever_chart_point() the Fever
    Charts report reads - not hand-faked cpsl/ppf/forecast_lateness
    numbers. apply_dependency_cascade must run before the snapshot:
    compute_fever_chart_point reads col/duration off the whole chain, so
    a snapshot taken against pre-cascade positions would be stale."""
    model.record_remaining_duration(task['task_id'], remaining, reason)
    task_ops.apply_dependency_cascade(task)
    model.capture_fever_chart_snapshot(project_id=task['project_id'])


def resource_working(model: TaskResourceModel, task, day: int) -> bool:
    """True only if every resource assigned to `task` has capacity on
    `day` - a task needs everyone it's assigned to actually available,
    not just one of them."""
    for resource_id_str in task['resources']:
        resource = model.get_resource_by_id(int(resource_id_str))
        if resource is None:
            continue
        if day >= len(resource['capacity']) or resource['capacity'][day] <= 0:
            return False
    return True


def next_working_day(model: TaskResourceModel, task, day: int) -> int:
    """First day >= `day` every resource assigned to `task` actually
    works - a plain forward scan, since this file's resources are never
    out for more than a weekend at a time."""
    d = day
    while d < model.days and not resource_working(model, task, d):
        d += 1
    return d


# Full-kit readiness: the rule this models is "a task should only start
# once everything it needs is actually in hand" - missing-but-predictable
# dependencies discovered mid-execution are one of the biggest sources of
# real project delay, which is exactly what the Full-Kit Readiness report
# exists to surface ahead of time. Some tasks only need information
# already known at planning time (agreed requirements, environment,
# deployment runbook) and can - and ideally should - be fully kitted well
# before the project itself starts; QA/ops prep in particular typically
# runs in parallel with build, not after it. Design/build work, by
# contrast, generically needs its own predecessor's actual output (the
# discovery findings, the agreed design) before it can be kitted for real
# - that's the "some successors are on the critical path for information,
# not just for execution" case the report is meant to catch.
FULLKIT_PLANTIME_ROLES = {'ba', 'qa', 'devops'}
# Turnaround after a predecessor's output becomes available before its
# successor's own kit can actually be assembled from it.
FULLKIT_LEAD_DAYS = (1, 5)
# Even once a task's kit realistically COULD be ready, it isn't always -
# the rest are exactly the "still needs more work" tasks a PM needs this
# report to catch before committing to a start date.
FULLKIT_READY_PROBABILITY = 0.8


def clamp_day(model: TaskResourceModel, day: int) -> int:
    return max(0, min(day, model.days - 1))


def simulate_fullkit_task(
    model: TaskResourceModel,
    task,
    target_day: int,
    today_day: int,
    rng: random.Random,
):
    """One task's full-kit outcome. A task that has already actually
    started (see simulate_progress) is retroactively given a fullkit_date
    on or just before its own actual start - it couldn't genuinely have
    started otherwise, whatever `target_day` says. A task that hasn't
    started yet is ready only if `target_day` (the earliest day its kit
    could realistically be complete - see simulate_fullkit/build_backlog
    for how callers compute this) has already passed, and even then only
    with FULLKIT_READY_PROBABILITY."""
    actual_start_date = task.get('actual_start_date')
    if actual_start_date:
        actual_start_day = model.get_day_for_date(
            datetime.fromisoformat(actual_start_date)
        )
        kit_day = clamp_day(model, min(target_day, actual_start_day, today_day))
        model.setdate = model.get_date_for_day(kit_day)
        model.set_fullkit_date(task['task_id'])
        return

    if target_day > today_day:
        return  # not ready yet - still waiting on predecessor info

    if rng.random() < FULLKIT_READY_PROBABILITY:
        kit_day = clamp_day(model, min(target_day, today_day))
        model.setdate = model.get_date_for_day(kit_day)
        model.set_fullkit_date(task['task_id'])


def simulate_fullkit(
    model: TaskResourceModel,
    tasks: list,
    shape_name: str,
    today_day: int,
    rng: random.Random,
):
    """Simulates full-kit prep across one project's whole task set (any
    phase - unlike fever charts, full-kit readiness matters during
    planning too, before a project has even started). See
    FULLKIT_PLANTIME_ROLES for the plan-time-vs-predecessor-output split
    that decides each task's own readiness window."""
    role_by_name = {
        name: role for name, role, _preds, _dur, _lane in PROJECT_SHAPES[shape_name]
    }
    id_to_task = {t['task_id']: t for t in tasks}
    kickoff_day = min(t['col'] for t in tasks if t.get('type') == 'task')

    for task in tasks:
        if task.get('type') != 'task':
            continue
        role = role_by_name[task['description']]

        if role in FULLKIT_PLANTIME_ROLES or not task['predecessors']:
            target_day = kickoff_day - rng.randint(3, 15)
            if target_day > today_day:
                # Kickoff is too far off for this to be "due" yet by that
                # countdown, but this kind of task was never actually
                # gated on the calendar - simulate it having been done at
                # some point during the normal course of planning
                # instead, rather than pinning every far-future project's
                # prep to the same exact today's-date.
                target_day = rng.randint(max(0, today_day - 45), today_day)
        else:
            target_day = 0
            for link in task['predecessors']:
                pred = id_to_task.get(link['id'])
                if pred is None:
                    continue
                pred_end_date = pred.get('actual_end_date')
                if pred_end_date:
                    pred_end_day = model.get_day_for_date(
                        datetime.fromisoformat(pred_end_date)
                    )
                else:
                    pred_end_day = pred['col'] + pred['duration']
                target_day = max(target_day, pred_end_day)
            target_day += rng.randint(*FULLKIT_LEAD_DAYS)

        simulate_fullkit_task(model, task, target_day, today_day, rng)


# CCPM strips safety out of individual task estimates and pools it in the
# project/feeding buffers instead - task['duration'] here is already that
# stripped-down, "50% confidence" figure, so a task is BY DESIGN expected
# to often run past its own estimate (Parkinson's Law/Student Syndrome);
# that overrun is exactly what the buffers exist to absorb. Weighted
# outcome buckets, each (weight, duration_factor_range, reason) - reason
# correlated with the outcome instead of drawn independently, so e.g. a
# task that ran 80% over doesn't get logged as 'On Time'. Skews right
# (most weight at/above 1.0x) rather than symmetric around 1.0, matching
# that skew.
TASK_OUTCOME_PROFILES = [
    (12, (0.6, 0.9), 'On Time'),
    (18, (0.9, 1.05), 'On Time'),
    (25, (1.05, 1.3), 'Task Variability'),
    (15, (1.1, 1.4), 'Multitasking'),
    (12, (1.2, 1.6), 'Waiting for Resource'),
    (10, (1.3, 1.9), "Parkinson's Law"),
    (5, (1.5, 2.3), 'Unplanned Events'),
    (3, (1.2, 2.0), 'Other / Unexplained'),
]

# A project buffer protects a whole critical chain, so by the law of large
# numbers its average consumption tends to land well under 100% even with
# every task individually running long - the averaging effect cancels out
# most of the noise. Real project buffers DO occasionally get fully
# exhausted, but that's usually a correlated, project-wide event (a key
# person got pulled away, requirements churned across the whole scope, a
# vendor problem hit every downstream task) rather than every task
# independently rolling bad luck - so a minority of projects are marked
# "troubled" up front and get every task's outcome factor amplified,
# instead of uniformly cranking the noise for every project.
TROUBLED_PROJECT_PROBABILITY = 0.22
TROUBLED_PROJECT_SEVERITY = 1.35


def sample_task_outcome(
    duration: int, rng: random.Random, severity: float = 1.0
) -> tuple[int, str]:
    """How long a task actually takes once real-world variability plays
    out, plus the reason that goes with it. See TASK_OUTCOME_PROFILES.
    `severity` amplifies the sampled factor - see TROUBLED_PROJECT_*."""
    weights = [profile[0] for profile in TASK_OUTCOME_PROFILES]
    _, (lo, hi), reason = rng.choices(TASK_OUTCOME_PROFILES, weights=weights, k=1)[0]
    factor = rng.uniform(lo, hi) * severity
    actual_duration = max(1, round(duration * factor))
    return actual_duration, reason


# -- task notes ----------------------------------------------------------
# Free-text, timestamped commentary (task['notes'] - distinct from the
# reason/note pair record_remaining_duration logs to remaining_duration_
# history) that the Add Task Note dialog writes, and that the Resource
# Schedule report's "Include task notes" option reads. Not every task gets
# one - a demo file wants a realistic, occasional scattering, the same way
# a real team doesn't narrate every single task.
#
# model.add_note_to_task() (task_resource_model.py) always stamps real
# wall-clock time - correct for a live user typing a note right now, wrong
# for this generator's backdated history - so notes are appended directly
# below with a timestamp keyed off the simulated day (the same
# model.get_date_for_day(day) conversion record_status's model.setdate
# assignments already use), not add_note_to_task() itself.

START_NOTE_PROBABILITY = 0.15
OUTCOME_NOTE_PROBABILITY = 0.30
TROUBLED_OUTCOME_NOTE_PROBABILITY = 0.55

START_NOTE_TEMPLATES = [
    'Kicked off - team is up to speed on scope.',
    'Underway - nothing blocking at the outset.',
    'Picking this up now, dependencies look clear.',
]
DELAYED_START_NOTE_TEMPLATES = [
    "Starting later than planned - resourcing wasn't free until now.",
    "Slipped the planned start, waiting on the assigned person's availability.",
]

# Keyed by the same reason strings as TASK_OUTCOME_PROFILES, so a note
# always elaborates on the exact reason record_status just logged rather
# than risking a mismatched narrative. {project}/{name} are filled from
# the roster/portfolio at random - close enough for a demo file without
# threading the *actual* other-project/other-person through every caller.
OUTCOME_NOTE_TEMPLATES = {
    'On Time': [
        'Went smoothly, no surprises.',
        'Straightforward once we got into it.',
    ],
    'Task Variability': [
        'Took longer than the estimate once we hit the edge cases.',
        'Scope was fuzzier than assumed going in.',
    ],
    'Multitasking': [
        'Kept getting pulled onto {project} in parallel - lost time to '
        'context switching.',
        'Split attention with another commitment this week.',
    ],
    'Waiting for Resource': [
        'Blocked for a couple of days waiting on {name} to free up.',
        'Had to wait on environment/access before this could really start.',
    ],
    "Parkinson's Law": [
        'Ran right up to the wire - probably could have been tighter.',
        'Stretched to fill the time available.',
    ],
    'Unplanned Events': [
        'Production incident pulled the team off this for a day.',
        'An unrelated dependency surfaced mid-task.',
    ],
    'Other / Unexplained': [
        'Not entirely sure why this slipped - worth a look in retro.',
    ],
}


def add_backdated_note(model: TaskResourceModel, task, day: int, text: str) -> None:
    """Appends a note stamped with the simulated `day` rather than real
    wall-clock time - see the module comment above for why this can't
    just call model.add_note_to_task()."""
    task.setdefault('notes', []).append(
        {'timestamp': model.get_date_for_day(day).isoformat(), 'text': text}
    )


def maybe_add_progress_notes(
    model: TaskResourceModel,
    task,
    actual_start: int,
    outcome_day: int,
    outcome_reason: str,
    delayed: bool,
    severity: float,
    rng: random.Random,
) -> None:
    """Probabilistically logs a start note (at actual_start) and/or an
    outcome note (at outcome_day) against `task`, so a demo of the
    Resource Schedule report's "Include task notes" option - and of a
    task carrying more than one timestamped note - doesn't need every
    note added by hand. Troubled projects (see TROUBLED_PROJECT_*) get
    more to say, hence the higher outcome-note probability."""
    if rng.random() < START_NOTE_PROBABILITY:
        pool = DELAYED_START_NOTE_TEMPLATES if delayed else START_NOTE_TEMPLATES
        add_backdated_note(model, task, actual_start, rng.choice(pool))

    outcome_probability = (
        TROUBLED_OUTCOME_NOTE_PROBABILITY
        if severity > 1.0
        else OUTCOME_NOTE_PROBABILITY
    )
    if rng.random() < outcome_probability:
        template = rng.choice(OUTCOME_NOTE_TEMPLATES[outcome_reason])
        text = template.format(
            project=rng.choice(PROJECT_NAMES), name=rng.choice(ROSTER)[0]
        )
        add_backdated_note(model, task, outcome_day, text)


def simulate_progress(
    model: TaskResourceModel,
    task_ops: TaskOperations,
    task,
    today_day: int,
    rng: random.Random,
    severity: float = 1.0,
):
    """Backdates a task's own start/finish against `model.setdate` so it
    looks genuinely worked on rather than just sitting in 'planning',
    logging a fever chart point at each status update along the way (see
    record_status). Only ordinary tasks are touched - fever_chart_history
    lives on buffer tasks, but capture_fever_chart_snapshot() finds and
    updates those on its own; there's nothing to backdate on a buffer
    task directly.

    `task['col']` here is wherever the relay-runner cascade last pulled
    or pushed it to (task_operations.py's apply_dependency_cascade,
    deliberately left as-is - pulling the next task forward the instant
    a predecessor finishes early is exactly the intended behaviour) -
    that day isn't guaranteed to be one every assigned resource actually
    works. Rather than always start right on that cascaded day
    regardless, this splits it: about half the time the resource works
    it anyway (expediting a critical task, or just incentivised to), the
    other half they wait for their own next working day instead - which
    is what actually opens a gap in an otherwise tight chain, and (via
    record_status's real apply_dependency_cascade call) ripples forward
    onto whatever comes next, the same way a real delayed status update
    would.

    The task's own ACTUAL duration (see sample_task_outcome) is likewise
    deliberately not always task['duration'] itself - that figure is
    already the CCPM-stripped, safety-free estimate, so realistically
    simulating "the safety now lives in the buffers, not the tasks"
    means letting a good fraction of tasks genuinely run long, which then
    ripples through the same cascade and is exactly what should show up
    consuming project/feeding buffer in the fever charts."""
    if task.get('type') != 'task':
        return

    planned_start = task['col']
    actual_start = planned_start
    if not resource_working(model, task, planned_start) and rng.random() < 0.5:
        actual_start = next_working_day(model, task, planned_start)
    delayed = actual_start != planned_start
    start_reason = 'Waiting for Resource' if delayed else 'On Time'

    duration = task['duration']
    actual_duration, outcome_reason = sample_task_outcome(duration, rng, severity)
    actual_end = actual_start + actual_duration

    if actual_end <= today_day:
        # Finished (with realistic variance) entirely in the past.
        model.setdate = model.get_date_for_day(actual_start)
        record_status(model, task_ops, task, duration, start_reason)
        model.setdate = model.get_date_for_day(actual_end)
        record_status(model, task_ops, task, 0, outcome_reason)
        maybe_add_progress_notes(
            model,
            task,
            actual_start,
            actual_end,
            outcome_reason,
            delayed,
            severity,
            rng,
        )
    elif actual_start < today_day < actual_end:
        # Genuinely in progress right now.
        model.setdate = model.get_date_for_day(actual_start)
        record_status(model, task_ops, task, duration, start_reason)
        model.setdate = model.get_date_for_day(today_day)
        remaining = max(1, actual_end - today_day)
        record_status(model, task_ops, task, remaining, outcome_reason)
        maybe_add_progress_notes(
            model, task, actual_start, today_day, outcome_reason, delayed, severity, rng
        )
    # else: starts in the future - stays untouched in 'planning'.


# Only meaningful once a project has real scheduler output to draw on
# (chain_id/is_critical), so this is a separate pass from the role/domain
# tags build_draft_network sets at draft time - see
# apply_schedule_based_tags.
AT_RISK_TAG_PROBABILITY = 0.4


def apply_schedule_based_tags(
    model: TaskResourceModel,
    scheduled_tasks: list,
    troubled: bool,
    rng: random.Random,
) -> None:
    """Two more tag dimensions, on top of the role/domain tags
    build_draft_network already set, that only exist once real scheduler
    output does: 'critical-chain' for every task on the project's
    critical chain (CCPM's own term for it, and a genuine cross-portfolio
    "show me only critical-chain work" filter - the Critical chain's own
    colour is only ever a per-project visual cue, not something the task
    grid can filter by across several projects at once), and - on a
    random subset of a troubled project's tasks, not the whole project -
    'at-risk', so filtering by it actually narrows things down rather
    than just restating "this project is troubled" on every one of its
    rows."""
    for task in scheduled_tasks:
        if task.get('type') != 'task':
            continue
        chain = model.get_chain_by_id(task.get('chain_id'))
        if chain and chain.get('is_critical'):
            model.add_tags_to_task(task['task_id'], ['critical-chain'])
        if troubled and rng.random() < AT_RISK_TAG_PROBABILITY:
            model.add_tags_to_task(task['task_id'], ['at-risk'])


def build_mini_project(
    model: TaskResourceModel,
    ccpm_ops: CcpmOperations,
    task_ops: TaskOperations,
    name: str,
    shape_name: str,
    by_role: dict[str, list[int]],
    row_occupied: dict[int, list[tuple[int, int]]],
    start_col: int,
    today_day: int,
    rng: random.Random,
) -> str:
    """Builds, schedules, and (if its timing calls for it) backdates one
    mini-project. Returns a one-line classification for the summary
    printed at the end."""
    draft_name = f'{name} (draft)'
    draft = model.add_project(draft_name)
    assert draft is not None, f'duplicate project name {draft_name!r}'
    team = pick_team(by_role, shape_name, rng)
    draft_task_ids = build_draft_network(
        model, draft['id'], shape_name, team, start_col, PROJECT_DOMAINS[name], rng
    )

    result = ccpm_ops.schedule_project_core(draft['id'], new_project_name=name)
    assert result['ok'], f'{name}: CCPM scheduling failed: {result["issues"]}'

    for task_id in draft_task_ids:
        model.delete_task(task_id)
    model.remove_project(draft['id'])

    scheduled = result['project']
    scheduled_tasks = [t for t in model.tasks if t['project_id'] == scheduled['id']]
    start_col_actual = min(t['col'] for t in scheduled_tasks)
    end_col_actual = max(t['col'] + t['duration'] for t in scheduled_tasks)
    assign_project_rows(
        model,
        scheduled['id'],
        shape_name,
        row_occupied,
        start_col_actual,
        end_col_actual,
    )

    if end_col_actual <= today_day:
        status = 'completed'
    elif start_col_actual > today_day:
        status = 'future'
    else:
        status = 'ongoing'

    troubled = status != 'future' and rng.random() < TROUBLED_PROJECT_PROBABILITY
    severity = TROUBLED_PROJECT_SEVERITY if troubled else 1.0

    apply_schedule_based_tags(model, scheduled_tasks, troubled, rng)

    if status != 'future':
        model.setdate = model.get_date_for_day(max(0, start_col_actual - 1))
        model.capture_project_baseline(scheduled['id'])
        model.set_project_phase(scheduled['id'], 'execution')
        for task in scheduled_tasks:
            simulate_progress(model, task_ops, task, today_day, rng, severity)

    simulate_fullkit(model, scheduled_tasks, shape_name, today_day, rng)

    span_days = end_col_actual - start_col_actual
    stats = result['stats']
    flag = ' [troubled]' if troubled else ''
    print(
        f'  [{status:>9}] {name:<28} shape={shape_name:<6} '
        f'{len(scheduled_tasks):>2} rows  span={span_days:>3}d  '
        f'critical_chain={stats.critical_chain_length}d  '
        f'buffer={stats.project_buffer}d{flag}'
    )
    return status


BACKLOG_TASK_NAMES = [
    'Fix broken report export',
    'Update supplier price list',
    'Investigate slow query',
    'Patch security advisory',
    'Rebuild stale cache',
    'Draft Q3 status update',
    'Reconcile ledger discrepancy',
    'Answer customer escalation',
    'Rotate API keys',
    'Clean up test data',
    'Review access request',
    'Update runbook',
    'Triage incoming defects',
    'Refresh dashboard widget',
    'Archive old records',
    'Validate backup restore',
    'Adjust alert thresholds',
    'Prepare audit evidence',
    'Onboard new vendor feed',
    'Correct mislabeled SKUs',
    'Tune batch job schedule',
    'Respond to compliance query',
    'Update training material',
    'Retire legacy endpoint',
    'Investigate payment mismatch',
    'Support store rollout',
    'Clarify requirements',
    'Review pull request backlog',
    'Update data dictionary',
    'Handle GDPR request',
]
BACKLOG_PRIORITIES = ['P1', 'P2', 'P3']


def build_backlog(
    model: TaskResourceModel,
    task_ops: TaskOperations,
    by_role: dict[str, list[int]],
    row_by_resource: dict[int, int],
    backlog_row_start: int,
    window_days: int,
    today_day: int,
    rng: random.Random,
    task_count: int,
) -> int:
    """One never-CCPM-scheduled project of small, independent tasks -
    the prioritised backlog work pulled off ad hoc between mini-project
    commitments (no established convention for this in the codebase, see
    CLAUDE.md/docs check during research - a plain project that's simply
    never scheduled is enough)."""
    project = model.add_project('Ad-hoc / Backlog Work')
    assert project is not None
    all_resource_ids = [rid for ids in by_role.values() for rid in ids]

    for i in range(task_count):
        name = rng.choice(BACKLOG_TASK_NAMES)
        priority = rng.choices(BACKLOG_PRIORITIES, weights=[2, 5, 3], k=1)[0]
        duration = rng.randint(1, 3)
        col = rng.randint(0, max(1, window_days - duration - 1))
        resource_id = rng.choice(all_resource_ids)

        task = model.add_task(
            row=backlog_row_start + row_by_resource[resource_id],
            col=col,
            duration=duration,
            description=f'{name} #{i + 1}',
            resources={resource_id: 1.0},
            tags=['backlog', priority],
            color=BACKLOG_COLOR,
            project_id=project['id'],
        )
        # Ad hoc work doesn't always have a ticket raised for it yet - most
        # does, some doesn't, so the sample file exercises both the
        # hyperlinked and the plain-text task rendering side by side.
        if rng.random() < 0.75:
            task['url'] = TRACKER_URL.format(n=task['task_id'])
        simulate_progress(model, task_ops, task, today_day, rng)
        # No dependency chain to gate on for an ad hoc backlog item - it's
        # available to kit as soon as it's flagged.
        simulate_fullkit_task(model, task, 0, today_day, rng)

    return len(model.tasks)


def main():
    rng = random.Random(RNG_SEED)
    model = TaskResourceModel()

    # Strip the model's own seeded defaults (10 default resources, one
    # default project) - this file builds its own roster from scratch.
    model.resources = []
    model.resource_id_counter = 0
    model.projects = []
    model.project_id_counter = 0
    model.default_project_id = None

    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    window_start = today - timedelta(days=PAST_DAYS)
    window_days = PAST_DAYS + FUTURE_DAYS + DAYS_MARGIN

    model.start_date = window_start
    model.days = window_days
    model.setdate = today

    by_role = build_roster(model)
    # capacity arrays are sized off model.days at add_resource() time -
    # re-seed them now that model.days reflects the real window, not the
    # constructor's default 100.
    for resource in model.resources:
        role = resource['tags'][0]
        weekends = working_capacity(role)
        capacity = []
        for day in range(model.days):
            date = model.get_date_for_day(day)
            capacity.append(0.0 if (date.weekday() >= 5 and not weekends) else 1.0)
        resource['capacity'] = capacity

    # Used only for the backlog's per-person lanes below backlog_row_start
    # - mini-project rows are packed fresh per project, see pack_rows().
    row_by_resource = {
        rid: i for i, rid in enumerate(rid for ids in by_role.values() for rid in ids)
    }
    row_occupied: dict[int, list[tuple[int, int]]] = defaultdict(list)

    today_day = model.get_day_for_date(today)
    print(
        f'Window: {window_start.date()} .. {(window_start + timedelta(days=window_days)).date()}'
        f'  (today = day {today_day} of {model.days})'
    )

    controller = MagicMock()
    controller.model = model
    ccpm_ops = CcpmOperations(controller, model)
    task_ops = TaskOperations(controller, model)

    # Stagger project starts across the window, evenly spaced with
    # jitter, so several are in flight (and overlapping in team members)
    # at any given point, the way a ~30-person org actually runs.
    n_projects = len(PROJECT_NAMES)
    span = PAST_DAYS + FUTURE_DAYS - 10
    step = span / n_projects
    shape_choices = ['small'] * 6 + ['medium'] * 8 + ['large'] * 4
    rng.shuffle(shape_choices)

    print(f'\nBuilding {n_projects} mini-projects...')
    counts = {'completed': 0, 'ongoing': 0, 'future': 0}
    for i, name in enumerate(PROJECT_NAMES):
        start_col = int(i * step + rng.randint(-3, 3))
        start_col = max(0, start_col)
        status = build_mini_project(
            model,
            ccpm_ops,
            task_ops,
            name,
            shape_choices[i],
            by_role,
            row_occupied,
            start_col,
            today_day,
            rng,
        )
        counts[status] += 1

    # row_occupied's own keys already include each project's trailing
    # ROW_GAP padding (pack_rows reserves it on both sides of every
    # block), so starting the backlog lanes right after the highest
    # occupied row keeps the same >= ROW_GAP separation from mini-project
    # work without stacking a second gap on top of it.
    max_project_row = max(row_occupied) if row_occupied else -1
    backlog_row_start = max_project_row + 1
    print(
        f'Mini-project rows used: 0..{max_project_row} (backlog starts at {backlog_row_start})'
    )

    print(f'\nMini-projects: {counts}')

    # Roughly a quarter of all work at any point in time is ad hoc -
    # sized relative to the mini-project task volume just built.
    mini_project_task_count = sum(1 for t in model.tasks if t.get('type') == 'task')
    backlog_target = max(40, mini_project_task_count // 3)
    print(f'\nBuilding {backlog_target} backlog tasks...')
    build_backlog(
        model,
        task_ops,
        by_role,
        row_by_resource,
        backlog_row_start,
        window_days,
        today_day,
        rng,
        backlog_target,
    )

    # The app's own simulated "today" - reset after all the backdating
    # above, which moved model.setdate around a lot.
    model.setdate = today

    # The task grid only ever scrolls to model.max_rows (task_manager.py/
    # ui_components.py size the canvas off it directly) - a task whose row
    # lands at or past it is placed but permanently unreachable, off the
    # bottom of the grid. build_backlog's per-resource lanes are the usual
    # culprit: backlog_row_start + row_by_resource[resource_id] can run
    # past max_rows once enough mini-projects have pushed the backlog's
    # starting row down, and nothing upstream caps it against the grid's
    # own size. Grow the grid to fit instead of just hoping it already
    # does, then check it actually worked before trusting the save.
    if model.tasks:
        max_task_row = max(t['row'] for t in model.tasks)
        required_rows = max_task_row + 1 + GRID_ROW_MARGIN
        if required_rows > model.max_rows:
            print(
                f'\nGrid grown from {model.max_rows} to {required_rows} rows '
                f'(highest task row used: {max_task_row})'
            )
            model.max_rows = required_rows

    off_grid = [t for t in model.tasks if t['row'] >= model.max_rows]
    assert not off_grid, (
        f'{len(off_grid)} task(s) still off the bottom of the grid '
        f'(max_rows={model.max_rows}): '
        f'{[(t["task_id"], t["description"], t["row"]) for t in off_grid]}'
    )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ok = model.save_to_file(str(OUTPUT_PATH))
    assert ok, 'save_to_file failed'

    task_count = len(model.tasks)
    buffer_count = sum(1 for t in model.tasks if t.get('type') != 'task')
    note_count = sum(len(t.get('notes', [])) for t in model.tasks)
    noted_task_count = sum(1 for t in model.tasks if t.get('notes'))
    tagged_task_count = sum(1 for t in model.tasks if t.get('tags'))
    print(
        f'\nSaved {OUTPUT_PATH} - {len(model.projects)} projects, '
        f'{task_count} tasks ({buffer_count} buffers), '
        f'{len(model.resources)} resources, '
        f'{note_count} notes on {noted_task_count} tasks, '
        f'{tagged_task_count} tasks tagged ({len(model.all_tags)} distinct tags), '
        f'grid rows 0..{model.max_rows - 1}.'
    )


if __name__ == '__main__':
    main()
