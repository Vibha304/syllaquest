"""Module 5 - Adaptive next-question selection.

Topic:      sampled with weight (1 - mastery)^2, so weak topics dominate.
Difficulty: per-topic staircase - correct -> harder, incorrect -> easier.
"""
import random

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Attempt, Mastery, Question, QuizSession, Topic
from . import bkt

LEVELS = ["easy", "medium", "hard"]


def mastery_map(db: Session, user_id: int, course_id: int) -> dict[int, Mastery]:
    rows = db.scalars(select(Mastery).where(Mastery.user_id == user_id, Mastery.course_id == course_id))
    return {m.topic_id: m for m in rows}


def start_level(p: float) -> int:
    return 0 if p < 0.45 else (1 if p < 0.75 else 2)


def step_level(session: QuizSession, topic_id: int, correct: bool) -> None:
    levels = dict(session.levels or {})
    cur = int(levels.get(str(topic_id), 1))
    levels[str(topic_id)] = max(0, min(2, cur + (1 if correct else -1)))
    session.levels = levels


def next_question(db: Session, session: QuizSession, rng: random.Random | None = None):
    """Return (question, reason) or (None, '') when the pool is exhausted."""
    rng = rng or random
    asked = set(session.asked or [])
    stmt = select(Question).where(Question.course_id == session.course_id, Question.status == "approved")
    if session.topic_ids:
        stmt = stmt.where(Question.topic_id.in_(session.topic_ids))
    if session.qtypes:
        stmt = stmt.where(Question.qtype.in_(session.qtypes))
    pool = [q for q in db.scalars(stmt) if q.id not in asked]
    if not pool:
        return None, ""

    by_topic: dict[int, list[Question]] = {}
    for q in pool:
        by_topic.setdefault(q.topic_id, []).append(q)
    mastery = mastery_map(db, session.user_id, session.course_id)

    last_topics = []
    if session.asked:
        last = db.scalars(select(Question.topic_id).where(Question.id.in_(session.asked[-2:]))).all()
        last_topics = list(last)

    weights = {}
    for tid in by_topic:
        m = mastery.get(tid)
        p = m.p if m else bkt.P_INIT
        w = (1 - p) ** 2 + 0.04
        if m is None or m.attempts == 0:
            w += 0.15  # explore topics we know nothing about
        if len(last_topics) == 2 and all(t == tid for t in last_topics) and len(by_topic) > 1:
            w *= 0.15  # avoid drilling one topic three times in a row
        weights[tid] = w
    tids = list(weights)
    topic_id = rng.choices(tids, weights=[weights[t] for t in tids])[0]

    m = mastery.get(topic_id)
    p = m.p if m else bkt.P_INIT
    levels = dict(session.levels or {})
    if str(topic_id) not in levels:
        levels[str(topic_id)] = start_level(p)
        session.levels = levels
    want = int(levels[str(topic_id)])

    candidates = by_topic[topic_id]
    seen = dict(db.execute(
        select(Attempt.question_id, func.max(Attempt.created_at))
        .where(Attempt.user_id == session.user_id, Attempt.question_id.in_([q.id for q in candidates]))
        .group_by(Attempt.question_id)
    ).all())

    def rank(q: Question):
        return (abs(LEVELS.index(q.difficulty) - want), q.id in seen, str(seen.get(q.id, "")), rng.random())

    question = min(candidates, key=rank)
    topic = db.get(Topic, topic_id)
    state = bkt.status(p, m.attempts if m else 0)
    if state == "weak":
        reason = f"Targeting a weak topic: {topic.name} (mastery {round(p * 100)}%)"
    elif state == "new":
        reason = f"Exploring a new topic: {topic.name}"
    elif state == "mastered":
        reason = f"Keeping {topic.name} sharp (mastery {round(p * 100)}%)"
    else:
        reason = f"Building mastery in {topic.name} ({round(p * 100)}%)"
    if question.difficulty != LEVELS[want]:
        reason += f" · closest available difficulty: {question.difficulty}"
    else:
        reason += f" · difficulty: {question.difficulty}"
    return question, reason
