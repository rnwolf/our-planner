import tkinter as tk
from tkinter import font as tkfont

from src.model import TaskResourceModel
from src.view import UIComponents

# from src.view.menus import HelpMenu, NetworkMenu
from src.operations.file_operations import FileOperations
from src.operations.network_operations import NetworkOperations
from src.operations.tag_operations import TagOperations
from src.operations.task_operations import TaskOperations
from src.operations.export_operations import ExportOperations

from src.utils import colors


class TaskResourceManager:
    """Controller class that connects the model and view components."""

    def __init__(self, root):
        self.root = root
        self.root.title('Task Resource Manager')
        self.root.geometry('1000x600')

        # Initialize the model
        self.model = TaskResourceModel()

        # UI configuration constants
        self.cell_width = 45
        self.task_height = 30
        self.timeline_height = 60
        self.resource_grid_height = 150
        self.task_grid_height = 300
        # The resource panel's ratio/drag-driven ceiling, tracked separately
        # from resource_grid_height (the actual, content-fitted height
        # applied to the widgets) - see UIComponents._fit_resource_pane.
        self.resource_grid_ideal_height = 150

        # Zoom and scaling properties
        self.zoom_level = 1.0  # Default zoom level (no zoom)
        self.min_zoom = 0.5  # Minimum zoom level (zoomed out)
        self.max_zoom = 3.0  # Maximum zoom level (zoomed in)
        self.zoom_step = 0.1  # Zoom increment/decrement per scroll
        self.base_cell_width = 45  # Store the original cell width for scaling
        self.base_task_height = 30  # Base height for rows at zoom level 1.0
        self.base_label_column_width = (
            150  # Base width for left column at zoom level 1.0 (increased from 100)
        )
        self.label_column_width = (
            self.base_label_column_width
        )  # Current width (will be scaled with zoom)

        # Add an attribute to track if the window has been resized to accommodate the notes panel
        self.window_adjusted_for_notes = False

        # Base font sizes (at zoom level 1.0)
        self.base_task_font_size = 9  # Base font size for task text
        self.base_tag_font_size = 7  # Base font size for tag text
        self.base_timeline_font_size = 8  # Base font size for timeline text
        self.base_resource_font_size = 8  # Base font size for resource labels

        # Current font sizes (will be scaled with zoom). Clamped the same
        # way on_zoom/reset_zoom do - this is the app's initial state,
        # before any zoom action has ever run, so without this the raw
        # (unclamped) base values would be what's actually on screen at
        # startup, regardless of any zoom-time fix.
        self.task_font_size = self.base_task_font_size
        self.tag_font_size = self._clamp_tag_font_size(self.base_tag_font_size)
        self.timeline_font_size = self._clamp_timeline_font_size(
            self.base_timeline_font_size
        )
        self.resource_font_size = self._clamp_resource_font_size(
            self.base_resource_font_size
        )

        # Dragging state for resizing panes
        self.dragging_task = None
        self.resizing_pane = False
        self.resize_y = 0
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.resize_edge = None
        self.new_task_in_progress = False
        self.new_task_start = None
        self.rubberband = None
        self.selected_task = None
        self.selected_tasks = []
        self.dragging_connector = False
        self.connector_line = None
        # Marquee-select (Stage 11): an empty-space drag while
        # multi_select_mode is on draws a free selection rectangle instead
        # of creating a new task.
        self.marquee_select_in_progress = False
        self.marquee_start = None

        # Transient hover highlight (canvas item id) drawn directly at the
        # connector/edge being hovered - a substitute for the cursor-shape
        # change in on_task_hover, which doesn't render on every
        # platform/WM. Canvas drawing goes through Tk's own painting, so
        # it's reliable regardless of what's broken about cursor theming.
        self.hover_highlight_id = None

        # Task selection mode
        self.multi_select_mode = False

        # When enabled, moving a task forward will push dependent successor
        # tasks forward too, according to their dependency link type
        self.auto_scheduling_enabled = False

        # Create a horizontal layout frame for main content and notes panel
        self.horizontal_layout_frame = tk.Frame(self.root)
        self.horizontal_layout_frame.pack(fill=tk.BOTH, expand=True)

        # Create main container frame (for timeline, tasks, resources)
        self.main_frame = tk.Frame(self.horizontal_layout_frame)
        self.main_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Note: The notes panel will be packed on the right side of horizontal_layout_frame when shown

        # Initialize canvas references (will be populated by UI component)
        self.timeline_canvas = None
        self.task_canvas = None
        self.timeline_canvas = None
        self.resource_canvas = None
        self.task_label_canvas = None
        self.resource_label_canvas = None
        self.h_scrollbar = None
        self.v_scrollbar = None

        # Initialize handlers
        self.task_ops = TaskOperations(self, self.model)
        self.tag_ops = TagOperations(self, self.model)
        self.ui = UIComponents(self, self.model)
        self.file_ops = FileOperations(self, self.model)
        self.export_ops = ExportOperations(self, self.model)
        self.network_ops = NetworkOperations(self, self.model)

        # Create UI elements
        self.ui = UIComponents(self, self.model)
        self.ui.create_menu_bar()
        self.ui.create_timeline_frame()
        self.ui.create_task_grid_frame()
        self.ui.create_resource_grid_frame()

        # Add status bar for showing filter information
        self.create_status_bar()

        # Create sample tasks in the model
        self.model.create_sample_tasks()

        # After UI creation but before update_view
        self.ui.update_menu_commands()

        # Render initial state
        self.update_view()

    def toggle_notes_panel(self):
        """Toggle the visibility of the notes panel."""
        if not hasattr(self.ui, 'notes_panel_frame'):
            # First time, create the panel and show it
            self.ui.create_notes_panel()
            self.ui.notes_panel_frame.pack(side=tk.RIGHT, fill=tk.Y)
            self.ui.notes_panel_visible = True
            self.ui.update_notes_panel()
            # Force update to ensure proper rendering
            self.root.update_idletasks()
            return

        # If panel exists, toggle its visibility
        if self.ui.notes_panel_visible:
            # Hide the panel
            self.ui.notes_panel_frame.pack_forget()
            self.ui.notes_panel_visible = False
        else:
            # Show the panel
            self.ui.notes_panel_frame.pack(side=tk.RIGHT, fill=tk.Y)
            self.ui.notes_panel_visible = True
            # Update notes display
            self.ui.update_notes_panel()

    def get_notes_for_display(self, task_ids=None):
        """Get notes for the specified tasks, or all tasks if none specified."""
        if task_ids is None or not task_ids:
            # Get notes for all tasks
            task_ids = [task['task_id'] for task in self.model.tasks]

        return self.model.get_all_notes_for_tasks(task_ids)

    def create_status_bar(self):
        """Create a status bar at the bottom of the window."""
        self.status_bar = tk.Frame(self.root, height=25, relief=tk.SUNKEN, bd=1)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        # Remember the platform's actual default background (e.g. "SystemButtonFace"
        # on Windows isn't a valid color name on Linux/macOS) so it can be restored later.
        self.status_bar_default_bg = self.status_bar.cget('bg')

        # Default project display
        self.default_project_status = tk.Label(
            self.status_bar, text='Default Project: None', anchor=tk.W, padx=5
        )
        self.default_project_status.pack(side=tk.LEFT)

        # Hover-state diagnostic - the cursor-change feedback in
        # on_task_hover isn't rendering reliably on this platform/WM at all,
        # confirmed by the user, so this is the actual primary visual
        # signal for what a click-drag will do (connector-link vs
        # edge-resize vs move), not just a debugging aid. Background color
        # is used as a substitute for the missing cursor cue - color
        # rendering goes through Tk's own painting, independent of the
        # platform cursor-theme rendering that isn't working here. Width
        # sized for the longest message ("Hover: Right edge (Task 12) -
        # drag to resize") with a bit of margin.
        self.hover_status = tk.Label(
            self.status_bar, text='Hover: -', anchor=tk.W, padx=5, width=48
        )
        self.hover_status.pack(side=tk.LEFT)
        self.hover_status_default_bg = self.hover_status.cget('bg')

        # Status message for filters
        self.filter_status = tk.Label(
            self.status_bar, text='No filters active', anchor=tk.W, padx=5
        )
        self.filter_status.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Multi-select mode/selection indicator - kept as its own widget
        # rather than sharing filter_status: update_filter_status() runs on
        # every update_view() (i.e. after almost any edit), which would
        # otherwise silently clobber a multi-select message written there.
        # A clickable button (not just a label) in the status bar's bottom
        # right corner, so toggling the mode is a single click to a fixed
        # screen corner rather than navigating the Filter menu each time.
        # Packed before clear_filters_btn so it ends up as the rightmost/
        # corner-most widget - the easiest target to reach with the mouse.
        self.multi_select_status = tk.Button(
            self.status_bar, text='', command=self.toggle_multi_select_mode
        )
        self.multi_select_status.pack(side=tk.RIGHT, padx=5, pady=2)
        self.multi_select_default_bg = self.multi_select_status.cget('bg')

        # Clear filters button
        self.clear_filters_btn = tk.Button(
            self.status_bar,
            text='Clear All Filters',
            command=self.clear_all_filters,
            state=tk.DISABLED,
        )
        self.clear_filters_btn.pack(side=tk.RIGHT, padx=5, pady=2)

        self.update_default_project_status()

    def update_default_project_status(self):
        """Update the default project display in the status bar."""
        default_project = self.model.get_default_project()
        if default_project:
            name = default_project['name']
            phase = default_project['phase'].capitalize()
            text = f'Default Project: {name} ({phase})'
        else:
            text = 'Default Project: None'
        self.default_project_status.config(text=text)

    def clear_all_filters(self):
        """Clear all active filters."""
        self.tag_ops.clear_task_filters()
        self.tag_ops.clear_resource_filters()
        self.update_filter_status()

    def update_filter_status(self):
        """Update the filter status display in the status bar."""
        task_filters = self.tag_ops.task_tag_filters
        resource_filters = self.tag_ops.resource_tag_filters
        project_filters = self.tag_ops.task_project_filters

        if not task_filters and not resource_filters and not project_filters:
            self.filter_status.config(text='No filters active')
            self.clear_filters_btn.config(state=tk.DISABLED)
        else:
            status_text = []
            if task_filters:
                match_type = 'ALL' if self.tag_ops.task_match_all else 'ANY'
                status_text.append(
                    f"Tasks: {match_type} of [{', '.join(task_filters)}]"
                )

            if project_filters:
                names = [
                    p['name'] for p in self.model.projects if p['id'] in project_filters
                ]
                status_text.append(f"Project: {', '.join(names)}")

            if resource_filters:
                match_type = 'ALL' if self.tag_ops.resource_match_all else 'ANY'
                status_text.append(
                    f"Resources: {match_type} of [{', '.join(resource_filters)}]"
                )

            self.filter_status.config(text=' | '.join(status_text))
            self.clear_filters_btn.config(state=tk.NORMAL)

    def update_multi_select_status(self):
        """Keep the multi-select button's label/color in sync with the mode
        and the current selection count. Called from update_view() too (in
        addition to every place selection actually changes) so it can never
        drift out of sync with a redraw the way the old shared-label version
        did. Always shows a state, even when off, since the button is now a
        permanent fixture in the status bar rather than only appearing when
        on - clicking it toggles the mode directly.
        """
        if not self.multi_select_mode:
            self.multi_select_status.config(
                text='Multi-Select: OFF', bg=self.multi_select_default_bg
            )
            return

        count = len(self.selected_tasks)
        if count:
            plural = 's' if count != 1 else ''
            text = f'Multi-Select: ON ({count} task{plural} selected)'
        else:
            text = 'Multi-Select: ON'
        self.multi_select_status.config(text=text, bg='#ffeecc')

    def update_view(self):
        """Update all view components to reflect current model state."""
        self.ui.draw_timeline()
        self.ui.draw_task_grid()
        self.ui.draw_resource_grid()
        self.update_resource_loading()
        self.update_filter_status()
        self.update_multi_select_status()
        self.update_default_project_status()
        self.ui.update_setdate_display()

    def update_resource_loading(self):
        """Calculate resource loading and update display."""
        # Get loading data from model
        resource_loading = self.model.calculate_resource_loading()
        # Pass to UI to display
        self.ui.display_resource_loading(resource_loading)

    def update_window_title(self, file_path=None, show_zoom=False):
        """Update the window title based on current file path and zoom level."""
        import os

        # Base title
        if file_path:
            title = f'Task Resource Manager - {os.path.basename(file_path)}'
        else:
            title = 'Task Resource Manager - New Project'

        # Add zoom info if requested or if not at 100%
        if show_zoom or self.zoom_level != 1.0:
            title += f' (Zoom: {int(self.zoom_level * 100)}%)'

        self.root.title(title)

    def get_task_ui_coordinates(self, task):
        """Convert task data model coordinates to UI coordinates, accounting for dynamic row height."""
        x1 = task['col'] * self.cell_width
        y1 = task['row'] * self.task_height
        width = task['duration'] * self.cell_width
        # A zero (or near-zero) duration task - e.g. a fully-consumed buffer
        # (Stage 7) - would otherwise render as a zero-width box: invisible,
        # and impossible to right-click since the hit-test (x1 < x < x2)
        # can never match. Enforce a small minimum so it still shows up as a
        # thin marker and stays clickable, without changing the underlying
        # `duration` used for scheduling.
        min_width = 6
        if width < min_width:
            width = min_width
        x2 = x1 + width
        y2 = y1 + self.task_height
        return x1, y1, x2, y2

    def connector_hit_radius(self):
        """The task connector dot's radius, scaled with zoom - shared by
        both drawing (`UIComponents.draw_task`) and hit-testing
        (`TaskOperations.on_task_press`/`on_task_hover`) so they can never
        drift apart. They used to compute this independently - drawing
        scaled with zoom while hit-testing stayed a fixed 5px - so at high
        zoom the visibly-drawn dot extended past its own clickable area, on
        top of an already-small 5px target to begin with. Widened
        significantly beyond just matching the two: a real reported click
        at 300% zoom landed 14px from the connector's center - a
        size-matched ~8px radius still wouldn't have covered it, so 5px was
        simply too tight a tolerance for realistic mouse aiming, not just
        inconsistent between drawing and hit-testing.
        """
        return max(8, min(20, 5 * self.zoom_level))

    def convert_ui_to_model_coordinates(self, x, y):
        """Convert UI coordinates to model coordinates (row, col)."""
        col = int(x / self.cell_width)
        row = int(y / self.task_height)
        return row, col

    def toggle_multi_select_mode(self):
        """Toggle multiple task selection mode."""
        self.multi_select_mode = not self.multi_select_mode

        # Update cursor to indicate mode
        self.task_canvas.config(cursor='crosshair' if self.multi_select_mode else '')

        # Clear selected tasks when disabling multi-select mode
        if not self.multi_select_mode:
            self.selected_tasks = []
            self.ui.remove_task_selections()

        self.update_multi_select_status()

    def toggle_auto_scheduling(self):
        """Toggle automatic forward scheduling of dependent successor tasks."""
        self.auto_scheduling_enabled = self.ui.auto_scheduling_var.get()

    def _max_font_size_that_fits(self, ideal_size, min_size, max_pixels, measure_fn):
        """Shrink a font size down from `ideal_size` (never below `min_size`)
        until `measure_fn(candidate_size)` - a pixel measurement from a real
        `tkinter.font.Font` at that size - fits within `max_pixels`. Used to
        clamp the timeline header and resource loading indicator fonts
        against their actual (fixed) row/cell pixel size, rather than
        letting them grow unbounded with zoom and overflow.
        """
        size = ideal_size
        while size > min_size and measure_fn(size) > max_pixels:
            size -= 1
        return max(min_size, size)

    def _clamp_timeline_font_size(self, ideal_size):
        row_height = self.timeline_height / 3
        return self._max_font_size_that_fits(
            ideal_size,
            6,
            row_height,
            lambda size: tkfont.Font(family='Arial', size=size).metrics('linespace'),
        )

    def _clamp_resource_font_size(self, ideal_size):
        # resource_font_size is used for two different things that share
        # one variable: the loading-grid numbers (width-constrained by
        # cell_width) and the resource *name* label (height-constrained by
        # the row height, task_height) - both need to be satisfied. The
        # name-label constraint was missing entirely before, which is why
        # clamping only the loading-grid width didn't stop the resource
        # name text itself from overflowing its row at high zoom.
        size = self._max_font_size_that_fits(
            ideal_size,
            6,
            self.cell_width,
            lambda size: tkfont.Font(family='Arial', size=size).measure('99.9/99.9'),
        )
        # Halved: when a tag is shown, the name occupies the upper half of
        # the row and the tag the lower half (see `draw_resource_grid`/
        # `_clamp_tag_font_size`) - a fixed geometric split, so the name
        # only needs to fit within its own half, independent of whatever
        # size the tag line ends up at.
        size = self._max_font_size_that_fits(
            size,
            6,
            self.task_height / 2,
            lambda size: tkfont.Font(family='Arial', size=size).metrics('linespace'),
        )
        return size

    def _clamp_tag_font_size(self, ideal_size):
        """`tag_font_size` is shared by task tags and resource tags. The
        resource label row is the tighter constraint: when a tag is shown,
        it occupies the lower half of the row (the name takes the upper
        half - see `draw_resource_grid`), a fixed geometric split
        independent of either font's own size, so this only needs to fit
        its own linespace within that half - no position-dependent
        coupling that could let it collide with the name above it.
        """
        return self._max_font_size_that_fits(
            ideal_size,
            6,
            self.task_height / 2,
            lambda size: tkfont.Font(family='Arial', size=size).metrics('linespace'),
        )

    def resource_tag_zone_fits(self):
        """Whether the current row height genuinely has room to show a
        resource's tag line below its name without the two overlapping -
        even the smallest floor font (6pt) can't always fit two stacked
        lines in a very short row (e.g. task_height below ~40px, which
        includes the default 100%-120% zoom range). Showing overlapping,
        garbled text would be worse than simply not showing the tag line
        until there's enough room - `draw_resource_grid` uses this to
        decide whether to draw it at all.
        """
        linespace = tkfont.Font(
            family='Arial', size=self.tag_font_size
        ).metrics('linespace')
        return linespace <= self.task_height / 2

    def on_zoom(self, event):
        """Handle zoom in/out with Ctrl+mouse wheel, ensuring the column under cursor stays fixed
        and scaling fonts, row heights, and label column width appropriately"""
        # Check if Ctrl key is pressed
        if event.state & 0x4:  # 0x4 is the state for Ctrl key
            # Store the old cell width and zoom level for calculations
            old_cell_width = self.cell_width
            old_task_height = self.task_height
            old_label_width = self.label_column_width
            old_zoom_level = self.zoom_level

            # Get the current position in the canvas (accounting for scroll)
            canvas_x = self.task_canvas.canvasx(event.x)
            canvas_y = self.task_canvas.canvasy(event.y)

            # Calculate which column and row are under the mouse cursor
            column_under_cursor = canvas_x / old_cell_width
            row_under_cursor = canvas_y / old_task_height

            # Determine zoom direction
            if event.delta > 0:
                # Zoom in
                self.zoom_level = min(self.max_zoom, self.zoom_level + self.zoom_step)
            else:
                # Zoom out
                self.zoom_level = max(self.min_zoom, self.zoom_level - self.zoom_step)

            # Calculate new sizes based on updated zoom level
            self.cell_width = int(self.base_cell_width * self.zoom_level)
            self.task_height = int(self.base_task_height * self.zoom_level)
            self.label_column_width = int(
                self.base_label_column_width * self.zoom_level
            )

            # Update font sizes based on zoom level
            font_scale_factor = max(1.0, self.zoom_level * 0.8)
            self.task_font_size = max(
                7, int(self.base_task_font_size * font_scale_factor)
            )
            self.tag_font_size = self._clamp_tag_font_size(
                max(6, int(self.base_tag_font_size * font_scale_factor))
            )
            self.timeline_font_size = self._clamp_timeline_font_size(
                max(6, int(self.base_timeline_font_size * font_scale_factor))
            )
            self.resource_font_size = self._clamp_resource_font_size(
                max(6, int(self.base_resource_font_size * font_scale_factor))
            )

            # Update all canvas scrollregions
            self.update_all_scrollregions()

            # Resize the label column frames and canvases
            self.timeline_label_frame.config(width=self.label_column_width)
            self.timeline_label_canvas.config(width=self.label_column_width)
            self.task_label_frame.config(width=self.label_column_width)
            self.task_label_canvas.config(width=self.label_column_width)
            self.resource_label_frame.config(width=self.label_column_width)
            self.resource_label_canvas.config(width=self.label_column_width)

            # Calculate new positions after zoom
            new_column_x = column_under_cursor * self.cell_width
            new_row_y = row_under_cursor * self.task_height

            # Calculate how much the view needs to shift to keep column and row under cursor
            x_view_offset = canvas_x - new_column_x
            y_view_offset = canvas_y - new_row_y

            # Calculate the new horizontal view position (fraction of total width)
            total_width = self.cell_width * self.model.days
            current_left = self.task_canvas.xview()[0] * total_width
            new_left = current_left + x_view_offset
            new_left_fraction = max(0, min(1.0, new_left / total_width))

            # Calculate the new vertical view position (fraction of total height)
            total_height = self.task_height * self.model.max_rows
            current_top = self.task_canvas.yview()[0] * total_height
            new_top = current_top + y_view_offset
            new_top_fraction = max(0, min(1.0, new_top / total_height))

            # Redraw everything with the new sizes
            self.update_view()

            # Apply the new horizontal view position to all canvases
            self.task_canvas.xview_moveto(new_left_fraction)
            self.timeline_canvas.xview_moveto(new_left_fraction)
            self.resource_canvas.xview_moveto(new_left_fraction)

            # Apply the new vertical view position to task and resource canvases
            self.task_canvas.yview_moveto(new_top_fraction)
            self.task_label_canvas.yview_moveto(new_top_fraction)

            # Update resource canvas vertical position if needed
            resource_row_under_cursor = canvas_y / old_task_height
            new_resource_row_y = resource_row_under_cursor * self.task_height
            resource_height = (
                len(self.tag_ops.get_filtered_resources()) * self.task_height
            )
            if resource_height > 0:  # Prevent division by zero
                new_resource_top = (current_top + y_view_offset) * (
                    total_height / resource_height
                )
                new_resource_top_fraction = max(
                    0, min(1.0, new_resource_top / resource_height)
                )
                self.resource_canvas.yview_moveto(new_resource_top_fraction)
                self.resource_label_canvas.yview_moveto(new_resource_top_fraction)

            # Update title to show current zoom level
            self.update_window_title(self.model.current_file_path, show_zoom=True)

    def zoom_via_keyboard(self, direction):
        """Zoom in/out via a keyboard shortcut (`Ctrl-+`/`Ctrl-=`/`Ctrl--`),
        reusing `on_zoom`'s exact logic through a synthetic event - the same
        approach already used for Linux's `Button-4`/`Button-5` scroll
        events. A keyboard shortcut has no mouse position to anchor on, so
        it zooms toward the center of the current viewport instead of
        wherever the cursor happens to be.
        """
        center_x = self.task_canvas.winfo_width() / 2
        center_y = self.task_canvas.winfo_height() / 2
        self.on_zoom(
            type(
                'event',
                (),
                {
                    'delta': 120 if direction > 0 else -120,
                    'x': center_x,
                    'y': center_y,
                    'state': 0x4,  # Ctrl - on_zoom checks this even though
                    # a Ctrl-bound keyboard shortcut already implies it.
                },
            )
        )

    # Add a method to reset zoom to 100%
    def reset_zoom(self):
        """Reset zoom level to 100% and restore default sizes and fonts"""
        # Store current view fractions
        old_cell_width = self.cell_width
        old_task_height = self.task_height
        task_x_view = self.task_canvas.xview()
        task_y_view = self.task_canvas.yview()

        # Reset zoom level
        self.zoom_level = 1.0
        self.cell_width = self.base_cell_width
        self.task_height = self.base_task_height
        self.label_column_width = self.base_label_column_width

        # Reset font sizes to base values
        self.task_font_size = self.base_task_font_size
        self.tag_font_size = self._clamp_tag_font_size(self.base_tag_font_size)
        self.timeline_font_size = self._clamp_timeline_font_size(
            self.base_timeline_font_size
        )
        self.resource_font_size = self._clamp_resource_font_size(
            self.base_resource_font_size
        )

        # Resize the label column frames and canvases
        self.timeline_label_frame.config(width=self.label_column_width)
        self.timeline_label_canvas.config(width=self.label_column_width)
        self.task_label_frame.config(width=self.label_column_width)
        self.task_label_canvas.config(width=self.label_column_width)
        self.resource_label_frame.config(width=self.label_column_width)
        self.resource_label_canvas.config(width=self.label_column_width)

        # Update scrollregions
        self.update_all_scrollregions()

        # Update view
        self.update_view()

        # Calculate and set new view position to maintain proper alignment
        new_x_fraction = task_x_view[0] * (old_cell_width / self.cell_width)
        new_y_fraction = task_y_view[0] * (old_task_height / self.task_height)

        # Apply horizontal position
        self.task_canvas.xview_moveto(new_x_fraction)
        self.timeline_canvas.xview_moveto(new_x_fraction)
        self.resource_canvas.xview_moveto(new_x_fraction)

        # Apply vertical position
        self.task_canvas.yview_moveto(new_y_fraction)
        self.task_label_canvas.yview_moveto(new_y_fraction)

        # Resource canvas needs separate calculation if it has a different structure
        # For now, just reset it to the top
        self.resource_canvas.yview_moveto(0)
        self.resource_label_canvas.yview_moveto(0)

        # Update window title
        self.update_window_title(self.model.current_file_path)

    def scroll_task_grid(self, dx_cells=0, dy_rows=0):
        """Scroll the main task grid by whole cells/rows via arrow keys -
        the scrollbars are thin and fiddly to grab precisely, especially
        once zoomed in. Scrolls by exactly one `cell_width`/`task_height`
        (whatever they currently are at the active zoom level) rather than
        relying on Canvas's own imprecise built-in 'unit' scroll amount.
        """
        if dx_cells:
            total_width = self.cell_width * self.model.days
            current_left = self.task_canvas.xview()[0] * total_width
            new_left = current_left + dx_cells * self.cell_width
            new_fraction = max(0, min(1.0, new_left / total_width))
            self.ui.sync_horizontal_scroll('moveto', new_fraction)

        if dy_rows:
            total_height = self.task_height * self.model.max_rows
            current_top = self.task_canvas.yview()[0] * total_height
            new_top = current_top + dy_rows * self.task_height
            new_fraction = max(0, min(1.0, new_top / total_height))
            self.ui.sync_vertical_scroll('moveto', new_fraction)

    def update_all_scrollregions(self):
        """Update scrollregions for all canvases based on the current zoom level and row height"""
        # Calculate canvas widths and heights
        canvas_width = self.cell_width * self.model.days
        task_canvas_height = self.task_height * self.model.max_rows
        resource_canvas_height = self.task_height * len(
            self.tag_ops.get_filtered_resources()
        )

        # Update timeline canvas scrollregion
        self.timeline_canvas.config(
            scrollregion=(0, 0, canvas_width, self.timeline_height)
        )

        # Update task canvas scrollregion
        self.task_canvas.config(scrollregion=(0, 0, canvas_width, task_canvas_height))

        # Update task label canvas scrollregion
        self.task_label_canvas.config(
            scrollregion=(0, 0, self.label_column_width, task_canvas_height)
        )

        # Update resource canvas scrollregion
        self.resource_canvas.config(
            scrollregion=(0, 0, canvas_width, resource_canvas_height)
        )

        # Update resource label canvas scrollregion
        self.resource_label_canvas.config(
            scrollregion=(0, 0, self.label_column_width, resource_canvas_height)
        )
