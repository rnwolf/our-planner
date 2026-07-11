#!/usr/bin/env python3
"""Stage 12 hand-verification walkthrough.

Builds a small CCPM scenario and then steps through it one status update at
a time, printing every tracked buffer's CPSL/PPF/Progress %/Consumption %/
Zone after each step - the same "hand-verify a scenario day-by-day before
writing a permanent pytest test" methodology used for Stage 15 (see
planning.md), applied to what Stage 12 still needs: a longer multi-update
narrative, a feeding buffer fully consumed with overflow onto the critical
chain (Stage 7's push side), and cross-project isolation checked at every
step, not just once.

This script is headless - it does NOT launch the GUI app. It drives the
same model/operations methods the app's dialogs call internally. To
cross-check its numbers against the real app:

1. Run this script once - it saves the Day 0 starting scenario to
   `scripts/stage12_scenario.json` (override with --save-scenario PATH).
2. In the running app: File > Open... that file. Both projects, chains,
   tasks, links, and baselines will be there exactly as built here.
3. Run this script again (or continue an already-running one) and follow
   the "MANUAL STEPS" printed before each step's computed report to
   reproduce that exact status update by hand (Date menu > Set Current
   Date..., then right-click the task > Record Remaining Duration...).
4. Compare what the app's Reports > Project Fever Charts... dialog shows
   against this script's printed CPSL/PPF/Progress %/Consumption %/Zone.

Usage:
    uv run python scripts/stage12_walkthrough.py            # pause after each step
    uv run python scripts/stage12_walkthrough.py --auto      # run straight through, no pauses
    uv run python scripts/stage12_walkthrough.py --step 3    # run steps 1..3 and stop

Once the numbers at each step have been eyeballed and agreed, the same
scenario/steps should be turned into permanent assertions in
tests/test_fever_charts_narrative.py (or wherever Stage 12's pytest test
ends up living) - this script is the scratch tool for getting there, not a
replacement for that test.
"""
import argparse
import sys
from datetime import timedelta
from unittest.mock import MagicMock

from src.model.task_resource_model import (
    TaskResourceModel,
    classify_fever_chart_zone,
    fever_chart_display_point,
)
from src.operations.task_operations import TaskOperations

DEFAULT_SCENARIO_PATH = 'scripts/stage12_scenario.json'


def build_scenario():
    """Critical chain C1->C2->C3->PB (project buffer), a feeding chain
    F1->FB merging into C2, and an untouched Control project for
    cross-project isolation checks."""
    model = TaskResourceModel()
    model.setdate = model.start_date

    controller = MagicMock()
    controller.model = model
    task_ops = TaskOperations(controller, model)

    # TaskResourceModel() always seeds an empty default "Sample Project" -
    # drop it so the saved scenario file only contains what this script
    # actually built (clutter-free when opened in the real app).
    model.remove_project(model.projects[0]['id'])

    project = model.add_project('Stage12 Demo')
    pid = project['id']
    critical = model.get_chain_by_name('Critical')
    feeding = model.get_chain_by_name('Feeding-01')

    c1 = model.add_task(row=0, col=0, duration=5, description='C1', project_id=pid, chain_id=critical['id'])
    f1 = model.add_task(row=1, col=0, duration=3, description='F1', project_id=pid, chain_id=feeding['id'])
    fb = model.add_task(row=2, col=3, duration=5, description='FB', project_id=pid, chain_id=feeding['id'])
    fb['type'] = 'feeding_buffer'
    fb['color'] = 'Salmon'
    c2 = model.add_task(row=0, col=8, duration=5, description='C2', project_id=pid, chain_id=critical['id'])
    c3 = model.add_task(row=0, col=13, duration=5, description='C3', project_id=pid, chain_id=critical['id'])
    pb = model.add_task(row=0, col=18, duration=8, description='PB', project_id=pid, chain_id=critical['id'])
    pb['type'] = 'project_buffer'
    pb['color'] = 'Plum'

    model.add_predecessor(fb['task_id'], f1['task_id'], 'FS')
    model.add_predecessor(c2['task_id'], c1['task_id'], 'FS')
    model.add_predecessor(c2['task_id'], fb['task_id'], 'FB')
    model.add_predecessor(c3['task_id'], c2['task_id'], 'FS')
    model.add_predecessor(pb['task_id'], c3['task_id'], 'PB')

    # Untouched control project - a status update in the demo project above
    # must never move anything here. Deliberately NOT using the 'Critical'
    # chain here - chains are a single global registry shared across every
    # project (only one chain is ever flagged is_critical model-wide), so
    # reusing 'Critical' would make these tasks display with the same
    # chain color/label as Stage12 Demo's real critical chain, even though
    # they belong to a different, unconnected project. Using a Feeding
    # chain instead keeps it visually obvious this is an unrelated project,
    # not "a second critical chain".
    control_project = model.add_project('Control')
    cpid = control_project['id']
    ctrl_chain = model.get_chain_by_name('Feeding-02')
    x1 = model.add_task(row=5, col=0, duration=4, description='X1', project_id=cpid, chain_id=ctrl_chain['id'])
    ctrl_pb = model.add_task(row=5, col=4, duration=6, description='Control PB', project_id=cpid, chain_id=ctrl_chain['id'])
    ctrl_pb['type'] = 'project_buffer'
    ctrl_pb['color'] = 'Plum'
    model.add_predecessor(ctrl_pb['task_id'], x1['task_id'], 'PB')

    model.capture_project_baseline(pid)
    model.set_project_phase(pid, 'execution')
    model.capture_project_baseline(cpid)
    model.set_project_phase(cpid, 'execution')
    model.capture_fever_chart_snapshot()  # day-0 point for every buffer

    tasks = {
        'C1': c1, 'F1': f1, 'FB': fb, 'C2': c2, 'C3': c3, 'PB': pb,
        'X1': x1, 'Control PB': ctrl_pb,
    }
    return model, task_ops, project, control_project, tasks


