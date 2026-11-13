"""Student dashboard, badges and global leaderboard."""
from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Attempt, Course, Mastery, QuizSession, Topic, User, UserBadge
from ..security import current_user
from ..services import bkt, gamification as game
from .auth import user_out

router = APIRouter(prefix="/api", tags=["me"])


@router.get("/me/dashboard")
def dashboard(user: User = Depends(current_user), db: Session = Depends(get_db)):
    attempts = db.scalars(select(Attempt).where(Attempt.user_id == user.id).order_by(Attempt.id)).all()
    today = date.today()
    days = {(today - timedelta(days=i)).isoformat(): {"xp": 0, "answered": 0, "correct": 0} for i in range(13, -1, -1)}
    for a in attempts:
        d = days.get(a.created_at.date().isoformat())
        if d:
            d["xp"] += a.xp
            d["answered"] += 1
            d["correct"] += int(a.correct)

    rows = db.execute(
        select(Mastery, Topic.name, Course.id, Course.name)
        .join(Topic, Topic.id == Mastery.topic_id).join(Course, Course.id == Mastery.course_id)
        .where(Mastery.user_id == user.id)
    ).all()
    topics = [{"topic_id": m.topic_id, "topic": tname, "course_id": cid, "course": cname, "p": m.p,
               "attempts": m.attempts, "accuracy": round(m.correct / m.attempts, 3) if m.attempts else 0,
               "status": bkt.status(m.p, m.attempts)} for m, tname, cid, cname in rows]
    weak = sorted([t for t in topics if t["status"] == "weak"], key=lambda t: t["p"])
    strong = sorted([t for t in topics if t["status"] == "mastered"], key=lambda t: -t["p"])

    sessions = db.execute(
        select(QuizSession, Course.name).join(Course, Course.id == QuizSession.course_id)
        .where(QuizSession.user_id == user.id, QuizSession.answered > 0)
        .order_by(QuizSession.id.desc()).limit(6)
    ).all()
    badges = db.scalars(select(UserBadge).where(UserBadge.user_id == user.id).order_by(UserBadge.id.desc())).all()

    # mastery trajectory: average P(mastery) across practised topics after each day
    trend, latest = [], {}
    by_day: dict[str, list[Attempt]] = {}
    for a in attempts:
        by_day.setdefault(a.created_at.date().isoformat(), []).append(a)
    for day in sorted(by_day):
        for a in by_day[day]:
            latest[a.topic_id] = a.p_after
        trend.append({"date": day, "mastery": round(sum(latest.values()) / len(latest), 3)})

    answered = len(attempts)
    return {
        "user": user_out(user),
        "totals": {"answered": answered, "correct": sum(a.correct for a in attempts),
                   "accuracy": round(sum(a.correct for a in attempts) / answered, 3) if answered else 0,
                   "quizzes": db.scalar(select(func.count(QuizSession.id)).where(
                       QuizSession.user_id == user.id, QuizSession.finished_at.is_not(None))) or 0,
                   "topics_mastered": len(strong), "topics_weak": len(weak)},
        "activity": [{"date": d, **v} for d, v in days.items()],
        "trend": trend[-30:],
        "weak_topics": weak[:6], "strong_topics": strong[:6], "topics": topics,
        "recent_sessions": [{"id": s.id, "course": cname, "course_id": s.course_id, "answered": s.answered,
                             "correct": s.correct, "xp": s.xp, "finished": s.finished_at is not None,
                             "date": s.started_at.isoformat()} for s, cname in sessions],
        "recent_badges": [{"key": b.key, "name": game.BADGES[b.key][0], "icon": game.BADGES[b.key][2]}
                          for b in badges[:4] if b.key in game.BADGES],
    }


@router.get("/me/badges")
def badges(user: User = Depends(current_user), db: Session = Depends(get_db)):
    earned = {b.key: b.earned_at for b in db.scalars(select(UserBadge).where(UserBadge.user_id == user.id))}
    return [{"key": key, "name": name, "description": desc, "icon": icon, "earned": key in earned,
             "earned_at": earned[key].isoformat() if key in earned else None}
            for key, (name, desc, icon) in game.BADGES.items()]


@router.get("/leaderboard")
def leaderboard(user: User = Depends(current_user), db: Session = Depends(get_db)):
    top = db.scalars(select(User).where(User.role == "student").order_by(User.xp.desc(), User.id).limit(25)).all()
    rows = [{"rank": i, "user_id": u.id, "name": u.name, "xp": u.xp, "level": game.level_info(u.xp)["level"],
             "title": game.level_info(u.xp)["title"], "streak": game.current_streak(u)}
            for i, u in enumerate(top, 1)]
    return {"rows": rows, "me": user.id}
