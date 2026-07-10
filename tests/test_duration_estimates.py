import os
import tempfile

import pytest

from src.model.task_resource_model import TaskResourceModel


class TestDurationEstimateDefaults:
    """Test cases for the realistic/optimal duration fields on task creation.

    CCPM terminology: Realistic = Optimal + Contingency. `realistic_duration`
    is the permanent record of the original estimate; `optimal_duration` is
    the "if everything went perfectly" estimate, captured separately since
    `duration` itself may later be overwritten by a buffer-cutting step.
    """

    def setup_method(self):
        self.model = TaskResourceModel()

    def test_realistic_duration_defaults_to_duration(self):
        task = self.model.add_task(
            row=1, col=5, duration=7, description='Test Task'
        )
        assert task['realistic_duration'] == 7

    def test_optimal_duration_defaults_to_none(self):
        task = self.model.add_task(
            row=1, col=5, duration=7, description='Test Task'
        )
        assert task['optimal_duration'] is None


class TestSetOptimalDuration:
    """Test cases for TaskResourceModel.set_optimal_duration."""

    def setup_method(self):
        self.model = TaskResourceModel()

    def test_set_optimal_duration_updates_task(self):
        task = self.model.add_task(
            row=1, col=5, duration=10, description='Test Task'
        )
        result = self.model.set_optimal_duration(task['task_id'], 6)

        assert result is True
        assert self.model.get_task(task['task_id'])['optimal_duration'] == 6

    def test_set_optimal_duration_does_not_change_duration_or_realistic(self):
        task = self.model.add_task(
            row=1, col=5, duration=10, description='Test Task'
        )
        self.model.set_optimal_duration(task['task_id'], 6)

        updated = self.model.get_task(task['task_id'])
        assert updated['duration'] == 10
        assert updated['realistic_duration'] == 10

    def test_set_optimal_duration_nonexistent_task_returns_false(self):
        result = self.model.set_optimal_duration(999, 6)
        assert result is False


class TestSetRealisticDuration:
    """Test cases for TaskResourceModel.set_realistic_duration."""

    def setup_method(self):
        self.model = TaskResourceModel()

    def test_set_realistic_duration_updates_task(self):
        task = self.model.add_task(
            row=1, col=5, duration=10, description='Test Task'
        )
        result = self.model.set_realistic_duration(task['task_id'], 12)

        assert result is True
        assert self.model.get_task(task['task_id'])['realistic_duration'] == 12

    def test_set_realistic_duration_does_not_change_duration(self):
        task = self.model.add_task(
            row=1, col=5, duration=10, description='Test Task'
        )
        self.model.set_realistic_duration(task['task_id'], 12)

        assert self.model.get_task(task['task_id'])['duration'] == 10

    def test_set_realistic_duration_nonexistent_task_returns_false(self):
        result = self.model.set_realistic_duration(999, 12)
        assert result is False


class TestBaselineCapturesDurationEstimates:
    """Test cases for capture_project_baseline recording realistic_duration.

    The baseline is the signed-off plan snapshot taken when a project moves
    from planning to execution (Stage 1/4). It must preserve whatever
    realistic_duration a task had at that moment, independent of later
    changes to duration/realistic_duration.
    """

    def setup_method(self):
        self.model = TaskResourceModel()
        self.project = self.model.add_project('Test Project')

    def test_baseline_records_realistic_duration(self):
        task = self.model.add_task(
            row=1,
            col=5,
            duration=10,
            description='Test Task',
            project_id=self.project['id'],
        )
        self.model.set_realistic_duration(task['task_id'], 15)

        self.model.capture_project_baseline(self.project['id'])

        baseline = self.model.get_task(task['task_id'])['baseline']
        assert baseline['duration'] == 10
        assert baseline['realistic_duration'] == 15
        assert 'captured_at' in baseline

    def test_baseline_realistic_duration_survives_later_changes(self):
        task = self.model.add_task(
            row=1,
            col=5,
            duration=10,
            description='Test Task',
            project_id=self.project['id'],
        )
        self.model.capture_project_baseline(self.project['id'])

        # Simulate a later buffer-cutting-style change to duration and
        # realistic_duration - the baseline snapshot must not be affected.
        self.model.set_realistic_duration(task['task_id'], 3)
        self.model.tasks[0]['duration'] = 6

        baseline = self.model.get_task(task['task_id'])['baseline']
        assert baseline['duration'] == 10
        assert baseline['realistic_duration'] == 10

    def test_capture_project_baseline_returns_task_count(self):
        self.model.add_task(
            row=1, col=5, duration=10, description='Task 1',
            project_id=self.project['id'],
        )
        self.model.add_task(
            row=2, col=5, duration=5, description='Task 2',
            project_id=self.project['id'],
        )

        count = self.model.capture_project_baseline(self.project['id'])
        assert count == 2

    def test_capture_project_baseline_unknown_project_returns_negative_one(self):
        count = self.model.capture_project_baseline(9999)
        assert count == -1


class TestDurationEstimateSaveLoadRoundTrip:
    """Test cases confirming optimal/realistic durations survive save/load."""

    def setup_method(self):
        self.model = TaskResourceModel()

    def test_save_and_load_preserves_duration_estimates(self):
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as temp:
            temp_path = temp.name

        try:
            task = self.model.add_task(
                row=1, col=5, duration=10, description='Test Task'
            )
            self.model.set_realistic_duration(task['task_id'], 14)
            self.model.set_optimal_duration(task['task_id'], 7)

            assert self.model.save_to_file(temp_path) is True

            new_model = TaskResourceModel()
            assert new_model.load_from_file(temp_path) is True

            loaded_task = new_model.get_task(task['task_id'])
            assert loaded_task['realistic_duration'] == 14
            assert loaded_task['optimal_duration'] == 7
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_load_repairs_missing_duration_estimate_fields(self):
        """Old save files predating this fields must be repaired on load."""
        with tempfile.NamedTemporaryFile(
            suffix='.json', delete=False, mode='w'
        ) as temp:
            temp_path = temp.name
            import json

            json.dump(
                {
                    'tasks': [
                        {
                            'task_id': 1,
                            'row': 1,
                            'col': 5,
                            'duration': 9,
                            'description': 'Legacy Task',
                            'resources': {},
                            'predecessors': [],
                            'tags': [],
                            'color': 'Cyan',
                            'notes': [],
                            # Deliberately omit realistic_duration/optimal_duration
                            # to simulate a pre-Stage-14 save file.
                        }
                    ],
                    'resources': [],
                    'days': 100,
                },
                temp,
            )

        try:
            new_model = TaskResourceModel()
            assert new_model.load_from_file(temp_path) is True

            loaded_task = new_model.get_task(1)
            assert loaded_task['realistic_duration'] == 9
            assert loaded_task['optimal_duration'] is None
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
