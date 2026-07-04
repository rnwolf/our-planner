# CCPM Auto-Scheduling & Multi-Project Planning — Design & Work Plan

This document exists to hand this work off cleanly — to another AI coding session, or to a human
picking it back up later. It captures what has been built, what remains, and the reasoning behind
the design decisions, so the _why_ isn't lost even if the conversation that produced it is gone.

## Goal

Support Critical Chain Project Management (CCPM) style planning on our-planner's task grid:
dependency links with types (not just Finish-to-Start), project buffers that absorb schedule
risk, and a way to auto-push dependent tasks forward when something moves — with different
behavior depending on whether a project is still being planned or is already executing.

The broader context: this canvas is used for **rolling-wave planning** — a fixed set of teams
(resources) works across multiple projects over time. Several projects can coexist on one
canvas, sharing the same resource pool, each independently in "planning" or "execution" phase.

## Already implemented (this session)

All of the following is built, tested (`uv run pytest`, 40 tests passing), and manually verified
in the running app.

### Dependency link types

- `src/model/dependency_notation.py` — parsing/formatting for a compact link notation:
  bare id = Finish-to-Start (`FS`, default), or `id:TYPE` / `id:TYPE+lag` / `id:TYPE-lag` for
  `SS`, `FF`, `SF`, `PB`, `FB`. `PB`/`FB` are reserved for links into buffer rows (project buffer /
  feeding buffer) — a real task should never be attached to a buffer via plain `FS`.
- `task['predecessors']` is now `List[{'id': int, 'type': str, 'lag': int}]` (was a plain list of
  ints). `successors` is **not stored** — it's derived on demand via `model.get_successor_ids()`,
  to avoid the two lists drifting out of sync (see `model.add_predecessor`).
- Backward compatible: old saved plans with plain int predecessor lists are normalized to
  `{'id': ..., 'type': 'FS', 'lag': 0}` on load (`normalize_predecessor_entries`).
- UI to create/edit links:
  - Right-click a task → `Add Predecessor` / `Add Successor` — accepts a single link token,
    e.g. `5:SS+2` (not just a bare int).
  - Right-click a task → `Edit Predecessors...` — free-text edit of the task's _entire_
    predecessor list via the same notation (e.g. `3 5:SS+2 7:FF`), replacing the whole set.
  - Right-click directly on a dependency arrow on the canvas → menu to change its link type,
    set its lag, or remove it.
- `PB`/`FB` links are drawn as dashed lines, both on-canvas (`ui_components.py:draw_arrow`) and
  in PNG export (`export_operations.py`, manual dashed-line helper since PIL has no native dash
  support), so buffer links read visually differently from ordinary CPM dependencies.

### Task type

