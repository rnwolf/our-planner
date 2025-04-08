# Getting Started with Our-Planner

## Prerequisites

*   Python 3.12 or higher

## Installation

1.  Clone the repository:

    ```bash
    git clone https://github.com/your-username/our-planner.git
    ```

2.  Navigate to the project directory:

    ```bash
    cd our-planner
    ```

3.  Install the required packages:

    ```bash
    pip install -r requirements.txt
    ```

## Running the Application

To start the application, run:

```bash
python src/main.py
```

## Installation

### Prerequisites

- Python 3.11 or higher
- Tkinter (The GUI library which usually comes with Python)

#### macOS

```
brew install python3 # Install Python
brew install python-tk # Install Tkinter
```

#### Ubuntu (Linux)

```
sudo apt-get install python3-tk
```

#### Fedora (Linux)

```
sudo dnf install python3-tkinter
```

#### MS-Windows

Tkinter is usually installed by default with every Python installation on MS-Windows. There is currently a problem with UV installed versions of Python!

### Install from source

```
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

```
pip install -r requirements.txt
```

### Install from PyPi

```
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

```

# Install and run app on MS-Windows
uvx -p "C:\Python313\python.exe" our-planner@latest
```

NOTE: The python builds provided via UV does not include the Tkinter libraries, and thus you need to install and specify Python from [https://www.python.org/downloads/
](https://www.python.org/downloads/)
