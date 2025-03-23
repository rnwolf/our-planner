import json
from typing import List, Dict, Any, Optional, Tuple


class TaskResourceModel:
    def __init__(self):
        # Configuration
        self.days = 100
        self.max_rows = 50

        # Resource management with IDs
        self.resource_id_counter = 0
        self.resources = [
            {
                "id": self._get_next_resource_id(),
                "name": "Resource A",
                "capacity": [1.0] * 100,
            },
            {
                "id": self._get_next_resource_id(),
                "name": "Resource B",
                "capacity": [1.0] * 100,
            },
            {
                "id": self._get_next_resource_id(),
                "name": "Resource C",
                "capacity": [1.0] * 100,
            },
            {
                "id": self._get_next_resource_id(),
                "name": "Resource D",
                "capacity": [1.0] * 100,
            },
            {
                "id": self._get_next_resource_id(),
                "name": "Resource E",
                "capacity": [1.0] * 100,
            },
            {
                "id": self._get_next_resource_id(),
                "name": "Resource F",
                "capacity": [1.0] * 100,
            },
            {
                "id": self._get_next_resource_id(),
                "name": "Resource G",
                "capacity": [1.0] * 100,
            },
            {
                "id": self._get_next_resource_id(),
                "name": "Resource H",
                "capacity": [1.0] * 100,
            },
            {
                "id": self._get_next_resource_id(),
                "name": "Resource I",
                "capacity": [1.0] * 100,
            },
            {
                "id": self._get_next_resource_id(),
                "name": "Resource J",
                "capacity": [1.0] * 100,
            },
        ]

        # Data structures
        self.tasks = []
        self.task_id_counter = 0

        # File path
        self.current_file_path = None

    def _get_next_resource_id(self) -> int:
        """Generate a unique resource ID."""
        self.resource_id_counter += 1
        return self.resource_id_counter

    def get_next_task_id(self) -> int:
        """Generate a unique task ID."""
        self.task_id_counter += 1
        return self.task_id_counter

    def add_task(
        self,
        row: int,
        col: int,
        duration: int,
        description: str,
        resources: Dict[int, float] = None,  # Changed to Dict[resource_id, allocation]
        url: str = "",
        predecessors: List[int] = None,
        successors: List[int] = None,
    ) -> Dict[str, Any]:
        """Add a new task to the model."""
        task = {
            "task_id": self.get_next_task_id(),
            "row": row,
            "col": col,
            "duration": duration,
            "description": description,
            "url": url,
            "resources": resources or {},  # Changed to Dict[resource_id, allocation]
            "predecessors": predecessors or [],
            "successors": successors or [],
        }
        self.tasks.append(task)
        return task

    def delete_task(self, task_id: int) -> bool:
        """Delete a task by its ID."""
        for i, task in enumerate(self.tasks):
            if task["task_id"] == task_id:
                del self.tasks[i]
                return True
        return False

    def update_task(self, task_id: int, **updates) -> bool:
        """Update task properties."""
        for task in self.tasks:
            if task["task_id"] == task_id:
                for key, value in updates.items():
                    task[key] = value
                return True
        return False

    def get_task(self, task_id: int) -> Optional[Dict[str, Any]]:
        """Get a task by its ID."""
        for task in self.tasks:
            if task["task_id"] == task_id:
                return task
        return None

    def move_task(self, task_id: int, row: int, col: int) -> bool:
        """Move a task to a new position."""
        return self.update_task(task_id, row=row, col=col)

    def resize_task(self, task_id: int, duration: int) -> bool:
        """Resize a task (change duration)."""
        return self.update_task(task_id, duration=duration)

    def calculate_resource_loading(self) -> Dict[int, List[float]]:
        """Calculate resource loading based on task positions."""
        resource_loading = {}

        # Initialize dictionary with resource IDs as keys
        for resource in self.resources:
            resource_id = resource["id"]
            resource_loading[resource_id] = [0.0] * self.days

        # Calculate loading for each resource on each day
        for task in self.tasks:
            col = task["col"]
            duration = task["duration"]

            # For each resource allocation in the task
            for resource_id, allocation in task["resources"].items():
                for day in range(duration):
                    if 0 <= col + day < self.days:
                        resource_loading[resource_id][col + day] += allocation

        return resource_loading

    def get_resource_by_id(self, resource_id: int) -> Optional[Dict[str, Any]]:
        """Find a resource by its ID."""
        for resource in self.resources:
            if resource["id"] == resource_id:
                return resource
        return None

    def get_resource_by_name(self, resource_name: str) -> Optional[Dict[str, Any]]:
        """Find a resource by its name."""
        for resource in self.resources:
            if resource["name"] == resource_name:
                return resource
        return None

    def add_resource(self, resource_name: str) -> bool:
        """Add a new resource."""
        # Check if resource with this name already exists
        if self.get_resource_by_name(resource_name):
            return False

        # Create new resource with default capacity
        new_resource = {
            "id": self._get_next_resource_id(),
            "name": resource_name,
            "capacity": [1.0] * self.days,
        }
        self.resources.append(new_resource)
        return True

    def remove_resource(self, resource_id: int) -> bool:
        """Remove a resource and update tasks."""
        resource = self.get_resource_by_id(resource_id)
        if not resource:
            return False

        # Remove resource from all tasks
        for task in self.tasks:
            if resource_id in task["resources"]:
                del task["resources"][resource_id]

        # Remove from resources list
        self.resources = [r for r in self.resources if r["id"] != resource_id]
        return True

    def update_resource_name(self, resource_id: int, new_name: str) -> bool:
        """Update the name of a resource."""
        # Check if the new name already exists
        if self.get_resource_by_name(new_name):
            return False

        resource = self.get_resource_by_id(resource_id)
        if resource:
            resource["name"] = new_name
            return True
        return False

    def update_resource_capacity(
        self, resource_id: int, day: int, capacity: float
    ) -> bool:
        """Update the capacity of a resource for a specific day."""
        resource = self.get_resource_by_id(resource_id)
        if resource and 0 <= day < self.days:
            resource["capacity"][day] = max(0.0, capacity)  # Ensure non-negative
            return True
        return False

    def update_resource_capacity_range(
        self, resource_id: int, start_day: int, end_day: int, capacity: float
    ) -> bool:
        """Update the capacity of a resource for a range of days."""
        resource = self.get_resource_by_id(resource_id)
        if not resource:
            return False

        start = max(0, start_day)
        end = min(self.days, end_day)

        for day in range(start, end):
            resource["capacity"][day] = max(0.0, capacity)  # Ensure non-negative

        return True

    def update_task_resource_allocation(
        self, task_id: int, resource_id: int, allocation: float
    ) -> bool:
        """Update the allocation of a resource for a task."""
        task = self.get_task(task_id)
        if not task:
            return False

        if allocation <= 0:
            # Remove the resource if allocation is zero or negative
            if resource_id in task["resources"]:
                del task["resources"][resource_id]
        else:
            # Add or update the resource allocation
            task["resources"][resource_id] = allocation

        return True

    def add_predecessor(self, task_id: int, predecessor_id: int) -> bool:
        """Add a predecessor relationship between tasks."""
        if task_id == predecessor_id:
            return False  # Prevent self-linking

        task = self.get_task(task_id)
        predecessor = self.get_task(predecessor_id)

        if not task or not predecessor:
            return False

        if predecessor_id not in task["predecessors"]:
            task["predecessors"].append(predecessor_id)

        if task_id not in predecessor["successors"]:
            predecessor["successors"].append(task_id)

        return True

    def add_successor(self, task_id: int, successor_id: int) -> bool:
        """Add a successor relationship between tasks."""
        if task_id == successor_id:
            return False  # Prevent self-linking
        return self.add_predecessor(successor_id, task_id)

    def load_from_file(self, file_path: str) -> bool:
        """Load project data from a file."""
        try:
            with open(file_path, "r") as f:
                data = json.load(f)

            # Basic validation
            if "tasks" not in data or "resources" not in data or "days" not in data:
                return False

            # Load project data
            self.tasks = data["tasks"]
            self.resources = data["resources"]
            self.days = data["days"]

            # Ensure resource capacity arrays are proper length
            for resource in self.resources:
                if "capacity" not in resource or len(resource["capacity"]) != self.days:
                    resource["capacity"] = [1.0] * self.days

            # Ensure resources have IDs
            for resource in self.resources:
                if "id" not in resource:
                    resource["id"] = self._get_next_resource_id()

            # Convert legacy resource format if needed
            for task in self.tasks:
                if isinstance(task["resources"], list):
                    # Convert from old list format to new dict format
                    old_resources = task["resources"]
                    task["resources"] = {}
                    for resource in self.resources:
                        if resource["name"] in old_resources:
                            task["resources"][resource["id"]] = (
                                1.0  # Default to 1.0 allocation
                            )

            # Find highest task ID to update counter
            max_task_id = 0
            for task in self.tasks:
                if task["task_id"] > max_task_id:
                    max_task_id = task["task_id"]
            self.task_id_counter = max_task_id

            # Find highest resource ID to update counter
            max_resource_id = 0
            for resource in self.resources:
                if resource["id"] > max_resource_id:
                    max_resource_id = resource["id"]
            self.resource_id_counter = max_resource_id

            self.current_file_path = file_path
            return True
        except Exception as e:
            print(f"Error loading file: {e}")
            return False

    def save_to_file(self, file_path: str) -> bool:
        """Save project data to a file."""
        try:
            project_data = {
                "tasks": self.tasks,
                "resources": self.resources,
                "days": self.days,
                "max_rows": self.max_rows,
            }

            with open(file_path, "w") as f:
                json.dump(project_data, f, indent=2)

            self.current_file_path = file_path
            return True
        except Exception as e:
            print(f"Error saving file: {e}")
            return False

    def create_sample_tasks(self) -> None:
        """Create some sample tasks for demo purposes."""
        # Get resource IDs for easier reference
        resource_a_id = self.resources[0]["id"]  # Resource A
        resource_b_id = self.resources[1]["id"]  # Resource B
        resource_c_id = self.resources[2]["id"]  # Resource C
        resource_d_id = self.resources[3]["id"]  # Resource D

        # Add tasks with fractional resource allocations
        self.add_task(
            row=1,
            col=5,
            duration=5,
            description="Task A",
            resources={resource_a_id: 0.5, resource_b_id: 1.5},
            url="https://www.google.com",
        )
        self.add_task(
            row=2,
            col=12,
            duration=4,
            description="Task B",
            resources={resource_a_id: 1.0, resource_b_id: 0.75, resource_c_id: 0.25},
            url="https://www.google.com",
        )
        self.add_task(
            row=3,
            col=2,
            duration=3,
            description="Task C",
            resources={resource_a_id: 2.0},
            url="https://www.google.com",
        )
        self.add_task(
            row=4,
            col=1,
            duration=2,
            description="Task D",
            resources={resource_a_id: 0.5, resource_d_id: 0.5},
        )
