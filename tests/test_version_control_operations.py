"""New Versioned Project... (File menu), the marker-based detection that
re-activates/deactivates versioning on later load/new/save-as, and the
autosave-to-autosave-branch hook - see version_control_operations.py's
own docstring for the design.
"""

import json
import tkinter as tk
from unittest.mock import MagicMock, patch

import pytest

from src.model.task_resource_model import TaskResourceModel
from src.operations.version_control_operations import (
    DEFAULT_AUTOSAVE_BRANCH,
    DEFAULT_MAIN_BRANCH,
    TRACKED_FILE_NAME,
    WORKSPACE_MARKER_FILENAME,
    VersionControlOperations,
    VersionControlState,
)
from src.utils import git_helper


def _ops():
    model = TaskResourceModel()
    controller = MagicMock()
    controller.model = model
    controller.version_control = None
    return VersionControlOperations(controller, model), controller, model


@pytest.fixture
def real_workspace(tmp_path, monkeypatch):
    """A real, initialized versioned workspace (repo + marker + initial
    commit on main + autosave branch checked out), the same shape
    new_versioned_project() produces - built directly via git_helper
    rather than through the full UI flow, so autosave tests can exercise
    maybe_autosave_checkpoint() in isolation.

    messagebox.showwarning is patched to a no-op by default (autouse via
    this fixture) - an unexpected GitError otherwise pops a REAL, blocking
    Tk dialog (confirmed live: a test hung indefinitely waiting for a
    mouse click nothing would ever provide), turning a real bug into a
    silent hang instead of a loud, fast test failure. A test that needs to
    assert on the exact call still can - `with patch(...)` inside a test
    body overrides this for the duration of that `with` block."""
    monkeypatch.setattr(
        'src.operations.version_control_operations.messagebox.showwarning',
        lambda *a, **k: None,
    )
    monkeypatch.setenv('HOME', str(tmp_path))
    import subprocess

    subprocess.run(['git', 'config', '--global', 'user.name', 'Test User'], check=True)
    subprocess.run(
        ['git', 'config', '--global', 'user.email', 'test@example.com'], check=True
    )

    workspace = tmp_path / 'workspace'
    workspace.mkdir()
    model = TaskResourceModel()
    controller = MagicMock()
    controller.model = model
    tracked_path = workspace / TRACKED_FILE_NAME

    git_helper.init_repo(workspace)
    model.save_to_file(str(tracked_path))
    # Normalize once, matching new_versioned_project()'s own fix - see
    # its comment: load_from_file's backfill isn't stable until one round
    # trip has happened, so every LATER load+resave in a test (mirroring
    # undo/redo) needs this same one-time normalization to be realistic.
    model.load_from_file(str(tracked_path))
    model.save_to_file(str(tracked_path))
    (workspace / WORKSPACE_MARKER_FILENAME).write_text(
        json.dumps(
            {
                'schema_version': 1,
                'tracked_files': [TRACKED_FILE_NAME],
                'autosave_branch': DEFAULT_AUTOSAVE_BRANCH,
                'main_branch': DEFAULT_MAIN_BRANCH,
            }
        )
    )
    git_helper.add(workspace, [TRACKED_FILE_NAME, WORKSPACE_MARKER_FILENAME])
    git_helper.commit(workspace, 'Initial commit')
    git_helper.create_branch(workspace, DEFAULT_AUTOSAVE_BRANCH)
    git_helper.checkout(workspace, DEFAULT_AUTOSAVE_BRANCH)

    initial_sha = git_helper.log(workspace, DEFAULT_AUTOSAVE_BRANCH)[0].sha
    controller.version_control = VersionControlState(
        workspace_dir=workspace,
        tracked_file=TRACKED_FILE_NAME,
        history_cursor_sha=initial_sha,
    )
    ops = VersionControlOperations(controller, model)
    return ops, controller, model, workspace


