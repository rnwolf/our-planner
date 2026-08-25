# User Guide

This page will have more information on how to use the application.

It currently follows what I consider normal practice for desktop GUI applications.

## Basic operations

1. **Create tasks**: Click and drag on the task grid to create new tasks
1. **Move tasks**: Click and drag existing tasks to reposition them
1. **Resize tasks duration**: Click and drag the left or right edge of a task
1. **Add dependencies**: Click the connector circle on the right edge of a task and drag to another task
1. **Edit task details**: Right-click on a task and select from the context menu
1. **Zoom in and out**: See details and overview with Ctrl+Scroll-wheel to zoom in and out
1. **Export your data**: Use the Network menu to export your data in various formats

## Export files

**Network → Export... → CSV** writes three files (columns aligned with the ccpm-scheduler vocabulary):

- `..._tasks.csv` — `id, name, project, chain, row, start_day, start_date, end_date, duration, realistic_duration, optimal_duration, predecessor_ids, resource_ids, tags, colour, url`. `start_day` is the absolute timeline day (day 0 = timeline start). `resource_ids` uses `id:allocation` tokens: `5:2;7` means 2 units of resource 5 and 1 unit (the default) of resource 7. `predecessor_ids` uses the same link notation as the app's dialogs (`3;5:SS+2`).
- `..._resources.csv` — `id, name, capacity, tags` (capacity = the resource's usual per-day value).
- `..._resource_loading.csv` — per-day loading, capacity, and utilization for each resource.

**Network → Export CCPM Network...** writes the ccpm-scheduler input files (`tasks.csv`, `resources.csv`, `calendar.csv`) plus optional `tags`/`colour` columns; any export notes go to a `notes.txt` alongside them. **Network → Import CCPM Schedule...** reads those tags/colours back if the `schedule.csv` carries them, and tags every imported row `ccpm`.

## Scheduling with CCPM

**Network → Schedule with CCPM...** validates a project's network, builds a critical-chain schedule in-process, and imports the result as a new project next to the source — the source is left untouched, so a hand-drawn plan and the CCPM-scheduled version can be compared side by side.

Resources are shared globally across every project in a plan file, so a resource being scheduled here may already be committed to tasks in *other* projects over the same days. Before scheduling, a **CCPM Scheduling Options** dialog offers **Account for capacity already committed to other projects**, checked by default: with it on, each resource's exported capacity is reduced by its load from every other project's tasks first, so the new schedule doesn't plan against capacity someone else already has a claim on — any resource actually reduced this way is named in the result dialog's Notes. Unchecking it schedules against each resource's full nominal capacity instead, ignoring other projects entirely (the previous behaviour, still available for when a resource pool genuinely isn't shared, or for comparing against the unconstrained plan). **Network → Export CCPM Network...** applies the same reduction unconditionally, since that flow has no dialog step to offer the choice in.

