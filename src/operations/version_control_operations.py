"""Versioned project folders: an opt-in git repo behind a project file,
giving autosave/undo/redo/checkpoints (see docs/user-guide.md's
"Versioned Project Folders" section for the user-facing explanation).

Deliberately opt-in, never global: a plain File > Open/Save project is
untouched by any of this. A directory only becomes a versioned workspace
via new_versioned_project() below, and is only ever recognised as one
again later by the presence of its own marker file
(WORKSPACE_MARKER_FILENAME) in the exact directory a file was opened
from - never by walking upward looking for a `.git`, which could
otherwise mistake a file saved inside some unrelated git repo (including
this app's own source checkout) for a versioned workspace.
"""

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox

from src.utils import git_helper

WORKSPACE_MARKER_FILENAME = '.our-planner-workspace.json'
TRACKED_FILE_NAME = 'project.json'
DEFAULT_AUTOSAVE_BRANCH = 'autosave'
DEFAULT_MAIN_BRANCH = 'main'
MARKER_SCHEMA_VERSION = 1


@dataclass
class VersionControlState:
    """Set on controller.version_control while the open project is a
    versioned workspace; None otherwise - every autosave/undo/checkpoint
    flow checks this first and no-ops when it's None, which is what keeps
    the feature fully inert for ordinary projects."""

    workspace_dir: Path
    tracked_file: str
    autosave_branch: str = DEFAULT_AUTOSAVE_BRANCH
    main_branch: str = DEFAULT_MAIN_BRANCH

    @property
    def tracked_path(self) -> Path:
        return self.workspace_dir / self.tracked_file


class VersionControlOperations:
    def __init__(self, controller, model):
        self.controller = controller
        self.model = model

    # ------------------------------------------------------------ detection

    def detect_workspace(self, file_path):
        """Sets controller.version_control from file_path's own directory
        marker, if any - called after every load/new/save-as in
        file_operations.py so versioning re-activates on reopening a
        workspace's tracked file later, and deactivates the moment the
        user moves to a plain file or a different project."""
        self.controller.version_control = None
        if not file_path:
            return
        workspace_dir = Path(file_path).parent
        marker_path = workspace_dir / WORKSPACE_MARKER_FILENAME
        try:
            manifest = json.loads(marker_path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            return
        tracked_files = manifest.get('tracked_files') or []
        if os.path.basename(file_path) not in tracked_files:
            return
        self.controller.version_control = VersionControlState(
            workspace_dir=workspace_dir,
            tracked_file=os.path.basename(file_path),
            autosave_branch=manifest.get('autosave_branch', DEFAULT_AUTOSAVE_BRANCH),
            main_branch=manifest.get('main_branch', DEFAULT_MAIN_BRANCH),
        )

    # ------------------------------------------------------------ UI flow

    def new_versioned_project(self):
        """File -> New Versioned Project...: creates a fresh directory
        backed by a real git repo, with autosave/undo/redo/checkpoints
        available - see this module's docstring. Refuses to adopt a
        non-empty directory, so this can never turn an existing folder
        (a document library, another git repo, ...) into a workspace by
        surprise."""
        if not git_helper.is_git_available():
            messagebox.showerror(
                'Git Not Found',
                'Versioned projects need git installed and on PATH. '
                'Install git and try again.',
            )
            return

        directory = filedialog.askdirectory(
            title='Choose an empty folder for the new versioned project',
            mustexist=True,
        )
        if not directory:
            return
        workspace_dir = Path(directory)

        if any(workspace_dir.iterdir()):
            messagebox.showerror(
                'Folder Not Empty',
                f'{workspace_dir} is not empty. Choose an empty folder so a '
                'versioned project never adopts files it did not create.',
            )
            return

        if not git_helper.is_git_configured(workspace_dir):
            messagebox.showerror(
                'Git Not Configured',
                'Git is installed but has no user.name/user.email '
                'configured, so commits would fail. Run:\n\n'
                '  git config --global user.name "Your Name"\n'
                '  git config --global user.email "you@example.com"\n\n'
                'then try again.',
            )
            return

        self.model.reset()
        for resource in list(self.model.resources[1:]):
            self.model.remove_resource(resource['id'])

        tracked_path = workspace_dir / TRACKED_FILE_NAME
        marker_path = workspace_dir / WORKSPACE_MARKER_FILENAME
        try:
            git_helper.init_repo(workspace_dir)
            self.model.save_to_file(str(tracked_path))
            marker_path.write_text(
                json.dumps(
                    {
                        'schema_version': MARKER_SCHEMA_VERSION,
                        'created': datetime.now().isoformat(timespec='seconds'),
                        'tracked_files': [TRACKED_FILE_NAME],
                        'autosave_branch': DEFAULT_AUTOSAVE_BRANCH,
                        'main_branch': DEFAULT_MAIN_BRANCH,
                    },
                    indent=2,
                ),
                encoding='utf-8',
            )
            git_helper.add(
                workspace_dir, [TRACKED_FILE_NAME, WORKSPACE_MARKER_FILENAME]
            )
            git_helper.commit(workspace_dir, 'Initial commit')
            git_helper.create_branch(workspace_dir, DEFAULT_AUTOSAVE_BRANCH)
            git_helper.checkout(workspace_dir, DEFAULT_AUTOSAVE_BRANCH)
        except git_helper.GitError as e:
            messagebox.showerror(
                'Git Error', f'Could not create the versioned project: {e}'
            )
            return

        self.detect_workspace(str(tracked_path))
        self.controller.update_window_title(str(tracked_path))
        self.controller.update_view()
        messagebox.showinfo(
            'Versioned Project Created',
            f'Created a versioned project in {workspace_dir}.\n\n'
            'Every edit is autosaved to a local "autosave" branch; use '
            'File > Save Version... to checkpoint onto "main".',
        )
