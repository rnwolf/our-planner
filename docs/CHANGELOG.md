
    ## [0.1.27] - 2026-08-21
    ### Added
    - Versioned Project Folders: File > New Versioned Project... creates a git-backed workspace
      with automatic autosave on every meaningful edit (including on app close), Edit >
      Undo/Redo (Ctrl+Z/Ctrl+Y) stepping one autosave commit at a time, Edit > Jump to
      Version... to return straight to any earlier autosave point, and File > Save Version...
      to checkpoint the current state as a single named commit on main. Ordinary (non-workspace)
      projects are entirely unaffected. Documented in the user guide's new "Versioned Project
      Folders" section and in-app Help > Documentation.
    - Reports > Resource Over-Allocation...: a By Resource / By Tag view of every overloaded
      resource or role across all projects plus backlog work, with worst-first sorting and
      drill-down into each contributing task (flagged Critical/Non-Critical/Unscheduled). Edit
      Task Resources also gained an inline tag filter alongside the existing name search.
    - "Schedule with CCPM..." gained an "Account for capacity already committed to other
      projects" option (checked by default), so scheduling no longer plans against a shared
      resource's full raw capacity when it's already committed elsewhere.
    - Home/Page Up/Page Down keyboard navigation on the task grid (re-center on today / scroll
      half a viewport vertically).
    - View > Show Task Names toggle: show just the task id instead of the full description when
      it doesn't fit its box, on-screen and in PDF/PNG export.
    - A realistic large sample portfolio (`sample-app-file/realistic-portfolio.json`, 19
      projects/218 tasks/30 resources) and its generator, exercising CCPM scheduling, buffer
      consumption, resource contention, and full-kit readiness with genuine (not hand-faked)
      outcomes - documented in a new Sample Portfolio Walkthrough doc page.
    ### Fixed
    - "Schedule with CCPM..."'s result/error dialog is now a resizable, scrollable window
      instead of an auto-sizing messagebox, and validation issues reference tasks/resources by
      name instead of raw internal ids.
    - Fever chart date labels are now drawn in chronological order with collision avoidance
      (previously could zig-zag and overlap), on-screen points are clickable to show the
      recorded reason/note, and each chart now also shows its project name.
    - A near-zero-duration (fully consumed) buffer's hit zone and stacking order no longer lose
      out to an overlapping successor task on hover/click/right-click.
    - A URL task's plain click no longer also opens the link in a browser tab (moved to
      double-click); resource tag editing moved into a proper Tags tab in Edit Resources instead
      of an unreachable right-click-on-empty-tags path.
    - A real drag-to-create bug: dragging out a brand-new task right after creating another one
      could silently move the previous task instead of sizing the new one.
    - The File menu's Save and Schedule with CCPM... mnemonics no longer collide.
    - Generated/imported CCPM schedules no longer force a 'ccpm' tag onto every task.
    - `docs/CHANGELOG.md` (not the repo-root copy) is now the single source of truth, fixing
      drift between the two.
    - CI's "Publish to PyPI" workflow now runs the test suite under Xvfb, pinned to a 24-bit
      screen depth - the Jump to Version... dialog's two real-Tk tests had never actually been
      able to pass on GitHub Actions' headless runner (no display, then Xvfb's default 8-bit
      depth aborting Tcl/Tk on the first widget creation), silently blocking every release
      since they were added (v0.1.25 and v0.1.26 were never published because of this).
    ### Removed
    - The legacy Network menu and its classic critical-path analysis - superseded by CCPM
      scheduling and unrelated to CCPM's own critical chain logic.

    ## [0.1.24] - 2026-08-18
    ### Added
    - Keyboard-only accessibility across the whole app: Alt-mnemonics and Ctrl accelerators on
      every menu, Enter now activates a focused button in every dialog (Tk doesn't bind this by
      default), fixed tab order and invisible-scrollbar Tab stops in Edit Resources and related
      dialogs, keyboard shortcuts throughout Manage Projects, Manage Chains, and Project
      Settings, Edit Task Resources redesigned as search-and-add, and Set Current Date made
      fully keyboard-operable (tkcalendar has no keyboard support of its own).
    - A persisted Base Font Size setting (Project Settings) and a persisted zoom level, both
      stored in a new `~/.our-planner/settings.json` alongside the app rather than in project
      files - viewing preferences, not plan data.
    - Reason codes for status updates: Record Remaining Duration... now captures a primary
      reason (a fixed vocabulary - On Time, Task Variability, Waiting for Full Kit, Waiting for
      Resource, No Early Start, Parkinson's Law, Multitasking, Waiting in Backlog, Unplanned
      Events, Other / Unexplained) and an optional multi-line note alongside the remaining-
      duration number. Surfaced in View Duration History..., a new "Show Status Update
      Reasons/Notes" toggle on Fever Charts, and a new Reports > Status Update Log... report -
      every recorded update for a project, with a Task URL column linking back to each task's
      own page, an "only annotated" filter, and CSV export - intended for periodic team review
      of root-cause patterns to improve delivery performance, not just a per-task log.
    - File > Recent: the 5 most recently opened/saved files, numbered 1-5 (most recent first)
      so the whole flow is reachable by keyboard - open the submenu and press the digit.
    - A new UI scenario testing framework (`scripts/ui_scenarios`): a fast in-process
      `ScenarioDriver` for driving the real app in tests, and a paced `VisualDriver` for
      narrated walkthroughs - documented in the README.
    ### Fixed
    - Base Font Size wasn't affecting the timeline row height or the "Current Date" label's
      font.
    - A silent drag-create failure immediately after creating another task.
    - File > New wasn't clearing resources or tags, and reseeded all 10 sample resources
      instead of trimming down to just the first one.
    ### Changed
    - The user guide and in-app Help > Documentation now cover all of the above.

    ## [0.1.23] - 2026-08-11
    ### Added
    - Resources gained an optional `emails` field (one or more addresses, comma/semicolon-
      separated) alongside the existing `url` - both are now editable in the Manage
      Resources dialog and carried through every resources.csv this app reads or writes,
      not just the fields the CSV importer recognized before. The ccpm-scheduler round
      trip's resources.csv also gains the same two columns; scheduling itself ignores
      them.
    - Resources with a `url` now show their name in blue in the resource grid and open it
      in the browser on click, matching the existing task name behavior.
    - Astral `ty` for static type checking, with a pre-commit hook and a Stop hook that
      runs it after every turn.
    ### Fixed
    - resources.csv import now rejects a row with more columns than the header instead of
      silently misaligning data - the failure mode an unquoted comma inside a cell (e.g.
      multiple `emails` addresses) produces.
    - `url` was importable but never appeared in either resources.csv export, and had no
      editor in the Manage Resources dialog - both gaps are closed.
    - A dead duplicate `add_resource()` call in the Manage Resources dialog's "Add
      Resource" handler.
    - Four real bugs `ty` caught while getting the codebase to a clean check: a dead/
      broken duplicate method referencing a nonexistent model attribute, a dead `import
      toml` block, a deprecated tkinter `trace()` call, and a fragile cross-block
      variable reference.
    - Dropped the docs.yml release trigger, which always failed harmlessly (a
      release-triggered run checks out the tag rather than main, which the
      github-pages environment's protection rules reject) - the preceding push-to-main
      run already deploys the correct content.
    ### Changed
    - Introduced TypedDicts (`src/model/entities.py`) for the core Task/Project/
      Resource/Chain shapes, replacing loosely-typed dicts throughout the model.
    - `load_from_file`'s backward-compat backfill logic split into named helper
      methods; a duplicated dialog resize-handle snippet extracted into a shared
      helper. Pure refactors, no behavior changes.

    ## [0.1.22] - 2026-07-28
    ### Fixed
    - A long-duration task's centered name label on the task box can scroll off-screen,
      leaving no way to read it. The task tooltip now shows the task name as its first
      line(s) - wrapped to at most two lines and truncated with an ellipsis if still too
      long - above the existing state/type/project/chain/etc. fields.
    ### Changed
    - Documentation site rebuilt with zensical (replacing mkdocs) and now deploys
      automatically to GitHub Pages via a new workflow on every push to main, instead of
      the previous manual, long-stale gh-pages branch deploy.
    - Adopted ruff for linting/formatting and pre-commit (with prek also supported) to
      run it automatically before each commit.

    ## [0.1.21] - 2026-07-27
    ### Fixed
    - Project Settings no longer corrupts resource capacity arrays when changing the
      number of days - this was causing an IndexError the next time resource loading
      redrew (e.g. closing the Edit Resources dialog).
    - Edit Resources dialog was slow to open (multiple seconds, worse the more days in
      the project): its Capacity tab built one row of widgets per project day and
      eagerly constructed two tkcalendar.DateEntry pickers regardless of which tab was
      visible. The tab now builds lazily (only when selected) and collapses consecutive
      equal-capacity days into a single row; the date pickers are now plain fields with
      a "Pick..." button that only builds the calendar popup if clicked. Also fixed the
      Capacity tab's resource dropdown silently desyncing from the Resources tab's
      listbox, and a capacity-update success popup that could render behind the modal
      dialog.
    - CSV export's "Choose Directory" picker could render behind the modal Export
      dialog, and - with no default folder - could silently write next to our-planner's
      own install location instead of the folder you actually chose.
    - A month-end-flaky date assertion in the delete-history tests (broke whenever the
      suite ran within 5 days of month-end).
    ### Added
    - "Edit Task Duration..." on the task right-click menu (single task or every
      selected task at once) - type an exact number of days instead of dragging a
      task's edge, and a new Edit > Task keyboard menu mirroring the same "Edit Task
      ..." commands for editing without a mouse.
    - File > Import Network: three sequential actions - Import Resources..., Import
      Resource Calendars..., Import Tasks... - for bringing in a plain, unscheduled
      reference network (tasks/resources matched by id), as the counterpart to
      Export CCPM Network.... New tasks get an automatic ASAP placement computed from
      predecessor links (FS/SS/FF/SF); an id that already exists only has its
      description/duration/resources/predecessors updated in place - state, notes,
      actual dates, and history are never touched. Every action validates up front and
      makes no changes at all if anything doesn't resolve. See Help > Documentation for
      the full column reference and the resource_ids id:allocation notation.
    ### Changed
    - Chain colors (critical + feeding chains) now use a validated, mutually
      distinguishable 8-hue palette - the previous feeding-chain colors sat too close in
      hue to the critical chain's red.
    - "Manage Chains..." moved from its own top-level Chains menu into a button on the
      Project Settings dialog.
    - "Set Task Color" renamed to "Edit Task Color" for consistency with the rest of
      that menu's "Edit Task ..." commands.

    ## [0.1.20] - 2026-07-19
    ### Changed
    - **Licence changed from GPL-3.0-or-later to MIT** (sole-author relicense) so the code
      can be used more freely by others. Note: the bundled date-picker dependency tkcalendar
      remains GPLv3-licensed; our-planner's own code is MIT.
    - Publishing to PyPI now happens only when a GitHub release is published (the old
      release.py script and the publish-on-every-push trigger are gone); the release steps
      are documented in the README and the Contributing page.
    ### Added
    - Keyboard-only status-update workflow: Alt+key mnemonics for every menu (View, Date,
      Projects, Reports, Chains, Network, Help - joining the existing File/Edit/Tasks/Filter);
      new Tasks-menu commands "Select Task by ID..." (scrolls to and selects the task,
      keyboard-first dialog), "Record Remaining Duration..." and "Add Note..." (routes to the
      Add Note to Multiple Tasks dialog when several tasks are selected); Alt+S / Alt+C save
      and cancel in both note dialogs, working while typing in the note text area.
    - The notes panel now follows the current selection: notes for the selected task(s) when
      there is a selection, every note when nothing is selected - so all / one / several
      lookups come from the same panel.
    ### Fixed
    - Right-click context menus near the bottom of the screen no longer run off-screen:
      menus are clamped to the physical monitor under the cursor (multi-monitor aware via
      xrandr on X11), not just the virtual screen.

    

    ## [0.1.19] - 2026-07-18
    ### Added
    - Resource grid at scale (Stage 21): resource IDs shown in the row labels; sort resources
      by ID, name, or whole-horizon load (utilization % shown in the label when load-sorted,
      most-loaded-first by default - the CCPM drum floats to the top); filter resources by
      project (a resource matches if assigned to a task of that project); load scope toggle
      to compute the loading numbers over all tasks or only the currently filtered ones, for
      multi-project alignment work; all driven from a new control bar under the resource grid
      (equivalent entries also in the Filter menu).
    - CCPM Method per project (Stage 20): selectable buffer sizing - cap (Cut & Paste,
      the default), hchain (50% of chain), rsem (root-squared error) - persisted per project,
      passed through both CCPM scheduling flows, inherited by the imported schedule copy.
      Requires ccpm-scheduler >= 0.9.0 (now >= 0.10.0).
    - Network Graph report (Stage 18): dependency network diagram for any set of tasks.
    - Import/export consistency pass (Stage 19), and imports now carry realistic_duration
      from CCPM schedules (engine >= 0.7.0).
    - Warn when an imported CCPM schedule reaches past the planning grid instead of drawing
      tasks off the edge.
    ### Fixed
    - Permanent grey dead band between the resource panel and the horizontal scrollbar:
      pane overhead is now measured from live geometry on every resize instead of a one-shot
      startup measurement that baked in ~40px of phantom overhead.
    - Shrinking the window no longer compresses the status bar to nothing (it now keeps its
      height and the grids give up the space instead); added a resize grip in the status
      bar's bottom-right corner and a sensible minimum window size (800x500).
    - At-capacity resource cells are no longer colored as overloaded.
    - Manage dialogs size themselves to their content so buttons can't be clipped, and keep
      the listbox selection while editing fields.

    

    ## [0.1.18] - 2026-07-13
    ### Fixed
    - Merge-task cascade bug: Stage 6's bidirectional pull now takes the max across ALL of a
      successor's predecessor links instead of whichever single link cascaded last - a routine
      status update on one branch can no longer drag a merge task in front of the other branch's
      unfinished work, and never corrupts the feeding buffer silently.
    ### Changed
    - Feeding buffers now behave as two-sided shock absorbers during execution: the buffer
      compresses (logged, reason "merge_pulled_earlier") when the relay-runner cascade pulls its
      merge point earlier, and regrows toward its baseline (logged, "merge_moved_later") when the
      merge point moves later. The fever chart's feeding-buffer consumption reflects both shock
      directions: effective lateness = baseline size - live size + overflow past the merge
      baseline, divided by the baseline size as before (push-only numbers are unchanged; >100%
      still means forecast breach).
    ### Added
    - Regression tests for the merge scenario (tests/test_fever_chart_merge_signal.py):
      pull-side alarm at 60%, idempotent status updates, pull never jumps unfinished feeding
      work, push-side signal unchanged.

    

    ## [0.1.17] - 2025-04-08
    ### Added
    - New Feature: Added MKDoc and documentation to publish to gh-pages.

    

    ## [0.1.16] - 2025-04-08
    ### Added
    - New Feature: Update the date for the task grid with optional ability to shift tasks based on the new start date.

    

    ## [0.1.15] - 2025-04-04
    ### Added
    - New Feature: Added State to tasks.
        - Gray text background for "buffered" state tasks
        - Green text background for "done" state tasks
        - No background for "planning" state tasks

    - New Feature: Add new task properties:
        - state
        - safe_duration
        - agressive_duration
        - actual_start_date
        - actual_end_date
        - fullkit_date
        - remaining_duration_history

    - New Feature: Add methods to handle these properties, such as recording remaining duration and retrieving that remaining estimates history

    - Improvements: Redraw of single and multiple tasks with state visulisation and floating tooltip.

    

    ## [0.1.14] - 2025-04-03
    ### Added
    - New Feature: Add or delete timestamped notes to a task with notes displaed on panel on the right.

    

    ## [0.1.13] - 2025-04-03
    ### Added
    - Fix: Increase Y size of tag filter dialogs so that buttons are not cut off.

    

    ## [0.1.12] - 2025-04-03
    ### Added
    - Fix: Fix the pakages in pyproject.toml so that we now get all the sub packages being included.
    - Fix: Updated GHA workflow with condition check to run only on changes to main branch

    

    ## [0.1.11] - 2025-04-02
    ### Added
    - Fix: added packages=[src] to pyproject.toml to fix issue with pipx install.

    

    ## [0.1.11] - 2025-04-02
    ### Added
    - Fix: added packages=[src] to pyproject.toml to fix issue with pipx install.

    

    ## [0.1.11] - 2025-04-02
    ### Added
    - Fix: added packages=[src] to pyproject.toml to fix issue with pipx install.

    

    ## [0.1.10] - 2025-04-02
    ### Added
    - Fix: Removed manual publish from GHA for release.

    

    ## [0.1.9] - 2025-04-02
    ### Added
    - Fix: Bump version to force build and release.

    

    ## [0.1.8] - 2025-04-02
    ### Added
    - Fix: Bump version to force build and release

    

    ## [0.1.7] - 2025-04-02
    ### Added
    - Enhance: build.py deal with duplicate release tags.

    

    ## [0.1.6] - 2025-04-02
    ### Added
    - Enhance: build.py update to deal with merg to main conflicts.

    

    ## [0.1.6] - 2025-04-02
    ### Added
    - Enhance: Hithub action not in correct folder. Now in workflow folder named main.yml

    

    ## [0.1.5] - 2025-04-02
    ### Added
    - Enhance: The application executuion name incorrect. is now our-planner.
    - Enhance: The application will now return release version number when using -v or --version as arguments.

    

    ## [0.1.4] - 2025-04-01
    ### Added
    - Enhance: Github action to build and release the package to PyPI and GitHub.



    ## [0.1.3] - 2025-04-01
    ### Added
    - New feature: Add a Github action to automatically release the package to PyPI and GitHub.

    ## [0.1.2] - 2025-04-01
    ### Added
    - Bug fix: Fix the build.py file to update develop branch and main branch correctly.

    ## [0.1.1] - 2025-04-01
    ### Added
    - New feature: Added uv.lock to version control.
    - New feature: Prepare for release process.

    ## [0.1.0] - 2025-03-31
    ### Added
    - New feature: Build script to help with release process.
    - New feature: Updated pyproject.toml development dependencies for use with UV.
