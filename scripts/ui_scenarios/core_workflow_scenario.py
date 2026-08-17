#!/usr/bin/env python3
"""Core workflow scenario: create tasks, wire dependencies, schedule with
CCPM - runnable against either UI driver.

Fast mode (default) proves out driver.ScenarioDriver against the real,
running TaskResourceManager app - real canvas drags, real context-menu
wiring, real dialogs (auto-answered) - rather than the model/operations-
only style tests/test_scenarios.py and scripts/stage12_walkthrough.py
already use. If this passes, the feature chain it exercises (drag-create
a task -> right-click-wire a predecessor -> File > Schedule with CCPM...)
genuinely works end to end in the UI, not just at the model layer.

--visual mode runs the identical steps against visual_driver.VisualDriver
instead - same real app, but paced and with real (unpatched) dialogs, for
a narrated walkthrough. It doesn't control screen recording itself; start
one yourself (e.g. GNOME's Ctrl+Alt+Shift+R) before running it.

Usage:
    uv run python -m scripts.ui_scenarios.core_workflow_scenario
    uv run python -m scripts.ui_scenarios.core_workflow_scenario --visual
    uv run python -m scripts.ui_scenarios.core_workflow_scenario --visual --pace 1.2
"""

import argparse
import sys

from scripts.ui_scenarios.driver import ScenarioDriver


def step(label: str):
    print(f'\n{"=" * 70}\n{label}\n{"=" * 70}')


def run_scenario(driver):
    step('1. Create three tasks on the real task grid (drag-to-create)')
    # A 1-column gap is left between tasks - starting a new task's drag
    # exactly on a neighboring task's right edge (its resize hit zone,
    # +/-8px) grabs that edge instead of creating a new task.
    c1 = driver.create_task(row=0, col=0, duration=5, name='C1')
    c2 = driver.create_task(row=0, col=6, duration=5, name='C2')
    c3 = driver.create_task(row=0, col=12, duration=5, name='C3')
    for t in (c1, c2, c3):
        print(
            f"  created '{t['description']}' (task_id={t['task_id']}, "
            f'col={t["col"]}, duration={t["duration"]})'
        )

    step(
        '2. Wire C1 -> C2 -> C3 as Finish-to-Start dependencies '
        '(right-click context menu -> Add Predecessor...)'
    )
    driver.add_predecessor(c2, c1)
    driver.add_predecessor(c3, c2)
    print(f'  C2 predecessors: {c2["predecessors"]}')
    print(f'  C3 predecessors: {c3["predecessors"]}')
    assert any(p['id'] == c1['task_id'] for p in c2['predecessors'])
    assert any(p['id'] == c2['task_id'] for p in c3['predecessors'])

    step(
        '3. Add a resource and assign it to every task '
        '(CCPM needs contention to identify a critical chain)'
    )
    dev = driver.add_resource('Dev')
    for t in (c1, c2, c3):
        driver.assign_resource(t, dev, allocation=1.0)
        print(f'  {t["description"]}: resources={t["resources"]}')

    step('4. File > Schedule with CCPM...')
    confirmation = driver.schedule_with_ccpm()
    if confirmation:
        print(f'  {confirmation}')

    step('5. Inspect the resulting CCPM project')
    original_ids = {c1['project_id']}
    ccpm_project = next(p for p in driver.model.projects if p['id'] not in original_ids)
    ccpm_tasks = [
        t for t in driver.model.tasks if t['project_id'] == ccpm_project['id']
    ]
    print(f"  New project: '{ccpm_project['name']}' ({len(ccpm_tasks)} rows)")
    for t in sorted(ccpm_tasks, key=lambda t: t['col']):
        print(
            f'    {t["description"]:<20} col={t["col"]:>3} '
            f'duration={t["duration"]:>3} type={t.get("type", "task")}'
        )
    buffer_tasks = [t for t in ccpm_tasks if t.get('type') == 'project_buffer']
    assert buffer_tasks, 'expected a project_buffer task in the CCPM output'
    print(f'  Project buffer: {buffer_tasks[0]["duration"]} days')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--visual',
        action='store_true',
        help='run against the paced, real-dialog VisualDriver instead of the fast driver',
    )
    parser.add_argument(
        '--pace',
        type=float,
        default=0.6,
        help='visual mode only: seconds between steps (default: 0.6)',
    )
    args = parser.parse_args()

    if args.visual:
        from scripts.ui_scenarios.visual_driver import VisualDriver

        print(
            'Visual mode: start your screen recorder now '
            '(e.g. GNOME Ctrl+Alt+Shift+R), then press Enter to begin.'
        )
        input()
        driver_factory = lambda: VisualDriver(pace=args.pace)  # noqa: E731
    else:
        driver_factory = ScenarioDriver

    with driver_factory() as driver:
        run_scenario(driver)

    print('\nPASS - core workflow scenario completed against the real app.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
