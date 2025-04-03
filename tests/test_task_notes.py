import pytest
from unittest.mock import MagicMock
from datetime import datetime

from src.model.task_resource_model import TaskResourceModel


class TestTaskNotes:
    """Test cases for task notes functionality."""

    def setup_method(self):
        """Set up a fresh model instance for each test."""
        self.model = TaskResourceModel()

        # Create some sample tasks with notes for testing
        self.task1 = self.model.add_task(row=1, col=5, duration=3, description='Task 1')
        self.task2 = self.model.add_task(
            row=2, col=10, duration=4, description='Task 2'
        )

        # Add notes to tasks
        self.model.add_note_to_task(self.task1['task_id'], 'Note 1 for Task 1')
        self.model.add_note_to_task(self.task1['task_id'], 'Note 2 for Task 1')
        self.model.add_note_to_task(self.task2['task_id'], 'Note 1 for Task 2')

    def test_add_note_to_task(self):
        """Test adding a note to a task."""
        task_id = self.task1['task_id']
        note_text = 'New test note'

        # Add a note
        result = self.model.add_note_to_task(task_id, note_text)

        # Verify note was added
        assert result is True
        task = self.model.get_task(task_id)
        assert 'notes' in task
        assert len(task['notes']) == 3  # Should now have 3 notes

        # Verify the latest note has the right text
        latest_note = task['notes'][-1]
        assert 'text' in latest_note
        assert latest_note['text'] == note_text

        # Verify timestamp was set
        assert 'timestamp' in latest_note
        # Ensure the timestamp can be parsed as a date
        timestamp = datetime.fromisoformat(latest_note['timestamp'])
        assert isinstance(timestamp, datetime)

    def test_get_task_notes(self):
        """Test retrieving notes for a task."""
        task_id = self.task1['task_id']

        # Get notes
        notes = self.model.get_task_notes(task_id)

        # Verify we got the expected notes
        assert len(notes) == 2  # Task 1 has 2 notes

        # Notes should be sorted newest first
        assert notes[0]['text'] == 'Note 2 for Task 1'
        assert notes[1]['text'] == 'Note 1 for Task 1'

        # Test with non-existent task
        notes = self.model.get_task_notes(999)
        assert notes == []  # Should return empty list for non-existent task

    def test_delete_note_from_task(self):
        """Test deleting a note from a task."""
        task_id = self.task1['task_id']

        # Delete the first note
        result = self.model.delete_note_from_task(task_id, 0)

        # Verify note was deleted
        assert result is True
        task = self.model.get_task(task_id)
        assert len(task['notes']) == 1  # Now has 1 note
        assert task['notes'][0]['text'] == 'Note 2 for Task 1'  # The remaining note

        # Test with invalid index
        result = self.model.delete_note_from_task(task_id, 5)
        assert result is False  # Should fail with invalid index

        # Test with non-existent task
        result = self.model.delete_note_from_task(999, 0)
        assert result is False  # Should fail with non-existent task

    def test_get_all_notes_for_tasks(self):
        """Test getting notes for multiple tasks."""
        # Get notes for both tasks
        task_ids = [self.task1['task_id'], self.task2['task_id']]
        all_notes = self.model.get_all_notes_for_tasks(task_ids)

        # Verify we got all notes
        assert len(all_notes) == 3  # 2 from task1, 1 from task2

        # Verify each note has task_id, task_description and original_index
        for note in all_notes:
            assert 'task_id' in note
            assert 'task_description' in note
            assert 'original_index' in note
            assert 'text' in note
            assert 'timestamp' in note

        # Verify notes are sorted by timestamp (newest first)
        # Since we added task2's note last, it should be first
        assert all_notes[0]['text'] == 'Note 1 for Task 2'

        # Test with empty task list
        empty_notes = self.model.get_all_notes_for_tasks([])
        assert empty_notes == []  # Should return empty list

    def test_save_and_load_with_notes(self):
        """Test saving and loading a file preserves notes."""
        import tempfile
        import os
        import json

        # Create a temporary file
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as temp:
            temp_path = temp.name

        try:
            # Save the model with notes
            self.model.save_to_file(temp_path)

            # Create a new model and load the file
            new_model = TaskResourceModel()
            result = new_model.load_from_file(temp_path)

            # Verify the file loaded correctly
            assert result is True
            assert len(new_model.tasks) == 2

            # Check that notes were preserved
            task1 = new_model.get_task(self.task1['task_id'])
            task2 = new_model.get_task(self.task2['task_id'])

            assert 'notes' in task1
            assert len(task1['notes']) == 2
            assert task1['notes'][0]['text'] == 'Note 1 for Task 1'
            assert task1['notes'][1]['text'] == 'Note 2 for Task 1'

            assert 'notes' in task2
            assert len(task2['notes']) == 1
            assert task2['notes'][0]['text'] == 'Note 1 for Task 2'

            # Now delete a note and save again
            new_model.delete_note_from_task(self.task1['task_id'], 0)
            new_model.save_to_file(temp_path)

            # Load into a third model and verify the note was deleted
            third_model = TaskResourceModel()
            third_model.load_from_file(temp_path)

            task1_again = third_model.get_task(self.task1['task_id'])
            assert len(task1_again['notes']) == 1
            assert task1_again['notes'][0]['text'] == 'Note 2 for Task 1'

        finally:
            # Clean up
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_notes_with_multiple_tasks(self):
        """Test note operations across multiple tasks."""
        # Add more tasks and notes
        task3 = self.model.add_task(row=3, col=15, duration=5, description='Task 3')
        self.model.add_note_to_task(task3['task_id'], 'Note 1 for Task 3')
        self.model.add_note_to_task(task3['task_id'], 'Note 2 for Task 3')

        # Get all notes for tasks 2 and 3
        task_ids = [self.task2['task_id'], task3['task_id']]
        notes = self.model.get_all_notes_for_tasks(task_ids)

        # Should have 3 notes total (1 from task2, 2 from task3)
        assert len(notes) == 3

        # Check that the original_index values are correct
        for note in notes:
            if note['task_id'] == self.task2['task_id']:
                assert note['original_index'] == 0  # task2 only has one note
            elif note['task_id'] == task3['task_id']:
                assert note['original_index'] in [0, 1]  # task3 has two notes
                if note['text'] == 'Note 1 for Task 3':
                    assert note['original_index'] == 0
                elif note['text'] == 'Note 2 for Task 3':
                    assert note['original_index'] == 1

        # Delete a note from task3
        self.model.delete_note_from_task(
            task3['task_id'], 1
        )  # Delete "Note 2 for Task 3"

        # Get notes again and verify
        notes_after_delete = self.model.get_all_notes_for_tasks(task_ids)
        assert len(notes_after_delete) == 2  # Now should have 2 notes

        # Only "Note 1 for Task 3" should remain for task3
        task3_notes = [
            n for n in notes_after_delete if n['task_id'] == task3['task_id']
        ]
        assert len(task3_notes) == 1
        assert task3_notes[0]['text'] == 'Note 1 for Task 3'
