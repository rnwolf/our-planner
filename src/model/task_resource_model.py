import json
from typing import List, Dict, Any, Optional, Tuple, Set
from datetime import datetime, timedelta


class TaskResourceModel:
    def __init__(self):
        # Configuration
        self.days = 100
        self.max_rows = 50
        self.start_date = datetime.now().replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        # Set date for tracking task status
        self.setdate = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        # Resource management with IDs
        self.resource_id_counter = 0
        self.resources = [
            {
                'id': self._get_next_resource_id(),
                'name': 'Resource A',
                'capacity': [1.0] * 100,
                'tags': [],  # Add tags list to resources
            },
            {
                'id': self._get_next_resource_id(),
                'name': 'Resource B',
                'capacity': [1.0] * 100,
                'tags': [],
            },
            {
                'id': self._get_next_resource_id(),
                'name': 'Resource C',
                'capacity': [1.0] * 100,
                'tags': [],
            },
            {
                'id': self._get_next_resource_id(),
                'name': 'Resource D',
                'capacity': [1.0] * 100,
                'tags': [],
            },
            {
                'id': self._get_next_resource_id(),
                'name': 'Resource E',
                'capacity': [1.0] * 100,
                'tags': [],
            },
            {
                'id': self._get_next_resource_id(),
                'name': 'Resource F',
                'capacity': [1.0] * 100,
                'tags': [],
            },
            {
                'id': self._get_next_resource_id(),
                'name': 'Resource G',
                'capacity': [1.0] * 100,
                'tags': [],
            },
            {
                'id': self._get_next_resource_id(),
                'name': 'Resource H',
                'capacity': [1.0] * 100,
                'tags': [],
            },
            {
                'id': self._get_next_resource_id(),
                'name': 'Resource I',
                'capacity': [1.0] * 100,
                'tags': [],
            },
            {
                'id': self._get_next_resource_id(),
                'name': 'Resource J',
                'capacity': [1.0] * 100,
                'tags': [],
            },
        ]

        # Data structures
        self.tasks = []
        self.task_id_counter = 0

        # File path
        self.current_file_path = None

        # All tags in the system for easy reference and autocomplete
        self.all_tags = set()

    def _get_next_resource_id(self) -> int:
        """Generate a unique resource ID."""
        self.resource_id_counter += 1
        return self.resource_id_counter

    def get_next_task_id(self) -> int:
        """Generate a unique task ID."""
        self.task_id_counter += 1
        return self.task_id_counter

    def get_date_for_day(self, day: int) -> datetime:
        """Get the calendar date for a specific day in the timeline."""
        return self.start_date + timedelta(days=day)

    def get_day_for_date(self, date: datetime) -> int:
        """Get the day index in the timeline for a specific calendar date."""
        delta = date - self.start_date
        return delta.days

    def get_month_ranges(self) -> List[Dict[str, Any]]:
        """Get a list of month ranges for the timeline."""
        month_ranges = []
        current_month = None
        start_col = 0
        month_format = '%Y-%m (%b)'

        for day in range(self.days):
            date = self.get_date_for_day(day)
            month_key = date.strftime('%Y-%m')  # Year-Month as key

            if month_key != current_month:
                # If there was a previous month, add it to the ranges
                if current_month is not None:
                    month_ranges.append(
                        {
                            'label': self.get_date_for_day(start_col).strftime(
                                month_format
                            ),
                            'start': start_col,
                            'end': day - 1,
                        }
                    )

                # Start a new month
                current_month = month_key
                start_col = day

        # Add the last month
        if current_month is not None:
            month_ranges.append(
                {
                    'label': self.get_date_for_day(start_col).strftime(month_format),
                    'start': start_col,
                    'end': self.days - 1,
                }
            )

        return month_ranges

    def add_task(
        self,
        row: int,
        col: int,
        duration: int,
        description: str,
        resources: Dict[int, float] = None,  # Changed to Dict[resource_id, allocation]
        url: str = '',
        predecessors: List[int] = None,
        successors: List[int] = None,
        tags: List[str] = None,  # Add tags parameter
        color: str = None,  # Add color parameter with None default
    ) -> Dict[str, Any]:
        """Add a new task to the model."""
        tags = tags or []  # Default to empty list if None
        color = color or 'Cyan'  # Default color if None

        # Update all_tags with any new tags
        for tag in tags:
            self.all_tags.add(tag)

        task = {
            'task_id': self.get_next_task_id(),
            'row': row,
            'col': col,
            'duration': duration,
            'description': description,
            'url': url,
            'resources': resources or {},  # Changed to Dict[resource_id, allocation]
            'predecessors': predecessors or [],
            'successors': successors or [],
            'tags': tags,  # Add tags to task dictionary
            'color': color,  # Add color to task dictionary
        }
        self.tasks.append(task)
        return task

    def add_tags_to_task(self, task_id: int, tags: List[str]) -> bool:
        """Add tags to a task."""
        task = self.get_task(task_id)
        if not task:
            return False

        # Make sure task has a tags list
        if 'tags' not in task:
            task['tags'] = []

        # Add new tags that aren't already present
        for tag in tags:
            if tag not in task['tags']:
                task['tags'].append(tag)
                self.all_tags.add(tag)

        return True

    def remove_tags_from_task(self, task_id: int, tags: List[str]) -> bool:
        """Remove tags from a task."""
        task = self.get_task(task_id)
        if not task or 'tags' not in task:
            return False

        # Remove specified tags
        task['tags'] = [tag for tag in task['tags'] if tag not in tags]
        return True

    def set_task_tags(self, task_id: int, tags: List[str]) -> bool:
        """Replace all tags for a task."""
        task = self.get_task(task_id)
        if not task:
            return False

        # Update all_tags
        for tag in tags:
            self.all_tags.add(tag)

        # Set the tags
        task['tags'] = tags
        return True

    def add_tags_to_resource(self, resource_id: int, tags: List[str]) -> bool:
        """Add tags to a resource."""
        resource = self.get_resource_by_id(resource_id)
        if not resource:
            return False

        # Make sure resource has a tags list
        if 'tags' not in resource:
            resource['tags'] = []

        # Add new tags that aren't already present
        for tag in tags:
            if tag not in resource['tags']:
                resource['tags'].append(tag)
                self.all_tags.add(tag)

        return True

    def remove_tags_from_resource(self, resource_id: int, tags: List[str]) -> bool:
        """Remove tags from a resource."""
        resource = self.get_resource_by_id(resource_id)
        if not resource or 'tags' not in resource:
            return False

        # Remove specified tags
        resource['tags'] = [tag for tag in resource['tags'] if tag not in tags]
        return True

    def set_resource_tags(self, resource_id: int, tags: List[str]) -> bool:
        """Replace all tags for a resource."""
        resource = self.get_resource_by_id(resource_id)
        if not resource:
            return False

        # Update all_tags
        for tag in tags:
            self.all_tags.add(tag)

        # Set the tags
        resource['tags'] = tags
        return True

    def get_tasks_by_tags(
        self, tags: List[str], match_all: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get tasks that match the specified tags.

        Args:
            tags: List of tags to match
            match_all: If True, task must have all specified tags. If False, task must have at least one.

        Returns:
            List of matching tasks
        """
        if not tags:
            return self.tasks.copy()

        matching_tasks = []
        for task in self.tasks:
            # Skip tasks without tags
            if 'tags' not in task or not task['tags']:
                continue

            # Check for tag matches
            if match_all:
                # Task must have all specified tags
                if all(tag in task['tags'] for tag in tags):
                    matching_tasks.append(task)
            else:
                # Task must have at least one of the specified tags
                if any(tag in task['tags'] for tag in tags):
                    matching_tasks.append(task)

        return matching_tasks

    def get_resources_by_tags(
        self, tags: List[str], match_all: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get resources that match the specified tags.

        Args:
            tags: List of tags to match
            match_all: If True, resource must have all specified tags. If False, resource must have at least one.

        Returns:
            List of matching resources
        """
        if not tags:
            return self.resources.copy()

        matching_resources = []
        for resource in self.resources:
            # Skip resources without tags
            if 'tags' not in resource or not resource['tags']:
                continue

            # Check for tag matches
            if match_all:
                # Resource must have all specified tags
                if all(tag in resource['tags'] for tag in tags):
                    matching_resources.append(resource)
            else:
                # Resource must have at least one of the specified tags
                if any(tag in resource['tags'] for tag in tags):
                    matching_resources.append(resource)

        return matching_resources

    def get_all_tags(self) -> List[str]:
        """Get all tags used in the project."""
        return sorted(list(self.all_tags))

    def refresh_all_tags(self) -> None:
        """Rebuild the all_tags set by scanning all tasks and resources."""
        self.all_tags = set()

        # Collect tags from tasks
        for task in self.tasks:
            if 'tags' in task:
                for tag in task['tags']:
                    self.all_tags.add(tag)

        # Collect tags from resources
        for resource in self.resources:
            if 'tags' in resource:
                for tag in resource['tags']:
                    self.all_tags.add(tag)

    def delete_task(self, task_id: int) -> bool:
        """Delete a task by its ID."""
        for i, task in enumerate(self.tasks):
            if task['task_id'] == task_id:
                del self.tasks[i]
                return True
        return False

    def update_task(self, task_id: int, **updates) -> bool:
        """Update task properties."""
        for task in self.tasks:
            if task['task_id'] == task_id:
                for key, value in updates.items():
                    task[key] = value
                return True
        return False

    def get_task(self, task_id: int) -> Optional[Dict[str, Any]]:
        """Get a task by its ID."""
        for task in self.tasks:
            if task['task_id'] == task_id:
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
            resource_id = resource['id']
            resource_loading[resource_id] = [0.0] * self.days

        # Calculate loading for each resource on each day
        for task in self.tasks:
            col = task['col']
            duration = task['duration']

            # For each resource allocation in the task
            for resource_id_str, allocation in task['resources'].items():
                # Convert string resource_id to integer
                resource_id = int(resource_id_str)

                for day in range(duration):
                    if 0 <= col + day < self.days:
                        resource_loading[resource_id][col + day] += allocation

        return resource_loading

    def get_resource_by_id(self, resource_id: int) -> Optional[Dict[str, Any]]:
        """Find a resource by its ID."""
        for resource in self.resources:
            if resource['id'] == resource_id:
                return resource
        return None

    def get_resource_by_name(self, resource_name: str) -> Optional[Dict[str, Any]]:
        """Find a resource by its name."""
        for resource in self.resources:
            if resource['name'] == resource_name:
                return resource
        return None

    def add_resource(self, resource_name: str) -> bool:
        """Add a new resource."""
        # Check if resource with this name already exists
        if self.get_resource_by_name(resource_name):
            return False

        # Create new resource with default capacity
        new_resource = {
            'id': self._get_next_resource_id(),
            'name': resource_name,
            'capacity': [1.0] * self.days,
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
            if resource_id in task['resources']:
                del task['resources'][resource_id]

        # Remove from resources list
        self.resources = [r for r in self.resources if r['id'] != resource_id]
        return True

    def update_resource_name(self, resource_id: int, new_name: str) -> bool:
        """Update the name of a resource."""
        # Check if the new name already exists
        if self.get_resource_by_name(new_name):
            return False

        resource = self.get_resource_by_id(resource_id)
        if resource:
            resource['name'] = new_name
            return True
        return False

    def update_resource_capacity(
        self, resource_id: int, day: int, capacity: float
    ) -> bool:
        """Update the capacity of a resource for a specific day."""
        resource = self.get_resource_by_id(resource_id)
        if resource and 0 <= day < self.days:
            resource['capacity'][day] = max(0.0, capacity)  # Ensure non-negative
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
            resource['capacity'][day] = max(0.0, capacity)  # Ensure non-negative

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
            if resource_id in task['resources']:
                del task['resources'][resource_id]
        else:
            # Add or update the resource allocation
            task['resources'][resource_id] = allocation

        return True

    def add_predecessor(self, task_id: int, predecessor_id: int) -> bool:
        """Add a predecessor relationship between tasks."""
        if task_id == predecessor_id:
            return False  # Prevent self-linking

        task = self.get_task(task_id)
        predecessor = self.get_task(predecessor_id)

        if not task or not predecessor:
            return False

        if predecessor_id not in task['predecessors']:
            task['predecessors'].append(predecessor_id)

        if task_id not in predecessor['successors']:
            predecessor['successors'].append(task_id)

        return True

    def add_successor(self, task_id: int, successor_id: int) -> bool:
        """Add a successor relationship between tasks."""
        if task_id == successor_id:
            return False  # Prevent self-linking
        return self.add_predecessor(successor_id, task_id)

    # Update load_from_file to handle tags
    def load_from_file(self, file_path: str) -> bool:
        """Load project data from a file."""
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)

            # Basic validation
            if 'tasks' not in data or 'resources' not in data or 'days' not in data:
                return False

            # Load project data
            self.tasks = data['tasks']
            self.resources = data['resources']
            self.days = data['days']

            # Load start_date if available
            if 'start_date' in data:
                try:
                    self.start_date = datetime.fromisoformat(data['start_date'])
                except ValueError:
                    # If there's an error parsing the date, use the current date
                    self.start_date = datetime.now().replace(
                        hour=0, minute=0, second=0, microsecond=0
                    )

            # Load setdate if available
            if 'setdate' in data:
                try:
                    self.setdate = datetime.fromisoformat(data['setdate'])
                except ValueError:
                    # If there's an error parsing the date, use the current date
                    self.setdate = datetime.now().replace(
                        hour=0, minute=0, second=0, microsecond=0
                    )

            # Load max_rows (previously max_tasks)
            if 'max_rows' in data:
                self.max_rows = data['max_rows']
            elif 'max_tasks' in data:  # For backward compatibility
                self.max_rows = data['max_tasks']

            # Ensure resource capacity arrays are proper length
            for resource in self.resources:
                if 'capacity' not in resource or len(resource['capacity']) != self.days:
                    resource['capacity'] = [1.0] * self.days

                # Ensure resources have tags field
                if 'tags' not in resource:
                    resource['tags'] = []

            # Ensure resources have IDs
            for resource in self.resources:
                if 'id' not in resource:
                    resource['id'] = self._get_next_resource_id()

            # Find highest task ID to update counter
            max_task_id = 0
            for task in self.tasks:
                if task['task_id'] > max_task_id:
                    max_task_id = task['task_id']
            self.task_id_counter = max_task_id

            # Find highest resource ID to update counter
            max_resource_id = 0
            for resource in self.resources:
                if resource['id'] > max_resource_id:
                    max_resource_id = resource['id']
            self.resource_id_counter = max_resource_id

            # Rebuild all_tags
            self.refresh_all_tags()

            self.current_file_path = file_path
            return True
        except Exception as e:
            print(f'Error loading file: {e}')
            return False

    def save_to_file(self, file_path: str) -> bool:
        """Save project data to a file."""
        try:
            project_data = {
                'tasks': self.tasks,
                'resources': self.resources,
                'days': self.days,
                'max_rows': self.max_rows,
                'start_date': self.start_date.isoformat(),
                'setdate': self.setdate.isoformat(),
            }

            with open(file_path, 'w') as f:
                json.dump(project_data, f, indent=2)

            self.current_file_path = file_path
            return True
        except Exception as e:
            print(f'Error saving file: {e}')
            return False

    # Add tags to existing tasks during sample creation
    def create_sample_tasks(self) -> None:
        """Create some sample tasks for demo purposes."""
        # Get resource IDs for easier reference
        resource_a_id = self.resources[0]['id']  # Resource A
        resource_b_id = self.resources[1]['id']  # Resource B
        resource_c_id = self.resources[2]['id']  # Resource C
        resource_d_id = self.resources[3]['id']  # Resource D

        # Add tasks with fractional resource allocations, tags, and colors
        self.add_task(
            row=1,
            col=5,
            duration=5,
            description='Task A',
            resources={resource_a_id: 0.5, resource_b_id: 1.5},
            url='https://www.google.com',
            tags=['important', 'phase1'],
            color='LightBlue',  # Add color attribute
        )
        self.add_task(
            row=2,
            col=12,
            duration=4,
            description='Task B',
            resources={resource_a_id: 1.0, resource_b_id: 0.75, resource_c_id: 0.25},
            url='https://www.google.com',
            tags=['phase1'],
            color='LightGreen',  # Add color attribute
        )
        self.add_task(
            row=3,
            col=2,
            duration=3,
            description='Task C',
            resources={resource_a_id: 2.0},
            url='https://www.google.com',
            tags=['phase2', 'critical'],
            color='Salmon',  # Add color attribute
        )
        self.add_task(
            row=4,
            col=1,
            duration=2,
            description='Task D',
            resources={resource_a_id: 0.5, resource_d_id: 0.5},
            tags=['phase2'],
            color='Gold',  # Add color attribute
        )

        # Add tags to resources as well
        self.set_resource_tags(resource_a_id, ['team1', 'developer'])
        self.set_resource_tags(resource_b_id, ['team1', 'designer'])
        self.set_resource_tags(resource_c_id, ['team2', 'developer'])
        self.set_resource_tags(resource_d_id, ['team2', 'qa'])

        # Make sure all_tags is updated
        self.refresh_all_tags()

    def set_task_color(self, task_id: int, color: str) -> bool:
        """Set the color for a specific task.

        Args:
            task_id: ID of the task to update
            color: Color name to set (must be a valid web color name)

        Returns:
            bool: True if successful, False if task not found
        """
        task = self.get_task(task_id)
        if not task:
            return False

        task['color'] = color
        return True

    def set_task_colors(self, task_ids: List[int], color: str) -> int:
        """Set the color for multiple tasks.

        Args:
            task_ids: List of task IDs to update
            color: Color name to set (must be a valid web color name)

        Returns:
            int: Number of tasks successfully updated
        """
        count = 0
        for task_id in task_ids:
            if self.set_task_color(task_id, color):
                count += 1
        return count
