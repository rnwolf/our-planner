import pytest
from unittest.mock import MagicMock, patch

from src.model.task_resource_model import TaskResourceModel
from src.view.ui_components import UIComponents


class TestTaskTooltips:
    """Tests for task tooltip functionality."""

    def setup_method(self):
        """Set up the test environment."""
        self.model = TaskResourceModel()
        self.controller = MagicMock()
        self.controller.model = self.model
        self.controller.task_canvas = MagicMock()

        # Create UI components
        self.ui = UIComponents(self.controller, self.model)

        # Mock the add_tag_tooltip method
        self.ui.add_tag_tooltip = MagicMock()

    def test_task_tooltips_with_tags_and_resources(self):
        """Test that tooltips include both tags and resources."""
        # Create resources
        resource1 = {'id': 1, 'name': 'Resource A', 'capacity': [1.0] * 100, 'tags': []}
        resource2 = {'id': 2, 'name': 'Resource B', 'capacity': [1.0] * 100, 'tags': []}
        self.model.resources = [resource1, resource2]

        # Create a task with tags and resources
        task = {
            'task_id': 1,
            'row': 0,
            'col': 0,
            'duration': 3,
            'description': 'Test Task',
            'tags': ['important', 'phase1'],
            'resources': {1: 0.5, 2: 1.0},
            'predecessors': [],
            'successors': [],
        }

        # Mock task UI elements
        box_id = MagicMock()
        self.ui.task_ui_elements = {1: {'box': box_id}}

        # Call the method to test
        self.ui.add_task_tooltips(task)

        # Verify add_tag_tooltip was called
        self.ui.add_tag_tooltip.assert_called_once()

        # Get the tooltip text from the call arguments
        args, kwargs = self.ui.add_tag_tooltip.call_args
        tooltip_text = args[2]

        # Verify tooltip content includes both tags and resources
        assert 'Tags: important, phase1' in tooltip_text
        assert 'Resources:' in tooltip_text
        assert '1.0 × Resource B' in tooltip_text  # Higher allocation first
        assert '0.5 × Resource A' in tooltip_text

    def test_task_tooltips_with_only_tags(self):
        """Test tooltips for tasks with tags but no resources."""
        # Create a task with only tags
        task = {
            'task_id': 1,
            'row': 0,
            'col': 0,
            'duration': 3,
            'description': 'Test Task',
            'tags': ['important', 'phase1'],
            'resources': {},
            'predecessors': [],
            'successors': [],
        }

        # Mock task UI elements
        box_id = MagicMock()
        self.ui.task_ui_elements = {1: {'box': box_id}}

        # Call the method to test
        self.ui.add_task_tooltips(task)

        # Verify add_tag_tooltip was called
        self.ui.add_tag_tooltip.assert_called_once()

        # Get the tooltip text from the call arguments
        args, kwargs = self.ui.add_tag_tooltip.call_args
        tooltip_text = args[2]

        # Verify tooltip content includes tags but not resources
        assert 'Tags: important, phase1' in tooltip_text
        assert 'Resources:' not in tooltip_text

    def test_task_tooltips_with_only_resources(self):
        """Test tooltips for tasks with resources but no tags."""
        # Create resources
        resource1 = {'id': 1, 'name': 'Resource A', 'capacity': [1.0] * 100, 'tags': []}
        self.model.resources = [resource1]

        # Create a task with only resources
        task = {
            'task_id': 1,
            'row': 0,
            'col': 0,
            'duration': 3,
            'description': 'Test Task',
            'tags': [],
            'resources': {1: 0.5},
            'predecessors': [],
            'successors': [],
        }

        # Mock task UI elements
        box_id = MagicMock()
        self.ui.task_ui_elements = {1: {'box': box_id}}

        # Call the method to test
        self.ui.add_task_tooltips(task)

        # Verify add_tag_tooltip was called
        self.ui.add_tag_tooltip.assert_called_once()

        # Get the tooltip text from the call arguments
        args, kwargs = self.ui.add_tag_tooltip.call_args
        tooltip_text = args[2]

        # Verify tooltip content includes resources but not tags
        assert 'Tags:' not in tooltip_text
        assert 'Resources:' in tooltip_text
        assert '0.5 × Resource A' in tooltip_text
