"""Module 3 - AI question generation with syllabus-topic mapping.

`generate_questions` produces questions for ONE topic; the caller stores each
with the topic's foreign key, which is what makes the topic-question graph
traceable. An LLM is used when configured; otherwise (or if the LLM call
fails / returns too few valid items) a rule-based NLP generator fills in.
"""
import random
import re

from . import llm
from .topics import STOP, defined_terms, split_sentences

DIFFICULTIES = ["easy", "medium", "hard"]
QTYPES = ["mcq", "tf", "short"]
BLOOMS = ["remember", "understand", "apply", "analyze", "evaluate", "create"]
BLOOM_FOR = {"easy": ["remember"], "medium": ["understand"], "hard": ["apply", "analyze"]}


def norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def plan_slots(n: int, types: list[str], difficulties: list[str]) -> list[dict]:
    types = [t for t in types if t in QTYPES] or ["mcq"]
    difficulties = [d for d in difficulties if d in DIFFICULTIES] or DIFFICULTIES
    slots = []
    for i in range(n):
        d = difficulties[(i + i // len(types)) % len(difficulties)]
        blooms = BLOOM_FOR[d]
        slots.append({"type": types[i % len(types)], "difficulty": d, "bloom": blooms[(i // 2) % len(blooms)]})
    return slots


# --------------------------------------------------------------------------- #
# Validation shared by both engines
# --------------------------------------------------------------------------- #
def normalize_question(raw: dict, rng: random.Random | None = None) -> dict | None:
    if not isinstance(raw, dict):
        return None
    text = str(raw.get("question") or raw.get("text") or "").strip()
    qtype = str(raw.get("type") or raw.get("qtype") or "mcq").lower().replace("-", "_").replace("/", "_")
    qtype = {"multiple_choice": "mcq", "true_false": "tf", "truefalse": "tf", "boolean": "tf",
             "short_answer": "short", "shortanswer": "short"}.get(qtype, qtype)
    if len(text) < 8 or qtype not in QTYPES:
        return None
    difficulty = str(raw.get("difficulty") or "medium").lower()
    if difficulty not in DIFFICULTIES:
        difficulty = "medium"
    bloom = str(raw.get("bloom") or "").lower()
    if bloom not in BLOOMS:
        bloom = BLOOM_FOR[difficulty][0]
    answer = raw.get("answer")
    options: list[str] = []
    keywords = [str(k).strip() for k in (raw.get("keywords") or []) if str(k).strip()][:8]

    if qtype == "mcq":
        opts = raw.get("options") or []
        if isinstance(opts, dict):
            opts = list(opts.values())
        opts = [re.sub(r"^\s*[\(\[]?[A-Da-d1-4][\)\].:]\s+", "", str(o)).strip() for o in opts]
        opts = [o for i, o in enumerate(opts) if o and norm(o) not in [norm(x) for x in opts[:i]]]
        if len(opts) < 3:
            return None
        ans = answer
        if isinstance(ans, int) and 0 <= ans < len(opts):
            ans = opts[ans]
        ans = str(ans or "").strip()
        if re.fullmatch(r"[\(\[]?[A-Da-d][\)\].]?", ans):
            idx = ord(re.sub(r"[^A-Da-d]", "", ans).upper()) - 65
            ans = opts[idx] if idx < len(opts) else ""
        ans = re.sub(r"^\s*[\(\[]?[A-Da-d][\)\].:]\s+", "", ans)
        match = next((o for o in opts if norm(o) == norm(ans)), None)
        if not match:
            return None
        others = [o for o in opts if o != match][:3]
        options = others + [match]
        (rng or random).shuffle(options)
        answer = match
    elif qtype == "tf":
        val = str(answer).strip().lower()
        if val not in ("true", "false", "t", "f"):
            return None
        answer = "True" if val in ("true", "t") else "False"
        options = ["True", "False"]
    else:
        answer = str(answer or "").strip()
        if len(answer) < 2:
            return None
        if not keywords:
            keywords = key_terms_of(answer)

    return {
        "qtype": qtype, "difficulty": difficulty, "bloom": bloom, "text": text, "options": options,
        "answer": answer, "explanation": str(raw.get("explanation") or "").strip(),
        "keywords": keywords, "source_excerpt": str(raw.get("source_excerpt") or "").strip()[:600],
    }


def key_terms_of(text: str, limit: int = 6) -> list[str]:
    words = [w for w in re.findall(r"[A-Za-z][A-Za-z0-9\-]+", text) if w.lower() not in STOP and len(w) > 2]
    seen, out = set(), []
    for w in sorted(words, key=len, reverse=True):
        if w.lower()[:5] not in seen:
            seen.add(w.lower()[:5])
            out.append(w.lower())
        if len(out) >= limit:
            break
    return out


# --------------------------------------------------------------------------- #
# LLM engine
# --------------------------------------------------------------------------- #
SYSTEM = (
    "You are an experienced university examiner. You write precise, unambiguous, syllabus-aligned "
    "assessment questions with exactly one defensible correct answer. Reply with JSON only."
)


def _llm_generate(course_name: str, topic, slots: list[dict], avoid: list[str]) -> list[dict]:
    spec = "\n".join(
        f"{i + 1}. type={s['type']}, difficulty={s['difficulty']}, bloom={s['bloom']}" for i, s in enumerate(slots)
    )
    excerpt = (topic.content or "")[:6000]
    prompt = f"""Course: {course_name}
Syllabus topic: {topic.name}
Key terms: {", ".join(topic.keywords or []) or "n/a"}

Source material for this topic (may be only a list of sub-topics; if so, rely on standard
textbook knowledge of exactly these sub-topics and stay inside the topic):
\"\"\"
{excerpt}
\"\"\"

Write exactly {len(slots)} questions, one for each specification below:
{spec}

Rules:
- type "mcq": exactly 4 options, plausible distractors, one correct; "answer" is the exact text of the correct option. No "all/none of the above".
- type "tf": a single clear statement; "answer" is "True" or "False". Mix true and false statements.
- type "short": answerable in 1-2 sentences; "answer" is a model answer; "keywords" lists 3-6 essential terms a correct answer must mention.
- difficulty/bloom: easy=remember (recall facts/definitions), medium=understand (explain, compare, interpret), hard=apply/analyze (scenarios, calculations, reasoning about consequences).
- Each question must be self-contained (never say "according to the text" or "in the passage").
- "explanation": 1-2 sentences explaining why the answer is right.
- "source_excerpt": the sentence or sub-topic from the source material that the question is derived from.
- Do not repeat or paraphrase any of these existing questions: {avoid[:20] if avoid else "none"}

Return JSON: {{"questions": [{{"type": "...", "difficulty": "...", "bloom": "...", "question": "...", "options": ["..."], "answer": "...", "keywords": ["..."], "explanation": "...", "source_excerpt": "..."}}]}}"""
    data = llm.chat_json(SYSTEM, prompt)
    items = data.get("questions", []) if isinstance(data, dict) else data
    return items if isinstance(items, list) else []


# --------------------------------------------------------------------------- #
# Offline rule-based engine
# --------------------------------------------------------------------------- #
DEF_RE = re.compile(
    r"^(?:(?P<art>An?|The)\s+)?(?P<subj>[A-Za-z][\w\-/ ()]{1,70}?)\s+(?P<verb>is|are|refers to|is defined as|is called|means)\s+(?P<rest>.{20,})$"
)


def _terms(topic) -> list[str]:
    """Noun-like key terms, best first: defined terms, acronyms, proper phrases, multi-word keywords."""
    content = topic.content or ""
    keywords = [k for k in (topic.keywords or []) if len(k) >= 3]
    terms = defined_terms(content)
    terms += re.findall(r"\b[A-Z]{2,6}\b", content)
    terms += re.findall(r"(?<=[a-z,] )(?:[A-Z][a-z]+ ){1,2}[A-Z][a-z]+\b", content)
    terms += [k for k in keywords if " " in k or any(ch.isupper() for ch in k)]
    seen, out = set(), []
    for t in terms + keywords:
        if len(out) >= 6 and t in keywords and " " not in t and not any(ch.isupper() for ch in t) \
                and t.lower() not in seen and t not in terms:
            continue  # plain single words are a last resort only
        if t.lower() not in seen and t.lower() not in STOP:
            seen.add(t.lower())
            out.append(t)
    return out


def _find(term: str, sentence: str):
    return re.search(r"(?<![\w\-])" + re.escape(term) + r"(?![\w\-])", sentence, re.I)


def _swap(sentence: str, term: str, replacement: str) -> str:
    def repl(m):
        return replacement[:1].upper() + replacement[1:] if m.start() == 0 else replacement
    out = re.sub(r"(?<![\w\-])" + re.escape(term) + r"(?![\w\-])", repl, sentence, flags=re.I)
    if replacement and replacement[0].isalpha():  # keep "a"/"an" grammatical after the swap
        article = "an" if replacement[0].lower() in "aeiou" else "a"
        out = re.sub(r"\b([Aa])n?(?= " + re.escape(replacement) + r"\b)",
                     lambda m: ("A" if m.group(1) == "A" else "a") + article[1:], out, flags=re.I)
    return out


def _distractors(term: str, sentence: str, own: list[str], others: list[str], prefer_own: bool,
                 rng: random.Random, k: int = 3) -> list[str]:
    def ok(c):
        return norm(c) != norm(term) and not _find(c, sentence) and norm(c) not in norm(term) and norm(term) not in norm(c)

    def shape(c):
        return (c.isupper() == term.isupper()) + (abs(len(c.split()) - len(term.split())) <= 1)

    pools = [own, others] if prefer_own else [others, own]
    picked: list[str] = []
    for pool in pools:
        cands = [c for c in pool if ok(c) and norm(c) not in [norm(p) for p in picked]]
        rng.shuffle(cands)
        cands.sort(key=shape, reverse=True)
        picked += cands[: k - len(picked)]
        if len(picked) >= k:
            break
    return picked


def _offline_generate(topic, all_topics, slots: list[dict], existing: set[str], rng: random.Random) -> list[dict]:
    own = _terms(topic)
    others = [t for other in all_topics if other.id != topic.id for t in _terms(other)]
    sentences = [
        s for s in split_sentences((topic.content or "").replace("\n", " "))
        if 7 <= len(s.split()) <= 45 and not s.endswith("?")
    ]
    pairs = []  # (sentence, term)
    for s in sentences:
        hits = [t for t in own if _find(t, s)]
        if hits:
            pairs.append((s, hits))
    rng.shuffle(pairs)
    used: dict[str, int] = {}
    out: list[dict] = []

    def emit(q: dict) -> bool:
        key = norm(q["question"])
        if key in existing:
            return False
        existing.add(key)
        out.append(q)
        return True

    def from_sentence(slot, sentence, hits) -> dict | None:
        qtype, diff = slot["type"], slot["difficulty"]
        term = hits[used.get(sentence, 0) % len(hits)]
        base = {"type": qtype, "difficulty": diff, "bloom": slot["bloom"], "source_excerpt": sentence}
        m = DEF_RE.match(sentence)
        if qtype == "mcq":
            if diff == "hard" and len(pairs) >= 4:
                wrong = []
                for s2, h2 in rng.sample(pairs, len(pairs)):
                    if s2 == sentence or len(s2.split()) > 32:
                        continue
                    d = _distractors(h2[0], s2, own, others, True, rng, 1)
                    if d:
                        wrong.append(_swap(s2, h2[0], d[0]))
                    if len(wrong) == 3:
                        break
                if len(wrong) == 3 and len(sentence.split()) <= 32:
                    return {**base, "question": f"Which of the following statements about {topic.name} is correct?",
                            "options": wrong + [sentence], "answer": sentence,
                            "explanation": "Only this statement matches the source material; the others swap in an incorrect term."}
            ds = _distractors(term, sentence, own, others, diff != "easy", rng)
            if len(ds) < 3:
                return None
            if m and diff != "easy" and _find(term, m.group("subj")):
                desc = m.group("rest").rstrip(".")
                stem = f"Which term is best described as follows? \"{desc[0].upper() + desc[1:]}.\""
                term_ans = m.group("subj").strip()
                if _find(term_ans, m.group("rest")):
                    return None
                return {**base, "question": stem, "options": ds + [term_ans], "answer": term_ans,
                        "explanation": f"From the source material: \"{sentence}\""}
            stem = _swap(sentence, term, "_____")
            return {**base, "question": f"Fill in the blank: \"{stem}\"", "options": ds + [term], "answer": term,
                    "explanation": f"From the source material: \"{sentence}\""}
        if qtype == "tf":
            make_false = rng.random() < 0.5
            if make_false:
                ds = _distractors(term, sentence, own, others, diff == "hard", rng, 1)
                if ds:
                    return {**base, "question": f"True or False: {_swap(sentence, term, ds[0])}", "answer": "False",
                            "explanation": f"The correct statement is: \"{sentence}\""}
            return {**base, "question": f"True or False: {sentence}", "answer": "True",
                    "explanation": "This statement appears in the source material."}
        # short answer
        if m and len(m.group("subj").split()) <= 6:
            subj = m.group("subj").strip()
            verb = "are" if m.group("verb") == "are" else "is"
            art = f"{m.group('art').lower()} " if m.group("art") else ""
            question = (f"What {verb} {art}{subj}?" if diff == "easy"
                        else f"Define \"{subj}\" and state its significance in {topic.name}.")
            return {**base, "question": question, "answer": sentence, "keywords": key_terms_of(m.group("rest")),
                    "explanation": "Model answer taken from the source material."}
        return {**base, "question": f"In the context of {topic.name}, briefly explain: {term}.", "answer": sentence,
                "keywords": key_terms_of(_swap(sentence, term, "")), "explanation": "Model answer taken from the source material."}

    def from_syllabus(slot) -> dict | None:
        """Thin content (a bare list of sub-topics): ask syllabus-mapping questions."""
        kws = [k for k in (topic.keywords or []) if len(k) >= 3]
        if not kws:
            return None
        kw = rng.choice(kws)
        base = {"type": slot["type"], "difficulty": slot["difficulty"], "bloom": "remember",
                "source_excerpt": f"{topic.name}: {', '.join(kws[:8])}"}
        other_topics = [t for t in all_topics if t.id != topic.id]
        if slot["type"] == "mcq":
            if len(other_topics) >= 2 and rng.random() < 0.5:
                opts = [t.name for t in rng.sample(other_topics, min(3, len(other_topics)))]
                return {**base, "question": f"Under which syllabus topic is \"{kw}\" studied?",
                        "options": opts + [topic.name], "answer": topic.name,
                        "explanation": f"\"{kw}\" is listed under {topic.name} in the syllabus."}
            ds = [d for d in others if norm(d) not in {norm(k) for k in kws}]
            if len(ds) < 3:
                return None
            return {**base, "question": f"Which of the following is covered under \"{topic.name}\"?",
                    "options": rng.sample(ds, 3) + [kw], "answer": kw,
                    "explanation": f"\"{kw}\" is listed under {topic.name} in the syllabus."}
        if slot["type"] == "tf":
            if other_topics and rng.random() < 0.5:
                wrong = rng.choice(other_topics)
                if not any(norm(kw) == norm(k) for k in (wrong.keywords or [])):
                    return {**base, "question": f"True or False: \"{kw}\" is a sub-topic of \"{wrong.name}\".",
                            "answer": "False", "explanation": f"\"{kw}\" belongs to {topic.name}."}
            return {**base, "question": f"True or False: \"{kw}\" is a sub-topic of \"{topic.name}\".", "answer": "True",
                    "explanation": f"\"{kw}\" is listed under {topic.name} in the syllabus."}
        return {**base, "question": f"Write a short note on \"{kw}\" as studied in {topic.name}.",
                "answer": f"A good answer defines {kw}, explains how it works and relates it to {topic.name}.",
                "keywords": key_terms_of(kw), "explanation": "Open-ended recall item generated from the syllabus list."}

    for slot in slots:
        made = False
        order = sorted(pairs, key=lambda p: (slot["type"] == "short" and not DEF_RE.match(p[0]), used.get(p[0], 0)))
        for sentence, hits in order[:25]:
            q = from_sentence(slot, sentence, hits)
            used[sentence] = used.get(sentence, 0) + (1 if q else 0)
            if q and emit(q):
                made = True
                break
        if not made:
            for _ in range(8):
                q = from_syllabus(slot)
                if q and emit(q):
                    break
    return out


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def generate_questions(course_name: str, topic, all_topics, n: int, types: list[str], difficulties: list[str],
                       existing_texts: list[str], offline_only: bool = False) -> tuple[list[dict], str, str]:
    """Return (questions, engine, note). Each question dict is ready to store."""
    slots = plan_slots(n, types, difficulties)
    existing = {norm(t) for t in existing_texts}
    rng = random.Random(f"{topic.id}-{len(existing)}")
    results: list[dict] = []
    engine, note = ("offline" if offline_only else llm.provider()), ""

    if engine != "offline":
        try:
            raw_items = _llm_generate(course_name, topic, slots, existing_texts)
            engine = llm.last_used or engine
            for raw in raw_items:
                q = normalize_question(raw, rng)
                if q and norm(q["text"]) not in existing:
                    existing.add(norm(q["text"]))
                    q["origin"] = engine
                    results.append(q)
                if len(results) >= n:
                    break
        except llm.LLMError as exc:
            note = f"AI provider unavailable ({exc}); used the offline generator instead."

    if len(results) < n:
        missing = slots[len(results):]
        for raw in _offline_generate(topic, all_topics, missing, existing, rng):
            q = normalize_question(raw, rng)
            if q:
                q["origin"] = "offline"
                results.append(q)
        if engine != "offline" and not note and len(results) > 0:
            note = "Some questions were filled in by the offline generator."
    if len(results) < n and not note:
        note = "The source text for this topic is short, so fewer questions could be generated."
    return results, engine, note
