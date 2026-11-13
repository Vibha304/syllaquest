# SyllaQuest

**Gamified AI-Based Syllabus-to-Quiz Learning System** (Mini Project BIS586, Dept. of ISE, BIT)

Upload a syllabus, chapter or notes. SyllaQuest extracts the topics, generates questions mapped to each
topic, serves them as a gamified adaptive quiz, and tracks topic-wise mastery. Teachers get a separate
workspace for building, reviewing and exporting question banks per subject.

Everything runs on free tools, including the AI model and hosting.

## What is implemented

| Synopsis module | Implementation |
| --- | --- |
| 1. Document ingestion | PDF (PyMuPDF), DOCX (python-docx), TXT/MD or pasted text. Font size, bold and heading styles are kept as heading hints. |
| 2. Topic extraction | Headings such as `Unit 3: Transport Layer`, `Module-2`, `2.1 Routing` seed the topics. Documents without headings fall back to LDA topic modelling (scikit-learn). Each topic gets TF-IDF key terms. |
| 3. Question generation and mapping | LLM prompt per topic with type (MCQ, True/False, short answer), difficulty and Bloom level. Every question row has a `topic_id` foreign key, shown as the syllabus map and the coverage matrix. |
| 4. Gamified quiz | Timer, instant feedback, XP scaled by difficulty and combo, levels, daily streaks, 17 badges, class and global leaderboards. |
| 5. Weak-topic detection and adaptive selection | Bayesian Knowledge Tracing per (student, topic). Topics under 50% mastery are flagged weak. Next topic is sampled by `(1 - mastery)^2`; difficulty follows a staircase (correct: harder, wrong: easier). Each question shows why it was picked. |
| VTU exam papers | Descriptive question papers in the VTU pattern: one section per module, two full questions with an OR choice, sub-questions with marks, Bloom level (L1-L6) and course outcome. Exports the paper and a scheme of valuation to Word. |
| Analytics | Student: mastery trend, XP per day, weak topics. Teacher: class mastery by topic, student heatmap, most-missed questions. |

### Teacher workspace

- Create a subject from a syllabus, pasted text, or from scratch
- Edit topics, key terms and source text
- Generate a question bank per topic: choose count, types, difficulty and Bloom levels
- Review drafts: edit, approve, delete, bulk actions, write questions manually
- Coverage matrix: topic by difficulty, Bloom level and type, with uncovered topics flagged
- Export to Word (with answer key), CSV or JSON
- Set VTU-pattern exam papers (see below), edit them, share them with the class and export to Word
- Publish with a class code; students join and their mastery appears in class analytics

### VTU examination papers

Open a subject and choose the **Exam papers** tab (students get the same section on their own
courses, and see papers their teacher has shared).

| Pattern | Marks per full question | Modules | Total |
| --- | --- | --- | --- |
| Semester End Exam | 20 | up to 5 | 100 marks, 3 hrs |
| Internal Assessment (CIE) | 25 | up to 3 | 25 to 75 marks, 90 min |
| Unit Test | 10 | up to 5 | 10 to 50 marks, 45 min |

1. Pick the pattern, the topics that form the modules, the cognitive level, semester and exam session.
2. Each module gets two alternative full questions split into parts (for example 6 + 6 + 8 or 10 + 10).
   Every part carries marks, a Bloom level and the module's course outcome.
3. Edit any sub-question, its marks, Bloom level or scheme; regenerate a single module; the page
   warns if a question's parts no longer add up.
4. Download the question paper and the scheme of valuation as Word files, and optionally share the
   paper with enrolled students (the scheme stays private).

With an AI key the model writes numerical, derivation and design questions with a marks breakdown.
Without one, the offline generator builds define / explain / compare / illustrate questions from each
topic's key terms, which is a starting draft rather than a finished paper.

## Demo accounts

Created automatically on first start, with a sample Computer Networks class (class code `CN2026`).

| Role | Email | Password |
| --- | --- | --- |
| Student | `student@demo.edu` | `demo1234` |
| Teacher | `teacher@demo.edu` | `demo1234` |

Set `SEED_DEMO=false` to start with an empty database.

## Run in VS Code

