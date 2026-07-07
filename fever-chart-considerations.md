# What the fever chart must answer

Not "how have we performed?" but **"should I intervene today?"** Every quantity below is therefore based on the *current forecast*, not on historical overruns. Both axes are recalculated from scratch at every status update, and both are allowed to move backwards — that's information, not an error.

NOTE: The Frontier ÷ Horizon formulation discussed below isn't in the published CCPM literature it's a coherent extension.

## One chart per buffer, one point per status update

Each buffer (the Project Buffer and every Feeding Buffer) gets its own fever chart. 
Each status update produces a coordinate **(Progress %, Buffer Consumption %)**, and the chart shows the trajectory of those points over time. 
Each status update happens at a recorded point in time, which is displayed, so that we can see at a glance when the last update was made.
Each status point on the chart is connected by a line so that we can follow the sequence of updates by eye which will help us determine trends more easily.
The buffer as it exists in the schedule is not a fixed object: the protected project end date/milestone is fixed, so when the chain expands, the buffer visible in the plan compresses.
For feeding buffers, movement in either the feeding chain tasks or the critical chain merge task can impact on the size of the feeding buffer. But it will get no greater than the baseline buffer agreed at the start of the project.


There are four cleanly separated calculations:

### 1. Current Protected Schedule Length (CPSL) — the X-axis denominator

The forecast elapsed time from the start of the protected chain to the **forecast finish of the terminal protected task** (the last work task before the buffer). Critically:

- It's a *timeline*, not a sum of task durations — it naturally includes calendar gaps, mandatory waits, and resource delays that a "sum of durations" denominator gets wrong.
- It **excludes the buffer itself**. The buffer is protection, not planned progress; when the chain reaches the buffer, progress is 100%.
- It's defined to the *terminal protected task's finish*, not "the start of the buffer," because the buffer start floats: the protected milestone is fixed, so when the chain slips, the buffer start moves right and the buffer compresses. Defining CPSL via the buffer would make the denominator depend on remaining buffer — circular.
- It's the **forecast** length, updated as estimates change. (The transcript debates baseline-vs-forecast; you argued for forecast and the conversation concludes that's right for an operational tool — discovering the journey is longer should show up as lower progress, like a satnav rerouting.)

### 2. Protected Progress Frontier (PPF) — the X-axis numerator

The latest point on the protected schedule that is **known with certainty**: every protected activity scheduled to finish before that point is confirmed complete. If a chain task is 50% done, the frontier sits at its predecessor's finish. This resolves the ambiguity of "% complete" on parallel/merging paths objectively — the frontier can't advance past an incomplete task even if later parallel work is finished.

### 3. Progress %

```
Progress = PPF ÷ CPSL   (Frontier ÷ Horizon)
```

If a task overruns and the horizon moves out, progress drops even as the frontier advances — e.g. week 1: 30/100 = 30%; week 2: frontier at 40 but forecast now 120 days → 33%, not the misleading 40%.

### 4. Buffer Consumption % — the Y-axis

```
Buffer Consumption = forecast lateness of the protected chain ÷ baseline buffer size
```

where forecast lateness = (forecast finish of terminal protected task) − (its scheduled finish in the plan). Key rules:

- Based on the **current forecast**, so it decreases when downstream tasks recover time. A task finishing 5 days late followed by another finishing 4 days early means consumption is 1 day, not 5.
- For a **Feeding Buffer**, the protected object is the merge point with the critical chain, not project finish — same math, different anchor. The merge milestone stays fixed; the buffer absorbs feeder-chain expansion.

Dividing by the **baseline buffer size — the insurance premium agreed when the commitment was made** — keeps the Y-axis linear and comparable across the project's life: 1 day of forecast lateness always costs the same percentage.

## Zones and decision rules

The chart is divided into green / yellow / red. The insight is that the threshold isn't absolute consumption but **consumption relative to progress** — 20% consumed at 50% progress is healthy; 60% consumed at 50% progress is a warning. Green = monitor; yellow = investigate and prepare recovery actions; red = intervene now to protect the committed date. The transcript doesn't fix exact boundary formulas (implementations vary); the common practice is sloped boundary lines in (X, Y) space — e.g. yellow above `Y = X`, red above `Y = X + k` — which you'll need to parameterise per your risk appetite.

## Implementation shape

Four independent functions per buffer, re-run on every status change: chain horizon (CPSL), certainty frontier (PPF), forecast finish → buffer consumption, and plotting the fever chart. 
Store the point history so the chart shows trajectory and velocity of buffer burn, not just today's position.
The *direction* of movement across zones is what drives the operational decision.

Because both axes are forecast-based, the chart is only as honest as your remaining-duration estimates. The frontier is objective (done/not done), but the horizon and lateness depend on updated task forecasts. We need disiplined updates on "remaining task durations" on in-progress tasks.

- **X-axis (Progress = PPF ÷ CPSL):** forecast-based, because the *journey* is what changes as you learn.
- **Y-axis (Consumption = forecast lateness ÷ baseline buffer):** the numerator is forecast-based, but the denominator is fixed, because the *commitment and its insurance* don't change with execution — only a formal re-baselining (a new agreement with the stakeholders) resets the buffer size.

Two practical consequences for the Fever chart:

1. **Consumption can exceed 100%.** If forecast lateness is bigger than the baseline buffer, you're forecasting a breach of the committed date. Don't clamp it — plot it above 100% (deep red); that's exactly the signal that demands escalation rather than mere intervention.
2. **Consumption can be negative** (chain forecast to finish ahead of its scheduled finish). Floor the display at 0%. Showing them has value (visible slack you could exploit, e.g. by resurfacing an early-finish opportunity to downstream resources). Flooring at 0 keeps the chart focused on risk.

So the stored inputs per buffer are: 
- baseline buffer size (fixed at commitment, when we toggle the project from planning to execution phase)
- The protected date (End date of the buffer)
- per status update the forecast finish of the terminal protected task