class TestNewVersionedProject:
    def test_creates_repo_marker_and_initial_commit(self, tmp_path, monkeypatch):
        ops, controller, model = _ops()
        # Point HOME at an empty temp dir with its own global git identity,
        # rather than relying on (or clobbering) the real developer's
        # ~/.gitconfig - subprocess.run inherits the patched env.
        monkeypatch.setenv('HOME', str(tmp_path))
        import subprocess

        subprocess.run(
            ['git', 'config', '--global', 'user.name', 'Test User'], check=True
        )
        subprocess.run(
            ['git', 'config', '--global', 'user.email', 'test@example.com'],
            check=True,
        )
        workspace = tmp_path / 'workspace'
        workspace.mkdir()

        with (
            patch(
                'src.operations.version_control_operations.filedialog.askdirectory',
                return_value=str(workspace),
            ),
            patch('src.operations.version_control_operations.messagebox.showinfo'),
            patch('src.operations.version_control_operations.messagebox.showerror'),
        ):
            ops.new_versioned_project()

        assert (workspace / '.git').is_dir()
        tracked_path = workspace / TRACKED_FILE_NAME
        assert tracked_path.exists()

        manifest = json.loads((workspace / WORKSPACE_MARKER_FILENAME).read_text())
        assert manifest['tracked_files'] == [TRACKED_FILE_NAME]
        assert manifest['autosave_branch'] == DEFAULT_AUTOSAVE_BRANCH
        assert manifest['main_branch'] == DEFAULT_MAIN_BRANCH

        main_commits = git_helper.log(workspace, DEFAULT_MAIN_BRANCH)
        assert [c.message for c in main_commits] == ['Initial commit']
        autosave_commits = git_helper.log(workspace, DEFAULT_AUTOSAVE_BRANCH)
        assert [c.message for c in autosave_commits] == ['Initial commit']

        assert git_helper.current_branch(workspace) == DEFAULT_AUTOSAVE_BRANCH
        assert git_helper.is_clean(workspace)

        assert controller.version_control == VersionControlState(
            workspace_dir=workspace,
            tracked_file=TRACKED_FILE_NAME,
            history_cursor_sha=autosave_commits[0].sha,
        )
        assert model.current_file_path == str(tracked_path)

    def test_refuses_a_nonempty_directory(self, tmp_path):
        ops, controller, _model = _ops()
        workspace = tmp_path / 'workspace'
        workspace.mkdir()
        (workspace / 'existing.txt').write_text('already here')

        with (
            patch(
                'src.operations.version_control_operations.filedialog.askdirectory',
                return_value=str(workspace),
            ),
            patch(
                'src.operations.version_control_operations.messagebox.showerror'
            ) as show_error,
        ):
            ops.new_versioned_project()

        show_error.assert_called_once()
        assert not (workspace / '.git').exists()
        assert controller.version_control is None

    def test_blocks_when_git_is_not_available(self, tmp_path):
        ops, controller, _model = _ops()

        with (
            patch('src.utils.git_helper.is_git_available', return_value=False),
            patch(
                'src.operations.version_control_operations.filedialog.askdirectory'
            ) as askdirectory,
            patch(
                'src.operations.version_control_operations.messagebox.showerror'
            ) as show_error,
        ):
            ops.new_versioned_project()

        askdirectory.assert_not_called()
        show_error.assert_called_once()
        assert controller.version_control is None

    def test_no_directory_chosen_is_a_noop(self, tmp_path):
        ops, controller, _model = _ops()

        with patch(
            'src.operations.version_control_operations.filedialog.askdirectory',
            return_value='',
        ):
            ops.new_versioned_project()

        assert controller.version_control is None


