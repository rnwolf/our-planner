import pytest
import os
import json
import tempfile
from unittest.mock import MagicMock, patch
from datetime import datetime

from src.model.task_resource_model import TaskResourceModel
from src.operations.file_operations import FileOperations


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
