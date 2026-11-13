"""Courses (subjects), topics, question bank, generation, coverage, exports and
class analytics. Teachers own 'class' courses; students own 'personal' ones."""
import secrets

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import Integer as Integer_, delete, func, select
from sqlalchemy.orm import Session, selectinload

from .. import config
from ..database import get_db
from ..models import Attempt, Course, Enrollment, ExamPaper, Mastery, Question, QuizSession, Topic, User
from ..security import current_user
from ..services import bkt, exporter, gamification as game, generator, llm
from ..services.parser import ParseError, parse_document
from ..services.topics import extract_topics

router = APIRouter(prefix="/api", tags=["courses"])


# ------------------------------------------------------------------ helpers
def get_course(db: Session, course_id: int) -> Course:
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(404, "Course not found")
    return course


def is_enrolled(db: Session, user: User, course: Course) -> bool:
    return db.scalar(select(Enrollment.id).where(
        Enrollment.user_id == user.id, Enrollment.course_id == course.id)) is not None


def viewable(db: Session, user: User, course_id: int) -> Course:
    course = get_course(db, course_id)
    if course.owner_id != user.id and not is_enrolled(db, user, course):
        raise HTTPException(403, "You do not have access to this course")
    return course


def owned(db: Session, user: User, course_id: int) -> Course:
    course = get_course(db, course_id)
    if course.owner_id != user.id:
        raise HTTPException(403, "Only the course owner can do this")
    return course


def _join_code(db: Session) -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    while True:
        code = "".join(secrets.choice(alphabet) for _ in range(6))
        if not db.scalar(select(Course.id).where(Course.join_code == code)):
            return code


def question_out(q: Question, topic_name: str | None = None) -> dict:
    return {
        "id": q.id, "topic_id": q.topic_id, "topic": topic_name or q.topic.name, "type": q.qtype,
        "difficulty": q.difficulty, "bloom": q.bloom, "text": q.text, "options": q.options or [],
        "answer": q.answer, "explanation": q.explanation, "keywords": q.keywords or [],
        "source_excerpt": q.source_excerpt, "status": q.status, "origin": q.origin,
    }


def _question_counts(db: Session, course_ids: list[int]) -> dict:
    rows = db.execute(
        select(Question.course_id, Question.topic_id, Question.difficulty, Question.status, func.count(Question.id))
        .where(Question.course_id.in_(course_ids))
        .group_by(Question.course_id, Question.topic_id, Question.difficulty, Question.status)
    ).all()
    out: dict = {}
    for cid, tid, diff, status, n in rows:
        c = out.setdefault(cid, {"approved": 0, "draft": 0, "topics": {}})
        c[status] = c.get(status, 0) + n
        t = c["topics"].setdefault(tid, {"easy": 0, "medium": 0, "hard": 0, "total": 0, "draft": 0})
        if status == "approved":
            t[diff] += n
            t["total"] += n
        else:
            t["draft"] += n
    return out


def course_out(db: Session, user: User, course: Course, counts: dict, detail: bool = False) -> dict:
    is_owner = course.owner_id == user.id
    c = counts.get(course.id, {"approved": 0, "draft": 0, "topics": {}})
    mastery = {m.topic_id: m for m in db.scalars(
        select(Mastery).where(Mastery.user_id == user.id, Mastery.course_id == course.id))}
    topics = course.topics
    ps = [mastery[t.id].p if t.id in mastery else 0.0 for t in topics]
    states = [bkt.status(mastery[t.id].p, mastery[t.id].attempts) if t.id in mastery else "new" for t in topics]
    data = {
        "id": course.id, "name": course.name, "code": course.code, "description": course.description,
        "kind": course.kind, "published": course.published, "is_owner": is_owner,
        "owner_name": course.owner.name, "source_name": course.source_name,
        "extraction_method": course.extraction_method,
        "join_code": course.join_code if is_owner else None,
        "topic_count": len(topics), "question_count": c["approved"],
        "draft_count": c["draft"] if is_owner else 0,
        "mastery": round(sum(ps) / len(ps), 4) if ps else 0.0,
        "weak_count": states.count("weak"), "mastered_count": states.count("mastered"),
        "created_at": course.created_at.isoformat(),
    }
    if is_owner:
        data["student_count"] = db.scalar(
            select(func.count(Enrollment.id)).where(Enrollment.course_id == course.id)) or 0
    if detail:
        data["topics"] = []
        for t, state in zip(topics, states):
            m = mastery.get(t.id)
            data["topics"].append({
                "id": t.id, "name": t.name, "summary": t.summary, "keywords": t.keywords or [],
                "position": t.position, "words": len((t.content or "").split()),
                "content": t.content if is_owner else None,
                "counts": c["topics"].get(t.id, {"easy": 0, "medium": 0, "hard": 0, "total": 0, "draft": 0}),
                "mastery": {"p": m.p if m else 0.0, "attempts": m.attempts if m else 0,
                            "correct": m.correct if m else 0, "status": state},
            })
    return data


