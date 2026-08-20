import datetime
import os
import tempfile
import tkinter as tk
import webbrowser
from tkinter import font as tkfont
from tkinter import ttk, messagebox

from src.model.dependency_notation import format_predecessor_notation
from src.operations.task_operations import OptionSelectDialog
from src.utils.tk_helpers import add_resize_handle, mnemonic


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
        dialog.title(f'Full-Kit Readiness: {project["name"]}')
        dialog.transient(self.controller.root)
        dialog.grab_set()
        dialog.geometry('480x420')

        frame = tk.Frame(dialog, padx=10, pady=10)
        frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            frame,
            text=f'Full-Kit Readiness: {project["name"]}',
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
                    tk.END, f'[{status}] {planned_start} - {task["description"]}'
                )

        tk.Button(frame, text='Close', command=dialog.destroy).pack(pady=(10, 0))

        add_resize_handle(dialog)

    # ---- Status Update Log report ----------------------------------------
    # The root-cause counterpart to Full-Kit Readiness: every Record
    # Remaining Duration update (reason/note or not), for periodic review
    # of *why* a plan is deviating, not just that it is.

    def compute_status_update_log(self, project) -> tuple[list, int]:
        """The extractor half - separated from the dialog (the renderer
        half) so the underlying data can be tested without a real Tk root.
        Returns (entries_sorted_oldest_first, with_reason_or_note_count),
        scoped to `project` and whatever filters are currently active on
        the Filter menu (same convention as compute_fullkit_readiness)."""
        filtered = self.controller.tag_ops.get_filtered_tasks()
        tasks = [t for t in filtered if t.get('project_id') == project['id']]

        entries = []
        for task in tasks:
            for record in task.get('remaining_duration_history', []):
                entry = {
                    'date': record['date'],
                    'task_id': task['task_id'],
                    'task_description': task['description'],
                    'remaining_duration': record['remaining_duration'],
                }
                task_url = task.get('url')
                if task_url and isinstance(task_url, str) and task_url.strip():
                    entry['task_url'] = task_url
                if record.get('reason'):
                    entry['reason'] = record['reason']
                if record.get('note'):
                    entry['note'] = record['note']
                entries.append(entry)

        entries.sort(key=lambda e: e['date'])
        with_reason_or_note = sum(
            1 for e in entries if e.get('reason') or e.get('note')
        )
        return entries, with_reason_or_note

    def view_status_update_log(self, project=None):
        """Every Record Remaining Duration update for a project (not just
        the ones with a reason/note - the point is reviewing the complete
        record to spot patterns, e.g. "most of our buffer consumption is
        Waiting for Resource"), scoped by whatever's currently active on
        the Filter menu, same as Full-Kit Readiness."""
        if project is None:
            project = self._select_project('Status Update Log')
            if project is None:
                return

        entries, with_reason_or_note = self.compute_status_update_log(project)

        dialog = tk.Toplevel(self.controller.root)
        dialog.title(f'Status Update Log: {project["name"]}')
        dialog.transient(self.controller.root)
        dialog.grab_set()
        dialog.bind('<Escape>', lambda e: dialog.destroy())
        dialog.geometry('560x520')

        frame = tk.Frame(dialog, padx=10, pady=10)
        frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            frame,
            text=f'Status Update Log: {project["name"]}',
            font=('Arial', 10, 'bold'),
            wraplength=520,
        ).pack(fill=tk.X, pady=(0, 10))

        if self.controller.tag_ops.has_active_filters():
            tk.Label(
                frame,
                text='(Scoped to the currently active Filter menu selection)',
                font=('Arial', 8, 'italic'),
                fg='gray',
            ).pack(anchor='w', pady=(0, 5))

        summary = tk.Label(
            frame,
            text=(
                f'{len(entries)} status update(s) recorded, '
                f'{with_reason_or_note} with a reason/note'
            ),
        )
        summary.pack(anchor='w', pady=(0, 5))

        only_annotated_var = tk.BooleanVar(value=False)

        list_frame = tk.Frame(frame)
        list_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        listbox = tk.Listbox(
            list_frame, yscrollcommand=scrollbar.set, exportselection=False
        )
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=listbox.yview)

        detail = tk.Label(frame, text='', anchor='w', justify=tk.LEFT, wraplength=520)

        # The task's URL - the link to wherever that task's team is meant to
        # collaborate on interventions - is shown here rather than crammed
        # onto the list line: it's per-task (not per-update), so most
        # consecutive entries for the same task would repeat it verbatim.
        task_url_label = tk.Label(
            frame, text='', anchor='w', justify=tk.LEFT, wraplength=520, fg='gray'
        )
        current_task_url: dict = {'value': None}

        def open_task_page():
            if current_task_url['value']:
                webbrowser.open(current_task_url['value'])

        # Rebuilt on toggle rather than filtered in place, matching the
        # Fever Charts "Show Status Update Reasons/Notes" toggle's pattern
        # - the list contents shown here always mirror `visible` exactly,
        # so index-based lookups from a click can't drift out of sync.
        visible: list = []

        def on_select(event=None):
            selected = listbox.curselection()
            if not selected:
                return
            entry = visible[selected[0]]
            detail.config(text=entry.get('note') or '(no note)')
            task_url = entry.get('task_url')
            current_task_url['value'] = task_url
            if task_url:
                task_url_label.config(text=f'Task page: {task_url}', fg='blue')
                open_page_button.config(state=tk.NORMAL)
            else:
                task_url_label.config(text='Task page: (none)', fg='gray')
                open_page_button.config(state=tk.DISABLED)

        def rebuild():
            visible.clear()
            visible.extend(
                e
                for e in entries
                if not only_annotated_var.get() or e.get('reason') or e.get('note')
            )
            listbox.delete(0, tk.END)
            if not visible:
                listbox.insert(tk.END, 'No matching status updates.')
                detail.config(text='')
                task_url_label.config(text='')
                current_task_url['value'] = None
                open_page_button.config(state=tk.DISABLED)
                return
            for entry in visible:
                date = datetime.datetime.fromisoformat(entry['date']).strftime(
                    '%Y-%m-%d'
                )
                line = (
                    f'{date}  {entry["task_description"]}: '
                    f'{entry["remaining_duration"]}d remaining'
                )
                if entry.get('reason'):
                    line += f'  —  {entry["reason"]}'
                listbox.insert(tk.END, line)
            listbox.selection_set(tk.END)
            on_select()

        listbox.bind('<<ListboxSelect>>', on_select)

        only_annotated_check = tk.Checkbutton(
            frame,
            text='Only show updates with a reason or note',
            variable=only_annotated_var,
            underline=mnemonic('Only show updates with a reason or note', 'Only'),
            command=rebuild,
        )
        only_annotated_check.pack(anchor='w', pady=(5, 5))
        dialog.bind(
            '<Alt-o>',
            lambda e: (
                only_annotated_var.set(not only_annotated_var.get()),
                rebuild(),
            ),
        )

        detail.pack(anchor='w', fill=tk.X, pady=(5, 0))
        task_url_label.pack(anchor='w', fill=tk.X, pady=(0, 5))

        button_frame = tk.Frame(frame)
        button_frame.pack(pady=(10, 0))

        download_button = tk.Button(
            button_frame,
            text='Download Data (CSV)...',
            underline=mnemonic('Download Data (CSV)...', 'Download'),
            command=lambda: self.controller.export_ops.export_status_update_log(
                project=project
            ),
        )
        download_button.pack(side=tk.LEFT, padx=5)
        download_button.bind('<Return>', lambda e: download_button.invoke())
        dialog.bind(
            '<Alt-d>',
            lambda e: self.controller.export_ops.export_status_update_log(
                project=project
            ),
        )

        open_page_button = tk.Button(
            button_frame,
            text='Open Task Page',
            underline=mnemonic('Open Task Page', 'Page'),
            command=open_task_page,
            state=tk.DISABLED,
        )
        open_page_button.pack(side=tk.LEFT, padx=5)
        open_page_button.bind(
            '<Return>',
            lambda e: (
                open_page_button.invoke()
                if str(open_page_button['state']) != tk.DISABLED
                else None
            ),
        )
        dialog.bind('<Alt-p>', lambda e: open_task_page())

        close_button = tk.Button(
            button_frame,
            text='Close',
            underline=mnemonic('Close', 'Close'),
            command=dialog.destroy,
        )
        close_button.pack(side=tk.LEFT, padx=5)
        close_button.bind('<Return>', lambda e: dialog.destroy())
        dialog.bind('<Alt-c>', lambda e: dialog.destroy())

        rebuild()

        add_resize_handle(dialog)

    # ---- Resource Over-Allocation report ---------------------------------
    # Unlike Full-Kit Readiness/Status Update Log, this is deliberately NOT
    # project-scoped - a resource's real demand sums every project plus any
    # never-CCPM-scheduled backlog work. Scoped instead by the resource
    # grid's own Load Scope control (All tasks / Filtered tasks), the same
    # question the grid itself is already answering.

    def compute_resource_overallocations(self):
        """The extractor half of the By Resource view - see
        compute_tag_overallocations for the By Tag/role counterpart."""
        tasks = None
        if self.controller.tag_ops.resource_load_scope == 'filtered':
            tasks = self.controller.tag_ops.get_filtered_tasks()
        return self.model.find_resource_overallocations(tasks=tasks)

    def compute_tag_overallocations(self):
        """The extractor half of the By Tag/role view."""
        tasks = None
        if self.controller.tag_ops.resource_load_scope == 'filtered':
            tasks = self.controller.tag_ops.get_filtered_tasks()
        return self.model.find_tag_overallocations(tasks=tasks)

    def _merge_overallocation_runs(self, findings):
        """Collapse consecutive overloaded days for the same (kind, key)
        into one display row - a pure rendering concern, the model layer
        keeps one finding per exact day. Each merged row reports the
        single worst (highest overload_pct) day in its run, since load/
        capacity can vary day to day within a run. Sorted worst-first."""
        by_key: dict[tuple, list] = {}
        for finding in findings:
            by_key.setdefault((finding['kind'], finding['key']), []).append(finding)

        rows = []
        for (kind, key), items in by_key.items():
            items.sort(key=lambda f: f['day'])
            run = [items[0]]
            for finding in items[1:]:
                if finding['day'] == run[-1]['day'] + 1:
                    run.append(finding)
                else:
                    rows.append(self._summarize_overallocation_run(kind, key, run))
                    run = [finding]
            rows.append(self._summarize_overallocation_run(kind, key, run))

        rows.sort(key=lambda r: r['overload_pct'], reverse=True)
        return rows

    def _summarize_overallocation_run(self, kind, key, run):
        peak = max(run, key=lambda f: f['overload_pct'])
        start_date = run[0]['date'][:10]
        end_date = run[-1]['date'][:10]
        date_range = (
            start_date if start_date == end_date else f'{start_date} to {end_date}'
        )
        return {
            'kind': kind,
            'key': key,
            'label': peak['label'],
            'date_range': date_range,
            'peak_day': peak['day'],
            'load': peak['load'],
            'capacity': peak['capacity'],
            'overload_pct': peak['overload_pct'],
        }

    def view_resource_overallocation_report(self):
        """Findings the resource grid's own colors can't scale to
        spotting once there are 20-30 rows to scan, plus a role/tag
        aggregate view no single resource row can show at all (three
        developers each individually under capacity, but the role as a
        whole isn't). Selecting a finding drills down to the specific
        tasks causing it, each flagged Critical/Non-Critical/Unscheduled
        (its chain's is_critical, or "no chain yet" for work never run
        through CCPM scheduling) - a non-critical/feeding-chain task
        already has buffer slack to absorb an overload; a critical one
        doesn't."""
        dialog = tk.Toplevel(self.controller.root)
        dialog.title('Resource Over-Allocation')
        dialog.transient(self.controller.root)
        dialog.grab_set()
        dialog.bind('<Escape>', lambda e: dialog.destroy())
        # No fixed pixel geometry (a guessed width/height, like rowheight
        # and the column widths above, goes stale the moment the font
        # doesn't match what was guessed for) - width comes from the
        # Treeview's own measured column widths below, height from its
        # `height=` (a row COUNT, already font-scale-safe) plus
        # add_resize_handle's measured minsize at the end of this method.

        frame = tk.Frame(dialog, padx=10, pady=10)
        frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            frame,
            text='Resource Over-Allocation',
            font=('Arial', 10, 'bold'),
        ).pack(fill=tk.X, pady=(0, 10))

        if self.controller.tag_ops.resource_load_scope == 'filtered':
            tk.Label(
                frame,
                text='(Scoped to Filtered tasks - matching the resource '
                "grid's Load Scope control)",
                font=('Arial', 8, 'italic'),
                fg='gray',
            ).pack(anchor='w', pady=(0, 5))

        mode_frame = tk.Frame(frame)
        mode_frame.pack(fill=tk.X, pady=(0, 5))
        tk.Label(mode_frame, text='View:').pack(side=tk.LEFT)
        mode_var = tk.StringVar(value='By Resource')
        mode_combo = ttk.Combobox(
            mode_frame,
            textvariable=mode_var,
            state='readonly',
            width=14,
            values=['By Resource', 'By Tag'],
        )
        mode_combo.pack(side=tk.LEFT, padx=5)

        summary_label = tk.Label(frame, text='')
        summary_label.pack(anchor='w', pady=(5, 5))

        tree_frame = tk.Frame(frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(tree_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # ttk.Treeview's built-in row height is a small theme default that
        # has no idea what font it's actually about to render (unlike
        # tk.Listbox, which always sizes its own rows off its own font) -
        # on a system with a large TkDefaultFont (HiDPI/accessibility
        # scaling), that leaves each row shorter than the text inside it,
        # so consecutive rows visually overlap. Measured off the real font
        # in use, not a guessed constant, so it stays correct regardless of
        # this system's font/DPI settings - the same "measured, so font/
        # theme-proof" approach add_resize_handle already uses.
        row_height = tkfont.nametofont('TkDefaultFont').metrics('linespace') + 6
        style = ttk.Style()
        style.configure('ResourceOverallocation.Treeview', rowheight=row_height)

        tree = ttk.Treeview(
            tree_frame,
            columns=('detail', 'load_capacity', 'overload'),
            yscrollcommand=scrollbar.set,
            style='ResourceOverallocation.Treeview',
            height=14,  # rows, not pixels - already font-scale-safe
        )
        tree.heading('#0', text='Resource / Task')
        tree.heading('detail', text='Detail')
        tree.heading('load_capacity', text='Load / Capacity')
        tree.heading('overload', text='Overload %')

        # Same font-measurement problem as rowheight above, sideways:
        # fixed pixel column widths guessed for a small font truncate
        # both headers and content on a large one. Measured against
        # realistic sample text (the longest a column normally holds)
        # instead of guessed, for the same reason.
        default_font = tkfont.nametofont('TkDefaultFont')

        def col_width(*sample_texts):
            return max(default_font.measure(t) for t in sample_texts) + 20

        tree_col_width = col_width(
            'Resource / Task', 'Customer Portal Refresh', '  ↳ Prepare audit evidence'
        )
        detail_col_width = col_width(
            'Detail', 'Non-Critical · alloc 1.0 · Fatima Al-Sayed'
        )
        load_capacity_col_width = col_width('Load / Capacity', '99.9 / 99.9')
        overload_col_width = col_width('Overload %', '999%')

        tree.column('#0', width=tree_col_width)
        tree.column('detail', width=detail_col_width)
        tree.column('load_capacity', width=load_capacity_col_width, anchor='e')
        tree.column('overload', width=overload_col_width, anchor='e')
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=tree.yview)

        # item id -> the merged row dict, for the lazy drill-down below.
        row_by_item: dict[str, dict] = {}
        # Every row starts with one empty placeholder child (below) so it
        # shows an expand arrow before being drilled into - that means
        # tree.get_children(item_id) is truthy even when unpopulated, so
        # "already populated" has to be tracked separately.
        populated_items: set[str] = set()

        def populate_children(item_id):
            if item_id in populated_items:
                return
            populated_items.add(item_id)
            tree.delete(*tree.get_children(item_id))  # drop the placeholder
            row = row_by_item[item_id]
            contributing = self.model.get_contributing_tasks(
                row['kind'], row['key'], row['peak_day']
            )
            for task_info in contributing:
                if task_info['is_critical'] is True:
                    status = 'Critical'
                elif task_info['is_critical'] is False:
                    status = 'Non-Critical'
                else:
                    status = 'Unscheduled'
                detail = f'{status} · alloc {task_info["allocation"]}'
                if row['kind'] == 'tag':
                    detail += f' · {task_info["resource_name"]}'
                tree.insert(
                    item_id,
                    tk.END,
                    text=f'  ↳ {task_info["description"]}',
                    values=(detail, '', ''),
                )

        def on_open(event=None):
            item_id = tree.focus()
            if item_id:
                populate_children(item_id)

        tree.bind('<<TreeviewOpen>>', on_open)

        def rebuild():
            tree.delete(*tree.get_children())
            row_by_item.clear()
            populated_items.clear()
            findings = (
                self.compute_resource_overallocations()
                if mode_var.get() == 'By Resource'
                else self.compute_tag_overallocations()
            )
            rows = self._merge_overallocation_runs(findings)
            noun = (
                'resource(s)' if mode_var.get() == 'By Resource' else 'tag(s)/role(s)'
            )
            summary_label.config(text=f'{len(rows)} {noun} over capacity')
            for row in rows:
                item_id = tree.insert(
                    '',
                    tk.END,
                    text=row['label'],
                    values=(
                        row['date_range'],
                        f'{row["load"]:.1f} / {row["capacity"]:.1f}',
                        f'{row["overload_pct"] * 100:.0f}%'
                        if row['overload_pct'] != float('inf')
                        else '∞',
                    ),
                )
                row_by_item[item_id] = row
                tree.insert(item_id, tk.END, text='')  # placeholder so it's expandable

        mode_combo.bind('<<ComboboxSelected>>', lambda e: rebuild())

        close_button = tk.Button(
            frame,
            text='Close',
            underline=mnemonic('Close', 'Close'),
            command=dialog.destroy,
        )
        close_button.pack(pady=(10, 0))
        close_button.bind('<Return>', lambda e: dialog.destroy())
        dialog.bind('<Alt-c>', lambda e: dialog.destroy())

        rebuild()

        add_resize_handle(dialog)

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
        for task in sorted(
            tasks, key=lambda t: (t['col'], t['col'] + t['duration'], t['task_id'])
        ):
            names = []
            for rid in task.get('resources') or {}:
                resource = self.model.get_resource_by_id(rid)
                if resource:
                    names.append(resource['name'])
            realistic = task.get('realistic_duration')
            if realistic in (None, '') or realistic == task['duration']:
                realistic = None
            rows.append(
                ScheduleRow(
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
                        task.get('predecessors') or []
                    ),
                    url=task.get('url', '') or '',
                )
            )
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
        plan = (
            os.path.basename(self.model.current_file_path)
            if self.model.current_file_path
            else 'Untitled plan'
        )
        plural = 's' if len(tasks) != 1 else ''
        self._open_network_graph(tasks, f'{len(tasks)} selected task{plural} — {plan}')

    def view_network_graph_project(self):
        """Reports > Network Graph > Project..."""
        project = self._select_project('Network Graph')
        if not project:
            return
        tasks = [t for t in self.model.tasks if t.get('project_id') == project['id']]
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
            Schedule(rows=self.build_network_report_rows(tasks)), title=title
        )
        fd, path = tempfile.mkstemp(prefix='our-planner-network-', suffix='.html')
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(html)
        webbrowser.open('file://' + path)
        status = getattr(self.controller, 'filter_status', None)
        if status is not None and hasattr(status, 'config'):
            status.config(text=f'Network graph opened in browser: {path}')
        return path
