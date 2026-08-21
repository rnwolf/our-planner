import json
import os
import tempfile
from unittest.mock import MagicMock, patch

from src.model.task_resource_model import TaskResourceModel
from src.operations.file_operations import FileOperations
from src.operations.version_control_operations import (
    TRACKED_FILE_NAME,
    WORKSPACE_MARKER_FILENAME,
    VersionControlOperations,
    VersionControlState,
)


class TestFileOperations:
    """Test cases for the FileOperations class."""

    def setup_method(self):
        """Set up a fresh model and mock controller for each test."""
        self.model = TaskResourceModel()
        self.controller = MagicMock()
        self.controller.model = self.model
        self.file_ops = FileOperations(self.controller, self.model)

    def test_save_and_load_file(self):
        """Test saving and loading a file."""
        # Create a temporary file path
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as temp:
            temp_path = temp.name

        try:
            # Add some tasks to the model
            self.model.add_task(row=1, col=5, duration=3, description='Test Task 1')
            self.model.add_task(row=2, col=10, duration=4, description='Test Task 2')

            # Save the file
            result = self.model.save_to_file(temp_path)
            assert result is True

            # Create a new model and load the file
            new_model = TaskResourceModel()
            result = new_model.load_from_file(temp_path)

            # Verify the file loaded correctly
            assert result is True
            assert len(new_model.tasks) == 2
            assert new_model.tasks[0]['description'] == 'Test Task 1'
            assert new_model.tasks[1]['description'] == 'Test Task 2'

        finally:
            # Clean up the temporary file
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_new_project(self):
        """Test creating a new project."""
        # Add some tasks to the model
        self.model.add_task(row=1, col=5, duration=3, description='Test Task')
        self.model.current_file_path = '/fake/path/file.json'

        # Mock messagebox.askyesno to return True
        with patch('tkinter.messagebox.askyesno', return_value=True):
            self.file_ops.new_project()

            # Verify the model was reset
            assert len(self.model.tasks) == 0
            assert self.model.current_file_path is None

            # Verify controller methods were called
            self.controller.update_window_title.assert_called_once()
            self.controller.update_view.assert_called_once()


class TestVersionControlWiring:
    """FileOperations calls version_control_ops.detect_workspace() after
    every new/load/save-as, so a versioned project stops being treated as
    one the moment the user moves to a different (or plain) file - a real
    VersionControlOperations is wired in here instead of the MagicMock the
    other tests use, so this actually exercises that behavior end to end."""

    def setup_method(self):
        self.model = TaskResourceModel()
        self.controller = MagicMock()
        self.controller.model = self.model
        self.controller.version_control = None
        self.controller.version_control_ops = VersionControlOperations(
            self.controller, self.model
        )
        self.file_ops = FileOperations(self.controller, self.model)

    def _make_workspace(self, tmp_path):
        workspace = tmp_path / 'workspace'
        workspace.mkdir()
        (workspace / WORKSPACE_MARKER_FILENAME).write_text(
            json.dumps(
                {
                    'schema_version': 1,
                    'tracked_files': [TRACKED_FILE_NAME],
                    'autosave_branch': 'autosave',
                    'main_branch': 'main',
                }
            )
        )
        tracked_path = workspace / TRACKED_FILE_NAME
        self.model.save_to_file(str(tracked_path))
        return tracked_path

    def test_new_project_clears_version_control(self, tmp_path):
        tracked_path = self._make_workspace(tmp_path)
        self.controller.version_control = VersionControlState(
            workspace_dir=tracked_path.parent, tracked_file=TRACKED_FILE_NAME
        )

        with patch('tkinter.messagebox.askyesno', return_value=True):
            self.file_ops.new_project()

        assert self.controller.version_control is None

    def test_opening_a_workspaces_tracked_file_activates_versioning(self, tmp_path):
        tracked_path = self._make_workspace(tmp_path)

        with patch('tkinter.messagebox.showinfo'):
            self.file_ops._load_file(str(tracked_path))

        assert self.controller.version_control == VersionControlState(
            workspace_dir=tracked_path.parent, tracked_file=TRACKED_FILE_NAME
        )

    def test_opening_a_plain_file_deactivates_versioning(self, tmp_path):
        tracked_path = self._make_workspace(tmp_path)
        self.controller.version_control = VersionControlState(
            workspace_dir=tracked_path.parent, tracked_file=TRACKED_FILE_NAME
        )
        plain_path = tmp_path / 'plain.json'
        self.model.save_to_file(str(plain_path))

        with patch('tkinter.messagebox.showinfo'):
            self.file_ops._load_file(str(plain_path))

        assert self.controller.version_control is None

    def test_save_as_outside_the_workspace_deactivates_versioning(self, tmp_path):
        tracked_path = self._make_workspace(tmp_path)
        self.controller.version_control = VersionControlState(
            workspace_dir=tracked_path.parent, tracked_file=TRACKED_FILE_NAME
        )
        new_path = tmp_path / 'elsewhere.json'

        with (
            patch('tkinter.filedialog.asksaveasfilename', return_value=str(new_path)),
            patch('tkinter.messagebox.showinfo'),
        ):
            self.file_ops.save_file_as()

        assert self.controller.version_control is None
