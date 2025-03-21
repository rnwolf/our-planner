import tkinter as tk
from task_manager import TaskResourceManager


def main():
    root = tk.Tk()
    app = TaskResourceManager(root)
    root.mainloop()


if __name__ == "__main__":
    main()
