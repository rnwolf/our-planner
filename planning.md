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
in the running app. **All 7 stages of the originally agreed build order (see each "Stage N — done"
heading below) are now complete.** Stage 8 (fever chart reporting) has since been added as a new
build item — see "Remaining work" below — now that Stages 4/7's data capture makes it practical to
build. What's left after Stage 8 is everything listed under "Explicitly out of scope" (automated
critical-chain detection, resource-constrained scheduling, event sourcing, and fever chart *export*
specifically, deferred as a fast-follow after Stage 8's on-screen viewing).

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

## Remaining work

### Stage 8 — Fever chart reporting (next up)

CCPM's key buffer-management tool: for a given buffer, plots % of its protected chain complete
(x-axis) against % of the buffer consumed (y-axis) over time, with green/yellow/red zones showing
whether the buffer is being consumed faster than the chain is progressing - i.e. whether the
insurance banked in that buffer is still sufficient, or a recovery plan is needed now.

- **Reference chart** (confirmed with the user):
  https://www.critical-chain-projects.com/medias/images/fever_chart_mono_projet_en.png - the
  classic sloped/diagonal zone model, *not* flat thirds. Reading that chart: at 0% chain complete
  the green/yellow boundary sits around 10% buffer consumed and yellow/red around 27%; at 100%
  chain complete those rise to roughly 65% and 82%. Approximated as two straight lines - `y =
  0.55x + 10` (green/yellow) and `y = 0.55x + 27` (yellow/red) - early consumption is judged more
  harshly than the same % consumed later in the chain. Treat the exact slope/intercept as tunable
  constants to nudge once real project data is on screen, not something to get pixel-perfect from
  a reference screenshot.
- **What chain a buffer's x-axis tracks**: a feeding buffer's own `chain_id` (e.g. `Feeding-01`)
  identifies its protected feeding chain; the project buffer's x-axis is the `Critical` chain.
  Reuses the existing chain-tagging convention directly - no new field needed.
- **% chain complete as of a historical date D needs one new model method.**
  `get_task_progress_fraction` (Stage 4) only computes progress *as of now* (via
  `get_latest_remaining_duration`, unfiltered by date). Need a new
  `get_task_progress_fraction_as_of(task_id, date)`: replay `remaining_duration_history` filtered
  to entries with `date <= D` (same `(date, index)` most-recent tie-break as the existing same-day
  bug fix), returning `0.0` if the task hadn't started as of D. Chain completion is then the
  `baseline.duration`-weighted average of this across every ordinary (non-buffer) task sharing the
  buffer's `chain_id` and `project_id`.
- **% buffer consumed as of D** needs no new method - look up the latest `buffer_size_history`
  entry with `date <= D` (or the `baseline` itself if none yet), compute `(baseline.duration -
  duration_at_D) / baseline.duration`.
- **Trajectory**: one point per distinct date in the union of every chain-tagged task's
  `remaining_duration_history` dates and the buffer's own `buffer_size_history` dates (plus the
  baseline's `captured_at` as the starting `(0%, 0%)` point) - a staircase across history, not
  just today's single dot, matching the reference chart's `W1..Week 6` weekly-snapshot style.
- **Rendering**: hand-drawn on a Tkinter `Canvas` (axes, sloped zone bands, plotted
  trajectory/labels) - confirmed with the user, consistent with how the rest of the app already
  draws everything (the task grid, dependency arrows) rather than adding a charting dependency.
- **Access point**: new `View Fever Chart...` right-click item on a buffer task, mirroring `View
  Buffer History...`'s placement and dialog-based approach.
- **Scope for this stage, confirmed with the user**: on-screen viewing only. PDF/PNG export is a
  deliberate fast-follow, not part of this stage - see "Explicitly out of scope" below for why
  that's still easy to add later (the existing PNG/PDF exports already work by independently
  redrawing the scene in PIL/reportlab rather than screenshotting the canvas, so a fever chart
  would follow the same "redraw the same data with each library's own primitives" pattern already
  established in this codebase).
- Not yet decided: single buffer at a time (as scoped above) vs. also a project-wide dashboard
  showing every buffer's chart together - flagged in "Open questions" below.

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
- **Fever chart PDF/PNG export.** Now that Stage 8 covers on-screen viewing, exporting it is a
  deliberate fast-follow, not bundled into that stage. Confirmed practical: the existing PNG/PDF
  exports already work by independently redrawing the whole scene in PIL/reportlab respectively
  rather than screenshotting the Tkinter canvas (e.g. the dashed `PB`/`FB` lines needed their own
  manual PIL dashed-line helper) — a fever chart export would follow the same pattern, redrawing
  the same computed data points/zone bands a second and third time with each library's own drawing
  primitives. Rejected alternative: Tkinter's `canvas.postscript()` + Ghostscript conversion, which
  would pull in an external system dependency with the same cross-platform fragility already seen
  with `uv`/Tkinter on Linux and Windows.
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
- **Stage 8**: single-buffer-at-a-time viewing (`View Fever Chart...` on one buffer, as currently
  scoped) vs. also a project-wide dashboard showing every buffer's chart together at a glance -
  not decided; real CCPM practice often means scanning all of a project's buffers regularly, so
  this may be worth revisiting once the single-buffer version exists and is being used.
- **Stage 8**: the sloped zone boundary formula (`y = 0.55x + 10` / `y = 0.55x + 27`) is a visual
  approximation from a reference screenshot, not a verified canonical formula - treat as a
  starting point to tune once real project data is being viewed, not as authoritative.
- **Stage 8**: what should happen for a task with no `baseline` when computing chain-%-complete
  (e.g. a task added to the chain after the project's planning→execution transition) - exclude it
  from the weighted average, or fall back to its current duration? Not discussed.
