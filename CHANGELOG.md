
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
