"""The LLM path with a mocked provider: valid items are kept, malformed ones are
dropped and the offline generator tops up the remainder."""
from types import SimpleNamespace

from app.services import generator, llm


def test_llm_generation_is_validated(monkeypatch):
    topic = SimpleNamespace(id=1, name="Transport Layer", keywords=["TCP", "UDP", "port number"], content=(
        "TCP is a connection-oriented transport protocol that provides reliable delivery. "
        "UDP is a connectionless transport protocol that provides best-effort delivery. "
        "A port number is a 16-bit identifier that distinguishes one application process from another."))
    other = SimpleNamespace(id=2, name="Network Layer", keywords=["router", "IP address", "subnet mask", "OSPF"], content="")
    reply = {"questions": [
        {"type": "mcq", "difficulty": "easy", "bloom": "remember", "question": "Which protocol is connectionless?",
         "options": ["A) TCP", "B) UDP", "C) FTP", "D) HTTP"], "answer": "B", "explanation": "UDP has no handshake."},
        {"type": "true_false", "difficulty": "medium", "question": "TCP guarantees ordered delivery.", "answer": True},
        {"type": "mcq", "difficulty": "hard", "question": "Broken item whose answer is not an option",
         "options": ["x", "y", "z", "w"], "answer": "q"},
        {"type": "short", "difficulty": "hard", "bloom": "apply", "question": "Why would a video call prefer UDP?",
         "answer": "Low latency matters more than reliability.", "keywords": ["latency", "retransmission"]},
    ]}
    monkeypatch.setattr(llm, "provider", lambda: "gemini")
    monkeypatch.setattr(llm, "chat_json", lambda *a, **k: reply)
    qs, engine, _ = generator.generate_questions("CN", topic, [topic, other], 4, ["mcq", "tf", "short"],
                                                 ["easy", "medium", "hard"], [])
    assert engine == "gemini"
    from_llm = [q for q in qs if q["origin"] == "gemini"]
    assert len(from_llm) == 3
    mcq = from_llm[0]
    assert mcq["answer"] == "UDP" and sorted(mcq["options"]) == ["FTP", "HTTP", "TCP", "UDP"]
    assert from_llm[1]["qtype"] == "tf" and from_llm[1]["answer"] == "True"
    assert len(qs) == 4 and qs[-1]["origin"] == "offline"

    def boom(*a, **k):
        raise llm.LLMError("quota exceeded")
    monkeypatch.setattr(llm, "chat_json", boom)
    qs, _, note = generator.generate_questions("CN", topic, [topic, other], 3, ["mcq", "tf"], ["easy"], [])
    assert qs and all(q["origin"] == "offline" for q in qs) and "offline generator" in note
