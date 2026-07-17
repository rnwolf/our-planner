import os
import tempfile
import tkinter as tk
import webbrowser
from tkinter import ttk, messagebox

from src.model.dependency_notation import format_predecessor_notation
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

        # Visible resize handle, and never allow shrinking below the size
        # the content actually needs (measured, so font/theme-proof)
        ttk.Sizegrip(dialog).place(relx=1.0, rely=1.0, anchor='se')
        dialog.update_idletasks()
        dialog.minsize(dialog.winfo_reqwidth(), dialog.winfo_reqheight())

    # ---- Network Graph report (Stage 18) --------------------------------
    # Renders any set of tasks as the interactive project-network HTML the
    # external ccpm-scheduler produces for its schedules (vis-network via
    # CDN, data embedded, resource filter, task inspector) - no scheduling
    # involved, it is a pure view of the tasks as they sit on the timeline.

    def _chain_label(self, chain_id):
        """Map a task's chain onto the graph's chain labels: 'critical' for
        the critical chain, the chain's own name otherwise ('none' when
        unassigned) - the renderer colors any distinct label and shows it
        verbatim in the legend (ccpm-scheduler >= 0.8)."""
        if chain_id is None:
            return 'none'
        chain = self.model.get_chain_by_id(chain_id)
        if chain is None:
            return 'none'
        return 'critical' if chain.get('is_critical') else chain['name']

    def build_network_report_rows(self, tasks):
        """Map task dicts onto ccpm_scheduler ScheduleRows for the graph.

        Links to tasks outside the set need no filtering - the renderer
        skips edges whose predecessor is not among the nodes. The realistic
        estimate is only passed when it differs from the task's current
        duration: on hand-drawn (uncut) tasks the duration IS the realistic
        value, and an 'optimal 10d / realistic 10d' row would mislead.
        """
        from ccpm_scheduler import ScheduleRow

        rows = []
        for task in sorted(tasks, key=lambda t: (t['col'],
                                                 t['col'] + t['duration'],
                                                 t['task_id'])):
            names = []
            for rid in task.get('resources') or {}:
                resource = self.model.get_resource_by_id(rid)
                if resource:
                    names.append(resource['name'])
            realistic = task.get('realistic_duration')
            if realistic in (None, '') or realistic == task['duration']:
                realistic = None
            rows.append(ScheduleRow(
                id=str(task['task_id']),
                name=task['description'],
                type=task.get('type') or 'task',
                chain=self._chain_label(task.get('chain_id')),
                start=task['col'],
                finish=task['col'] + task['duration'],
                duration=task['duration'],
                realistic_duration=realistic,
                resource_ids=';'.join(names),
                predecessor_ids=format_predecessor_notation(
                    task.get('predecessors') or []),
                url=task.get('url', '') or '',
            ))
        return rows

    def view_network_graph_selected(self):
        """Reports > Network Graph > Selected Tasks."""
        tasks = list(self.controller.selected_tasks or [])
        if not tasks:
            messagebox.showinfo(
                'Network Graph',
                'Turn on Multi-Select and select tasks first.',
                parent=self.controller.root,
            )
            return
        plan = (os.path.basename(self.model.current_file_path)
                if self.model.current_file_path else 'Untitled plan')
        plural = 's' if len(tasks) != 1 else ''
        self._open_network_graph(
            tasks, f'{len(tasks)} selected task{plural} — {plan}')

    def view_network_graph_project(self):
        """Reports > Network Graph > Project..."""
        project = self._select_project('Network Graph')
        if not project:
            return
        tasks = [t for t in self.model.tasks
                 if t.get('project_id') == project['id']]
        if not tasks:
            messagebox.showinfo(
                'Network Graph',
                f"Project '{project['name']}' has no tasks.",
                parent=self.controller.root,
            )
            return
        self._open_network_graph(tasks, project['name'])

    def _open_network_graph(self, tasks, title):
        """Render to a temp file, open it in the browser, and note the path
        in the (transient) status message."""
        from ccpm_scheduler import Schedule, render_network_html

        html = render_network_html(
            Schedule(rows=self.build_network_report_rows(tasks)), title=title)
        fd, path = tempfile.mkstemp(prefix='our-planner-network-',
                                    suffix='.html')
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(html)
        webbrowser.open('file://' + path)
        status = getattr(self.controller, 'filter_status', None)
        if status is not None and hasattr(status, 'config'):
            status.config(text=f'Network graph opened in browser: {path}')
        return path
