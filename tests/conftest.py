# tests/conftest.py — shared pytest fixtures and path setup
import sys
import os

# Make sure project root is on the path for all test files
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
