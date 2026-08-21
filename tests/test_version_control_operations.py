"""New Versioned Project... (File menu) and the marker-based detection
that re-activates/deactivates versioning on later load/new/save-as -
see version_control_operations.py's own docstring for the design.
"""

import json
from unittest.mock import MagicMock, patch

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
            workspace_dir=workspace, tracked_file=TRACKED_FILE_NAME
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
