# # Old imports
# from model import TaskResourceModel
# from ui_components import UIComponents

# # New imports
# from src.model.task_resource_model import TaskResourceModel
# from src.view.ui_components import UIComponents

#!/usr/bin/env python3
"""
Our-Planner - Entry point script

This script runs the Our-Planner application.
"""

import sys
import os

# Add the project root directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.main import main

if __name__ == '__main__':
    main()
