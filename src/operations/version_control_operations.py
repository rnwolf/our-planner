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
from tkinter import filedialog, messagebox, simpledialog
from typing import Optional

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
    # Set once a git failure happens mid-session, so a broken autosave
    # doesn't pop a fresh warning on every subsequent edit.
    autosave_disabled: bool = False
    # The autosave-branch commit the in-memory model currently reflects -
    # NOT necessarily the branch tip, since undo/redo load older commits
    # without moving the branch itself. maybe_autosave_checkpoint() diffs
    # against THIS, not HEAD, so browsing history (no real edit) never
    # looks like a change worth committing - only content that genuinely
    # differs from what's currently loaded does. Kept in sync: set to the
    # tip on workspace creation/detection, to a new commit's sha after
    # each autosave, and to the target commit's sha by undo/redo/jump.
    history_cursor_sha: Optional[str] = None

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
        autosave_branch = manifest.get('autosave_branch', DEFAULT_AUTOSAVE_BRANCH)
        try:
            cursor = git_helper.log(workspace_dir, autosave_branch)[0].sha
        except (git_helper.GitError, IndexError):
            cursor = None
        self.controller.version_control = VersionControlState(
            workspace_dir=workspace_dir,
            tracked_file=os.path.basename(file_path),
            autosave_branch=autosave_branch,
            main_branch=manifest.get('main_branch', DEFAULT_MAIN_BRANCH),
            history_cursor_sha=cursor,
        )

    # ------------------------------------------------------------ autosave

    def _serialize_model(self, vc: VersionControlState) -> bytes:
        """The model's current state, serialized exactly as save_to_file
        would write it, without touching the real tracked file - used to
        test for a real change before committing to disk/git at all (see
        maybe_autosave_checkpoint). save_to_file's own side effect of
        setting model.current_file_path is undone immediately after, so a
        pure "is there anything to commit" check can never redirect where
        a later File > Save would write to."""
        original_path = self.model.current_file_path
        scratch = vc.workspace_dir / f'.{vc.tracked_file}.autosave-scratch'
        try:
            self.model.save_to_file(str(scratch))
            return scratch.read_bytes()
        finally:
            scratch.unlink(missing_ok=True)
            self.model.current_file_path = original_path

    def maybe_autosave_checkpoint(self):
        """Commits the current model state to the autosave branch if it's
        actually different from history_cursor_sha - the commit the model
        is currently understood to reflect, NOT necessarily the branch
        tip (see VersionControlState.history_cursor_sha). A no-op when the
        open project isn't a versioned workspace.

        Called from every point an edit might just have happened
        (controller.update_view, on_task_release's drag/resize tail) plus
        every session-ending action (save_file, undo/redo, save_version)
        as a safety net for any edit path that reaches neither of those
        two. Safe to call redundantly from all of them: comparing the
        model's serialization against the cursor's own committed content
        (never touching the real tracked file or git's index until a real
        difference is confirmed - see _serialize_model) means a no-op call
        (a pure view toggle, a click with no drag, or simply browsing
        history via undo/redo with no new edit yet) never leaves the
        tracked file staged-but-uncommitted relative to autosave's actual
        tip. Confirmed live that mattered: an earlier version wrote the
        model to the tracked file unconditionally before checking for a
        diff, which - since update_view() re-triggers this after every
        undo/redo step - left the working tree dirty relative to HEAD
        after browsing alone, breaking save_version()'s own `git checkout
        main` (git refuses to switch branches over conflicting
        uncommitted changes). This is also what makes several overlapping
        call sites safe instead of noisy, rather than needing to classify
        every model-mutating call site by hand (see this feature's design
        plan for why that classification approach was rejected).

        If the cursor is behind the branch tip (the user undid, then made
        a genuine new edit), the tip's now-abandoned commits are discarded
        via reset_hard before committing - a conventional linear undo/redo
        where editing after undo discards the redo-able future. reset_hard,
        not reset_branch (`branch -f`), because autosave is always the
        currently checked-out branch at this point, and git refuses to
        force-move that (see git_helper.reset_branch's own docstring)."""
        vc = self.controller.version_control
        if vc is None or vc.autosave_disabled:
            return
        try:
            current_bytes = self._serialize_model(vc)
            if vc.history_cursor_sha is not None:
                baseline = git_helper.checkout_file_content(
                    vc.workspace_dir, vc.history_cursor_sha, vc.tracked_file
                )
            else:
                baseline = None
            if current_bytes == baseline:
                return

            vc.tracked_path.write_bytes(current_bytes)
            git_helper.add(vc.workspace_dir, [vc.tracked_file])
            tip = git_helper.log(vc.workspace_dir, vc.autosave_branch)[0].sha
            if vc.history_cursor_sha is not None and vc.history_cursor_sha != tip:
                # reset_hard overwrites the working tree with the cursor's
                # own content, wiping out the write just above - it has to
                # be written again on top before staging+committing.
                git_helper.reset_hard(vc.workspace_dir, vc.history_cursor_sha)
                vc.tracked_path.write_bytes(current_bytes)
                git_helper.add(vc.workspace_dir, [vc.tracked_file])
            message = f'Autosave {datetime.now().isoformat(timespec="seconds")}'
            git_helper.commit(vc.workspace_dir, message)
            vc.history_cursor_sha = git_helper.log(
                vc.workspace_dir, vc.autosave_branch
            )[0].sha
        except git_helper.GitError as e:
            vc.autosave_disabled = True
            messagebox.showwarning(
                'Autosave Disabled',
                f'Autosave stopped working for this session and has been '
                f'disabled: {e}\n\nYour edits are still in the app - use '
                'File > Save to write them to disk, but they will not be '
                'versioned until you reopen this project.',
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
            # Normalize once: load_from_file's schema-migration backfill
            # (e.g. a resource's missing works_weekends default) can add
            # fields on first load that a freshly-reset model's own
            # serialization doesn't have yet - confirmed live this is
            # idempotent after one round trip. Doing it now, before the
            # very first commit, means every LATER load+resave (undo/
            # redo, reopening this file) is stable, so the autosave
            # diff-gate never mistakes backfill noise for a real edit.
            self.model.load_from_file(str(tracked_path))
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

    def save_version(self):
        """File -> Save Version...: squashes every commit on the autosave
        branch since the last checkpoint into ONE commit on main, then
        resets autosave back to main's new tip - see this module's
        docstring for the two-tier branch design. A no-op (with a message)
        if there's nothing new to checkpoint. Disabled/no-op when the
        project isn't a versioned workspace."""
        vc = self.controller.version_control
        if vc is None:
            return

        # Captures any edit not yet committed, so it's included in this
        # checkpoint rather than left stranded on autosave past a reset.
        self.maybe_autosave_checkpoint()

        autosave_tip = git_helper.log(vc.workspace_dir, vc.autosave_branch)[0].sha
        main_tip = git_helper.log(vc.workspace_dir, vc.main_branch)[0].sha
        if autosave_tip == main_tip:
            messagebox.showinfo(
                'Nothing to Save', 'No changes since the last saved version.'
            )
            return

        message = simpledialog.askstring(
            'Save Version',
            'Optional message for this version (leave blank for a default):',
            parent=self.controller.root,
        )
        if message is None:  # Cancel
            return
        if not message.strip():
            message = f'Checkpoint {datetime.now().isoformat(timespec="seconds")}'

        try:
            git_helper.checkout(vc.workspace_dir, vc.main_branch)
            git_helper.merge_squash(vc.workspace_dir, vc.autosave_branch)
            git_helper.commit(vc.workspace_dir, message)
        except git_helper.GitError as e:
            # merge_squash's own docstring: a failed --squash never writes
            # MERGE_HEAD, so `git reset --merge` (not `merge --abort`) is
            # what actually unwinds it - confirmed live building git_helper.
            git_helper.merge_abort(vc.workspace_dir)
            git_helper.checkout(vc.workspace_dir, vc.autosave_branch)
            messagebox.showerror(
                'Save Version Failed', f'Could not save this version: {e}'
            )
            return

        git_helper.reset_branch(vc.workspace_dir, vc.autosave_branch, vc.main_branch)
        git_helper.checkout(vc.workspace_dir, vc.autosave_branch)
        # The model's content didn't change (the squash only rewrote
        # history), but the commit it corresponds to did.
        vc.history_cursor_sha = git_helper.log(vc.workspace_dir, vc.main_branch)[0].sha
        messagebox.showinfo('Version Saved', f'Saved version: {message}')

    # ------------------------------------------------------------ undo/redo

    def undo(self):
        """Edit -> Undo (Ctrl+Z): steps one commit backward on autosave,
        reloading the model from that commit's content. A no-op (not an
        error) at the oldest commit, or when the project isn't versioned."""
        self._step_history(-1)

    def redo(self):
        """Edit -> Redo (Ctrl+Y): steps one commit forward, back toward
        autosave's tip. A no-op past the tip."""
        self._step_history(1)

    def can_undo(self) -> bool:
        """Whether Undo has anywhere to go - used by the Edit menu's
        postcommand to disable the item rather than leave it silently
        inert at the oldest commit."""
        vc = self.controller.version_control
        if vc is None:
            return False
        try:
            shas = self._autosave_shas(vc)
        except git_helper.GitError:
            return False
        return self._history_position(vc, shas) > 0

    def can_redo(self) -> bool:
        """Whether Redo has anywhere to go - past the autosave tip."""
        vc = self.controller.version_control
        if vc is None:
            return False
        try:
            shas = self._autosave_shas(vc)
        except git_helper.GitError:
            return False
        return self._history_position(vc, shas) < len(shas) - 1

    def _autosave_shas(self, vc: VersionControlState) -> list[str]:
        """autosave's own commit shas, oldest first - oldest-first makes
        "index + 1 = one step toward the tip" match undo/redo's own
        direction sign (+1 for redo, -1 for undo) with no extra negation."""
        return [
            c.sha
            for c in reversed(git_helper.log(vc.workspace_dir, vc.autosave_branch))
        ]

    def _history_position(self, vc: VersionControlState, shas: list[str]) -> int:
        """Index of the cursor within `shas` - falls back to "at the tip"
        if the cursor is unknown (e.g. a fresh detect_workspace that hit a
        git error), matching maybe_autosave_checkpoint's own fallback."""
        if vc.history_cursor_sha in shas:
            return shas.index(vc.history_cursor_sha)
        return len(shas) - 1

    def _step_history(self, direction: int):
        vc = self.controller.version_control
        if vc is None:
            return
        # Captures any in-flight edit BEFORE moving away from it, so
        # Undo's first press always steps away from what's actually on
        # screen, not from some earlier, already-superseded autosave.
        self.maybe_autosave_checkpoint()
        try:
            shas = self._autosave_shas(vc)
            index = self._history_position(vc, shas)
            new_index = index + direction
            if not (0 <= new_index < len(shas)):
                return  # already at the oldest/newest - nothing to do
            self._load_commit(shas[new_index])
        except git_helper.GitError as e:
            messagebox.showerror('Undo/Redo Failed', f'Could not do that: {e}')

    def _load_commit(self, sha: str):
        vc = self.controller.version_control
        content = git_helper.checkout_file_content(
            vc.workspace_dir, sha, vc.tracked_file
        )
        # Loaded via a scratch path, NOT vc.tracked_path - pure browsing
        # must never touch the actual tracked file or git's index/working
        # tree. Confirmed live this matters: writing historical content
        # straight to the tracked file left it staged-but-uncommitted
        # relative to autosave's real tip, which made save_version()'s own
        # `git checkout main` fail outright (git refuses to switch
        # branches over conflicting uncommitted changes), and would have
        # shown stale "just previewing" content if the app closed before
        # a real edit or a redo resolved it. A genuine new edit still
        # writes vc.tracked_path directly, via maybe_autosave_checkpoint.
        preview_path = vc.workspace_dir / f'.{vc.tracked_file}.undo-preview'
        preview_path.write_bytes(content)
        try:
            self.model.load_from_file(str(preview_path))
        finally:
            preview_path.unlink(missing_ok=True)
        self.model.current_file_path = str(vc.tracked_path)
        vc.history_cursor_sha = sha
        if hasattr(self.controller.ui, 'update_notes_panel'):
            self.controller.ui.update_notes_panel()
        self.controller.update_view()
