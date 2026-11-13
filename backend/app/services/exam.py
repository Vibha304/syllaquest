"""VTU-pattern examination paper generation.

Pattern (VTU CBCS semester-end exam): the paper has one section per module;
each module offers TWO full questions (e.g. Q1 OR Q2) of equal marks, each split
into sub-questions (a, b, c). Every sub-question carries marks, a Bloom level
(L1-L6) and a course outcome (CO). Students answer one full question per module.
"""
import random
import re

from . import llm
from .generator import _find, _terms
from .topics import split_sentences

PATTERNS = {
    "see": {"label": "Semester End Examination", "marks_per_question": 20, "duration": "3 hrs.", "max_modules": 5},
    "cie": {"label": "Continuous Internal Evaluation", "marks_per_question": 25, "duration": "90 min.", "max_modules": 3},
    "quiz": {"label": "Unit Test", "marks_per_question": 10, "duration": "45 min.", "max_modules": 5},
}
SPLITS = {
    20: [[6, 6, 8], [10, 10], [8, 12], [7, 7, 6], [5, 5, 10], [4, 8, 8], [6, 8, 6]],
    25: [[8, 8, 9], [10, 15], [12, 13], [5, 10, 10], [7, 8, 10]],
    10: [[5, 5], [4, 6], [10], [3, 7]],
}
BLOOM_NAMES = {"L1": "Remember", "L2": "Understand", "L3": "Apply", "L4": "Analyze", "L5": "Evaluate", "L6": "Create"}


def bloom_for(marks: int, level: str, rng: random.Random) -> str:
    if marks <= 5:
        base = rng.choice([1, 2])
    elif marks <= 8:
        base = rng.choice([2, 2, 3])
    else:
        base = rng.choice([2, 3, 3, 4])
    base += {"foundational": -1, "balanced": 0, "advanced": 1}.get(level, 0)
    return f"L{max(1, min(5, base))}"


