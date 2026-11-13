"""Demo data so the app is explorable the moment it starts:
a teacher, a student, a few classmates and a published Computer Networks class
with a generated question bank and some practice history."""
import random
from datetime import date, datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Attempt, Course, Enrollment, Mastery, Question, QuizSession, Topic, User, UserBadge
from .security import hash_password
from .services import bkt, gamification as game, generator
from .services.parser import parse_document
from .services.topics import extract_topics

DEMO_PASSWORD = "demo1234"
SIM_SEED = int(__import__("os").getenv("SIM_SEED", "5"))
SAMPLE = Path(__file__).parent / "sample_data" / "computer_networks.txt"


def _simulate(db: Session, rng: random.Random, user: User, course: Course, questions: list[Question],
              skill: dict[int, float], n_sessions: int, last_day_offset: int) -> None:
    by_topic: dict[int, list[Question]] = {}
    for q in questions:
        by_topic.setdefault(q.topic_id, []).append(q)
    mastery: dict[int, Mastery] = {}
    total_xp = 0
    for s in range(n_sessions):
        day = date.today() - timedelta(days=last_day_offset + (n_sessions - 1 - s))
        start = datetime.combine(day, datetime.min.time()) + timedelta(hours=rng.randint(9, 21), minutes=rng.randint(0, 59))
        session = QuizSession(user_id=user.id, course_id=course.id, topic_ids=[], qtypes=[], length=8,
                              asked=[], levels={}, started_at=start)
        db.add(session)
        db.flush()
        combo = 0
        picks = rng.sample(questions, 8)
        for i, q in enumerate(picks):
            p_right = min(0.97, max(0.08, skill[q.topic_id] - {"easy": -0.1, "medium": 0.0, "hard": 0.15}[q.difficulty]))
            correct = rng.random() < p_right
            m = mastery.get(q.topic_id)
            if m is None:
                m = mastery[q.topic_id] = Mastery(user_id=user.id, topic_id=q.topic_id, course_id=course.id,
                                                  p=bkt.P_INIT, attempts=0, correct=0)
                db.add(m)
            m.p = bkt.update(m.p, correct, q.qtype, q.difficulty)
            m.attempts += 1
            m.correct += int(correct)
            if bkt.status(m.p, m.attempts) == "weak":
                m.was_weak = True
            combo = combo + 1 if correct else 0
            time_ms = rng.randint(4000, 30000)
            xp = game.xp_for(q.difficulty, combo, time_ms) if correct else 0
            if i == 7:
                xp += game.QUIZ_BONUS
            db.add(Attempt(user_id=user.id, session_id=session.id, course_id=course.id, topic_id=q.topic_id,
                           question_id=q.id, correct=correct, response=q.answer if correct else "", time_ms=time_ms,
                           difficulty=q.difficulty, xp=xp, p_after=m.p,
                           created_at=start + timedelta(seconds=40 * i)))
            session.answered += 1
            session.correct += int(correct)
            session.xp += xp
            session.best_combo = max(session.best_combo, combo)
            session.asked = [*session.asked, q.id]
        session.finished_at = start + timedelta(minutes=6)
        total_xp += session.xp
    user.xp = total_xp
    user.streak = user.longest_streak = n_sessions
    user.last_active = date.today() - timedelta(days=last_day_offset)


def seed(db: Session) -> None:
    if db.scalar(select(User.id).limit(1)):
        return
    rng = random.Random(2026)
    pw = hash_password(DEMO_PASSWORD)
    teacher = User(name="Prof. Demo Teacher", email="teacher@demo.edu", password_hash=pw, role="teacher")
    student = User(name="Demo Student", email="student@demo.edu", password_hash=pw, role="student")
    mates = [User(name=n, email=f"{n.split()[0].lower()}@demo.edu", password_hash=pw, role="student")
             for n in ("Aarav Sharma", "Diya Patel", "Kabir Rao", "Meera Nair", "Rohan Iyer")]
    db.add_all([teacher, student, *mates])
    db.flush()

    topics, method = extract_topics(parse_document(SAMPLE.name, SAMPLE.read_bytes()))
    course = Course(owner_id=teacher.id, name="Computer Networks", code="BCS502", kind="class",
                    description="Demo class generated from the bundled Computer Networks notes.",
                    join_code="CN2026", published=True, source_name=SAMPLE.name, extraction_method=method)
    for i, t in enumerate(topics):
        course.topics.append(Topic(name=t["name"], summary=t["summary"], content=t["content"],
                                   keywords=t["keywords"], position=i))
    db.add(course)
    db.flush()

    questions: list[Question] = []
    for topic in course.topics:
        items, _, _ = generator.generate_questions(course.name, topic, course.topics, 12, ["mcq", "tf", "short"],
                                                   ["easy", "medium", "hard"], [], offline_only=True)
        for item in items:
            q = Question(course_id=course.id, topic_id=topic.id, status="approved", **item)
            db.add(q)
            questions.append(q)
    db.flush()

    practice = [q for q in questions if q.qtype != "short"]
    tids = [t.id for t in course.topics]
    profiles = [(student, 0.82, 4, 1), (mates[0], 0.85, 6, 0), (mates[1], 0.74, 5, 0),
                (mates[2], 0.55, 3, 2), (mates[3], 0.68, 5, 1), (mates[4], 0.45, 2, 3)]
    for user, base, sessions, offset in profiles:
        db.add(Enrollment(user_id=user.id, course_id=course.id))
        skill = {tid: min(0.95, max(0.15, base + rng.uniform(-0.18, 0.18))) for tid in tids}
        if user is student and len(tids) >= 4:  # give the demo student two clear weak spots
            skill[tids[3]], skill[tids[4 % len(tids)]] = 0.18, 0.25
        _simulate(db, random.Random(f"{user.email}-{SIM_SEED}"), user, course, practice, skill, sessions, offset)
        db.add_all([UserBadge(user_id=user.id, key="first_steps"), UserBadge(user_id=user.id, key="finisher")])
        if user.streak >= 3:
            db.add(UserBadge(user_id=user.id, key="streak_3"))
    db.commit()
