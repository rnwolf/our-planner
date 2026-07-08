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
in the running app. **Stages 1-8 (see each "Stage N — done" heading below) are now complete** —
the original 7-stage build order, plus Stage 8 (fever chart reporting, including PNG export), added
afterward once Stages 4/7's data capture made it practical to build. Stage 9 (fever chart CSV data
export) and Stage 10 (backlog full-kit readiness report) are the next build items — see "Remaining
work" below. What's left after that is everything listed under "Explicitly out of scope" (automated
critical-chain detection, resource-constrained
scheduling, event sourcing, full plan-vs-baseline comparison UI).

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
- **Pitfall confirmed by testing**: naming a task "Feeding Buffer" and linking it via an `FB`/`PB`
  link is *not* enough to get buffer behavior — every buffer-aware mechanism (Stage 2's skip,
  Stage 3/6's glue, Stage 7) checks the task's actual `type` field, not its description text or
  the link type pointing at it. A task must have `Set Task Type` actually applied. The tooltip
  (see below) now shows `Task type:` explicitly so this is checkable at a glance instead of only
  discoverable by testing behavior.

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
  (`src/controller/task_manager.py`), kept in sync via `toggle_auto_scheduling()`.
- **Revised after Stage 6 testing**: this toggle only gates the cascade while a task's project is
  still in `planning` (a manual, optional convenience while sketching out a plan). Once a project
  is in `execution`, `apply_dependency_cascade` always runs regardless of the toggle - the user's
  call was that execution-phase reactions (relay-runner cascade, buffer glue) aren't optional at
  that point, that's just how the schedule stays truthful once real status updates start coming
  in. See `apply_dependency_cascade`'s docstring (`task_operations.py`).

### CCPM schedule import

`File → Import CCPM Schedule...` (`FileOperations.import_ccpm_schedule`, `file_operations.py`) —
imports a `schedule.csv` (+ `resources.csv`, optionally `calendar.csv`) produced by an external
CCPM scheduling tool as a new project, rather than requiring the whole plan to be recreated by
hand in the UI. Format documented in `sample-ccpm-projects/file-structure.md`, which also holds
four real sample projects (`equipment-retrofit`, `kitchen-renovation`, `lab-trials`,
`website-launch`) used to verify this.

- Prompts for `schedule.csv`, requires `resources.csv` alongside it in the same folder
  (`calendar.csv` optional), then a name for the new project (prefilled from the folder name).
- **Resources are imported by name, reusing an existing one rather than duplicating it** — this
  app already models resources as a shared team pool across projects (rolling-wave planning), so a
  resource named the same as one already in the plan is assumed to be the same person/team.
  `calendar.csv`'s half-open `[from, to)` capacity overrides are applied on top.
- **Two-pass task import**: create every task/buffer first (`schedule.csv`'s own ids are arbitrary
  alphanumeric strings like `K2`/`W3`, not this model's plain-integer task ids, so a translation
  map is built as tasks are created), then wire up predecessor links once every id is resolvable.
  Link notation (`K2:FB`, lag, etc.) reuses the same `FS`/`SS`/`FF`/`SF`/`PB`/`FB` vocabulary this
  app already has - just with a separate token parser since `schedule.csv` ids are alphanumeric,
  not the plain integers `dependency_notation.py`'s own parser requires.
- **Chain labels** (`critical`, `feeding-1`, `feeding-2`, ...) are mapped to real chains, creating
  a new one (cycling through an unused default color) if it doesn't already exist - so a schedule
  needing more feeding chains than the default 5 just works without manual setup first.
- Extends the timeline (`model.days`) and every resource's capacity array to fit if the imported
  schedule needs more days than currently exist.
- Verified against all four real sample projects headlessly: correct task/resource/chain/
  predecessor data (including calendar overrides applying correctly, e.g. a resource correctly
  showing `0.0` capacity during its outage window), no errors or warnings, and a full save/load
  round-trip of the imported data.

### Phase switch + baseline capture (Stage 1 — done)

- `project['phase']` toggled via `Projects → Manage Projects...` → select a project → `Toggle
Phase` button (not a separate top-level menu item — chosen so phase management lives alongside
  the rest of project CRUD). Confirmation dialog before switching either direction.
- On a genuine `planning → execution` transition, `model.capture_project_baseline(project_id)`
  snapshots every task belonging to that project (originally buffer-typed tasks only; widened by
  Stage 4 to cover the whole project — see below): `task['baseline'] = {'col': int, 'duration':
  int, 'safe_duration': int, 'captured_at': str}`, using `self.setdate.isoformat()`. Returns a
  count so the caller can react (see below).
- If a baseline already exists for the project, `model.project_has_baseline()` gates a "recapture
  and overwrite?" confirmation before `capture_project_baseline` runs again.
- If the project has no tasks assigned to it at all (`captured_count == 0`), the dialog shows a
  `No Tasks Found` info message explaining why nothing was captured, instead of silently writing
  `null` — this was a real point of confusion during manual testing (see bug fixes below; the
  message originally said `No Buffers Found`, from when capture was still buffer-only).
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
  (`_propagate_from_task`, with a recursion-stack `visiting` set to stop on a dependency cycle
  rather than push forever). **Only pushes forward, never pulls back.** Buffer-type successors
  (`project_buffer`/`feeding_buffer`) are explicitly skipped — they're reached via `PB`/`FB`
  links, not `FS`, and are reserved for Stage 3/7 instead. Pushed positions are clamped to
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

### Buffer-follows-merge-point glue (Stage 3 — done, since revised to apply in both phases)

- `TaskOperations._glue_buffer_predecessors(task, visiting)` (`task_operations.py`) — called from
  within `_propagate_from_task` for every task whose position was just set (whether by a direct
  user move/resize, or by being pushed/pulled there by Stage 2/6's cascade). For each of `task`'s
  predecessor links of type `FS` **or `FB`** whose predecessor is a buffer task
  (`project_buffer`/`feeding_buffer`), it recomputes `buffer.col = task.col - buffer.duration -
  lag` unconditionally — i.e. it snaps the buffer to stay glued in **either** direction, unlike
  Stage 2's one-directional push. `FB` was added alongside plain `FS` because that's the link type
  actually used in practice between a feeding buffer and its critical-chain merge-point task.
- Deliberately does **not** trigger off the buffer's own predecessors (the feeding chain) — those
  are only ever read by Stage 2/6 (which always skips buffer-type successors), so a feeding-chain
  task moving later just opens a gap between it and the still-glued buffer, exactly as intended.
- **Originally planning-phase only, revised to apply in both phases.** Initially built with an
  `if project['phase'] != 'planning': continue` guard, reasoning that Stage 7 would own all buffer
  behavior once a project executes. User testing (a critical-chain task finishing early, correctly
  pulling its merge-point successor back via Stage 6, but *not* pulling the feeding buffer glued to
  that successor) showed this was wrong: a feeding buffer's whole purpose is to protect its merge
  point, so it must track that merge point moving for *any* reason, in *any* phase - the
  phase-dependent part is only what happens on the buffer's own predecessor side (the feeding
  chain itself), which is Stage 7's job, not this glue. The phase guard was removed entirely.
- No ping-pong: if a buffer's own finish is what pushes the merge task forward (e.g. a manual
  buffer resize triggering Stage 2's ordinary push), re-gluing afterward recomputes the exact same
  buffer position it already had, so `_propagate_from_task`'s cycle guard is never even needed to
  stop this case - the glue and the push land on the same equality by construction.
- Verified with a headless script (merge task moves later -> buffer follows; moves earlier ->
  buffer follows, clamped at 0; feeding chain moves -> buffer stays, gap opens; buffer resize
  pushes merge task -> no oscillation; **and, after the revision, the same glue confirmed working
  identically during execution**) for both a plain `FS` and an explicit `FB` buffer->merge-task
  link, and confirmed manually in the running app for both link types and both phases.

### Task progress tracking & anchoring (Stage 4 — done)

Turns `task['col']`/`task['duration']` from "the plan" into "the current best estimate," driven by
real status updates. The original signed-off plan is not lost — it's preserved separately in the
(now widened) baseline.

- **Widened Stage 1's baseline.** `capture_project_baseline`/`project_has_baseline` now snapshot
  **every task** in a project (`{'col': int, 'duration': int, 'safe_duration': int, 'captured_at':
  str}`), not just buffer-typed ones — so a PM/stakeholder can pull up "the plan we signed off on"
  at any point during execution and compare it to where things actually stand, not just buffer
  sizes. `safe_duration` was added to the snapshot after manual testing surfaced that the `View
  Duration History...` dialog needed it (see below). The `No Buffers Found` info message was
  reworded to `No Tasks Found` to match the widened scope.
- **Anchoring the start.** `model.record_remaining_duration` now snaps `task['col']` to
  `model.get_day_for_date(self.setdate)` the first time it's called for a task (when
  `actual_start_date` isn't set yet) — the bar's left edge visually jumps to where work *actually*
  started, which may be earlier or later than where it was planned.
- **Re-estimating the finish.** Every call recomputes `task['duration']` from the *most recent*
  history entry (via `_get_latest_remaining_duration_entry`), so `task['col'] + task['duration']`
  always equals `(day-column of that entry's date) + its remaining_duration`.
  - **Bug found and fixed by testing**: "most recent" is `(date, insertion index)`, not `date`
    alone. `setdate` is day-granularity by design (a PM's "as-of" project clock, not a wall-clock
    timestamp - see `Date → Set Current Date`), so multiple updates recorded on the same day share
    an identical `date` string. The original implementation sorted by `date` alone with
    `reverse=True`; Python's sort is *stable*, so entries tied on `date` kept their original
    insertion order even under `reverse=True` - meaning the **first** entry recorded on a given
    day always won, and every subsequent same-day correction was silently ignored (`Record
    Remaining Duration` appeared to only ever take effect once per day). Fixed by tie-breaking on
    each entry's index in `remaining_duration_history` (always append-only, so index reliably
    reflects recording order regardless of `date` granularity) - the last entry recorded for a
    given day now correctly wins. Verified against a real reproduction file with four same-day
    entries (`9, 8, 8, 7`) that previously resolved to `9`; now correctly resolves to `7`.
    Pre-existing saved files may still have a stale `task['duration']` baked in from before this
    fix (recording one more update recomputes it correctly).