def record_status(model, task_ops, project_id, day, task, remaining):
    """The status-update flow: advance to the simulated day, record, cascade,
    snapshot - mirrors record_remaining_duration in task_operations, minus
    the dialog. Advancing setdate matters: model.record_remaining_duration
    anchors a task's *first* recorded position to setdate's day-column, so
    every step needs to run "on" the day it claims to."""
    model.setdate = model.start_date + timedelta(days=day)
    model.record_remaining_duration(task['task_id'], remaining)
    task_ops.apply_dependency_cascade(task)
    model.capture_fever_chart_snapshot(project_id=project_id)


def print_manual_steps(model, day, task, remaining):
    """What to click in the real, running app to reproduce this exact step
    by hand - the Date menu sets `setdate`, then the task's own context menu
    records the remaining duration. Mirrors task_operations.py's
    record_remaining_duration dialog flow exactly."""
    date_str = (model.start_date + timedelta(days=day)).strftime('%Y-%m-%d')
    already_started = bool(task.get('actual_start_date'))
    print('  MANUAL STEPS in the running app:')
    print(f"    1. Date menu -> Set Current Date... -> set to {date_str}")
    print(f"    2. Right-click '{task['description']}' -> Record Remaining Duration...")
    print(f"    3. Enter {remaining} in the 'Remaining Duration' prompt and confirm")
    if not already_started:
        print(
            "       (first time this task has been updated - the app will warn "
            "it's about to mark the task started on this date)"
        )


def explain_progress_frontier(model, buffer_task):
    """Print the exact PPF/CPSL/Progress % working for one buffer, walking
    the same chain-tasks-sorted-by-finish logic compute_fever_chart_point
    uses - the point being made explicit: PPF only credits a task's span
    once it's actually marked done (state == 'done'), no matter how settled
    or well-forecast an unfinished task's position looks."""
    terminal_task = model.get_buffer_terminal_task(buffer_task['task_id'])
    chain_tasks = sorted(
        model.get_chain_tasks(terminal_task.get('chain_id'), terminal_task.get('project_id')),
        key=lambda t: t['col'],
    )
    chain_start = min(t['col'] for t in chain_tasks)

    print(f"\n  How Progress % was calculated for {buffer_task['description']}:")
    print(f"    Chain tasks (by start): {[t['description'] for t in chain_tasks]}")
    print(f"    chain_start = min(col) = {chain_start}")

    frontier = chain_start
    print('    Frontier walk (same tasks, sorted by FINISH instead):')
    for task in sorted(chain_tasks, key=lambda t: t['col'] + t['duration']):
        finish = task['col'] + task['duration']
        done = task.get('state') == 'done'
        if done:
            frontier = max(frontier, finish)
            print(f"      {task['description']}: finish={finish}, done -> frontier advances to {frontier}")
        else:
            print(
                f"      {task['description']}: finish={finish}, NOT done -> STOP "
                '(only a completed task can push the frontier forward, regardless '
                "of how confident that task's own forecast position looks)"
            )
            break

    ppf = frontier - chain_start
    forecast_finish = terminal_task['col'] + terminal_task['duration']
    cpsl = forecast_finish - chain_start
    progress_pct = (ppf / cpsl * 100) if cpsl > 0 else 0.0

    print(f'    PPF = frontier - chain_start = {frontier} - {chain_start} = {ppf}')
    print(
        f"    CPSL = {terminal_task['description']}'s forecast finish - chain_start "
        f'= {forecast_finish} - {chain_start} = {cpsl}'
    )
    print(f'    Progress % = PPF / CPSL = {ppf}/{cpsl} = {progress_pct:.1f}%')


