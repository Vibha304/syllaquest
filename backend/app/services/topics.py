"""Module 2 - Topic extraction and identification.

Strategy (cheap enough for free hosting, no GPU):
  1. Explicit headings ("Unit 3: Transport Layer", "2.1 Routing", bold/large
     lines) seed the topic list.
  2. If the document has no usable headings, fall back to LDA topic modelling
     (scikit-learn) over paragraph chunks.
  3. Each topic gets TF-IDF keywords and a short summary.
"""
import re

from sklearn.decomposition import LatentDirichletAllocation
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, CountVectorizer, TfidfVectorizer

STOP = set(ENGLISH_STOP_WORDS) | {
    "also", "using", "used", "use", "uses", "called", "known", "example", "examples", "one", "two", "three",
    "may", "can", "like", "etc", "unit", "module", "chapter", "section", "topic", "introduction", "hours",
    "hrs", "page", "figure", "fig", "table", "following", "given", "based", "various", "different", "types",
    "type", "new", "many", "much", "well", "must", "will", "shall", "thus", "hence", "however", "therefore",
}
SKIP_TITLES = re.compile(
    r"^(table of )?contents?$|^references?$|^bibliography$|^index$|^acknowledge?ments?$|^text ?books?$|"
    r"^reference books?$|^suggested (readings?|learning resources)$|^web ?links.*$|^abstract$|^preface$",
    re.I,
)
UNIT_RE = re.compile(
    r"^(unit|module|chapter|section|part|topic|lecture|week|lesson)\s*[-–—:#]?\s*(\d{1,2}|[ivxlc]{1,5})\b[\s:.\-–—)]*(.*)$",
    re.I,
)
NUM_RE = re.compile(r"^(\d{1,2}(?:\.\d{1,2}){0,2})[.)]?\s+([A-Z][^.!?]{2,90})$")


def _title_case(s: str) -> str:
    s = s.strip(" :-–—.\t")
    return s.title() if s.isupper() and len(s) > 4 else s


def _split_long_heading(rest: str) -> tuple[str, str]:
    """'Transport Layer: UDP, TCP, congestion...' -> ('Transport Layer', 'UDP, TCP, ...')."""
    rest = rest.strip()
    if len(rest.split()) <= 10:
        return rest, ""
    m = re.match(r"^(.{3,80}?)\s*[:–—]\s+(.*)$", rest) or re.match(r"^(.{3,80}?)\s+-\s+(.*)$", rest)
    if m:
        return m.group(1), m.group(2)
    m = re.match(r"^([^.,;]{3,80})[.,;]\s*(.*)$", rest)
    if m and len(m.group(1).split()) <= 10:
        return m.group(1), rest
    words = rest.split()
    return " ".join(words[:6]), rest


def _classify(block: dict) -> tuple[int, str, str] | None:
    """Return (level, title, leftover_text) if the block looks like a heading."""
    text = block["text"]
    if not text:
        return None
    m = UNIT_RE.match(text)
    if m:
        title, extra = _split_long_heading(m.group(3))
        label = f"{m.group(1).title()} {m.group(2).upper() if not m.group(2).isdigit() else m.group(2)}"
        return 1, (title or label), extra
    words = text.split()
    m = NUM_RE.match(text)
    if m and len(words) <= 12:
        return (1 if "." not in m.group(1) else 2), m.group(2), ""
    if block.get("heading") and 1 <= len(words) <= 14 and re.search(r"[A-Za-z]{3}", text):
        return 2, re.sub(r"^\d+(\.\d+)*[.)]?\s*", "", text), ""
    letters = re.sub(r"[^A-Za-z]", "", text)
    if letters.isupper() and len(letters) >= 5 and 1 <= len(words) <= 8 and not text.endswith("."):
        return 2, text, ""
    return None


