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
1. **Export your data**: Use the File menu to export your data in various formats

## Export files

**File → Export... → CSV** writes three files (columns aligned with the ccpm-scheduler vocabulary):

- `..._tasks.csv` — `id, name, project, chain, row, start_day, start_date, end_date, duration, realistic_duration, optimal_duration, predecessor_ids, resource_ids, tags, colour, url`. `start_day` is the absolute timeline day (day 0 = timeline start). `resource_ids` uses `id:allocation` tokens: `5:2;7` means 2 units of resource 5 and 1 unit (the default) of resource 7. `predecessor_ids` uses the same link notation as the app's dialogs (`3;5:SS+2`).
- `..._resources.csv` — `id, name, capacity, tags` (capacity = the resource's usual per-day value).
- `..._resource_loading.csv` — per-day loading, capacity, and utilization for each resource.

**File → Export CCPM Network...** writes the ccpm-scheduler input files (`tasks.csv`, `resources.csv`, `calendar.csv`) plus optional `tags`/`colour` columns; any export notes go to a `notes.txt` alongside them. **File → Import CCPM Schedule...** reads those tags/colours back if the `schedule.csv` carries them, and tags every imported row `ccpm`.

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

## Keyboard shortcuts

- **Ctrl+A**: Select all visible tasks
- **Escape**: Clear the current selection
- **Delete**: Delete the selected task(s), after confirmation — also available as Tasks → Delete Selected
- **Alt+F / Alt+E / Alt+I / Alt+T**: Open the File, Edit, Filter and Tasks menus
- **Arrow keys**: Scroll the task grid
- **Ctrl+Plus / Ctrl+Minus / Ctrl+0**: Zoom in, zoom out, reset zoom
- **Ctrl+E**: Open the export dialog