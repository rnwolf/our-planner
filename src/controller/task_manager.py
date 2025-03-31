import tkinter as tk

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

        # Base font sizes (at zoom level 1.0)
        self.base_task_font_size = 9  # Base font size for task text
        self.base_tag_font_size = 7  # Base font size for tag text
        self.base_timeline_font_size = 8  # Base font size for timeline text
        self.base_resource_font_size = 8  # Base font size for resource labels

        # Current font sizes (will be scaled with zoom)
        self.task_font_size = self.base_task_font_size
        self.tag_font_size = self.base_tag_font_size
        self.timeline_font_size = self.base_timeline_font_size
        self.resource_font_size = self.base_resource_font_size

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

        # Task selection mode
        self.multi_select_mode = False

        # Create main container frame
        self.main_frame = tk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

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

    def create_status_bar(self):
        """Create a status bar at the bottom of the window."""
        self.status_bar = tk.Frame(self.root, height=25, relief=tk.SUNKEN, bd=1)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # Status message for filters
        self.filter_status = tk.Label(
            self.status_bar, text='No filters active', anchor=tk.W, padx=5
        )
        self.filter_status.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Clear filters button
        self.clear_filters_btn = tk.Button(
            self.status_bar,
            text='Clear All Filters',
            command=self.clear_all_filters,
            state=tk.DISABLED,
        )
        self.clear_filters_btn.pack(side=tk.RIGHT, padx=5, pady=2)

    def clear_all_filters(self):
        """Clear all active filters."""
        self.tag_ops.clear_task_filters()
        self.tag_ops.clear_resource_filters()
        self.update_filter_status()

    def update_filter_status(self):
        """Update the filter status display in the status bar."""
        task_filters = self.tag_ops.task_tag_filters
        resource_filters = self.tag_ops.resource_tag_filters

        if not task_filters and not resource_filters:
            self.filter_status.config(text='No filters active')
            self.clear_filters_btn.config(state=tk.DISABLED)
        else:
            status_text = []
            if task_filters:
                match_type = 'ALL' if self.tag_ops.task_match_all else 'ANY'
                status_text.append(
                    f"Tasks: {match_type} of [{', '.join(task_filters)}]"
                )

            if resource_filters:
                match_type = 'ALL' if self.tag_ops.resource_match_all else 'ANY'
                status_text.append(
                    f"Resources: {match_type} of [{', '.join(resource_filters)}]"
                )

            self.filter_status.config(text=' | '.join(status_text))
            self.clear_filters_btn.config(state=tk.NORMAL)

    def update_view(self):
        """Update all view components to reflect current model state."""
        self.ui.draw_timeline()
        self.ui.draw_task_grid()
        self.ui.draw_resource_grid()
        self.update_resource_loading()
        self.update_filter_status()
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
        x2 = x1 + task['duration'] * self.cell_width
        y2 = y1 + self.task_height
        return x1, y1, x2, y2

    def convert_ui_to_model_coordinates(self, x, y):
        """Convert UI coordinates to model coordinates (row, col)."""
        col = int(x / self.cell_width)
        row = int(y / self.task_height)
        return row, col

    def toggle_multi_select_mode(self):
        """Toggle multiple task selection mode."""
        self.multi_select_mode = not self.multi_select_mode

        # Update cursor to indicate mode
        if self.multi_select_mode:
            self.task_canvas.config(cursor='crosshair')
            self.status_bar.config(
                bg='#ffeecc'
            )  # Light orange background to indicate mode
            self.filter_status.config(
                text='Multi-select mode: ON - Use Ctrl+click to select multiple tasks'
            )
        else:
            self.task_canvas.config(cursor='')
            self.status_bar.config(bg='SystemButtonFace')  # Default background
            self.update_filter_status()  # Reset to standard filter status display

        # Clear selected tasks when disabling multi-select mode
        if not self.multi_select_mode:
            self.selected_tasks = []
            self.ui.remove_task_selections()

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
            self.tag_font_size = max(
                6, int(self.base_tag_font_size * font_scale_factor)
            )
            self.timeline_font_size = max(
                6, int(self.base_timeline_font_size * font_scale_factor)
            )
            self.resource_font_size = max(
                6, int(self.base_resource_font_size * font_scale_factor)
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
        self.tag_font_size = self.base_tag_font_size
        self.timeline_font_size = self.base_timeline_font_size
        self.resource_font_size = self.base_resource_font_size

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
