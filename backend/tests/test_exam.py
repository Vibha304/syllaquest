"""VTU-pattern exam papers: generation, mark totals, editing, sharing, export."""
import io
from pathlib import Path

import docx
from fastapi.testclient import TestClient

from app.main import app
from app.services import exam, llm
from tests.test_flow import SAMPLE, auth


def test_vtu_paper_flow(monkeypatch):
    with TestClient(app) as client:
        teacher = auth(client, "exam-t@x.edu", "teacher", "Exam Teacher")
        student = auth(client, "exam-s@x.edu", "student", "Exam Student")
        with SAMPLE.open("rb") as fh:
            course = client.post("/api/courses", headers=teacher, data={"name": "Computer Networks", "code": "BCS502"},
                                 files={"file": ("cn.txt", fh, "text/plain")}).json()
        cid, topic_ids = course["id"], [t["id"] for t in course["topics"]]

        # SEE: capped at 5 modules, 2 full questions of 20 marks each
        r = client.post(f"/api/courses/{cid}/papers", headers=teacher, json={
            "pattern": "see", "topic_ids": topic_ids, "semester": "Fifth", "session": "Dec.2026/Jan.2027"})
        assert r.status_code == 200, r.text
        paper = r.json()
        assert paper["module_count"] == 5 and paper["max_marks"] == 100 and not paper["ready"]
        pid = paper["id"]
        for i in range(5):
            r = client.post(f"/api/papers/{pid}/modules/{i}/generate", headers=teacher)
            assert r.status_code == 200, r.text
        paper = r.json()["paper"]
        assert paper["ready"]
        texts = set()
        for m in paper["modules"]:
            assert len(m["questions"]) == 2 and m["co"].startswith("CO")
            for q in m["questions"]:
                assert sum(p["marks"] for p in q["parts"]) == 20
                for p in q["parts"]:
                    assert p["bloom"] in exam.BLOOM_NAMES and p["scheme"] and len(p["text"]) > 12
                    texts.add(p["text"])
        assert len(texts) >= 20  # little repetition across the paper

        # regenerate one module gives a different draw
        before = paper["modules"][0]["questions"]
        after = client.post(f"/api/papers/{pid}/modules/0/generate", headers=teacher).json()["paper"]["modules"][0]["questions"]
        assert before != after

        # edit a part, keep totals
        modules = client.get(f"/api/papers/{pid}", headers=teacher).json()["modules"]
        modules[1]["questions"][0]["parts"][0]["text"] = "Derive the Shannon capacity theorem and state its significance."
        r = client.patch(f"/api/papers/{pid}", headers=teacher, json={"modules": modules, "title": "CN SEE Model Paper 1"})
        assert r.status_code == 200, r.text
        assert r.json()["modules"][1]["questions"][0]["parts"][0]["text"].startswith("Derive the Shannon")

        # exports
        r = client.get(f"/api/papers/{pid}/export?kind=paper", headers=teacher)
        assert r.status_code == 200
        body = "\n".join(c.text for t in docx.Document(io.BytesIO(r.content)).tables for row in t.rows for c in row.cells)
        full = "\n".join(p.text for p in docx.Document(io.BytesIO(r.content)).paragraphs)
        assert "Module - 5" in body and "OR" in body and "Q.10" in body and "Derive the Shannon" in body
        assert "Answer any FIVE full questions" in full and "Fifth Semester B.E. Degree Examination" in full
        assert "Max. Marks: 100" in body
        r = client.get(f"/api/papers/{pid}/export?kind=scheme", headers=teacher)
        assert r.status_code == 200 and b"word/" in r.content

        # sharing: hidden until shared; scheme never visible to students
        client.post(f"/api/courses/{cid}/questions/bulk", headers=teacher, json={"ids": [], "action": "approve"})
        client.patch(f"/api/courses/{cid}", headers=teacher, json={"published": True})
        client.post("/api/courses/join", headers=student, json={"code": course["join_code"]})
        assert client.get(f"/api/courses/{cid}/papers", headers=student).json() == []
        assert client.get(f"/api/papers/{pid}", headers=student).status_code == 403
        client.patch(f"/api/papers/{pid}", headers=teacher, json={"shared": True})
        assert len(client.get(f"/api/courses/{cid}/papers", headers=student).json()) == 1
        seen = client.get(f"/api/papers/{pid}", headers=student).json()
        assert all(p["scheme"] == [] for m in seen["modules"] for q in m["questions"] for p in q["parts"])
        assert client.get(f"/api/papers/{pid}/export?kind=paper", headers=student).status_code == 200
        assert client.get(f"/api/papers/{pid}/export?kind=scheme", headers=student).status_code == 403
        assert client.post(f"/api/papers/{pid}/modules/0/generate", headers=student).status_code == 403
        assert client.delete(f"/api/papers/{pid}", headers=student).status_code == 403

        # CIE: 25-mark questions, at most 3 modules
        cie = client.post(f"/api/courses/{cid}/papers", headers=teacher,
                          json={"pattern": "cie", "topic_ids": topic_ids[:2], "level": "advanced"}).json()
        assert cie["max_marks"] == 50
        got = client.post(f"/api/papers/{cie['id']}/modules/0/generate", headers=teacher).json()["paper"]
        assert all(sum(p["marks"] for p in q["parts"]) == 25 for q in got["modules"][0]["questions"])

        # LLM path (mocked): text comes from the model, marks/bloom from the plan; short reply is topped up
        monkeypatch.setattr(llm, "provider", lambda: "gemini")
        monkeypatch.setattr(llm, "chat_json", lambda *a, **k: {"questions": [
            {"parts": [{"text": "a) With a neat diagram, explain the TCP three-way handshake. (8 Marks)",
                        "scheme": ["Diagram - 3M", "Explanation - 5M"]}]}]})
        got = client.post(f"/api/papers/{cie['id']}/modules/1/generate", headers=teacher).json()
        first = got["paper"]["modules"][1]["questions"][0]["parts"][0]
        assert first["text"] == "With a neat diagram, explain the TCP three-way handshake."
        assert all(sum(p["marks"] for p in q["parts"]) == 25 for q in got["paper"]["modules"][1]["questions"])
        assert "offline generator" in got["note"]

        assert client.delete(f"/api/papers/{cie['id']}", headers=teacher).status_code == 200
        assert client.delete(f"/api/courses/{cid}", headers=teacher).status_code == 200