class TestDetectWorkspace:
    def _make_workspace(self, tmp_path, tracked_files=(TRACKED_FILE_NAME,)):
        workspace = tmp_path / 'workspace'
        workspace.mkdir()
        (workspace / WORKSPACE_MARKER_FILENAME).write_text(
            json.dumps(
                {
                    'schema_version': 1,
                    'tracked_files': list(tracked_files),
                    'autosave_branch': DEFAULT_AUTOSAVE_BRANCH,
                    'main_branch': DEFAULT_MAIN_BRANCH,
                }
            )
        )
        return workspace

    def test_recognizes_a_tracked_file_in_a_marked_directory(self, tmp_path):
        ops, controller, _model = _ops()
        workspace = self._make_workspace(tmp_path)
        tracked_path = workspace / TRACKED_FILE_NAME

        ops.detect_workspace(str(tracked_path))

        assert controller.version_control == VersionControlState(
            workspace_dir=workspace, tracked_file=TRACKED_FILE_NAME
        )

    def test_none_for_a_directory_without_a_marker(self, tmp_path):
        ops, controller, _model = _ops()
        plain_dir = tmp_path / 'plain'
        plain_dir.mkdir()

        ops.detect_workspace(str(plain_dir / 'project.json'))

        assert controller.version_control is None

    def test_none_when_file_is_not_in_tracked_files(self, tmp_path):
        ops, controller, _model = _ops()
        workspace = self._make_workspace(tmp_path, tracked_files=['other.json'])

        ops.detect_workspace(str(workspace / TRACKED_FILE_NAME))

        assert controller.version_control is None

    def test_none_for_a_falsy_path(self, tmp_path):
        ops, controller, _model = _ops()
        controller.version_control = VersionControlState(
            workspace_dir=tmp_path, tracked_file=TRACKED_FILE_NAME
        )

        ops.detect_workspace(None)

        assert controller.version_control is None

    def test_does_not_walk_up_past_the_files_own_directory(self, tmp_path):
        """A marker in a PARENT directory must not activate versioning for
        a file in a subdirectory - detection is deliberately non-recursive
        (see the module docstring's "never by walking upward" rule)."""
        ops, controller, _model = _ops()
        workspace = self._make_workspace(tmp_path, tracked_files=['sub/project.json'])
        sub = workspace / 'sub'
        sub.mkdir()

        ops.detect_workspace(str(sub / 'project.json'))

        assert controller.version_control is None


class TestMaybeAutosaveCheckpoint:
    def test_noop_when_project_is_not_versioned(self):
        ops, controller, _model = _ops()
        controller.version_control = None

        ops.maybe_autosave_checkpoint()  # must not raise - nothing to do

    def test_commits_a_real_edit_to_the_autosave_branch(self, real_workspace):
        ops, controller, model, workspace = real_workspace
        before = git_helper.log(workspace, DEFAULT_AUTOSAVE_BRANCH)

        model.add_task(row=1, col=0, duration=3, description='New Task')
        ops.maybe_autosave_checkpoint()

        after = git_helper.log(workspace, DEFAULT_AUTOSAVE_BRANCH)
        assert len(after) == len(before) + 1
        assert after[0].message.startswith('Autosave ')
        assert git_helper.is_clean(workspace)
        assert git_helper.current_branch(workspace) == DEFAULT_AUTOSAVE_BRANCH

    def test_noop_commit_when_nothing_actually_changed(self, real_workspace):
        """The diff-gate: calling this after a pure view toggle (no model
        change) must produce zero commits, not a spurious empty one - this
        is what makes calling it from many overlapping chokepoints safe."""
        ops, _controller, _model, workspace = real_workspace
        before = git_helper.log(workspace, DEFAULT_AUTOSAVE_BRANCH)

        ops.maybe_autosave_checkpoint()
        ops.maybe_autosave_checkpoint()

        after = git_helper.log(workspace, DEFAULT_AUTOSAVE_BRANCH)
        assert after == before

    def test_repeated_edits_produce_one_commit_each(self, real_workspace):
        ops, _controller, model, workspace = real_workspace

        model.add_task(row=1, col=0, duration=3, description='Task A')
        ops.maybe_autosave_checkpoint()
        model.add_task(row=2, col=0, duration=3, description='Task B')
        ops.maybe_autosave_checkpoint()

        commits = git_helper.log(workspace, DEFAULT_AUTOSAVE_BRANCH)
        assert len(commits) == 3  # initial + 2 autosaves

    def test_git_failure_disables_further_autosaves_and_warns_once(
        self, real_workspace
    ):
        ops, controller, model, workspace = real_workspace
        model.add_task(row=1, col=0, duration=3, description='Task A')

        with (
            patch.object(git_helper, 'commit', side_effect=git_helper.GitError('boom')),
            patch(
                'src.operations.version_control_operations.messagebox.showwarning'
            ) as warn,
        ):
            ops.maybe_autosave_checkpoint()
            assert warn.call_count == 1
            assert controller.version_control.autosave_disabled is True

            # A further edit must not retry (and must not warn again).
            model.add_task(row=2, col=0, duration=3, description='Task B')
            ops.maybe_autosave_checkpoint()
            assert warn.call_count == 1

    def _reload_from(self, model, workspace, tracked_file, sha):
        """Mirrors exactly what undo()/redo() will do: load the model from
        an older commit's content without moving the autosave branch."""
        content = git_helper.checkout_file_content(workspace, sha, tracked_file)
        path = workspace / tracked_file
        path.write_bytes(content)
        model.load_from_file(str(path))

    def test_browsing_history_with_no_new_edit_creates_no_commit(self, real_workspace):
        """The core correctness property this cursor design exists for:
        a model that reflects an OLDER commit (as if the user had just
        undone) must not look like "a change worth committing" just
        because its content differs from the branch tip - only a genuine
        edit relative to what's currently loaded should."""
        ops, controller, model, workspace = real_workspace
        model.add_task(row=1, col=0, duration=3, description='Task A')
        ops.maybe_autosave_checkpoint()
        initial_sha = git_helper.log(workspace, DEFAULT_AUTOSAVE_BRANCH)[-1].sha

        self._reload_from(model, workspace, TRACKED_FILE_NAME, initial_sha)
        controller.version_control.history_cursor_sha = initial_sha
        before = git_helper.log(workspace, DEFAULT_AUTOSAVE_BRANCH)

        ops.maybe_autosave_checkpoint()

        assert git_helper.log(workspace, DEFAULT_AUTOSAVE_BRANCH) == before

    def test_editing_after_the_cursor_moves_back_discards_the_redo_future(
        self, real_workspace
    ):
        ops, controller, model, workspace = real_workspace
        model.add_task(row=1, col=0, duration=3, description='Task A')
        ops.maybe_autosave_checkpoint()
        initial_sha = git_helper.log(workspace, DEFAULT_AUTOSAVE_BRANCH)[-1].sha

        self._reload_from(model, workspace, TRACKED_FILE_NAME, initial_sha)
        controller.version_control.history_cursor_sha = initial_sha
        # A genuine new edit, made from the rewound state.
        model.add_task(row=1, col=0, duration=5, description='Task B')
        ops.maybe_autosave_checkpoint()

        commits = git_helper.log(workspace, DEFAULT_AUTOSAVE_BRANCH)
        # initial + the new edit - Task A's commit was discarded, not kept
        # alongside it, so this is a linear two-commit history, not three.
        assert len(commits) == 2
        assert commits[-1].sha == initial_sha
        assert [t['description'] for t in model.tasks] == ['Task B']


