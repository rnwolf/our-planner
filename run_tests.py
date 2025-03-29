#!/usr/bin/env python3
"""
Simple script to run pytest with proper arguments.
You can run this directly instead of typing the pytest command.
"""

import os
import sys
import pytest

if __name__ == "__main__":
    # Change to the project's root directory
    project_root = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_root)

    # Add arguments for pytest
    pytest_args = [
        "--verbose",  # Verbose output
        # Add any other pytest arguments here
    ]

    # Add any command line arguments passed to this script
    pytest_args.extend(sys.argv[1:])

    # Run pytest
    sys.exit(pytest.main(pytest_args))