def explain_consumption(model, buffer_task):
    """Print the exact forecast-lateness/Consumption % working for one
    buffer - a Feeding Buffer's formula (baseline - live + overflow) differs
    from a Project Buffer's (forecast finish - baseline finish), see
    compute_fever_chart_point in the model; this makes both explicit with
    this scenario's actual numbers rather than leaving the arithmetic to
    trust."""
    baseline = buffer_task.get('baseline')
    baseline_duration = baseline['duration'] if baseline else buffer_task['duration']
    live_duration = buffer_task['duration']

    print(f"\n  How Consumption % was calculated for {buffer_task['description']}:")
    print(f'    Baseline buffer size = {baseline_duration} days (the insurance agreed at baseline capture)')
    print(f'    Live buffer size now = {live_duration} days')

    if buffer_task.get('type') == 'feeding_buffer':
        merge_task = model.get_buffer_merge_task(buffer_task['task_id'])
        overflow = 0
        if merge_task:
            merge_baseline = merge_task.get('baseline')
            if merge_baseline:
                overflow = max(0, merge_task['col'] - merge_baseline['col'])
                print(
                    f"    Merge point ({merge_task['description']}) baseline start = "
                    f"{merge_baseline['col']}, current start = {merge_task['col']}"
                )
                print(
                    f"    Overflow past baseline merge point = max(0, "
                    f"{merge_task['col']} - {merge_baseline['col']}) = {overflow}"
                )
        forecast_lateness = baseline_duration - live_duration + overflow
        print(
            '    Forecast lateness = baseline - live + overflow = '
            f'{baseline_duration} - {live_duration} + {overflow} = {forecast_lateness}'
        )
        print(
            '    (a Feeding Buffer measures how much of the agreed protection is '
            "no longer available - whichever side the shock came from, push (the "
            'feeding chain slipping into it) or pull (the merge point being '
            "dragged earlier) - it's the same formula either way, Stage 15)"
        )
    else:
        terminal_task = model.get_buffer_terminal_task(buffer_task['task_id'])
        terminal_baseline = terminal_task.get('baseline')
        if terminal_baseline:
            baseline_finish = terminal_baseline['col'] + terminal_baseline['duration']
        else:
            baseline_finish = terminal_task['col'] + terminal_task['duration']
        forecast_finish = terminal_task['col'] + terminal_task['duration']
        forecast_lateness = forecast_finish - baseline_finish
        print(
            f"    {terminal_task['description']}'s baseline finish = {baseline_finish}, "
            f'current forecast finish = {forecast_finish}'
        )
        print(
            '    Forecast lateness = forecast finish - baseline finish = '
            f'{forecast_finish} - {baseline_finish} = {forecast_lateness}'
        )
        print(
            '    (a Project Buffer just measures how late the terminal task is '
            'forecast to finish against its own baseline - no overflow term, '
            "since there's nothing further downstream on the critical chain to "
            'push past)'
        )

    consumption_pct = (
        (forecast_lateness / baseline_duration * 100) if baseline_duration > 0 else 0.0
    )
    print(
        '    Consumption % = forecast lateness / baseline size = '
        f'{forecast_lateness}/{baseline_duration} = {consumption_pct:.1f}%'
    )