def plan(marks_per_question: int, level: str, rng: random.Random) -> list[list[dict]]:
    """Two alternative full questions with different mark splits."""
    options = SPLITS.get(marks_per_question) or [[marks_per_question // 2, marks_per_question - marks_per_question // 2]]
    first, second = rng.sample(options, 2) if len(options) >= 2 else (options[0], options[0])
    return [[{"marks": m, "bloom": bloom_for(m, level, rng)} for m in split] for split in (first, second)]


# --------------------------------------------------------------------------- #
# LLM engine
# --------------------------------------------------------------------------- #
SYSTEM = (
    "You are a senior faculty member who sets question papers for Visvesvaraya Technological University (VTU) "
    "B.E. examinations. You write clear descriptive questions in VTU style with a scheme of valuation. "
    "Reply with JSON only."
)


def _llm_module(course_name: str, topic, slots: list[list[dict]]) -> list[list[dict]]:
    spec = "\n".join(
        f"Full question {i + 1}: " + "; ".join(
            f"part ({'abcdef'[j]}) = {p['marks']} marks, Bloom level {p['bloom']} ({BLOOM_NAMES[p['bloom']]})"
            for j, p in enumerate(parts))
        for i, parts in enumerate(slots))
    prompt = f"""Course: {course_name}
Module / syllabus topic: {topic.name}
Sub-topics and key terms: {", ".join(topic.keywords or []) or "n/a"}

Syllabus text / notes for this module (may be only a list of sub-topics; if so rely on standard
engineering textbook knowledge of exactly these sub-topics):
\"\"\"
{(topic.content or "")[:6000]}
\"\"\"

Set the questions for this module of a VTU examination paper. The module has two alternative full
questions (the student answers either one), so they must be of equal difficulty and together cover
the module's sub-topics without repeating each other.

{spec}

Rules:
- Descriptive engineering examination questions, not objective ones. Use VTU-style command words
  matched to the Bloom level: L1 Define/List/State; L2 Explain/Describe/Discuss/With a neat diagram explain;
  L3 Apply/Solve/Illustrate/Write a program or algorithm/Compute with given data; L4 Compare/Differentiate/Analyze/Derive;
  L5 Justify/Evaluate.
- The depth of each part must fit its marks (about 1 mark per valid point or step). Parts of 8 marks or
  more should ask for a diagram, derivation, algorithm, worked numerical problem or detailed comparison.
- Where the subject allows, include at least one numerical, design or problem-solving part with concrete data.
- Each part must be self-contained and unambiguous. Do not write the marks inside the question text.
- "scheme": the scheme of valuation for that part: 2 to 5 short lines, each ending with its marks
  (for example "Definition - 2M"), adding up to the part's marks.

Return JSON: {{"questions": [{{"parts": [{{"text": "...", "scheme": ["...", "..."]}}]}}, {{"parts": [...]}}]}}"""
    data = llm.chat_json(SYSTEM, prompt, temperature=0.7)
    questions = data.get("questions", []) if isinstance(data, dict) else data
    out: list[list[dict]] = []
    for q in questions if isinstance(questions, list) else []:
        parts = q.get("parts", []) if isinstance(q, dict) else []
        cleaned = []
        for p in parts:
            if not isinstance(p, dict):
                continue
            text = re.sub(r"\s*[\(\[]\s*\d+\s*(marks?|M)\s*[\)\]]\s*$", "", str(p.get("text") or "").strip(), flags=re.I)
            text = re.sub(r"^\s*[\(\[]?[a-f][\)\].]\s+", "", text)
            scheme = [str(s).strip() for s in (p.get("scheme") or []) if str(s).strip()][:6]
            if len(text) >= 12:
                cleaned.append({"text": text, "scheme": scheme})
        out.append(cleaned)
    return out


# --------------------------------------------------------------------------- #
# Offline engine: VTU-style stems built from the module's key terms
# --------------------------------------------------------------------------- #
def _cap(term: str) -> str:
    return term if term[:1].isupper() else term


def _evidence(topic, term: str) -> str:
    for s in split_sentences((topic.content or "").replace("\n", " ")):
        words = len(s.split())
        if _find(term, s) and 6 <= words <= 45 and (s.count(",") + s.count(":")) / words < 0.09:
            return s
    return ""


def _clean_terms(terms: list[str]) -> list[str]:
    """Drop fragments that are part of a longer term ("MAC" vs "MAC address", "CSMA" vs "CSMA/CD")."""
    low = [t.lower() for t in terms]
    return [t for t, l in zip(terms, low) if len(l) > 2 and not any(l != o and l in o for o in low)]


def _related(a: str, terms: list[str]) -> str | None:
    """A term worth comparing with `a`: shares a head word or prefix (e.g. two ARQ protocols)."""
    wa = set(re.findall(r"[a-z0-9]+", a.lower()))
    for t in terms:
        wt = set(re.findall(r"[a-z0-9]+", t.lower()))
        if (wa & wt and wa != wt) or (len(a) >= 3 and a[:3].lower() == t[:3].lower() and a.isupper() and t.isupper()):
            return t
    return None


def _offline_part(topic, marks: int, bloom: str, terms: list[str], rng: random.Random) -> dict:
    a = terms.pop(0) if terms else topic.name
    b = terms[0] if terms else topic.name
    level = int(bloom[1])
    diagram = max(2, round(marks * 0.3))
    if marks <= 4:
        text, scheme = rng.choice([
            (f"Define {a}. Mention its significance.", [f"Definition - {marks - 1}M", "Significance - 1M"]),
            (f"What is {a}? List any {marks - 1} of its characteristics.", ["Definition - 1M", f"Characteristics - {marks - 1}M"]),
        ])
    elif level >= 4:
        b = _related(a, terms)
        if b:
            terms.remove(b)
            text = rng.choice([
                f"Differentiate between {a} and {b}.",
                f"Compare {a} and {b} with respect to their working, advantages and limitations.",
            ])
            scheme = [f"Any {marks - 2} valid points of comparison - {marks - 2}M", "Conclusion / suitable example - 2M"]
        else:
            text = f"Explain {a} in detail and analyze its advantages and limitations."
            scheme = [f"Explanation of {a} - {marks - marks // 2}M", f"Advantages - {marks // 4}M",
                      f"Limitations - {marks // 2 - marks // 4}M"]
    elif level == 3:
        text = rng.choice([
            f"Illustrate the working of {a} with a suitable example.",
            f"With a suitable example, explain the role of {a} in {topic.name}.",
        ])
        scheme = [f"Concept of {a} - {marks - marks // 2 - 1}M", f"Worked example / illustration - {marks // 2}M", "Conclusion - 1M"]
    elif marks >= 8:
        text = rng.choice([
            f"What is {a}? Explain {a} in detail with a neat diagram.",
            f"With a neat diagram, explain the working of {a}.",
            f"Define {a}. Explain {a} with suitable examples and state its advantages and limitations.",
        ])
        scheme = ["Definition - 2M", f"Neat labelled diagram / example - {diagram}M", f"Explanation - {marks - 2 - diagram}M"]
    else:
        if terms and rng.random() < 0.35:
            terms.pop(0)
            text = f"Write short notes on: (i) {_cap(a)} (ii) {_cap(b)}."
            scheme = [f"{_cap(a)} - {marks - marks // 2}M", f"{_cap(b)} - {marks // 2}M"]
        else:
            text = rng.choice([f"Explain {a} with a suitable example.", f"Describe {a}. Why is it important in {topic.name}?",
                               f"Explain the concept of {a} with a neat diagram."])
            scheme = [f"Explanation of {a} - {marks - 2}M", "Example / diagram - 2M"]
    ref = _evidence(topic, a)
    if ref:
        scheme = scheme + [f"Expected content: {ref}"]
    return {"text": text[0].upper() + text[1:], "scheme": scheme}


def generate_module(course_name: str, topic, marks_per_question: int, level: str, seed: str,
                    offline_only: bool = False) -> tuple[list[dict], str, str]:
    """Return ([{"parts": [{text, marks, bloom, scheme}]} x2], engine, note)."""
    rng = random.Random(seed)
    slots = plan(marks_per_question, level, rng)
    engine, note = ("offline" if offline_only else llm.provider()), ""
    generated: list[list[dict]] = []
    if engine != "offline":
        try:
            generated = _llm_module(course_name, topic, slots)
        except llm.LLMError as exc:
            note = f"AI provider unavailable ({exc}); used the offline generator instead."

    terms = _clean_terms(_terms(topic))
    rng.shuffle(terms)
    questions, used_offline = [], False
    for qi, parts in enumerate(slots):
        got = generated[qi] if qi < len(generated) else []
        out = []
        for pi, slot in enumerate(parts):
            if pi < len(got):
                part = got[pi]
            else:
                part, used_offline = _offline_part(topic, slot["marks"], slot["bloom"], terms, rng), True
            out.append({"text": part["text"], "marks": slot["marks"], "bloom": slot["bloom"],
                        "scheme": part.get("scheme") or [f"Valid answer - {slot['marks']}M"]})
        questions.append({"parts": out})
    if engine != "offline" and used_offline and not note:
        note = "Some parts were filled in by the offline generator."
    return questions, (engine if not (used_offline and not generated) else "offline"), note