class TestSaveVersion:
    def test_noop_when_not_versioned(self):
        ops, controller, _model = _ops()
        controller.version_control = None

        ops.save_version()  # must not raise - nothing to do

    def test_nothing_to_save_when_no_changes_since_last_checkpoint(
        self, real_workspace
    ):
        ops, _controller, _model, workspace = real_workspace

        with (
            patch(
                'src.operations.version_control_operations.messagebox.showinfo'
            ) as showinfo,
            patch(
                'src.operations.version_control_operations.simpledialog.askstring'
            ) as askstring,
        ):
            ops.save_version()

        showinfo.assert_called_once()
        assert showinfo.call_args[0][0] == 'Nothing to Save'
        askstring.assert_not_called()
        assert git_helper.current_branch(workspace) == DEFAULT_AUTOSAVE_BRANCH

    def test_squashes_autosave_commits_into_one_main_commit(self, real_workspace):
        ops, _controller, model, workspace = real_workspace
        model.add_task(row=1, col=0, duration=3, description='Task A')
        ops.maybe_autosave_checkpoint()
        model.add_task(row=2, col=0, duration=3, description='Task B')
        ops.maybe_autosave_checkpoint()
        assert len(git_helper.log(workspace, DEFAULT_AUTOSAVE_BRANCH)) == 3

        with (
            patch(
                'src.operations.version_control_operations.simpledialog.askstring',
                return_value='End of day one',
            ),
            patch('src.operations.version_control_operations.messagebox.showinfo'),
        ):
            ops.save_version()

        main_commits = git_helper.log(workspace, DEFAULT_MAIN_BRANCH)
        assert [c.message for c in main_commits] == [
            'End of day one',
            'Initial commit',
        ]
        autosave_commits = git_helper.log(workspace, DEFAULT_AUTOSAVE_BRANCH)
        assert autosave_commits == main_commits  # reset onto main's new tip

        assert git_helper.current_branch(workspace) == DEFAULT_AUTOSAVE_BRANCH
        assert git_helper.is_clean(workspace)
        assert len(model.tasks) == 2  # both edits survived the squash

    def test_blank_message_uses_a_generated_default(self, real_workspace):
        ops, _controller, model, workspace = real_workspace
        model.add_task(row=1, col=0, duration=3, description='Task A')

        with (
            patch(
                'src.operations.version_control_operations.simpledialog.askstring',
                return_value='   ',
            ),
            patch('src.operations.version_control_operations.messagebox.showinfo'),
        ):
            ops.save_version()

        main_commits = git_helper.log(workspace, DEFAULT_MAIN_BRANCH)
        assert main_commits[0].message.startswith('Checkpoint ')

    def test_cancel_leaves_history_untouched(self, real_workspace):
        ops, _controller, model, workspace = real_workspace
        model.add_task(row=1, col=0, duration=3, description='Task A')
        ops.maybe_autosave_checkpoint()
        before_main = git_helper.log(workspace, DEFAULT_MAIN_BRANCH)

        with patch(
            'src.operations.version_control_operations.simpledialog.askstring',
            return_value=None,
        ):
            ops.save_version()

        assert git_helper.log(workspace, DEFAULT_MAIN_BRANCH) == before_main
        assert git_helper.current_branch(workspace) == DEFAULT_AUTOSAVE_BRANCH
        assert git_helper.is_clean(workspace)


