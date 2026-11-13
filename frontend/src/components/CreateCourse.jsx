import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { CheckCircle2, FileText, Loader2, Sparkles, UploadCloud, Wand2 } from "lucide-react";
import { api } from "../api";
import { useApp } from "../store";
import { Bar, ChipSelect, Modal, cx } from "./ui";

export const TYPE_OPTIONS = [{ value: "mcq", label: "Multiple choice" }, { value: "tf", label: "True / False" }, { value: "short", label: "Short answer" }];
export const DIFF_OPTIONS = [{ value: "easy", label: "Easy · Remember" }, { value: "medium", label: "Medium · Understand" }, { value: "hard", label: "Hard · Apply / Analyze" }];

/** Runs question generation one topic at a time so the UI can show real progress. */
export async function generateForTopics(courseId, topics, opts, onProgress) {
  let created = 0;
  const notes = [];
  for (let i = 0; i < topics.length; i++) {
    onProgress?.({ index: i, total: topics.length, topic: topics[i].name, created });
    try {
      const r = await api.post(`/api/courses/${courseId}/generate`, { topic_id: topics[i].id, ...opts });
      created += r.created.length;
      if (r.note) notes.push(`${topics[i].name}: ${r.note}`);
    } catch (e) {
      notes.push(`${topics[i].name}: ${e.message}`);
    }
  }
  onProgress?.({ index: topics.length, total: topics.length, topic: "", created });
  return { created, notes };
}

