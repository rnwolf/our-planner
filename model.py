import json
from typing import List, Dict, Any, Optional, Tuple


class TaskResourceModel:
    def __init__(self):
        # Configuration
        self.days = 100
        self.max_tasks = 50
        self.resources = [
            "Resource A", "Resource B", "Resource C", "Resource D", 
            "Resource E", "Resource F", "Resource G", "Resource H",
            "Resource I", "Resource J"
        ]
        
        # Data structures
        self.tasks = []
        self.task_id_counter = 0
        
        # File path
        self.current_file_path = None
    
    def get_next_task_id(self) -> int:
        """Generate a unique task ID."""
        self.task_id_counter += 1
        return self.task_id_counter
    
    def add_task(self, row: int, col: int, duration: int, description: str, 
                resources: List[str] = None, url: str = "", predecessors: List[int] = None, 
                successors: List[int] = None) -> Dict[str, Any]:
        """Add a new task to the model."""
        task = {
            "task_id": self.get_next_task_id(),
            "row": row,
            "col": col,
            "duration": duration,
            "description": description,
            "url": url,
            "resources": resources or [],
            "predecessors": predecessors or [],
            "successors": successors or []
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
    
    def calculate_resource_loading(self) -> Dict[str, List[int]]:
        """Calculate resource loading based on task positions."""
        resource_loading = {}
        for resource in self.resources:
            resource_loading[resource] = [0] * self.days
        
        for task in self.tasks:
            col = task["col"]
            duration = task["duration"]
            for resource in task["resources"]:
                for day in range(duration):
                    if 0 <= col + day < self.days:
                        resource_loading[resource][col + day] += 1
        
        return resource_loading
    
    def add_resource(self, resource_name: str) -> bool:
        """Add a new resource."""
        if resource_name in self.resources:
            return False
        self.resources.append(resource_name)
        return True
    
    def remove_resource(self, resource_name: str) -> bool:
        """Remove a resource and update tasks."""
        if resource_name not in self.resources:
            return False
        
        # Remove resource from all tasks
        for task in self.tasks:
            if resource_name in task["resources"]:
                task["resources"].remove(resource_name)
        
        # Remove from resources list
        self.resources.remove(resource_name)
        return True
    
    def add_predecessor(self, task_id: int, predecessor_id: int) -> bool:
        """Add a predecessor relationship between tasks."""
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
            
            # Find highest task ID to update counter
            max_id = 0
            for task in self.tasks:
                if task["task_id"] > max_id:
                    max_id = task["task_id"]
            self.task_id_counter = max_id
            
            self.current_file_path = file_path
            return True
        except Exception:
            return False
    
    def save_to_file(self, file_path: str) -> bool:
        """Save project data to a file."""
        try:
            project_data = {
                "tasks": self.tasks,
                "resources": self.resources,
                "days": self.days,
                "max_tasks": self.max_tasks
            }
            
            with open(file_path, "w") as f:
                json.dump(project_data, f, indent=2)
            
            self.current_file_path = file_path
            return True
        except Exception:
            return False
            
    def create_sample_tasks(self) -> None:
        """Create some sample tasks for demo purposes."""
        self.add_task(
            row=1, 
            col=5, 
            duration=5, 
            description="Task A", 
            resources=["Resource A", "Resource B"],
            url="https://www.google.com"
        )
        self.add_task(
            row=2, 
            col=12, 
            duration=4, 
            description="Task B", 
            resources=["Resource A", "Resource B", "Resource C"],
            url="https://www.google.com"
        )
        self.add_task(
            row=3, 
            col=2, 
            duration=3, 
            description="Task C", 
            resources=["Resource A"],
            url="https://www.google.com"
        )
        self.add_task(
            row=4, 
            col=1, 
            duration=2, 
            description="Task D", 
            resources=["Resource A", "Resource D"]
        )