class TestUndoRedo:
    def test_noop_when_not_versioned(self):
        ops, controller, _model = _ops()
        controller.version_control = None

        ops.undo()  # must not raise - nothing to do
        ops.redo()

    def test_undo_at_the_oldest_commit_is_a_noop(self, real_workspace):
        ops, controller, model, workspace = real_workspace
        cursor_before = controller.version_control.history_cursor_sha

        ops.undo()

        assert controller.version_control.history_cursor_sha == cursor_before
        assert len(model.tasks) == 0
        assert git_helper.is_clean(workspace)

    def test_redo_at_the_tip_is_a_noop(self, real_workspace):
        ops, controller, model, workspace = real_workspace
        cursor_before = controller.version_control.history_cursor_sha

        ops.redo()

        assert controller.version_control.history_cursor_sha == cursor_before

    def test_undo_reverts_to_the_previous_commits_content(self, real_workspace):
        ops, controller, model, workspace = real_workspace
        model.add_task(row=1, col=0, duration=3, description='Task A')
        ops.maybe_autosave_checkpoint()
        model.add_task(row=2, col=0, duration=3, description='Task B')
        ops.maybe_autosave_checkpoint()
        assert {t['description'] for t in model.tasks} == {'Task A', 'Task B'}

        ops.undo()

        assert [t['description'] for t in model.tasks] == ['Task A']
        assert git_helper.is_clean(workspace)
        assert git_helper.current_branch(workspace) == DEFAULT_AUTOSAVE_BRANCH

    def test_redo_reapplies_the_undone_edit(self, real_workspace):
        ops, controller, model, workspace = real_workspace
        model.add_task(row=1, col=0, duration=3, description='Task A')
        ops.maybe_autosave_checkpoint()
        model.add_task(row=2, col=0, duration=3, description='Task B')
        ops.maybe_autosave_checkpoint()
        ops.undo()
        assert [t['description'] for t in model.tasks] == ['Task A']

        ops.redo()

        assert {t['description'] for t in model.tasks} == {'Task A', 'Task B'}
        assert git_helper.is_clean(workspace)

    def test_undo_captures_an_in_flight_edit_before_moving(self, real_workspace):
        """Ctrl+Z pressed right after a drag, with no explicit save in
        between: the drag must be committed (so it's not just lost) and
        THEN undone back to the state before it - not silently discarded."""
        ops, controller, model, workspace = real_workspace
        model.add_task(
            row=1, col=0, duration=3, description='Task A'
        )  # not yet committed

        ops.undo()

        assert len(model.tasks) == 0  # back to before Task A
        commits = git_helper.log(workspace, DEFAULT_AUTOSAVE_BRANCH)
        assert any('Autosave' in c.message for c in commits)  # Task A was captured
        assert len(commits) == 2  # initial + the captured edit

    def test_can_undo_and_can_redo_reflect_position(self, real_workspace):
        ops, _controller, model, _workspace = real_workspace
        assert ops.can_undo() is False  # only the initial commit exists
        assert ops.can_redo() is False

        model.add_task(row=1, col=0, duration=3, description='Task A')
        ops.maybe_autosave_checkpoint()
        assert ops.can_undo() is True  # one step back to the initial commit
        assert ops.can_redo() is False  # already at the tip

        ops.undo()
        assert ops.can_undo() is False  # back at the oldest commit
        assert ops.can_redo() is True  # can step forward to Task A again

    def test_editing_after_undo_makes_redo_unavailable(self, real_workspace):
        """A new edit after undoing discards the redo-able future (see
        maybe_autosave_checkpoint's own docstring) - can_redo must reflect
        that immediately, the same way a conventional editor's redo
        history disappears once you type something new."""
        ops, controller, model, workspace = real_workspace
        model.add_task(row=1, col=0, duration=3, description='Task A')
        ops.maybe_autosave_checkpoint()
        ops.undo()
        assert ops.can_redo() is True

        model.add_task(row=1, col=0, duration=5, description='Task B')
        ops.maybe_autosave_checkpoint()

        assert ops.can_redo() is False
        assert [t['description'] for t in model.tasks] == ['Task B']

    def test_save_version_after_a_plain_undo_still_works(self, real_workspace):
        """The scenario that motivated keeping undo/redo from touching the
        real tracked file at all: git refuses to `checkout` a branch over
        conflicting uncommitted changes, so if undo had left the working
        tree dirty relative to autosave's tip, save_version()'s own
        `checkout main` would fail outright here."""
        ops, _controller, model, workspace = real_workspace
        model.add_task(row=1, col=0, duration=3, description='Task A')
        ops.maybe_autosave_checkpoint()
        ops.undo()  # browsing only, no new edit made after this

        with (
            patch(
                'src.operations.version_control_operations.simpledialog.askstring',
                return_value='v1',
            ),
            patch('src.operations.version_control_operations.messagebox.showinfo'),
        ):
            ops.save_version()

        main_commits = git_helper.log(workspace, DEFAULT_MAIN_BRANCH)
        assert [c.message for c in main_commits] == ['v1', 'Initial commit']
        assert git_helper.is_clean(workspace)


