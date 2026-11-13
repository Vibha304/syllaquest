import { useEffect, useState } from "react";
import { AlertTriangle, ArrowLeft, Check, Download, FileText, Loader2, Pencil, Plus, RefreshCw, ScrollText, Sparkles, Trash2, X } from "lucide-react";
import { api } from "../api";
import { useApp, useLoad } from "../store";
import { Bar, ChipSelect, Empty, ErrorBox, Modal, Spinner, Toggle, cx } from "./ui";

const PATTERNS = [
  { value: "see", label: "Semester End Exam", hint: "100 marks · 3 hrs · 5 modules × 20 marks", max: 5, marks: 20 },
  { value: "cie", label: "Internal Assessment (CIE)", hint: "25 marks per module · 90 min · up to 3 modules", max: 3, marks: 25 },
  { value: "quiz", label: "Unit Test", hint: "10 marks per module · 45 min", max: 5, marks: 10 },
];
const LEVELS = [{ value: "foundational", label: "Foundational (L1–L2)" }, { value: "balanced", label: "Balanced (L1–L4)" }, { value: "advanced", label: "Advanced (L2–L5)" }];
const SEMESTERS = ["", "First", "Second", "Third", "Fourth", "Fifth", "Sixth", "Seventh", "Eighth"];
const WORDS = ["", "ONE", "TWO", "THREE", "FOUR", "FIVE", "SIX", "SEVEN", "EIGHT"];

