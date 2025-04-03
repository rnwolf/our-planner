import tkinter as tk
from tkinter import ttk, simpledialog
import re


class TagsDialog(tk.Toplevel):
    """Dialog for managing tags on tasks or resources."""

    def __init__(self, parent, title, current_tags=None, all_tags=None, on_save=None):
        """
        Initialize tag dialog.

        Args:
            parent: Parent window
            title: Dialog title
            current_tags: List of current tags
            all_tags: List of all tags in the system for autocomplete
            on_save: Callback function to call with new tags list when saved
        """
        super().__init__(parent)
        self.title(title)
        self.transient(parent)
        self.grab_set()

        self.current_tags = current_tags or []
        self.all_tags = all_tags or []
        self.on_save = on_save

        # Position the dialog relative to the parent window
        x = parent.winfo_x() + 50
        y = parent.winfo_y() + 50

        # Increase the default size of the dialog to make buttons visible
        self.geometry(f'500x600+{x}+{y}')

        self.create_widgets()

        # Make dialog modal
        self.wait_visibility()
        self.focus_set()
        self.bind('<Escape>', lambda e: self.destroy())

        # Center the dialog on the parent window
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()
        x = parent.winfo_rootx() + (parent_width - width) // 2
        y = parent.winfo_rooty() + (parent_height - height) // 2
        self.geometry(f'+{x}+{y}')

    def create_widgets(self):
        """Create dialog widgets."""
        main_frame = tk.Frame(self, padx=10, pady=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Current tags section
        tags_frame = tk.Frame(main_frame)
        tags_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        tk.Label(tags_frame, text='Current Tags:', anchor='w').pack(fill=tk.X)

        # Frame for tag buttons
        self.tags_button_frame = tk.Frame(tags_frame)
        self.tags_button_frame.pack(fill=tk.X, pady=5)

        # Scrollable frame for tags with REDUCED HEIGHT (previously was expand=True)
        tag_scroll_frame = tk.Frame(tags_frame)
        tag_scroll_frame.pack(fill=tk.X, pady=5, ipady=40)  # Fixed height with ipady

        scrollbar = ttk.Scrollbar(tag_scroll_frame, orient='vertical')
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.tag_canvas = tk.Canvas(
            tag_scroll_frame,
            yscrollcommand=scrollbar.set,
            highlightthickness=1,
            highlightbackground='gray',
            height=80,  # Set a fixed height to reduce vertical size
        )
        self.tag_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar.config(command=self.tag_canvas.yview)

        self.tag_container = tk.Frame(self.tag_canvas)
        self.tag_canvas_window = self.tag_canvas.create_window(
            (0, 0), window=self.tag_container, anchor='nw'
        )

        # Update scroll region when the tag container changes size
        self.tag_container.bind('<Configure>', self.update_tag_scrollregion)
        self.tag_canvas.bind('<Configure>', self.update_tag_canvas)

        # Input for new tags
        input_frame = tk.Frame(main_frame)
        input_frame.pack(fill=tk.X, pady=(0, 10))

        tk.Label(input_frame, text='Add Tag:', anchor='w').pack(fill=tk.X)

        self.tag_input_var = tk.StringVar()
        self.tag_entry = tk.Entry(input_frame, textvariable=self.tag_input_var)
        self.tag_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.tag_entry.bind('<Return>', self.add_tag)

        # Add button for new tag
        self.add_button = tk.Button(input_frame, text='Add', command=self.add_tag)
        self.add_button.pack(side=tk.LEFT)

        # Suggestions for common tags
        # Suggestions section in the TagsDialog.create_widgets method
        # Replace the entire suggestions section with this improved version

        # Suggestions for common tags
        if self.all_tags:
            suggestions_frame = tk.Frame(main_frame)
            suggestions_frame.pack(fill=tk.X, pady=(0, 10))

            tk.Label(suggestions_frame, text='Suggestions:', anchor='w').pack(fill=tk.X)

            # Create a scrollable frame for suggestions with vertical scrolling
            suggestion_scroll_frame = tk.Frame(suggestions_frame)
            suggestion_scroll_frame.pack(fill=tk.BOTH, expand=True, pady=5)

            # Add vertical scrollbar instead of horizontal
            suggestion_scrollbar = ttk.Scrollbar(
                suggestion_scroll_frame, orient='vertical'
            )
            suggestion_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            suggestion_canvas = tk.Canvas(
                suggestion_scroll_frame,
                height=120,  # Increased height for multiple rows
                highlightthickness=1,
                highlightbackground='gray',
                yscrollcommand=suggestion_scrollbar.set,  # Use vertical scrolling
            )
            suggestion_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            suggestion_scrollbar.config(command=suggestion_canvas.yview)

            suggestion_container = tk.Frame(suggestion_canvas)
            suggestion_canvas_window = suggestion_canvas.create_window(
                (0, 0), window=suggestion_container, anchor='nw'
            )

            # Configure suggestion container to fit the canvas width
            suggestion_canvas.bind(
                '<Configure>', lambda e: suggestion_container.configure(width=e.width)
            )

            # Track the current row and column for placing buttons
            row_frame = tk.Frame(suggestion_container)
            row_frame.pack(fill=tk.X, pady=2)
            col_count = 0
            max_cols = 4  # Number of buttons per row before wrapping

            # Add suggestion buttons in a grid pattern that wraps
            for tag in sorted(self.all_tags):
                if tag not in self.current_tags:
                    # Start a new row if needed
                    if col_count >= max_cols:
                        row_frame = tk.Frame(suggestion_container)
                        row_frame.pack(fill=tk.X, pady=2)
                        col_count = 0

                    # Create and add the button
                    btn = tk.Button(
                        row_frame,
                        text=tag,
                        command=lambda t=tag: self.add_tag_from_suggestion(t),
                    )
                    btn.pack(side=tk.LEFT, padx=2, pady=2, fill=tk.X, expand=True)
                    col_count += 1

            # Update the scroll region when the size changes
            suggestion_container.bind(
                '<Configure>',
                lambda e: suggestion_canvas.configure(
                    scrollregion=suggestion_canvas.bbox('all')
                ),
            )

        # Button frame - increased padding to ensure visibility
        button_frame = tk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(20, 10))

        save_button = tk.Button(button_frame, text='Save', command=self.save_tags)
        save_button.pack(side=tk.RIGHT, padx=5)

        cancel_button = tk.Button(button_frame, text='Cancel', command=self.destroy)
        cancel_button.pack(side=tk.RIGHT, padx=5)

        # Populate with current tags
        self.refresh_tag_display()

        # Set focus to the entry
        self.tag_entry.focus_set()

    def update_tag_scrollregion(self, event=None):
        """Update the scroll region of the tag canvas."""
        self.tag_canvas.configure(scrollregion=self.tag_canvas.bbox('all'))

    def update_tag_canvas(self, event=None):
        """Update the tag canvas when it's resized."""
        # Update the width of the window to match the canvas
        self.tag_canvas.itemconfig(self.tag_canvas_window, width=event.width)

    def refresh_tag_display(self):
        """Refresh the display of current tags."""
        # Clear existing tag widgets
        for widget in self.tag_container.winfo_children():
            widget.destroy()

        # Create a button for each tag
        if not self.current_tags:
            tk.Label(self.tag_container, text='No tags yet', fg='gray').pack(
                anchor='w', padx=5, pady=5
            )
        else:
            # Display tags in rows
            current_row = tk.Frame(self.tag_container)
            current_row.pack(fill=tk.X, pady=2)

            for i, tag in enumerate(sorted(self.current_tags)):
                if i > 0 and i % 3 == 0:  # Create a new row every 3 tags
                    current_row = tk.Frame(self.tag_container)
                    current_row.pack(fill=tk.X, pady=2)

                tag_frame = tk.Frame(
                    current_row,
                    highlightthickness=1,
                    highlightbackground='gray',
                    padx=5,
                    pady=2,
                )
                tag_frame.pack(side=tk.LEFT, padx=2)

                tk.Label(tag_frame, text=tag).pack(side=tk.LEFT, padx=(0, 5))

                remove_btn = tk.Button(
                    tag_frame,
                    text='×',
                    width=1,
                    height=1,
                    command=lambda t=tag: self.remove_tag(t),
                )
                remove_btn.pack(side=tk.LEFT)

        # Update the scroll region
        self.update_tag_scrollregion()

    def add_tag(self, event=None):
        """Add a new tag from the entry field."""
        tag = self.tag_input_var.get().strip()

        if not tag:
            return

        # Validate tag (only letters, numbers, underscore, hyphen, no spaces)
        if not re.match(r'^[\w\-]+$', tag):
            tk.messagebox.showerror(
                'Invalid Tag',
                'Tags can only contain letters, numbers, underscores, and hyphens.',
            )
            return

        if tag not in self.current_tags:
            self.current_tags.append(tag)
            self.refresh_tag_display()

        # Clear input
        self.tag_input_var.set('')

    def add_tag_from_suggestion(self, tag):
        """Add a tag from the suggestions."""
        if tag not in self.current_tags:
            self.current_tags.append(tag)
            self.refresh_tag_display()

    def remove_tag(self, tag):
        """Remove a tag from the list."""
        if tag in self.current_tags:
            self.current_tags.remove(tag)
            self.refresh_tag_display()

    def save_tags(self):
        """Save the tags and close the dialog."""
        if self.on_save:
            self.on_save(self.current_tags)
        self.destroy()