# ------------------------------------------------------------------ courses
@router.get("/meta")
def meta():
    p = llm.provider()
    return {"llm_provider": p, "llm_model": llm.model_name(), "ai_enabled": p != "offline",
            "max_upload_mb": config.MAX_UPLOAD_MB}


@router.get("/courses")
def list_courses(user: User = Depends(current_user), db: Session = Depends(get_db)):
    enrolled = select(Enrollment.course_id).where(Enrollment.user_id == user.id)
    courses = db.scalars(
        select(Course).where((Course.owner_id == user.id) | Course.id.in_(enrolled))
        .options(selectinload(Course.topics), selectinload(Course.owner)).order_by(Course.created_at.desc())
    ).all()
    counts = _question_counts(db, [c.id for c in courses]) if courses else {}
    return [course_out(db, user, c, counts) for c in courses]


@router.post("/courses")
async def create_course(
    name: str = Form(..., min_length=2, max_length=160),
    code: str = Form(""),
    description: str = Form(""),
    text: str = Form(""),
    file: UploadFile | None = File(None),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    topics, method, source = [], "manual", ""
    try:
        if file is not None and file.filename:
            data = await file.read()
            if len(data) > config.MAX_UPLOAD_MB * 1024 * 1024:
                raise HTTPException(413, f"File is larger than {config.MAX_UPLOAD_MB} MB")
            topics, method = extract_topics(parse_document(file.filename, data))
            source = file.filename
        elif text.strip():
            topics, method = extract_topics(parse_document("pasted.txt", text.encode("utf-8")))
            source = "Pasted text"
    except ParseError as exc:
        raise HTTPException(422, str(exc)) from exc

    course = Course(
        owner_id=user.id, name=name.strip(), code=code.strip()[:40], description=description.strip(),
        kind="class" if user.role == "teacher" else "personal", join_code=_join_code(db),
        source_name=source[:300], extraction_method=method,
    )
    for i, t in enumerate(topics):
        course.topics.append(Topic(name=t["name"], summary=t["summary"], content=t["content"],
                                   keywords=t["keywords"], position=i))
    db.add(course)
    db.flush()
    if user.role == "student" and topics:
        game.award(db, user, ["curator"])
    db.commit()
    db.refresh(course)
    return course_out(db, user, course, {}, detail=True)


@router.get("/courses/{course_id}")
def course_detail(course_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    course = viewable(db, user, course_id)
    return course_out(db, user, course, _question_counts(db, [course.id]), detail=True)


class CoursePatch(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    code: str | None = None
    description: str | None = None
    published: bool | None = None


@router.patch("/courses/{course_id}")
def update_course(course_id: int, body: CoursePatch, user: User = Depends(current_user),
                  db: Session = Depends(get_db)):
    course = owned(db, user, course_id)
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(course, field, value.strip() if isinstance(value, str) else value)
    db.commit()
    return course_out(db, user, course, _question_counts(db, [course.id]), detail=True)


@router.delete("/courses/{course_id}")
def delete_course(course_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    course = owned(db, user, course_id)
    for model in (Attempt, Mastery, QuizSession, Enrollment, ExamPaper):
        db.execute(delete(model).where(model.course_id == course.id))
    db.delete(course)
    db.commit()
    return {"ok": True}


class JoinIn(BaseModel):
    code: str


@router.post("/courses/join")
def join_course(body: JoinIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    course = db.scalar(select(Course).where(Course.join_code == body.code.strip().upper()))
    if not course or course.kind != "class" or not course.published:
        raise HTTPException(404, "No published class matches that code")
    if course.owner_id == user.id:
        raise HTTPException(400, "You own this course")
    if not is_enrolled(db, user, course):
        db.add(Enrollment(user_id=user.id, course_id=course.id))
        db.commit()
    return {"id": course.id, "name": course.name}


@router.delete("/courses/{course_id}/enrollment")
def leave_course(course_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.execute(delete(Enrollment).where(Enrollment.user_id == user.id, Enrollment.course_id == course_id))
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------------- topics
class TopicIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    content: str = ""
    keywords: list[str] = []


class TopicPatch(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    content: str | None = None
    keywords: list[str] | None = None


def _clean_keywords(keywords: list[str]) -> list[str]:
    return list(dict.fromkeys(k.strip() for k in keywords if k.strip()))[:20]


@router.post("/courses/{course_id}/topics")
def add_topic(course_id: int, body: TopicIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    course = owned(db, user, course_id)
    content = body.content.strip()
    keywords = _clean_keywords(body.keywords)
    if content and not keywords:
        extracted, _ = extract_topics([{"text": content, "heading": False}])
        keywords = extracted[0]["keywords"] if extracted else []
    topic = Topic(course_id=course.id, name=body.name.strip(), content=content, keywords=keywords,
                  summary=content[:280], position=len(course.topics))
    db.add(topic)
    db.commit()
    return {"id": topic.id}


@router.patch("/topics/{topic_id}")
def update_topic(topic_id: int, body: TopicPatch, user: User = Depends(current_user),
                 db: Session = Depends(get_db)):
    topic = db.get(Topic, topic_id)
    if not topic:
        raise HTTPException(404, "Topic not found")
    owned(db, user, topic.course_id)
    if body.name is not None:
        topic.name = body.name.strip()
    if body.content is not None:
        topic.content = body.content.strip()
        topic.summary = topic.content[:280]
    if body.keywords is not None:
        topic.keywords = _clean_keywords(body.keywords)
    db.commit()
    return {"ok": True}


@router.delete("/topics/{topic_id}")
def delete_topic(topic_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    topic = db.get(Topic, topic_id)
    if not topic:
        raise HTTPException(404, "Topic not found")
    owned(db, user, topic.course_id)
    for model in (Attempt, Mastery):
        db.execute(delete(model).where(model.topic_id == topic.id))
    db.delete(topic)
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------- questions
class GenerateIn(BaseModel):
    topic_id: int
    count: int = Field(default=6, ge=1, le=15)
    types: list[str] = ["mcq", "tf"]
    difficulties: list[str] = ["easy", "medium", "hard"]


@router.post("/courses/{course_id}/generate")
def generate(course_id: int, body: GenerateIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    course = owned(db, user, course_id)
    topic = db.get(Topic, body.topic_id)
    if not topic or topic.course_id != course.id:
        raise HTTPException(404, "Topic not found in this course")
    existing = list(db.scalars(select(Question.text).where(Question.topic_id == topic.id)))
    items, engine, note = generator.generate_questions(
        course.name, topic, course.topics, body.count, body.types, body.difficulties, existing)
    # Teacher-generated items wait for review; a student's own practice set is usable immediately.
    status = "draft" if course.kind == "class" else "approved"
    created = []
    for item in items:
        q = Question(course_id=course.id, topic_id=topic.id, status=status, **item)
        db.add(q)
        created.append(q)
    db.commit()
    return {"created": [question_out(q, topic.name) for q in created], "engine": engine, "note": note,
            "requested": body.count}


@router.get("/courses/{course_id}/questions")
def list_questions(course_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    course = owned(db, user, course_id)
    names = {t.id: t.name for t in course.topics}
    rows = db.scalars(select(Question).where(Question.course_id == course.id).order_by(Question.id.desc()))
    return [question_out(q, names.get(q.topic_id, "")) for q in rows]


class QuestionIn(BaseModel):
    topic_id: int
    type: str = Field(pattern="^(mcq|tf|short)$")
    difficulty: str = Field(pattern="^(easy|medium|hard)$")
    bloom: str = "remember"
    text: str = Field(min_length=8)
    options: list[str] = []
    answer: str = Field(min_length=1)
    explanation: str = ""
    keywords: list[str] = []
    status: str = Field(default="approved", pattern="^(approved|draft)$")


def _validated(body: QuestionIn) -> dict:
    raw = body.model_dump()
    raw["question"] = raw.pop("text")
    q = generator.normalize_question(raw)
    if q is None:
        raise HTTPException(422, "Invalid question: MCQs need at least 3 distinct options including the answer; "
                                 "True/False answers must be True or False.")
    if body.type == "mcq":
        q["options"] = [o.strip() for o in body.options if o.strip()][:6]  # keep the author's order
    return q


@router.post("/courses/{course_id}/questions")
def add_question(course_id: int, body: QuestionIn, user: User = Depends(current_user),
                 db: Session = Depends(get_db)):
    course = owned(db, user, course_id)
    topic = db.get(Topic, body.topic_id)
    if not topic or topic.course_id != course.id:
        raise HTTPException(404, "Topic not found in this course")
    q = Question(course_id=course.id, topic_id=topic.id, status=body.status, origin="manual", **_validated(body))
    db.add(q)
    db.commit()
    return question_out(q, topic.name)


@router.put("/questions/{question_id}")
def update_question(question_id: int, body: QuestionIn, user: User = Depends(current_user),
                    db: Session = Depends(get_db)):
    q = db.get(Question, question_id)
    if not q:
        raise HTTPException(404, "Question not found")
    course = owned(db, user, q.course_id)
    topic = db.get(Topic, body.topic_id)
    if not topic or topic.course_id != course.id:
        raise HTTPException(404, "Topic not found in this course")
    for field, value in _validated(body).items():
        if field != "source_excerpt":
            setattr(q, field, value)
    q.topic_id, q.status = topic.id, body.status
    db.commit()
    return question_out(q, topic.name)


class BulkIn(BaseModel):
    ids: list[int]
    action: str = Field(pattern="^(approve|draft|delete)$")


@router.post("/courses/{course_id}/questions/bulk")
def bulk_questions(course_id: int, body: BulkIn, user: User = Depends(current_user),
                   db: Session = Depends(get_db)):
    course = owned(db, user, course_id)
    rows = db.scalars(select(Question).where(Question.course_id == course.id, Question.id.in_(body.ids))).all()
    if body.action == "delete":
        ids = [q.id for q in rows]
        db.execute(delete(Attempt).where(Attempt.question_id.in_(ids)))
        for q in rows:
            db.delete(q)
    else:
        for q in rows:
            q.status = "approved" if body.action == "approve" else "draft"
    db.commit()
    return {"affected": len(rows)}


# ------------------------------------------------------- coverage & exports
@router.get("/courses/{course_id}/coverage")
def coverage(course_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Syllabus-coverage matrix: how many questions exist per topic x difficulty / Bloom / type."""
    course = owned(db, user, course_id)
    rows = db.scalars(select(Question).where(Question.course_id == course.id)).all()
    topics = []
    for t in course.topics:
        qs = [q for q in rows if q.topic_id == t.id]
        topics.append({
            "id": t.id, "name": t.name, "total": len(qs),
            "approved": sum(q.status == "approved" for q in qs),
            "difficulty": {d: sum(q.difficulty == d for q in qs) for d in generator.DIFFICULTIES},
            "bloom": {b: sum(q.bloom == b for q in qs) for b in generator.BLOOMS},
            "type": {k: sum(q.qtype == k for q in qs) for k in generator.QTYPES},
        })
    return {"topics": topics, "total": len(rows),
            "uncovered": [t["name"] for t in topics if t["total"] == 0]}


@router.get("/courses/{course_id}/export")
def export(course_id: int, format: str = "docx", answers: bool = True, status: str = "approved",
           user: User = Depends(current_user), db: Session = Depends(get_db)):
    course = owned(db, user, course_id)
    stmt = select(Question).where(Question.course_id == course.id).options(selectinload(Question.topic))
    if status == "approved":
        stmt = stmt.where(Question.status == "approved")
    order = {t.id: t.position for t in course.topics}
    questions = sorted(db.scalars(stmt).all(), key=lambda q: (order.get(q.topic_id, 0), q.id))
    if not questions:
        raise HTTPException(400, "There are no questions to export yet")
    slug = "".join(ch if ch.isalnum() else "_" for ch in course.name)[:40] or "question_bank"
    if format == "csv":
        data, mime, ext = exporter.to_csv(course, questions), "text/csv", "csv"
    elif format == "json":
        data, mime, ext = exporter.to_json(course, questions), "application/json", "json"
    elif format == "docx":
        data = exporter.to_docx(course, questions, answers)
        mime, ext = "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "docx"
    else:
        raise HTTPException(400, "format must be docx, csv or json")
    return Response(data, media_type=mime,
                    headers={"Content-Disposition": f'attachment; filename="{slug}_question_bank.{ext}"'})


# ---------------------------------------------------------- class analytics
def _course_board(db: Session, course: Course) -> list[dict]:
    rows = db.execute(
        select(User.id, User.name, func.coalesce(func.sum(Attempt.xp), 0), func.count(Attempt.id),
               func.coalesce(func.sum(func.cast(Attempt.correct, Integer_)), 0))
        .join(Attempt, Attempt.user_id == User.id)
        .where(Attempt.course_id == course.id, User.role == "student")
        .group_by(User.id, User.name)
    ).all()
    board = [{"user_id": uid, "name": name, "xp": int(xp), "answered": n,
              "accuracy": round(int(c) / n, 3) if n else 0, "level": game.level_info(int(xp))["level"]}
             for uid, name, xp, n, c in rows]
    board.sort(key=lambda r: (-r["xp"], -r["accuracy"], r["name"]))
    for i, r in enumerate(board, 1):
        r["rank"] = i
    return board



@router.get("/courses/{course_id}/leaderboard")
def course_leaderboard(course_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    course = viewable(db, user, course_id)
    return {"course": course.name, "rows": _course_board(db, course), "me": user.id}


@router.get("/courses/{course_id}/class-analytics")
def class_analytics(course_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    course = owned(db, user, course_id)
    topics = course.topics
    students = db.scalars(
        select(User).join(Enrollment, Enrollment.user_id == User.id).where(Enrollment.course_id == course.id)
    ).all()
    mastery = db.scalars(select(Mastery).where(Mastery.course_id == course.id)).all()
    by_user: dict[int, dict[int, Mastery]] = {}
    for m in mastery:
        by_user.setdefault(m.user_id, {})[m.topic_id] = m
    board = {r["user_id"]: r for r in _course_board(db, course)}

    student_rows = []
    for s in students:
        ms = by_user.get(s.id, {})
        ps = [ms[t.id].p if t.id in ms else 0.0 for t in topics]
        weak = [t.name for t in topics if t.id in ms and bkt.status(ms[t.id].p, ms[t.id].attempts) == "weak"]
        b = board.get(s.id, {})
        student_rows.append({
            "id": s.id, "name": s.name, "email": s.email, "xp": b.get("xp", 0), "answered": b.get("answered", 0),
            "accuracy": b.get("accuracy", 0), "mastery": round(sum(ps) / len(ps), 3) if ps else 0,
            "weak_topics": weak, "last_active": s.last_active.isoformat() if s.last_active else None,
            "topic_mastery": {t.id: round(ms[t.id].p, 3) if t.id in ms else None for t in topics},
        })
    student_rows.sort(key=lambda r: -r["xp"])

    stats = {tid: (n, int(c or 0)) for tid, n, c in db.execute(
        select(Attempt.topic_id, func.count(Attempt.id), func.sum(func.cast(Attempt.correct, Integer_)))
        .where(Attempt.course_id == course.id).group_by(Attempt.topic_id))}
    topic_rows = []
    for t in topics:
        ms = [m for m in mastery if m.topic_id == t.id and m.attempts > 0]
        n, c = stats.get(t.id, (0, 0))
        topic_rows.append({
            "id": t.id, "name": t.name, "attempts": n, "accuracy": round(c / n, 3) if n else None,
            "avg_mastery": round(sum(m.p for m in ms) / len(ms), 3) if ms else None,
            "students_practised": len(ms),
            "weak_students": sum(bkt.status(m.p, m.attempts) == "weak" for m in ms),
            "mastered_students": sum(bkt.status(m.p, m.attempts) == "mastered" for m in ms),
        })

    hardest = []
    for qid, n, c in db.execute(
        select(Attempt.question_id, func.count(Attempt.id), func.sum(func.cast(Attempt.correct, Integer_)))
        .where(Attempt.course_id == course.id).group_by(Attempt.question_id)
        .having(func.count(Attempt.id) >= 3)
    ):
        hardest.append((int(c or 0) / n, n, qid))
    hardest.sort()
    tough = []
    for acc, n, qid in hardest[:6]:
        q = db.get(Question, qid)
        if q and acc < 0.7:
            tough.append({"id": q.id, "text": q.text, "topic": q.topic.name, "difficulty": q.difficulty,
                          "accuracy": round(acc, 3), "attempts": n})
    total_attempts = sum(r["attempts"] for r in topic_rows)
    return {"students": student_rows, "topics": topic_rows, "hardest_questions": tough,
            "total_attempts": total_attempts, "student_count": len(students)}