- `TaskOperations.record_remaining_duration` (`task_operations.py`) now calls
  `self.apply_dependency_cascade(task)` right after the model update, so a re-estimated finish
  pushes FS successors forward exactly like a drag/resize would (Stage 6/7 will build on this same
  entry point once chains exist).
- **Full Kit stays informational, not a gate** — `Set Full Kit Done`/`fullkit_date` unchanged, no
  blocking behavior added. New: a small green circular badge in the task box's top-left corner
  (`ui_components.py:draw_task`), shown whenever `fullkit_date` is set, visible without hovering.
- **`Record Remaining Duration`'s two guardrails** (`task_operations.py`):
  - If the task hasn't started yet (no `actual_start_date`), the prompt itself warns that
    recording a value now will anchor `actual_start_date` to today and suggests dragging the
    task's edge instead if the goal is just to update the duration estimate for a not-yet-started
    task (e.g. after completing its full kit) - added after the user found this anchoring
    side-effect surprising when using the dialog for that purpose.
  - **Hard block if the task's project is still in `planning`** (found necessary after the user
    kept triggering the dialog by habit on planning-phase tasks): checked before the prompt is
    even shown, replaced entirely with an info message pointing at `Manage Projects... > Toggle
    Phase`. Recording progress is inherently an execution-phase concept - there's nothing to
    "record remaining duration" against before a plan has actually started being executed.
    Verified headlessly (blocked + no dialog shown in planning phase; unaffected + dialog shown
    once the project is toggled to execution).
- **Progress visualization.** New `model.get_task_progress_fraction(task_id)` — `None` before a
  task has started, `1.0` once `state == 'done'`, otherwise `(duration - latest_remaining) /
  duration` (i.e. how much of the current best-estimate span had elapsed as of the latest status
  update). Drawn as a thick stripe along the task box's **bottom** edge, proportional width. The
  **top** edge was left free at the time, and is now used by Stage 5's chain-color stripe.
- **`View Duration History...` dialog** (`task_operations.py`) updated: the pre-existing "Original
  Duration" line was renamed to `Current Duration` (it now reflects the live re-estimated value,
  not the original plan — keeping the old label would have been actively misleading). Two new
  lines, `Baseline Duration` and `Baseline Safe Duration`, are shown whenever `task['baseline']`
  exists, pulled from the widened baseline snapshot. Baselines captured before this change (missing
  `safe_duration`) fall back to the task's current `safe_duration`.
- Verified headlessly: anchoring, re-estimation (including an out-of-order/backdated correction),
  progress-fraction values at several points in a task's lifecycle, the widened baseline capturing
  both buffer and ordinary tasks with `safe_duration` included, and the cascade firing correctly
  from a recorded update. Confirmed manually in the running app: recording remaining duration
  visibly moves/resizes the bar and (with Auto Scheduling on) still only pushes a later-finishing
  successor forward — the user confirmed this is expected, since the bidirectional "relay runner"
  pull-back is Stage 6 and depends on Stage 5's chain classification, which didn't exist yet at
  the time (Stage 5 has since been built - see below).

### Chain registry & chain-aware task classification (Stage 5 — done)

