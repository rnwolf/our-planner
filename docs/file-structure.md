# CCPM Project Data

The CCPM Skill attempts to create CCPM project schedules.

## Files formats

### tasks.csv

**tasks.csv** — `id, name, duration_safe, duration_aggressive (optional), predecessor_ids, resource_ids, url (optional)`

```csv
id,name,duration_safe,predecessor_ids,resource_ids,url
A,Spec,10,,blue,https://example.com/wiki/spec
B,Build,20,A,green,https://example.com/tickets/build
F,Commission,10,D;E,red,
```

- `predecessor_ids`: semicolon-separated links. A bare id is Finish-to-Start; typed links with lag are supported: `A:SS+2`, `A:FF`, `A:SF`. The network must be acyclic; multiple entry or exit tasks are fine (the scheduler anchors them to synthetic Start/Finish milestones).
- Every task needs a **positive duration** and **at least one resource** — a task without a resource cannot contend for capacity, so it cannot participate in critical chain identification.
- If `duration_aggressive` is missing, the skill applies the classic 50% cut to `duration_safe`. If your estimates are _already_ aggressive, say so in the prompt — it changes buffer sizes by 2x.
- `url`: optional link to a ticket/wiki page; it is carried into the outputs.
- `tags`, `colour` (optional, written by our-planner's `File → Export CCPM Network...`): comma-separated task tags and the task's canvas colour. The scheduler currently ignores unknown columns (passthrough to `schedule.csv` is planned); our-planner's import reads them back if present.

### resources.csv

**resources.csv** — `id, name, capacity, url (optional)`; capacity defaults to 1.

A list of the project resources and default capacity.

### `calendar.csv`

**calendar.csv** (optional) — availability overrides:

```csv
resource_id,from,to,capacity
green,2,4,0
red,0,10,0
```

Overrides a resource's capacity on the day range `[from, to)`. The bracket notation is deliberate — it is the mathematical convention for a **half-open interval**: the square bracket `[` means `from` is **included**, the round bracket `)` means `to` is **excluded**. So `green,2,4,0` means green is unavailable on days 2 and 3, and back at work on day 4 — the range covers `to − from` days, never `to` itself.

Why half-open? It matches how the schedule itself works: a task with `start=2, finish=4` occupies days 2 and 3 too, so a calendar row and a task span with the same numbers cover exactly the same days, and adjacent ranges like `[0,5)` and `[5,10)` butt together without overlapping or leaving a gap.

Days are working-day offsets from day 0 (the same axis as the Gantt chart). `capacity 0` = unavailable (holiday, another project); a higher value models temporary extra capacity (e.g. a contractor). Outside the listed ranges, the resource's default capacity from `resources.csv` applies. Ranges for the same resource must not overlap.

Tasks run **contiguously** — they never pause across an outage, so a task is scheduled entirely before or entirely after it.

### `schedule.csv`

Every task and buffer with `start`/`finish` day offsets, chain membership (`critical`, `feeding-n`), and link notation. Buffers attach via CCPM-specific `:PB`/`:FB` link types (they behave differently from work during execution — slippage consumes them rather than pushing them).

our-planner's `File → Import CCPM Schedule...` additionally reads optional `tags` and `colour` columns (`color` accepted as an alias) if present, and tags every imported row `ccpm`.

### `summary.md`

— critical chain sequence, project duration, buffer sizes, and the promised completion date (= end of the project buffer). Task/resource urls become clickable links here.

### `gantt.png`

The chart: critical chain in cross-hatched dark red, feeding chains colored, buffers hatched gold/khaki with a commitment-date diamond, dependency arrows (non-FS links labeled), and a resource-utilization panel where red means over capacity and grey hatching means unavailable.