See [Sample Portfolio Walkthrough → Resource Over-Allocation](sample-portfolio-walkthrough.md#resource-over-allocation-is-this-actually-a-problem) for the read-only, whole-portfolio view of the same cross-project contention this option feeds directly into scheduling.

## CCPM buffer sizing method

Each project has a **CCPM Method** (Projects → Manage Projects...) that selects how the scheduler sizes its project and feeding buffers: `cap` (Cut & Paste — buffer = the safety removed from the chain; the default and the most explainable), `hchain` (50% of chain length), or `rsem` (root-squared error). Both **Schedule with CCPM...** and the **Export CCPM Network...** command hint use the project's method. Buffers can always be resized by hand before the project enters execution mode. Formulas and trade-offs are documented in the ccpm-scheduler package's `docs/buffer-sizing.md`.

## Recording status updates and reason codes

While a task is under way, its remaining-duration estimate is expected to change as work progresses. **Record Remaining Duration...** (right-click a task, or Tasks menu) captures each update together with:

- **Reason** — a primary reason picked from a fixed list: `On Time`, `Task Variability`, `Waiting for Full Kit`, `Waiting for Resource`, `No Early Start`, `Parkinson's Law`, `Multitasking`, `Waiting in Backlog`, `Unplanned Events`, `Other / Unexplained`. `On Time` is the default, so an unremarkable update costs no extra clicks — anything that actually needs explaining just means picking a different reason.
- **Note** *(optional)* — free text for whatever detail doesn't fit the reason alone, captured in a multi-line box.

This is deliberately quick to record in the moment, but it's the raw material for a more valuable exercise: **periodically reviewing the recorded reasons as a team to find root-cause patterns** — e.g. spotting that most of a project's buffer consumption is "Waiting for Resource" — and acting on them. That review is the actual point of capturing this data, not the remaining-duration number alone. This is an essential input into investigations into improving team and delivery performance.

Where it shows up:

- **View Duration History...** (task right-click menu) — the full history for one task, reason and note included.
- **Fever Chart** — toggle **Show Status Update Reasons/Notes** to see the annotated updates for a buffer's protected chain alongside its fever chart.
- **Reports → Status Update Log...** — every recorded update for a project (not just the annotated ones), scoped by whatever's active on the Filter menu. Includes a **Task URL** column linking straight back to that task's own page — wherever the team collaborates on interventions — and a checkbox to narrow the list down to only the updates that carry a reason or note. **Download Data (CSV)...** exports exactly what's on screen, for a pivot table or feeding it into whatever reporting the team already uses to track delivery performance.

## Recent files

**File → Recent** lists the 5 most recently opened/saved files, most recent first and numbered `1`–`5`. Open the submenu and press the number key to reopen one without going through the file picker again.

## Versioned Project Folders

our-planner has no undo of any kind for a plain project file — a mistake sticks unless you remembered to Save As under a new name first. **File → New Versioned Project...** creates an opt-in alternative: a fresh, empty directory backed by a real local git repository, giving you fine-grained undo/redo plus deliberate save points. A plain **File → Open/Save** project is completely unaffected — versioning only ever applies to a directory you deliberately create this way, never to a folder the app decides to adopt on its own.

**Reopening a versioned project later needs no special step.** Use **File → Open...** (or **File → Recent**) on its `project.json` exactly as you would for a plain file. our-planner recognizes the workspace automatically from a `.our-planner-workspace.json` marker file sitting next to it (only in that exact directory — a marker in a parent folder doesn't count) and re-activates versioning right away: the window title shows `[versioned]` again and Undo/Redo/Jump to Version/Save Version... light back up in the Edit and File menus. There's no separate "open versioned project" command.

Once a project is versioned (the window title shows `[versioned]`):

- **Every meaningful edit is autosaved automatically** to a local `autosave` branch — no action needed, and nothing to remember to save. A pure display toggle (e.g. Show Tags on Tasks) never creates a commit; only a real change to the project does.
- **Edit → Undo (Ctrl+Z) / Redo (Ctrl+Y)** step one autosaved edit at a time, exactly like a conventional editor's undo/redo. Making a new edit after undoing discards whatever you'd undone past, the same as any other app.
- **Edit → Jump to Version...** lists `autosave`'s fine-grained edit history with real timestamps (e.g. "the version from before lunch") in a pick list and jumps straight to the one you choose, rather than stepping through Undo repeatedly. This is scoped to `autosave` only — it does not list or restore `main`'s deliberate `Save Version...` checkpoints (see below).
- **File → Save Version...** is a deliberate checkpoint: it squashes every autosaved edit since the last checkpoint into one clean, optionally-named commit on the `main` branch, so `main`'s history stays a short, meaningful list of real versions rather than every individual edit. There's nothing to save if nothing changed since the last checkpoint.

To browse or restore one of `main`'s named checkpoints, there's currently no in-app equivalent of Jump to Version — open a terminal in the workspace folder and run `git log main` to see them, then `git checkout <commit> -- project.json` (followed by reopening the file in our-planner) to restore one.

**Disaster recovery is manual, by design.** This app never pushes anywhere on your behalf. To back up a versioned project off your machine, open a terminal in the workspace folder and add a normal git remote yourself — `git remote add origin <url>` then `git push origin main` — the same way you would for any other git repository. Only `main`'s checkpoints are meant to be pushed; the `autosave` branch is purely local, fine-grained scratch history.

If `git` isn't installed, or has no `user.name`/`user.email` configured, **New Versioned Project...** tells you so up front rather than creating a half-working workspace.

## Keyboard shortcuts

- **Ctrl+A**: Select all visible tasks
- **Escape**: Clear the current selection
- **Delete**: Delete the selected task(s), after confirmation — also available as Tasks → Delete Selected
- **Alt+F / Alt+E / Alt+I / Alt+T**: Open the File, Edit, Filter and Tasks menus
- **Arrow keys**: Scroll the task grid
- **Ctrl+Plus / Ctrl+Minus / Ctrl+0**: Zoom in, zoom out, reset zoom
- **Ctrl+E**: Open the export dialog
- **Ctrl+Z / Ctrl+Y**: Undo / Redo the last autosaved edit — versioned projects only (see [Versioned Project Folders](#versioned-project-folders))