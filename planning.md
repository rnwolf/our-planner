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
  Stage 3/6/7's buffer and chain-aware cascade behavior once those are built.

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

### Planning-phase buffer glue (Stage 3 — done)

- `TaskOperations._glue_buffer_predecessors(task, visiting)` (`task_operations.py`) — called from
  within `_propagate_from_task` for every task whose position was just set (whether by a direct
  user move/resize, or by being pushed there by Stage 2's cascade). For each of `task`'s
  predecessor links of type `FS` **or `FB`** whose predecessor is a buffer task
  (`project_buffer`/`feeding_buffer`) belonging to a project still in the `planning` phase, it
  recomputes `buffer.col = task.col - buffer.duration - lag` unconditionally — i.e. it snaps the
  buffer to stay glued in **either** direction, unlike Stage 2's one-directional push. `FB` was
  added alongside plain `FS` because that's the link type actually used in practice between a
  feeding buffer and its critical-chain merge-point task.
- Deliberately does **not** trigger off the buffer's own predecessors (the feeding chain) — those
  are only ever read by Stage 2 (which already skips buffer-type successors entirely), so a
  feeding-chain task moving later just opens a gap between it and the still-glued buffer, exactly
  as intended.
- Execution-phase projects are excluded entirely (the `project['phase'] != 'planning'` guard) —
  Stage 7 owns buffer behavior once a project is executing.
- No ping-pong: if a buffer's own finish is what pushes the merge task forward (e.g. a manual
  buffer resize triggering Stage 2's ordinary push), re-gluing afterward recomputes the exact same
  buffer position it already had, so `_propagate_from_task`'s cycle guard is never even needed to
  stop this case - the glue and the push land on the same equality by construction.
- Verified with a headless script (merge task moves later -> buffer follows; moves earlier ->
  buffer follows, clamped at 0; feeding chain moves -> buffer stays, gap opens; execution phase ->
  glue disabled; buffer resize pushes merge task -> no oscillation) for both a plain `FS` and an
  explicit `FB` buffer->merge-task link, and confirmed manually in the running app for both link
  types.

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
- **Re-estimating the finish.** Every call recomputes `task['duration']` from the history entry
  that is *latest by date* (not insertion order, via a new `_get_latest_remaining_duration_entry`
  helper — handles a backdated correction the same way `get_latest_remaining_duration` already
  sorted), so `task['col'] + task['duration']` always equals `(day-column of that entry's date) +
  its remaining_duration`.
- `TaskOperations.record_remaining_duration` (`task_operations.py`) now calls
  `self.apply_dependency_cascade(task)` right after the model update, so a re-estimated finish
  pushes FS successors forward exactly like a drag/resize would (Stage 6/7 will build on this same
  entry point once chains exist).
- **Full Kit stays informational, not a gate** — `Set Full Kit Done`/`fullkit_date` unchanged, no
  blocking behavior added. New: a small green circular badge in the task box's top-left corner
  (`ui_components.py:draw_task`), shown whenever `fullkit_date` is set, visible without hovering.
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

## Remaining work, in agreed build order

Each stage should be implemented and manually verified in the running app before moving to the
next — this is a lot of interacting behavior and each piece needs to be trustworthy on its own.
Stages 1-5 (phase switch + baseline capture; ordinary FS cascade; planning-phase buffer glue; task
progress tracking & anchoring; chain registry & classification) are done — see "Already
implemented" above. Next up is Stage 6.

### Stage 6 — Execution-phase chain-aware relay-runner cascade (next up)

This is what "Stage 4" originally meant before the chain discussion, refined with the classification
from Stage 5. It only changes behavior when a project is in the `execution` phase — Stage 2's
planning-phase rule (forward-only, regardless of chain) is completely unchanged.

- Whenever a task's position/estimate changes (drag, resize, or a new `Record Remaining Duration`
  entry from Stage 4) **and its project is in execution**:
  - If the task's assigned chain has `is_critical = True`: its ordinary (non-buffer) `FS`
    successors are kept in lock-step **bidirectionally** — pushed later *or* pulled earlier to
    always sit exactly at `task.col + task.duration + lag`, cascading transitively along the
    critical chain. This is the "relay runner" mentality: if a critical-chain task finishes early,
    the next runner starts immediately, they don't wait around for the baton.
  - If the task's chain is anything else (a specific `Feeding-NN`, or unset/`None`): successors are
    only ever **pushed forward** automatically — identical to today's Stage 2 rule, never pulled
    earlier automatically. A feeding-chain task finishing early is fine; the feeding buffer
    downstream absorbs that slack (Stage 7), and feeding-chain tasks are expected to run close to
    as-late-as-possible by design. A human can still manually drag a feeding-chain task earlier to
    grab an opportunity (e.g. a resource freed up sooner than planned) — that stays a deliberate
    manual choice, not an automatic one.
  - Either way, propagation still **stops at a buffer** — buffer-type successors are never
    pushed/pulled by this rule; Stage 7 owns what happens to a buffer.