def _sections(blocks: list[dict]) -> list[dict]:
    sections: list[dict] = []
    current: dict | None = None
    pending_label = False
    for block in blocks:
        text = block["text"]
        head = _classify(block)
        if head and not (pending_label and current is not None):
            level, title, extra = head
            current = {"title": _title_case(title), "level": level, "parts": [extra] if extra else []}
            sections.append(current)
            # "Module 1" alone on a line: the real title is on the next line
            um = UNIT_RE.match(text)
            pending_label = bool(um) and not um.group(3).strip(" :-–—.")
            continue
        if pending_label and current is not None and text:
            text = re.sub(r"^\d+(\.\d+)*[.)]?\s+", "", text)
            m = re.match(r"^(.{3,80}?)\s*[:–—]\s+(.*)$", text)
            if m:
                title, extra = m.group(1), m.group(2)
            elif len(text.split()) <= 8 and not text.endswith(","):
                title, extra = text, ""
            else:
                title, extra = _split_long_heading(text + " " * 0) if len(text.split()) > 10 else (
                    re.split(r"[,;.]", text)[0], text)
            current["title"] = _title_case(title)
            if extra:
                current["parts"].append(extra)
            pending_label = False
            continue
        if not text:
            if current and current["parts"] and current["parts"][-1] != "\n":
                current["parts"].append("\n")
            continue
        if current is None:
            current = {"title": "", "level": 9, "parts": []}
            sections.append(current)
        current["parts"].append(text)

    out = []
    for s in sections:
        text = re.sub(r" *\n *", "\n", " ".join(s["parts"])).strip()
        out.append({"title": s["title"], "level": s["level"], "text": text})
    return out


def _merge_sections(sections: list[dict], max_topics: int = 12) -> list[dict]:
    secs = [s for s in sections if s["title"] and not SKIP_TITLES.match(s["title"])]
    # If the document has explicit Unit/Module level headings, fold sub-headings into them.
    top = [s for s in secs if s["level"] == 1]
    if len(top) >= 2:
        first = next(i for i, s in enumerate(secs) if s["level"] == 1)
        secs = [s for i, s in enumerate(secs) if i >= first or len(s["text"].split()) >= 40]  # drop title-page preamble
        merged: list[dict] = []
        for s in secs:
            if s["level"] == 1 or not merged:
                merged.append(dict(s))
            else:
                merged[-1]["text"] += f"\n{s['title']}. {s['text']}"
        secs = merged
    # Fold near-empty sections into their predecessor.
    merged = []
    for s in secs:
        if merged and len(s["text"].split()) < 12:
            merged[-1]["text"] += f"\n{s['title']}. {s['text']}"
        else:
            merged.append(dict(s))
    secs = merged
    while len(secs) > max_topics:
        i = min(range(1, len(secs)), key=lambda k: len(secs[k]["text"]))
        secs[i - 1]["text"] += f"\n{secs[i]['title']}. {secs[i]['text']}"
        secs.pop(i)
    return [s for s in secs if len(s["text"].split()) >= 5]


def split_sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text)
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])", text)
    return [p.strip() for p in parts if p.strip()]


