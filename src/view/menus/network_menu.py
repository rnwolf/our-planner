"""
Network menu for Our-Planner.

This module contains the UI components for the Network menu.
"""

import tkinter as tk
from src.utils.tk_helpers import mnemonic


class NetworkMenu:
    """Implementation of the Network menu for Our-Planner."""

    def __init__(self, controller, root, menu_bar):
        """Initialize the network menu.

        Args:
            controller: The main application controller
            root: The root Tk window
            menu_bar: The main menu bar to add the Network menu to
        """
        self.controller = controller
        self.root = root

        # Create Network menu
        self.network_menu = tk.Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label='Network', menu=self.network_menu, underline=0)

        self.network_menu.add_command(
            label='Import CCPM Schedule...',
            underline=mnemonic('Import CCPM Schedule...', 'Import'),
            command=self.controller.file_ops.import_ccpm_schedule,
        )

        # Import Network: a plain, unscheduled reference network (tasks with
        # predecessor_ids/resource_ids, no start/finish yet) - Import CCPM
        # Schedule above needs an already-scheduled schedule.csv, which this
        # doesn't have. Three deliberately separate steps, in the order they
        # must run: resources, then their calendars, then tasks (each task's
        # resource_ids must already exist).
        self.import_network_menu = tk.Menu(self.network_menu, tearoff=0)
        self.network_menu.add_cascade(
            label='Import Network',
            menu=self.import_network_menu,
            # the 'w' - 'I' is already Import CCPM Schedule's mnemonic above
            underline=mnemonic('Import Network', 'Network', 'w'),
        )
        self.import_network_menu.add_command(
            label='Import Resources...',
            underline=mnemonic('Import Resources...', 'Resources'),
            command=self.controller.file_ops.import_resources,
        )
        self.import_network_menu.add_command(
            label='Import Resource Calendars...',
            underline=mnemonic('Import Resource Calendars...', 'Calendars'),
            command=self.controller.file_ops.import_resource_calendars,
        )
        self.import_network_menu.add_command(
            label='Import Tasks...',
            underline=mnemonic('Import Tasks...', 'Tasks'),
            command=self.controller.file_ops.import_tasks,
        )

        self.network_menu.add_command(
            label='Export CCPM Network...',
            # 'C' - 'E' is Export...'s mnemonic below
            underline=mnemonic('Export CCPM Network...', 'CCPM'),
            command=self.controller.ccpm_ops.export_ccpm_network,
        )
        self.network_menu.add_command(
            label='Schedule with CCPM...',
            underline=mnemonic('Schedule with CCPM...', 'Schedule'),
            command=self.controller.ccpm_ops.schedule_with_ccpm,
        )

        self.network_menu.add_separator()
        self.network_menu.add_command(
            label='Export...',
            underline=mnemonic('Export...', 'Export'),
            command=self.controller.export_ops.open_export_dialog,
        )
