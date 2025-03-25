import tkinter as tk
from task_manager import TaskResourceManager


def main():
    root = tk.Tk()

    # Set application title and icon
    root.title("Task Resource Manager")

    # Create the main application
    TaskResourceManager(root)

    # Start the main loop
    root.mainloop()


if __name__ == "__main__":
    main()
