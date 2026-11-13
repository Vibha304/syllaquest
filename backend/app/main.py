"""SyllaQuest - Gamified AI-based Syllabus-to-Quiz Learning System (API + static frontend)."""
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import config
from .database import Base, SessionLocal, engine
from .routers import auth, courses, exams, me, quiz
from .services import llm


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)
    if config.SEED_DEMO:
        from .seed import seed
        with SessionLocal() as db:
            seed(db)
    yield


app = FastAPI(title="SyllaQuest API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])

for r in (auth.router, courses.router, exams.router, quiz.router, me.router):
    app.include_router(r)


@app.get("/api/health")
def health():
    return {"status": "ok", "llm_provider": llm.provider()}


# ---- serve the built React app (single-service deployment) ------------------
DIST = config.FRONTEND_DIST
if (DIST / "index.html").exists():
    if (DIST / "assets").exists():
        app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404, "Not found")
        target = (DIST / path).resolve()
        if path and target.is_file() and DIST.resolve() in target.parents:
            return FileResponse(target)
        return FileResponse(DIST / "index.html")
