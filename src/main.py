"""
Task Resource Manager - Main application module

This module initializes and starts the Task Resource Manager application.
"""

import tkinter as tk
from src.controller.task_manager import TaskResourceManager


def main():
    """
    Main entry point for the Task Resource Manager application.

    Sets up the root window, creates the application instance, and starts the main loop.
    """
    root = tk.Tk()

    # Set application title
    root.title("Task Resource Manager")

    # Set window size
    root.geometry("1000x600")

    # Create the main application controller
    TaskResourceManager(root)

    # Start the main loop
    root.mainloop()


if __name__ == "__main__":
    main()
