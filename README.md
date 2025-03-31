# Task Resource Manager

A Python application for managing tasks and resources with timeline visualization. This tool helps you create and manage project schedules with resource allocation and dependency tracking.

## Features

- Create and manage tasks with durations, dependencies, and resource allocations
- Visualize tasks in a timeline view
- Track resource loading and avoid over-allocation
- Tag-based filtering for tasks and resources
- Export to PDF, PNG, CSV, and HTML formats
- Critical path analysis
- Multi-select and bulk operations

## Installation

### Prerequisites

- Python 3.8 or higher
- Tkinter (usually comes with Python)

### Install from source

```bash
# Clone the repository
git clone https://github.com/yourusername/task-resource-manager.git
cd task-resource-manager

# Create and activate a virtual environment (optional but recommended)
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install the package and dependencies
pip install -e .
```

### Install dependencies only

```bash
pip install -r requirements.txt
```

## Usage

### Running the application

```bash
# If installed as a package
task-resource-manager

# Or run directly
python run.py
```

### Basic operations

1. **Create tasks**: Click and drag on the task grid to create new tasks
2. **Move tasks**: Click and drag existing tasks to reposition them
3. **Resize tasks**: Click and drag the left or right edge of a task
4. **Add dependencies**: Click the connector circle on the right edge of a task and drag to another task
5. **Edit task details**: Right-click on a task and select from the context menu
6. **Export your project**: Use the File menu to export your project in various formats

## Development

### Project Structure

```
task_resource_manager/
├── src/                       # Main source code directory
│   ├── model/                 # Model components
│   ├── view/                  # View components
│   ├── controller/            # Controller components
│   ├── operations/            # Business logic operations
│   └── utils/                 # Utility and helper functions
├── resources/                 # Static resources
├── tests/                     # Test directory
├── docs/                      # Documentation
└── examples/                  # Example files
```

### Running tests

```bash
pytest
```

## License

[MIT License](LICENSE)
