"""Answer checking. MCQ/TF are exact; short answers use keyword coverage."""
import re

from .generator import key_terms_of, norm


def _stems(text: str) -> set[str]:
    return {w[:5] for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 1}


def grade(question, response: str) -> bool:
    response = (response or "").strip()
    if not response:
        return False
    if question.qtype in ("mcq", "tf"):
        return norm(response) == norm(question.answer)
    if norm(response) == norm(question.answer):
        return True
    keys = question.keywords or key_terms_of(question.answer)
    if not keys:
        return False
    got = _stems(response)
    hits = sum(1 for k in keys if all(part in got for part in _stems(k)))
    return hits / len(keys) >= 0.5
