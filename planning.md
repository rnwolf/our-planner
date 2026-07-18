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

All of the following is built, tested (`uv run pytest`, 115 tests passing), and manually verified
in the running app. **Stages 1-15 (see each "Stage N — done" heading below) are now complete** —
the original 7-stage build order, Stage 8 (fever chart reporting, including PNG export) and Stage 9
(fever chart CSV data export) added once Stages 4/7's data capture made them practical to build,
Stage 10 (Reporting framework - new derived filter dimensions plus a pluggable `Reports` menu, with
Full-Kit Readiness as the first new report type; Fever Charts, Stage 8, stay as-is but are now
discoverable from the same menu), Stage 11 (task/project filtering + marquee-select), Stage 12 (the
remaining fever chart hand-verification: a full multi-update narrative test, feeding-buffer
full-consumption/overflow, and cross-project isolation), Stage 13 (rolling timeline compaction /
"Delete History...", including a latent baseline-shift bug fix found while designing it), Stage 14
(Optimal/Realistic terminology rename), and Stage 15 (merge-point pull rule + feeding-buffer
shock-absorber fix, prompted by hand-verifying the fever chart math for Stage 12). **Stage 16
(CCPM round trip with the external scheduler) is also done — see its section.** **Still open**:
Stage 17 (resource buffer,
a third manual buffer type, design discussion only, not scheduled) — see "Remaining work" below.
**Stage 18 (network graph report) is done — see its section.**
**Stage 19 (import/export consistency — tags/colour round trip, notes.txt instead of unbounded
dialogs, slimmer resources CSV, `id:allocation` resource tokens, snake_case column alignment with
ccpm-scheduler) is done on the our-planner side — see its section; two scheduler-side items
(column passthrough, allocation tokens) carry over to the ccpm-scheduler repo's plan.**
**Stage 20 (CCPM Method per project — selectable buffer sizing: cap/hchain/rsem, riding
ccpm-scheduler 0.9.0's buffer_method knob) is done — see its section.**
What's left after that is everything listed under "Explicitly out of scope" (automated
critical-chain detection, resource-constrained scheduling, event sourcing, full plan-vs-baseline
comparison UI).

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
hand in the UI. Format documented in `docs/file-structure.md`, which also holds
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

### Task/project filtering + marquee-select (Stage 11 — done)

Prompted by manual testing making it clear the app needed more/clearer ways to select and filter
tasks and resources - the `Tags` menu no longer described what it did once project-based filtering
joined tag-based filtering, and `Ctrl+click`-only multi-select was a poor fit for its main real use
case (selecting a cluster of tasks to move together while rebalancing resource loading).

**Filter menu (renamed from `Tags`)** - `ui_components.py`:
- `Filter Tasks by Tags...`, `Filter Tasks by Project...` (new), `Filter Resources by Tags...`,
  `Select Tasks by Tags...`, `Toggle Multi-Select Mode`, `Clear All Filters` - same order as spec'd.
- `ProjectFilterDialog` (`tag_operations.py`) - a checkbox list of `model.projects`, deliberately
  simpler than `TagFilterDialog` (no match-all toggle): a task belongs to exactly one project, so
  checking several is inherently OR logic among them.
- `TagOperations.task_project_filters` (list of project ids) + `filter_tasks_by_project()` /
  `apply_task_project_filter()`. `get_filtered_tasks()` ANDs it against any active tag filter -
  build the tag-filtered list first (or start from `model.tasks` if no tag filter), then narrow to
  tasks whose `project_id` is in the selected set.
- No project filter for resources - confirmed out of scope, since resources are deliberately shared
  across projects (rolling-wave planning); revisit only as a derived filter if actually requested.
- `clear_task_filters()` and `has_active_filters()` both extended to include the project filter;
  `update_filter_status()` (`task_manager.py`) shows it alongside the tag summary, e.g. `Tasks: ANY
  of [urgent] | Project: Kitchen Renovation`.

**Marquee-select** - `task_operations.py`/`task_manager.py`:
- Reuses the existing Multi-Select Mode flag rather than a new modifier key: mode off, an
  empty-space drag creates a new task exactly as before (fully unchanged code path); mode on, the
  same drag instead draws a free (not grid-snapped) selection rectangle via a new
  `marquee_select_in_progress`/`marquee_start` pair of controller attributes, and on release every
  task whose bounding box overlaps the rectangle (any intersection, not just full containment)
  becomes `selected_tasks`, replacing whatever was selected before. `Ctrl+click` is untouched and
  still adds/removes individual tasks from the result.
- Dependency-link connector points needed no special handling - `on_task_press`'s connector
  hit-test already runs before the "empty space" branch entirely, regardless of
  `multi_select_mode`, so a marquee-mode drag starting near a connector still correctly starts a
  dependency link instead. Confirmed by test rather than assumed.
- Bulk-move (dragging one selected task to move the whole group) is untouched - marquee-select only
  changes how the selection is built.
- Verified headlessly against a real `TaskResourceManager`: marquee drag with mode on selects the
  tasks under the rectangle and leaves `new_task_in_progress` false; the identical drag gesture
  with mode off still creates a task (task count increments by one, as before); pressing exactly on
  a connector point with mode on sets `dragging_connector`, not `marquee_select_in_progress`; and
  the project filter's AND-with-tags behavior, `has_active_filters()`, `clear_all_filters()`, and
  the status bar text were all checked directly against a model with two projects and mixed tags.
- **Follow-on bug found immediately in real use: dragging a task out of a multi-selection
  collapsed the group instead of moving it.** `on_task_press`'s task-body-click branch
  unconditionally did `selected_tasks = [task]` on any plain (non-Ctrl) click - so clicking a task
  specifically *to drag the whole group* (the main real use case marquee-select was built for)
  destroyed the selection down to that one task before the drag even started, exactly as if
  marquee-select had never run. Fixed by adding a check: a plain click on a task that's already
  part of a multi-selection (`len(selected_tasks) > 1`) now preserves the whole selection instead
  of collapsing it - only clicking a task *outside* the current selection still collapses it, the
  standard pattern from most GUI file managers/design tools. This also fixes the same latent bug
  for a multi-selection built via `Select Tasks by Tags...`, which doesn't require Multi-Select
  Mode to be on at all. Separately tightened the marquee overlap test itself from inclusive
  (`>=`/`<=`) to strict (`>`/`<`) comparisons while verifying this, since the sample data's
  tightly-packed tasks exposed that a task merely touching the marquee rectangle's edge (no real
  overlapping area) was being swept into the selection. Verified headlessly: marquee-selected two
  tasks, then simulated a plain click-drag starting on one of them - both moved together by the
  same delta and the selection stayed intact throughout; separately confirmed a plain click on a
  task *outside* an existing multi-selection still correctly collapses to just that task.
- **Follow-on bug found while preparing for Stage 12: connector-drag and edge-resize both silently
  stopped working (fixed, took two passes).**
  - **First pass**: found and fixed a real but, as it turned out, unrelated defect -
    `marquee_select_in_progress`, `dragging_connector`, and `new_task_in_progress` are all checked
    *before* the connector/edge-resize/move logic in `on_task_drag`, so if any one of them was ever
    left `True` because its own `on_task_release` never fired (e.g. the mouse released outside the
    canvas), every subsequent drag of *any* kind would silently short-circuit at that stale check.
    Fixed by resetting all three at the top of `on_task_press`. Verified headlessly and genuinely
    correct, but the user reported the original symptom was unchanged - this bug wasn't what they
    were hitting.
  - **Actual root cause, found via a live diagnostic + screenshot the user provided**: a temporary
    print added to `on_task_press` captured the real click at 300% zoom landing at canvas (419,
    413), 14px away from the connector's true center (405, 405) - a genuine, realistic mouse-aiming
    miss, not a logic bug. The connector's *drawn* radius scales with zoom (`draw_task` in
    `ui_components.py`) but its *hit-test* radius was a hardcoded 5px regardless of zoom (same for
    the edge-resize tolerance) - at high zoom the visibly-drawn dot extended past its own clickable
    area, compounding an already-too-tight 5px tolerance to begin with.
  - Fixed with a shared `connector_hit_radius()` (`task_manager.py`), used by both the drawing code
    and every hit-test (`on_task_press`/`on_task_hover` in `task_operations.py`) so they can never
    drift apart again, widened well beyond just matching the two: `max(8, min(20, 5 *
    zoom_level))` - 8px even at 100% zoom (up from 5px), scaling to 15px at the reported 300% zoom,
    comfortably covering the actual 14px miss observed. The edge-resize tolerance reuses the same
    value, on the reasoning that both are small, precise targets that should get *easier* to hit as
    the view zooms in, not stay pinned to a fixed pixel count regardless of how large everything
    else has gotten.
  - Verified by reproducing the user's exact reported click (canvas 419, 413 at 300% zoom) against
    task 4's real stored position (connector at 405, 405) - correctly resolved to
    `dragging_connector = True` after the fix, versus falling through to new-task-creation before
    it; separately confirmed edge-resize tolerates a comparably-imprecise (10px off) click too.
  - **Note for next time**: z-ordering was raised as a possible cause during investigation and
    ruled out directly rather than assumed - this hit-testing loops through stored coordinates in a
    fixed code order and never relies on Tkinter's canvas item stacking, so it can't be affected by
    which item renders on top.
  - **Still not fully resolved** - the radius fix measurably helped, but the user reports the
    interaction is still inconsistent (sometimes edge-resize, sometimes connector-drag, sometimes a
    plain move triggers instead) and, critically, `on_task_hover`'s cursor-change feedback isn't
    visibly working for them at all, making it hard to tell in advance what a click-drag will do.
    Added a **hover-state diagnostic** to the status bar (`hover_status` label, `task_manager.py`)
    as a more reliable substitute for the cursor cue - a plain text label doesn't depend on cursor
    theme/rendering working correctly on a given platform/WM the way a custom cursor shape does.
    `on_task_hover` (`task_operations.py`) now updates it at every branch (`Hover: Connector (Task
    N) - drag to link`, `Left edge`/`Right edge - drag to resize`, `Task N body - drag to move`,
    or `Hover: -` when over empty space), verified to update correctly for all four zones in a
    headless test. This also doubles as a debugging tool: if the label doesn't update as expected
    while actually hovering in the running app, that points to something more fundamental (event
    delivery not reaching `on_task_hover` at all) rather than a hit-zone sizing issue, which the
    radius fix already addressed. Root cause of the remaining inconsistency not yet found.
  - **Confirmed by the user: the hover-status label correctly reflects the detected zone, and the
    native cursor genuinely never changes on this platform/WM at all** - not a rendering flake, a
    real, apparently permanent limitation here. That reframes the label from "debugging aid" to the
    user's actual primary visual signal for what a click-drag will do, so it needed to hold up as
    one: widened from 28 to 48 characters (the longest message, `Hover: Right edge (Task 12) - drag
    to resize`, was being cut off) and given a background color per zone (`#cfe2ff` connector/URL,
    `#d4edda` edges, `#fff3cd` body, reset to the label's own captured default over empty space) -
    color rendering goes through Tk's own painting rather than the platform cursor-theme rendering
    that isn't working, so it doesn't depend on whatever is broken about cursors here. Verified
    headlessly: label width and all four background colors update correctly, including the reset
    back to the exact captured default over empty space.
  - **Follow-on: hover state got stuck on "drag to move" after moving the mouse away from a task.**
    `on_task_hover` is only bound to `<Motion>`, which exclusively fires while the cursor is
    *inside* task_canvas - so moving the mouse off a task's body straight out of the canvas
    entirely (into the timeline header, resource panel, or off the window), without passing over
    empty grid space first, never re-triggered `on_task_hover` to reset anything, leaving the last
    hover state stuck indefinitely. Fixed by extracting the existing reset logic into
    `reset_hover_state()` (`task_operations.py`) and binding it to `<Leave>` on `task_canvas`
    (`ui_components.py`) - Tk's dedicated "cursor exited this widget" event, which fires
    regardless of how the cursor left, closing exactly the gap `<Motion>` alone couldn't cover.
    Verified headlessly with a real `<Leave>` event after hovering a task body: label and cursor
    both correctly reset to their neutral state.
  - **Follow-on: the native cursor still doesn't render at all** (suspected Wayland/XWayland cursor
    theme issue, possibly tied to a pending OS update - being investigated by the user separately
    via a restart) - **but this matters, since the user will be watching the mouse position while
    working, not the status bar.** Added a canvas-drawn highlight directly at the hovered
    connector/edge/body as a platform-independent substitute: a blue ring around the connector
    (`create_oval`), a thick green line over whichever edge (`create_line`), and a dashed border
    around the task body (`create_rectangle`, deliberately dashed and a different color from
    `highlight_selected_tasks`'s solid orange so "hovering" and "selected" read as visually
    distinct) - all tracked via a single `hover_highlight_id` (`task_manager.py`) that gets deleted
    and redrawn fresh on every hover change, and cleaned up by `reset_hover_state` too. Since this
    is Tk's own canvas painting rather than platform cursor-theme rendering, it doesn't depend on
    whatever is broken about cursors here - confirmed working by the user. Also swapped the
    connector's cursor from `hand2` to `target` (a bullseye) on the user's suggestion - a better
    semantic fit for "aim here to drag out a link" than a plain pointing hand, which stays reserved
    for the "click to open" URL-hover case. Verified headlessly with carefully-isolated coordinates
    for each zone (an earlier pass had accidentally tested overlapping zones, e.g. a point that
    matches both the connector and the right edge since they share the same x-position): connector
    -> `target` cursor + blue oval, both edges -> `sb_h_double_arrow` + green line, body -> `fleur`
    + dashed rectangle, and `<Leave>` still correctly clears everything.
  - **Open issue, deliberately parked**: the user restarted their machine (hoping a pending
    Wayland/OS update was the cause) and the native cursor shape still does not render, even though
    `task_canvas.cget('cursor')` reports the correct value at every step (confirmed above) - so this
    is specifically a display/rendering problem, not a logic bug in this codebase, and not something
    a code change here is likely to fix. Not investigated further for now; the canvas-drawn
    highlight + hover-status label are the reliable, working substitutes in the meantime. Worth
    revisiting later if it turns out to matter more than it does today, but low priority given the
    substitutes already cover the actual need (knowing what a click-drag will do before committing
    to it).