def report(model, project, control_project, tasks, label):
    print(f'\n{"=" * 70}\n{label}\n{"=" * 70}')

    slope = project.get('fever_chart_slope', 0.55)
    yellow = project.get('fever_chart_yellow_intercept', 10.0)
    red = project.get('fever_chart_red_intercept', 27.0)

    def print_buffer(name, task):
        history = task.get('fever_chart_history', [])
        if not history:
            print(f'  {name}: no fever chart history yet')
            return
        entry = history[-1]
        baseline = task.get('baseline')
        baseline_duration = baseline['duration'] if baseline else task['duration']
        progress_pct, consumption_pct = fever_chart_display_point(entry, baseline_duration)
        zone = classify_fever_chart_zone(progress_pct, consumption_pct, slope, yellow, red)
        print(
            f'  {name}: col={task["col"]:>3} duration={task["duration"]:>3} | '
            f'CPSL={entry["cpsl"]:>3} PPF={entry["ppf"]:>3} '
            f'lateness={entry["forecast_lateness"]:>4} | '
            f'Progress={progress_pct:6.1f}%  Consumption={consumption_pct:7.1f}%  Zone={zone}'
        )

    print(f'-- {project["name"]} --')
    for name in ('C1', 'F1', 'FB', 'C2', 'C3', 'PB'):
        task = tasks[name]
        if task.get('type') in ('feeding_buffer', 'project_buffer'):
            print_buffer(name, task)
        else:
            print(f'  {name}: col={task["col"]:>3} duration={task["duration"]:>3}')

    print(f'-- {control_project["name"]} (must never change) --')
    print_buffer('Control PB', tasks['Control PB'])


