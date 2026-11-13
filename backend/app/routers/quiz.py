"""Module 4 + 5 - gamified, adaptive quiz engine."""
import random

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Attempt, Mastery, Question, QuizSession, Topic, User, now
from ..security import current_user
from ..services import adaptive, bkt, gamification as game, grading
from .auth import user_out
from .courses import viewable

router = APIRouter(prefix="/api/quiz", tags=["quiz"])


class StartIn(BaseModel):
    course_id: int
    topic_ids: list[int] = []
    types: list[str] = []
    length: int = Field(default=10, ge=3, le=30)
    seconds_per_question: int = Field(default=45, ge=0, le=300)


class AnswerIn(BaseModel):
    question_id: int
    answer: str = ""
    time_ms: int = Field(default=0, ge=0)


def public_question(db: Session, q: Question, session: QuizSession) -> dict:
    """What the student sees - never includes the answer."""
    options = list(q.options or [])
    if q.qtype == "mcq":
        random.Random(f"{session.id}-{q.id}").shuffle(options)
    return {"id": q.id, "type": q.qtype, "text": q.text, "options": options, "difficulty": q.difficulty,
            "bloom": q.bloom, "topic": {"id": q.topic_id, "name": q.topic.name},
            "reason": session.current_reason, "number": session.answered + 1, "total": session.length,
            "seconds": session.seconds_per_question}


def _session(db: Session, user: User, session_id: int) -> QuizSession:
    session = db.get(QuizSession, session_id)
    if not session or session.user_id != user.id:
        raise HTTPException(404, "Quiz session not found")
    return session