### Rename "Aggressive" to "Optimal", clarify the three-duration workflow (Stage 14 — done)

The app's task-estimate terminology is now aligned to: **Realistic = Optimal + Contingency**.
"Aggressive" carried a negative emotional connotation (implying recklessness) that "Optimal"
doesn't, for what's meant to be a best-case/50%-confidence estimate. "Realistic" replaces "Safe,"
which implied hidden padding rather than a transparent, normal-contingency-included estimate.

**The real-world estimating conversation this models**, as explained by the user: ask the people
doing the work "how long will this take?" - that answer, which already has normal everyday
contingency baked in, is the **Realistic** estimate, captured first. Then ask "if everything went
perfectly, no disruptions, best case - how long?" - that's the **Optimal** estimate. The gap between
them is the task's individual contingency. A not-yet-built function is meant to eventually strip
that contingency out of each task, pool the sum of it into that chain's project/feeding buffer, and
re-schedule the now-shorter tasks against resource availability.

**`duration` (the field actually shown on the grid and used for scheduling) is not permanently tied
to one meaning - it changes over a task's lifecycle**: it starts out equal to the Realistic
estimate (what's naturally entered first, before any buffer-cutting has happened), and would later
be *overwritten* to the Optimal estimate once the buffer-cutting function (still not built) runs and
pools the difference into a buffer. This is why a separate, permanent field to remember the original
Realistic estimate was kept rather than retired, correcting this stage's own initial draft, which
had wrongly proposed retiring the "Safe" field entirely.

**Final field mapping, implemented as a full internal rename** (model field names, method names,
and all displayed text - not just a cosmetic label change, since the app hasn't been distributed
yet and this was the opportunity to fix the inconsistency properly):
- `duration` - unchanged name; its *role* is now documented at every definition site: the task's
  current, active, schedulable duration. Starts as a copy of the Realistic estimate; later may be
  reduced to the Optimal estimate once buffer-cutting (not yet built) runs.
- `aggressive_duration` -> **`optimal_duration`** (`task_resource_model.py`) - the captured "if
  everything went perfectly" estimate. Optional/nullable until explicitly set, same as before.
  `set_aggressive_duration` -> `set_optimal_duration` (model and `task_operations.py` wrapper);
  `Set Aggressive Duration...` menu item -> `Set Optimal Duration...` (`ui_components.py`).
- `safe_duration` -> **`realistic_duration`** (`task_resource_model.py`) - the captured "how long
  will this really take" estimate, defaulting to a copy of `duration` at task creation and
  preserved unchanged even if `duration` itself is later reduced - a permanent historical record of
  the original estimate. `set_safe_duration` -> `set_realistic_duration`.
- `baseline` snapshot dict's `safe_duration` key -> `realistic_duration` (`capture_project_baseline`
  and its consumers in `task_operations.py`'s details dialog).
- All UI text updated to match: task tooltip and task details dialog now show `Optimal Duration: N
  days` / `Realistic Duration: N days` / `Baseline Realistic Duration: N days`.

**No migration needed** - the user confirmed old `sample-*.json` files can simply be deleted and
re-saved fresh now that the rename is done, rather than needing a load-time key migration. The
existing backward-compatibility repair pattern in `load_from_file` (fill in a default if a field is
missing) was kept, just updated to the new key names - an old save file with the old key names
gets fresh defaults for the new ones (silently losing whatever was in the old fields), an explicitly
accepted outcome given no migration was requested.

**Verified clean by grep**: zero remaining occurrences of `aggressive_duration`, `safe_duration`,
`set_aggressive_duration`, `set_safe_duration`, `Aggressive Duration`, or `Safe Duration` anywhere
under `src/` or `tests/` after the rename.

**Still-open asymmetry, not resolved by this stage**: `model.set_realistic_duration` is defined but
still never called from anywhere in the operations/UI layer - there's no `Set Realistic
Duration...` menu item, unlike Optimal. Fine for *initial* capture (`duration` already captures the
Realistic estimate at creation time), but there's still no way to *edit* the preserved
`realistic_duration` after the fact. Left as-is, since it's arguably only needed once the
buffer-cutting function actually exists.

**Test coverage added** (per explicit user request to use this refactor as an opportunity to check
test coverage of key functionality): surveying the existing suite (~40 tests, ~1,490 lines across
9 files) found essentially zero coverage of any of this session's CCPM-specific work (chains,
buffers, fever charts, baseline capture, phase transitions, marquee-select/filtering, or the
duration fields being renamed here) - the only file matching a broad grep, `test_critical_path.py`,
tests the unrelated pre-existing plain-CPM algorithm in `network_operations.py`. Given the size of
that gap, the user explicitly scoped this session's test-writing to the Stage 14 area only, leaving
the broader gap (chains, buffers, phase transitions, fever charts, marquee-select) as a
separately-scoped future follow-up.

New `tests/test_duration_estimates.py` (14 tests) covers, against the real model rather than a
one-off headless script:
- `add_task` defaults: `realistic_duration` copies `duration`, `optimal_duration` starts `None`.
- `set_optimal_duration`/`set_realistic_duration`: update the intended field, leave `duration` (and
  the other duration field) untouched, and return `False` for a non-existent task id.
- `capture_project_baseline`: the baseline snapshot correctly records `realistic_duration` as of the
  moment it's captured, and - the specific regression this field exists to prevent - survives later
  changes to `duration`/`realistic_duration` unaffected; also covers the task-count return value and
  the `-1` return for an unknown project.
- Save/load round trip: `optimal_duration`/`realistic_duration` survive a real `save_to_file`/
  `load_from_file` cycle through an actual temp file.
- Backward-compatible load repair: a hand-built legacy save file missing both fields entirely loads
  cleanly with `realistic_duration` defaulted from `duration` and `optimal_duration` defaulted to
  `None`, exercising the exact fallback branch added to `load_from_file`.

Full suite (`uv run pytest tests/ -q`): **54 passed** (40 pre-existing + 14 new), 0 failures.

### Merge-point pull rule and the shock-absorber fever signal (Stage 15 — done)

Triggered by a real bug found while hand-verifying the fever chart math on a merge scenario, as
part of Stage 12's "work through a full scenario by hand" exercise (C1 critical 0–5; F1 feeding
0–3; FB 3–8, baseline 5d; C2 merge 8–13): recording a routine "on track, no change" status update
on C1 fired Stage 6's bidirectional cascade, which set `C2.col = C1.finish` from whichever single
link was cascading — ignoring the feeding path — yanking C2 to day 5 and dragging the glued buffer
with it. The merge task was whipsawed by whichever predecessor last fired: exactly the "merge task"
ambiguity previously parked in the open questions below.

**The design conversation that shaped the fix** (user's train analogy vs relay runners): waiting
for planned dates is timetable thinking — CCPM wants the next runner lined up the moment the
baton *can* arrive. But the relay rule is still a max: the runner can't leave without the baton
AND the track. And a buffer is a shock absorber — it doesn't matter whether the shock comes from
the feeding chain slipping (push) or the merge point being pulled earlier by the critical chain
running to plan (pull); either way "we thought 5 days of protection would be sufficient, now we
find we only have 2" and the fever chart must say so at that exact status update.

What was implemented (all in `task_operations.py` / `task_resource_model.py`):

- **Pull = max across ALL gating predecessor links** (`_earliest_allowed_start`): a merge task
  is pulled back only to the latest of every incoming constraint. An ordinary predecessor gates
  at its finish (+lag); a buffer predecessor gates at the finish of the work feeding it
  (`_buffer_feed_floor`) — a buffer is protection, not work: it may compress to nothing, but the
  work behind it can never be jumped.
- **Stage 3's glue is now execution-phase size-aware**: the buffer's end stays glued to the merge
  point, and its size reacts in both directions — compressed against the feed floor when the
  merge point is pulled earlier, regrown toward (never past) its baseline when it moves later.
  Every size change is logged to `buffer_size_history` (reasons `merge_pulled_earlier` /
  `merge_moved_later`), mirroring Stage 7's absorb which owns the feeding-chain side.
- **Feeding buffer fever chart formula** (`compute_fever_chart_point`): effective lateness =
  `baseline size − live size + overflow`, where overflow is how far the merge point sits past its
  own baseline once the buffer is fully consumed. Consumers already divide by the baseline size,
  so the history schema and all chart/export code are untouched. Scenario numbers: the on-track
  update on C1 plots 3/5 = 60% on the feeding buffer at that instant; F1 slipping 2 days plots
  40% exactly as the old push-only formula did (the new formula strictly generalizes it, and
  >100% still means forecast breach). Trade-off knowingly accepted: a feeding chain running
  *early* now reads 0% rather than negative, since regrowth is capped at baseline.
- **Regression tests** (`tests/test_fever_chart_merge_signal.py`, 4 tests): the pull rings the 60%
  alarm with all baselines untouched; status updates are idempotent (same news twice changes
  nothing); the pull never jumps unfinished feeding work (F1 slips first, then a C1 update — C2
  lands at 7, not 5); the push-side signal is numerically unchanged.

Full suite (`uv run pytest tests/ -q`): **58 passed** (54 pre-existing + 4 new), 0 failures.

**What Stage 12 still needs**: this covered the specific merge-pull scenario that surfaced the bug,
not the full narrative Stage 12 originally scoped (a longer day-by-day walk asserting CPSL/PPF/
Progress %/Consumption %/Zone at every step, a feeding buffer fully consumed with overflow onto the
critical chain, and cross-project isolation). See "Remaining fever chart hand-verification (Stage
12 — done)" below for how that remainder was closed out.

### Reporting framework (Stage 10 — done)

Stage 10 was originally scoped as a single-purpose "Backlog Full Kit readiness report," then
generalized: "backlog" (not-started) shouldn't be baked into the report's own definition - it's one
value of a filter dimension a report applies, and the readiness report is really just the first of
several report *types* that all share the same shape (pick a project, narrow to a subset of its
tasks via combinable filters, then extract/render a specific metric). Fever Charts (Stage 8)
already are a second instance of that same shape, built before this framework existed. Part A is
the filter-dimension half of that generalization, extending Stage 11's Filter menu
(`ui_components.py`/`tag_operations.py`) so both the task grid *and* future reports can use them -
none need a new stored field, all are computed from data already on every task:

- **State** (`TaskResourceModel.get_task_state`/`get_tasks_by_state`) - `Not Started`
  (`actual_start_date is None`), `In Progress` (`actual_start_date` set, `actual_end_date is
  None`), `Complete` (`actual_end_date` set). Mutually exclusive, so it's a checkbox list (OR
  within the dimension) via the new generic `CheckboxListFilterDialog`.
- **Full-Kit Readiness** (`get_tasks_by_fullkit`) - `fullkit_date is not None` vs not. Orthogonal
  to State (a task can be Not Started and kitted, Not Started and not kitted, etc.), so it's its
  own filter rather than a value of State - a tri-state radio dialog (`FullKitFilterDialog`:
  Any/Ready/Not Yet Kitted), since checking both "ready" and "not ready" as checkboxes would be
  equivalent to neither.
- **Planned Start Window** (`get_task_start_window`/`get_tasks_by_start_window`) - derived from a
  task's scheduled start (`col` → date) relative to `model.setdate` (the app's own simulated
  "today," not wall-clock time - consistent with the rest of the execution-phase design):
  `Overdue`, `Next 1 week`, `Next 2 weeks`, `Next 1 month`, `Next 2 months`, `Later`. Half-open,
  non-overlapping buckets (a task exactly 7 days out lands in `Next 2 weeks`, not `Next 1 week`) so
  checking several is still simple OR, same pattern as State.

All three AND-combine with each other and with the existing Tags/Project filters in
`TagOperations.get_filtered_tasks()`, e.g. "Project X, Not Started, not yet full-kitted, planned
start within 2 weeks" as a single query - exactly the combinability the readiness report needs, but
useful on the plain task grid too (this is why it's built into the Filter menu, not hidden inside a
report dialog). `clear_task_filters()` and `has_active_filters()` extended to cover all three; the
status bar's `update_filter_status()` (`task_manager.py`) now derives its "any filters active" check
from `has_active_filters()` rather than re-listing dimensions by hand, so a future dimension can't
be added to one and forgotten in the other.

18 new tests in `tests/test_report_filter_dimensions.py` (state/fullkit/window derivation, bucket
boundaries, multi-dimension AND combination, clear/has-active-filters coverage).

**Part B - the reporting framework itself** (`src/operations/report_operations.py`, new file):

- New **`Reports` menu** (`ui_components.py`) - `Project Fever Charts...` moved here unchanged from
  the `Projects` menu (which now holds only `Manage Projects...`), plus a new `Full-Kit
  Readiness...` entry. One home for every report type, old and new, as the design intended.
- **`ReportOperations`** (wired into the controller as `self.report_ops`, alongside
  `self.tag_ops`/`self.export_ops`) is deliberately *not* a generic plugin-discovery registry -
  with exactly one new report type in existence, that would be abstraction ahead of need. What it
  does establish: an extractor/renderer split per report method, so a future report type is "write
  an extractor + a dialog," not "re-derive filtering." `_select_project()` mirrors Fever Charts'
  existing "prompt if more than one project" flow.
- **Full-Kit Readiness** (`compute_fullkit_readiness` = extractor, `view_fullkit_readiness_report`
  = renderer): scopes to a chosen project, filtered through whatever's currently active on the
  Filter menu (`tag_ops.get_filtered_tasks()`) - e.g. checking the State filter's `Not Started`
  reproduces the original "backlog" framing, but nothing forces that scope. Excludes buffer tasks
  (`type == 'task'` only - full-kit readiness isn't a meaningful concept for a buffer). Shows
  ready-count/total/percentage plus a listing sorted soonest-planned-start-first. No phase guard,
  unlike Fever Charts - full-kit readiness matters during planning too. On-screen only for now, no
  CSV/PNG export (consistent with how Stage 8 started before export was a fast-follow ask).
- Fever Charts' own code/dialogs untouched, as planned - only its menu location moved.
- 5 new tests in `tests/test_report_operations.py` covering the extractor only (project scoping,
  buffer exclusion, sort order, respecting active Filter-menu state, empty-project zero-counts) -
  the renderer is a plain Tkinter dialog with no independent logic worth a headless test, verified
  instead by a manual headless smoke run that opens the real dialog against a real controller.

Full suite (`uv run pytest tests/ -q`): **81 passed**, 0 failures.

### Remaining fever chart hand-verification (Stage 12 — done)

Closed out what Stage 15 left open: a full multi-update narrative test, a feeding buffer fully
consumed with overflow onto the critical chain, and cross-project isolation checked at every step.

- **`scripts/stage12_walkthrough.py`** (new) - a headless, step-through hand-verification tool,
  built to answer "how do I know these formulas are right?" before locking them into a permanent
  test. Builds a small CCPM scenario (critical chain C1->C2->C3->Project Buffer baseline 8, feeding
  chain F1->Feeding Buffer baseline 5 merging into C2, plus an untouched "Control" project for
  isolation) and steps through 9 status updates one at a time - printing the exact manual actions
  to reproduce each step in the real running app (`Date menu > Set Current Date...`, then
  `Record Remaining Duration...` with the value to enter), pausing so the app can be driven by hand
  before revealing the expected CPSL/PPF/Progress %/Consumption %/Zone, and for two of those steps
  printing the full PPF/consumption arithmetic line-by-line (`explain_progress_frontier`/
  `explain_consumption`) - e.g. showing exactly why a well-forecast but not-yet-`done` task doesn't
  advance the Progress Frontier. Also saves the Day-0 scenario to `scripts/stage12_scenario.json`
  for `File > Open...`, and colors the Project/Feeding Buffer tasks Plum/Salmon so they're easy to
  call out by color on video. Cross-checked step-by-step against the real app by the user.
- **The narrative surfaced two real design points worth recording**, both confirmed as correct
  existing behavior rather than bugs:
  - A feeding buffer's consumption isn't only driven by its own feeding chain running late - a
    routine on-track update on the *critical* chain can pull the merge point earlier and compress
    the buffer too (Stage 15's shock-direction-agnostic design working as intended).
  - Recording a task's status for the first time *and* marking it done in the same update collapses
    its footprint to zero length at that date, since the model only anchors `actual_start_date` on
    a task's first recorded update - skipping an earlier "in progress, N remaining" update loses
    real elapsed-progress visibility. The scenario/script route around this by recording an early
    on-track update for every task before it's ever marked done, matching how a PM would actually
    hear about and backdate a late status report.
  - Separately, the scenario originally let C3 (FS-dependent on C2) get marked finished before C2
    itself was ever recorded done - an impossible ordering in reality. Fixed by inserting a C2
    completion step first; this also demonstrates Progress % advancing past two tasks instead of
    one.
- **`fever_chart_display_point`** (`task_resource_model.py`, new) - the walkthrough script needed to
  call the *exact* Progress %/Consumption % math the app uses to be trustworthy, which surfaced that
  this math was hand-copied identically into three places (the on-screen chart, the PNG export, and
  the CSV export) with no shared test. Extracted into one function, all three call sites updated to
  use it, covered directly by 5 new tests in `tests/test_fever_chart_display_point.py`.
- **`tests/test_fever_charts_narrative.py`** (new, 2 tests) - the permanent regression test the
  walkthrough's hand-verified numbers were turned into once agreed: the full 9-step narrative
  (asserting CPSL/PPF/Progress %/Consumption %/Zone at every step) plus a Day-0 baseline sanity
  check, with cross-project isolation (`Control` project's buffer must never move) asserted after
  every single step, not just once. Verified to actually catch a regression, not just pass by
  construction, by deliberately breaking the overflow term and confirming the test failed with the
  expected diff before reverting.

Full suite (`uv run pytest tests/ -q`): **88 passed**, 0 failures.

### Stage 13 — Rolling timeline compaction ("Delete History...", done)

A rolling-wave planning tool will eventually accumulate a grid where the earliest columns are all
long-completed history with nothing actionable left in them, while there's no room left to plan
further into the future (`model.days` is a fixed-width window).

**Assumed usage pattern** (confirmed with the user, shapes several decisions below): the project
manager is expected to leave many weeks of completed history sitting in the timeline and only chop
it off when it's clearly safe to do so - this is an occasional, deliberate housekeeping action by
someone who already understands the risk, not something the tool needs to manage aggressively or
automatically. The PM is also expected to be saving the current plan to a version-controlled repo
as a matter of course, so a past plan can always be recovered from there if needed - the
application itself is not expected to be the sole source of historical truth. Both points directly
support the "delete outright, no archive" decision below, and mean the performance question further
down is unlikely to bite in the first several chop cycles of a given plan's life.

**Grounded in the actual model first**, rather than assumed: checked every timing-related field on
a task. Only `col` (and the `col`/`duration` inside a task's `baseline` dict) is relative to the
timeline's day-zero (`model.start_date`). Everything with real reporting value -
`actual_start_date`, `actual_end_date`, `fullkit_date`, `fever_chart_history[].date`,
`buffer_size_history[].date` - is an absolute calendar date/string, entirely independent of where
day-zero sits. So shifting `col` values to compact the timeline does **not** touch or invalidate
any fever chart history, buffer history, or completion record - a much smaller blast radius than
"reindex everything" might suggest. Predecessor/successor `lag` values are relative *between
tasks*, not to day-zero, so links are unaffected by a shift too.

**The mechanism already mostly exists.** `update_project_start_date` (`task_operations.py:1866`)
already shifts every task's `col` by a date delta and shifts every resource's `capacity` array
(`_update_resource_capacities_for_date_change`) - and, importantly, it operates on `self.model.tasks`
globally, not scoped to one project. All projects share a single day-axis (there's no per-project
timeline), so there's no "whose chop point wins" ambiguity across concurrent projects to design
around - it's inherently one shared operation. This existing function is **not** safe to reuse
as-is for a compaction feature, though, for three reasons - the third found while designing this
stage, and serious enough that it's being fixed in the existing function too, not just avoided in
the new one:
1. It confirms every deleted task with an individual `messagebox.askyesno` popup - fine for
   correcting one project's start date by a few days, unworkable for "compact 6 months of
   completed history across 3 projects" (dozens of dialogs to click through one at a time).
2. It deletes any task that falls off the edge, completed or not, with no distinction - a
   delayed-but-not-yet-started task sitting in the chopped region would be silently lost.
3. **It shifts `task['col']` but never `task['baseline']['col']`.** Every buffer's forecast-lateness
   math (`compute_fever_chart_point`) compares a task's *current* `col` against its `baseline`
   `col` (`terminal_baseline['col']`, `merge_baseline['col']`) - if only the live `col` shifts, every
   subsequent Progress %/Consumption % calculation for that buffer is silently wrong by exactly the
   shifted number of days, for the rest of the project's life. Not a UI gap like the other two - a
   real data-correctness bug, latent in `update_project_start_date` today (nothing currently guards
   against calling it on an executing project with captured baselines). Fix: extract one shared
   helper that shifts a task's `col` and its `baseline`'s `col` together, atomically, used by both
   `update_project_start_date` and the new Delete History feature - never shift one without the
   other again.

**Decisions made in discussion so far:**
- **Chopped tasks are deleted outright, not archived** - matches how `update_project_start_date`
  already behaves, and matches the assumed usage pattern above: the PM's own version-controlled
  save history is the recovery mechanism for old task details, not a feature the app itself needs
  to build.
- **The operation warns but allows override** when a task that isn't fully `done` would fall in the
  chopped region, rather than hard-refusing - flexible, consistent with the "warn, don't block"
  precedent `update_project_start_date` already sets, but does mean the user can still choose to
  lose track of an incomplete task if they override the warning.
- **Hard block, not warn-and-override, if the chopped region contains a buffer's terminal task or
  merge task** (`get_buffer_terminal_task`/`get_buffer_merge_task`), regardless of whether that task
  is itself `done`. Deleting either doesn't just lose track of one task's progress - it permanently
  breaks `compute_fever_chart_point` for that buffer (`None`, no terminal/merge task to anchor to)
  for the rest of the project's life, a strictly worse and unrecoverable-by-override consequence
  than the not-done warning above. There's no legitimate reason to delete it while its buffer is
  still in use, so this one refuses outright rather than merely flagging it.
- **Bulk confirmation UX**: one summary dialog (total tasks to delete, date range, how many are not
  `done` - flagged, overridable) with a single confirm/cancel, not `update_project_start_date`'s
  one-popup-per-task pattern, which doesn't scale to a bulk housekeeping operation. If any buffer's
  terminal/merge task falls in the chosen range, the dialog reports it and blocks confirmation
  entirely until the cutoff is moved earlier to exclude it.
- **Trigger mechanism**: a manual, explicit, user-triggered action - `Date` menu → `Delete
  History...` (alongside `Set Current Date...`/`Reset to Today`, since this is fundamentally a
  date-axis operation), not `Compact Timeline...` as originally drafted, since "compact" undersells
  that this is a destructive, delete-outright operation and "Delete History" says so plainly,
  matching how directly this codebase already names other destructive actions rather than softening
  them. Purely opt-in, never automatic or proactively suggested - this reindexes a shared,
  cross-project coordinate system and should never happen as a side effect of something else.
- **Grid background coloring**: shade exactly the "safe-to-delete" region - columns strictly before
  the earliest start of any not-yet-`done` task *and* before any buffer's terminal/merge task -
  i.e. precisely what Delete History would remove with zero warnings and zero blocks if that cutoff
  were chosen. Gives an at-a-glance "this much is genuinely free to reclaim" signal on the grid
  itself, distinct from just shading everything before today's setdate (which wouldn't distinguish
  truly-safe history from history that still matters).

**Implementation:**
- **`TaskResourceModel.shift_task_position(task, delta_days)`** (new) - shifts `task['col']` and
  `task['baseline']['col']` (if a baseline exists) together, atomically. `update_project_start_date`
  refactored to call it instead of mutating `col` directly, fixing its latent bug as planned.
- **`compute_delete_history_impact(cutoff_col)`** (new, pure/no side effects) - returns `to_delete`
  (every task with `col < cutoff_col`), `not_done` (the subset not `state == 'done'`, warn-only),
  and `blocking` (`{'buffer', 'task', 'role'}` for any buffer whose terminal/merge task is caught,
  regardless of its own done state - hard block, checked against both `get_buffer_terminal_task` and
  `get_buffer_merge_task` for every buffer in the model).
- **`delete_history(cutoff_col)`** (new) - deletes every task in `to_delete`, shifts everything else
  (via `shift_task_position`) and every resource's `capacity` array left by `cutoff_col`, and shrinks
  `self.days` by `cutoff_col` - unlike `update_project_start_date`, this actually reclaims space
  rather than re-anchoring within a constant-size window. Returns `False` (no-op) if blocking or
  `cutoff_col <= 0`, re-checking `compute_delete_history_impact` itself as a safety net.
- **`compute_safe_delete_cutoff()`** (new) - the largest cutoff with zero warnings/blocks (`min` over
  every not-done task's `col` and every buffer terminal/merge task's `col`, model-wide); drives the
  grid's background shading.
- **UI**: `Date` menu → `Delete History...` (`task_operations.py`) - a calendar-picker cutoff date
  (tkcalendar, with the same manual-entry fallback pattern as `edit_setdate`), then
  `_delete_history_confirm`: hard-blocks with an explanatory `messagebox.showerror` listing every
  blocking buffer/task/role if any exist (no override), otherwise one bulk confirmation dialog
  (total to delete, date range, not-done tasks named and counted if any) before calling
  `model.delete_history` and `controller.update_view()`.
- **Grid shading** (`ui_components.py:draw_task_grid`) - a plain `#e8e8e8` rectangle behind the grid
  lines/tasks, spanning columns `0` to `compute_safe_delete_cutoff()`.
- **A genuinely non-obvious finding, confirmed by test rather than assumed**: shifting preserves a
  buffer's math *only* when the deleted tasks aren't part of that buffer's own chain. Deleting
  history that includes chain members legitimately changes Progress % (PPF/CPSL) going forward -
  the chain's own `chain_start` naturally moves to whatever task now remains earliest, since some of
  the "already confirmed done" certainty being counted was just discarded on purpose. Forecast
  lateness (Consumption %) is unaffected either way, since it's anchored to the terminal task's own
  baseline, not to how many earlier siblings still exist. Not a bug - an honest consequence of
  choosing to delete history - but worth knowing before assuming Progress % is untouched by a cut.
- **`TaskResourceModel.extend_timeline(additional_days)`** (new) - "growing the right side," added
  right after the rest of this stage once it became clear a manual, user-triggered version was
  actually wanted (not just the CCPM import's internal auto-growth). Extends `self.days` and every
  resource's `capacity` array, generating weekend-aware default capacity for the new days (1.0, or
  0.0 on Sat/Sun for a `works_weekends=False` resource) - a real improvement over the blind `1.0`
  fill `file_operations.py`'s pre-existing `_ensure_model_days` used, which is now a thin wrapper
  around this same method so CCPM import and manual extension can't drift apart on the logic, the
  same reasoning as `shift_task_position` above. Returns `False` (no-op) if `additional_days <= 0`.
- **UI**: `Date` menu → `Extend Timeline...` (`task_operations.py`) - a plain integer prompt ("how
  many additional days"), showing the current/new timeline end date, no confirmation dialog needed
  since this is purely additive and non-destructive (unlike `Delete History...`, nothing to warn
  about or block).
- 26 new tests in `tests/test_delete_history.py` (was 19: shift mechanics, impact computation,
  blocking on both terminal and merge roles even when done, the fever-chart-invariant-across-
  compaction case above, safe-cutoff computation, the delete dialog's confirm/decline/block/no-op
  paths, `extend_timeline`'s capacity generation/weekend-awareness/non-positive-input handling, and
  the extend dialog's confirm/cancel paths) plus one in `tests/test_project_start_date.py`
  regression-testing the baseline-col-shift fix directly. Full suite (`uv run pytest tests/ -q`):
  **115 passed**, 0 failures.

**Still not done:**
- **Performance motivation, still not quantified.** The per-day iteration cost in
  `calculate_resource_loading` and related functions as `model.days` grows was the reason to ever
  trim rather than let the window grow indefinitely - still unmeasured. Worth doing before assuming
  it's a real problem in practice for any given plan's actual size.

## Remaining work

(Stage 9, fever chart CSV data export, is done — see "Fever chart reporting (Stage 8 — done)"
above. Stage 11, filter menu restructure + marquee-select, is done — see "Task/project filtering +
marquee-select (Stage 11 — done)" above. Stage 12, the remaining fever chart hand-verification, and
Stage 14/15, the Optimal/Realistic rename and merge-point pull rule + shock-absorber fever fix, are
all done too — see their own "— done" headings above. Stage 10, generalized from a single-purpose
backlog report into a Reporting framework, is done in full (Parts A and B) — see "Reporting
framework (Stage 10 — done)" above. Stage 13, rolling timeline compaction / "Delete History...", is
also done — see its own "— done" heading above.)

### Stage 16 — Export a project network for the external CCPM scheduler (round-trip with Stage 14/import) — done

**Done.** Implemented as `CcpmOperations` (`src/operations/ccpm_operations.py`), two new File-menu
items, 11 tests (`tests/test_ccpm_operations.py`). The external tool is now the
[ccpm-scheduler](https://github.com/rnwolf/ccpm-scheduler) Python package (extracted from the
Claude-skill scripts; a git dependency of this app until its first PyPI release), which resolved
the column-name question below: the exported columns are `realistic_duration`/`optimal_duration`,
confirmed against that repo. Two flows share one mapping (`build_network_data`, producing the
package's JSON exchange shape):

- **File → Export CCPM Network...** — writes `tasks.csv`/`resources.csv`/`calendar.csv` for a
  chosen project (capacity arrays run-length-encoded into half-open `[from, to)` windows against
  the most-common value as the base capacity); the success dialog shows the exact
  `ccpm-scheduler build ...` command and points back to `File → Import CCPM Schedule...`.
- **File → Schedule with CCPM...** — the full trip in-process via the `ccpm_scheduler` library:
  validate (errors surface as the engine's coded issues, e.g. `E_CYCLE`, `E_NO_RESOURCE`,
  `E_FRACTIONAL_ALLOCATION` — the engine schedules whole resources only in its v1), build, verify,
  then import the result as a NEW project named `<source> (CCPM)` by reusing
  `import_ccpm_schedule`'s private helpers — so manual and automated plans sit side by side, and
  the shared resource pool is reused by name, never duplicated.

The open design questions resolved: scope = the whole selected project, with `complete` tasks
excluded (links into them dropped with a warning); existing `project_buffer`/`feeding_buffer`
tasks are never exported (the scheduler computes its own buffers); `optimal_duration` is exported
only when the user captured one (otherwise the tool's classic 50% cut applies); the day axis is
**anchored at the first day of the project's earliest task** — the scheduler always plans from its
own day 0, so calendar windows are exported anchor-relative (future availability falls exactly
where it does relative to the project; windows entirely before the anchor are past and dropped)
and the in-process flow shifts the imported schedule back by +anchor. Refined after first real
use, matching the intended practice (plan the next project overlapping the tail of the executing
one, schedule it against the future calendar, compare, adjust, delete the hand-drawn tasks):

- the imported CCPM project's rows start two rows below the source project's rows (when free),
  so the two networks compare at a glance;
- the schedule's task ids are the source `task_id`s, so color, tags, and notes are carried across
  to the CCPM copy — deleting the hand-drawn network no longer loses them;
- every generated row (buffers included) gets a `ccpm` tag, so the whole generated network is
  selectable via the tag filter alongside/against the original.

The original design sketch for this stage follows.

The other half of the round trip described in Stage 14: export a chosen project's network,
resources, and calendars for a given time frame, in the format the external CCPM scheduling tool
actually consumes as *input* - upload that, let the external tool compute the schedule, then bring
the result back into our-planner via the already-built `import_ccpm_schedule`
(`file_operations.py`). Manual and automated schedules can then be compared side by side, per the
strategy in Stage 14/the "out of scope" note above.

**Grounded in the tool's real input format**, not guessed - re-checked `file-structure.md`
(now at `docs/file-structure.md`), which documents the *input* side (not just the
`schedule.csv` output the importer already reads):
- **`tasks.csv`** (column names below reflect the *current* documented format -
  `duration_safe`/`duration_aggressive`; the user owns the external CCPM utility too and intends to
  rename these columns there to match our-planner's new `realistic`/`optimal` convention, so the
  export's column names should follow whatever that ends up being rather than the "safe"/
  "aggressive" names quoted here - confirm the exact renamed columns against that repo once it's
  updated, rather than assuming): `id, name, duration_safe, duration_aggressive (optional),
  predecessor_ids, resource_ids, url (optional)`. This is the direct, concrete link to Stage 14 -
  the export needs **both** duration estimates per task, mapping our `realistic_duration` and
  `optimal_duration` onto whichever two columns the aligned format uses. The doc notes that if the
  optimal-estimate column is omitted the tool applies a classic 50% cut itself - worth deciding
  whether to omit it for tasks where the user never captured an explicit Optimal estimate, rather
  than exporting a guessed value.
  Predecessor notation (`A:SS+2` style) needs re-serializing from our model's predecessor list -
  `format_predecessor_notation` (`dependency_notation.py`, already built and used for tooltips this
  session) is the natural fit, just needs the reverse of the importer's id-mapping (our integer
  `task_id` -> whatever id scheme goes out, could just be the stringified integer).
- **`resources.csv`**: `id, name, capacity (default 1), url (optional)` - straightforward from
  `model.resources`.
- **`calendar.csv`**: `resource_id, from, to, capacity` half-open-interval overrides - derived from
  each exported resource's `capacity` array, collapsing consecutive equal-capacity days into ranges
  rather than emitting one row per day.

**Open design questions**:
- **"For a given time frame"** - how is the export scoped? A date range picked by the user, the
  project's full remaining (not-yet-`done`) work, or something tied to rolling-wave planning (e.g.
  only the near-term window that's about to be worked, matching Stage 13's eventual timeline
  compaction)? Not yet decided.
- **Task eligibility**: should already-`done` tasks be excluded from the export entirely (the
  external tool only needs to schedule remaining work), or included for context? Likely excluded,
  but not confirmed.
- **Buffers**: our model's existing `project_buffer`/`feeding_buffer` tasks presumably shouldn't be
  sent as regular input tasks (the external tool computes its own buffer sizing from the safe/
  aggressive gap) - needs to only export ordinary tasks, not the buffers we may have manually
  placed for the interim manual workflow.

### Stage 17 — Resource buffer (third manual buffer type, design discussion only, not scheduled)

Raised while building Stage 12's cross-project walkthrough scenario: real usage will have multiple
projects in flight at once (rolling-wave planning, already supported), and the project managers'
actual job at that point is largely staggering the *constrained resource's* tasks across those
projects so they don't overlap - inserting a **resource buffer** between two tasks on the same
bottleneck resource, possibly on entirely different chains/projects with no logical dependency link
between them at all. Non-bottleneck resources' overlapping delays are a lesser concern, since their
slack typically gets absorbed by the existing project/feeding buffers already.

This is CCPM's third buffer type (alongside Project Buffer and Feeding Buffer, Stage 3/7), currently
**not represented at all** - `BUFFER_TASK_TYPES` is only `{'project_buffer', 'feeding_buffer'}`. Two
things distinguish it from "automated resource leveling," which stays out of scope (see "Explicitly
out of scope" below): a resource buffer here would be a **manually-placed** task the user creates and
tags, exactly like project/feeding buffers already are - the tool's job is still just to react
correctly to whatever graph exists (Stages 2-7's philosophy), not to detect resource contention or
compute staggering automatically.

Not scoped further than this - no data model changes, no glue/cascade behavior, no fever chart
formula decided yet. Likely needs: a resource identifier on the buffer (which constrained resource
it protects), and glue/cascade logic similar to a feeding buffer's but keyed off a resource-sharing
relationship between two tasks instead of a chain-following one.

### Stage 18 — Network Graph report (any set of tasks) — done

**Done.** `Reports → Network Graph → {Selected Tasks, Project...}`
(`ReportOperations.view_network_graph_selected/_project`, mapping helper
`build_network_report_rows`, 7 tests in `tests/test_network_graph_report.py`).
Renders any set of tasks through the external scheduler's
`render_network_html` (ccpm-scheduler >= 0.8) — the same standalone
interactive vis-network HTML its `graph` subcommand produces (zoom/pan/drag,
resource filter, task inspector) — as a pure *view* of the tasks as they sit
on the timeline: no scheduling, `start = col`. Written to a temp file,
auto-opened in the browser, path noted in the transient `filter_status`
message.

Mapping decisions: resource **names** (not ids) go into the graph so the
resource filter reads "Resource A" — enabled by two v0.8 engine
generalizations built for this stage (resource lists split on `;` only so
names with spaces survive; any chain label gets a palette color with the
verbatim name in the legend, so our-planner chain names like "Feeding-01"
or renamed chains render correctly, `critical` maps from the is_critical
chain). `realistic_duration` is passed only when it differs from the task's
current duration — on hand-drawn (uncut) tasks duration IS the realistic
value and an "optimal 10d / realistic 10d" inspector row would mislead.
Links to tasks outside the rendered set need no filtering: the renderer
drops edges whose predecessor is not among the nodes. Empty selection shows
"Turn on Multi-Select and select tasks first"; titles are
"{project name}" / "{n} selected tasks — {plan file name}".

### Stage 19 — Import/Export consistency — done (our-planner side)

**Done (2026-07-16).** All eight our-planner work items below are implemented and tested
(12 new tests: `TestStage19ExportColumns` / `TestStage19ImportTagsColour` in
`tests/test_ccpm_operations.py`, plus `tests/test_export_csv.py` for the reworked general CSV
export; 154 total passing). Implementation notes that refined the plan:

- `export_to_csv` was split into a UI wrapper + testable `_write_csv_export(directory)` core,
  mirroring the `export_network_core` pattern.
- The `id:allocation` token helper is `_resource_token` in `export_operations.py`; the base
  capacity in the general resources CSV reuses `CcpmOperations._encode_capacity` so the two
  exports can't drift on what "capacity" means.
- `format_predecessor_notation` gained a `sep` parameter (default `' '` for dialogs, `';'` for
  CSVs — parsers accept both).
- The Export Complete dialog's `len(files) > 2` heuristic for "calendar.csv present" would have
  broken when notes.txt joined the list — replaced with an explicit basename check.
- Import tags every `schedule.csv` row `ccpm` (not only rows with a `tags` column), matching the
  in-process flow's rationale: the whole imported network is tag-selectable.
- The two **scheduler-side items remain open** (tags/colour passthrough to `schedule.csv`;
  `id:allocation` tokens in its CSV contract) — they are inputs to the ccpm-scheduler plan, and
  until they land the CCPM tasks.csv keeps flatten-and-warn for allocations ≠ 1.

The original plan follows.

Iron out the inconsistencies between our-planner's three CSV surfaces and the external
ccpm-scheduler's file contract, so the same concepts use the same column names and token
notations everywhere. Once this is aligned, a follow-up plan will improve ccpm-scheduler itself
(the two scheduler-side items below are inputs to that plan, not part of this stage).

**Current state, verified in code (our-planner @ Stage 18, ccpm-scheduler 0.8.0 installed):**

| Surface | Files | Columns |
|---|---|---|
| `File → Export CCPM Network...` (`ccpm_operations.export_network_core`) | `tasks.csv` | `id, name, realistic_duration, optimal_duration, predecessor_ids, resource_ids, url` |
| | `resources.csv` | `id, name, capacity` |
| | `calendar.csv` | `resource_id, from, to, capacity` (half-open `[from, to)`) |
| `File → Import CCPM Schedule...` (`file_operations._import_schedule_tasks`) | `schedule.csv` | reads `id, start, duration` (required); `name, type, chain, resource_ids, predecessor_ids, url, realistic_duration, finish` (optional) |
| ccpm-scheduler output (`SCHEDULE_COLUMNS` in its `model.py`) | `schedule.csv` | `id, name, type, chain, start, finish, duration, realistic_duration, resource_ids, predecessor_ids, url` |
| `File → Export → CSV` (`export_operations.export_to_csv`) | `..._tasks.csv` | `ID, Row, Column, Description, Project, Chain, Start Date, End Date, Duration, Resources, Resource Allocations, Predecessors, Successors, Tags, URL` |
| | `..._resources.csv` | `ID, Name, Tags, Total Capacity, Total Loading, Average Utilization, Peak Utilization` |
| | `..._resource_loading.csv` | `Resource ID, Resource Name` + per-day `Loading_/Capacity_/Utilization_<date>` triples |

So the CCPM export/import pair is already exactly aligned with the scheduler's contract
(import's optional-column reading matches `SCHEDULE_COLUMNS` one for one; `finish` is used only
to size the timeline). The misalignment is concentrated in the general `File → Export → CSV`
family, plus two round-trip gaps (tags/colour, allocations) that today only the in-process
`Schedule with CCPM` path papers over by copying color/tags/notes across by task id.

**Work items (our-planner side, this stage):**

1. **Tags + colour columns on CCPM export** — add `tags` (comma-joined) and `colour` (the task's
   `color` field) columns to the exported `tasks.csv`. Safe today: the scheduler's CSV loader
   reads known columns by name and ignores extras (verified in its `io.py`). Until the scheduler
   passes them through to `schedule.csv` (see scheduler items below), they document the network;
   after that, they complete the external round trip.
2. **Tags + colour on CCPM import** — `_import_schedule_tasks` reads optional `tags` and
   `colour` columns from `schedule.csv` when present (accept `color` as an alias on read; we
   write `colour`). Tags merge with the `ccpm` tag the same way `schedule_project_core` does.
3. **`Export Complete` dialog must not grow with the notes** — with many warnings the messagebox
   can outgrow a laptop screen, hiding the OK button. Write the notes to a `notes.txt` alongside
   `tasks.csv`/`resources.csv` in the export folder instead, and have the dialog say
   "N notes written to notes.txt". Check `Schedule with CCPM`'s completion dialog for the same
   unbounded-notes hazard (it has no export folder — cap/truncate there, e.g. first 10 + count).
4. **Slim `..._resources.csv`** — remove the derived-stats columns `Total Capacity`,
   `Total Loading`, `Average Utilization`, `Peak Utilization` (the per-day
   `..._resource_loading.csv` in the same export already carries the underlying data). Add
   `capacity` (the base capacity, as in the CCPM `resources.csv`) so the file aligns with the
   scheduler's resource shape: `id, name, capacity, tags`.
5. **Consolidate `Resources` + `Resource Allocations` in `..._tasks.csv`** — one `resource_ids`
   column using an `id:allocation` token notation mirroring the predecessor tokens:
   `5:2;7` = 2 units of resource 5 plus 1 (default, `:1` omitted) of resource 7. Referencing
   resource *ids* (resolvable via the `..._resources.csv` written in the same export) instead of
   names matches the CCPM files and survives resource renames — this was the conclusion in
   `export_import_inconsistencies.ods` too ("Should we not reference resource ID?").
6. **Align the rest of `..._tasks.csv` with the scheduler vocabulary** — snake_case names, same
   spellings: `id, name, project, chain, row, start_day, start_date, end_date, duration,
   realistic_duration, optimal_duration, predecessor_ids, resource_ids, tags, colour, url`.
   `Description → name`, `Column → start_day` (canvas `col`), predecessors keep the shared token
   notation but semicolon-joined like the scheduler (the import regex already splits on `[;\s]+`,
   and `format_predecessor_notation` currently joins with spaces — add a separator argument or
   join its tokens with `;` here). Drop `Successors` (derived from predecessors; the model never
   stores it for exactly this drift reason). This export has no matching import today, so no
   compatibility constraint — but aligned columns mean a filtered general export could one day
   feed the scheduler directly.
7. **Tests** — extend `tests/test_ccpm_operations.py` (tags/colour columns out, notes.txt,
   tags/colour in via `schedule.csv`) and add coverage for the reshaped general CSV export
   (column set, `id:alloc` tokens, no derived stats).
8. **Docs** — update `docs/file-structure.md` (new optional columns) and the
   user guide's export section.

**Needs ccpm-scheduler changes (record here, plan there):** the scheduler's source lives at
`/home/rnwolf/workspace/ccpm-scheduler` (published to PyPI; the Claude-skill wrapper is in
`~/workspace/ccpm-single-project-skill`). Its own `PLAN.md` already reserves "Phase 5 — Close
the model gaps" for fractional capacity/allocation in the leveler, which is where the
`id:allocation` semantics below belong; tags/colour passthrough would be a new phase there.

- **Column passthrough** — carry `tags`/`colour` (or arbitrary unknown columns) from `tasks.csv`
  through to the matching `schedule.csv` rows, so the external round trip preserves them the way
  `Schedule with CCPM` already does in-process. Buffer rows it generates have no source row —
  they'd get empty tags/colour (our-planner import then applies its own buffer styling anyway).
- **`id:allocation` tokens in `resource_ids`** — the JSON exchange already accepts
  `{"id": alloc}` dicts, but the engine rejects fractional allocations
  (`E_FRACTIONAL_ALLOCATION`, whole-resources v1) and the CSV notation doesn't exist, which is
  why `export_network_core` currently flattens allocations to whole resources with a warning.
  Scheduler work: parse/emit the token form, define semantics at least for integer units > 1
  (consume N capacity units of that resource). Until that lands, our-planner keeps the
  flatten-and-warn behavior in the CCPM export (emitting `5:2` today would read as an unknown
  resource id); the general export (item 5) can adopt the notation immediately since nothing
  external parses it yet.

**Decisions (resolved 2026-07-16):**

- `colour` vs `color`: *write* `colour`, *accept* both spellings on import. If the scheduler
  ends up echoing the column, its docs should use the same spelling.
- No `resource_names` convenience column in the general tasks export — resource *ids* plus the
  `..._resources.csv` written in the same export are enough.
- Keep the two start-axis column names distinct on purpose: the general export's `start_day` is
  absolute (day 0 = timeline start), while the CCPM files' `start` is anchor-relative (day 0 =
  the project's earliest task). The different names make the different axes visible.

### Stage 20 — CCPM Method per project — done

**Done (2026-07-17, against ccpm-scheduler 0.9.0 from PyPI; pin bumped to >=0.9.0).**
Implemented as planned below: `project['ccpm_method']` (default `'cap'`, validated in
`update_project`, defaulted on legacy saves), a read-only "CCPM Method" combobox in
`Manage Projects...`, `build_network_data` adds the top-level `buffer_method` JSON key, and the
`Export CCPM Network...` dialog's command hint includes `--buffer-method <method>`. One addition
beyond the plan: the imported `<source> (CCPM)` project inherits the source's method, so
rescheduling the copy reproduces the same buffer arithmetic. 8 new tests (model persistence /
legacy-load default; JSON key; per-method scheduling pinned to the documented sizes — worked
example 30/15/16, mixed 4-task chain 29/16/16; dialog hint), existing worked-example assertions
re-baselined to the cap default. Verified end-to-end in the running app: cap → PB 30/day 60,
hchain → 15/45, rsem → 16/46, copy inherits method. Note: the app's *startup sample tasks* use
fractional allocations, which the scheduler still rejects (`E_FRACTIONAL_ALLOCATION`) — its
PLAN.md Phase 5, unchanged by this stage.

The original plan follows.

### Stage 20 — original plan (was: blocked on ccpm-scheduler Phase 6)

Buffer sizing is becoming selectable in ccpm-scheduler (its PLAN.md Phase 6, agreed
2026-07-16): `cap` (Cut & Paste, Σ of removed safety — the new default), `hchain` (50% of
chain — today's only behavior), `rsem` (root-squared error). Formulas, pros/cons, and how
mixed single-/two-point estimates normalize are documented canonically in that repo's
`docs/buffer-sizing.md` — don't duplicate the math here. our-planner's side:

- `project['ccpm_method']` ∈ `{'cap', 'hchain', 'rsem'}`, default `'cap'`; new "CCPM Method"
  dropdown in `Manage Projects...` next to the phase field; persisted in save/load with
  backward compatibility (missing key → `'cap'`).
- Both round-trip flows pass it through: `build_network_data` adds a top-level
  `buffer_method` key to the JSON exchange dict (`Schedule with CCPM`), and the
  `Export CCPM Network...` completion dialog's command hint gains
  `--buffer-method <method>`. Requires the ccpm-scheduler release that ships Phase 6 —
  bump the pin then; until that lands this stage must not start (passing the key today
  would be silently ignored, which is worse than not offering the choice).
- The imported schedule's buffers stay manually resizable before the project enters
  execution mode (existing behavior — the formula is a starting point, not a contract).
- Tests: method persisted/defaulted correctly; JSON dict carries `buffer_method`; per-method
  scheduling produces the documented buffer sizes for the worked example
  (CAP 29 / HCHAIN 16 / RSEM 16 on the mixed 4-task chain in `docs/buffer-sizing.md`).

### Stage 21 — Resource grid at scale: ID display, sorting, filtering, and a resource control bar — done

**Done (2026-07-18).** Implemented as planned below, with two deliberate deviations: the sort/
scope state (`resource_sort_key`/`resource_sort_desc`/`resource_load_scope`) lives in
`TagOperations` alongside the rest of the grid's filter state rather than on the controller —
one home for all of it, and testable without Tk (`get_display_resources(utilization)` takes the
summary as an argument for the same reason); and `save_resource_tags`'s hand-patching of tag text
onto the label canvas was replaced by a full `update_resource_loading()` redraw, since its
computed row positions assumed filter order, which sorting breaks. `update_resource_loading` is
now the single redraw path for the whole resource panel (compute loading → utilization summary →
`draw_resource_grid` → `display_resource_loading` → `update_resource_control_bar`), and the six
`draw_resource_grid(); update_resource_loading()` pairs in `task_operations.py` collapsed to the
single call. Selecting the Load % sort defaults to descending (the drum is what you're looking
for); ID/Name default ascending; the ↑↓ button toggles from there. 25 new tests
(`tests/test_resource_grid_controls.py`), 194 total passing. Verified end-to-end in the running
app (label IDs/%, load sort both directions, bar project filter → 4/10 shown + status bar text +
pane shrink-to-content, scope toggle, clear restoring 10/10 with sort/scope surviving).

The original plan follows.

Designed in discussion 2026-07-18, no code yet. Motivation: with realistic team sizes (~60
resources) the resource grid needs to surface *the resources that matter* — in CCPM that means the
maximally loaded resource (the drum). The driving workflow is multi-project alignment: filter tasks
to the two projects being overlaid, slide the later project along the timeline, watch which
resources rise to the top of the grid, and use that to place feeding/capacity buffer between the
projects. Sorting by load makes the top of the visible grid *be* the drum report.

**Grounding facts** (verified against the code, don't re-derive):

- `draw_resource_grid` (`ui_components.py`) draws resources in raw `model.resources` order; the
  only existing filter is by tag (`get_filtered_resources`, `tag_operations.py`). Tasks already
  have a project filter (`ProjectFilterDialog`, Stage 11) — the pattern to reuse.
- `calculate_resource_loading()` (`task_resource_model.py`) already runs on **every**
  `update_view()` (`task_manager.py`), i.e. after essentially every edit/drag. It's one pass over
  task-days (~tens of thousands of float adds at 60 resources / 300 days) — the sort metric is a
  free by-product of a computation already happening; no caching regime needed. The actual cost
  center at scale is `display_resource_loading` creating one rectangle+text per resource-day cell
  (≈18k canvas items at 60×300, recreated per redraw) — pre-existing, out of scope here; if it ever
  hurts, the levers are drawing only rows in the visible scroll window and skipping zero-load
  cells.
- `update_view()` currently draws the resource grid *before* computing loading. Sorting by load
  requires computing loading first, then drawing — a small, safe reorder (compute in
  `update_resource_loading`, pass the per-resource summary into `draw_resource_grid` /
  `display_resource_loading`; the two must share one ordering).
- The label cell already splits into name-upper/tag-lower zones with font-fitting
  (`resource_tag_zone_fits`) — don't add a third zone; put the ID inline in the name line.

**Part A — resource ID in the label cell.** Render `#<id> <name>` in the existing name zone
(the ID is already in hand at draw time for the canvas tags). When load-sort is active, append the
utilisation: `#12 Alice · 87%` — a sort by an invisible number looks arbitrary; showing it makes
the order legible and doubles as a mini drum report. IDs also match the CSV exports, which key by
resource id.

**Part B — resource control bar.** A slim (~26px) `tk.Frame` packed at the bottom of
`resource_frame`, above `h_scrollbar` (the grey strip currently visible there is the ttk
scrollbar plus leftover lightgray label-canvas below the last row — the bar replaces/abuts that
space). Contents, left to right:

```
Sort: [Load % ▾][↓]  Project: [All ▾]  [Tags]  Load scope: [All tasks ▾]   14/60 shown  [Clear]
```

- Sort combobox (`ttk.Combobox`, readonly): Default order / ID / Name / Load %, plus an ↑↓
  direction toggle button. Visible state — you can see at a glance the grid is load-sorted.
- Project combobox: "All projects" + one entry per project; single-select covers the one-click
  CCPM case. (A multi-select via `ProjectFilterDialog` can stay reachable from the Filter menu;
  combobox shows "Multiple…" then.) Semantics: a resource matches if assigned to ≥1 task of the
  project — resources don't *belong* to projects, they're linked through task assignments.
- Tags button showing active count ("Tags (2)"), opening the existing `TagFilterDialog` — don't
  rebuild tag multi-select inline.
- Load scope (see Part D), shown-count label, and a Clear button scoped to *resource* filters only
  (the status bar's global "Clear All Filters" already exists; don't duplicate it).
- Existing Filter-menu entries stay; menu and bar drive the same `tag_operations` state.
- **The known risk lives here:** `_fit_resource_pane` / `resource_grid_height` negotiate the
  task/resource split down to the pixel (see the hard-won comments around them). The bar must be
  explicitly inside or outside that height budget — decide once, adjust `total_available` math
  accordingly, and expect the bugs of this stage to be in this seam, not in the sorting/filtering.

**Part C — sorting.** Metric for "Load %": **whole-horizon total utilisation**, Σload ÷ Σcapacity
per resource over all days (chosen over peak-day and absolute person-days: it's the classic
capacity-constrained-resource measure, and history informs where future overload lands; capacity
normalisation matters because capacities differ). Derived in one extra pass over the
`resource_loading` dict. Sort is a pure reorder of `resources_to_draw`; applied identically in
`draw_resource_grid` and `display_resource_loading`. Re-sort is live (every redraw): rows
reshuffling as tasks move is the feature — the hottest resource floats up while you drag — accept
the mid-drag reshuffle unless it proves disorienting in practice.

**Part D — load scope (the CCPM-critical piece).** `calculate_resource_loading()` gains an
optional task-subset parameter (currently hardwired to `self.tasks`). Scope toggle: **All tasks**
vs **Filtered tasks** (= `get_filtered_tasks()`, so it composes with the project/state/tag/window
task filters for free). Scope drives cells, the label-cell %, and the sort *together* — one
consistent view, never a scoped sort over unscoped cells. The two scopes answer different
questions: *Filtered* = "for these two projects being overlaid, who is the drum and how does
contention shift as I slide Project B?" (the alignment exercise); *All* = "given everything else
on this person's plate, does the alignment survive?" (the reality check). Note this makes the
task-filter-driven mechanism the general one — the Project combobox in the bar is a convenience,
"filter tasks to the projects + Filtered scope" is the full workflow.

**Tests:** utilisation summary math (incl. zero-capacity guard); sort orders for each key + both
directions; project-membership resource filter; scoped loading equals loading of the filtered
task subset; filter composition (project AND tags) with shown-count; `update_view` ordering
(loading computed before grid draw); ID/% rendering in the label text.

**Deferred (this stage's backlog):** overload-only filter toggle ("show resources with any
overloaded day" — cheap once the summary exists); "follow task filter" resource-visibility toggle;
visible-rows-only canvas drawing if 60-resource redraw hurts; persisting sort/filter choices in
the save file (existing filters are session-only — stay consistent until asked otherwise).

## UI polish backlog (not CCPM-specific, but worth fixing)

Small, unrelated-to-CCPM items flagged during this session's testing — not urgent enough to stop
and fix immediately, but real annoyances likely to be hit by other testers too, and distracting
from evaluating the actual planning features. Worth picking up opportunistically.

- **Permanent grey band above h_scrollbar (fixed, 2026-07-18).** A ~41px dead strip sat between
  the resource panel and the horizontal scrollbar, unclaimed by any widget. Root cause: the
  one-shot `_pane_overhead` startup measurement (main_frame height minus the two panes, taken
  right after widget creation) ran before the window had settled at its real geometry, and the
  mismatch at that instant (140 measured vs 99 real) was baked in forever as phantom overhead -
  every later resize handed out that much less height than main_frame actually had, and since
  h_scrollbar packs BOTTOM, the undistributed remainder surfaced exactly between the resource
  panel and the scrollbar. Fix: `_pane_overhead()` is now a method computed from live geometry on
  every call - the requested heights of the three fixed widgets (timeline_frame,
  grid_resizer_frame, h_scrollbar) plus every pack pady among the five stacked main_frame
  children, read from `pack_info()`. No one-time measurement to go stale; the reclaimed height
  went back to the task/resource grids.

- **Status bar squeezed to nothing when shrinking the window; no resize grip (fixed,
  2026-07-18).** Tk's packer takes space from the LAST-packed widget first when a window shrinks,
  and the status bar was packed on root after the main content - so dragging the window edge up
  compressed the status bar to nothing while the grids kept their full height. Fixed by packing
  the status bar with `before=horizontal_layout_frame`, moving it ahead in the packing order:
  visually identical, but now the grids give up the space (on_main_frame_configure re-fits the
  panes as main_frame shrinks) and the status bar keeps its height like the resource control bar
  does. Also added a `ttk.Sizegrip` in the status bar's bottom-right corner (several WMs draw no
  edge handles of their own - same reason the fixed-geometry dialogs grew Sizegrips) and
  `root.minsize(800, 500)`, the floor below which whole bars would get clipped rather than
  degrade gracefully.

- **Arrow-key grid navigation (fixed, one iteration).** Requested after repeatedly finding the
  scrollbars too thin and fiddly to grab precisely, especially once zoomed in.
  `scroll_task_grid(dx_cells, dy_rows)` (`task_manager.py`) scrolls the task grid by exactly one
  `cell_width`/`task_height` per key press (whatever they currently are at the active zoom level -
  fraction math mirrors the same pattern `on_zoom` already uses for precise positioning) rather
  than relying on Canvas's own imprecise built-in "unit" scroll amount. `<Left>`/`<Right>` call
  `sync_horizontal_scroll`, `<Up>`/`<Down>` call `sync_vertical_scroll` (`ui_components.py`) -
  reusing the exact same sync methods the scrollbars themselves already call, so the timeline and
  task-label canvases stay aligned automatically; deliberately does *not* touch the resource grid's
  own separate vertical scroll region, since this is grid-specific navigation, not "move
  everything."
  - **First attempt bound the keys to `task_canvas` itself** (relying on `task_canvas.focus_set()`
    at startup and on every grid click) reasoning that this would naturally scope the feature away
    from dialogs. Verified headlessly via `event_generate` and appeared to work - but
    `event_generate` injects synthetic events directly into Tk's queue, bypassing the operating
    system entirely, so it only proved the binding *logic* was correct, not that a real physical
    key-press would reach that specific widget. The user reported it not working after a real
    click in the actual running app: `focus_set()` only requests focus *within* the Tk
    application - it doesn't guarantee the window manager has actually made that widget (as
    opposed to some other part of the window, or the window not being considered active at all)
    the real keyboard target, which is a much more fragile, WM/platform-dependent thing than it
    appears from headless testing alone.
  - **Fixed by binding to `root` instead.** `root.bind()` only needs the whole *window* to have
    OS-level keyboard focus - true as soon as the user clicks anywhere in it - rather than one
    specific child widget holding Tk's internal focus too. Every text-entry widget in this app
    (date entry, tag entry, tkcalendar, etc.) lives inside a `grab_set()`'d dialog, confirmed by
    checking every `tk.Entry`/`tk.Text` instance in `ui_components.py` - so a dialog's own
    arrow-key use (cursor movement, calendar day navigation) still can't be interfered with here:
    a dialog's local grab blocks root-level bindings from firing at all while it's open, which
    needed no special-casing to get for free.
  - Verified headlessly against a real `TaskResourceManager`, this time including the actual
    mechanism being relied on rather than just the scroll math: real `event_generate('<Right>')`
    scrolled `task_canvas` correctly with `timeline_canvas` staying in sync when only `root` (not
    any specific child widget) had focus; and, with a real `grab_set()`'d `Toplevel` and a focused
    `Entry` inside it, confirmed the root-level arrow-key binding was completely blocked from
    firing while the entry's own cursor-movement behavior kept working normally.
- **Keyboard zoom shortcuts (fixed).** Added `Ctrl-+`/`Ctrl-=` (zoom in) and `Ctrl--` (zoom out) as
  keyboard equivalents to `Ctrl`+mouse wheel, via a new `zoom_via_keyboard(direction)`
  (`task_manager.py`) that reuses `on_zoom`'s exact logic through a synthetic event - the same
  approach already used for Linux's `Button-4`/`Button-5` scroll events. Bound both the shifted
  `+`/unshifted `=` keysyms (`<Control-plus>`/`<Control-equal>`) for zoom in, and both `-`/`_`
  (`<Control-minus>`/`<Control-underscore>`) for zoom out, plus the numpad equivalents
  (`<Control-KP_Add>`/`<Control-KP_Subtract>`) - same physical key either way, so neither direction
  requires remembering whether shift is needed. A keyboard shortcut has no mouse position to anchor
  the zoom on (unlike scroll-wheel zoom, which keeps the point under the cursor fixed), so it zooms
  toward the center of the current viewport instead. Verified both by calling the method directly
  and via real `event_generate('<Control-plus>')`/`('<Control-minus>')` calls against a live
  `TaskResourceManager`.
- **Text overflow at higher zoom levels (fixed).** Two spots, both confirmed with real
  `tkinter.font.Font` measurements rather than guessing, and both root-caused to the same pattern:
  a font size that grows with zoom (`font_scale_factor = max(1.0, zoom_level * 0.8)`, no ceiling)
  measured against a dimension that doesn't grow enough (or at all) to keep up.
  - **Timeline header** (`timeline_font_size`): the three stacked rows (month/date/day) share a
    *fixed* `timeline_height` that never scales with zoom. Measuring actual font metrics
    (`Font.metrics('linespace')`) showed the default 8pt font is already 25px tall in a ~20px row
    even at 100% zoom (not exclusively a high-zoom problem, just far more visually obvious once the
    gap widens further with zoom) - the three rows' text would genuinely bleed into each other at
    the row boundaries, not just get clipped. Fixed with `_clamp_timeline_font_size()`
    (`task_manager.py`), which shrinks the font down (never below 6pt) until its measured
    `linespace` fits the actual `timeline_height / 3`, applied in both `on_zoom` and `reset_zoom`.
    This does mean the timeline font is now 6pt even at default 100% zoom (down from 8pt) rather
    than growing with zoom at all past that point - a deliberate, discussed trade-off in favor of a
    simple, low-risk fix (pure font-size logic, no changes to `timeline_height` or the pane-height
    layout math that caused several tricky bugs earlier this session) over a fully "correct" one
    that would keep 8pt at baseline by scaling the header rows themselves with zoom.
  - **Resource loading indicator** (`resource_font_size`): here `cell_width` *does* scale with
    zoom, so this could be fixed without any baseline visual change. `_clamp_resource_font_size()`
    shrinks the font (never below 6pt) until it measures within `cell_width` for a generous
    worst-case load/capacity string (`'99.9/99.9'`) - sized against a fixed reference string rather
    than each cell's actual text, so every cell shares one consistent font size instead of varying
    cell-by-cell. Verified against the realistic `'0.5/1.0'`-style text actually seen in the app:
    fits cleanly from 110% zoom upward, with a negligible 3px overflow remaining only exactly at
    100% zoom (down from 21px before the fix) - a pre-existing baseline tightness for that specific
    string length, not something that gets worse with zoom, and not what was reported.
  - Both `_clamp_*_font_size` helpers share a small `_max_font_size_that_fits(ideal_size, min_size,
    max_pixels, measure_fn)` helper (`task_manager.py`) that shrinks a candidate size using a real
    `tkinter.font.Font` instance rather than an estimated ratio.
  - **Follow-on: resource tags (fixed, took two iterations).** A third spot noticed afterward,
    using the same shared `tag_font_size` as task tags: the resource label's tag line is drawn
    below its name at `task_height/2 + tag_font_size + 3` (`draw_resource_grid`) - as the font grows
    with zoom, both its own height *and* its distance from the row's center grow together, so it
    outgrows the row faster than the timeline/resource-loading cases even though `task_height` does
    scale with zoom. First pass added `_clamp_tag_font_size()` (`task_manager.py`), clamping against
    the tag line's own computed bottom edge using the same formula the drawing code itself uses -
    verified correct against real font metrics, but the user reported no visible difference.
    - **Root cause of the miss**: `resource_font_size` - used for the resource *name* text directly
      above the tag line, sharing the row with it - had only ever been clamped against `cell_width`
      (a different dimension, in the loading-grid's own column, from an earlier fix). It was never
      checked against the row's height at all, so the name text itself kept growing unbounded with
      zoom regardless of the tag fix, which is what the screenshot actually showed overflowing.
    - `_clamp_resource_font_size()` now also clamps against half of `task_height` (leaving room for
      the tag line below), in addition to its existing `cell_width` clamp for the loading-grid
      numbers - one variable, two independent constraints, both now enforced.
    - Verified this second pass by rendering the *actual* `draw_resource_grid` output (not just
      reimplemented formula checks, which is exactly what missed the gap the first time) via
      headless Tk + `postscript()` + Ghostscript, at a zoom level matching the reported screenshot's
      density (2.2x, `task_height=66px`) - every resource's name and tag sat cleanly within their
      own row. The user reported *still* no visible difference after a confirmed fresh restart.
    - **Actual root cause, third pass**: `TaskResourceManager.__init__` set the app's *initial*
      font sizes directly from the raw base values (`self.tag_font_size = self.base_tag_font_size`,
      etc.) - completely bypassing every one of these clamp functions, which only ever ran inside
      `on_zoom`/`reset_zoom`. So the very first, never-zoomed view (almost certainly what was being
      re-tested after each restart) always showed the old unclamped sizes regardless of how correct
      the zoom-time fix was - explaining why *every* one of this session's zoom-related font fixes
      (timeline, resource-loading numbers, resource name, resource tag) kept "not working": none of
      them had ever actually been exercised at the point being tested. Fixed by routing `__init__`'s
      initial values through the exact same `_clamp_timeline_font_size`/`_clamp_resource_font_size`/
      `_clamp_tag_font_size` calls `on_zoom`/`reset_zoom` already use. Confirmed via a fresh
      (never-zoomed) `TaskResourceManager` instance: `resource_font_size`/`tag_font_size`/
      `timeline_font_size` all now come out clamped to 6pt at startup (previously 8/7/8pt
      unclamped) - the user still reported no visible difference after this fix too.
    - **Fourth pass - the actual remaining bug, and a request to go with it**: the name and tag
      clamps each independently checked their own text against the row's *outer* boundary, but
      never checked against *each other* - the name (centered at the row's midpoint) and the tag
      (positioned as an offset below that same midpoint, using `tag_font_size` for the offset
      itself) could each individually "fit the row" while still overlapping each other in the
      middle. Confirmed numerically: at 100% zoom, even both floored to 6pt, the name spans
      roughly [5.5, 24.5]px and the tag [14.5, 33.5]px - a real 10px overlap. The user separately
      asked for the name to be nudged up so the two "don't compete for attention," which is the
      same underlying fix. Redesigned `draw_resource_grid` (`ui_components.py`) to use two fixed,
      independent zones instead of a name-centered-plus-offset formula: when a tag is shown, the
      name sits at the row's upper quarter and the tag at its lower quarter - a pure geometric
      split with no dependency on either font's own size, so they can no longer grow into each
      other. `_clamp_tag_font_size` (`task_manager.py`) simplified to match - it now only needs to
      fit its own linespace within half the row height, the same check `_clamp_resource_font_size`
      already does for the name.
    - **Residual, resolved decisively rather than left as a caveat**: at 100%-120% zoom, the row is
      genuinely too short to fit two stacked lines without overlap even at the 6pt floor - a real
      physical space constraint. Rather than report yet another "small residual," added
      `resource_tag_zone_fits()` (`task_manager.py`): when there truly isn't room, the tag line is
      suppressed entirely (name only) instead of rendering overlapping/garbled text, and it
      reappears automatically once zooming in enough to fit (confirmed at exactly 130% zoom in
      testing). Verified both states by rendering the actual `draw_resource_grid` output at 100%
      zoom (tags cleanly absent) and 200% zoom (name and tag clearly separated, no overlap).
    - **Follow-on: long tag lists overflowing the label column width.** The vertical fix above says
      nothing about horizontal space - a resource with many tags (e.g.
      `[team1, developer, senior, backend, on-call, contractor]`) had no width constraint at all
      and would overflow past the label column's edges into whatever's drawn next to it. Fixed with
      `UIComponents._truncate_text_to_width(text, font, max_width, suffix='')` - shrinks `text` from
      the end until `text + '...' + suffix` fits, with `suffix` (the closing `]`) guaranteed to
      survive truncation rather than getting chopped along with everything else. When truncated, a
      tooltip with the full untruncated tag list is added via the existing `add_tag_tooltip()`
      (already used elsewhere for task tooltips) - hover to see the whole list. Verified: a
      6-tag resource truncates to `[team1, developer, senio...]` (bracket intact, tooltip bound)
      while a 1-tag resource on the same row draws untruncated with no tooltip added.
    - **Follow-on: right-click on the tag text itself didn't work (fixed).** The user reported
      there seemed to be no way to edit a resource's tags at all - the feature already existed
      (right-click a resource's *name* -> `Edit Resource Tags`), but the `<ButtonPress-3>` binding
      was only ever attached to the name text item, never to the tag text below it. Right-clicking
      directly on the tags themselves - the natural thing to try when you want to edit them,
      especially now that they sit in their own zone lower in the row - silently did nothing,
      which reasonably read as "this feature doesn't exist." Fixed by adding the same
      `show_resource_context_menu` binding to the `resource_tags_{resource_id}` canvas tag. Verified
      with a real simulated `<ButtonPress-3>` event at the tag text's actual on-screen coordinates
      (not just checking the binding exists) - correctly posts the context menu and sets
      `selected_resource_id`.
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
- **Multi-select status turned into a clickable toggle button (fixed/enhanced).** Follow-on
  request: the indicator above only ever appeared while the mode was already on, so there was no
  way to tell it was off at a glance, and toggling it still required navigating the `Filter` menu
  every time - the user specifically wanted a fixed screen corner to click without having to
  remember which menu the feature lives in. `multi_select_status` (`task_manager.py`) is now a
  `tk.Button` (was a `tk.Label`) with `command=self.toggle_multi_select_mode`, packed
  `side=tk.RIGHT` *before* `clear_filters_btn` so it lands as the rightmost/corner-most widget in
  the status bar - the easiest on-screen target to reach with the mouse. `update_multi_select_status()`
  now always shows a state (`Multi-Select: OFF` in the default button color, or `Multi-Select: ON`
  / `Multi-Select: ON (N tasks selected)` in light orange) instead of going blank when off. The
  `Toggle Multi-Select Mode` menu item is left in place alongside it (same pattern as `Clear All
  Filters` already existing as both a menu item and a status bar button). Verified headlessly:
  initial button text reads "Multi-Select: OFF"; clicking it (`.invoke()`) toggles the mode and
  updates text/color each time; its right edge sits at 994px of a 1000px-wide status bar, i.e.
  effectively flush with the corner.

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
  **Confirmed still out of scope, with the strategy now clarified** (see Stage 14): the actual
  scheduling algorithm lives in a separate repo the user already has, and is deliberately not being
  rebuilt here - our-planner's role is the manual, easy-to-use CCPM interface, with the automated
  scheduler integrated incrementally later (likely via the existing `import_ccpm_schedule` feature)
  so manual and automated results can be compared side by side before depending on the automation.
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
  `shift_task_position`/`compute_delete_history_impact`/`delete_history`/
  `compute_safe_delete_cutoff`/`extend_timeline` (Stage 13 - "Delete History..."/"Extend
  Timeline...").
- `src/model/dependency_notation.py` — link notation parse/format, `LINK_TYPES_ORDERED`,
  `BUFFER_LINK_TYPES`.
- `src/operations/task_operations.py` — task mutation logic, right-click dialogs,
  `on_task_press`/`on_task_drag`/`on_task_release` (where Stage 2's trigger points live),
  `handle_task_collisions` (the pre-existing, unrelated same-row collision mechanism),
  `update_project_start_date`/`delete_history_dialog` (Stage 13 - share `shift_task_position`).
- `src/view/ui_components.py` — menus, canvas drawing, `draw_dependencies`/`draw_arrow`
  (dashed buffer links), context menu construction.
- `src/controller/task_manager.py` — `TaskResourceManager` (main controller), status bar,
  `auto_scheduling_enabled` flag and `toggle_auto_scheduling()`.
- `src/operations/network_operations.py` — existing plain-CPM critical path calculation.
- `src/operations/file_operations.py` — `New`/`Open`/`Save`, and `import_ccpm_schedule` (CCPM
  schedule.csv import).
- `src/operations/export_operations.py` — PDF/PNG/CSV exports, fever chart PNG export.
- `src/operations/tag_operations.py` — tag/project/state/full-kit/planned-start-window task and
  resource filtering and selection (`get_filtered_tasks`/`get_filtered_resources`,
  `TagFilterDialog`, `ProjectFilterDialog`, `CheckboxListFilterDialog`, `FullKitFilterDialog`).
- `src/operations/report_operations.py` — the Reporting framework (Stage 10 Part B):
  `ReportOperations`, `compute_fullkit_readiness`/`view_fullkit_readiness_report`.
- `docs/file-structure.md` — documents the expected CCPM CSV formats.
- `sample-ccpm-projects/` — real sample CCPM schedules used to test the importer (untracked;
  to be reworked when ccpm-scheduler — the source of some of those files — is updated).

## Open questions for whoever picks this up next

(The "merge task" uniqueness question previously parked here is resolved — see "Merge-point pull
rule and the shock-absorber fever signal (Stage 15 — done)" above.)

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
- **Right-click on dependency lines too hard to trigger (fixed).** The `<ButtonPress-3>` event was originally bound directly to the dependency line items using `tag_bind('dependency', ...)`. Because the line `width` is only 1.5 pixels, Tkinter's strict pixel-perfect hit detection made it extremely difficult for users to successfully trigger the link context menu. Fixed by removing the `tag_bind` and moving the detection into the global `on_right_click` handler using `canvas.find_overlapping` with a generous 5-pixel "halo" radius around the mouse coordinates. This dramatically increases the clickable hit area without changing the line's visual appearance or interfering with any other task drag/drop events.
