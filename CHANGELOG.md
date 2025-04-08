
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
