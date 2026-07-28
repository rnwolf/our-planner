from unittest.mock import MagicMock

from src.model.task_resource_model import TaskResourceModel
from src.view.ui_components import (
    TASK_NAME_TOOLTIP_WIDTH,
    UIComponents,
    wrap_task_name_for_tooltip,
)


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

    def test_task_tooltip_starts_with_task_name(self):
        """The task name must be the first line of the tooltip, so it's
        readable even when a long-duration task's centered on-canvas label
        has scrolled off-screen."""
        task = {
            'task_id': 1,
            'row': 0,
            'col': 0,
            'duration': 3,
            'description': 'Build the widget',
            'tags': [],
            'resources': {},
            'predecessors': [],
            'successors': [],
        }
        box_id = MagicMock()
        self.ui.task_ui_elements = {1: {'box': box_id}}

        self.ui.add_task_tooltips(task)

        args, kwargs = self.ui.add_tag_tooltip.call_args
        tooltip_text = args[2]
        assert tooltip_text.startswith('Build the widget')

    def test_task_tooltip_name_wraps_to_two_lines(self):
        """A long task name wraps onto a second line rather than being cut
        off or left as one very wide line."""
        long_name = (
            'This is a fairly long task name that should wrap onto a second line nicely'
        )
        task = {
            'task_id': 1,
            'row': 0,
            'col': 0,
            'duration': 3,
            'description': long_name,
            'tags': [],
            'resources': {},
            'predecessors': [],
            'successors': [],
        }
        box_id = MagicMock()
        self.ui.task_ui_elements = {1: {'box': box_id}}

        self.ui.add_task_tooltips(task)

        args, kwargs = self.ui.add_tag_tooltip.call_args
        tooltip_text = args[2]
        name_lines = wrap_task_name_for_tooltip(long_name)
        assert len(name_lines) == 2
        assert tooltip_text.startswith('\n'.join(name_lines))
        # the next line after the wrapped name is a regular tooltip field
        assert 'Task state:' in tooltip_text.splitlines()[len(name_lines)]


class TestWrapTaskNameForTooltip:
    """Tests for the wrap_task_name_for_tooltip helper in isolation."""

    def test_short_name_is_not_wrapped(self):
        assert wrap_task_name_for_tooltip('Short name') == ['Short name']

    def test_long_name_wraps_to_at_most_two_lines(self):
        name = (
            'This is a fairly long task name that should wrap onto a second line nicely'
        )
        lines = wrap_task_name_for_tooltip(name)
        assert len(lines) == 2
        for line in lines:
            assert len(line) <= TASK_NAME_TOOLTIP_WIDTH

    def test_very_long_name_is_truncated_with_ellipsis(self):
        name = (
            'This task name is extremely long and will definitely need '
            'truncation because it goes on and on and on far beyond two '
            'lines worth of text'
        )
        lines = wrap_task_name_for_tooltip(name)
        assert len(lines) == 2
        assert lines[-1].endswith('...')
        for line in lines:
            assert len(line) <= TASK_NAME_TOOLTIP_WIDTH

    def test_empty_name_returns_single_empty_line(self):
        assert wrap_task_name_for_tooltip('') == ['']
