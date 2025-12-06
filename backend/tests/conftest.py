import sys
import os
import pytest

# Add backend to path so services/ can be imported
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