class TagFilterDialog(tk.Toplevel):
    """Dialog for filtering by tags."""

    def __init__(self, parent, title, all_tags=None, on_filter=None):
        """
        Initialize tag filter dialog.

        Args:
            parent: Parent window
            title: Dialog title
            all_tags: List of all tags in the system
            on_filter: Callback function to call with selected tags and match option
        """
        super().__init__(parent)
        self.title(title)
        self.transient(parent)
        self.grab_set()

        self.all_tags = all_tags or []
        self.selected_tags = []
        self.on_filter = on_filter
        self.match_all = tk.BooleanVar(value=False)

        # Position the dialog relative to the parent window
        x = parent.winfo_x() + 50
        y = parent.winfo_y() + 50
        self.geometry(f'350x600+{x}+{y}')

        self.create_widgets()

        # Make dialog modal
        self.wait_visibility()
        self.focus_set()
        self.bind('<Escape>', lambda e: self.destroy())

        # Center the dialog on the parent window
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()
        x = parent.winfo_rootx() + (parent_width - width) // 2
        y = parent.winfo_rooty() + (parent_height - height) // 2
        self.geometry(f'+{x}+{y}')

    def create_widgets(self):
        """Create dialog widgets."""
        main_frame = tk.Frame(self, padx=10, pady=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        tk.Label(main_frame, text='Select tags to filter by:', anchor='w').pack(
            fill=tk.X, pady=(0, 10)
        )

        # Tag selection frame
        selection_frame = tk.Frame(main_frame)
        selection_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Scrollable frame for tag checkboxes
        tag_scroll_frame = tk.Frame(selection_frame)
        tag_scroll_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(tag_scroll_frame, orient='vertical')
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.tag_canvas = tk.Canvas(
            tag_scroll_frame,
            yscrollcommand=scrollbar.set,
            highlightthickness=1,
            highlightbackground='gray',
        )
        self.tag_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar.config(command=self.tag_canvas.yview)

        self.tag_container = tk.Frame(self.tag_canvas)
        self.tag_canvas_window = self.tag_canvas.create_window(
            (0, 0), window=self.tag_container, anchor='nw'
        )

        # Update scroll region when the tag container changes size
        self.tag_container.bind(
            '<Configure>',
            lambda e: self.tag_canvas.configure(
                scrollregion=self.tag_canvas.bbox('all')
            ),
        )
        self.tag_canvas.bind(
            '<Configure>',
            lambda e: self.tag_canvas.itemconfig(self.tag_canvas_window, width=e.width),
        )

        # Create a checkbox for each tag
        self.tag_vars = {}

        if not self.all_tags:
            tk.Label(self.tag_container, text='No tags available', fg='gray').pack(
                anchor='w', padx=5, pady=5
            )
        else:
            for tag in sorted(self.all_tags):
                var = tk.BooleanVar()
                self.tag_vars[tag] = var

                row = tk.Frame(self.tag_container)
                row.pack(fill=tk.X, pady=1)

                cb = tk.Checkbutton(
                    row,
                    text=tag,
                    variable=var,
                    anchor='w',
                    command=self.update_selected_tags,
                )
                cb.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Match option
        match_frame = tk.Frame(main_frame)
        match_frame.pack(fill=tk.X, pady=(0, 10))

        match_cb = tk.Checkbutton(
            match_frame, text='Match all tags (AND logic)', variable=self.match_all
        )
        match_cb.pack(anchor='w')

        help_text = tk.Label(
            match_frame,
            text='Unchecked = Match any tag (OR logic)',
            fg='gray',
            anchor='w',
        )
        help_text.pack(fill=tk.X)

        # Selected tags display
        selected_frame = tk.Frame(main_frame)
        selected_frame.pack(fill=tk.X, pady=(0, 10))

        tk.Label(selected_frame, text='Selected tags:', anchor='w').pack(fill=tk.X)

        self.selected_label = tk.Label(
            selected_frame, text='None', fg='gray', anchor='w'
        )
        self.selected_label.pack(fill=tk.X)

        # Buttons
        button_frame = tk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        filter_button = tk.Button(
            button_frame, text='Apply Filter', command=self.apply_filter
        )
        filter_button.pack(side=tk.RIGHT, padx=5)

        clear_button = tk.Button(
            button_frame, text='Clear Filters', command=self.clear_filters
        )
        clear_button.pack(side=tk.RIGHT, padx=5)

        cancel_button = tk.Button(button_frame, text='Cancel', command=self.destroy)
        cancel_button.pack(side=tk.RIGHT, padx=5)

    def update_selected_tags(self):
        """Update the list of selected tags based on checkboxes."""
        self.selected_tags = []
        for tag, var in self.tag_vars.items():
            if var.get():
                self.selected_tags.append(tag)

        # Update the selected tags label
        if self.selected_tags:
            self.selected_label.config(
                text=', '.join(sorted(self.selected_tags)), fg='black'
            )
        else:
            self.selected_label.config(text='None', fg='gray')

    def apply_filter(self):
        """Apply the filter and close the dialog."""
        if self.on_filter:
            self.on_filter(self.selected_tags, self.match_all.get())
        self.destroy()

    def clear_filters(self):
        """Clear all filters and apply."""
        if self.on_filter:
            self.on_filter([], False)
        self.destroy()


class TagOperations:
    """Handles operations related to tags."""

    def __init__(self, controller, model):
        self.controller = controller
        self.model = model

        # Create tag-related variables
        self.task_tag_filters = []
        self.resource_tag_filters = []
        self.task_match_all = False
        self.resource_match_all = False

    def edit_task_tags(self, task=None):
        """Edit tags for a task."""
        if task is None:
            task = self.controller.selected_task

        if not task:
            return

        # Ensure task has a tags field
        if 'tags' not in task:
            task['tags'] = []

        # Create and show the tags dialog
        TagsDialog(
            self.controller.root,
            'Edit Task Tags',
            current_tags=task['tags'],
            all_tags=self.model.get_all_tags(),
            on_save=lambda tags: self.save_task_tags(task, tags),
        )

    def save_task_tags(self, task, tags):
        """Save tags for a task and update the UI."""
        # Update the model
        self.model.set_task_tags(task['task_id'], tags)

        # Update the UI element if the task is displayed
        task_id = task['task_id']
        if task_id in self.controller.ui.task_ui_elements:
            ui_elements = self.controller.ui.task_ui_elements[task_id]

            # Remove existing tag text if it exists
            if 'tag_text' in ui_elements:
                self.controller.task_canvas.delete(ui_elements['tag_text'])

            # Only add tag text if there are tags and show_tags is enabled
            if tags and self.controller.ui.show_tags_var.get():
                tag_text = ', '.join(tags)
                x1, y1, x2, y2 = (
                    ui_elements['x1'],
                    ui_elements['y1'],
                    ui_elements['x2'],
                    ui_elements['y2'],
                )

                # Create new tag text
                new_tag_id = self.controller.task_canvas.create_text(
                    (x1 + x2) / 2,
                    (y1 + y2) / 2 + 8,
                    text=f'[{tag_text}]',
                    fill='blue',
                    font=('Arial', 7),
                    tags=('task', 'task_tags', f'task_tags_{task_id}'),
                )

                # Update the UI elements dictionary with the new tag text ID
                ui_elements['tag_text'] = new_tag_id

            # Refresh tooltips
            self.controller.ui.add_task_tooltips(task)

        # Refresh the view if we're using tag filters
        if self.task_tag_filters:
            self.controller.update_view()
        else:
            # If not using filters, just update resource loading which might be affected by tags
            self.controller.update_resource_loading()

    def edit_resource_tags(self, resource_id):
        """Edit tags for a resource."""
        if not resource_id:
            return

        resource = self.model.get_resource_by_id(resource_id)
        if not resource:
            return

        # Ensure resource has a tags field
        if 'tags' not in resource:
            resource['tags'] = []

        # Create and show the tags dialog
        TagsDialog(
            self.controller.root,
            f"Edit Resource Tags: {resource['name']}",
            current_tags=resource['tags'],
            all_tags=self.model.get_all_tags(),
            on_save=lambda tags: self.save_resource_tags(resource_id, tags),
        )

    def save_resource_tags(self, resource_id, tags):
        """Save tags for a resource and update the UI."""
        # Update the model
        self.model.set_resource_tags(resource_id, tags)

        # Get the resource's position in the filtered resources list
        resources = self.controller.tag_ops.get_filtered_resources()
        resource_index = None

        for i, resource in enumerate(resources):
            if resource['id'] == resource_id:
                resource_index = i
                break

        if resource_index is not None:
            # Calculate y position
            y = resource_index * self.controller.task_height
            tag_y = y + self.controller.task_height / 2

            # Remove existing tag text if it exists
            self.controller.resource_label_canvas.delete(f'resource_tags_{resource_id}')

            # Only add tag text if there are tags and show_tags is enabled
            if tags and self.controller.ui.show_tags_var.get():
                tag_text = ', '.join(tags)
                tag_id = self.controller.resource_label_canvas.create_text(
                    50,
                    tag_y + 10,
                    text=f'[{tag_text}]',
                    anchor='center',
                    font=('Arial', 7),
                    tags=(f'resource_tags_{resource_id}',),
                )

        # Refresh the view if we're using resource tag filters
        if self.resource_tag_filters:
            self.controller.update_view()
        else:
            # If not using filters, just update resource loading which might be affected by tags
            self.controller.update_resource_loading()

    def filter_tasks_by_tags(self):
        """Open dialog to filter tasks by tags."""
        TagFilterDialog(
            self.controller.root,
            'Filter Tasks by Tags',
            all_tags=self.model.get_all_tags(),
            on_filter=self.apply_task_tag_filter,
        )

    def apply_task_tag_filter(self, tags, match_all):
        """Apply a tag filter to tasks."""
        self.task_tag_filters = tags
        self.task_match_all = match_all

        # Clear multi-selections when filter changes
        self.controller.selected_tasks = []
        self.controller.selected_task = None

        self.controller.update_view()

    def filter_resources_by_tags(self):
        """Open dialog to filter resources by tags."""
        TagFilterDialog(
            self.controller.root,
            'Filter Resources by Tags',
            all_tags=self.model.get_all_tags(),
            on_filter=self.apply_resource_tag_filter,
        )

    def apply_resource_tag_filter(self, tags, match_all):
        """Apply a tag filter to resources."""
        self.resource_tag_filters = tags
        self.resource_match_all = match_all

        # Clear multi-selections when filter changes
        self.controller.selected_tasks = []
        self.controller.selected_task = None

        self.controller.update_view()

    def get_filtered_tasks(self):
        """Get tasks filtered by the current tag filter."""
        if not self.task_tag_filters:
            return self.model.tasks

        return self.model.get_tasks_by_tags(
            self.task_tag_filters, match_all=self.task_match_all
        )

    def get_filtered_resources(self):
        """Get resources filtered by the current tag filter."""
        if not self.resource_tag_filters:
            return self.model.resources

        return self.model.get_resources_by_tags(
            self.resource_tag_filters, match_all=self.resource_match_all
        )

    def clear_task_filters(self):
        """Clear all task filters."""
        self.task_tag_filters = []
        self.task_match_all = False

        # Clear multi-selections when filter changes
        self.controller.selected_tasks = []
        self.controller.selected_task = None

        self.controller.update_view()

    def clear_resource_filters(self):
        """Clear all resource filters."""
        self.resource_tag_filters = []
        self.resource_match_all = False

        # Clear multi-selections when filter changes
        self.controller.selected_tasks = []
        self.controller.selected_task = None

        self.controller.update_view()

    def has_active_filters(self):
        """Check if any filters are active."""
        return bool(self.task_tag_filters or self.resource_tag_filters)

    def select_tasks_by_tag(self):
        """Select all tasks with specific tags."""
        TagFilterDialog(
            self.controller.root,
            'Select Tasks by Tags',
            all_tags=self.model.get_all_tags(),
            on_filter=self.apply_task_selection,
        )

    def apply_task_selection(self, tags, match_all):
        """Apply task selection based on tags."""
        if not tags:
            return

        matching_tasks = self.model.get_tasks_by_tags(tags, match_all=match_all)
        self.controller.selected_tasks = matching_tasks

        # Update the view to show selected tasks
        self.controller.ui.highlight_selected_tasks()