Requirements: [Python 3.10+](https://www.python.org/downloads/), [Node.js 18+](https://nodejs.org/), VS Code.

1. **File > Open Folder** and choose the `syllaquest` folder.
2. Open a terminal (**Terminal > New Terminal**) and start the backend:

   Windows (PowerShell):
   ```powershell
   cd backend
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   pip install -r requirements-dev.txt
   uvicorn app.main:app --reload --port 8000
   ```

   macOS / Linux:
   ```bash
   cd backend
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements-dev.txt
   uvicorn app.main:app --reload --port 8000
   ```

3. Open a second terminal (the **+** button) and start the frontend:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

4. Open <http://localhost:5173> and sign in with a demo account.

After the first install you can use **Terminal > Run Build Task** (`Ctrl+Shift+B`), which starts both
servers. API docs are at <http://localhost:8000/docs>. Run the tests with `python -m pytest -q` inside
`backend`.

If PowerShell blocks the activate script, run
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.

## Turn on AI question generation (free)

Without a key the app uses a built-in rule-based generator. It works offline but only produces
fill-in-the-blank, definition and true/false items from sentences in the document. For real
LLM-written questions, add one free key:

1. Copy `.env.example` to `.env` in the project root.
2. Set one of these, then restart the backend:
   - `GEMINI_API_KEY` from <https://aistudio.google.com/apikey> (Google Gemini free tier)
   - `GROQ_API_KEY` from <https://console.groq.com/keys> (hosted Llama 3, free tier)
   - `OLLAMA_URL=http://localhost:11434` to use a local model through [Ollama](https://ollama.com)

The sidebar shows which engine is active. If a model name has been retired by the provider, change
`GEMINI_MODEL` or `GROQ_MODEL` in `.env`. If the AI call fails or hits a rate limit, the offline
generator fills in automatically.

## Deploy for free (Render + Neon)

The Dockerfile builds the React app and serves it from the FastAPI server, so one free web service
hosts everything.

1. Push this folder to a GitHub repository:
   ```bash
   git remote add origin https://github.com/YOUR-USERNAME/syllaquest.git
   ```
   ```bash
   git push -u origin main
   ```
2. Create a free PostgreSQL database at <https://neon.tech> and copy its connection string.
3. At <https://render.com> choose **New > Blueprint**, pick the repository (it reads `render.yaml`),
   and fill in:
   - `DATABASE_URL`: the Neon connection string
   - `GEMINI_API_KEY` or `GROQ_API_KEY`: your free AI key (optional)
4. Deploy. The app is served at `https://<service-name>.onrender.com`.

Notes on the free tier: the service sleeps after about 15 minutes without traffic, so the first
request afterwards takes up to a minute. If `DATABASE_URL` is not set the app uses a SQLite file
that is erased on every redeploy.

To run the same container locally with PostgreSQL: `docker compose up --build`, then open
<http://localhost:8000>.

## Project structure

```
syllaquest/
  backend/
    app/
      main.py            FastAPI app, serves the built frontend in production
      models.py          Users, courses, topics, questions, attempts, mastery, badges
      routers/           auth, courses (topics, bank, coverage, export, analytics), exams, quiz, me
      services/
        parser.py        Module 1: PDF / DOCX / TXT ingestion
        topics.py        Module 2: heading detection, LDA fallback, key terms
        llm.py           Gemini / Groq / Ollama client
        generator.py     Module 3: LLM generation, validation, offline fallback
        gamification.py  Module 4: XP, levels, streaks, badges
        bkt.py           Module 5: Bayesian Knowledge Tracing
        adaptive.py      Module 5: next-question selection
        exam.py          VTU-pattern exam paper generation
        exporter.py      DOCX / CSV / JSON question-bank and exam paper export
      seed.py            Demo data
    tests/               End-to-end API tests
  frontend/              React + Vite + Tailwind CSS
  Dockerfile, docker-compose.yml, render.yaml, .github/workflows/ci.yml
```

## Differences from the synopsis

- **BERTopic / sentence-transformers** are replaced by heading detection plus scikit-learn LDA. The
  transformer stack needs more memory than free hosting provides (512 MB).
- **Redis** is not used; the leaderboard is computed from PostgreSQL, which is fast enough at class scale.
- **Scanned PDFs** are not supported (no OCR). The app reports this and asks for a text PDF.
- **Short answers** are graded by key-term overlap with the model answer, so grading is approximate.