def _find_toplevel(root, title):
    for w in root.winfo_children():
        if isinstance(w, tk.Toplevel) and w.title() == title:
            return w
    raise AssertionError(f'no {title!r} dialog found')


def _find_widgets(parent, cls):
    found = []
    for child in parent.winfo_children():
        if isinstance(child, cls):
            found.append(child)
        found.extend(_find_widgets(child, cls))
    return found


def _find_button(parent, text):
    for button in _find_widgets(parent, tk.Button):
        if button.cget('text') == text:
            return button
    raise AssertionError(f'no button labeled {text!r} found')


class TestJumpToVersion:
    def test_noop_when_not_versioned(self):
        ops, controller, _model = _ops()
        controller.version_control = None

        ops.jump_to_version()  # must not raise - nothing to do

    def test_jump_to_the_oldest_commit_reloads_its_content(self, real_workspace):
        ops, controller, model, workspace = real_workspace
        model.add_task(row=1, col=0, duration=3, description='Task A')
        ops.maybe_autosave_checkpoint()
        initial_sha = git_helper.log(workspace, DEFAULT_AUTOSAVE_BRANCH)[-1].sha

        root = tk.Tk()
        try:
            controller.root = root

            def answer():
                dialog = _find_toplevel(root, 'Jump to Version')
                listbox = _find_widgets(dialog, tk.Listbox)[0]
                # Oldest commit ("Initial commit") is the last row - the
                # dialog lists most-recent first, matching git log's order.
                listbox.selection_clear(0, tk.END)
                listbox.selection_set(tk.END)
                _find_button(dialog, 'Jump').invoke()

            root.after(50, answer)
            ops.jump_to_version()
            root.update()
        finally:
            root.destroy()

        assert len(model.tasks) == 0
        assert controller.version_control.history_cursor_sha == initial_sha

    def test_cancel_leaves_everything_unchanged(self, real_workspace):
        ops, controller, model, workspace = real_workspace
        model.add_task(row=1, col=0, duration=3, description='Task A')
        ops.maybe_autosave_checkpoint()
        cursor_before = controller.version_control.history_cursor_sha

        root = tk.Tk()
        try:
            controller.root = root

            def answer():
                dialog = _find_toplevel(root, 'Jump to Version')
                _find_button(dialog, 'Cancel').invoke()

            root.after(50, answer)
            ops.jump_to_version()
            root.update()
        finally:
            root.destroy()

        assert controller.version_control.history_cursor_sha == cursor_before
        assert [t['description'] for t in model.tasks] == ['Task A']