An explicit, user-managed classification of which chain each task belongs to — critical, or one
of several feeding chains. This was originally going to be derived structurally (walk a task's
plain-FS chain forward until it hits a buffer, and classify by that buffer's type), but the user
opted for an explicit, constrained-choice attribute instead: simpler to reason about, and it gives
a stable place to hang a visual color, at the cost of the user having to tag tasks manually
(consistent with buffers and task types already being manual, not auto-derived).

- `model.chains`: `List[{'id': int, 'name': str, 'color': str, 'is_critical': bool}]`.
  - Exactly one entry may have `is_critical = True` at a time (`set_critical_chain` unmarks any
    other chain) — mirrors the existing single-flag `default_project_id` pattern. Stage 6's
    cascade will check this boolean, **not** a string match on the name, so renaming the chain
    later can't silently change scheduling behavior.
  - Global across the whole plan, not scoped per project.
  - A fresh model seeds 5 entries: `Critical` (`is_critical=True`, red) plus `Feeding-01` through
    `Feeding-04` (blue/magenta/purple/deep-orange), so a user can start building a project network
    without first having to set up this reference data. Loading an *older* save file with no
    `chains` key at all leaves `self.chains` empty (consistent with how `projects` is handled) —
    only a brand-new model auto-seeds. All names/colors remain freely editable, and more chains
    can be added via `Manage Chains...` if a plan needs more than 4 feeding chains.
- CRUD: `add_chain`, `update_chain`, `remove_chain` (unassigns tasks that referenced it, same
  pattern as `remove_project`), `get_chain_by_id`/`by_name`, `set_critical_chain`,
  `get_critical_chain`.
- `Chains` menu (new top-level menu) → `Manage Chains...` dialog (`task_operations.py`) — same
  CRUD dialog shape as `Manage Projects...`, plus a `Choose Color...` button (stdlib
  `tkinter.colorchooser`) and each chain's listbox row tinted with its own color.
- `task['chain_id']: Optional[int]`, defaulting to `None` — settable via right-click → `Edit Task
  Chain...` (dropdown of chain names + "None (unassigned)"), reusing a newly generalized
  `OptionSelectDialog` (renamed from the project-specific `ProjectSelectDialog`, since the same
  dropdown-pick shape now serves both projects and chains).
  - `chain_id = None` behaves like "not critical" for Stage 6's cascade — backward compatible, a
    plan with no chains assigned keeps behaving exactly like today's forward-only-push cascade.
  - Buffers get a `chain_id` too, purely for consistency/visual grouping — it does **not** drive
    buffer behavior, which is still entirely governed by `task['type']`.
- **Visual**: a colored stripe along the task box's top edge (`ui_components.py:draw_task`) using
  the assigned chain's color — separate from the progress stripe (bottom edge, Stage 4) and from
  the pre-existing free-form `task['color']` fill, so assigning a chain doesn't take over a user's
  existing color-coding for unrelated purposes. Chain name also shown in the task tooltip.
- Verified headlessly (seeding, CRUD, duplicate-name rejection, single-critical-chain enforcement,
  task assignment/unassignment/removal-cascades-to-unassign, save/load round-trip) and confirmed
  manually in the running app (`Chains` menu, add/recolor/remove, task assignment).
- **Exports** (`export_operations.py`): PDF task table gained a `Chain` column (right after
  `Description`); CSV tasks export gained `Project` and `Chain` columns (after `Description`) —
  added on request as "the quickest way to check what tasks are on what chain" without opening the
  app. Both blank when unassigned.

### Execution-phase chain-aware relay-runner cascade (Stage 6 — done)

This is what "Stage 4" originally meant before the chain discussion, refined with the
classification from Stage 5. It only changes behavior when a project is in the `execution` phase
— Stage 2's planning-phase rule (forward-only, regardless of chain) is completely unchanged.

- `TaskOperations._is_critical_chain_task_in_execution(task)` (`task_operations.py`) — true only
  when `task`'s own project is in `execution` **and** `task`'s assigned chain has `is_critical =
  True`. Checked inside `_propagate_from_task` for every task whose position was just set:
  - If true: its ordinary (non-buffer) `FS` successors are kept in lock-step **bidirectionally** —
    pushed later *or* pulled earlier to always sit exactly at `task.col + task.duration + lag`,
    cascading transitively along the critical chain. This is the "relay runner" mentality: if a
    critical-chain task finishes early, the next runner starts immediately, they don't wait around
    for the baton.
  - If false (a specific `Feeding-NN`, unset/`None`, or still planning): successors are only ever
    **pushed forward** automatically — identical to Stage 2's rule, never pulled earlier
    automatically. A feeding-chain task finishing early is fine; the feeding buffer downstream
    absorbs that slack (Stage 7, still pending), and feeding-chain tasks are expected to run close
    to as-late-as-possible by design. A human can still manually drag a feeding-chain task earlier
    to grab an opportunity - that stays a deliberate manual choice, not an automatic one.
  - Either way, propagation still **stops at a buffer** — buffer-type successors are never
    pushed/pulled by this rule; Stage 7 owns what happens to a buffer *from its predecessor side*
    (Stage 3's glue, now phase-independent, owns the buffer's position relative to its merge point
    — see above).
- **`apply_dependency_cascade` no longer requires the Auto Scheduling toggle while a task's project
  is executing** (see "Auto Scheduling toggle" above) — this was a deliberate follow-up decision
  made once Stage 6 existed and made the toggle's scope concrete, not part of the original build
  plan for this stage.
- **Known limitation, explicitly out of scope**: this cascade only follows *declared*
  `predecessors` links. It cannot detect an implicit dependency caused by two tasks on different,
  unlinked chains competing for the same constrained resource — the classic CPM-vs-CCPM gap (the
  *critical chain*, unlike the critical *path*, can run through a resource-constrained feeding
  task with no direct logical link to the nominal critical path). If that happens, it'll show up
  as an overlap on the resource-loading view, not as an automatic reschedule — the user needs to
  add an explicit link or resequence manually. See also "Explicitly out of scope" below.
- Tooltip (`ui_components.py:add_task_tooltips`) now also shows `Task type: <Task/Project
  Buffer/Feeding Buffer>` and always shows a `Chain:` line (`Chain: None` when unassigned, instead
  of omitting the line) — added after a real debugging session where a task named "Feeding Buffer"
  and linked via `FB` turned out to still have `type: 'task'` (never actually run through `Set Task
  Type`), so none of the buffer-aware logic engaged. The tooltip now makes that checkable at a
  glance instead of only discoverable by testing behavior (see the "Task type" pitfall note above).
- Tooltip also now shows `Predecessors: <compact notation, e.g. "3 5:SS+2", or "None">` and
  `Successors: <comma-separated ids, or "None">` (`format_predecessor_notation` /
  `model.get_successor_ids` — the same derivations `help_menu.py`'s task-detail view already used,
  just not previously surfaced on hover) — added after the CCPM schedule importer (see below) made
  it common to be looking at a plan with real feeding-chain topology that needed tracing/untangling
  by hovering, without opening `Help → task details` for the same information every time.
- Verified headlessly (planning phase leaves a critical-tagged task forward-only; execution +
  critical pulls back and pushes forward bidirectionally; execution + feeding/unassigned stays
  forward-only; transitive cascading through multiple critical-chain tasks; buffer successors
  still isolated from this rule; clamping; cascade now firing during execution with Auto
  Scheduling off, still gated by the toggle during planning) and confirmed manually in the running
  app, including the debugging round above that led to the buffer-glue phase fix and the tooltip
  additions.

### Execution-phase buffer absorb-then-overflow (Stage 7 — done)

Supersedes the original single-direction sketch — genuinely bidirectional, with growth capped at
the buffer's baseline size.

- `TaskOperations._absorb_into_buffer_successors(task, visiting)` (`task_operations.py`) — for
  each of `task`'s successor links pointing at a buffer task whose project is executing:
  - `required_start = task.col + task.duration + lag`; `current_end = buffer.col +
    buffer.duration` (the buffer's end *right now*, not the Stage 1/4 baseline, which is only for
    later comparison/reporting).
  - **Encroachment** (`required_start > buffer.col`): the buffer shrinks — `buffer.col =
    required_start`, `buffer.duration = current_end - required_start`, end stays fixed. If
    `required_start > current_end`, the buffer is **fully consumed** (`duration` clamped to `0`),
    and the overflow cascades through to the buffer's own successor (the critical-chain merge
    task) via the ordinary cascade above — this is the moment a feeding chain has effectively
    become the (new) critical chain through that merge point, exactly as the user described it.
  - **Slack** (`required_start < buffer.col`): the buffer grows by moving its start earlier, end
    still fixed, capped at `task['baseline']['duration']` (falls back to the buffer's own current
    duration if no baseline is on record, which makes the cap a no-op rather than unbounded
    growth). Once regrown to baseline size, further slack just opens a gap in front of the
    (capped) buffer rather than growing it past its original sizing.
  - The buffer's own end (and therefore the merge task) is **never** pulled earlier by this rule —
    enforced structurally (propagation *from* a buffer is always forced forward-only, regardless
    of the buffer's own chain tag), not just incidentally because feeding buffers are typically
    tagged non-critical. Only Stage 6's critical-chain bidirectional rule, triggered from the
    merge task's own chain, may pull it earlier.
  - Every actual size change is logged via `model.record_buffer_size_change` (see the
    fever-chart data capture below).
- **Bug found and fixed during testing #1**: the ordinary cascade's main successor loop
  (`_propagate_from_task`) originally only followed `FS`-type links. Once a buffer is fully
  consumed and needs to push its overflow onward, that link is realistically typed `FB` (the
  buffer's link to its own merge point), not `FS` — confirmed against a real save file where
  Task B's predecessor entry for the feeding buffer was `{'type': 'FB'}`. Widened the loop to also
  follow `FB`/`PB` links (safe: ordinary, non-buffer tasks never have outgoing `FB`/`PB` links, so
  this only ever matters when propagating from a buffer).
- **Bug found and fixed during testing #2**: `_absorb_into_buffer_successors` itself originally
  only recognized `FB`/`PB` links when checking whether a task feeds *into* a buffer. Confirmed
  against a real save file that the link feeding an ordinary task *into* a buffer is legitimately
  a plain `FS` link (`FB`/`PB` describe the link *out of* a buffer to its merge point, not into
  one) — so a real "Task C exceeds the feeding buffer" scenario silently did nothing. Fixed by
  widening the check to `FS`/`FB`/`PB`, relying entirely on the *successor's* `type` being a
  buffer to decide whether this applies, not the link's own type.
- **Follow-up UX fixes, prompted by "how do I even see/access a fully-consumed buffer?"**:
  - `TaskResourceManager.get_task_ui_coordinates` (`task_manager.py`) now enforces a 6px minimum
    render width — a zero-duration buffer would otherwise be a zero-width box: invisible, and
    unclickable (the right-click hit-test `x1 < x < x2` can never match when `x1 == x2`). Doesn't
    touch the underlying `duration` used for scheduling, purely rendering/hit-testing.
  - New `View Buffer History...` context menu item (`task_operations.py:view_buffer_history`,
    mirrors `View Duration History...`) shows a buffer's type, current/baseline duration, and its
    full `buffer_size_history` log (date, duration, reason, and the triggering task) — raw data
    made inspectable now, ahead of the eventual fever chart itself.
- Verified headlessly (partial encroachment; full consumption with push-through using the real
  `FB` link type; slack growth capped exactly at baseline with a gap opening once capped; planning
  phase correctly not absorbing at all; project buffer via `PB` link behaving identically;
  save/load round-trip of `buffer_size_history`) and confirmed manually in the running app against
  two real reproduction files, including the minimum-width/`View Buffer History...` follow-ups.

**Data capture for future fever-chart reporting.** A CCPM fever chart plots, over time, % of a
chain complete (x-axis) against % of its buffer consumed (y-axis). The chart itself, and the %
computations, remain deferred (still out of scope) — this only concerns making sure the necessary
raw data exists:

- **% chain complete needs no new capture** — every task's `remaining_duration_history` is a dated
  log of every status update (not just the latest), and every task's `chain_id` +
  `baseline.duration` (Stage 4, project-wide) are already on record, so "% of chain X complete as
  of date D" is fully reconstructable later by replaying this history.
- **% buffer consumed needed a new capture, since it can't be reconstructed after the fact** — a
  buffer only ever had two points in time on record (its one-time `baseline`, and whatever
  `col`/`duration` are *right now*), with no trail of intermediate sizes; unlike the
  chain-completion side, this can't be rebuilt without replaying the entire cascade history
  event-by-event (the event-sourcing approach already discussed and deliberately deferred - see
  below). `model.record_buffer_size_change(buffer_task_id, duration, reason, trigger_task_id)`
  appends to `task['buffer_size_history']` every time Stage 7 changes a buffer's `duration`:
  ```
  {
      'date': str,             # self.setdate.isoformat(), same convention as elsewhere
      'duration': int,         # the buffer's new duration after this change
      'reason': str,           # 'encroachment' | 'fully_consumed' | 'slack_growth'
      'trigger_task_id': int,  # the predecessor task whose movement caused this change
  }
  ```
  `trigger_task_id` is recorded so a PM can later figure out *what happened*, not just that the
  buffer changed size - "which task's slip actually ate into this buffer." Applies identically to
  both feeding buffers and the project buffer.

### A subtlety already resolved

Whether a task/buffer reacts via Stage 2/3 or Stage 6/7 depends on the **current** phase of its
project at the moment a move happens — not on a one-time snapshot of "the critical chain" taken
when buffers were originally cut. This was a deliberate design choice: tasks get added to an
executing project's critical chain later (rolling-wave planning, scope discovered mid-project),
or get decomposed into smaller tasks — the push behavior should just react correctly to
whatever the dependency graph looks like _right now_, keyed off each task's type/phase/chain,
rather than needing to re-run some global "recompute the critical chain" step.

### Fever chart reporting (Stage 8 — done)

**Superseded design.** The formulation below replaces an earlier, simpler sketch (per-task
progress fractions weighted by baseline duration). That sketch is wrong: it treats "% complete"
as a smooth average, which doesn't hold up on chains with partially-done tasks, and it couldn't
account for the fact that both axes need to be genuinely *forecast*-based (able to move backwards
as estimates improve), not cumulative. The design below comes from a dedicated write-up the user
provided (`fever-chart-considerations.md`, kept in the repo root) and is considerably more
rigorous. Read that file directly if anything below is unclear — this is a summary, not a
replacement for it.

**The question the chart answers.** Not "how have we performed?" but **"should I intervene
today?"** — so every quantity is based on the *current forecast*, recalculated from scratch at
every status update, and both axes are explicitly allowed to move backwards (that's information,
e.g. a downstream recovery, not an error to smooth away).

**Four independent quantities, computed per buffer, re-run on every status change:**

1. **CPSL (Current Protected Schedule Length)** — the x-axis denominator. The forecast elapsed
   time from the start of the protected chain to the forecast finish of the **terminal protected
   task** (the one ordinary, non-buffer task that is the buffer's own direct predecessor — the
   last work task before the buffer). It's a *timeline* (chain-start `col` to terminal task's
   *current* `col + duration`), not a sum of task durations, and it **excludes the buffer itself**
   — the buffer is protection, not planned progress. Chain start is the earliest `col` among the
   chain's tasks (their live position, following Stage 4 anchoring if that first task has already
   started).
