"""Data layer: users, syllabus/topics, questions (each with a foreign key to
its source topic = the traceable topic-question graph), attempts, mastery,
XP/badges."""
from datetime import date, datetime, timezone

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(300))
    role: Mapped[str] = mapped_column(String(20), default="student")  # student | teacher
    xp: Mapped[int] = mapped_column(Integer, default=0)
    streak: Mapped[int] = mapped_column(Integer, default=0)
    longest_streak: Mapped[int] = mapped_column(Integer, default=0)
    last_active: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Course(Base):
    __tablename__ = "courses"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    code: Mapped[str] = mapped_column(String(40), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    kind: Mapped[str] = mapped_column(String(20), default="personal")  # personal | class
    join_code: Mapped[str] = mapped_column(String(12), unique=True, index=True)
    published: Mapped[bool] = mapped_column(Boolean, default=False)
    source_name: Mapped[str] = mapped_column(String(300), default="")
    extraction_method: Mapped[str] = mapped_column(String(40), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    owner: Mapped[User] = relationship()
    topics: Mapped[list["Topic"]] = relationship(
        back_populates="course", cascade="all, delete-orphan", order_by="Topic.position"
    )


class Enrollment(Base):
    __tablename__ = "enrollments"
    __table_args__ = (UniqueConstraint("user_id", "course_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Topic(Base):
    __tablename__ = "topics"
    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    summary: Mapped[str] = mapped_column(Text, default="")
    content: Mapped[str] = mapped_column(Text, default="")
    keywords: Mapped[list] = mapped_column(JSON, default=list)
    position: Mapped[int] = mapped_column(Integer, default=0)

    course: Mapped[Course] = relationship(back_populates="topics")
    questions: Mapped[list["Question"]] = relationship(back_populates="topic", cascade="all, delete-orphan")


class Question(Base):
    __tablename__ = "questions"
    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"), index=True)
    qtype: Mapped[str] = mapped_column(String(10))  # mcq | tf | short
    difficulty: Mapped[str] = mapped_column(String(10))  # easy | medium | hard
    bloom: Mapped[str] = mapped_column(String(20), default="remember")
    text: Mapped[str] = mapped_column(Text)
    options: Mapped[list] = mapped_column(JSON, default=list)
    answer: Mapped[str] = mapped_column(Text)
    explanation: Mapped[str] = mapped_column(Text, default="")
    keywords: Mapped[list] = mapped_column(JSON, default=list)  # grading keys for short answers
    source_excerpt: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(12), default="approved")  # approved | draft
    origin: Mapped[str] = mapped_column(String(30), default="manual")  # gemini | groq | ollama | offline | manual
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    topic: Mapped[Topic] = relationship(back_populates="questions")


class QuizSession(Base):
    __tablename__ = "quiz_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    topic_ids: Mapped[list] = mapped_column(JSON, default=list)
    qtypes: Mapped[list] = mapped_column(JSON, default=list)
    length: Mapped[int] = mapped_column(Integer, default=10)
    seconds_per_question: Mapped[int] = mapped_column(Integer, default=45)
    asked: Mapped[list] = mapped_column(JSON, default=list)
    levels: Mapped[dict] = mapped_column(JSON, default=dict)  # topic_id -> staircase level 0..2
    current_qid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    current_reason: Mapped[str] = mapped_column(String(300), default="")
    combo: Mapped[int] = mapped_column(Integer, default=0)
    best_combo: Mapped[int] = mapped_column(Integer, default=0)
    answered: Mapped[int] = mapped_column(Integer, default=0)
    correct: Mapped[int] = mapped_column(Integer, default=0)
    xp: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Attempt(Base):
    """Response log: topic, difficulty, correctness, response time."""
    __tablename__ = "attempts"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("quiz_sessions.id"), index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"), index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), index=True)
    correct: Mapped[bool] = mapped_column(Boolean)
    response: Mapped[str] = mapped_column(Text, default="")
    time_ms: Mapped[int] = mapped_column(Integer, default=0)
    difficulty: Mapped[str] = mapped_column(String(10))
    xp: Mapped[int] = mapped_column(Integer, default=0)
    p_after: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)


class Mastery(Base):
    """Knowledge-tracing state: P(mastered) per (student, topic)."""
    __tablename__ = "mastery"
    __table_args__ = (UniqueConstraint("user_id", "topic_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"), index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    p: Mapped[float] = mapped_column(Float, default=0.3)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    correct: Mapped[int] = mapped_column(Integer, default=0)
    was_weak: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class UserBadge(Base):
    __tablename__ = "user_badges"
    __table_args__ = (UniqueConstraint("user_id", "key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    key: Mapped[str] = mapped_column(String(40))
    earned_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class ExamPaper(Base):
    """A VTU-pattern descriptive question paper. `content` is a JSON snapshot:
    {"modules": [{"topic_id", "topic", "co", "questions": [{"parts": [
        {"text", "marks", "bloom", "scheme": [..]}]}]}]}"""
    __tablename__ = "exam_papers"
    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    pattern: Mapped[str] = mapped_column(String(20), default="see")  # see | cie | quiz
    level: Mapped[str] = mapped_column(String(20), default="balanced")
    semester: Mapped[str] = mapped_column(String(40), default="")
    session: Mapped[str] = mapped_column(String(60), default="")
    marks_per_question: Mapped[int] = mapped_column(Integer, default=20)
    duration: Mapped[str] = mapped_column(String(30), default="3 hrs.")
    shared: Mapped[bool] = mapped_column(Boolean, default=False)
    content: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