- **Known limitation, explicitly out of scope**: this cascade only follows *declared*
  `predecessors` links. It cannot detect an implicit dependency caused by two tasks on different,
  unlinked chains competing for the same constrained resource — the classic CPM-vs-CCPM gap (the
  *critical chain*, unlike the critical *path*, can run through a resource-constrained feeding
  task with no direct logical link to the nominal critical path). If that happens, it'll show up
  as an overlap on the resource-loading view, not as an automatic reschedule — the user needs to
  add an explicit link or resequence manually. See also "Explicitly out of scope" below.

### Stage 7 — Execution-phase buffer absorb-then-overflow

Supersedes the original single-direction sketch — now genuinely bidirectional, with growth capped
at the buffer's baseline size.

Applies only to buffer tasks whose owning project's `phase == 'execution'`, triggered whenever a
buffer's `PB`/`FB` predecessor's finish changes, in either direction:

- `required_start = predecessor.col + predecessor.duration + lag`
- `current_end = buffer.col + buffer.duration` (the buffer's end *right now* — not the Stage 1/4
  baseline, which is only for later comparison/reporting)
- **Encroachment** (`required_start > buffer.col`): the buffer absorbs it by shrinking —
  `buffer.col = required_start`, `buffer.duration = current_end - required_start`, end stays
  fixed. If `required_start > current_end`, the buffer is **fully consumed** (`duration` clamped
  to `0`), and the overflow cascades through to the buffer's own `FS` successor (the critical-chain
  merge task) using Stage 6's cascade from that point on — this is the moment a feeding chain has
  effectively become the (new) critical chain through that merge point, exactly as the user
  described it.
- **Slack** (`required_start < buffer.col`): new behavior — the buffer grows to absorb it by
  moving its start earlier (`buffer.col = required_start`), end still fixed, **capped at the
  buffer's own baseline duration** (`task['baseline']['duration']`, captured at the
  planning→execution transition). Once the buffer has grown back to its baseline size, further
  slack just opens a gap in front of the (capped) buffer instead of growing it more — a buffer
  bigger than its original sizing isn't meaningful protection, it's just an idle gap.
- The buffer's own end (and therefore the merge task) is **never** pulled earlier by this rule —
  only Stage 6's critical-chain bidirectional rule can move the merge task earlier, and only
  because the merge task is itself on the critical chain, not because the buffer grew.

### A subtlety already resolved

Whether a task/buffer reacts via Stage 2/3 or Stage 6/7 depends on the **current** phase of its
project at the moment a move happens — not on a one-time snapshot of "the critical chain" taken
when buffers were originally cut. This was a deliberate design choice: tasks get added to an
executing project's critical chain later (rolling-wave planning, scope discovered mid-project),
or get decomposed into smaller tasks — the push behavior should just react correctly to
whatever the dependency graph looks like _right now_, keyed off each task's type/phase/chain,
rather than needing to re-run some global "recompute the critical chain" step.

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
- **Fever chart / % buffer consumption reporting, and full plan-vs-baseline comparison UI.** Was
  already on the project's README Todo list before this work started. Stage 4's (widened) baseline
  capture is preparation for this — the data will exist — but the actual reporting/comparison UI
  for showing stakeholders "the plan then vs. now" is not part of this work.
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

## Open questions for whoever picks this up next

- Whether "the merge task" in Stage 3/7 (a buffer's `FS`/`FB` successor) needs to be uniquely
  identifiable — i.e., what happens if a buffer somehow has more than one such successor. Not
  discussed; likely worth a guard/validation when this is built. `chain_id` doesn't resolve this
  ambiguity by itself.
- Exact default color palette for the 5 seeded chain entries (`Critical` + `Feeding-01`..`04`) —
  needs picking at implementation time; freely editable afterward via `Manage Chains...` regardless.
- Whether removing a `Chains` entry that's still referenced by tasks should be blocked, or should
  null out `chain_id` on those tasks — not discussed. (`remove_project` sets the precedent of
  unassigning rather than blocking.)
- Whether a buffer's `chain_id` should be validated against the chain(s) of the tasks feeding it
  (e.g. warn if inconsistent) — not discussed; currently assumed trusted/unvalidated, consistent
  with everything else in this system that the user sets manually.
- Whether the progress-stripe/chain-stripe edge assignment (progress stripe implemented on the
  bottom edge in Stage 4; top edge reserved for Stage 5's chain color) reads well once the chain
  stripe is added, or should be swapped.