2. **PPF (Protected Progress Frontier)** — the x-axis numerator. The latest point on the chain
   that is **known with certainty**: every task scheduled to finish before that point is
   *confirmed complete* (`state == 'done'`). If a chain task is 50% done, the frontier sits at its
   predecessor's finish, not partway into that task — this resolves the ambiguity of "% complete"
   on a chain where later work has progressed further than earlier work still isn't marked done.
   **Generalizes cleanly to branching/parallel feeder paths that merge before the buffer**: sort
   *every* task tagged with the chain (`get_chain_tasks`, regardless of which parallel path it's
   on) by **scheduled finish** (`col + duration`), then walk in that order, extending the frontier
   past each `'done'` task's finish and stopping at the first task that isn't - so a later-finishing
   task on a *different* path already being done can never let the frontier skip past an earlier,
   still-incomplete one on another path (confirmed against `fever-chart-considerations.md`'s own
   wording: "the frontier can't advance past an incomplete task even if later parallel work is
   finished"). No dependency-order derivation needed - sorting by finish time already gives the
   right answer regardless of topology.
3. **Progress % = PPF ÷ CPSL.** If a task overruns and the horizon (CPSL) moves out, progress can
   *drop* even as the frontier (PPF) advances — e.g. week 1: 30/100 = 30%; week 2: frontier now 40
   but forecast horizon now 120 → 33%, not a misleadingly-improved 40%. This is why CPSL must be
   forecast-based, not the chain's baseline length.
4. **Buffer Consumption % = forecast lateness ÷ baseline buffer size**, where `forecast lateness =
   (current forecast finish of the terminal task) − (that same task's baseline finish)`. The
   **denominator is fixed** (the buffer's own `baseline.duration` — the insurance premium agreed
   at the planning→execution transition; only a formal re-baselining would change it), but the
   **numerator is forecast-based** — it decreases when downstream tasks recover time. For a
   feeding buffer the protected object is the merge point with the critical chain, not project
   finish; same math, different anchor (its terminal task is the feeding chain's own last task).
   - **Not clamped.** Consumption can exceed 100% (forecast lateness bigger than the baseline
     buffer — a forecast breach of the committed date; plot it, don't clamp it, that's exactly
     the signal that should escalate rather than just intervene). Consumption can go negative
     (chain forecast to finish *ahead* of plan); **floor the display at 0%** but don't discard the
     underlying value — visible slack has its own value (an opportunity to pull downstream work
     earlier), flooring just keeps the chart itself focused on risk.

**This resolves the earlier open question about needing a baseline on every task — for the fever
chart's own math, specifically.** CPSL/PPF/Consumption% only ever need: the buffer's own
`baseline.duration`, the *terminal* task's baseline finish (`baseline.col + baseline.duration`),
and each chain task's *current* `state`/position — not a baseline on every single task along the
chain. A task added to a chain mid-execution (no baseline of its own) only affects the frontier
walk (its completion status), not any of the four formulas above.

**This is not a reason to narrow Stage 4's baseline capture back down.** Stage 4 deliberately
widened `capture_project_baseline` to snapshot *every* task, not just buffers, precisely because
the user wants to be able to retrospect after a project finishes — visualizing how the plan as a
whole differed from what actually happened, not just how the buffers fared. That's a separate,
still out-of-scope "full plan-vs-baseline comparison UI" (see "Explicitly out of scope" below) —
the fever chart just doesn't happen to need most of that data itself.

**Why history is captured proactively, not replayed retroactively (a real architectural
decision).** The obvious approach — reconstruct each historical chart point after the fact from
`remaining_duration_history` — doesn't work here. Ordinary chain tasks only log history when
*they themselves* receive a direct status update; a task's position can also change because a
neighboring task's cascade pushed/pulled it (Stage 2/3/6/7), and none of that leaves a trace on
the task that moved. So the terminal task's forecast finish "as of some past date" isn't reliably
recoverable after the fact — the same fundamental limitation that justified `buffer_size_history`
being captured live in Stage 7, rather than reconstructed from the cascade's history. Following
that precedent: after **every** `record_remaining_duration` call, recompute the four quantities
for every buffer *in that task's own project* and append `{'date': str, 'cpsl': int, 'ppf': int,
'forecast_lateness': int}` to a new `task['fever_chart_history']` list on that buffer (same
append-only pattern as `buffer_size_history`; percentages are derived from these raw numbers at
render time, not stored, so the zone-boundary formula can be re-tuned later without invalidating
history already captured).

**Bug found and fixed during testing: cross-project bleed.** This app supports several concurrent
projects on one canvas (rolling-wave planning). `capture_fever_chart_snapshot()` initially looped
over *every* buffer in the whole model unconditionally — so recording a status update in Project
One also logged a redundant point onto Project Two's completely unrelated buffers (same values,
just a spurious extra timestamp, since Project Two's own tasks hadn't actually changed). Fixed by
scoping the recompute to the triggering task's own `project_id`
(`capture_fever_chart_snapshot(project_id=...)`); verified two independent projects each only log
points from their own status updates. Known remaining simplification: an explicit *cross-project*
dependency link (rolling-wave planning allows these structurally) could legitimately affect a
different project's buffer, and this scoping wouldn't catch that — accepted as an edge case rather
than threading affected-project-tracking through the whole cascade for it.

**Zone model** — unchanged from the earlier discussion: sloped diagonal boundaries (not flat
thirds), approximated from the reference chart
(https://www.critical-chain-projects.com/medias/images/fever_chart_mono_projet_en.png) as `y =
slope·x + yellow_intercept` and `y = slope·x + red_intercept`, defaults `slope=0.55,
yellow_intercept=10, red_intercept=27` from that reading. **New**: these three constants become
per-project settings (`project['fever_chart_slope']`, `project['fever_chart_yellow_intercept']`,
`project['fever_chart_red_intercept']`), editable via the `Manage Projects...` dialog (extending
its existing per-project fields — assumed rather than a wholly separate "Project Settings" dialog,
since that's the established per-project settings surface; revisit if that assumption is wrong)
so different projects can carry a different risk appetite.

**Trajectory**: one point per `fever_chart_history` entry, connected by a line so trends are
visible by eye, each point labeled with its date (matching the reference chart's `W1..Week 6`
weekly-snapshot style) — not just today's single dot.

**Rendering**: `UIComponents.draw_fever_chart(canvas, buffer_task, project, x0, y0, width, height)`
(`ui_components.py`) — hand-drawn on a Tkinter `Canvas` (sloped zone bands as filled polygons,
trajectory connected point-to-point with each dot colored by its own zone via
`classify_fever_chart_zone`, axis ticks/labels, date labels per point), consistent with how the
rest of the app already draws everything (the task grid, dependency arrows) rather than adding a
charting dependency. Reused identically by both access points below.

**Access points, implemented:**
- Right-click a buffer task → `View Fever Chart...` (`task_operations.py:view_fever_chart`,
  mirrors `View Buffer History...`) — a single buffer's chart, with guard messages if the task
  isn't actually typed as a buffer or its project isn't executing yet.
- `Projects` menu → `Project Fever Charts...` (`task_operations.py:view_project_fever_charts`) —
  prompts for a project if there's more than one (reusing `OptionSelectDialog`), then shows every
  buffer's chart for that project stacked in a scrollable dialog.
- `Manage Projects...` dialog extended with three new fields (Fever Chart Slope, Yellow Intercept,
  Red Intercept), validated as numbers, wired to `model.update_project`.

**Export (originally scoped as a fast-follow, now built as part of the same round of testing)**:
- `ExportOperations.export_fever_charts(project)` (bulk) and
  `ExportOperations.export_single_fever_chart(buffer_task, project)` (one buffer) —
  `export_operations.py`. Both independently redraw the chart with PIL at 1600×1200 (far higher
  resolution than the on-screen canvas, requested specifically so charts can be zoomed into for
  manual annotation/distribution), via a new module-level `_draw_fever_chart_image` helper that
  mirrors `draw_fever_chart`'s math exactly — same "redraw per format" pattern as every other
  export in this codebase.
- `Download All (High-Res PNG)...` button on the `Project Fever Charts` dialog;
  `Download (High-Res PNG)...` button on the single-buffer `View Fever Chart` dialog.
- A label-overlap bug (the "% buffer consumed" axis title colliding with tick labels or the chart
  title depending on chart size) was found by visually inspecting the actual rendered output
  (headless Tk + `canvas.postscript()` + Ghostscript, and the PIL image directly) — fixed by
  repositioning the label above the plot area in both renderers, not just one, so they stay
  visually consistent with each other.
- Verified: headless render of both the Tkinter and PIL versions, visually inspected as actual
  images (not just "no exception raised") — zones, colors, trajectory, and labels all correct and
  non-overlapping. Confirmed manually in the running app for both charts, both export buttons.

**CSV data export (Stage 9 — done)**, a further extension so the underlying numbers can be dropped
into Excel or fed into a PMO reporting system, not just consumed as a rendered image:
- `ExportOperations.export_fever_chart_data(project)` (`export_operations.py`) — one long/tidy CSV
  per export (not one file per buffer), columns `Project`, `Buffer ID`, `Buffer Description`,
  `Buffer Type`, `Date`, `CPSL`, `PPF`, `Progress %`, `Baseline Buffer Duration`,
  `Forecast Lateness`, `Consumption %`, `Zone` — mirrors why the existing task/resource CSV export
  is already structured as one table rather than many small files.
- `Progress %`/`Consumption %`/`Zone` are recomputed at export time from the same raw
  `fever_chart_history` entries and the project's own zone settings that
  `_draw_fever_chart_image`/`draw_fever_chart` already use for rendering, via the same
  `classify_fever_chart_zone` helper — so these numbers can never disagree with the chart images.
  Nothing new is stored for this.
- Reuses `export_fever_charts`' exact project-selection flow and execution-phase guard rather than
  duplicating either — a project still in planning has no `fever_chart_history` to export
  (`compute_fever_chart_point` already returns `None` outside execution), so the guard is free.
- `Download Data (CSV)...` button added alongside `Download All (High-Res PNG)...` on the
  `Project Fever Charts` dialog (`task_operations.py:view_project_fever_charts`).
- Verified headlessly against a real model: built a project with a feeding buffer and a project
  buffer, each with multiple `fever_chart_history` entries, exported, then re-read the CSV and
  hand-checked the zone math for every row against `classify_fever_chart_zone`'s formula (all
  matched); confirmed the execution-phase guard short-circuits before ever opening a save dialog
  for a still-planning project.

**Resolved** (previously "not yet resolved" above): the branching-feeder-path PPF question is
resolved — see item 2 above (sort by finish, not dependency order) — verified with a headless test
(two parallel paths, one done, one not, merging into a shared terminal task: frontier correctly
capped by the earlier-finishing incomplete task regardless of the other path being fully done and
finishing later; correctly advances once both paths catch up). The `Project Fever Charts`
multi-buffer layout question remains genuinely open — see "Open questions".

## Remaining work

(Stage 9, fever chart CSV data export, is done — see "Fever chart reporting (Stage 8 — done)"
above.)

### Stage 10 — Backlog Full Kit readiness report

A different kind of report from the fever charts above, and explicitly **not** execution-only:
full-kit readiness matters throughout a project's life - during planning, to make sure near-term
work is being prepped ahead of execution kicking off; during execution, for whatever's still
queued up but hasn't started. Applies regardless of `project['phase']`.

- **"Backlog"** = a project's tasks that haven't started yet (`actual_start_date is None`) - the
  queue of upcoming work, derivable directly from data already on every task, no new field needed.
- **Report content**: for a chosen project, the % of backlog tasks with `fullkit_date` set (ready)
  vs not, plus a listing of individual backlog tasks - sorted soonest-to-start first (by `col`),
  since imminent tasks lacking a full kit are the actual risk, not distant ones - each showing its
  full-kit status and scheduled start.
- **Access point**: proposed `Projects` menu → `Backlog Full Kit Report...`, alongside `Manage
  Projects...` and `Project Fever Charts...` - same project-selection flow as those (prompt if more
  than one project), but *without* the execution-phase guard the other two have.
- **Format**: a simple listing dialog (mirrors `View Duration History...`/`View Buffer History...`)
  rather than a chart - there's no second axis or trend here, just a percentage and a sorted list,
  so a chart would be overkill.
- Not yet decided: whether this should also get a CSV/image export like the fever charts, or stay
  on-screen only for now (leaning on-screen only until asked otherwise, consistent with how Stage 8
  started before export was requested as a fast-follow).

### Stage 11 — Filter menu restructure + marquee-select

Prompted by manual testing making it clear the app needs more/clearer ways to select and filter
tasks and resources: the `Tags` top-level menu no longer describes what it does now that
project-based filtering is being added alongside tag-based filtering, and multi-select's only
input (`Ctrl+click`, one task at a time) is a poor fit for its main real use case - selecting a
cluster of tasks to move together while manually rebalancing resource loading.

**Filter menu (replaces `Tags`)**

- Rename the `Tags` top-level menu to `Filter`. Item order:
  1. `Filter Tasks by Tags...` (existing, unchanged)
  2. `Filter Tasks by Project...` (new)
  3. `Filter Resources by Tags...` (existing, unchanged)
  4. *(separator)*
  5. `Select Tasks by Tags...` (existing, unchanged)
  6. `Toggle Multi-Select Mode` (existing item; behavior extended - see marquee-select below)
  7. *(separator)*
  8. `Clear All Filters` (existing, extended to also reset the project filter)
- **`Filter Tasks by Project...`**: checkbox list of `model.projects`. A task belongs to exactly one
  project (`task['project_id']`), so - unlike the tag filter - this is inherently OR logic among
  checked projects (a task matches if its project is *any* of the checked ones); no AND/OR toggle
  needed. Combines with an active tag filter as AND (must match both), consistent with how the
  existing task/resource tag filters already combine internally.
- **No `Filter Resources by Project`.** Confirmed out of scope: resources are deliberately shared
  across projects (rolling-wave planning), so "this resource belongs to project X" isn't a
  meaningful direct filter the way it is for tasks. If a resource-side view ends up needed later,
  it'd be a *derived* filter (resources with at least one task in the selected project(s)), not a
  new field - revisit only if actually requested.
- **Likely implementation shape**: `tag_operations.py` gains `task_project_filters` (a list of
  project ids) alongside the existing `task_tag_filters`/`resource_tag_filters`, plus
  `filter_tasks_by_project()` (opens a simplified version of the existing `TagFilterDialog` - no
  AND/OR toggle needed) and `get_filtered_tasks()` extended to AND against it. `clear_all_filters`
  (`task_manager.py`) and `update_filter_status()` both need to know about the new filter dimension
  too, so the status bar correctly reflects it (e.g. `Tasks: ANY of [urgent] | Project: Kitchen
  Renovation`).

**Marquee-select**

- Today, click-dragging on empty task-grid space *creates a new task* (existing rubber-band
  behavior in `task_operations.py`/`ui_components.py`), and `Ctrl+click` only adds to
  `selected_tasks` when Multi-Select Mode is already toggled on - otherwise Ctrl is ignored and any
  click collapses to a single selection.
- **Design**: reuse the existing Multi-Select Mode flag as the switch for what an empty-space drag
  does, rather than introducing a new modifier key to remember:
  - Mode **off** (default): empty-space drag creates a new task, exactly as today - untouched.
  - Mode **on**: empty-space drag instead draws a marquee (selection) rectangle; on release, every
    task whose bounding box overlaps the rectangle becomes the selection (replacing whatever was
    previously selected). `Ctrl+click` continues to work exactly as it does today for adding/
    removing individual tasks from whatever the marquee last produced.
- **Likely implementation shape**: the existing rubber-band drag handlers (`on_task_press`/
  `on_task_drag`/`on_task_release`-equivalents around the `self.controller.rubberband` canvas
  rectangle in `task_operations.py`) branch on `self.controller.multi_select_mode` at the point
  where they currently assume "empty space drag = new task": if the mode is on, skip task creation
  and instead hit-test the rectangle against `task_ui_elements` on release, building the new
  `selected_tasks` list and calling `ui.highlight_selected_tasks()` - which, thanks to the status
  bar fix earlier this session, will already show a live "N tasks selected" count without further
  changes needed there.
- **Interaction to watch for**: dependency-link connector points (the small circles at task
  corners used to draw predecessor/successor links) are hit-tested within the same canvas region -
  need to confirm a marquee-mode drag starting near a connector doesn't get misinterpreted as
  starting a dependency link instead of a marquee. Not yet investigated; flag during implementation.
- Bulk-move (drag one selected task to move the whole group, already implemented via
  `on_task_drag`'s existing `len(selected_tasks) > 1` check) is unaffected by this - marquee-select
  only changes how the *selection* is built, not what happens once tasks are selected.

### Stage 12 — Hand-verified fever chart scenario + regression test

Every fever chart fix so far this session (the cross-project isolation bug, the PPF branching-path
sort-by-finish fix, the CSV export numbers) was verified with a one-off headless script written for
that specific change, then discarded - there's no standing, durable test that would catch a future
change accidentally reintroducing one of those exact bugs. The underlying formulas
(`compute_fever_chart_point`, `classify_fever_chart_zone`) are also intricate enough (frontier
walk across parallel feeder paths, buffer absorb-then-overflow, per-project sloped zone
boundaries) that spot-checking arithmetic in isolation, the way Stage 9's CSV numbers were
verified, isn't the same as confirming the *whole* day-by-day trajectory a real execution would
produce is correct.

- **Work through a full scenario by hand, day by day.** Build a small project with a critical chain
  plus at least one feeding chain/buffer (and ideally one with a branching/merging feeder path, to
  exercise the Stage 8 PPF fix specifically), then walk it forward one simulated day at a time via
  `record_remaining_duration`, capturing a fever chart point at each step. At every step, hand-
  calculate the expected CPSL, PPF, Progress %, Consumption %, and Zone from the raw task
  data - independently of the code - and compare against what `compute_fever_chart_point`/
  `classify_fever_chart_zone` actually produce. The goal is confidence in the *narrative* (a buffer
  correctly absorbing early, then correctly tipping into yellow/red as delays accumulate), not just
  that individual formulas are internally consistent with each other.
- **Turn that scenario into an automated regression test** once hand-verified - likely a new
  `tests/test_fever_charts.py` (or an addition to `tests/test_scenarios.py`, which already has this
  session's precedent for narrative/day-by-day integration tests), asserting the exact expected
  CPSL/PPF/Progress %/Consumption %/Zone at each simulated day. This is the part that actually
  protects future work: any change to the fever chart math that breaks this test fails loudly in
  CI/`run_tests.py`, instead of relying on someone remembering to re-derive and re-verify by hand.
- Worth covering in the same scenario (or a second one) if the first pass doesn't naturally exercise
  it: a feeding buffer fully consumed (overflow into the critical chain, Stage 7) and the
  cross-project isolation fix (a second, unrelated project's buffers must show zero change from an
  update to the first project's tasks).

## UI polish backlog (not CCPM-specific, but worth fixing)

Small, unrelated-to-CCPM items flagged during this session's testing — not urgent enough to stop
and fix immediately, but real annoyances likely to be hit by other testers too, and distracting
from evaluating the actual planning features. Worth picking up opportunistically.

- **Keyboard zoom shortcuts.** Zoom currently only works via `Ctrl` + mouse wheel/middle-mouse
  (fixed earlier this session for Linux's `Button-4`/`Button-5` scroll events). Add `Ctrl-+` (zoom
  in) and `Ctrl--` (zoom out) as keyboard equivalents, reusing the same `on_zoom` logic the scroll
  handler already calls. Should bind both the shifted `+` key and the unshifted `=` key on the same
  physical key (`<Control-plus>`/`<Control-equal>`), since requiring the shift key for zoom-in but
  not zoom-out is an easy inconsistency to trip over.
- **Text overflow at higher zoom levels.** Two spots noticed so far:
  - Timeline header text (dates/column labels) overflows its row once zoomed in past some point -
    font size doesn't appear to be capped/scaled sensibly relative to the row height at high zoom.
  - The resource loading indicator's text (allocation/percentage shown per grid cell) overflows its
    own cell similarly, making it hard to read at higher zoom.
  - Not diagnosed further yet - likely needs the font size to be clamped against the actual
    cell/row pixel size at the current zoom level, rather than scaling unbounded with zoom.
- **Resource panel not resizing with the window (fixed, took several iterations).** Originally
  reported as a grey dead-space block beneath the last resource row at a small default window
  size; re-reported after maximizing as the label column simply not growing into the newly
  available space; final report was the splitter bar becoming impossible to drag up at all after
  maximizing (it kept sliding back down and clamping near the footer). All three turned out to be
  the same underlying design problem surfacing in different ways, not independent bugs -
  `task_frame` and `resource_frame` were both packed with `fill=tk.BOTH, expand=True` in
  `main_frame`, which makes Tk's own pack manager equally-split *any* extra space between them on
  every relayout, regardless of their current sizes or of whatever the code had explicitly
  configured. That's an unpredictable, code-fighting-the-toolkit setup: a `Canvas` widget doesn't
  auto-track its parent's growth once given an explicit height (unlike a `Frame`), so patching the
  canvases' heights via a `<Configure>` handler bound to `resource_frame` only fixed the symptom
  visible at the time, each time surfacing the next problem underneath:
  1. Canvas heights explicitly bumped via `.config(height=...)` on every resize, but
     `resource_label_frame`/`resource_scroll_frame` had no `pack_propagate(False)`, so each bump
     inflated its parent's own *requested* size, cascading all the way up through
     `resource_frame` -> `main_frame` -> `horizontal_layout_frame` -> root - eventually making
     root's requested height exceed the actual window and squeezing `status_bar` (packed on root,
     `side=tk.BOTTOM`, after this whole tree) down to an unmapped 1px. It only flickered into view
     while manually dragging the window edge (briefly giving Tk enough real pixels to satisfy the
     inflated request).
  2. Adding `pack_propagate(False)` to those two frames (mirroring `task_frame`) stopped that
     cascade, but without an explicit height of their own, a `pack_propagate(False)` frame reports
     a natural size of ~1px - which starved `resource_frame`'s own share of Tk's equal-split
     against `task_frame` (whose explicit height gave it a much bigger natural size floor). That's
     what caused the splitter to seem to "clamp to the bottom": Tk's own layout negotiation kept
     re-allocating almost everything to `task_frame` regardless of what the drag handler tried to
     set.
  - **Actual fix**: stopped relying on Tk's `expand=True` equal-split entirely. Removed
    `expand=True` from both `task_frame.pack(...)` and `resource_frame.pack(...)`; gave
    `resource_frame` its own `pack_propagate(False)` + explicit `height=resource_grid_height`
    (matching `task_frame`); and replaced the `resource_frame`-scoped `<Configure>` binding with one
    on `main_frame` (`on_main_frame_configure` in `ui_components.py`) that explicitly computes and
    sets *both* frames' heights on every resize, preserving whatever task:resource height ratio is
    currently in effect (startup default, or the user's last manual drag) rather than either frame
    unpredictably keeping the extra space for itself. `on_resizer_drag` was updated to match
    (it previously relied on `resource_frame` auto-tracking natively, which no longer happens with
    `expand=True` removed, so it now explicitly sets `resource_frame`'s own height too, not just the
    two canvases inside it). The fixed overhead (timeline frame, h-scrollbar, resizer bar, and all
    the `pady` spacing between them) is measured once empirically right after widget creation
    (`self._pane_overhead`) rather than guessed as a hardcoded constant - an under-estimate here was
    exactly what caused `main_frame`'s true requirement to still slightly exceed its actual size and
    re-starve the status bar even after the `pack_propagate(False)` fix.
  - **Verified** by instrumenting a real `TaskResourceManager`: resized the root window from
    600px to 1200px tall, then simulated a splitter drag up 150px followed by down 150px via direct
    calls to `on_resizer_press`/`on_resizer_drag`/`on_resizer_release`. Confirmed at every step:
    `status_bar.winfo_ismapped()` stays `1` at its full 57px height; `task_frame`/`resource_frame`
    change by exactly the dragged amount and fully reverse (659/334 -> 509/484 -> back to 659/334);
    `resource_frame` grows proportionally on the maximize step (132px -> 334px) rather than staying
    pinned at its startup size.
  - **Follow-on: dead grey space when there are few resources (fixed).** Once the panel correctly
    tracked window size, maximizing with only a handful of resources (e.g. the 10-resource sample
    project) reserved far more height than the actual rows needed, leaving a large blank area below
    the last resource row - functionally the original dead-space complaint again, just for a
    legitimate reason this time (the panel's *reserved* height growing with the window, exactly as
    fixed above, while its *content* stayed the same). Fixed by having the resource pane give back
    whatever part of its ratio-driven share its actual content doesn't need, to `task_frame`,
    instead of leaving it as blank canvas background. `resource_grid_ideal_height` tracks the
    ratio/drag-driven ceiling separately from `resource_grid_height` (the actual, content-fitted
    height applied to the widgets), so the panel can still grow back up to that ceiling if content
    grows later (more resources added, a filter cleared, zooming in) without needing another window
    resize to recompute it from scratch. Implemented as a shared `_fit_resource_pane` helper used by
    `on_main_frame_configure`, `on_resizer_drag`, and `draw_resource_grid` (the last one re-fits on
    every redraw, since resource count/filters/zoom can change independently of any resize). Also
    had to cap `on_resizer_drag`'s `new_task_height` at `total_available - 100`, otherwise dragging
    the splitter down far enough could grow task_frame into resource_frame's 100px floor and
    (rarely) squeeze the status bar again the same way. Verified with the 10-resource sample data:
    after maximizing, `resource_frame` clamps to exactly `content_height` (300px, not the larger
    ratio-implied share) with the surplus going to `task_frame`, while a 50-resource project (whose
    content exceeds the ratio-implied share) correctly keeps the full share and would scroll -
    confirming this doesn't regress the already-working case.
  - **Residual: small gap still reported at 169% zoom (unresolved, low priority).** After the fix
    above, the user still saw a smaller version of the same dead-space strip below the last
    resource row at a specific window size + zoom (169%) with the 10-resource sample project, and
    noted they can live with it. Re-tested several matching scenarios (various window sizes,
    zoomed to 1.69, both before and after a window resize) and could not reproduce a positive gap
    in any of them - `resource_frame`'s height always came out either an exact match for
    `content_height` or smaller (correctly triggering scroll instead of showing dead space), per
    the same `_fit_resource_pane` logic above. Whatever's left in the reported screenshot is likely
    a small (few-pixel) rounding/timing residual rather than the same structural bug - left
    unresolved rather than guessed at further, since it wasn't reproducible and the user isn't
    blocked on it. Worth another look if it turns out to be bigger/more consistent than that.
- **Multi-select status indicator kept silently disappearing (fixed).** The user reported
  repeatedly losing track of whether multi-select mode was still on while testing. Root cause: both
  `toggle_multi_select_mode` and `highlight_selected_tasks()` wrote their "Multi-select mode:
  ON..."/selection-count text into the *same* `filter_status` label used for the tag-filter
  summary. `update_filter_status()` runs on every `update_view()` - i.e. after almost any edit,
  move, or drag - and unconditionally overwrites that label back to the filter summary, silently
  wiping the multi-select message even though `multi_select_mode` was still `True` underneath.
  Fixed by giving multi-select its own persistent `multi_select_status` label
  (`task_manager.py`), driven by a single `update_multi_select_status()` method that shows
  mode-on-with-no-selection vs. a live selected-task count, called from
  `toggle_multi_select_mode`, `highlight_selected_tasks()`/`clear_selections()` (so it updates the
  moment selection changes), and `update_view()` itself (so it can never drift out of sync with a
  redraw the way the old shared-label version did). Verified headlessly: toggled multi-select on,
  selected two tasks, then triggered an unrelated `update_view()` (simulating an unconnected filter
  change) - the multi-select label correctly still read "2 tasks selected" afterwards, with the
  filter-status label showing its own text independently alongside it.

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
  auto-inserting `PB`/`FB` buffer tasks is **not** being automated. The user creates buffer tasks,
  marks task types, and (Stage 5) assigns chains manually; the tool's job is to react correctly
  (via Stages 2–7) to whatever graph currently exists, not to construct that graph for them.
- **Fever chart PNG export is done** (see Stage 8 above) — built as PIL redraws at 1600×1200,
  following the same "redraw per format" pattern as every other export in this codebase. PDF export
  specifically was never actually requested (PNG covered the "high resolution for annotation" need)
  and isn't planned unless asked for. Rejected alternative considered for either format: Tkinter's
  `canvas.postscript()` + Ghostscript conversion, which would pull in an external system dependency
  with the same cross-platform fragility already seen with `uv`/Tkinter on Linux and Windows.
- **Full plan-vs-baseline comparison UI** (showing stakeholders "the whole plan, then vs. now,"
  not just a single buffer's fever chart). Stage 4's widened baseline capture is preparation for
  this, but the comparison UI itself is not part of this work.
- **Resource-constrained critical chain / resource leveling.** `network_operations.py`'s existing
  critical-path calculation (`calculate_critical_path`) is plain CPM (no resource contention
  awareness). Relatedly, Stage 6's execution-phase cascade only reacts to *declared* dependency
  links — it has no visibility into implicit dependencies caused by two chains competing for the
  same constrained resource (the classic CPM-vs-CCPM distinction: the critical chain, unlike the
  critical path, can be forced through a feeding chain purely by resource contention, with no
  logical link involved at all). Not addressed by anything in this document.

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
- `src/operations/file_operations.py` — `New`/`Open`/`Save`, and `import_ccpm_schedule` (CCPM
  schedule.csv import).
- `src/operations/export_operations.py` — PDF/PNG/CSV exports, fever chart PNG export.
- `src/operations/tag_operations.py` — tag-based task/resource filtering and selection
  (`get_filtered_tasks`/`get_filtered_resources`, `TagFilterDialog`) - Stage 11 extends this with
  project-based filtering.
- `sample-ccpm-projects/` — real sample CCPM schedules used to test the importer; `file-structure.md`
  documents the expected CSV format.

## Open questions for whoever picks this up next

- Whether "the merge task" in Stage 3/7 (a buffer's `FS`/`FB` successor) needs to be uniquely
  identifiable — i.e., what happens if a buffer somehow has more than one such successor. Not
  discussed; likely worth a guard/validation when this is built. `chain_id` doesn't resolve this
  ambiguity by itself.
- Whether removing a `Chains` entry that's still referenced by tasks should be blocked, or should
  null out `chain_id` on those tasks — not discussed. (`remove_project` sets the precedent of
  unassigning rather than blocking.)
- Whether a buffer's `chain_id` should be validated against the chain(s) of the tasks feeding it
  (e.g. warn if inconsistent) — not discussed; currently assumed trusted/unvalidated, consistent
  with everything else in this system that the user sets manually.
- Whether the progress-stripe/chain-stripe edge assignment (progress stripe implemented on the
  bottom edge in Stage 4; top edge reserved for Stage 5's chain color) reads well once the chain
  stripe is added, or should be swapped.
- **Stage 8**: the sloped zone boundary defaults (`slope=0.55, yellow_intercept=10,
  red_intercept=27`) are a visual approximation from a reference screenshot, not a verified
  canonical formula - reasonable starting defaults now that they're per-project settings, but not
  authoritative.
- **Stage 8**: whether `Manage Projects...` is really the right home for the fever chart
  slope/intercept settings, or whether a dedicated "Project Settings" dialog is warranted once
  there's more than one or two per-project tunables to hold.
- **Stage 8**: exact layout of `Project Fever Charts` when a project has several feeding buffers -
  side-by-side small multiples, a scrollable stack, tabs? Not discussed.
