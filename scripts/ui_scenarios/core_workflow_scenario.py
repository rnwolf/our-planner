#!/usr/bin/env python3
"""Core workflow scenario: new project, role resources with capacity, a
small SDLC task network with multiple development chains, schedule with
CCPM - runnable against either UI driver.

Fast mode (default) proves out driver.ScenarioDriver against the real,
running TaskResourceManager app - real canvas drags, real context-menu
wiring, real dialogs (auto-answered) - rather than the model/operations-
only style tests/test_scenarios.py and scripts/stage12_walkthrough.py
already use. If this passes, the feature chain it exercises (File > New
-> add a project -> add resources and set their capacity -> drag-create
a task network with a merge point -> wire predecessors -> File > Schedule
with CCPM... -> File > Save As...) genuinely works end to end in the UI,
not just at the model layer. The task network's three parallel
development chains merging at one task also exercises CCPM's
feeding-buffer placement, not just its project buffer.

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
import os
import sys
import tempfile

from scripts.ui_scenarios.driver import ScenarioDriver


def step(label: str):
    print(f'\n{"=" * 70}\n{label}\n{"=" * 70}')


def run_scenario(driver):
    step('1. File > New (start from a clean, single-project slate)')
    driver.new_project()

    step(
        '2. Projects > Manage Projects... > Add '
        '(add a second project and make it the default)'
    )
    demo_project = driver.add_project('Core Workflow Demo', set_as_default=True)
    print(
        f"  created '{demo_project['name']}' (id={demo_project['id']}), set as default"
    )

    step(
        '3. Add role resources and set their capacity '
        '(Edit > Add Resource..., Edit > Edit Resources... > Capacity)'
    )
    capacities = {
        'Designer': 1.0,
        'Developer': 3.0,
        'Tester': 1.0,
        'Operations': 2.0,
    }
    resources = {name: driver.add_resource(name) for name in capacities}
    driver.set_resource_capacities(capacities)
    for name, capacity in capacities.items():
        print(f'  {name}: capacity/day={capacity}')

    step(
        '4. Create a small SDLC task network on the real task grid '
        '(drag-to-create) - three parallel development chains that merge '
        'back at Integration, so CCPM has more than one chain to insert '
        'feeding buffers for'
    )
    # A 1-column gap is left between same-row tasks - starting a new
    # task's drag exactly on a neighboring task's right edge (its resize
    # hit zone, +/-8px) grabs that edge instead of creating a new task.
    # The three Dev-* tasks run in parallel, so each gets its own row.
    design = driver.create_task(row=0, col=0, duration=3, name='Design')
    dev_backend = driver.create_task(row=0, col=4, duration=8, name='Dev-Backend')
    dev_frontend = driver.create_task(row=1, col=4, duration=5, name='Dev-Frontend')
    dev_infra = driver.create_task(row=2, col=4, duration=4, name='Dev-Infra')
    integration = driver.create_task(row=0, col=13, duration=3, name='Integration')
    test = driver.create_task(row=0, col=17, duration=4, name='Test')
    deploy = driver.create_task(row=0, col=22, duration=2, name='Deploy')
    tasks = (design, dev_backend, dev_frontend, dev_infra, integration, test, deploy)
    for t in tasks:
        print(
            f"  created '{t['description']}' (task_id={t['task_id']}, "
            f'col={t["col"]}, duration={t["duration"]})'
        )

    step(
        '5. Wire dependencies: Design fans out to three parallel '
        'development chains, which merge back at Integration -> Test -> '
        'Deploy (right-click context menu -> Add Predecessor...)'
    )
    for dev_task in (dev_backend, dev_frontend, dev_infra):
        driver.add_predecessor(dev_task, design)
        driver.add_predecessor(integration, dev_task)
    driver.add_predecessor(test, integration)
    driver.add_predecessor(deploy, test)
    print(f'  Integration predecessors: {integration["predecessors"]}')
    assert len(integration['predecessors']) == 3, (
        'expected Dev-Backend/Dev-Frontend/Dev-Infra to all merge at Integration'
    )

    step('6. Assign each task to its role resource')
    role_assignments = (
        (design, 'Designer'),
        (dev_backend, 'Developer'),
        (dev_frontend, 'Developer'),
        (dev_infra, 'Developer'),
        (integration, 'Developer'),
        (test, 'Tester'),
        (deploy, 'Operations'),
    )
    for task, role in role_assignments:
        driver.assign_resource(task, resources[role], allocation=1.0)
        print(f'  {task["description"]}: {role} ({task["resources"]})')

    step('8. Network > Schedule with CCPM...')
    # Two projects exist by this point (the 'Sample Project' File > New
    # leaves behind, and 'Core Workflow Demo') - capture every id that
    # exists right before scheduling so the lookup below can't mistake
    # 'Sample Project' for the CCPM output.
    original_ids = {p['id'] for p in driver.model.projects}
    confirmation = driver.schedule_with_ccpm('Core Workflow Demo')
    if confirmation:
        print(f'  {confirmation}')

    step('9. File > Save As... (persist the finished CCPM schedule)')
    save_dir = tempfile.mkdtemp(prefix='core_workflow_scenario_')
    save_path = os.path.join(save_dir, 'core-workflow-demo.json')
    driver.save_as(save_path)
    assert os.path.exists(save_path), f'Save As did not write {save_path}'
    print(f'  saved to {save_path}')

    step(
        '10. Inspect the resulting CCPM project - project buffer plus a '
        'feeding buffer for each non-critical development chain'
    )
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
    feeding_buffers = [t for t in ccpm_tasks if t.get('type') == 'feeding_buffer']
    assert buffer_tasks, 'expected a project_buffer task in the CCPM output'
    assert len(feeding_buffers) >= 2, (
        'expected a feeding buffer for each of the two non-critical '
        f'development chains, got {len(feeding_buffers)}'
    )
    print(f'  Project buffer: {buffer_tasks[0]["duration"]} days')
    for fb in feeding_buffers:
        print(f'  Feeding buffer: {fb["description"]} ({fb["duration"]} days)')


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

        driver_factory = lambda: VisualDriver(pace=args.pace)  # noqa: E731
    else:
        driver_factory = ScenarioDriver

    driver = driver_factory()
    try:
        if args.visual:
            # The window appears wherever Tk defaults to (primary monitor,
            # default size) - pause here, before anything is recorded or
            # scripted, so a human can maximize it and drag it to whichever
            # monitor they're actually recording, the same way they would
            # before narrating any other screen capture.
            print(
                'Application window is now visible - maximize it and move '
                'it to your recording monitor, then press Enter to continue.'
            )
            input()
            print(
                'Start your screen recorder now (e.g. GNOME '
                'Ctrl+Alt+Shift+R), then press Enter to begin.'
            )
            input()
        run_scenario(driver)
    except BaseException:
        # Close on any failure, same as the plain `with driver_factory() as
        # driver:` this replaced - the "stay open" behavior below only
        # applies once the scenario has actually finished cleanly.
        driver.close()
        raise

    print('\nPASS - core workflow scenario completed against the real app.')

    if args.visual:
        # Left open on purpose, not closed - visual mode's whole point is a
        # human picking up right where the script left off (finishing the
        # recording, making manual follow-on edits), so the window has to
        # survive past the script's own exit instead of being torn down the
        # instant run_scenario returns. mainloop() hands off to the real Tk
        # event loop and blocks here until the window is closed by hand.
        print("Leaving the app open - close its window when you're done.")
        driver.root.mainloop()
    else:
        driver.close()

    return 0


if __name__ == '__main__':
    sys.exit(main())
