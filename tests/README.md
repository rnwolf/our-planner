# Task Resource Manager Tests

This directory contains the tests for the Task Resource Manager application.

## Running Tests

You can run the tests in several ways:

### Using the run_tests.py script

The simplest way is to use the provided script:

```bash
python run_tests.py
```

### Using pytest directly

You can also run pytest directly from the project root:

```bash
pytest
```

Or with specific options:

```bash
# Run tests with verbose output
pytest -v

# Run tests with code coverage report
pytest --cov=.

# Run a specific test file
pytest tests/test_model.py

# Run a specific test
pytest tests/test_model.py::TestTaskResourceModel::test_add_task
```

## Test Organization

The tests are organized as follows:

- `test_model.py`: Tests for the TaskResourceModel class
- Additional test files will be added as the application grows

## Adding New Tests

When adding new tests:

1. Create a new test file named `test_*.py` in the tests directory
2. Create test classes named `Test*`
3. Create test methods named `test_*`

For example:

```python
# tests/test_controller.py
import pytest
from task_manager import TaskResourceManager

class TestTaskResourceManager:
    def test_something(self):
        # Test code here
        pass
```

## Test Dependencies

The tests require the following packages:
- pytest
- pytest-cov
- tkcalendar
- reportlab