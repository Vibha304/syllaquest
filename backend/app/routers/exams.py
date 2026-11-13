"""VTU-pattern examination papers: generate per module, edit, share, export."""
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ExamPaper, Topic, User
from ..security import current_user
from ..services import exam, exporter
from .courses import get_course, is_enrolled, owned, viewable

router = APIRouter(prefix="/api", tags=["exam papers"])


class PaperIn(BaseModel):
    title: str = Field(default="", max_length=180)
    pattern: str = Field(default="see", pattern="^(see|cie|quiz)$")
    level: str = Field(default="balanced", pattern="^(foundational|balanced|advanced)$")
    topic_ids: list[int] = Field(min_length=1, max_length=8)
    semester: str = Field(default="", max_length=40)
    session: str = Field(default="", max_length=60)


class PartIn(BaseModel):
    text: str = Field(min_length=3)
    marks: int = Field(ge=1, le=50)
    bloom: str = Field(pattern="^L[1-6]$")
    scheme: list[str] = []


class QuestionIn(BaseModel):
    parts: list[PartIn] = Field(min_length=1, max_length=6)


class ModuleIn(BaseModel):
    topic_id: int | None = None
    topic: str
    co: str = ""
    questions: list[QuestionIn]


class PaperPatch(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=180)
    semester: str | None = None
    session: str | None = None
    shared: bool | None = None
    modules: list[ModuleIn] | None = None


def paper_out(paper: ExamPaper, is_owner: bool, full: bool = True) -> dict:
    modules = (paper.content or {}).get("modules", [])
    data = {
        "id": paper.id, "course_id": paper.course_id, "title": paper.title, "pattern": paper.pattern,
        "pattern_label": exam.PATTERNS[paper.pattern]["label"], "level": paper.level, "semester": paper.semester,
        "session": paper.session, "marks_per_question": paper.marks_per_question, "duration": paper.duration,
        "max_marks": paper.marks_per_question * len(modules), "shared": paper.shared, "is_owner": is_owner,
        "module_count": len(modules), "ready": all(m.get("questions") for m in modules) and bool(modules),
        "created_at": paper.created_at.isoformat(),
    }
    if full:
        data["modules"] = [
            {**m, "questions": [
                {"parts": [{**p, "scheme": p.get("scheme", []) if is_owner else []} for p in q["parts"]]}
                for q in m.get("questions", [])]}
            for m in modules]
    return data


def _paper(db: Session, user: User, paper_id: int, need_owner: bool = False) -> tuple[ExamPaper, bool]:
    paper = db.get(ExamPaper, paper_id)
    if not paper:
        raise HTTPException(404, "Question paper not found")
    course = get_course(db, paper.course_id)
    is_owner = course.owner_id == user.id
    if need_owner and not is_owner:
        raise HTTPException(403, "Only the course owner can do this")
    if not is_owner and not (paper.shared and is_enrolled(db, user, course)):
        raise HTTPException(403, "You do not have access to this question paper")
    return paper, is_owner


@router.get("/courses/{course_id}/papers")
def list_papers(course_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    course = viewable(db, user, course_id)
    is_owner = course.owner_id == user.id
    stmt = select(ExamPaper).where(ExamPaper.course_id == course.id).order_by(ExamPaper.id.desc())
    if not is_owner:
        stmt = stmt.where(ExamPaper.shared.is_(True))
    return [paper_out(p, is_owner, full=False) for p in db.scalars(stmt)]


@router.post("/courses/{course_id}/papers")
def create_paper(course_id: int, body: PaperIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Creates the paper shell; the client then generates each module (keeps every request short)."""
    course = owned(db, user, course_id)
    cfg = exam.PATTERNS[body.pattern]
    by_id = {t.id: t for t in course.topics}
    topics = [by_id[i] for i in dict.fromkeys(body.topic_ids) if i in by_id][: cfg["max_modules"]]
    if not topics:
        raise HTTPException(400, "Choose at least one topic of this course")
    paper = ExamPaper(
        course_id=course.id, title=body.title.strip() or f"{course.name} - {cfg['label']}", pattern=body.pattern,
        level=body.level, semester=body.semester.strip(), session=body.session.strip(),
        marks_per_question=cfg["marks_per_question"], duration=cfg["duration"],
        content={"modules": [{"topic_id": t.id, "topic": t.name, "co": f"CO{i + 1}", "questions": []}
                             for i, t in enumerate(topics)]},
    )
    db.add(paper)
    db.commit()
    return paper_out(paper, True)


@router.post("/papers/{paper_id}/modules/{index}/generate")
def generate_module(paper_id: int, index: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    paper, _ = _paper(db, user, paper_id, need_owner=True)
    modules = [dict(m) for m in paper.content.get("modules", [])]
    if not 0 <= index < len(modules):
        raise HTTPException(404, "Module not found")
    course = get_course(db, paper.course_id)
    topic = db.get(Topic, modules[index].get("topic_id") or 0)
    if not topic or topic.course_id != course.id:
        raise HTTPException(400, "The topic for this module no longer exists")
    version = int(modules[index].get("version", 0)) + 1
    questions, engine, note = exam.generate_module(
        course.name, topic, paper.marks_per_question, paper.level, f"{paper.id}-{index}-{version}")
    modules[index] = {**modules[index], "topic": topic.name, "questions": questions, "engine": engine, "version": version}
    paper.content = {"modules": modules}
    db.commit()
    return {"paper": paper_out(paper, True), "engine": engine, "note": note}


@router.get("/papers/{paper_id}")
def get_paper(paper_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    paper, is_owner = _paper(db, user, paper_id)
    return paper_out(paper, is_owner)


@router.patch("/papers/{paper_id}")
def update_paper(paper_id: int, body: PaperPatch, user: User = Depends(current_user), db: Session = Depends(get_db)):
    paper, _ = _paper(db, user, paper_id, need_owner=True)
    for field in ("title", "semester", "session"):
        value = getattr(body, field)
        if value is not None:
            setattr(paper, field, value.strip())
    if body.shared is not None:
        paper.shared = body.shared
    if body.modules is not None:
        old = paper.content.get("modules", [])
        modules = []
        for i, m in enumerate(body.modules):
            keep = old[i] if i < len(old) else {}
            modules.append({**keep, **m.model_dump()})
        paper.content = {"modules": modules}
    db.commit()
    return paper_out(paper, True)


@router.delete("/papers/{paper_id}")
def delete_paper(paper_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    paper, _ = _paper(db, user, paper_id, need_owner=True)
    db.delete(paper)
    db.commit()
    return {"ok": True}


@router.get("/papers/{paper_id}/export")
def export_paper(paper_id: int, kind: str = "paper", user: User = Depends(current_user),
                 db: Session = Depends(get_db)):
    paper, is_owner = _paper(db, user, paper_id)
    if kind == "scheme" and not is_owner:
        raise HTTPException(403, "The scheme of valuation is only available to the course owner")
    if kind not in ("paper", "scheme"):
        raise HTTPException(400, "kind must be paper or scheme")
    course = get_course(db, paper.course_id)
    data = exporter.exam_docx(course, paper_out(paper, True), scheme=kind == "scheme")
    slug = "".join(ch if ch.isalnum() else "_" for ch in paper.title)[:50] or "question_paper"
    suffix = "_scheme_of_valuation" if kind == "scheme" else ""
    return Response(data, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    headers={"Content-Disposition": f'attachment; filename="{slug}{suffix}.docx"'})
