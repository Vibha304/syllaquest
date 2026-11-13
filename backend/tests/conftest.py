"""Every test run uses a fresh temporary SQLite database and the offline generator."""
import os
import tempfile

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/test.db"
os.environ["LLM_PROVIDER"] = "offline"
os.environ["SEED_DEMO"] = "true"
