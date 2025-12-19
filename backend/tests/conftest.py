import sys
import os

# Add backend to path so services/ can be imported
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock Env Vars
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost:5432/db")


