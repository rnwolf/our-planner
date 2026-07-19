"""
Our-Planner - Main application module

This module initializes and starts the application.

Copyright (c) 2025-2026 Rüdiger Wolf

Distributed under the terms of the MIT License - see LICENSE.txt.

"""

import tkinter as tk
from src.controller.task_manager import TaskResourceManager
import argparse
import sys
from src import __version__  # Import the version from your package


def main():
    """
    Main entry point for the Task Resource Manager application.

    Sets up the root window, creates the application instance, and starts the main loop.
    """
    parser = argparse.ArgumentParser(
        prog='our-planner',  # Optional: Specify the program name
        description='An application for collaboratively working on plans with our team.',
    )

    # Add the version argument
    parser.add_argument(
        '-v',
        '--version',
        action='version',
        version=f'%(prog)s {__version__}',  # Display version
    )
    # parse the command line arguments and display verison information
    args = parser.parse_args()
    # If no arguments are provided, launch the GUI
    if len(sys.argv) == 1:
        root = tk.Tk()
        # Set application title
        root.title('Task Resource Manager')
        # Set window size
        root.geometry('1000x900')
        # Create the main application controller
        TaskResourceManager(root)
        # Start the main loop
        root.mainloop()


if __name__ == '__main__':
    main()