@router.post("/start")
def start(body: StartIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    course = viewable(db, user, body.course_id)
    stmt = select(func.count(Question.id)).where(Question.course_id == course.id, Question.status == "approved")
    if body.topic_ids:
        stmt = stmt.where(Question.topic_id.in_(body.topic_ids))
    if body.types:
        stmt = stmt.where(Question.qtype.in_(body.types))
    available = db.scalar(stmt) or 0
    if available == 0:
        raise HTTPException(400, "No questions are available for this selection yet")
    session = QuizSession(
        user_id=user.id, course_id=course.id, topic_ids=body.topic_ids, qtypes=body.types,
        length=min(body.length, available), seconds_per_question=body.seconds_per_question,
        asked=[], levels={},
    )
    db.add(session)
    db.flush()
    question, reason = adaptive.next_question(db, session)
    session.current_qid, session.current_reason = question.id, reason
    db.commit()
    return {"session_id": session.id, "course": {"id": course.id, "name": course.name},
            "question": public_question(db, question, session)}


@router.get("/{session_id}")
def resume(session_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    session = _session(db, user, session_id)
    if session.finished_at or not session.current_qid:
        return {"finished": True}
    q = db.get(Question, session.current_qid)
    return {"finished": False, "session_id": session.id, "question": public_question(db, q, session),
            "combo": session.combo, "xp": session.xp, "correct": session.correct}


@router.post("/{session_id}/answer")
def answer(session_id: int, body: AnswerIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    session = _session(db, user, session_id)
    if session.finished_at:
        raise HTTPException(400, "This quiz is already finished")
    if body.question_id != session.current_qid:
        raise HTTPException(409, "That is not the current question")
    q = db.get(Question, body.question_id)
    correct = grading.grade(q, body.answer)

    # --- knowledge tracing -------------------------------------------------
    m = db.scalar(select(Mastery).where(Mastery.user_id == user.id, Mastery.topic_id == q.topic_id))
    if m is None:
        mix = dict(db.execute(select(Question.difficulty, func.count(Question.id))
                              .where(Question.topic_id == q.topic_id).group_by(Question.difficulty)).all())
        m = Mastery(user_id=user.id, topic_id=q.topic_id, course_id=q.course_id, p=bkt.prior_for(mix),
                    attempts=0, correct=0)
        db.add(m)
    before = m.p
    m.p = bkt.update(m.p, correct, q.qtype, q.difficulty)
    m.attempts += 1
    m.correct += int(correct)
    m.updated_at = now()
    state = bkt.status(m.p, m.attempts)
    if state == "weak":
        m.was_weak = True

    # --- gamification ------------------------------------------------------
    old_level = game.level_info(user.xp)["level"]
    session.combo = session.combo + 1 if correct else 0
    session.best_combo = max(session.best_combo, session.combo)
    earned = game.xp_for(q.difficulty, session.combo, body.time_ms) if correct else 0
    game.touch_streak(user)
    session.answered += 1
    session.correct += int(correct)
    session.asked = [*(session.asked or []), q.id]
    adaptive.step_level(session, q.topic_id, correct)

    attempt = Attempt(user_id=user.id, session_id=session.id, course_id=q.course_id, topic_id=q.topic_id,
                      question_id=q.id, correct=correct, response=body.answer[:1000], time_ms=body.time_ms,
                      difficulty=q.difficulty, xp=earned, p_after=m.p)
    db.add(attempt)
    db.flush()

    # --- adaptive next question -------------------------------------------
    nxt, reason = (None, "")
    if session.answered < session.length:
        nxt, reason = adaptive.next_question(db, session)
    finished = nxt is None
    bonus = 0
    if finished:
        session.finished_at = now()
        session.current_qid = None
        bonus = game.QUIZ_BONUS + (game.PERFECT_BONUS if session.answered >= 5 and session.correct == session.answered else 0)
        attempt.xp += bonus
    else:
        session.current_qid, session.current_reason = nxt.id, reason
    session.xp += earned + bonus
    user.xp += earned + bonus

    new_badges = game.check_badges(db, user, session, attempt, finished)
    db.commit()
    info = game.level_info(user.xp)
    return {
        "correct": correct, "correct_answer": q.answer, "explanation": q.explanation,
        "source_excerpt": q.source_excerpt, "xp_earned": earned, "bonus_xp": bonus, "combo": session.combo,
        "session": {"xp": session.xp, "correct": session.correct, "answered": session.answered},
        "mastery": {"topic": q.topic.name, "before": round(before, 4), "after": m.p, "status": state},
        "new_badges": new_badges, "level_up": info["level"] > old_level, "user": user_out(user),
        "finished": finished, "next": None if finished else public_question(db, nxt, session),
    }


@router.get("/{session_id}/summary")
def summary(session_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    session = _session(db, user, session_id)
    attempts = db.scalars(select(Attempt).where(Attempt.session_id == session.id).order_by(Attempt.id)).all()
    topics: dict[int, dict] = {}
    review = []
    for a in attempts:
        q = db.get(Question, a.question_id)
        t = topics.get(a.topic_id)
        if t is None:
            prev = db.scalar(select(Attempt.p_after).where(
                Attempt.user_id == user.id, Attempt.topic_id == a.topic_id, Attempt.id < attempts[0].id
            ).order_by(Attempt.id.desc()).limit(1))
            topic = db.get(Topic, a.topic_id)
            t = topics[a.topic_id] = {"id": a.topic_id, "name": topic.name if topic else "Removed topic",
                                      "correct": 0, "total": 0, "before": prev if prev is not None else bkt.P_INIT}
        t["total"] += 1
        t["correct"] += int(a.correct)
        t["after"] = a.p_after
        if q:
            review.append({"text": q.text, "type": q.qtype, "topic": t["name"], "difficulty": q.difficulty,
                           "your_answer": a.response, "correct_answer": q.answer, "correct": a.correct,
                           "explanation": q.explanation, "time_ms": a.time_ms, "xp": a.xp})
    for t in topics.values():
        m = db.scalar(select(Mastery).where(Mastery.user_id == user.id, Mastery.topic_id == t["id"]))
        t["status"] = bkt.status(m.p, m.attempts) if m else "new"
    total_time = sum(a.time_ms for a in attempts)
    return {
        "session_id": session.id, "course_id": session.course_id, "finished": session.finished_at is not None,
        "answered": session.answered, "correct": session.correct, "xp": session.xp,
        "best_combo": session.best_combo,
        "accuracy": round(session.correct / session.answered, 3) if session.answered else 0,
        "avg_time_ms": int(total_time / len(attempts)) if attempts else 0,
        "topics": sorted(topics.values(), key=lambda t: t["after"]), "review": review,
    }
