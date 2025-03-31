import pytest
from unittest.mock import MagicMock, patch
import tkinter as tk

import sys
import os

# Add the parent directory to sys.path to allow importing application modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.view.menus.help_menu import HelpMenu


class TestHelpMenu:
    """Test cases for the HelpMenu class."""

    def setup_method(self):
        """Set up the test environment."""
        # Create a mock Tk root window
        self.root = MagicMock()

        # Create a mock controller
        self.controller = MagicMock()
        self.controller.model = MagicMock()
        self.controller.selected_tasks = []

        # Create a mock menu bar
        self.menu_bar = MagicMock()

        # These attributes would typically cascade from tk.Menu
        self.menu_bar.add_cascade = MagicMock()

        # Create a mock menu that would be created by tk.Menu
        self.mock_menu = MagicMock()
        self.mock_menu.add_command = MagicMock()

        # Patch tk.Menu to return our mock menu
        with patch('tkinter.Menu', return_value=self.mock_menu):
            # Create the help menu
            self.help_menu = HelpMenu(self.controller, self.root, self.menu_bar)

    def test_initialization(self):
        """Test that the help menu is initialized correctly."""
        # Verify that a menu was created and added to the menu bar
        self.menu_bar.add_cascade.assert_called_once()

        # Check that the correct menu items were added
        assert (
            self.mock_menu.add_command.call_count == 4
        ), 'Expected 3 menu items to be added'

        # Verify the first call was for the Website menu item
        args, kwargs = self.mock_menu.add_command.call_args_list[0]
        assert (
            kwargs['label'] == 'Documentation'
        ), f"Expected 'Documentation' but got {kwargs['label']}"

        # Verify the second call was for the Website menu item
        args, kwargs = self.mock_menu.add_command.call_args_list[1]
        assert (
            kwargs['label'] == 'Website'
        ), f"Expected 'Website' but got {kwargs['label']}"

        # Verify the third call was for the About menu item
        args, kwargs = self.mock_menu.add_command.call_args_list[2]
        assert kwargs['label'] == 'About', f"Expected 'About' but got {kwargs['label']}"

        # Verify the fourth call was for the Debug menu item
        args, kwargs = self.mock_menu.add_command.call_args_list[3]
        assert kwargs['label'] == 'Debug', f"Expected 'Debug' but got {kwargs['label']}"

    @patch('webbrowser.open')
    def test_open_website(self, mock_webbrowser_open):
        """Test that open_website opens the correct URL."""
        self.help_menu.open_website()
        mock_webbrowser_open.assert_called_once_with(
            'https://github.com/rnwolf/py_sequencer'
        )
