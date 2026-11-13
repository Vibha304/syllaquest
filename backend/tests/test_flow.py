"""End-to-end test of the whole pipeline with the offline generator:
upload -> topics -> questions -> review -> publish -> join -> adaptive quiz -> analytics."""
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.services import bkt, gamification as game

SAMPLE = Path(__file__).parent.parent / "app" / "sample_data" / "computer_networks.txt"


def auth(client, email, role="student", name="Test User"):
    r = client.post("/api/auth/register", json={"name": name, "email": email, "password": "secret12", "role": role})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_bkt_and_levels():
    p = bkt.P_INIT
    up = bkt.update(p, True)
    assert up > p > bkt.update(p, False) - 0.2
    assert bkt.update(0.9, False) < 0.9
    assert game.level_info(0)["level"] == 1 and game.level_info(100)["level"] == 2
    assert game.xp_for("hard", 3, 5000) > game.xp_for("easy", 1, 20000)


def test_full_flow():
    with TestClient(app) as client:
        teacher = auth(client, "t@x.edu", "teacher", "Teach")
        student = auth(client, "s@x.edu", "student", "Stu")

        # demo data was seeded
        r = client.post("/api/auth/login", json={"email": "student@demo.edu", "password": "demo1234"})
        assert r.status_code == 200
        demo = {"Authorization": f"Bearer {r.json()['token']}"}
        dash = client.get("/api/me/dashboard", headers=demo).json()
        assert dash["totals"]["answered"] > 0 and dash["weak_topics"]

        # teacher uploads a syllabus -> topics
        with SAMPLE.open("rb") as fh:
            r = client.post("/api/courses", headers=teacher, data={"name": "Networks", "code": "CN1"},
                            files={"file": ("cn.txt", fh, "text/plain")})
        assert r.status_code == 200, r.text
        course = r.json()
        assert len(course["topics"]) == 6
        assert course["topics"][3]["name"] == "Network Layer"
        cid = course["id"]

        # generate a question bank topic by topic -> drafts
        total = 0
        for t in course["topics"]:
            r = client.post(f"/api/courses/{cid}/generate", headers=teacher,
                            json={"topic_id": t["id"], "count": 9, "types": ["mcq", "tf", "short"]})
            assert r.status_code == 200, r.text
            created = r.json()["created"]
            assert len(created) >= 7, (t["name"], len(created))
            assert all(q["status"] == "draft" and q["topic_id"] == t["id"] for q in created)
            for q in created:
                if q["type"] == "mcq":
                    assert q["answer"] in q["options"] and len(set(q["options"])) == len(q["options"]) >= 3
            total += len(created)

        # students cannot see drafts / unpublished classes
        assert client.post("/api/courses/join", headers=student, json={"code": course["join_code"]}).status_code == 404
        qs = client.get(f"/api/courses/{cid}/questions", headers=teacher).json()
        assert len(qs) == total
        assert client.get(f"/api/courses/{cid}/questions", headers=student).status_code == 403

        # review: edit one, delete one, approve the rest, publish
        q0 = qs[0]
        r = client.put(f"/api/questions/{q0['id']}", headers=teacher, json={
            "topic_id": q0["topic_id"], "type": "tf", "difficulty": "easy", "text": "True or False: TCP is reliable.",
            "answer": "True", "status": "approved"})
        assert r.status_code == 200, r.text
        client.post(f"/api/courses/{cid}/questions/bulk", headers=teacher, json={"ids": [qs[1]["id"]], "action": "delete"})
        client.post(f"/api/courses/{cid}/questions/bulk", headers=teacher,
                    json={"ids": [q["id"] for q in qs], "action": "approve"})
        client.patch(f"/api/courses/{cid}", headers=teacher, json={"published": True})
        cov = client.get(f"/api/courses/{cid}/coverage", headers=teacher).json()
        assert cov["total"] == total - 1 and not cov["uncovered"]
        for fmt in ("docx", "csv", "json"):
            r = client.get(f"/api/courses/{cid}/export?format={fmt}", headers=teacher)
            assert r.status_code == 200 and len(r.content) > 500

        # student joins and takes an adaptive quiz, always answering wrong on purpose for one topic
        assert client.post("/api/courses/join", headers=student, json={"code": course["join_code"]}).status_code == 200
        r = client.post("/api/quiz/start", headers=student, json={"course_id": cid, "length": 12, "types": ["mcq", "tf"]})
        assert r.status_code == 200, r.text
        sid, q = r.json()["session_id"], r.json()["question"]
        assert "answer" not in q
        answers = {x["id"]: x["answer"] for x in client.get(f"/api/courses/{cid}/questions", headers=teacher).json()}
        weak_topic = course["topics"][0]["id"]
        seen_topics = []
        while True:
            wrong = q["topic"]["id"] == weak_topic
            seen_topics.append(q["topic"]["id"])
            r = client.post(f"/api/quiz/{sid}/answer", headers=student, json={
                "question_id": q["id"], "answer": "zzz" if wrong else answers[q["id"]], "time_ms": 5000})
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["correct"] == (not wrong)
            if body["finished"]:
                break
            q = body["next"]
        summary = client.get(f"/api/quiz/{sid}/summary", headers=student).json()
        assert summary["answered"] == 12 and summary["xp"] > 0 and len(summary["review"]) == 12
        me = client.get("/api/auth/me", headers=student).json()
        assert me["xp"] == summary["xp"] and me["streak"] == 1
        badges = [b["key"] for b in client.get("/api/me/badges", headers=student).json() if b["earned"]]
        assert {"first_steps", "finisher"} <= set(badges)

        detail = client.get(f"/api/courses/{cid}", headers=student).json()
        assert detail["join_code"] is None and detail["topics"][0]["content"] is None
        analytics = client.get(f"/api/courses/{cid}/class-analytics", headers=teacher).json()
        assert analytics["student_count"] == 1 and analytics["total_attempts"] == 12
        board = client.get(f"/api/courses/{cid}/leaderboard", headers=student).json()
        assert board["rows"][0]["xp"] == summary["xp"]
        assert client.get("/api/leaderboard", headers=student).status_code == 200

        # student creates a personal course from pasted text (LDA fallback path, auto-approved questions)
        text = SAMPLE.read_text().replace("Unit ", "").split("\n", 2)[2]
        text = "\n".join(line for line in text.splitlines() if len(line.split()) > 12)
        r = client.post("/api/courses", headers=student, data={"name": "My notes", "text": text})
        assert r.status_code == 200, r.text
        mine = r.json()
        assert mine["kind"] == "personal" and len(mine["topics"]) >= 2, mine["extraction_method"]
        r = client.post(f"/api/courses/{mine['id']}/generate", headers=student,
                        json={"topic_id": mine["topics"][0]["id"], "count": 5})
        assert r.json()["created"] and r.json()["created"][0]["status"] == "approved"
        assert client.delete(f"/api/courses/{mine['id']}", headers=student).status_code == 200
        assert client.delete(f"/api/courses/{cid}", headers=teacher).status_code == 200
