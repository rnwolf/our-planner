import tkinter as tk
from tkinter import ttk, messagebox

from src.operations.task_operations import OptionSelectDialog


class ReportOperations:
    """Stage 10 Part B: the pluggable Reporting framework. Fever Charts
    (Stage 8) are a separate, already-working report left untouched by
    design - this is where new report types that reuse the Filter menu's
    combinable filters (Stage 10 Part A) live, starting with Full-Kit
    Readiness.
    """

    def __init__(self, controller, model):
        self.controller = controller
        self.model = model

    def _select_project(self, title):
        """Prompt for a project if more than one exists (same "prompt if
        more than one project" flow as Fever Charts' project selection) -
        returns None (already reported to the user, or the user cancelled)
        if there's nothing to build a report for."""
        if not self.model.projects:
            messagebox.showinfo(
                'No Projects',
                'Create a project first via Projects > Manage Projects...',
                parent=self.controller.root,
            )
            return None

        if len(self.model.projects) == 1:
            return self.model.projects[0]

        names = [p['name'] for p in self.model.projects]
        default = self.model.get_default_project()
        dialog = OptionSelectDialog(
            self.controller.root,
            title,
            'Project:',
            names,
            initial_value=default['name'] if default else names[0],
        )
        if dialog.result is None:
            return None
        return self.model.get_project_by_name(dialog.result)

    def compute_fullkit_readiness(self, project):
        """The extractor half of the Full-Kit Readiness report - separated
        from the dialog (the renderer half) so the underlying data can be
        tested without a real Tk root. Returns (tasks_sorted_by_planned_
        start, ready_count, total_count), scoped to `project` and whatever
        filters are currently active on the Filter menu."""
        filtered = self.controller.tag_ops.get_filtered_tasks()
        tasks = [
            t
            for t in filtered
            if t.get('project_id') == project['id'] and t.get('type') == 'task'
        ]
        tasks.sort(key=lambda t: t['col'])

        ready_count = sum(1 for t in tasks if t.get('fullkit_date'))
        return tasks, ready_count, len(tasks)

    def view_fullkit_readiness_report(self, project=None):
        """The first report type built against the framework: the
        percentage of a project's tasks with a fullkit_date set, plus a
        listing sorted soonest-planned-start-first (the imminent tasks
        lacking a full kit are the actual risk, not distant ones).

        Scoped by whatever combination of Tags/Project/State/Full-Kit/
        Planned-Start-Window filters is currently active on the Filter menu
        (Stage 10 Part A) - e.g. checking "Not Started" there reproduces the
        original "backlog" framing, but nothing forces that scope.

        Applies regardless of project phase - unlike Fever Charts, full-kit
        readiness matters during planning too, not just execution.
        """
        if project is None:
            project = self._select_project('Full-Kit Readiness Report')
            if project is None:
                return

        tasks, ready_count, total = self.compute_fullkit_readiness(project)
        pct = (ready_count / total * 100) if total else 0.0

        dialog = tk.Toplevel(self.controller.root)
        dialog.title(f"Full-Kit Readiness: {project['name']}")
        dialog.transient(self.controller.root)
        dialog.grab_set()
        dialog.geometry('480x420')

        frame = tk.Frame(dialog, padx=10, pady=10)
        frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            frame,
            text=f"Full-Kit Readiness: {project['name']}",
            font=('Arial', 10, 'bold'),
            wraplength=460,
        ).pack(fill=tk.X, pady=(0, 10))

        if self.controller.tag_ops.has_active_filters():
            tk.Label(
                frame,
                text='(Scoped to the currently active Filter menu selection)',
                font=('Arial', 8, 'italic'),
                fg='gray',
            ).pack(anchor='w', pady=(0, 5))

        tk.Label(
            frame, text=f'{ready_count} of {total} tasks full-kitted ({pct:.0f}%)'
        ).pack(anchor='w', pady=(0, 10))

        tk.Label(
            frame,
            text='Tasks (soonest planned start first):',
            font=('Arial', 9, 'bold'),
        ).pack(anchor='w', pady=(0, 5))

        list_frame = tk.Frame(frame)
        list_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set)
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=listbox.yview)

        if not tasks:
            listbox.insert(tk.END, 'No matching tasks.')
        else:
            for task in tasks:
                planned_start = self.model.get_date_for_day(task['col']).strftime(
                    '%Y-%m-%d'
                )
                status = 'Ready' if task.get('fullkit_date') else 'Not Kitted'
                listbox.insert(
                    tk.END, f"[{status}] {planned_start} - {task['description']}"
                )

        tk.Button(frame, text='Close', command=dialog.destroy).pack(pady=(10, 0))