# Each step is data, not an opaque lambda, so print_manual_steps() can
# describe it generically instead of duplicating the same info in prose.
STEPS = [
    {
        'day': 0, 'task': 'C1', 'remaining': 5,
        'label': 'Day 0 - C1 starts on schedule (remaining=5)',
        'note': (
            "C1's very first status update, recorded on its actual (on-schedule) "
            "start day - anchors actual_start_date/col correctly to day 0. "
            "Mirrors real life: even if you hear about this days later, you set "
            "Current Date back to when the work actually started before "
            "recording it, rather than to today. Skipping this and jumping "
            "straight to a later 'finished' update would collapse C1's anchor "
            "to that later date instead (see the day-5 step below)."
        ),
    },
    {
        'day': 2, 'task': 'F1', 'remaining': 1,
        'label': 'Day 2 - F1 on track (remaining=1)',
        'note': 'Pure "no news" update - nothing should move, FB stays green at 0%.',
    },
    {
        'day': 2, 'task': 'C1', 'remaining': 3,
        'label': 'Day 2 - C1 on track (remaining=3)',
        'note': (
            'A PM reviewing status on day 2 would check both tasks in flight, '
            'not just F1 - this is the same-day check-in for C1 (2 used of 5, '
            'on track, no change expected).'
        ),
    },
    {
        'day': 5, 'task': 'C1', 'remaining': 0,
        'label': 'Day 5 - C1 finishes on time (remaining=0)',
        'note': (
            'C1 (planned finish day 5) finishes exactly on time. Because it was '
            'already anchored to day 0 above, this update keeps its real 5-day '
            'footprint (col=0, duration=5) instead of collapsing to a point at '
            'day 5. The critical chain frontier can now advance past it - first '
            'time Progress % moves off 0% for the project buffer. Watch the '
            'feeding buffer too: pulling the merge point earlier compresses it, '
            'even though this is good news on the critical chain (Stage 15).'
        ),
        'explain_progress': ['PB'],
    },
    {
        'day': 9, 'task': 'F1', 'remaining': 0,
        'label': 'Day 9 - F1 actually finishes 6 days late (remaining=0)',
        'note': (
            "F1 (planned finish day 3) actually finishes on day 9 - a 6-day "
            "slip. FB's 5-day baseline can't absorb that - fully consumed with "
            "1 day of overflow pushed onto the merge point C2 (Stage 7's push "
            "side, the untested half of Stage 12's remaining scope)."
        ),
        'explain_progress': ['FB', 'PB'],
        'explain_consumption': ['FB', 'PB'],
    },
    {
        'day': 9, 'task': 'C2', 'remaining': 5,
        'label': 'Day 9 - routine check-in on C2 (remaining=5, unchanged)',
        'note': (
            'A routine, unrelated on-track check-in on C2 - confirms the merge '
            "point the overflow just pushed doesn't get dragged somewhere else "
            "by an ordinary cascade (Stage 15's max-across-all-paths rule "
            'holding up inside a longer narrative, not just in isolation).'
        ),
    },
    {
        'day': 14, 'task': 'C2', 'remaining': 0,
        'label': 'Day 14 - C2 finishes on time (remaining=0)',
        'note': (
            "C3 is FS-dependent on C2 - in reality, C3 could not have genuinely "
            "started, let alone been reported finished, before C2 was actually "
            "done. This step completes C2 (matching its own day-9 forecast: 5 "
            "remaining then, so finishing exactly on day 14) before C3 is "
            "touched again, so the narrative doesn't imply an impossible task "
            "ordering. Watch how completing C2 shifts the Progress Frontier "
            "forward past its own span too, not just C1's."
        ),
        'explain_progress': ['PB'],
    },
    {
        'day': 16, 'task': 'C3', 'remaining': 4,
        'label': 'Day 16 - C3 reports a 2-day slip (remaining=4)',
        'note': (
            "C3 reports a modest 2-day slip against its baseline finish (day "
            "18) - first sign of trouble for the project buffer."
        ),
        'explain_progress': ['PB'],
        'explain_consumption': ['PB'],
    },
    {
        'day': 22, 'task': 'C3', 'remaining': 0,
        'label': 'Day 22 - C3 finishes, 5 days late overall (remaining=0)',
        'note': (
            "C3 finishes 5 days late in total against its baseline (day 18) - "
            "a bigger bite out of the project buffer. This is the "
            '"trajectory" Stage 12 wants to see: two points on the same '
            "buffer's chart, moving in a worsening direction."
        ),
        'explain_progress': ['PB'],
        'explain_consumption': ['PB'],
    },
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--auto', action='store_true', help='run straight through, no pauses')
    parser.add_argument('--step', type=int, default=len(STEPS), help='stop after this many steps')
    parser.add_argument(
        '--save-scenario', default=DEFAULT_SCENARIO_PATH,
        help=f'where to save the Day 0 scenario for File > Open in the real app (default: {DEFAULT_SCENARIO_PATH})',
    )
    parser.add_argument(
        '--no-save', action='store_true', help="don't write the scenario JSON file",
    )
    args = parser.parse_args()

    model, task_ops, project, control_project, tasks = build_scenario()

    day0_date = model.start_date.strftime('%Y-%m-%d')
    if not args.no_save:
        model.save_to_file(args.save_scenario)
        print(f'Day 0 scenario saved to {args.save_scenario}')
        print(f'  -> In the running app: File > Open... > {args.save_scenario}')
        print(
            f"  -> The current date is already saved as {day0_date} in that file - "
            "no manual date change needed until step 1."
        )

    resourced_tasks = [t for t in model.tasks if t.get('resources')]
    if not resourced_tasks:
        print(
            '  -> No resources are assigned to any task in this scenario - every '
            'delay/slip below comes purely from dependency links and buffer math, '
            'not resource contention (Stage 17\'s resource buffer idea, not exercised here).\n'
        )

    report(model, project, control_project, tasks, 'Day 0 - baseline captured, execution begins')

    if not args.auto:
        input('\nPress Enter for step 1...')

    for i, step in enumerate(STEPS[: args.step], start=1):
        task = tasks[step['task']]
        print(f"\n{step['note']}")
        print_manual_steps(model, step['day'], task, step['remaining'])

        if not args.auto:
            input(
                '\nGo make this change in the app now, then press Enter here '
                'to reveal the expected result...'
            )

        record_status(model, task_ops, project['id'], step['day'], task, step['remaining'])
        report(model, project, control_project, tasks, f"Step {i}: {step['label']}")

        for buffer_name in step.get('explain_progress', []):
            explain_progress_frontier(model, tasks[buffer_name])
        for buffer_name in step.get('explain_consumption', []):
            explain_consumption(model, tasks[buffer_name])

        if not args.auto and i < min(args.step, len(STEPS)):
            input(f'\nPress Enter for step {i + 1} (or Ctrl+C to stop)...')

    print('\nDone.')


if __name__ == '__main__':
    sys.exit(main())