/** Upload wizard: document -> extracted topics -> generated, topic-mapped questions. */
export default function CreateCourse({ open, onClose, onCreated }) {
  const { user, meta, toast } = useApp();
  const teacher = user.role === "teacher";
  const navigate = useNavigate();
  const fileRef = useRef(null);
  const [step, setStep] = useState(1);
  const [form, setForm] = useState({ name: "", code: "", description: "", text: "" });
  const [file, setFile] = useState(null);
  const [source, setSource] = useState("file");
  const [drag, setDrag] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [course, setCourse] = useState(null);
  const [opts, setOpts] = useState({ count: 6, types: ["mcq", "tf"], difficulties: ["easy", "medium", "hard"] });
  const [progress, setProgress] = useState(null);

  const reset = () => { setStep(1); setForm({ name: "", code: "", description: "", text: "" }); setFile(null); setCourse(null); setProgress(null); setError(""); };
  const close = () => { if (busy) return; if (course) onCreated?.(course); reset(); onClose(); };
  const goTo = (c) => { onCreated?.(c); reset(); onClose(); navigate(teacher ? `/subjects/${c.id}` : `/courses/${c.id}`); };

  const pick = (f) => {
    if (!f) return;
    if (!/\.(pdf|docx|txt|md)$/i.test(f.name)) return setError("Please choose a PDF, DOCX or TXT file.");
    if (f.size > meta.max_upload_mb * 1024 * 1024) return setError(`That file is larger than ${meta.max_upload_mb} MB.`);
    setError("");
    setFile(f);
    if (!form.name) setForm((s) => ({ ...s, name: f.name.replace(/\.[^.]+$/, "").replace(/[_-]+/g, " ") }));
  };

  const create = async (e) => {
    e.preventDefault();
    if (source === "file" && !file) return setError("Add a document, or switch to “Paste text”.");
    if (source === "text" && form.text.trim().split(/\s+/).length < 25) return setError("Paste at least a few sentences of syllabus or notes.");
    setBusy(true);
    setError("");
    try {
      const fd = new FormData();
      fd.append("name", form.name);
      fd.append("code", form.code);
      fd.append("description", form.description);
      if (source === "file") fd.append("file", file);
      else if (source === "text") fd.append("text", form.text);
      const c = await api.form("/api/courses", fd);
      setCourse(c);
      if (c.topics.length) setStep(2);
      else goTo(c);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const generate = async () => {
    setBusy(true);
    setStep(3);
    const result = await generateForTopics(course.id, course.topics, opts, setProgress);
    setBusy(false);
    setProgress((p) => ({ ...p, done: true, ...result }));
    if (!result.created) toast("No questions could be generated from this document.", "error");
  };

  const sources = teacher ? [["file", "Upload document"], ["text", "Paste text"], ["none", "Start empty"]] : [["file", "Upload document"], ["text", "Paste text"]];

  return (
    <Modal open={open} onClose={busy ? undefined : close} wide title={step === 1 ? (teacher ? "New subject" : "New course from your material") : step === 2 ? "Topics found" : "Generating questions"}>
      <ol className="mb-5 flex items-center gap-2 text-xs font-semibold text-mute">
        {["Document", "Topics", "Questions"].map((s, i) => (
          <li key={s} className="flex items-center gap-2">
            <span className={cx("flex h-6 w-6 items-center justify-center rounded-full", step > i + 1 ? "bg-emerald-500 text-white" : step === i + 1 ? "bg-brand text-white dark:text-[#0b0d1a]" : "bg-soft")}>{step > i + 1 ? "✓" : i + 1}</span>
            <span className={step === i + 1 ? "text-ink" : ""}>{s}</span>
            {i < 2 && <span className="mx-1 h-px w-6 bg-line" />}
          </li>
        ))}
      </ol>

      {step === 1 && (
        <form onSubmit={create} className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-[1fr_140px]">
            <div>
              <label className="label" htmlFor="c-name">{teacher ? "Subject name" : "Course name"}</label>
              <input id="c-name" className="input" required minLength={2} placeholder="e.g. Computer Networks" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </div>
            <div>
              <label className="label" htmlFor="c-code">Code (optional)</label>
              <input id="c-code" className="input" placeholder="BCS502" value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} />
            </div>
          </div>
          <div>
            <span className="label">Syllabus / study material</span>
            <div className="mb-3 inline-flex rounded-xl bg-soft p-1">
              {sources.map(([v, l]) => (
                <button key={v} type="button" onClick={() => { setSource(v); setError(""); }} className={cx("rounded-lg px-3 py-1.5 text-xs font-semibold transition", source === v ? "bg-card text-ink shadow" : "text-mute")}>{l}</button>
              ))}
            </div>
            {source === "file" && (
              <div onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)}
                onDrop={(e) => { e.preventDefault(); setDrag(false); pick(e.dataTransfer.files[0]); }}
                onClick={() => fileRef.current?.click()} role="button" tabIndex={0} onKeyDown={(e) => e.key === "Enter" && fileRef.current?.click()}
                className={cx("flex cursor-pointer flex-col items-center rounded-2xl border-2 border-dashed px-6 py-9 text-center transition", drag ? "border-brand bg-brand/5" : "border-line hover:border-brand/60")}>
                <input ref={fileRef} type="file" accept=".pdf,.docx,.txt,.md" hidden onChange={(e) => pick(e.target.files[0])} />
                {file ? (
                  <><FileText className="h-8 w-8 text-brand" /><p className="mt-2 text-sm font-semibold">{file.name}</p><p className="text-xs text-mute">{(file.size / 1024).toFixed(0)} KB · click to replace</p></>
                ) : (
                  <><UploadCloud className="h-8 w-8 text-mute" /><p className="mt-2 text-sm font-semibold">Drop a PDF, DOCX or TXT here</p><p className="text-xs text-mute">or click to browse · up to {meta.max_upload_mb} MB</p></>
                )}
              </div>
            )}
            {source === "text" && <textarea className="input min-h-[170px]" placeholder={"Unit 1: Introduction\nPaste your syllabus, chapter or lecture notes here…"} value={form.text} onChange={(e) => setForm({ ...form, text: e.target.value })} />}
            {source === "none" && <p className="rounded-xl bg-soft px-4 py-3 text-sm text-mute">You will add topics by hand on the next screen.</p>}
          </div>
          {error && <p role="alert" className="rounded-xl bg-rose-500/10 px-3 py-2 text-sm font-medium text-rose-600 dark:text-rose-300">{error}</p>}
          <div className="flex justify-end gap-2">
            <button type="button" className="btn-ghost" onClick={close}>Cancel</button>
            <button className="btn-primary" disabled={busy}>{busy ? <><Loader2 className="h-4 w-4 animate-spin" />Reading document…</> : <><Wand2 className="h-4 w-4" />Extract topics</>}</button>
          </div>
        </form>
      )}

      {step === 2 && course && (
        <div className="space-y-5">
          <p className="text-sm text-mute">Found <b className="text-ink">{course.topics.length} topics</b> in <b className="text-ink">{course.source_name}</b> using {course.extraction_method === "headings" ? "the document's headings" : "LDA topic modelling"}.</p>
          <div className="max-h-56 space-y-2 overflow-y-auto pr-1">
            {course.topics.map((t, i) => (
              <div key={t.id} className="rounded-xl border border-line p-3">
                <div className="text-sm font-semibold">{i + 1}. {t.name}</div>
                <div className="mt-1.5 flex flex-wrap gap-1.5">{t.keywords.slice(0, 6).map((k) => <span key={k} className="chip py-0.5">{k}</span>)}</div>
              </div>
            ))}
          </div>
          <div className="grid gap-4 rounded-2xl bg-soft/60 p-4 sm:grid-cols-2">
            <div className="sm:col-span-2">
              <span className="label">Questions per topic: {opts.count}</span>
              <input type="range" min="3" max="12" value={opts.count} onChange={(e) => setOpts({ ...opts, count: +e.target.value })} className="w-full accent-[rgb(var(--brand))]" />
            </div>
            <div><span className="label">Question types</span><ChipSelect options={TYPE_OPTIONS} value={opts.types} onChange={(v) => v.length && setOpts({ ...opts, types: v })} /></div>
            <div><span className="label">Difficulty</span><ChipSelect options={DIFF_OPTIONS} value={opts.difficulties} onChange={(v) => v.length && setOpts({ ...opts, difficulties: v })} /></div>
          </div>
          <p className="flex items-start gap-2 text-xs text-mute">
            <Sparkles className={cx("mt-0.5 h-4 w-4 shrink-0", meta.ai_enabled ? "text-emerald-500" : "text-amber-500")} />
            {meta.ai_enabled ? `Questions will be written by ${meta.llm_provider} (${meta.llm_model}).` : "No AI key is configured, so the built-in offline generator will be used. Add a free Gemini or Groq key for richer questions."}
          </p>
          <div className="flex justify-end gap-2">
            <button className="btn-ghost" onClick={() => goTo(course)}>Skip for now</button>
            <button className="btn-primary" onClick={generate}><Sparkles className="h-4 w-4" />Generate {opts.count * course.topics.length} questions</button>
          </div>
        </div>
      )}

      {step === 3 && progress && (
        <div className="py-4 text-center">
          {progress.done ? <CheckCircle2 className="mx-auto h-12 w-12 text-emerald-500" /> : <Loader2 className="mx-auto h-12 w-12 animate-spin text-brand" />}
          <h3 className="mt-4 text-xl font-bold">{progress.done ? `${progress.created} questions ready` : `Writing questions for “${progress.topic}”`}</h3>
          <p className="sub mt-1">{progress.done ? (teacher ? "They are saved as drafts for you to review and approve." : "Every question is linked to its syllabus topic.") : `Topic ${Math.min(progress.index + 1, progress.total)} of ${progress.total} · ${progress.created} questions so far`}</p>
          <Bar value={progress.index / progress.total} className="mx-auto mt-5 h-2.5 max-w-sm" />
          {progress.done && progress.notes?.length > 0 && (
            <ul className="mx-auto mt-4 max-w-md space-y-1 rounded-xl bg-amber-500/10 p-3 text-left text-xs text-amber-800 dark:text-amber-200">{progress.notes.slice(0, 4).map((n) => <li key={n}>{n}</li>)}</ul>
          )}
          {progress.done && <button className="btn-primary mt-6" onClick={() => goTo(course)}>{teacher ? "Review question bank" : "Open course"}</button>}
        </div>
      )}
    </Modal>
  );
}