def _lda_topics(text: str) -> list[dict]:
    paragraphs = [p.strip() for p in re.split(r"\n{1,}", text) if len(p.split()) >= 8]
    chunks: list[str] = []
    for p in paragraphs:
        sents = split_sentences(p)
        for i in range(0, len(sents), 4):
            chunk = " ".join(sents[i:i + 4])
            if len(chunk.split()) >= 8:
                chunks.append(chunk)
    if len(chunks) < 4:
        return [{"title": "", "text": text}]
    k = max(2, min(8, len(chunks) // 4))
    try:
        vec = CountVectorizer(stop_words=list(STOP), ngram_range=(1, 2), min_df=1, max_features=3000,
                              token_pattern=r"(?u)\b[A-Za-z][A-Za-z\-]{2,}\b")
        X = vec.fit_transform(chunks)
        lda = LatentDirichletAllocation(n_components=k, random_state=42, max_iter=40, learning_method="batch")
        doc_topic = lda.fit_transform(X)
    except ValueError:
        return [{"title": "", "text": text}]
    groups: dict[int, list[str]] = {}
    for chunk, dist in zip(chunks, doc_topic):
        groups.setdefault(int(dist.argmax()), []).append(chunk)
    return [{"title": "", "text": " ".join(g)} for _, g in sorted(groups.items()) if g]


def _keywords(texts: list[str], top: int = 10) -> list[list[str]]:
    if not texts:
        return []
    try:
        vec = TfidfVectorizer(stop_words=list(STOP), ngram_range=(1, 3), sublinear_tf=True, max_features=6000,
                              token_pattern=r"(?u)\b[A-Za-z][A-Za-z0-9\-]{1,}\b")
        X = vec.fit_transform(texts)
    except ValueError:
        return [[] for _ in texts]
    terms = vec.get_feature_names_out()
    result = []
    for i, text in enumerate(texts):
        row = X[i].toarray().ravel()
        low = text.lower()
        scored = []
        for j in row.argsort()[::-1][:60]:
            if row[j] <= 0:
                break
            term = terms[j]
            n = len(term.split())
            # Prefer multi-word phrases that genuinely repeat, and acronyms
            boost = 1.0 + (0.5 * (n - 1) if low.count(term) >= 2 else -0.3 * (n - 1))
            scored.append((row[j] * boost, term))
        chosen: list[str] = []
        for _, term in sorted(scored, reverse=True):
            if any(term in c or c in term for c in chosen):
                continue
            chosen.append(term)
            if len(chosen) >= top:
                break
        result.append([_restore_case(c, text) for c in chosen])
    return result


def _restore_case(term: str, text: str) -> str:
    m = re.search(r"\b" + re.escape(term) + r"\b", text, re.I)
    if not m:
        return term
    found = m.group(0)
    if found.isupper() or (found[:1].isupper() and m.start() > 0 and text[m.start() - 2:m.start() - 1] not in ".!?"):
        return found
    return term


DEF_SUBJECT = re.compile(
    r"^(?:(?:An?|The)\s+)?([A-Za-z][\w\-/]*(?: [\w\-/]+){0,3}?)\s+(?:is|are|refers to|is defined as|is called|means)\s+\S"
)
_NOT_SUBJECT = {"it", "this", "that", "these", "those", "there", "they", "he", "she", "we", "each", "which", "what"}


def defined_terms(text: str) -> list[str]:
    """Subjects of definitional sentences ("X is a ...") - the best key terms a text offers."""
    out: list[str] = []
    for sent in split_sentences(text.replace("\n", " ")):
        m = DEF_SUBJECT.match(sent)
        if not m:
            continue
        subj = m.group(1).strip()
        first = subj.split()[0].lower()
        if first in _NOT_SUBJECT or first in STOP or len(subj) < 2:
            continue
        if not subj.split()[0].isupper() and not any(ch.isupper() for ch in subj[1:]):
            subj = subj[0].lower() + subj[1:]
        if subj.lower() not in [o.lower() for o in out]:
            out.append(subj)
    return out


def _syllabus_phrases(text: str) -> list[str]:
    """Syllabus documents list sub-topics as comma separated phrases."""
    parts = re.split(r"[,;:\n•·]| - |\.\s", text)
    out = []
    for p in parts:
        p = re.sub(r"^(and|or)\s+", "", p.strip(" .-–()"), flags=re.I)
        if p.count("(") != p.count(")"):
            continue
        if 1 <= len(p.split()) <= 5 and len(p) >= 3 and re.search(r"[A-Za-z]{2}", p) and p.lower() not in STOP:
            if p.lower() not in [o.lower() for o in out]:
                out.append(p)
    return out


def _auto_title(keywords: list[str]) -> str:
    picks = [k for k in keywords if len(k) > 2][:2]
    return " & ".join(k if k.isupper() else k.title() for k in picks) or "General Concepts"


def extract_topics(blocks: list[dict]) -> tuple[list[dict], str]:
    """Return ([{name, summary, content, keywords}], method)."""
    sections = _merge_sections(_sections(blocks))
    method = "headings"
    if len(sections) < 2:
        full = "\n".join(b["text"] for b in blocks)
        sections = _lda_topics(full)
        method = "lda" if len(sections) > 1 else "single"
    keyword_sets = _keywords([s["text"] for s in sections])
    topics = []
    seen_names: set[str] = set()
    for s, kws in zip(sections, keyword_sets):
        text = s["text"].strip()
        words = len(text.split())
        commas = text.count(",") + text.count(";")
        if words and commas / words > 0.09:  # syllabus-style list of sub-topics
            phrases = _syllabus_phrases(text)
            kws = (phrases + [k for k in kws if k.lower() not in {p.lower() for p in phrases}])[:14]
        else:
            defined = defined_terms(text)
            low = {d.lower() for d in defined}
            kws = (defined + [k for k in kws if k.lower() not in low])[:16]
        name = (s["title"] or _auto_title(kws))[:120]
        base, n = name, 2
        while name.lower() in seen_names:
            name, n = f"{base} ({n})", n + 1
        seen_names.add(name.lower())
        sents = split_sentences(text.replace("\n", " "))
        summary = " ".join(sents[:2])[:280] if sents else text[:280]
        topics.append({"name": name, "summary": summary, "content": text[:20000], "keywords": kws})
    return topics, method