- `task['type']` ∈ `{'task', 'project_buffer', 'feeding_buffer'}`, defaults to `'task'`.
- `model.set_task_type(task_id, task_type)` validates the value.
- Right-click a task → `Set Task Type` cascade (mirrors the existing `Set Task State` menu).
- Buffers are created **manually** by the user (set a task's type to a buffer type) — there is no
  automatic critical-chain detection or buffer-cutting algorithm, and none is planned right now
  (see "Explicitly out of scope" below).

### Projects (rolling-wave planning)

- `model.projects`: `List[{'id': int, 'name': str, 'url': str, 'phase': 'planning'|'execution'}]`.
- `model.default_project_id` — new tasks are auto-assigned to this project unless a `project_id`
  is passed explicitly to `add_task`.
- CRUD: `add_project`, `update_project`, `remove_project`, `set_default_project`,
  `get_default_project`, `get_project_by_id`, `get_project_by_name`.
- `task['project_id']` — settable via right-click → `Edit Task Project...` (dropdown of existing
  projects + "None (unassigned)").
- `Projects` menu → `Manage Projects...` — full CRUD dialog (add/update/remove/set default, with
  a `url` field for linking out to more detail later).
- Footer status bar shows `Default Project: <name> (<Phase>)`, updates live.
- A fresh model seeds one `Sample Project` as the default so startup sample tasks aren't
  unassigned; persisted in save/load with backward compatibility for older files with no
  `projects` key at all.

### Auto Scheduling toggle
- `Tasks` menu → `Auto Scheduling` checkbutton, off by default.
- `controller.auto_scheduling_enabled` — a plain flag on `TaskResourceManager`
  (`src/controller/task_manager.py`), kept in sync via `toggle_auto_scheduling()`. Gates the
  Stage 2 FS cascade below (`TaskOperations.apply_dependency_cascade`), and will similarly gate
  Stage 3/4's buffer behavior once those are built.

### Phase switch + baseline capture (Stage 1 — done)

- `project['phase']` toggled via `Projects → Manage Projects...` → select a project → `Toggle
Phase` button (not a separate top-level menu item — chosen so phase management lives alongside
  the rest of project CRUD). Confirmation dialog before switching either direction.
- On a genuine `planning → execution` transition, `model.capture_project_baseline(project_id)`
  snapshots every buffer task (`type` ∈ `{project_buffer, feeding_buffer}`) belonging to that
  project: `task['baseline'] = {'col': int, 'duration': int, 'captured_at': str}`, using
  `self.setdate.isoformat()`. Returns a count so the caller can react (see below).
- If a baseline already exists for the project, `model.project_has_baseline()` gates a "recapture
  and overwrite?" confirmation before `capture_project_baseline` runs again.
- If the project has no buffer-typed tasks assigned to it (`captured_count == 0`), the dialog
  shows a `No Buffers Found` info message explaining why nothing was captured, instead of
  silently writing `null` — this was a real point of confusion during manual testing (see bug
  fixes below).
- Reversible: toggling back to `planning` just flips `phase`, it does not clear the baseline.
- Since a task's own `state` field (`planning`/`buffered`/`done` — task progress) is easily
  confused with a _project's_ `phase` (`planning`/`execution`), both are now surfaced
  side-by-side wherever either shows up, to disambiguate at a glance:
  - Task tooltip: `Task state: <state>` (renamed from `State:`) plus a separate
    `Project: <name> (<Phase>)` line.
  - Help → task details (`help_menu.py`, both detail blocks): same `Project: <name> (<Phase>)`
    line.
  - Footer status bar: `Default Project: <name> (<Phase>)`, refreshed both on toggle and on every
    `update_view()`. (Bug fix along the way: the `Toggle Phase` button originally updated the
    listbox but not the footer — `refresh_footer()` is now called there too.)

### Ordinary FS cascade (Stage 2 — done)

- `TaskOperations.apply_dependency_cascade(task)` (`task_operations.py`) — no-ops unless
  `controller.auto_scheduling_enabled` is `True`. Walks `model.get_successor_links(task_id)`
  (a new model method deriving outgoing links from successors' `predecessors` lists), and for
  each `FS`-type link where `successor.col < task.col + task.duration + lag`, pushes
  `successor.col` forward to that value and recurses into the successor's own successors
  (`_cascade_from_task`, with a recursion-stack `visiting` set to stop on a dependency cycle
  rather than push forever). **Only pushes forward, never pulls back.** Buffer-type successors
  (`project_buffer`/`feeding_buffer`) are explicitly skipped — they're reached via `PB`/`FB`
  links, not `FS`, and are reserved for Stage 3/4 instead. Pushed positions are clamped to
  `model.days` bounds.
- Wired into `on_task_release` (`task_operations.py`) at the three places a task's position can
  change: right-edge resize, single-task move, and multi-selected-task move. Left-edge resize is
  **not** wired up — it keeps the finish date fixed by construction, so no successor is ever
  affected by it. When the cascade actually moves another task, the caller does a full
  `ui.draw_task_grid()` redraw (simplest correct option, since the cascade can touch tasks
  anywhere on the grid) instead of the narrower single-task redraw used when nothing cascaded.
- Coexists with, and runs after, the pre-existing `handle_task_collisions` (same-row visual
  overlap, unrelated to dependency links) — both fire in `on_task_release`, collision-handling
  first, cascade second, and the cascade is idempotent so ordering isn't fragile.
- Verified: a chain `A -> B (FS) -> C (SS+1)` with `D` behind a feeding buffer (`PB`/`FB`) — moving
  `A` later correctly pushes `B` then `C` (respecting the `SS+1` lag), leaves the buffer and `D`
  untouched, does nothing when the flag is off, and does nothing when `A` moves earlier. Confirmed
  manually in the running app as well (Auto Scheduling on, dragging a task with a plain FS
  successor pushes it forward, including cascading further).

### Bug fixes (unrelated to CCPM, fixed along the way this session)

- Ctrl+scroll zoom only zoomed out on Linux (`Button-4` binding had no synthesized `delta`,
  fixed in `ui_components.py`).
- Toggling multi-select mode off crashed with `TclError: unknown color name "SystemButtonFace"`
  (Windows-only Tk color name used on Linux) — now captures the platform's real default
  background at startup and restores that instead.
- PNG export drew every task box `lightblue` regardless of its actual color — now uses the
  task's real color, same as the on-screen canvas.

## Remaining work, in agreed build order

Each stage should be implemented and manually verified in the running app before moving to the
next — this is a lot of interacting behavior and each piece needs to be trustworthy on its own.
Stages 1 and 2 (phase switch + baseline capture; ordinary FS cascade) are done — see "Already
implemented" above. Next up is Stage 3.

### Stage 3 — Planning-phase buffer glue (next up)

Applies only to buffer tasks (`type` ∈ `{project_buffer, feeding_buffer}`) whose owning
project's `phase == 'planning'`.

- A buffer is conceptually glued to its `FS` successor (the critical-chain merge-point task):
  `buffer.col + buffer.duration` must always equal `merge_task.col`, and `buffer.duration` is
  **fixed** (buffers do not resize automatically during planning).
- When the merge task moves — in **either** direction, for any reason — recompute
  `buffer.col = merge_task.col - buffer.duration` to keep it glued, without changing
  `buffer.duration`.
- Movement of the buffer's own predecessors (the feeding chain, connected via `PB`/`FB`) does
  **not** move the buffer during planning. A gap opening up between the feeding chain and the
  buffer is expected/fine — it's a visual indicator that the feeding chain currently finishes
  earlier than it needs to.
- Rationale (from the user): during planning, the buffer size is a deliberate protection amount
  chosen for the feeding chain — it shouldn't silently change just because tasks are being
  arranged. Only once execution starts does consumption become real.

### Stage 4 — Execution-phase absorb-then-overflow

Applies only to buffer tasks whose owning project's `phase == 'execution'`.

Triggered when a buffer's `PB`/`FB` predecessor (the feeding chain's last task) moves such that
it would encroach on the buffer:

- `required_start = predecessor.col + predecessor.duration + lag`
- `current_end = buffer.col + buffer.duration` (the buffer's end _right now_, before this event —
  not the Stage 1 baseline; the baseline is only for later fever-chart reporting)
- If `required_start <= buffer.col`: no encroachment, nothing happens.
- If `buffer.col < required_start <= current_end`: **buffer absorbs it** —
  `buffer.col = required_start`, `buffer.duration = current_end - required_start` (buffer visibly
  shrinks; its end stays fixed, so nothing after it needs to move).
- If `required_start > current_end`: **buffer fully consumed** — `buffer.col = required_start`,
  `buffer.duration = 0`, and the push **cascades through** to the buffer's own `FS` successor(s)
  using the buffer's new finish (`= required_start`), via the same mechanism as Stage 2.
- This is exactly the "shock absorber" behavior CCPM buffers are meant to have: the feeding
  chain can push into and fully consume the buffer before it starts delaying the critical chain
  merge point (and from there, potentially into the Project Buffer at the end of the chain).

### A subtlety already resolved

Whether a task/buffer reacts via Stage 2, 3, or 4 depends on the **current** phase of its
project at the moment a move happens — not on a one-time snapshot of "the critical chain" taken
when buffers were originally cut. This was a deliberate design choice: tasks get added to an
executing project's critical chain later (rolling-wave planning, scope discovered mid-project),
or get decomposed into smaller tasks — the push behavior should just react correctly to
whatever the dependency graph looks like _right now_, keyed off each task's type/phase, rather
than needing to re-run some global "recompute the critical chain" step.

## Explicitly out of scope (deferred, not forgotten)

- **Event-sourced architecture.** Discussed and deliberately deferred. The user is interested in
  it for two reasons: (a) point-in-time reconstruction of fever charts / reports during
  execution, and (b) a belief that event-sourced architectures may be easier to maintain with AI
  coding tools if the app is ever redeveloped from scratch. For now, the recommendation on record
  (not yet acted on) was: don't rewrite the mutable-model architecture; if/when the fever-chart
  need becomes concrete, consider a small _separate_ append-only log of just the CCPM-relevant
  facts (buffer size changes, phase transitions, actual start/end dates) rather than converting
  the whole app's state management.
- **Automated critical-chain detection / buffer-cutting algorithm.** The traditional CCPM step of
  computing the critical chain, stripping task safety, aggregating it into buffers, and
  auto-inserting `PB`/`FB` buffer tasks is **not** being automated. The user creates buffer tasks
  and marks task types manually; the tool's job is to react correctly (via Stages 2–4) to
  whatever graph currently exists, not to construct that graph for them.
- **Fever chart / % buffer consumption reporting.** Was already on the project's README Todo list
  before this work started. Stage 1's baseline capture is preparation for this, but the actual
  reporting UI is not part of this work.
- **Resource-constrained critical chain / resource leveling.** `network_operations.py`'s existing
  critical-path calculation (`calculate_critical_path`) is plain CPM (no resource contention
  awareness). Not addressed by anything in this document.

## Relevant files

- `src/model/task_resource_model.py` — core model: tasks, projects, predecessors, resources.
- `src/model/dependency_notation.py` — link notation parse/format, `LINK_TYPES_ORDERED`,
  `BUFFER_LINK_TYPES`.
- `src/operations/task_operations.py` — task mutation logic, right-click dialogs,
  `on_task_press`/`on_task_drag`/`on_task_release` (where Stage 2's trigger points live),
  `handle_task_collisions` (the pre-existing, unrelated same-row collision mechanism).
- `src/view/ui_components.py` — menus, canvas drawing, `draw_dependencies`/`draw_arrow`
  (dashed buffer links), context menu construction.
- `src/controller/task_manager.py` — `TaskResourceManager` (main controller), status bar,
  `auto_scheduling_enabled` flag and `toggle_auto_scheduling()`.
- `src/operations/network_operations.py` — existing plain-CPM critical path calculation.

## Open questions for whoever picks this up next

- Whether "the merge task" in Stage 3 (a buffer's `FS` successor) needs to be uniquely
  identifiable — i.e., what happens if a buffer somehow has more than one `FS` successor. Not
  discussed; likely worth a guard/validation when this is built.
