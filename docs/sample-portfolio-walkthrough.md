# Sample Portfolio Walkthrough

`sample-app-file/realistic-portfolio.json` is a generated example file — a whole
organisation's project portfolio, built to be opened and explored rather than
just read about. Where the [User Guide](user-guide.md) documents individual
features, this page walks through one realistic file feature by feature, so
you can see how the pieces fit together: CCPM scheduling, buffer consumption,
full-kit readiness, resource loading, and the reports that sit on top of all
of it.

It's also a good file to hand to someone else — a colleague, a client, an
audience at a demo — so they can click around a portfolio that already has a
story in it, instead of an empty grid.

## Open it

**File → Open...** and pick `sample-app-file/realistic-portfolio.json` from
the repository. It's a plain save file — nothing else to set up.

## What it models

An organisation of 30 people (`dev`, `qa`, `designer`, `ba`, `devops`,
`lead`, `architect`, and `data` specialists), each represented as a named
resource tagged with their role, running a portfolio spanning roughly three
months in the past through one month ahead of today. Two kinds of work
coexist on the same canvas, sharing the same 30-person resource pool — the
way a real portfolio actually competes for the same people:

- **19 mini-projects**, each a small rolling-wave network (`small`/`medium`/
  `large` shapes — Analysis/Build/Test/Deploy and variants) scheduled for
  real through **Network → Schedule with CCPM...**, with a team kept constant
  for the life of the project. Buffer sizes, the critical chain, and the
  feeding-buffer merge points are all genuine scheduler output, not
  hand-picked numbers.
- **One "Ad-hoc / Backlog Work" project** — about a quarter of the
  portfolio's total task volume, tagged `backlog` plus a priority
  (`P1`/`P2`/`P3`), pulled from the roster independent of any project team,
  and deliberately never run through CCPM scheduling. This is the other half
  of the operating model the mini-projects assume: triage work into a small
  CCPM-scheduled project, or leave it on the backlog to be pulled by
  priority.

Because generation is anchored to whenever it was last run, some of the 19
mini-projects land in the past (already complete), some straddle today
(in progress), and a few haven't started yet — a realistic mix of every
project phase existing on the canvas simultaneously, exactly like a real
portfolio.

## Task colours: a team convention, not a status

Every task on the grid is filled with whatever colour this file gave it —
`color` is a free-form field, and the app never assigns or changes it on its
own. This sample uses one convention, by role:

```python
ROLE_COLOR = {
    'dev': 'LightBlue',
    'qa': 'LightGreen',
    'designer': 'MediumOrchid',
    'ba': 'Khaki',
    'devops': 'Orange',
    'lead': 'Gold',
    'architect': 'CornflowerBlue',
    'data': 'LightSalmon',
}
```

(`sample-app-file/generate_sample_app_file.py`). Every mini-project task is
coloured by the role of the person assigned to it, and every backlog task is
a flat `LightYellow` regardless of who's on it — so scanning the grid answers
"who's doing what kind of work across the whole portfolio right now", the
same lens a resource manager needs when deciding whether the org has enough
of a given skill committed versus free.

**This is genuinely a decision your team has to make, not something the app
assumes for you** — colour-by-role is only one workable convention.
Colour-by-project (so a team can pick its own work out from a shared,
multi-project canvas at a glance) or colour-by-priority for a
backlog-heavy team are just as valid; whichever is chosen, it's worth writing
down and agreeing once, since nothing enforces consistency automatically -
**Right-click a task → Edit Task Color** sets it per task, and it's easy for
a convention to quietly drift once several people are creating tasks.

Two things colour does *not* signal here, worth agreeing on explicitly since
they're easy to assume by default:

- **Completion isn't a colour.** A `done` task keeps its role colour - the
  box fill is deliberately left untouched by state. What *does* change is
  the small background rectangle directly behind the task's id/description
  text: light green for `done`, dark grey for `buffered`, both easy to miss
  at a glance next to a bright role colour. The clearer at-a-glance
  "how much of this is actually finished" signal is the progress stripe
  along the bottom edge of the box instead.
- **Chain membership isn't a colour either** - that's the thin stripe along
  the *top* edge of a task (a chain's own assigned colour, set when it's
  created), independent of both role colour and state.

## Fever charts: where the safety actually went

CCPM strips safety out of individual task estimates and pools it into
project/feeding buffers instead, so a task running long shouldn't show up as
a blown task date — it should show up as buffer consumption. Open **Reports →
Fever Chart** on a few of the completed projects and compare:

- **Customer Portal Refresh**'s first feeding buffer finishes deep in the red
  zone (consumption around 300% of its own baseline) — several tasks feeding
  into that merge point ran long, and the buffer that was supposed to absorb
  it wasn't big enough to fully cover the overrun.
- **Returns Workflow**'s project buffer, by contrast, finishes comfortably in
  the green (negative consumption — it finished ahead) — its chain ran close
  enough to plan that the buffer barely got touched.
