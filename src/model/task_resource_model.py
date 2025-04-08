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
            'notes': [],  # Initialize empty notes list
            # New CCPM-related properties
            'state': 'planning',  # Initial state: 'planning', 'buffered', or 'done'
            'safe_duration': duration,  # Initially set to the provided duration
            'aggressive_duration': None,  # Optimistic duration (if set)
            'actual_start_date': None,  # When work actually started
            'actual_end_date': None,  # When work was completed
            'fullkit_date': None,  # When all prerequisites were ready
            'remaining_duration_history': [],  # Track history of remaining duration estimates
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

    def add_resource(self, resource_name, works_weekends=True):
        """Add a new resource with default capacity."""
        if self.get_resource_by_name(resource_name):
            return False

        # Create new resource with default capacity
        default_capacity = [1.0] * self.days

        # If resource doesn't work weekends, set weekend capacity to 0
        if not works_weekends:
            for day in range(self.days):
                date = self.get_date_for_day(day)
                if date.weekday() >= 5:  # 5=Saturday, 6=Sunday
                    default_capacity[day] = 0.0

        new_resource = {
            'id': self._get_next_resource_id(),
            'name': resource_name,
            'capacity': default_capacity,
            'tags': [],
            'works_weekends': works_weekends,
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

    def _is_weekend(self, day_index, start_date=None):
        """Determine if a day index is a weekend based on a given start date."""
        # Use provided start date or the model's current start date
        start = start_date if start_date is not None else self.model.start_date
        date = start + timedelta(days=day_index)
        # Print for debugging (you can remove this later)
        print(
            f"Day {day_index}: {date.strftime('%Y-%m-%d')} is weekday {date.weekday()}"
        )
        return date.weekday() >= 5  # 5=Saturday, 6=Sunday

    def _update_resource_capacities_for_date_change(self, delta_days):
        """Update resource capacities when the start date changes."""
        # Calculate the new start date
        new_start_date = self.model.start_date + timedelta(days=-delta_days)

        # For each resource
        for resource in self.model.resources:
            works_weekends = resource.get('works_weekends', True)
            new_capacity = [1.0] * self.model.days

            if delta_days > 0:
                # Moving start date forward, shift capacities left
                for day in range(self.model.days - delta_days):
                    if day + delta_days < len(resource['capacity']):
                        # Copy existing capacity if available
                        new_capacity[day] = resource['capacity'][day + delta_days]

            elif delta_days < 0:
                # Moving start date backward, shift capacities right
                abs_delta = abs(delta_days)
                for day in range(abs_delta, self.model.days):
                    if day - abs_delta < len(resource['capacity']):
                        # Copy existing capacity if available
                        new_capacity[day] = resource['capacity'][day - abs_delta]

            # Check all days for weekend status using the new start date
            if not works_weekends:
                for day in range(self.model.days):
                    if self._is_weekend(day, new_start_date):
                        new_capacity[day] = 0.0

            # Update the resource capacity
            resource['capacity'] = new_capacity

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

            # After loading tasks, ensure each task has a notes field for backward complatability
            # After loading tasks, ensure each task has a notes field with the expected structure
            for task in self.tasks:
                if 'notes' not in task:
                    task['notes'] = []
                else:
                    # Ensure each note has the expected structure
                    for note in task['notes']:
                        if not isinstance(note, dict):
                            # Convert to proper format if needed
                            task['notes'] = []
                            break

                        # Ensure timestamp and text fields exist
                        if 'timestamp' not in note or 'text' not in note:
                            # If note is missing key fields, reset notes
                            task['notes'] = []
                            break
                    # Add CCPM fields if they don't exist

                if 'state' not in task:
                    task['state'] = 'planning'

                # Add fields if they don't exist fir backward compatability
                if 'safe_duration' not in task:
                    task['safe_duration'] = task['duration']

                if 'aggressive_duration' not in task:
                    task['aggressive_duration'] = None

                if 'actual_start_date' not in task:
                    task['actual_start_date'] = None

                if 'actual_end_date' not in task:
                    task['actual_end_date'] = None

                if 'fullkit_date' not in task:
                    task['fullkit_date'] = None

                if 'remaining_duration_history' not in task:
                    task['remaining_duration_history'] = []
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
                if 'works_weekends' not in resource:
                    resource['works_weekends'] = True

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

    def add_note_to_task(self, task_id: int, note_text: str) -> bool:
        """Add a timestamped note to a task.

        Args:
            task_id: ID of the task to add the note to
            note_text: Content of the note

        Returns:
            bool: True if successful, False if task not found
        """
        task = self.get_task(task_id)
        if not task:
            return False

        # Ensure task has a notes list
        if 'notes' not in task:
            task['notes'] = []

        # Create the note with timestamp
        note = {'timestamp': datetime.now().isoformat(), 'text': note_text}

        # Add the note to the task
        task['notes'].append(note)
        return True

    def get_task_notes(self, task_id: int) -> List[Dict[str, Any]]:
        """Get all notes for a specific task.

        Args:
            task_id: ID of the task

        Returns:
            List of note dictionaries, each with 'timestamp' and 'text' fields
        """
        task = self.get_task(task_id)
        if not task or 'notes' not in task:
            return []

        # Sort notes by timestamp, newest first
        return sorted(task['notes'], key=lambda note: note['timestamp'], reverse=True)

    def delete_note_from_task(self, task_id: int, note_index: int) -> bool:
        """Delete a note from a task.

        Args:
            task_id: ID of the task
            note_index: Index of the note in the task's notes list

        Returns:
            bool: True if successful, False if task or note not found
        """
        task = self.get_task(task_id)
        if not task or 'notes' not in task:
            return False

        # Ensure the index is valid
        if note_index < 0 or note_index >= len(task['notes']):
            return False

        # Remove the note
        task['notes'].pop(note_index)
        return True

    def get_all_notes_for_tasks(self, task_ids: List[int]) -> List[Dict[str, Any]]:
        """Get all notes for a list of tasks, sorted by timestamp.

        Args:
            task_ids: List of task IDs to get notes for

        Returns:
            List of note dictionaries with additional 'task_id' and 'original_index' fields
        """
        all_notes = []

        for task_id in task_ids:
            task = self.get_task(task_id)
            if not task or 'notes' not in task:
                continue

            # Add task_id and original_index to each note for reference
            for i, note in enumerate(task['notes']):
                note_with_task = note.copy()
                note_with_task['task_id'] = task_id
                note_with_task['task_description'] = task.get(
                    'description', f'Task {task_id}'
                )
                note_with_task['original_index'] = i  # Store the original index
                all_notes.append(note_with_task)

        # Sort all notes by timestamp, newest first
        return sorted(all_notes, key=lambda note: note['timestamp'], reverse=True)

    def record_remaining_duration(self, task_id: int, remaining_duration: int) -> bool:
        """Record a new remaining duration estimate for a task on the current setdate.

        Args:
            task_id: ID of the task
            remaining_duration: Estimated remaining duration in days

        Returns:
            bool: True if successful, False if task not found
        """
        task = self.get_task(task_id)
        if not task:
            return False

        # Create record with current setdate
        record = {
            'date': self.setdate.isoformat(),
            'remaining_duration': remaining_duration,
        }

        # Initialize the history list if not present (for backward compatibility)
        if 'remaining_duration_history' not in task:
            task['remaining_duration_history'] = []

        # Add the record
        task['remaining_duration_history'].append(record)

        # If this is the first record, set the actual start date
        if not task.get('actual_start_date'):
            task['actual_start_date'] = self.setdate.isoformat()

        # If remaining duration is 0, set the actual end date and mark as done
        if remaining_duration == 0:
            task['actual_end_date'] = self.setdate.isoformat()
            task['state'] = 'done'

        return True

    def get_remaining_duration_history(self, task_id: int) -> List[Dict[str, Any]]:
        """Get the history of remaining duration estimates for a task.

        Args:
            task_id: ID of the task

        Returns:
            List of dictionaries with date and remaining_duration fields
        """
        task = self.get_task(task_id)
        if not task or 'remaining_duration_history' not in task:
            return []

        return task['remaining_duration_history']

    def get_latest_remaining_duration(self, task_id: int) -> Optional[int]:
        """Get the most recent remaining duration estimate for a task.

        Args:
            task_id: ID of the task

        Returns:
            The most recent remaining duration estimate, or None if no estimates exist
        """
        history = self.get_remaining_duration_history(task_id)
        if not history:
            return None

        # Sort by date, newest first
        sorted_history = sorted(history, key=lambda x: x['date'], reverse=True)
        return sorted_history[0]['remaining_duration']

    def set_task_state(self, task_id: int, state: str) -> bool:
        """Set the state of a task.

        Args:
            task_id: ID of the task
            state: New state ('planning', 'buffered', 'done')

        Returns:
            bool: True if successful, False if task not found or invalid state
        """
        valid_states = ['planning', 'buffered', 'done']
        if state not in valid_states:
            return False

        task = self.get_task(task_id)
        if not task:
            return False

        task['state'] = state
        return True

    def set_aggressive_duration(self, task_id: int, duration: int) -> bool:
        """Set the aggressive duration for a task.

        Args:
            task_id: ID of the task
            duration: The aggressive duration in days

        Returns:
            bool: True if successful, False if task not found
        """
        task = self.get_task(task_id)
        if not task:
            return False

        task['aggressive_duration'] = duration
        return True

    def set_safe_duration(self, task_id: int, duration: int) -> bool:
        """Set the safe duration for a task.

        Args:
            task_id: ID of the task
            duration: The safe duration in days

        Returns:
            bool: True if successful, False if task not found
        """
        task = self.get_task(task_id)
        if not task:
            return False

        task['safe_duration'] = duration
        return True

    def set_fullkit_date(self, task_id: int) -> bool:
        """Set the full kit date to the current setdate.

        Args:
            task_id: ID of the task

        Returns:
            bool: True if successful, False if task not found
        """
        task = self.get_task(task_id)
        if not task:
            return False

        task['fullkit_date'] = self.setdate.isoformat()
        return True
