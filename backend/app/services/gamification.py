"""Module 4 - XP, levels, streaks and badges (tied to topic-level performance)."""
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Attempt, Course, Mastery, Topic, User, UserBadge
from . import bkt

BASE_XP = {"easy": 10, "medium": 20, "hard": 30}
QUIZ_BONUS, PERFECT_BONUS = 20, 50
TITLES = ["Novice", "Apprentice", "Scholar", "Adept", "Specialist", "Expert", "Master", "Sage", "Legend"]

BADGES = {
    "first_steps": ("First Steps", "Answer your first question", "footprints"),
    "finisher": ("Finisher", "Complete your first quiz", "flag"),
    "perfect_quiz": ("Perfect Quiz", "Finish a quiz with every answer correct", "target"),
    "combo_5": ("On Fire", "Get 5 correct answers in a row", "flame"),
    "combo_10": ("Unstoppable", "Get 10 correct answers in a row", "zap"),
    "streak_3": ("3-Day Streak", "Practise three days in a row", "calendar"),
    "streak_5": ("5-Day Streak", "Practise five days in a row", "calendar-check"),
    "streak_10": ("10-Day Streak", "Practise ten days in a row", "calendar-heart"),
    "topic_master": ("Topic Master", "Reach mastery in any topic", "award"),
    "triple_master": ("Triple Crown", "Master three topics", "crown"),
    "course_master": ("Syllabus Conqueror", "Master every topic of a course", "trophy"),
    "comeback": ("Comeback", "Turn a weak topic into a mastered one", "trending-up"),
    "quick_thinker": ("Quick Thinker", "Answer a hard question correctly in under 10 seconds", "timer"),
    "brainiac": ("Brainiac", "Answer 10 hard questions correctly", "brain"),
    "centurion": ("Centurion", "Answer 100 questions", "shield"),
    "curator": ("Curator", "Turn your own document into a quiz", "upload"),
    "level_5": ("Rising Star", "Reach level 5", "star"),
}


def level_floor(level: int) -> int:
    """Total XP needed to reach `level` (1 -> 0, 2 -> 100, 3 -> 300, 4 -> 600 ...)."""
    return 50 * (level - 1) * level


def level_info(xp: int) -> dict:
    level = 1
    while level_floor(level + 1) <= xp:
        level += 1
    lo, hi = level_floor(level), level_floor(level + 1)
    return {
        "level": level, "title": TITLES[min(level - 1, len(TITLES) - 1)], "xp": xp,
        "level_xp": xp - lo, "level_span": hi - lo, "next_level_at": hi,
        "progress": round((xp - lo) / (hi - lo), 4),
    }


def xp_for(difficulty: str, combo: int, time_ms: int) -> int:
    base = BASE_XP.get(difficulty, 10)
    multiplier = 1 + 0.1 * min(max(combo - 1, 0), 5)
    speed = 5 if 0 < time_ms < 10_000 else 0
    return int(round(base * multiplier)) + speed


def touch_streak(user: User, today: date | None = None) -> None:
    today = today or date.today()
    if user.last_active == today:
        return
    user.streak = user.streak + 1 if user.last_active == today - timedelta(days=1) else 1
    user.longest_streak = max(user.longest_streak, user.streak)
    user.last_active = today


def current_streak(user: User) -> int:
    if user.last_active and user.last_active >= date.today() - timedelta(days=1):
        return user.streak
    return 0


def award(db: Session, user: User, keys: list[str]) -> list[dict]:
    owned = set(db.scalars(select(UserBadge.key).where(UserBadge.user_id == user.id)))
    new = []
    for key in dict.fromkeys(keys):
        if key in BADGES and key not in owned:
            db.add(UserBadge(user_id=user.id, key=key))
            name, desc, icon = BADGES[key]
            new.append({"key": key, "name": name, "description": desc, "icon": icon})
    return new


def check_badges(db: Session, user: User, session, attempt: Attempt, finished: bool) -> list[dict]:
    keys = ["first_steps"]
    if session.combo >= 5:
        keys.append("combo_5")
    if session.combo >= 10:
        keys.append("combo_10")
    for n in (3, 5, 10):
        if user.streak >= n:
            keys.append(f"streak_{n}")
    if attempt.correct and attempt.difficulty == "hard" and 0 < attempt.time_ms < 10_000:
        keys.append("quick_thinker")
    total = db.scalar(select(func.count(Attempt.id)).where(Attempt.user_id == user.id)) or 0
    if total >= 100:
        keys.append("centurion")
    hard = db.scalar(select(func.count(Attempt.id)).where(
        Attempt.user_id == user.id, Attempt.correct.is_(True), Attempt.difficulty == "hard")) or 0
    if hard >= 10:
        keys.append("brainiac")

    rows = db.scalars(select(Mastery).where(Mastery.user_id == user.id)).all()
    mastered = [m for m in rows if bkt.status(m.p, m.attempts) == "mastered"]
    if mastered:
        keys.append("topic_master")
    if len(mastered) >= 3:
        keys.append("triple_master")
    if any(m.was_weak for m in mastered):
        keys.append("comeback")
    n_topics = db.scalar(select(func.count(Topic.id)).where(Topic.course_id == session.course_id)) or 0
    if n_topics and sum(1 for m in mastered if m.course_id == session.course_id) >= n_topics:
        keys.append("course_master")
    if finished:
        keys.append("finisher")
        if session.answered >= 5 and session.correct == session.answered:
            keys.append("perfect_quiz")
    if level_info(user.xp)["level"] >= 5:
        keys.append("level_5")
    return award(db, user, keys)