- **Loyalty Programme Revamp**'s project buffer is the sharpest story of the
  three: it tracks green through the first half of the chain, then a run of
  tasks going badly wrong mid-project drives it straight through yellow into
  red, finishing with the buffer **completely exhausted** — consumption past
  100% of baseline, meaning this project would genuinely have missed its
  promised date without the buffer's early warning prompting an intervention.
  That sharp green-to-red jump partway across the chart, rather than a
  gradual drift, is itself worth noticing — it's usually a sign of one
  correlated cause (the generator models this as a "troubled" project, where
  most of that project's tasks ran long together) rather than ordinary
  task-by-task noise.

Same organisation, same estimating discipline, genuinely different outcomes
— which is the point of tracking it per-project rather than assuming one
number describes the whole portfolio.

Toggle **Show Status Update Reasons/Notes** on the fever chart to see why:
every recorded status update in this file carries a reason (`On Time`,
`Task Variability`, `Waiting for Resource`, `Parkinson's Law`, `Multitasking`,
`Unplanned Events`, `Other / Unexplained`), the same fixed list a real user
picks from in **Record Remaining Duration...**. **Reports → Status Update
Log...** lists every recorded update for a project in one place if you want
to see the full trail rather than just the annotated points on the chart.

## Full-Kit Readiness: catching trouble before it starts

The three mini-projects that haven't started yet (still in `planning`
phase) are the interesting case for **Reports → Full-Kit Readiness...** —
unlike fever charts, full-kit readiness matters before execution begins, not
just during it.

Open the report for whichever of the three not-yet-started projects has the
lowest readiness percentage. You'll typically see something like: the first
task (discovery/analysis) and the later QA/deploy tasks already have a
full-kit date — that kind of task only needs information known at planning
time (requirements, environment, a runbook), so a well-run project gets it
done well ahead of the kickoff. The design/build tasks in between, though,
show **Not Kitted** — they genuinely need their own predecessor's actual
output (the discovery findings, the agreed design) before there's anything
real to kit, so they can't have been finished yet.

That's the distinction this report exists to surface: some gaps are just
"still waiting on upstream work, as expected"; others are "this should have
been sorted out by now and wasn't" — missing-but-predictable dependencies
discovered mid-execution are one of the most common causes of a project
grinding to a halt partway through. The report doesn't decide which is which
for you, but it puts every task's status in one place so you can.

## Resource Over-Allocation: is this actually a problem?

**Reports → Resource Over-Allocation...** aggregates load across every
project a resource (or a tag/role) is committed to — not just whatever's
currently on screen — which is exactly the kind of clash a single project's
own grid can't show you.

Switch to **By Resource** and look for **Ben Carter** — he's double-booked
at 200% of capacity for a couple of days in August, drawn from two different
projects. Expand the finding and the drill-down shows why it's not
necessarily urgent: one of the two tasks (**Build-A**, in *Pricing Engine
Update*) is on that project's **Critical** chain, but the other (**Build-B**,
in *Contract Renewal Tool*) is on a **Feeding** chain — which by definition
has slack absorbing exactly this kind of clash. This is the judgement call
the report is built for: a critical-chain/critical-chain clash needs a
decision (shift a task, reassign a resource); a critical/feeding clash
usually doesn't, because the feeding buffer is already there to absorb it.

Switch to **By Tag** and you'll typically see the same clashes reappear,
aggregated by role instead of by name — in this file no *role* is
saturated in aggregate even though individual people are double-booked,
which is itself worth noticing: a tag-level view exists for the opposite
case, where three developers are each individually under capacity but the
role as a whole is genuinely over-committed, something no single resource's
row would ever show as red.

Ben Carter's double-booking exists here because both mini-projects were
scheduled independently, each unaware of the other's claim on him — this
file predates **Account for capacity already committed to other projects**,
the option now offered by **Network → Schedule with CCPM...** (see
[User Guide → Scheduling with CCPM](user-guide.md#scheduling-with-ccpm)).
Re-scheduling either project with that option checked would reduce his
exported capacity by the other project's load over the clashing days,
pushing the lower-priority task out rather than leaving both projects
planned against the same person at the same time — the report above still
matters for judging clashes across projects that were scheduled separately
(or where a resource's other commitment isn't itself a CCPM-scheduled
project), but a single project's own scheduling run can now avoid creating
this particular kind of clash in the first place.

## Filtering resources by tag when assigning

This file names every resource after a real person (`capacity=1.0`) and
tags them with their skill (`ba`, `dev`, `qa`, `designer`, `devops`, `lead`,
`architect`, `data`) — one of two ways our-planner can model a resource; the
other is a named *role* resource with `capacity` set above 1 (e.g. a pooled
`Developers` resource at capacity 3), which this file doesn't currently use.

Right-click any task → **Edit Task Resources** and try the tag combobox next
to the search box — filter to `qa`, for instance, to narrow the available
list down to just the testers, then combine it with a name search. It's
scoped to this one dialog deliberately: whether a resource ends up
over-allocated once assigned is a question for the Resource Over-Allocation
report above, not something this dialog checks live — the positions here are
still provisional until a CCPM schedule run actually levels them.

## Regenerating the file

`sample-app-file/generate_sample_app_file.py` builds this file from scratch
(`uv run python sample-app-file/generate_sample_app_file.py`) — a fixed RNG
seed keeps the story consistent run to run, but the exact numbers above will
drift slightly each time it's regenerated, since the three-month lookback
window is always anchored to whichever day it was generated on. The shape of
the walkthrough — some projects deep in the red (occasionally a project
buffer completely exhausted), some comfortably green, a few not-yet-started
projects with partial full-kit readiness, at least one resource
double-booked across projects — is what the generator is designed
to reproduce, not the specific numbers quoted here.
