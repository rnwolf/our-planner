import tkinter as tk
from tkinter import simpledialog, Menu, Entry, Button


class TextVariableUpdater:
    def __init__(self, root):
        self.root = root
        self.root.title("Text Variable Updater")

        self.text_vars = [
            tk.StringVar(value=f"Var {i+1}: Initial Text") for i in range(5)
        ]
        self.labels = []

        for i, var in enumerate(self.text_vars):
            label = tk.Label(root, textvariable=var)
            label.pack(pady=5)
            self.labels.append(label)

        self.create_menu()

    def create_menu(self):
        menubar = Menu(self.root)
        config_menu = Menu(menubar, tearoff=0)
        config_menu.add_command(label="Update", command=self.open_update_dialog)
        menubar.add_cascade(label="Config", menu=config_menu)
        self.root.config(menu=menubar)

    def open_update_dialog(self):
        print(self.root)
        dialog = tk.Toplevel(self.root)
        dialog.title("Update Variables")

        # Position the dialog relative to the parent window
        x = self.root.winfo_x() + 50
        y = self.root.winfo_y() + 50
        dialog.geometry(f"+{x}+{y}")

        entries = []
        for i, var in enumerate(self.text_vars):
            tk.Label(dialog, text=f"Var {i+1}:").grid(row=i, column=0, sticky="w")
            entry = Entry(dialog, textvariable=tk.StringVar(value=var.get()))
            entry.grid(row=i, column=1)
            entries.append(entry)

        def update_variables():
            for i, entry in enumerate(entries):
                self.text_vars[i].set(entry.get())
            dialog.destroy()

        def cancel_update():
            dialog.destroy()

        submit_button = Button(dialog, text="Submit", command=update_variables)
        submit_button.grid(row=len(self.text_vars), column=0, pady=10)

        cancel_button = Button(dialog, text="Cancel", command=cancel_update)
        cancel_button.grid(row=len(self.text_vars), column=1, pady=10)


if __name__ == "__main__":
    root = tk.Tk()
    app = TextVariableUpdater(root)
    root.mainloop()