/** VTU-pattern examination papers for a course: generate, edit, share and export. */
export default function ExamPapers({ course }) {
  const { meta, toast } = useApp();
  const owner = course.is_owner;
  const list = useLoad(`/api/courses/${course.id}/papers`);
  const [openId, setOpenId] = useState(null);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState(null);
  const [progress, setProgress] = useState(null);

  const startNew = () => {
    setForm({ pattern: "see", level: "balanced", topic_ids: course.topics.slice(0, 5).map((t) => t.id), semester: "", session: "", title: "" });
    setCreating(true);
  };
  const pattern = PATTERNS.find((p) => p.value === form?.pattern);

  const create = async (e) => {
    e.preventDefault();
    const ordered = course.topics.filter((t) => form.topic_ids.includes(t.id)).map((t) => t.id).slice(0, pattern.max);
    try {
      const paper = await api.post(`/api/courses/${course.id}/papers`, { ...form, topic_ids: ordered });
      const notes = [];
      for (let i = 0; i < paper.module_count; i++) {
        setProgress({ index: i, total: paper.module_count, topic: paper.modules[i].topic });
        const r = await api.post(`/api/papers/${paper.id}/modules/${i}/generate`);
        if (r.note) notes.push(r.note);
      }
      setProgress(null);
      setCreating(false);
      if (notes.length) toast(notes[0], "info");
      list.reload();
      setOpenId(paper.id);
    } catch (err) {
      setProgress(null);
      toast(err.message, "error");
      list.reload();
    }
  };

  if (openId) return <PaperView id={openId} course={course} onBack={() => { setOpenId(null); list.reload(); }} />;
  if (list.loading && !list.data) return <Spinner />;
  if (list.error) return <ErrorBox message={list.error} onRetry={list.reload} />;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="sub max-w-2xl">{owner
          ? "Set descriptive question papers in the VTU pattern: two full questions per module with an OR choice, sub-questions carrying marks, Bloom level and course outcome."
          : "Model question papers shared by your teacher, in the VTU examination pattern."}</p>
        {owner && <button className="btn-primary" onClick={startNew} disabled={!course.topics.length}><Plus className="h-4 w-4" />New question paper</button>}
      </div>

      {list.data.length === 0 ? (
        <Empty icon={ScrollText} title={owner ? "No question papers yet" : "No model papers shared yet"}
          action={owner && course.topics.length > 0 && <button className="btn-primary" onClick={startNew}>Generate a VTU paper</button>}>
          {owner ? (course.topics.length ? "Pick the modules and SyllaQuest drafts a full paper with a scheme of valuation. You can edit every question before exporting to Word." : "Add topics to this course first; each topic becomes a module of the paper.")
            : "When your teacher shares a model paper it will appear here for download."}
        </Empty>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {list.data.map((p) => (
            <button key={p.id} onClick={() => setOpenId(p.id)} className="card group flex flex-col p-5 text-left transition hover:-translate-y-0.5 hover:border-brand/50">
              <div className="flex items-center justify-between gap-2">
                <span className="chip">{p.pattern_label}</span>
                {owner && <span className={cx("rounded-full px-2.5 py-1 text-xs font-semibold", p.shared ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300" : "bg-soft text-mute")}>{p.shared ? "Shared" : "Private"}</span>}
              </div>
              <h3 className="mt-3 text-base font-bold leading-snug group-hover:text-brand">{p.title}</h3>
              <p className="mt-1 text-xs text-mute">{p.max_marks} marks · {p.duration} · {p.module_count} module{p.module_count > 1 ? "s" : ""}{p.session ? ` · ${p.session}` : ""}</p>
              {!p.ready && <p className="mt-2 flex items-center gap-1.5 text-xs font-semibold text-amber-600 dark:text-amber-300"><AlertTriangle className="h-3.5 w-3.5" />Some modules are not generated yet</p>}
            </button>
          ))}
        </div>
      )}

      <Modal open={creating} onClose={progress ? undefined : () => setCreating(false)} title="New VTU question paper" wide>
        {form && (progress ? (
          <div className="py-6 text-center">
            <Loader2 className="mx-auto h-10 w-10 animate-spin text-brand" />
            <h3 className="mt-4 text-lg font-bold">Setting Module {progress.index + 1}: {progress.topic}</h3>
            <p className="sub mt-1">Module {progress.index + 1} of {progress.total}</p>
            <Bar value={progress.index / progress.total} className="mx-auto mt-5 h-2.5 max-w-sm" />
          </div>
        ) : (
          <form onSubmit={create} className="space-y-5">
            <div>
              <span className="label">Exam pattern</span>
              <div className="grid gap-2 sm:grid-cols-3">
                {PATTERNS.map((p) => (
                  <button key={p.value} type="button" aria-pressed={form.pattern === p.value}
                    onClick={() => setForm({ ...form, pattern: p.value, topic_ids: course.topics.slice(0, p.max).map((t) => t.id) })}
                    className={cx("rounded-xl border p-3 text-left transition", form.pattern === p.value ? "border-brand bg-brand/10" : "border-line hover:border-brand/50")}>
                    <div className="text-sm font-bold">{p.label}</div><div className="mt-0.5 text-xs text-mute">{p.hint}</div>
                  </button>
                ))}
              </div>
            </div>
            <div>
              <span className="label">Modules ({form.topic_ids.length} of up to {pattern.max}) · total {form.topic_ids.length * pattern.marks} marks</span>
              <ChipSelect value={form.topic_ids} options={course.topics.map((t) => ({ value: t.id, label: t.name }))}
                onChange={(v) => v.length && v.length <= pattern.max && setForm({ ...form, topic_ids: v })} />
              <p className="mt-1.5 text-xs text-mute">Each selected topic becomes one module, in syllabus order.</p>
            </div>
            <div><span className="label">Cognitive level</span><ChipSelect multi={false} value={form.level} options={LEVELS} onChange={(v) => setForm({ ...form, level: v })} /></div>
            <div className="grid gap-3 sm:grid-cols-3">
              <div><label className="label" htmlFor="p-sem">Semester</label><select id="p-sem" className="input" value={form.semester} onChange={(e) => setForm({ ...form, semester: e.target.value })}>{SEMESTERS.map((s) => <option key={s} value={s}>{s || "Not specified"}</option>)}</select></div>
              <div><label className="label" htmlFor="p-ses">Exam session</label><input id="p-ses" className="input" placeholder="Dec.2026/Jan.2027" value={form.session} onChange={(e) => setForm({ ...form, session: e.target.value })} /></div>
              <div><label className="label" htmlFor="p-title">Paper title (optional)</label><input id="p-title" className="input" placeholder="Model Question Paper 1" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /></div>
            </div>
            <p className="flex items-start gap-2 rounded-xl bg-soft px-3 py-2.5 text-xs text-mute">
              <Sparkles className={cx("mt-0.5 h-4 w-4 shrink-0", meta.ai_enabled ? "text-emerald-500" : "text-amber-500")} />
              {meta.ai_enabled ? `Questions will be written by ${meta.llm_provider} (${meta.llm_model}).` : "No AI key is configured: the offline generator builds questions from the key terms of each topic. Add a free Gemini or Groq key for numerical, derivation and design questions."}
            </p>
            <div className="flex justify-end gap-2"><button type="button" className="btn-ghost" onClick={() => setCreating(false)}>Cancel</button><button className="btn-primary"><Sparkles className="h-4 w-4" />Generate paper</button></div>
          </form>
        ))}
      </Modal>
    </div>
  );
}

function PaperView({ id, course, onBack }) {
  const { toast } = useApp();
  const [paper, setPaper] = useState(null);
  const [error, setError] = useState("");
  const [edit, setEdit] = useState(null); // {m, q, p, text, marks, bloom, scheme}
  const [busy, setBusy] = useState("");
  const [showScheme, setShowScheme] = useState(false);

  useEffect(() => { api.get(`/api/papers/${id}`).then(setPaper).catch((e) => setError(e.message)); }, [id]);
  if (error) return <ErrorBox message={error} onRetry={onBack} />;
  if (!paper) return <Spinner />;
  const owner = paper.is_owner;

  const run = async (key, fn, ok) => {
    setBusy(key);
    try { const r = await fn(); if (r) setPaper(r.paper || r); if (ok) toast(ok, "success"); }
    catch (e) { toast(e.message, "error"); }
    setBusy("");
  };
  const savePart = (e) => {
    e.preventDefault();
    const modules = structuredClone(paper.modules);
    modules[edit.m].questions[edit.q].parts[edit.p] = { text: edit.text.trim(), marks: +edit.marks, bloom: edit.bloom, scheme: edit.scheme.split("\n").map((s) => s.trim()).filter(Boolean) };
    run("save", () => api.patch(`/api/papers/${id}`, { modules }).then((r) => { setEdit(null); return r; }));
  };
  const download = (kind) => run(kind, () => api.download(`/api/papers/${id}/export?kind=${kind}`, `question_paper_${kind}.docx`).then(() => null));
  const remove = async () => {
    if (!confirm("Delete this question paper?")) return;
    await api.del(`/api/papers/${id}`);
    onBack();
  };
  let number = 0;
  const heading = [paper.semester && `${paper.semester} Semester`, "B.E. Degree", paper.pattern === "see" ? "Examination" : paper.pattern_label].filter(Boolean).join(" ") + (paper.session ? `, ${paper.session}` : "");

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <button className="btn-ghost" onClick={onBack}><ArrowLeft className="h-4 w-4" />All papers</button>
        <span className="flex-1" />
        {owner && <Toggle checked={showScheme} onChange={setShowScheme} label="Show scheme" />}
        {owner && <Toggle checked={paper.shared} onChange={(v) => run("share", () => api.patch(`/api/papers/${id}`, { shared: v }), v ? "Shared with enrolled students" : "No longer shared")} label="Share with students" />}
        <button className="btn-soft" disabled={!!busy || !paper.ready} onClick={() => download("paper")}>{busy === "paper" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}Question paper</button>
        {owner && <button className="btn-soft" disabled={!!busy || !paper.ready} onClick={() => download("scheme")}>{busy === "scheme" ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileText className="h-4 w-4" />}Scheme of valuation</button>}
        {owner && <button className="btn-danger" onClick={remove} aria-label="Delete paper"><Trash2 className="h-4 w-4" /></button>}
      </div>

      <article className="card mx-auto max-w-4xl overflow-x-auto p-5 sm:p-8" style={{ fontFamily: 'Georgia, "Times New Roman", serif' }}>
        <header className="text-center">
          <div className="flex items-center justify-between text-sm font-bold">
            <span className="flex items-center gap-1">USN {Array.from({ length: 10 }, (_, i) => <span key={i} className="inline-block h-5 w-4 border border-ink/50" />)}</span>
            <span>{course.code}</span>
          </div>
          <p className="mt-4 text-base font-bold">{heading}</p>
          <h2 className="mt-1 text-xl font-bold" style={{ fontFamily: "inherit" }}>{course.name}</h2>
          <div className="mt-3 flex justify-between text-sm font-bold"><span>Time: {paper.duration}</span><span>Max. Marks: {paper.max_marks}</span></div>
          <p className="mt-2 text-left text-sm italic"><b className="not-italic">Note:</b> {paper.module_count === 1 ? "Answer any ONE full question." : `Answer any ${WORDS[paper.module_count]} full questions, choosing ONE full question from each module.`} M: Marks, L: Bloom's level, C: Course outcome.</p>
        </header>

        <table className="mt-4 w-full min-w-[560px] border-collapse text-sm">
          <thead><tr className="border-y-2 border-ink/60 text-xs">
            <th className="w-12 py-1.5">Q.No</th><th className="w-6" /><th className="py-1.5 text-left">Question</th><th className="w-9">M</th><th className="w-9">L</th><th className="w-11">C</th>{owner && <th className="w-8" />}
          </tr></thead>
          <tbody>
            {paper.modules.map((m, mi) => (
              <ModuleRows key={mi}>
                <tr className="border-b border-ink/30 bg-soft/60"><td colSpan={owner ? 7 : 6} className="py-1.5 text-center font-bold">
                  Module – {mi + 1}{owner && <span className="ml-2 font-sans text-xs font-medium text-mute">{m.topic}</span>}
                  {owner && <button className="btn-ghost btn-sm ml-2 font-sans" disabled={!!busy} onClick={() => run(`gen${mi}`, () => api.post(`/api/papers/${id}/modules/${mi}/generate`), "Module regenerated")}>
                    {busy === `gen${mi}` ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}{m.questions.length ? "Regenerate" : "Generate"}</button>}
                </td></tr>
                {m.questions.map((q, qi) => {
                  number += 1;
                  const total = q.parts.reduce((a, p) => a + p.marks, 0);
                  return (
                    <ModuleRows key={qi}>
                      {qi > 0 && <tr className="border-b border-ink/20"><td colSpan={owner ? 7 : 6} className="py-1 text-center font-bold">OR</td></tr>}
                      {q.parts.map((p, pi) => (
                        <tr key={pi} className="border-b border-ink/15 align-top">
                          <td className="py-2 text-center font-bold">{pi === 0 ? `Q.${String(number).padStart(2, "0")}` : ""}</td>
                          <td className="py-2 text-center">{"abcdef"[pi]}</td>
                          <td className="py-2 pr-3 leading-relaxed">{p.text}
                            {owner && showScheme && p.scheme.length > 0 && <ul className="mt-1.5 space-y-0.5 border-l-2 border-brand/40 pl-3 font-sans text-xs text-mute">{p.scheme.map((s) => <li key={s}>{s}</li>)}</ul>}
                            {pi === q.parts.length - 1 && total !== paper.marks_per_question && <p className="mt-1 flex items-center gap-1 font-sans text-xs font-semibold text-rose-600"><AlertTriangle className="h-3.5 w-3.5" />Parts add up to {total}, expected {paper.marks_per_question}</p>}
                          </td>
                          <td className="py-2 text-center">{p.marks}</td><td className="py-2 text-center">{p.bloom}</td><td className="py-2 text-center">{m.co}</td>
                          {owner && <td className="py-1 text-center"><button className="btn-ghost btn-sm px-1.5" aria-label="Edit question" onClick={() => setEdit({ m: mi, q: qi, p: pi, text: p.text, marks: p.marks, bloom: p.bloom, scheme: p.scheme.join("\n") })}><Pencil className="h-3.5 w-3.5" /></button></td>}
                        </tr>
                      ))}
                    </ModuleRows>
                  );
                })}
                {m.questions.length === 0 && <tr><td colSpan={owner ? 7 : 6} className="py-4 text-center font-sans text-xs text-mute">Not generated yet.</td></tr>}
              </ModuleRows>
            ))}
          </tbody>
        </table>
        <p className="mt-5 text-center font-bold tracking-[0.4em]">*****</p>
      </article>

      <Modal open={!!edit} onClose={() => setEdit(null)} title="Edit sub-question" wide>
        {edit && (
          <form onSubmit={savePart} className="space-y-4">
            <div><label className="label" htmlFor="e-text">Question</label><textarea id="e-text" className="input min-h-[110px]" required minLength={3} value={edit.text} onChange={(e) => setEdit({ ...edit, text: e.target.value })} /></div>
            <div className="grid grid-cols-2 gap-3">
              <div><label className="label" htmlFor="e-marks">Marks</label><input id="e-marks" type="number" min="1" max="50" className="input" value={edit.marks} onChange={(e) => setEdit({ ...edit, marks: e.target.value })} /></div>
              <div><label className="label" htmlFor="e-bloom">Bloom level</label><select id="e-bloom" className="input" value={edit.bloom} onChange={(e) => setEdit({ ...edit, bloom: e.target.value })}>{["L1 Remember", "L2 Understand", "L3 Apply", "L4 Analyze", "L5 Evaluate", "L6 Create"].map((b) => <option key={b} value={b.slice(0, 2)}>{b}</option>)}</select></div>
            </div>
            <div><label className="label" htmlFor="e-scheme">Scheme of valuation (one line per step)</label><textarea id="e-scheme" className="input min-h-[90px]" value={edit.scheme} onChange={(e) => setEdit({ ...edit, scheme: e.target.value })} /></div>
            <div className="flex justify-end gap-2"><button type="button" className="btn-ghost" onClick={() => setEdit(null)}><X className="h-4 w-4" />Cancel</button><button className="btn-primary" disabled={busy === "save"}>{busy === "save" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}Save</button></div>
          </form>
        )}
      </Modal>
    </div>
  );
}
const ModuleRows = ({ children }) => children;
