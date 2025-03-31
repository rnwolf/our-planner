import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import os
import datetime
import tempfile
import subprocess
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, landscape, A3, A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch


class ExportOperations:
    def __init__(self, controller, model):
        self.controller = controller
        self.model = model

    def open_export_dialog(self):
        """Open a dialog to configure export options."""
        dialog = tk.Toplevel(self.controller.root)
        dialog.title("Export Project")
        dialog.transient(self.controller.root)
        dialog.grab_set()

        # Position the dialog
        x = self.controller.root.winfo_rootx() + 50
        y = self.controller.root.winfo_rooty() + 50
        dialog.geometry(f"500x500+{x}+{y}")

        # Main frame with padding
        main_frame = tk.Frame(dialog, padx=20, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        tk.Label(main_frame, text="Export Project", font=("Arial", 14, "bold")).pack(
            anchor="w", pady=(0, 15)
        )

        # Export format selection
        format_frame = tk.Frame(main_frame)
        format_frame.pack(fill=tk.X, pady=5)

        tk.Label(format_frame, text="Export Format:").pack(side=tk.LEFT)

        format_var = tk.StringVar(value="pdf")
        formats = [
            ("PDF Document", "pdf"),
            ("PNG Image", "png"),
            ("CSV Data", "csv"),
            ("HTML Report", "html"),
        ]

        format_menu = ttk.OptionMenu(
            format_frame, format_var, formats[0][1], *[f[1] for f in formats]
        )
        format_menu.pack(side=tk.LEFT, padx=10)

        # Format description
        format_desc = tk.StringVar()
        format_desc.set("PDF: Complete document with timeline, tasks, and resources.")
        format_label = tk.Label(
            main_frame,
            textvariable=format_desc,
            fg="gray",
            justify=tk.LEFT,
            wraplength=450,
        )
        format_label.pack(fill=tk.X, pady=5)

        # Options frame (changes based on selected format)
        options_frame = tk.Frame(main_frame)
        options_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        # PDF Options
        pdf_options_frame = tk.Frame(options_frame)
        pdf_options_frame.pack(fill=tk.BOTH, expand=True)

        # Page size for PDF
        page_size_frame = tk.Frame(pdf_options_frame)
        page_size_frame.pack(fill=tk.X, pady=5)

        tk.Label(page_size_frame, text="Page Size:").pack(side=tk.LEFT)

        page_size_var = tk.StringVar(value="A3")
        page_sizes = ["Letter", "A4", "A3", "A2"]

        page_size_menu = ttk.OptionMenu(
            page_size_frame, page_size_var, page_sizes[2], *page_sizes
        )
        page_size_menu.pack(side=tk.LEFT, padx=10)

        # Orientation
        orientation_frame = tk.Frame(pdf_options_frame)
        orientation_frame.pack(fill=tk.X, pady=5)

        tk.Label(orientation_frame, text="Orientation:").pack(side=tk.LEFT)

        orientation_var = tk.StringVar(value="landscape")

        tk.Radiobutton(
            orientation_frame,
            text="Portrait",
            variable=orientation_var,
            value="portrait",
        ).pack(side=tk.LEFT, padx=10)
        tk.Radiobutton(
            orientation_frame,
            text="Landscape",
            variable=orientation_var,
            value="landscape",
        ).pack(side=tk.LEFT)

        # What to include
        include_frame = tk.Frame(pdf_options_frame)
        include_frame.pack(fill=tk.X, pady=5)

        tk.Label(include_frame, text="Include:").pack(anchor="w")

        include_timeline_var = tk.BooleanVar(value=True)
        include_task_grid_var = tk.BooleanVar(value=True)
        include_resources_var = tk.BooleanVar(value=True)

        tk.Checkbutton(
            include_frame, text="Timeline", variable=include_timeline_var
        ).pack(anchor="w", padx=20)
        tk.Checkbutton(
            include_frame, text="Task Grid", variable=include_task_grid_var
        ).pack(anchor="w", padx=20)
        tk.Checkbutton(
            include_frame, text="Resource Loading", variable=include_resources_var
        ).pack(anchor="w", padx=20)

        # Apply filters
        filter_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            pdf_options_frame,
            text="Apply current filters to export",
            variable=filter_var,
        ).pack(anchor="w", pady=5)

        # Function to update the UI based on the selected format
        def update_format_options(*args):
            selected_format = format_var.get()

            # Clear the options frame
            for widget in options_frame.winfo_children():
                widget.pack_forget()

            if selected_format == "pdf":
                pdf_options_frame.pack(fill=tk.BOTH, expand=True)
                format_desc.set(
                    "PDF: Complete document with timeline, tasks, and resources."
                )
            elif selected_format == "png":
                # PNG options would go here
                format_desc.set("PNG: Export the current view as an image file.")
            elif selected_format == "csv":
                # CSV options would go here
                format_desc.set(
                    "CSV: Export task and resource data in spreadsheet format."
                )
            elif selected_format == "html":
                # HTML options would go here
                format_desc.set(
                    "HTML: Interactive web report with filtering capabilities."
                )

        # Connect format selection to update function
        format_var.trace("w", update_format_options)

        # Buttons
        button_frame = tk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))

        def on_export():
            selected_format = format_var.get()

            if selected_format == "pdf":
                # Get PDF-specific options
                page_size = page_size_var.get()
                orientation = orientation_var.get()
                include_timeline = include_timeline_var.get()
                include_task_grid = include_task_grid_var.get()
                include_resources = include_resources_var.get()
                apply_filters = filter_var.get()

                self.export_to_pdf(
                    page_size=page_size,
                    orientation=orientation,
                    include_timeline=include_timeline,
                    include_task_grid=include_task_grid,
                    include_resources=include_resources,
                    apply_filters=apply_filters,
                )
            elif selected_format == "png":
                self.export_to_image()
            elif selected_format == "csv":
                self.export_to_csv()
            elif selected_format == "html":
                self.export_to_html()

            dialog.destroy()

        tk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(
            side=tk.RIGHT, padx=5
        )
        tk.Button(button_frame, text="Export", command=on_export).pack(
            side=tk.RIGHT, padx=5
        )

        # Make sure dialog is centered
        dialog.update_idletasks()
        width = dialog.winfo_width()
        height = dialog.winfo_height()
        x = (
            self.controller.root.winfo_rootx()
            + (self.controller.root.winfo_width() - width) // 2
        )
        y = (
            self.controller.root.winfo_rooty()
            + (self.controller.root.winfo_height() - height) // 2
        )
        dialog.geometry(f"+{x}+{y}")

    def export_to_pdf(
        self,
        page_size="A3",
        orientation="landscape",
        include_timeline=True,
        include_task_grid=True,
        include_resources=True,
        apply_filters=True,
    ):
        """Export the project to a PDF file."""
        # Ask for file location
        file_path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
            title="Export to PDF",
        )

        if not file_path:
            return False

        try:
            # Determine page size
            if page_size == "Letter":
                pdf_size = letter
            elif page_size == "A4":
                pdf_size = A4
            elif page_size == "A3":
                pdf_size = A3
            else:
                pdf_size = A3  # Default to A3

            # Apply orientation
            if orientation == "landscape":
                pdf_size = landscape(pdf_size)

            # Create document
            doc = SimpleDocTemplate(
                file_path,
                pagesize=pdf_size,
                title=f"Task Resource Plan - {datetime.datetime.now().strftime('%Y-%m-%d')}",
                author="Task Resource Manager",
            )

            # Define styles
            styles = getSampleStyleSheet()
            title_style = styles["Title"]
            heading_style = styles["Heading1"]
            sub_heading_style = styles["Heading2"]
            normal_style = styles["Normal"]

            # Create content
            content = []

            # Add title
            project_name = (
                os.path.basename(self.model.current_file_path)
                if self.model.current_file_path
                else "New Project"
            )
            content.append(
                Paragraph(f"Task Resource Plan: {project_name}", title_style)
            )
            content.append(Spacer(1, 0.25 * inch))

            # Add export date
            content.append(
                Paragraph(
                    f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}",
                    normal_style,
                )
            )

            # Add setdate
            content.append(
                Paragraph(
                    f"Current Plan Date: {self.model.setdate.strftime('%Y-%m-%d')}",
                    normal_style,
                )
            )

            # Add date range
            start_date = self.model.start_date.strftime("%Y-%m-%d")
            end_date = (
                self.model.start_date + datetime.timedelta(days=self.model.days - 1)
            ).strftime("%Y-%m-%d")
            content.append(
                Paragraph(f"Timeline: {start_date} to {end_date}", normal_style)
            )
            content.append(Spacer(1, 0.25 * inch))

            # Add filter info if applicable
            if apply_filters and self.controller.tag_ops.has_active_filters():
                content.append(Paragraph("Applied Filters:", sub_heading_style))

                if self.controller.tag_ops.task_tag_filters:
                    match_type = (
                        "ALL" if self.controller.tag_ops.task_match_all else "ANY"
                    )
                    filter_text = f"Tasks: {match_type} of [{', '.join(self.controller.tag_ops.task_tag_filters)}]"
                    content.append(Paragraph(filter_text, normal_style))

                if self.controller.tag_ops.resource_tag_filters:
                    match_type = (
                        "ALL" if self.controller.tag_ops.resource_match_all else "ANY"
                    )
                    filter_text = f"Resources: {match_type} of [{', '.join(self.controller.tag_ops.resource_tag_filters)}]"
                    content.append(Paragraph(filter_text, normal_style))

                content.append(Spacer(1, 0.25 * inch))

            # Get tasks to include (filtered or all)
            if apply_filters:
                tasks = self.controller.tag_ops.get_filtered_tasks()
                resources = self.controller.tag_ops.get_filtered_resources()
            else:
                tasks = self.model.tasks
                resources = self.model.resources

            # Table of tasks
            if include_task_grid and tasks:
                content.append(Paragraph("Task Schedule", heading_style))
                content.append(Spacer(1, 0.15 * inch))

                # Create task table data
                task_data = [
                    [
                        "ID",
                        "Row",
                        "Description",
                        "Start",
                        "End",
                        "Duration",
                        "Resources",
                        "Predecessors",
                        "Successors",
                        "Tags",
                    ]
                ]

                for task in sorted(tasks, key=lambda t: (t["row"], t["col"])):
                    task_id = task["task_id"]
                    row = task["row"]
                    col = task["col"]
                    description = task["description"]
                    duration = task["duration"]

                    # Calculate dates
                    start_date = self.model.get_date_for_day(col).strftime("%Y-%m-%d")
                    end_date = self.model.get_date_for_day(col + duration - 1).strftime(
                        "%Y-%m-%d"
                    )

                    # Format resources
                    resource_names = []
                    for resource_id_str, allocation in task["resources"].items():
                        resource_id = (
                            int(resource_id_str)
                            if isinstance(resource_id_str, str)
                            else resource_id_str
                        )
                        resource = self.model.get_resource_by_id(resource_id)
                        if resource:
                            resource_names.append(f"{resource['name']} ({allocation})")

                    resources_text = ", ".join(resource_names)

                    # Format predecessors and successors
                    predecessors_text = ", ".join(
                        map(str, task.get("predecessors", []))
                    )
                    successors_text = ", ".join(map(str, task.get("successors", [])))

                    # Format tags
                    tags_text = ", ".join(task.get("tags", []))

                    task_data.append(
                        [
                            task_id,
                            row,
                            description,
                            start_date,
                            end_date,
                            duration,
                            resources_text,
                            predecessors_text,
                            successors_text,
                            tags_text,
                        ]
                    )

                # Create task table
                task_table = Table(task_data, repeatRows=1)
                task_table.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                            ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                            ("FONTSIZE", (0, 0), (-1, 0), 10),
                            ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                            ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                            ("GRID", (0, 0), (-1, -1), 1, colors.black),
                            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                            (
                                "ALIGN",
                                (3, 1),
                                (5, -1),
                                "CENTER",
                            ),  # Center date and duration columns
                        ]
                    )
                )

                content.append(task_table)
                content.append(Spacer(1, 0.25 * inch))

            # Resource loading information
            if include_resources and resources:
                content.append(Paragraph("Resource Loading", heading_style))
                content.append(Spacer(1, 0.15 * inch))

                # Create resource table data
                resource_data = [["ID", "Name", "Tags", "Allocation"]]

                # Calculate resource loading
                resource_loading = self.model.calculate_resource_loading()

                for resource in resources:
                    resource_id = resource["id"]
                    name = resource["name"]
                    tags = ", ".join(resource.get("tags", []))

                    # Calculate total and max allocation
                    total_allocation = sum(resource_loading[resource_id])
                    max_allocation = max(resource_loading[resource_id])
                    capacity = sum(resource["capacity"])

                    # Calculate percent utilization
                    if capacity > 0:
                        utilization = (total_allocation / capacity) * 100
                        utilization_text = (
                            f"{utilization:.1f}% (Max: {max_allocation:.1f})"
                        )
                    else:
                        utilization_text = "N/A"

                    resource_data.append([resource_id, name, tags, utilization_text])

                # Create resource table
                resource_table = Table(resource_data, repeatRows=1)
                resource_table.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                            ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                            ("FONTSIZE", (0, 0), (-1, 0), 10),
                            ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                            ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                            ("GRID", (0, 0), (-1, -1), 1, colors.black),
                            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ]
                    )
                )

                content.append(resource_table)
                content.append(Spacer(1, 0.25 * inch))

            # Build document
            doc.build(content)

            # Show success message
            messagebox.showinfo("Export Successful", f"Project exported to {file_path}")

            # Ask if user wants to open the file
            if messagebox.askyesno(
                "Open File", "Would you like to open the exported PDF file?"
            ):
                try:
                    if os.name == "nt":  # Windows
                        os.startfile(file_path)
                    elif os.name == "posix":  # macOS or Linux
                        subprocess.call(("xdg-open", file_path))
                except Exception as e:
                    messagebox.showwarning(
                        "Could not open file", f"Error opening file: {e}"
                    )

            return True

        except Exception as e:
            messagebox.showerror("Export Error", f"Error exporting to PDF: {e}")
            return False

    # def export_to_image(self):
    #     """Export the current view to an image (PNG)."""
    #     # For a full implementation, we would:
    #     # 1. Create a temporary canvas
    #     # 2. Draw all elements to that canvas
    #     # 3. Save it as a PNG file

    #     messagebox.showinfo(
    #         "Not Implemented", "PNG export will be available in a future update."
    #     )

    def export_to_image(self):
        """Export the current view to an image (PNG)."""
        # Ask for file location
        file_path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[
                ("PNG files", "*.png"),
                ("JPEG files", "*.jpg"),
                ("All files", "*.*"),
            ],
            title="Export to Image",
        )

        if not file_path:
            return False

        try:
            # For this implementation, we'll use PIL to create a screenshot of the canvases
            from PIL import Image, ImageDraw, ImageFont
            import io

            # Calculate the dimensions of the image to create
            timeline_width = self.controller.cell_width * self.model.days
            tasks_height = self.model.max_rows * self.controller.task_height

            # Get filtered resources if filters are active
            resources = self.controller.tag_ops.get_filtered_resources()
            resources_height = len(resources) * self.controller.task_height

            # Add some padding
            padding = 20
            header_height = 60

            # Set up widths and heights
            full_width = (
                timeline_width + self.controller.label_column_width + (padding * 2)
            )

            # Decide what to include based on what's visible in the UI
            include_timeline = True
            include_tasks = True
            include_resources = True

            # Calculate total height
            full_height = header_height + padding

            if include_timeline:
                full_height += self.controller.timeline_height + padding

            if include_tasks:
                full_height += tasks_height + padding

            if include_resources:
                full_height += resources_height + padding

            # Create a new image with white background
            image = Image.new("RGB", (full_width, full_height), "white")
            draw = ImageDraw.Draw(image)

            # Try to load a font
            try:
                font = ImageFont.truetype("arial.ttf", 14)
                title_font = ImageFont.truetype("arial.ttf", 18)
            except IOError:
                # Fallback to default font
                font = ImageFont.load_default()
                title_font = ImageFont.load_default()

            # Draw header with project information
            project_name = (
                os.path.basename(self.model.current_file_path)
                if self.model.current_file_path
                else "New Project"
            )
            export_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

            draw.text(
                (padding, padding),
                f"Task Resource Plan: {project_name}",
                fill="black",
                font=title_font,
            )
            draw.text(
                (padding, padding + 25),
                f"Generated: {export_date}",
                fill="black",
                font=font,
            )
            draw.text(
                (padding + 300, padding + 25),
                f"Current Date: {self.model.setdate.strftime('%Y-%m-%d')}",
                fill="black",
                font=font,
            )

            current_y = header_height + padding

            # Now we'll draw each section of the app

            # 1. Timeline
            if include_timeline:
                # Draw timeline header
                draw.text(
                    (padding, current_y), "Timeline", fill="black", font=title_font
                )
                current_y += 30

                # Setup the coordinate system
                x_offset = padding + self.controller.label_column_width
                y_offset = current_y

                # Draw timeline background
                draw.rectangle(
                    [
                        (x_offset, y_offset),
                        (
                            x_offset + timeline_width,
                            y_offset + self.controller.timeline_height,
                        ),
                    ],
                    fill="#f5f5f5",
                    outline="gray",
                )

                # Draw month headers and day numbers
                # Calculate month positions
                month_ranges = self.model.get_month_ranges()

                for month_range in month_ranges:
                    start_x = month_range["start"] * self.controller.cell_width
                    end_x = (month_range["end"] + 1) * self.controller.cell_width
                    month_center_x = (start_x + end_x) / 2

                    # Draw month background
                    fill_color = (
                        "#f0f0f0" if month_range["start"] % 2 == 0 else "#e0e0e0"
                    )
                    draw.rectangle(
                        [
                            (x_offset + start_x, y_offset),
                            (
                                x_offset + end_x,
                                y_offset + self.controller.timeline_height / 3,
                            ),
                        ],
                        fill=fill_color,
                        outline="gray",
                    )

                    # Draw month label
                    draw.text(
                        (
                            x_offset + month_center_x,
                            y_offset + self.controller.timeline_height / 6,
                        ),
                        month_range["label"],
                        fill="black",
                        font=font,
                        anchor="mm",
                    )

                # Draw day numbers and dates
                for i in range(self.model.days):
                    x = i * self.controller.cell_width
                    date = self.model.get_date_for_day(i)

                    # Draw grid line
                    draw.line(
                        [
                            (x_offset + x, y_offset),
                            (x_offset + x, y_offset + self.controller.timeline_height),
                        ],
                        fill="gray",
                    )

                    # Draw date
                    date_y = y_offset + (self.controller.timeline_height * 2 / 3)
                    draw.text(
                        (x_offset + x + self.controller.cell_width / 2, date_y),
                        f"{date.day}",
                        fill="black",
                        font=font,
                        anchor="mm",
                    )

                    # Draw day number
                    day_y = y_offset + (self.controller.timeline_height * 5 / 6)
                    draw.text(
                        (x_offset + x + self.controller.cell_width / 2, day_y),
                        f"{i+1}",
                        fill="black",
                        font=font,
                        anchor="mm",
                    )

                # Draw the last vertical grid line
                draw.line(
                    [
                        (x_offset + timeline_width, y_offset),
                        (
                            x_offset + timeline_width,
                            y_offset + self.controller.timeline_height,
                        ),
                    ],
                    fill="gray",
                )

                # Draw horizontal dividers
                date_divider_y = y_offset + (self.controller.timeline_height / 3)
                draw.line(
                    [
                        (x_offset, date_divider_y),
                        (x_offset + timeline_width, date_divider_y),
                    ],
                    fill="gray",
                )

                day_divider_y = y_offset + (self.controller.timeline_height * 2 / 3)
                draw.line(
                    [
                        (x_offset, day_divider_y),
                        (x_offset + timeline_width, day_divider_y),
                    ],
                    fill="gray",
                )

                # Update current Y position
                current_y = y_offset + self.controller.timeline_height + padding

            # 2. Task Grid
            if include_tasks:
                # Draw task grid header
                draw.text(
                    (padding, current_y), "Task Grid", fill="black", font=title_font
                )
                current_y += 30

                # Draw task labels on the left
                label_x = padding
                for i in range(self.model.max_rows):
                    row_y = current_y + (i * self.controller.task_height)

                    # Draw row label
                    draw.text(
                        (
                            label_x + self.controller.label_column_width / 2,
                            row_y + self.controller.task_height / 2,
                        ),
                        f"Row {i+1}",
                        fill="black",
                        font=font,
                        anchor="mm",
                    )

                    # Draw horizontal grid line
                    draw.line(
                        [
                            (label_x, row_y),
                            (label_x + self.controller.label_column_width, row_y),
                        ],
                        fill="gray",
                    )

                # Draw the last horizontal line
                draw.line(
                    [
                        (label_x, current_y + tasks_height),
                        (
                            label_x + self.controller.label_column_width,
                            current_y + tasks_height,
                        ),
                    ],
                    fill="gray",
                )

                # Draw vertical line separating labels from grid
                draw.line(
                    [
                        (label_x + self.controller.label_column_width, current_y),
                        (
                            label_x + self.controller.label_column_width,
                            current_y + tasks_height,
                        ),
                    ],
                    fill="gray",
                )

                # Setup grid coordinates
                grid_x = padding + self.controller.label_column_width
                grid_y = current_y

                # Draw task grid background
                draw.rectangle(
                    [
                        (grid_x, grid_y),
                        (grid_x + timeline_width, grid_y + tasks_height),
                    ],
                    fill="white",
                    outline="gray",
                )

                # Draw grid lines
                for i in range(self.model.days + 1):
                    x = grid_x + (i * self.controller.cell_width)
                    draw.line([(x, grid_y), (x, grid_y + tasks_height)], fill="gray")

                for i in range(self.model.max_rows + 1):
                    y = grid_y + (i * self.controller.task_height)
                    draw.line([(grid_x, y), (grid_x + timeline_width, y)], fill="gray")

                # Draw tasks
                tasks = self.controller.tag_ops.get_filtered_tasks()

                for task in tasks:
                    task_id = task["task_id"]
                    row = task["row"]
                    col = task["col"]
                    duration = task["duration"]
                    description = task["description"]

                    # Calculate position
                    task_x = grid_x + (col * self.controller.cell_width)
                    task_y = grid_y + (row * self.controller.task_height)
                    task_width = duration * self.controller.cell_width
                    task_height = self.controller.task_height

                    # Draw task box
                    draw.rectangle(
                        [(task_x, task_y), (task_x + task_width, task_y + task_height)],
                        fill="lightblue",
                        outline="black",
                    )

                    # Draw task text
                    text_x = task_x + (task_width / 2)
                    text_y = task_y + (task_height / 2)

                    draw.text(
                        (text_x, text_y),
                        f"{task_id} - {description}",
                        fill="black",
                        font=font,
                        anchor="mm",
                    )

                    # Draw tags if present
                    if (
                        "tags" in task
                        and task["tags"]
                        and hasattr(self.controller.ui, "show_tags_var")
                        and self.controller.ui.show_tags_var.get()
                    ):
                        tag_text = ", ".join(task["tags"])
                        draw.text(
                            (text_x, text_y + 15),
                            f"[{tag_text}]",
                            fill="blue",
                            font=font,
                            anchor="mm",
                        )

                # Draw dependencies
                for task in tasks:
                    task_id = task["task_id"]

                    # Draw links to successors
                    for successor_id in task["successors"]:
                        successor = self.model.get_task(successor_id)
                        if successor:
                            # Get task coordinates
                            task_x = (
                                grid_x
                                + (task["col"] * self.controller.cell_width)
                                + (task["duration"] * self.controller.cell_width)
                            )
                            task_y = (
                                grid_y
                                + (task["row"] * self.controller.task_height)
                                + (self.controller.task_height / 2)
                            )

                            successor_x = grid_x + (
                                successor["col"] * self.controller.cell_width
                            )
                            successor_y = (
                                grid_y
                                + (successor["row"] * self.controller.task_height)
                                + (self.controller.task_height / 2)
                            )

                            # Draw arrow
                            # Determine color based on dependency direction
                            predecessor_end_date = task["col"] + task["duration"]
                            successor_start_date = successor["col"]

                            if predecessor_end_date > successor_start_date:
                                arrow_color = "red"  # backward dependency
                            else:
                                arrow_color = "blue"  # forward dependency

                            # Draw line
                            if (
                                task["row"] == successor["row"]
                                and task["col"] + task["duration"] == successor["col"]
                            ):
                                # Direct connection, no need to draw arrow
                                pass
                            else:
                                # Draw curved arrow
                                # For simplicity in PIL, we'll just draw straight lines
                                draw.line(
                                    [(task_x, task_y), (successor_x, successor_y)],
                                    fill=arrow_color,
                                    width=2,
                                )

                                # Draw arrowhead
                                arrow_size = 5
                                draw.polygon(
                                    [
                                        (successor_x, successor_y),
                                        (
                                            successor_x - arrow_size,
                                            successor_y - arrow_size,
                                        ),
                                        (
                                            successor_x - arrow_size,
                                            successor_y + arrow_size,
                                        ),
                                    ],
                                    fill=arrow_color,
                                )

                # Update current Y position
                current_y = grid_y + tasks_height + padding

            # 3. Resource Grid
            if include_resources:
                # Draw resource grid header
                draw.text(
                    (padding, current_y),
                    "Resource Loading",
                    fill="black",
                    font=title_font,
                )
                current_y += 30

                # Draw resource labels
                label_x = padding
                for i, resource in enumerate(resources):
                    row_y = current_y + (i * self.controller.task_height)

                    # Draw resource name
                    draw.text(
                        (
                            label_x + self.controller.label_column_width / 2,
                            row_y + self.controller.task_height / 2,
                        ),
                        resource["name"],
                        fill="black",
                        font=font,
                        anchor="mm",
                    )

                    # Draw tags if present
                    if (
                        "tags" in resource
                        and resource["tags"]
                        and hasattr(self.controller.ui, "show_tags_var")
                        and self.controller.ui.show_tags_var.get()
                    ):
                        tag_text = ", ".join(resource["tags"])
                        draw.text(
                            (
                                label_x + self.controller.label_column_width / 2,
                                row_y + self.controller.task_height / 2 + 15,
                            ),
                            f"[{tag_text}]",
                            fill="blue",
                            font=font,
                            anchor="mm",
                        )

                    # Draw horizontal grid line
                    draw.line(
                        [
                            (label_x, row_y),
                            (label_x + self.controller.label_column_width, row_y),
                        ],
                        fill="gray",
                    )

                # Draw the last horizontal line
                draw.line(
                    [
                        (label_x, current_y + resources_height),
                        (
                            label_x + self.controller.label_column_width,
                            current_y + resources_height,
                        ),
                    ],
                    fill="gray",
                )

                # Draw vertical line separating labels from grid
                draw.line(
                    [
                        (label_x + self.controller.label_column_width, current_y),
                        (
                            label_x + self.controller.label_column_width,
                            current_y + resources_height,
                        ),
                    ],
                    fill="gray",
                )

                # Setup grid coordinates
                grid_x = padding + self.controller.label_column_width
                grid_y = current_y

                # Calculate resource loading
                resource_loading = self.model.calculate_resource_loading()

                # Draw resource grid
                for i, resource in enumerate(resources):
                    resource_id = resource["id"]

                    for day in range(self.model.days):
                        # Get resource capacity and loading
                        capacity = resource["capacity"][day]
                        load = resource_loading[resource_id][day]

                        # Calculate usage percentage
                        usage_pct = (load / capacity) if capacity > 0 else float("inf")

                        # Cell coordinates
                        cell_x = grid_x + (day * self.controller.cell_width)
                        cell_y = grid_y + (i * self.controller.task_height)

                        # Choose color based on load vs capacity
                        if usage_pct == 0:  # No usage
                            color = "white"
                        elif usage_pct < 0.8:  # Normal usage (< 80%)
                            # Create a blue shade
                            intensity = min(int(usage_pct * 200), 200)
                            blue_value = 255
                            other_value = 255 - intensity
                            color = f"rgb({other_value},{other_value},{blue_value})"
                        elif usage_pct < 1.0:  # High usage (80-99%)
                            color = "#ffffcc"  # Light yellow
                        else:  # Overloaded (>= 100%)
                            color = "#ffcccc"  # Light red

                        # Draw cell
                        draw.rectangle(
                            [
                                (cell_x, cell_y),
                                (
                                    cell_x + self.controller.cell_width,
                                    cell_y + self.controller.task_height,
                                ),
                            ],
                            fill=color,
                            outline="gray",
                        )

                        # Display load number if there is any loading
                        if load > 0:
                            # Format load to show decimals only if needed
                            load_text = (
                                f"{load:.1f}" if load != int(load) else str(int(load))
                            )

                            # Show as fraction of capacity
                            display_text = f"{load_text}/{capacity}"

                            # Draw text
                            draw.text(
                                (
                                    cell_x + self.controller.cell_width / 2,
                                    cell_y + self.controller.task_height / 2,
                                ),
                                display_text,
                                fill="black",
                                font=font,
                                anchor="mm",
                            )

                # Draw vertical grid lines
                for i in range(self.model.days + 1):
                    x = grid_x + (i * self.controller.cell_width)
                    draw.line(
                        [(x, grid_y), (x, grid_y + resources_height)], fill="gray"
                    )

                # Update current Y position
                current_y = grid_y + resources_height + padding

            # Save the image
            image.save(file_path)

            # Show success message
            messagebox.showinfo("Export Successful", f"Image exported to {file_path}")

            # Ask if user wants to open the file
            if messagebox.askyesno(
                "Open File", "Would you like to open the exported image file?"
            ):
                try:
                    if os.name == "nt":  # Windows
                        os.startfile(file_path)
                    elif os.name == "posix":  # macOS or Linux
                        subprocess.call(("xdg-open", file_path))
                except Exception as e:
                    messagebox.showwarning(
                        "Could not open file", f"Error opening file: {e}"
                    )

            return True

        except ImportError:
            messagebox.showerror(
                "Export Error",
                "Could not export to image. Please install the Pillow library (pip install Pillow).",
            )
            return False
        except Exception as e:
            messagebox.showerror("Export Error", f"Error exporting to image: {e}")
            return False

    # def export_to_csv(self):
    #     """Export task and resource data to CSV."""
    #     # For a full implementation, we would:
    #     # 1. Create CSV data for tasks and resources
    #     # 2. Save to a file

    #     messagebox.showinfo(
    #         "Not Implemented", "CSV export will be available in a future update."
    #     )

    def export_to_csv(self):
        """Export task and resource data to CSV."""
        # Ask for directory location
        directory_path = filedialog.askdirectory(
            title="Choose Directory for CSV Export"
        )

        if not directory_path:
            return False

        try:
            import csv
            from datetime import datetime, timedelta

            # Get filtered data if filters are active
            tasks = self.controller.tag_ops.get_filtered_tasks()
            resources = self.controller.tag_ops.get_filtered_resources()
            resource_loading = self.model.calculate_resource_loading()

            # Create unique base filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_filename = f"task_resource_export_{timestamp}"

            # 1. Export tasks
            tasks_file = os.path.join(directory_path, f"{base_filename}_tasks.csv")
            with open(tasks_file, "w", newline="", encoding="utf-8") as csvfile:
                # Define the CSV columns
                fieldnames = [
                    "ID",
                    "Row",
                    "Column",
                    "Description",
                    "Start Date",
                    "End Date",
                    "Duration",
                    "Resources",
                    "Resource Allocations",
                    "Predecessors",
                    "Successors",
                    "Tags",
                    "URL",
                ]

                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()

                # Write task data
                for task in tasks:
                    # Calculate dates
                    start_date = self.model.get_date_for_day(task["col"]).strftime(
                        "%Y-%m-%d"
                    )
                    end_date = self.model.get_date_for_day(
                        task["col"] + task["duration"] - 1
                    ).strftime("%Y-%m-%d")

                    # Format resources
                    resource_names = []
                    resource_allocations = []

                    for resource_id_str, allocation in task["resources"].items():
                        resource_id = (
                            int(resource_id_str)
                            if isinstance(resource_id_str, str)
                            else resource_id_str
                        )
                        resource = self.model.get_resource_by_id(resource_id)
                        if resource:
                            resource_names.append(resource["name"])
                            resource_allocations.append(
                                f"{resource['name']}:{allocation}"
                            )

                    # Row to write
                    row = {
                        "ID": task["task_id"],
                        "Row": task["row"],
                        "Column": task["col"],
                        "Description": task["description"],
                        "Start Date": start_date,
                        "End Date": end_date,
                        "Duration": task["duration"],
                        "Resources": ",".join(resource_names),
                        "Resource Allocations": ",".join(resource_allocations),
                        "Predecessors": ",".join(map(str, task["predecessors"]))
                        if "predecessors" in task
                        else "",
                        "Successors": ",".join(map(str, task["successors"]))
                        if "successors" in task
                        else "",
                        "Tags": ",".join(task.get("tags", [])),
                        "URL": task.get("url", ""),
                    }

                    writer.writerow(row)

            # 2. Export resources
            resources_file = os.path.join(
                directory_path, f"{base_filename}_resources.csv"
            )
            with open(resources_file, "w", newline="", encoding="utf-8") as csvfile:
                # Define the CSV columns
                fieldnames = [
                    "ID",
                    "Name",
                    "Tags",
                    "Total Capacity",
                    "Total Loading",
                    "Average Utilization",
                    "Peak Utilization",
                ]

                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()

                # Write resource data
                for resource in resources:
                    resource_id = resource["id"]

                    # Calculate total capacity and loading
                    total_capacity = sum(resource["capacity"])
                    total_loading = sum(resource_loading[resource_id])

                    # Calculate utilization
                    average_utilization = (
                        (total_loading / total_capacity * 100)
                        if total_capacity > 0
                        else 0
                    )

                    # Calculate peak utilization
                    peak_utilization = 0
                    for day in range(self.model.days):
                        capacity = resource["capacity"][day]
                        loading = resource_loading[resource_id][day]

                        if capacity > 0:
                            utilization = (loading / capacity) * 100
                            peak_utilization = max(peak_utilization, utilization)

                    # Row to write
                    row = {
                        "ID": resource_id,
                        "Name": resource["name"],
                        "Tags": ",".join(resource.get("tags", [])),
                        "Total Capacity": total_capacity,
                        "Total Loading": total_loading,
                        "Average Utilization": f"{average_utilization:.2f}%",
                        "Peak Utilization": f"{peak_utilization:.2f}%",
                    }

                    writer.writerow(row)

            # 3. Export daily resource loading
            loading_file = os.path.join(
                directory_path, f"{base_filename}_resource_loading.csv"
            )
            with open(loading_file, "w", newline="", encoding="utf-8") as csvfile:
                # Create header with date columns
                fieldnames = ["Resource ID", "Resource Name"]

                # Add all days as columns
                for day in range(self.model.days):
                    date = self.model.get_date_for_day(day).strftime("%Y-%m-%d")
                    fieldnames.append(f"Loading_{date}")
                    fieldnames.append(f"Capacity_{date}")
                    fieldnames.append(f"Utilization_{date}")

                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()

                # Write resource loading data
                for resource in resources:
                    resource_id = resource["id"]

                    # Start with resource info
                    row = {
                        "Resource ID": resource_id,
                        "Resource Name": resource["name"],
                    }

                    # Add loading for each day
                    for day in range(self.model.days):
                        date = self.model.get_date_for_day(day).strftime("%Y-%m-%d")
                        capacity = resource["capacity"][day]
                        loading = resource_loading[resource_id][day]

                        # Calculate utilization
                        utilization = (loading / capacity * 100) if capacity > 0 else 0

                        row[f"Loading_{date}"] = loading
                        row[f"Capacity_{date}"] = capacity
                        row[f"Utilization_{date}"] = f"{utilization:.2f}%"

                    writer.writerow(row)

            # Show success message
            messagebox.showinfo(
                "Export Successful",
                f"Data exported to:\n{tasks_file}\n{resources_file}\n{loading_file}",
            )

            # Ask if user wants to open the directory
            if messagebox.askyesno(
                "Open Directory", "Would you like to open the export directory?"
            ):
                try:
                    if os.name == "nt":  # Windows
                        os.startfile(directory_path)
                    elif os.name == "posix":  # macOS or Linux
                        subprocess.call(("xdg-open", directory_path))
                except Exception as e:
                    messagebox.showwarning(
                        "Could not open directory", f"Error opening directory: {e}"
                    )

            return True

        except Exception as e:
            messagebox.showerror("Export Error", f"Error exporting to CSV: {e}")
            return False

    # def export_to_html(self):
    #     """Export to an interactive HTML report."""
    #     # For a full implementation, we would:
    #     # 1. Create HTML with embedded JavaScript
    #     # 2. Include task and resource data
    #     # 3. Generate interactive charts

    #     messagebox.showinfo(
    #         "Not Implemented", "HTML export will be available in a future update."
    #     )

    def export_to_html(self):
        """Export to an interactive HTML report."""
        # Ask for file location
        file_path = filedialog.asksaveasfilename(
            defaultextension=".html",
            filetypes=[("HTML files", "*.html"), ("All files", "*.*")],
            title="Export to HTML",
        )

        if not file_path:
            return False

        try:
            # Get data based on filters
            tasks = self.controller.tag_ops.get_filtered_tasks()
            resources = self.controller.tag_ops.get_filtered_resources()
            resource_loading = self.model.calculate_resource_loading()

            # Generate HTML content
            html_content = self._generate_html_report(
                tasks, resources, resource_loading
            )

            # Write HTML file
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(html_content)

            # Show success message
            messagebox.showinfo("Export Successful", f"Project exported to {file_path}")

            # Ask if user wants to open the file
            if messagebox.askyesno(
                "Open File", "Would you like to open the exported HTML file?"
            ):
                try:
                    if os.name == "nt":  # Windows
                        os.startfile(file_path)
                    elif os.name == "posix":  # macOS or Linux
                        subprocess.call(("xdg-open", file_path))
                except Exception as e:
                    messagebox.showwarning(
                        "Could not open file", f"Error opening file: {e}"
                    )

            return True

        except Exception as e:
            messagebox.showerror("Export Error", f"Error exporting to HTML: {e}")
            return False

    def _generate_html_report(self, tasks, resources, resource_loading):
        """Generate the HTML report content."""
        # Get project details
        project_name = (
            os.path.basename(self.model.current_file_path)
            if self.model.current_file_path
            else "New Project"
        )
        export_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        start_date = self.model.start_date.strftime("%Y-%m-%d")
        end_date = (
            self.model.start_date + datetime.timedelta(days=self.model.days - 1)
        ).strftime("%Y-%m-%d")

        # Generate task data as JSON for the timeline
        task_data = []
        for task in tasks:
            task_id = task["task_id"]
            description = task["description"]
            row = task["row"]
            col = task["col"]
            duration = task["duration"]

            # Calculate start and end dates
            start_date_obj = self.model.get_date_for_day(col)
            end_date_obj = self.model.get_date_for_day(col + duration - 1)

            # Format resource allocations
            resource_text = []
            for resource_id_str, allocation in task["resources"].items():
                resource_id = (
                    int(resource_id_str)
                    if isinstance(resource_id_str, str)
                    else resource_id_str
                )
                resource = self.model.get_resource_by_id(resource_id)
                if resource:
                    resource_text.append(f"{resource['name']} ({allocation})")

            # Determine color based on tags
            color = self._get_color_for_tags(task.get("tags", []))

            task_data.append(
                {
                    "id": task_id,
                    "name": description,
                    "row": row,
                    "start": start_date_obj.strftime("%Y-%m-%d"),
                    "end": end_date_obj.strftime("%Y-%m-%d"),
                    "resources": ", ".join(resource_text),
                    "tags": task.get("tags", []),
                    "color": color,
                }
            )

        # Generate resource loading data
        resource_data = []
        for resource in resources:
            resource_id = resource["id"]
            name = resource["name"]

            # Calculate loading by day
            loading_by_day = []
            for day in range(self.model.days):
                date_obj = self.model.get_date_for_day(day)
                date_str = date_obj.strftime("%Y-%m-%d")
                capacity = resource["capacity"][day]
                loading = resource_loading[resource_id][day]

                # Calculate utilization percentage
                utilization = 0 if capacity == 0 else (loading / capacity) * 100

                loading_by_day.append(
                    {
                        "date": date_str,
                        "loading": loading,
                        "capacity": capacity,
                        "utilization": utilization,
                    }
                )

            resource_data.append(
                {
                    "id": resource_id,
                    "name": name,
                    "tags": resource.get("tags", []),
                    "loading": loading_by_day,
                }
            )

        # Generate all unique tags
        all_tags = set()
        for task in tasks:
            for tag in task.get("tags", []):
                all_tags.add(tag)

        for resource in resources:
            for tag in resource.get("tags", []):
                all_tags.add(tag)

        # Convert data to JSON for embedding in the HTML
        import json

        tasks_json = json.dumps(task_data)
        resources_json = json.dumps(resource_data)
        tags_json = json.dumps(list(all_tags))
        setdate_str = self.model.setdate.strftime("%Y-%m-%d")

        # HTML template - JavaScript code needs to be careful with braces since this is inside an f-string
        html = f"""<!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Task Resource Plan: {project_name}</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 1200px;
                margin: 0 auto;
                padding: 20px;
            }}
            header {{
                margin-bottom: 20px;
                border-bottom: 1px solid #eee;
                padding-bottom: 10px;
            }}
            h1, h2, h3 {{
                color: #2c3e50;
            }}
            .info-box {{
                background-color: #f8f9fa;
                border: 1px solid #ddd;
                padding: 15px;
                border-radius: 5px;
                margin-bottom: 20px;
            }}
            .timeline {{
                position: relative;
                background-color: #f5f5f5;
                padding: 20px;
                overflow-x: auto;
                margin-bottom: 30px;
                border-radius: 5px;
            }}
            .timeline-grid {{
                position: relative;
            }}
            .timeline-months {{
                display: flex;
                border-bottom: 1px solid #ddd;
                margin-bottom: 5px;
            }}
            .month {{
                background-color: #e9ecef;
                padding: 5px;
                text-align: center;
                font-weight: bold;
                border-right: 1px solid #ddd;
            }}
            .timeline-days {{
                display: flex;
                border-bottom: 1px solid #ddd;
                margin-bottom: 10px;
            }}
            .day {{
                width: 30px;
                text-align: center;
                padding: 2px 0;
                font-size: 12px;
                border-right: 1px solid #eee;
            }}
            .weekend {{
                background-color: #f8d7da;
            }}
            .today {{
                background-color: #d4edda;
                font-weight: bold;
            }}
            .task-row {{
                position: relative;
                height: 40px;
                border-bottom: 1px solid #eee;
            }}
            .task-bar {{
                position: absolute;
                height: 30px;
                top: 5px;
                border-radius: 3px;
                padding: 5px;
                box-sizing: border-box;
                font-size: 12px;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
                cursor: pointer;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }}
            .task-bar:hover {{
                opacity: 0.9;
                box-shadow: 0 4px 8px rgba(0,0,0,0.15);
            }}
            .task-tooltip {{
                position: absolute;
                background-color: #fff;
                border: 1px solid #ddd;
                padding: 10px;
                border-radius: 4px;
                box-shadow: 0 4px 8px rgba(0,0,0,0.1);
                z-index: 10;
                display: none;
                max-width: 300px;
                font-size: 12px;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin-bottom: 20px;
            }}
            th, td {{
                padding: 10px;
                border: 1px solid #ddd;
                text-align: left;
            }}
            th {{
                background-color: #f5f5f5;
                font-weight: bold;
            }}
            tr:nth-child(even) {{
                background-color: #f9f9f9;
            }}
            .tag {{
                display: inline-block;
                background-color: #e9ecef;
                padding: 2px 8px;
                margin-right: 5px;
                border-radius: 10px;
                font-size: 12px;
                color: #333;
            }}
            .filter-panel {{
                margin-bottom: 20px;
                padding: 10px;
                background-color: #f5f5f5;
                border-radius: 5px;
            }}
            .chart-container {{
                width: 100%;
                height: 250px;
                margin-bottom: 20px;
            }}
            .tab {{
                overflow: hidden;
                border: 1px solid #ccc;
                background-color: #f1f1f1;
                border-radius: 5px 5px 0 0;
            }}
            .tab button {{
                background-color: inherit;
                float: left;
                border: none;
                outline: none;
                cursor: pointer;
                padding: 14px 16px;
                transition: 0.3s;
                font-size: 14px;
            }}
            .tab button:hover {{
                background-color: #ddd;
            }}
            .tab button.active {{
                background-color: #fff;
                border-bottom: 2px solid #007bff;
            }}
            .tabcontent {{
                display: none;
                padding: 20px;
                border: 1px solid #ccc;
                border-top: none;
                animation: fadeEffect 1s;
                border-radius: 0 0 5px 5px;
            }}
            @keyframes fadeEffect {{
                from {{opacity: 0;}}
                to {{opacity: 1;}}
            }}
        </style>
    </head>
    <body>
        <header>
            <h1>Task Resource Plan: {project_name}</h1>
            <div class="info-box">
                <p><strong>Generated:</strong> {export_date}</p>
                <p><strong>Project Period:</strong> {start_date} to {end_date}</p>
                <p><strong>Current Date:</strong> {setdate_str}</p>
            </div>
        </header>

        <div class="tab">
            <button class="tablinks active" onclick="openTab(event, 'Timeline')">Timeline</button>
            <button class="tablinks" onclick="openTab(event, 'Tasks')">Tasks</button>
            <button class="tablinks" onclick="openTab(event, 'Resources')">Resources</button>
        </div>

        <div id="Timeline" class="tabcontent" style="display: block;">
            <div class="filter-panel">
                <h3>Filter by Tag</h3>
                <div id="tag-filters"></div>
                <button onclick="clearFilters()">Clear Filters</button>
            </div>

            <div class="timeline" id="timeline-container">
                <!-- Timeline will be generated by JavaScript -->
            </div>
        </div>

        <div id="Tasks" class="tabcontent">
            <h2>Task List</h2>
            <table id="task-table">
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Description</th>
                        <th>Start Date</th>
                        <th>End Date</th>
                        <th>Duration</th>
                        <th>Resources</th>
                        <th>Tags</th>
                    </tr>
                </thead>
                <tbody>
                    <!-- Task data will be populated by JavaScript -->
                </tbody>
            </table>
        </div>

        <div id="Resources" class="tabcontent">
            <h2>Resource Allocation</h2>
            <table id="resource-table">
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Name</th>
                        <th>Tags</th>
                        <th>Average Utilization</th>
                        <th>Peak Utilization</th>
                    </tr>
                </thead>
                <tbody>
                    <!-- Resource data will be populated by JavaScript -->
                </tbody>
            </table>

            <h3>Resource Loading Charts</h3>
            <div id="resource-charts">
                <!-- Charts will be generated by JavaScript -->
            </div>
        </div>

        <script src="https://cdn.jsdelivr.net/npm/chart.js@3.7.1/dist/chart.min.js"></script>
        <script>
            // Task and resource data from Python
            const taskData = {tasks_json};
            const resourceData = {resources_json};
            const allTags = {tags_json};
            const startDate = new Date('{start_date}');
            const endDate = new Date('{end_date}');
            const currentDate = new Date('{setdate_str}');

            // Filter state
            let activeFilters = [];

            // Initialize on page load
            document.addEventListener('DOMContentLoaded', function() {{
                initializeTimeline();
                populateTaskTable();
                populateResourceTable();
                createResourceCharts();
                initializeTagFilters();
            }});

            // Tab functionality
            function openTab(evt, tabName) {{
                let tabcontent = document.getElementsByClassName("tabcontent");
                for (let i = 0; i < tabcontent.length; i++) {{
                    tabcontent[i].style.display = "none";
                }}

                let tablinks = document.getElementsByClassName("tablinks");
                for (let i = 0; i < tablinks.length; i++) {{
                    tablinks[i].className = tablinks[i].className.replace(" active", "");
                }}

                document.getElementById(tabName).style.display = "block";
                evt.currentTarget.className += " active";
            }}

            // Timeline functions
            function initializeTimeline() {{
                const timelineContainer = document.getElementById('timeline-container');

                // Create timeline grid
                const timelineGrid = document.createElement('div');
                timelineGrid.className = 'timeline-grid';

                // Create months row
                const monthsRow = document.createElement('div');
                monthsRow.className = 'timeline-months';

                // Create days row
                const daysRow = document.createElement('div');
                daysRow.className = 'timeline-days';

                // Calculate the number of days in the timeline
                const dayCount = Math.round((endDate - startDate) / (24 * 60 * 60 * 1000)) + 1;

                // Generate month headers
                let currentMonth = null;
                let monthElement = null;
                let monthWidth = 0;

                for (let i = 0; i < dayCount; i++) {{
                    const date = new Date(startDate);
                    date.setDate(date.getDate() + i);

                    const month = date.toLocaleString('default', {{ month: 'short' }}) + ' ' + date.getFullYear();

                    // Add day cell
                    const dayElement = document.createElement('div');
                    dayElement.className = 'day';

                    const isWeekend = date.getDay() === 0 || date.getDay() === 6;
                    if (isWeekend) {{
                        dayElement.classList.add('weekend');
                    }}

                    const isToday = date.toDateString() === currentDate.toDateString();
                    if (isToday) {{
                        dayElement.classList.add('today');
                    }}

                    dayElement.textContent = date.getDate();
                    daysRow.appendChild(dayElement);

                    // Handle month headers
                    if (month !== currentMonth) {{
                        if (monthElement) {{
                            monthElement.style.width = (monthWidth * 30) + 'px';
                        }}

                        currentMonth = month;
                        monthWidth = 1;

                        monthElement = document.createElement('div');
                        monthElement.className = 'month';
                        monthElement.textContent = month;
                        monthsRow.appendChild(monthElement);
                    }} else {{
                        monthWidth++;
                    }}
                }}

                // Set width of last month
                if (monthElement) {{
                    monthElement.style.width = (monthWidth * 30) + 'px';
                }}

                // Add month and day rows to grid
                timelineGrid.appendChild(monthsRow);
                timelineGrid.appendChild(daysRow);

                // Create task rows
                const tasksByRow = {{}};

                // Group tasks by row
                const filteredTasks = filterTasksByTags(taskData);
                filteredTasks.forEach(task => {{
                    if (!tasksByRow[task.row]) {{
                        tasksByRow[task.row] = [];
                    }}
                    tasksByRow[task.row].push(task);
                }});

                // Create task rows in order
                const rows = Object.keys(tasksByRow).sort((a, b) => parseInt(a) - parseInt(b));

                rows.forEach(rowNum => {{
                    const taskRow = document.createElement('div');
                    taskRow.className = 'task-row';
                    taskRow.setAttribute('data-row', rowNum);

                    // Add tasks to this row
                    tasksByRow[rowNum].forEach(task => {{
                        const taskStart = new Date(task.start);
                        const taskEnd = new Date(task.end);

                        // Calculate position
                        const startDays = Math.round((taskStart - startDate) / (24 * 60 * 60 * 1000));
                        const duration = Math.round((taskEnd - taskStart) / (24 * 60 * 60 * 1000)) + 1;

                        const taskBar = document.createElement('div');
                        taskBar.className = 'task-bar';
                        taskBar.setAttribute('data-id', task.id);
                        taskBar.style.left = (startDays * 30) + 'px';
                        taskBar.style.width = (duration * 30) + 'px';
                        taskBar.style.backgroundColor = task.color || '#6c757d';
                        taskBar.textContent = `${{task.id}} - ${{task.name}}`;

                        // Create tooltip
                        const tooltip = document.createElement('div');
                        tooltip.className = 'task-tooltip';
                        tooltip.innerHTML = `
                            <strong>ID:</strong> ${{task.id}}<br>
                            <strong>Name:</strong> ${{task.name}}<br>
                            <strong>Duration:</strong> ${{duration}} days<br>
                            <strong>Dates:</strong> ${{task.start}} to ${{task.end}}<br>
                            <strong>Resources:</strong> ${{task.resources || 'None'}}<br>
                            <strong>Tags:</strong> ${{task.tags.map(tag => `<span class="tag">${{tag}}</span>`).join(' ') || 'None'}}
                        `;

                        // Show tooltip on hover
                        taskBar.addEventListener('mouseenter', function(e) {{
                            tooltip.style.display = 'block';
                            tooltip.style.left = e.pageX + 'px';
                            tooltip.style.top = e.pageY + 'px';
                        }});

                        taskBar.addEventListener('mousemove', function(e) {{
                            tooltip.style.left = (e.pageX + 10) + 'px';
                            tooltip.style.top = (e.pageY + 10) + 'px';
                        }});

                        taskBar.addEventListener('mouseleave', function() {{
                            tooltip.style.display = 'none';
                        }});

                        taskRow.appendChild(taskBar);
                        document.body.appendChild(tooltip);
                    }});

                    timelineGrid.appendChild(taskRow);
                }});

                timelineContainer.appendChild(timelineGrid);
            }}

            // Filter tasks by selected tags
            function filterTasksByTags(tasks) {{
                if (activeFilters.length === 0) {{
                    return tasks;
                }}

                return tasks.filter(task => {{
                    if (!task.tags || task.tags.length === 0) {{
                        return false;
                    }}

                    // Check if task has any of the active filter tags
                    return task.tags.some(tag => activeFilters.includes(tag));
                }});
            }}

            // Initialize tag filters
            function initializeTagFilters() {{
                const tagFiltersContainer = document.getElementById('tag-filters');

                allTags.forEach(tag => {{
                    const tagElement = document.createElement('span');
                    tagElement.className = 'tag';
                    tagElement.textContent = tag;
                    tagElement.style.cursor = 'pointer';
                    tagElement.style.margin = '5px';

                    tagElement.addEventListener('click', function() {{
                        if (activeFilters.includes(tag)) {{
                            // Remove tag from filters
                            activeFilters = activeFilters.filter(t => t !== tag);
                            tagElement.style.backgroundColor = '#e9ecef';
                        }} else {{
                            // Add tag to filters
                            activeFilters.push(tag);
                            tagElement.style.backgroundColor = '#007bff';
                            tagElement.style.color = 'white';
                        }}

                        // Refresh timeline and tables
                        document.getElementById('timeline-container').innerHTML = '';
                        initializeTimeline();
                        populateTaskTable();
                    }});

                    tagFiltersContainer.appendChild(tagElement);
                }});
            }}

            // Clear active filters
            function clearFilters() {{
                activeFilters = [];

                // Reset tag appearances
                const tags = document.querySelectorAll('#tag-filters .tag');
                tags.forEach(tag => {{
                    tag.style.backgroundColor = '#e9ecef';
                    tag.style.color = '#333';
                }});

                // Refresh timeline and tables
                document.getElementById('timeline-container').innerHTML = '';
                initializeTimeline();
                populateTaskTable();
            }}

            // Populate task table
            function populateTaskTable() {{
                const tableBody = document.querySelector('#task-table tbody');
                tableBody.innerHTML = '';

                const filteredTasks = filterTasksByTags(taskData);

                filteredTasks.forEach(task => {{
                    const row = document.createElement('tr');

                    // ID
                    const idCell = document.createElement('td');
                    idCell.textContent = task.id;
                    row.appendChild(idCell);

                    // Description
                    const descCell = document.createElement('td');
                    descCell.textContent = task.name;
                    row.appendChild(descCell);

                    // Start Date
                    const startCell = document.createElement('td');
                    startCell.textContent = task.start;
                    row.appendChild(startCell);

                    // End Date
                    const endCell = document.createElement('td');
                    endCell.textContent = task.end;
                    row.appendChild(endCell);

                    // Duration
                    const taskStart = new Date(task.start);
                    const taskEnd = new Date(task.end);
                    const duration = Math.round((taskEnd - taskStart) / (24 * 60 * 60 * 1000)) + 1;

                    const durationCell = document.createElement('td');
                    durationCell.textContent = duration + ' days';
                    row.appendChild(durationCell);

                    // Resources
                    const resourcesCell = document.createElement('td');
                    resourcesCell.textContent = task.resources || 'None';
                    row.appendChild(resourcesCell);

                    // Tags
                    const tagsCell = document.createElement('td');
                    if (task.tags && task.tags.length > 0) {{
                        task.tags.forEach(tag => {{
                            const tagSpan = document.createElement('span');
                            tagSpan.className = 'tag';
                            tagSpan.textContent = tag;
                            tagsCell.appendChild(tagSpan);
                        }});
                    }} else {{
                        tagsCell.textContent = 'None';
                    }}
                    row.appendChild(tagsCell);

                    tableBody.appendChild(row);
                }});
            }}

            // Populate resource table
            function populateResourceTable() {{
                const tableBody = document.querySelector('#resource-table tbody');
                tableBody.innerHTML = '';

                resourceData.forEach(resource => {{
                    const row = document.createElement('tr');

                    // ID
                    const idCell = document.createElement('td');
                    idCell.textContent = resource.id;
                    row.appendChild(idCell);

                    // Name
                    const nameCell = document.createElement('td');
                    nameCell.textContent = resource.name;
                    row.appendChild(nameCell);

                    // Tags
                    const tagsCell = document.createElement('td');
                    if (resource.tags && resource.tags.length > 0) {{
                        resource.tags.forEach(tag => {{
                            const tagSpan = document.createElement('span');
                            tagSpan.className = 'tag';
                            tagSpan.textContent = tag;
                            tagsCell.appendChild(tagSpan);
                        }});
                    }} else {{
                        tagsCell.textContent = 'None';
                    }}
                    row.appendChild(tagsCell);

                    // Calculate average utilization
                    let totalUtilization = 0;
                    let maxUtilization = 0;
                    let daysWithLoading = 0;

                    resource.loading.forEach(day => {{
                        if (day.loading > 0) {{
                            totalUtilization += day.utilization;
                            daysWithLoading++;

                            if (day.utilization > maxUtilization) {{
                                maxUtilization = day.utilization;
                            }}
                        }}
                    }});

                    const avgUtilization = daysWithLoading > 0 ? totalUtilization / daysWithLoading : 0;

                    // Average Utilization
                    const avgCell = document.createElement('td');
                    avgCell.textContent = avgUtilization.toFixed(1) + '%';
                    row.appendChild(avgCell);

                    // Peak Utilization
                    const peakCell = document.createElement('td');
                    peakCell.textContent = maxUtilization.toFixed(1) + '%';
                    row.appendChild(peakCell);

                    tableBody.appendChild(row);
                }});
            }}

            // Create resource charts
            function createResourceCharts() {{
                const chartsContainer = document.getElementById('resource-charts');
                chartsContainer.innerHTML = '';

                resourceData.forEach(resource => {{
                    // Create chart container
                    const chartContainer = document.createElement('div');
                    chartContainer.className = 'chart-container';
                    chartContainer.style.position = 'relative';
                    chartContainer.style.height = '200px';
                    chartContainer.style.marginBottom = '30px';

                    // Create canvas for chart
                    const canvas = document.createElement('canvas');
                    canvas.id = 'chart-' + resource.id;
                    chartContainer.appendChild(canvas);

                    chartsContainer.appendChild(chartContainer);

                    // Prepare data for chart
                    const dates = [];
                    const loadingData = [];
                    const capacityData = [];

                    resource.loading.forEach(day => {{
                        dates.push(day.date);
                        loadingData.push(day.loading);
                        capacityData.push(day.capacity);
                    }});

                    // Create chart
                    new Chart(canvas, {{
                        type: 'bar',
                        data: {{
                            labels: dates,
                            datasets: [
                                {{
                                    label: 'Loading',
                                    data: loadingData,
                                    backgroundColor: 'rgba(54, 162, 235, 0.5)',
                                    borderColor: 'rgba(54, 162, 235, 1)',
                                    borderWidth: 1
                                }},
                                {{
                                    label: 'Capacity',
                                    data: capacityData,
                                    type: 'line',
                                    fill: false,
                                    borderColor: 'rgba(255, 99, 132, 1)',
                                    borderWidth: 2,
                                    pointRadius: 0
                                }}
                            ]
                        }},
                        options: {{
                            responsive: true,
                            maintainAspectRatio: false,
                            plugins: {{
                                title: {{
                                    display: true,
                                    text: resource.name + ' Loading',
                                    font: {{
                                        size: 16
                                    }}
                                }},
                                legend: {{
                                    position: 'bottom'
                                }}
                            }},
                            scales: {{
                                x: {{
                                    display: true,
                                    title: {{
                                        display: true,
                                        text: 'Date'
                                    }},
                                    ticks: {{
                                        maxRotation: 90,
                                        minRotation: 90,
                                        autoSkip: true,
                                        maxTicksLimit: 20
                                    }}
                                }},
                                y: {{
                                    display: true,
                                    title: {{
                                        display: true,
                                        text: 'Allocation'
                                    }},
                                    beginAtZero: true
                                }}
                            }}
                        }}
                    }});
                }});
            }}

            // Helper to get color for tags
            function getColorForTags(tags) {{
                if (!tags || tags.length === 0) {{
                    return '#6c757d'; // Default gray
                }}

                // Use the first tag to determine color
                const tag = tags[0];

                // Generate color based on tag name
                let hash = 0;
                for (let i = 0; i < tag.length; i++) {{
                    hash = tag.charCodeAt(i) + ((hash << 5) - hash);
                }}

                const hue = hash % 360;
                return `hsl(${{hue}}, 70%, 60%)`;
            }}
        </script>
    </body>
    </html>"""

        return html

    def _get_color_for_tags(self, tags):
        """Generate a color based on task tags."""
        if not tags:
            return "#6c757d"  # Default gray

        # Use the first tag for the color
        tag = tags[0]

        # Simple hash function to generate consistent colors for the same tag
        hash_value = 0
        for char in tag:
            hash_value = ord(char) + ((hash_value << 5) - hash_value)

        # Convert to RGB
        r = (hash_value & 0xFF0000) >> 16
        g = (hash_value & 0x00FF00) >> 8
        b = hash_value & 0x0000FF

        return f"#{r:02x}{g:02x}{b:02x}"
