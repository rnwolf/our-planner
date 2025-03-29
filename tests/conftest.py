import pytest
import sys
import os

# This allows importing the application modules from tests
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
