# Our-Planner

An application for collaboratively working on plans with our team. Planning can take resource availability into account. Timeline visualisation for tasks and resources makes it easy to modify and sense check.  Buffer management features provide early indicators that actual and planned activity requires intervention.

## Why another planning tool?

Good plans are co-created with the team that will do the work. For that digital whiteboarding tools such as Miro & Mural are very helpful to map out features and dependencies.
Invariably the question is going to be asked "When will you be done?".
The team will need to make some estimates of how long the individual tasks are going to take. This requires caputing data on estimates and taking into account the availability of the people required to do the work. The current crop of whiteboarding tools do not make this easy.
Quickly moving araound dependant tasks, with updated durations, on a timeline takes so much effort, it kills collaboration.

There are many excellent commercial tools in the market that could do the job but as a consultant to large enterprises it's not practical to change the existing corporate planning and task management tooling stack. Consequently I needed;

 - a free application as I can't expect the corporate to buy software just for a few teams I work with
 - to keep all the corporate data secure in a locally run application, no cloud service here!
 - to link tasks to the corporate task management tool, like Jira
 - I needed source code to be open for inspection by corporate security professionals

Thus this app is written in Python, which is the data analysts' tool of choice, and should be available in most enterprise user desktop builds. Code is hosted on Github and open for inspection, with releases distributed on PyPi for easy installation.

## Features

- Easily create and manage tasks with durations, dependencies, and resource allocations
- Visualise tasks in a timeline view
- Visualise resource loading and avoid over-allocation
- Tag-based filtering for tasks and resources
- Multi-select tasks for bulk operations
- Export tasks to PDF, PNG, CSV, and HTML formats
- Select tasks for Critical Path analysis

### Todo

- Multi-point estimates, for **safe** and **optimistic** estimates
- Adding **dated notes** to tasks
- **Remaining** days estimate for tasks (Updates duration and pushes or pulls in dependent tasks)
- Shift the timeframe on i.e. drop dates in the past and add dates in the future to planning timeline
- CCPM features such as buffer creation and feverchart reporting
- Reporting for resource, working on now and next tasks, with buffer status to help prioritise which tasks should get focus

## Installation

### Prerequisites

- Python 3.11 or higher
- Tkinter (usually comes with Python)

#### macOS

```bash
brew install python3 # Install Python
brew install python-tk # Install Tkinter
```

#### Ubuntu (Linux)

```bash
sudo apt-get install python3-tk
```

#### Fedora (Linux)

```bash
sudo dnf install python3-tkinter
```

#### MS-Windows

Tkinter is installed by default with every Python installation on MS-Windows.

### Install from source

```bash
# Clone the repository
git clone https://github.com/rnwolf/our-planner.git
cd our-planner

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install the package and dependencies
pip install -r requirements.txt

# Install the package
pip install -e .
```

### Install dependencies only

```bash
pip install -r requirements.txt
```

### Install from PyPi

```bash
cd our-planner
# Create and activate a virtual environment (optional but recommended)
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

pip install our-planner

# Run app
our-planner
```

### Install from via uvx (Recomended way)

[Install uv](https://docs.astral.sh/uv/getting-started/installation/).

This also installs the tool `uvx`. See more options on astral [website](https://docs.astral.sh/uv/guides/tools/).

```bash

# Install and run app
uvx -p "C:\Python313\python.exe" our-planner@latest
```

NOTE: The python builds provided via UV does not include the Tkinter libraries, and thus you need to install and specify Python from https://www.python.org/downloads/

### Basic operations

1. **Create tasks**: Click and drag on the task grid to create new tasks
2. **Move tasks**: Click and drag existing tasks to reposition them
3. **Resize tasks duration**: Click and drag the left or right edge of a task
4. **Add dependencies**: Click the connector circle on the right edge of a task and drag to another task
5. **Edit task details**: Right-click on a task and select from the context menu
6. **Zoom in and out**: See details and overview with Ctrl+Scroll-wheel to zoom in and out
7. **Export your data**: Use the File menu to export your data in various formats

## Development

### Application code structure

```
our-planner/
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

or

```bash
python run_test.py
```

## Licence

Our-planner is distributed under the terms of the [GPLv3 or later Licence](https://spdx.org/licenses/GPL-3.0-or-later.html).

## Changelog

See [CHANGELOG.md](https://github.com/rnwolf/our-planner/blob/main/CHANGELOG.md) on GitHub.