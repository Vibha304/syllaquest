"""Central configuration. Everything is driven by environment variables so the
same code runs locally (SQLite, offline generator) and in the cloud
(PostgreSQL, free-tier LLM API)."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    """Tiny .env loader (avoids an extra dependency)."""
    for candidate in (BASE_DIR / ".env", BASE_DIR.parent / ".env"):
        if not candidate.exists():
            continue
        for line in candidate.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()


def _db_url() -> str:
    url = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'syllaquest.db'}")
    # Hosted Postgres providers hand out postgres:// or postgresql:// URLs.
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


DATABASE_URL = _db_url()
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me-in-production-please")
TOKEN_HOURS = int(os.getenv("TOKEN_HOURS", "168"))
SEED_DEMO = os.getenv("SEED_DEMO", "true").lower() in ("1", "true", "yes")
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "15"))
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]

# --- LLM providers (all have a free option) ---------------------------------
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "auto").lower()  # auto|gemini|groq|ollama|offline
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
OLLAMA_URL = os.getenv("OLLAMA_URL", "")  # e.g. http://localhost:11434
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "60"))

FRONTEND_DIST = Path(os.getenv("FRONTEND_DIST", BASE_DIR.parent / "frontend" / "dist"))
