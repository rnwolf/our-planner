import tkinter as tk


class DraggableRectangleApp:
    def __init__(self, master):
        self.master = master
        master.title("Draggable and Resizable Rectangle")

        self.canvas = tk.Canvas(master, width=400, height=300, bg="white")
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Create the rectangle
        self.rect_x1, self.rect_y1 = 50, 50
        self.rect_x2, self.rect_y2 = 150, 100
        self.rectangle = self.canvas.create_rectangle(
            self.rect_x1,
            self.rect_y1,
            self.rect_x2,
            self.rect_y2,
            fill="lightblue",
            tags="rect",
        )

        # Bind mouse events
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)

        # Dragging state
        self.dragging = False
        self.resizing_left = False
        self.resizing_right = False
        self.drag_data = {"x": 0, "y": 0}

    def on_click(self, event):
        """Handle mouse click event."""
        item = self.canvas.find_closest(event.x, event.y)
        if "rect" in self.canvas.gettags(item):
            self.dragging = True
            self.drag_data["x"] = event.x
            self.drag_data["y"] = event.y

            # Check if the click is near the left or right edge
            if abs(event.x - self.rect_x1) < 5:
                self.resizing_left = True
            elif abs(event.x - self.rect_x2) < 5:
                self.resizing_right = True
            else:
                self.resizing_left = False
                self.resizing_right = False

    def on_drag(self, event):
        """Handle mouse drag event."""
        if self.dragging:
            if self.resizing_left:
                # Resize from the left
                self.rect_x1 = event.x
            elif self.resizing_right:
                # Resize from the right
                self.rect_x2 = event.x
            else:
                # Move the entire rectangle
                delta_x = event.x - self.drag_data["x"]
                delta_y = event.y - self.drag_data["y"]
                self.rect_x1 += delta_x
                self.rect_x2 += delta_x
                self.rect_y1 += delta_y
                self.rect_y2 += delta_y

            # Update the rectangle's coordinates
            self.canvas.coords(
                self.rectangle, self.rect_x1, self.rect_y1, self.rect_x2, self.rect_y2
            )

            self.drag_data["x"] = event.x
            self.drag_data["y"] = event.y

    def on_release(self, event):
        """Handle mouse release event."""
        self.dragging = False
        self.resizing_left = False
        self.resizing_right = False


if __name__ == "__main__":
    root = tk.Tk()
    app = DraggableRectangleApp(root)
    root.mainloop()
