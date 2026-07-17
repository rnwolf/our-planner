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

## Keyboard shortcuts

- **Ctrl+A**: Select all visible tasks
- **Escape**: Clear the current selection
- **Delete**: Delete the selected task(s), after confirmation — also available as Tasks → Delete Selected
- **Alt+F / Alt+E / Alt+I / Alt+T**: Open the File, Edit, Filter and Tasks menus
- **Arrow keys**: Scroll the task grid
- **Ctrl+Plus / Ctrl+Minus / Ctrl+0**: Zoom in, zoom out, reset zoom
- **Ctrl+E**: Open the export dialog