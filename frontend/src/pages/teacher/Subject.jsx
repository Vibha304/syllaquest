import { useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Bar as RBar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import {
  AlertTriangle, ArrowLeft, Check, CheckCheck, ChevronDown, Copy, Download, FileSpreadsheet, FileText, Braces, Loader2, Pencil, Plus,
  Search, Sparkles, Trash2, Users, X,
} from "lucide-react";
import { api } from "../../api";
import { useApp, useLoad } from "../../store";
import TopicGraph from "../../components/TopicGraph";
import ExamPapers from "../../components/ExamPapers";
import { DIFF_OPTIONS, generateForTopics, TYPE_OPTIONS } from "../../components/CreateCourse";
import { Bar, ChipSelect, DiffPill, Empty, ErrorBox, Modal, Spinner, Stat, Toggle, TYPE_LABEL, cx, pct } from "../../components/ui";

const TABS = [["overview", "Overview"], ["topics", "Topics"], ["generate", "Generate"], ["bank", "Question bank"], ["exam", "Exam papers"], ["coverage", "Coverage"], ["class", "Class analytics"]];
const BLOOMS = ["remember", "understand", "apply", "analyze", "evaluate", "create"];

export default function Subject() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { toast } = useApp();
  const { data: course, error, loading, reload } = useLoad(`/api/courses/${id}`);
  const [tab, setTab] = useState("overview");
  if (loading && !course) return <Spinner />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;

  const publish = async (published) => {
    if (published && course.question_count === 0) return toast("Approve at least one question before publishing.", "error");
    await api.patch(`/api/courses/${id}`, { published });
    toast(published ? "Published. Students can join with the class code." : "Unpublished. New students can no longer join.", "success");
    reload();
  };
  const copy = () => navigator.clipboard?.writeText(course.join_code).then(() => toast("Class code copied", "success"));
  const remove = async () => {
    if (!confirm(`Delete "${course.name}" with all its questions and student progress? This cannot be undone.`)) return;
    await api.del(`/api/courses/${id}`);
    navigate("/");
  };

  return (
    <div className="space-y-5">
      <Link to="/" className="inline-flex items-center gap-1.5 text-sm font-semibold text-mute hover:text-ink"><ArrowLeft className="h-4 w-4" />Subjects</Link>
      <div className="card flex flex-wrap items-center justify-between gap-4 p-5">
        <div className="min-w-0">
          <p className="font-mono text-xs font-semibold text-brand">{course.code || "SUBJECT"}</p>
          <h1 className="h-page">{course.name}</h1>
          <p className="sub mt-1">{course.topic_count} topics · {course.question_count} approved · {course.draft_count} drafts · {course.student_count} students</p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <button onClick={copy} className="flex items-center gap-2 rounded-xl border border-dashed border-line px-3 py-2 text-left hover:border-brand" title="Copy class code">
            <span><span className="block text-[10px] font-semibold uppercase tracking-wider text-mute">Class code</span><span className="font-mono text-base font-bold tracking-widest">{course.join_code}</span></span>
            <Copy className="h-4 w-4 text-mute" />
          </button>
          <Toggle checked={course.published} onChange={publish} label={course.published ? "Published" : "Private"} />
        </div>
      </div>

      <div className="-mx-4 overflow-x-auto px-4 sm:mx-0 sm:px-0">
        <div role="tablist" className="inline-flex gap-1 rounded-2xl bg-soft p-1">
          {TABS.map(([k, l]) => (
            <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)} className={cx("whitespace-nowrap rounded-xl px-3.5 py-2 text-sm font-semibold transition", tab === k ? "bg-card text-ink shadow" : "text-mute hover:text-ink")}>
              {l}{k === "bank" && course.draft_count > 0 && <span className="ml-1.5 rounded-full bg-amber-500 px-1.5 py-0.5 text-[10px] font-bold text-white">{course.draft_count}</span>}
            </button>
          ))}
        </div>
      </div>

      {tab === "overview" && <Overview course={course} setTab={setTab} onDelete={remove} />}
      {tab === "topics" && <Topics course={course} reload={reload} />}
      {tab === "generate" && <Generate course={course} reload={reload} setTab={setTab} />}
      {tab === "bank" && <Bank course={course} reloadCourse={reload} setTab={setTab} />}
      {tab === "exam" && <ExamPapers course={course} />}
      {tab === "coverage" && <Coverage course={course} setTab={setTab} />}
      {tab === "class" && <ClassAnalytics course={course} />}
    </div>
  );
}

/* ----------------------------------------------------------------- overview */
function Overview({ course, setTab, onDelete }) {
  const { toast } = useApp();
  const [answers, setAnswers] = useState(true);
  const [busy, setBusy] = useState("");
  const exportAs = async (format) => {
    setBusy(format);
    try { await api.download(`/api/courses/${course.id}/export?format=${format}&answers=${answers}`, `question_bank.${format}`); }
    catch (e) { toast(e.message, "error"); }
    setBusy("");
  };
  const steps = [
    { done: course.topic_count > 0, label: "Add topics from a syllabus", tab: "topics" },
    { done: course.question_count + course.draft_count > 0, label: "Generate a question bank", tab: "generate" },
    { done: course.question_count > 0 && course.draft_count === 0, label: "Review and approve drafts", tab: "bank" },
    { done: course.published, label: "Publish and share the class code" },
  ];
  return (
    <div className="grid gap-4 lg:grid-cols-5">
      <section className="card p-5 lg:col-span-3">
        <h2 className="text-base font-bold">Syllabus-to-question map</h2>
        <p className="text-xs text-mute">Every question is stored against the topic it was generated from. The number is the question count per topic.</p>
        {course.topics.length ? <TopicGraph course={course} showMastery={false} /> : <p className="sub py-10 text-center">No topics yet. Add them in the Topics tab.</p>}
      </section>
      <div className="space-y-4 lg:col-span-2">
        <section className="card p-5">
          <h2 className="text-base font-bold">Setup checklist</h2>
          <ul className="mt-3 space-y-2">
            {steps.map((s) => (
              <li key={s.label} className="flex items-center gap-3 text-sm">
                <span className={cx("flex h-5 w-5 shrink-0 items-center justify-center rounded-full", s.done ? "bg-emerald-500 text-white" : "border-2 border-line")}>{s.done && <Check className="h-3 w-3" />}</span>
                <span className={cx("flex-1", s.done && "text-mute line-through")}>{s.label}</span>
                {!s.done && s.tab && <button className="text-xs font-semibold text-brand hover:underline" onClick={() => setTab(s.tab)}>Open</button>}
              </li>
            ))}
          </ul>
        </section>
        <section className="card p-5">
          <h2 className="text-base font-bold">Export question bank</h2>
          <p className="text-xs text-mute">Approved questions, grouped by topic, tagged with difficulty and Bloom level.</p>
          <div className="mt-3"><Toggle checked={answers} onChange={setAnswers} label="Include answer key in DOCX" /></div>
          <div className="mt-4 grid grid-cols-3 gap-2">
            {[["docx", FileText, "Word"], ["csv", FileSpreadsheet, "CSV"], ["json", Braces, "JSON"]].map(([f, Icon, label]) => (
              <button key={f} className="btn-soft flex-col gap-1 py-3" disabled={!!busy || !course.question_count} onClick={() => exportAs(f)}>
                {busy === f ? <Loader2 className="h-5 w-5 animate-spin" /> : <Icon className="h-5 w-5" />}<span className="text-xs">{label}</span>
              </button>
            ))}
          </div>
        </section>
        <button className="btn-danger w-full" onClick={onDelete}><Trash2 className="h-4 w-4" />Delete subject</button>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------- topics */
function Topics({ course, reload }) {
  const { toast } = useApp();
  const [edit, setEdit] = useState(null);
  const [open, setOpen] = useState(null);
  const [busy, setBusy] = useState(false);
  const save = async (e) => {
    e.preventDefault();
    setBusy(true);
    const body = { name: edit.name, content: edit.content, keywords: edit.keywords.split(",").map((k) => k.trim()).filter(Boolean) };
    try {
      if (edit.id) await api.patch(`/api/topics/${edit.id}`, body);
      else await api.post(`/api/courses/${course.id}/topics`, body);
      setEdit(null);
      reload();
    } catch (err) { toast(err.message, "error"); }
    setBusy(false);
  };
  const remove = async (t) => {
    if (!confirm(`Delete topic "${t.name}" and its ${t.counts.total + t.counts.draft} questions?`)) return;
    await api.del(`/api/topics/${t.id}`);
    reload();
  };
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="sub">{course.source_name ? `Extracted from ${course.source_name} (${course.extraction_method === "lda" ? "LDA topic modelling" : "document headings"}). ` : ""}Edit names, key terms and source text before generating.</p>
        <button className="btn-soft" onClick={() => setEdit({ name: "", content: "", keywords: "" })}><Plus className="h-4 w-4" />Add topic</button>
      </div>
      {course.topics.length === 0 && <Empty title="No topics yet">Add a topic with its syllabus text or notes; questions are generated from that text.</Empty>}
      {course.topics.map((t, i) => (
        <div key={t.id} className="card p-4">
          <div className="flex flex-wrap items-start gap-3">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-brand/10 text-sm font-bold text-brand">{i + 1}</span>
            <div className="min-w-0 flex-1">
              <h3 className="font-sans text-base font-bold">{t.name}</h3>
              <p className="text-xs text-mute">{t.words} words of source text · {t.counts.total} approved · {t.counts.draft} drafts</p>
              <div className="mt-2 flex flex-wrap gap-1.5">{t.keywords.slice(0, 12).map((k) => <span key={k} className="chip py-0.5">{k}</span>)}</div>
            </div>
            <div className="flex gap-1">
              <button className="btn-ghost btn-sm" onClick={() => setOpen(open === t.id ? null : t.id)} aria-expanded={open === t.id}>Source<ChevronDown className={cx("h-3.5 w-3.5 transition", open === t.id && "rotate-180")} /></button>
              <button className="btn-ghost btn-sm" aria-label="Edit topic" onClick={() => setEdit({ id: t.id, name: t.name, content: t.content || "", keywords: t.keywords.join(", ") })}><Pencil className="h-3.5 w-3.5" /></button>
              <button className="btn-ghost btn-sm hover:text-rose-500" aria-label="Delete topic" onClick={() => remove(t)}><Trash2 className="h-3.5 w-3.5" /></button>
            </div>
          </div>
          {open === t.id && <p className="mt-3 max-h-56 overflow-y-auto whitespace-pre-line rounded-xl bg-soft/70 p-3 text-xs leading-relaxed text-mute">{t.content || "No source text."}</p>}
        </div>
      ))}
      <Modal open={!!edit} onClose={() => setEdit(null)} title={edit?.id ? "Edit topic" : "Add topic"} wide>
        {edit && (
          <form onSubmit={save} className="space-y-4">
            <div><label className="label" htmlFor="t-name">Topic name</label><input id="t-name" className="input" required minLength={2} value={edit.name} onChange={(e) => setEdit({ ...edit, name: e.target.value })} /></div>
            <div><label className="label" htmlFor="t-kw">Key terms (comma separated)</label><input id="t-kw" className="input" placeholder="Leave blank to detect automatically" value={edit.keywords} onChange={(e) => setEdit({ ...edit, keywords: e.target.value })} /></div>
            <div><label className="label" htmlFor="t-content">Source text (syllabus lines or notes)</label><textarea id="t-content" className="input min-h-[180px]" value={edit.content} onChange={(e) => setEdit({ ...edit, content: e.target.value })} /></div>
            <div className="flex justify-end gap-2"><button type="button" className="btn-ghost" onClick={() => setEdit(null)}>Cancel</button><button className="btn-primary" disabled={busy}>{busy ? <Loader2 className="h-4 w-4 animate-spin" /> : "Save topic"}</button></div>
          </form>
        )}
      </Modal>
    </div>
  );
}

/* ----------------------------------------------------------------- generate */
function Generate({ course, reload, setTab }) {
  const { meta } = useApp();
  const [picked, setPicked] = useState(course.topics.map((t) => t.id));
  const [opts, setOpts] = useState({ count: 6, types: ["mcq", "tf", "short"], difficulties: ["easy", "medium", "hard"] });
  const [progress, setProgress] = useState(null);
  const [result, setResult] = useState(null);
  const run = async () => {
    setResult(null);
    const topics = course.topics.filter((t) => picked.includes(t.id));
    const r = await generateForTopics(course.id, topics, opts, setProgress);
    setProgress(null);
    setResult(r);
    reload();
  };
  if (!course.topics.length) return <Empty title="Add topics first" action={<button className="btn-primary" onClick={() => setTab("topics")}>Go to topics</button>}>Questions are generated per topic so each one stays mapped to the syllabus.</Empty>;
  return (
    <div className="grid gap-4 lg:grid-cols-5">
      <section className="card p-5 lg:col-span-3">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-bold">1. Choose topics</h2>
          <button className="text-xs font-semibold text-brand hover:underline" onClick={() => setPicked(picked.length === course.topics.length ? [] : course.topics.map((t) => t.id))}>{picked.length === course.topics.length ? "Clear all" : "Select all"}</button>
        </div>
        <ul className="mt-3 space-y-2">
          {course.topics.map((t) => {
            const on = picked.includes(t.id);
            return (
              <li key={t.id}>
                <label className={cx("flex cursor-pointer items-center gap-3 rounded-xl border p-3 transition", on ? "border-brand bg-brand/5" : "border-line hover:border-brand/50")}>
                  <input type="checkbox" className="h-4 w-4 accent-[rgb(var(--brand))]" checked={on} onChange={() => setPicked(on ? picked.filter((x) => x !== t.id) : [...picked, t.id])} />
                  <span className="min-w-0 flex-1"><span className="block truncate text-sm font-semibold">{t.name}</span><span className="text-xs text-mute">{t.counts.total + t.counts.draft} existing · {t.words} words of source</span></span>
                  {t.words < 40 && <span className="chip" title="Short source text: an AI key gives much better results for syllabus-only topics">thin source</span>}
                </label>
              </li>
            );
          })}
        </ul>
      </section>
      <section className="card h-fit space-y-5 p-5 lg:col-span-2">
        <h2 className="text-base font-bold">2. Configure</h2>
        <div><span className="label">Questions per topic: {opts.count}</span><input type="range" min="1" max="15" value={opts.count} onChange={(e) => setOpts({ ...opts, count: +e.target.value })} className="w-full accent-[rgb(var(--brand))]" /></div>
        <div><span className="label">Question types</span><ChipSelect options={TYPE_OPTIONS} value={opts.types} onChange={(v) => v.length && setOpts({ ...opts, types: v })} /></div>
        <div><span className="label">Difficulty and Bloom level</span><ChipSelect options={DIFF_OPTIONS} value={opts.difficulties} onChange={(v) => v.length && setOpts({ ...opts, difficulties: v })} /></div>
        <p className="flex items-start gap-2 rounded-xl bg-soft px-3 py-2.5 text-xs text-mute">
          <Sparkles className={cx("mt-0.5 h-4 w-4 shrink-0", meta.ai_enabled ? "text-emerald-500" : "text-amber-500")} />
          {meta.ai_enabled ? `Using ${meta.llm_provider} · ${meta.llm_model}` : "Offline rule-based generator (no AI key configured). Set GEMINI_API_KEY or GROQ_API_KEY for LLM-written questions."}
        </p>
        {progress ? (
          <div><div className="mb-2 flex items-center gap-2 text-sm font-semibold"><Loader2 className="h-4 w-4 animate-spin text-brand" /><span className="truncate">{progress.topic || "Finishing…"}</span></div><Bar value={progress.index / progress.total} className="h-2.5" /><p className="mt-1.5 text-xs text-mute">{progress.created} questions created</p></div>
        ) : (
          <button className="btn-primary w-full" disabled={!picked.length} onClick={run}><Sparkles className="h-4 w-4" />Generate {picked.length * opts.count} questions</button>
        )}
        {result && (
          <div className="rounded-xl border border-emerald-500/40 bg-emerald-500/5 p-3 text-sm">
            <p className="font-semibold">{result.created} draft questions created</p>
            {result.notes.slice(0, 3).map((n) => <p key={n} className="mt-1 text-xs text-mute">{n}</p>)}
            <button className="btn-soft btn-sm mt-3" onClick={() => setTab("bank")}>Review drafts</button>
          </div>
        )}
      </section>
    </div>
  );
}

/* --------------------------------------------------------------------- bank */
const blank = (topicId) => ({ topic_id: topicId, type: "mcq", difficulty: "medium", bloom: "understand", text: "", options: ["", "", "", ""], answer: "", explanation: "", status: "approved" });

function Bank({ course, reloadCourse, setTab }) {
  const { toast } = useApp();
  const { data, error, loading, reload } = useLoad(`/api/courses/${course.id}/questions`);
  const [f, setF] = useState({ q: "", topic: "", type: "", difficulty: "", status: "" });
  const [sel, setSel] = useState(new Set());
  const [edit, setEdit] = useState(null);
  const [busy, setBusy] = useState(false);
  const [shown, setShown] = useState(20);
  const rows = useMemo(() => (data || []).filter((q) =>
    (!f.q || q.text.toLowerCase().includes(f.q.toLowerCase())) && (!f.topic || q.topic_id === +f.topic) &&
    (!f.type || q.type === f.type) && (!f.difficulty || q.difficulty === f.difficulty) && (!f.status || q.status === f.status)), [data, f]);
  if (loading && !data) return <Spinner />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;

  const refresh = () => { setSel(new Set()); reload(); reloadCourse(); };
  const bulk = async (action, ids = [...sel]) => {
    if (!ids.length) return;
    if (action === "delete" && !confirm(`Delete ${ids.length} question${ids.length > 1 ? "s" : ""}?`)) return;
    await api.post(`/api/courses/${course.id}/questions/bulk`, { ids, action });
    toast(`${ids.length} question${ids.length > 1 ? "s" : ""} ${action === "approve" ? "approved" : action === "delete" ? "deleted" : "moved to drafts"}`, "success");
    refresh();
  };
  const save = async (e) => {
    e.preventDefault();
    setBusy(true);
    const body = { ...edit, options: edit.type === "mcq" ? edit.options.filter((o) => o.trim()) : [] };
    try {
      if (edit.id) await api.put(`/api/questions/${edit.id}`, body);
      else await api.post(`/api/courses/${course.id}/questions`, body);
      setEdit(null);
      refresh();
    } catch (err) { toast(err.message, "error"); }
    setBusy(false);
  };
  const toggle = (id) => { const n = new Set(sel); n.has(id) ? n.delete(id) : n.add(id); setSel(n); };
  const drafts = data.filter((q) => q.status === "draft");
  const select = (key, label, options) => (
    <select aria-label={label} className="input w-auto py-2 text-xs" value={f[key]} onChange={(e) => setF({ ...f, [key]: e.target.value })}>
      <option value="">{label}</option>{options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
    </select>
  );

  if (!data.length) return <Empty icon={Sparkles} title="The question bank is empty" action={<div className="flex gap-2"><button className="btn-primary" onClick={() => setTab("generate")}>Generate questions</button>{course.topics.length > 0 && <button className="btn-soft" onClick={() => setEdit(blank(course.topics[0].id))}>Write one manually</button>}</div>}>Generate questions per topic, then review them here before students see them.</Empty>;

  return (
    <div className="space-y-3">
      <div className="card flex flex-wrap items-center gap-2 p-3">
        <div className="relative min-w-[160px] flex-1"><Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-mute" /><input aria-label="Search questions" className="input py-2 pl-9 text-xs" placeholder="Search questions" value={f.q} onChange={(e) => setF({ ...f, q: e.target.value })} /></div>
        {select("topic", "All topics", course.topics.map((t) => [t.id, t.name]))}
        {select("type", "All types", Object.entries(TYPE_LABEL))}
        {select("difficulty", "All levels", [["easy", "Easy"], ["medium", "Medium"], ["hard", "Hard"]])}
        {select("status", "Any status", [["approved", "Approved"], ["draft", "Draft"]])}
        <button className="btn-soft btn-sm" onClick={() => setEdit(blank(course.topics[0]?.id))} disabled={!course.topics.length}><Plus className="h-3.5 w-3.5" />Add</button>
      </div>

      <div className="flex flex-wrap items-center gap-2 text-sm">
        <label className="flex items-center gap-2 font-medium"><input type="checkbox" className="h-4 w-4 accent-[rgb(var(--brand))]" checked={rows.length > 0 && rows.every((q) => sel.has(q.id))} onChange={(e) => setSel(e.target.checked ? new Set(rows.map((q) => q.id)) : new Set())} />{sel.size ? `${sel.size} selected` : `${rows.length} of ${data.length} questions`}</label>
        <span className="flex-1" />
        {sel.size > 0 ? (
          <>
            <button className="btn-soft btn-sm" onClick={() => bulk("approve")}><Check className="h-3.5 w-3.5" />Approve</button>
            <button className="btn-soft btn-sm" onClick={() => bulk("draft")}>Move to drafts</button>
            <button className="btn-danger btn-sm" onClick={() => bulk("delete")}><Trash2 className="h-3.5 w-3.5" />Delete</button>
          </>
        ) : drafts.length > 0 && <button className="btn-primary btn-sm" onClick={() => bulk("approve", drafts.map((q) => q.id))}><CheckCheck className="h-3.5 w-3.5" />Approve all {drafts.length} drafts</button>}
      </div>

      <ul className="space-y-2.5">
        {rows.slice(0, shown).map((q) => (
          <li key={q.id} className={cx("card p-4", sel.has(q.id) && "border-brand")}>
            <div className="flex gap-3">
              <input type="checkbox" aria-label="Select question" className="mt-1 h-4 w-4 shrink-0 accent-[rgb(var(--brand))]" checked={sel.has(q.id)} onChange={() => toggle(q.id)} />
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className="chip chip-on py-0.5">{q.topic}</span><DiffPill value={q.difficulty} /><span className="chip py-0.5 capitalize">{q.bloom}</span><span className="chip py-0.5">{TYPE_LABEL[q.type]}</span>
                  <span className={cx("rounded-full px-2 py-0.5 text-[11px] font-bold uppercase tracking-wide", q.status === "draft" ? "bg-amber-500/15 text-amber-700 dark:text-amber-300" : "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300")}>{q.status}</span>
                  <span className="ml-auto text-[11px] text-mute">by {q.origin}</span>
                </div>
                <p className="mt-2 text-sm font-semibold leading-relaxed">{q.text}</p>
                {q.type === "mcq" ? (
                  <ol className="mt-2 grid gap-1 text-sm sm:grid-cols-2">
                    {q.options.map((o, i) => <li key={o} className={cx("flex gap-2 rounded-lg px-2 py-1", o === q.answer ? "bg-emerald-500/10 font-semibold text-emerald-700 dark:text-emerald-300" : "text-mute")}><span>{"ABCD"[i]}.</span><span>{o}</span></li>)}
                  </ol>
                ) : <p className="mt-2 text-sm"><span className="text-mute">Answer: </span><b className="text-emerald-700 dark:text-emerald-300">{q.answer}</b></p>}
                {q.explanation && <p className="mt-2 text-xs text-mute">{q.explanation}</p>}
              </div>
              <div className="flex shrink-0 flex-col gap-1">
                {q.status === "draft" && <button className="btn-ghost btn-sm text-emerald-600" aria-label="Approve" title="Approve" onClick={() => bulk("approve", [q.id])}><Check className="h-4 w-4" /></button>}
                <button className="btn-ghost btn-sm" aria-label="Edit" title="Edit" onClick={() => setEdit({ ...q, options: q.type === "mcq" ? [...q.options, "", "", "", ""].slice(0, Math.max(4, q.options.length)) : ["", "", "", ""] })}><Pencil className="h-4 w-4" /></button>
                <button className="btn-ghost btn-sm hover:text-rose-500" aria-label="Delete" title="Delete" onClick={() => bulk("delete", [q.id])}><Trash2 className="h-4 w-4" /></button>
              </div>
            </div>
          </li>
        ))}
        {rows.length === 0 && <li className="sub py-8 text-center">No questions match these filters.</li>}
      </ul>
      {rows.length > shown && <div className="text-center"><button className="btn-soft" onClick={() => setShown(shown + 20)}>Show 20 more ({rows.length - shown} remaining)</button></div>}

      <Modal open={!!edit} onClose={() => setEdit(null)} title={edit?.id ? "Edit question" : "Add question"} wide>
        {edit && (
          <form onSubmit={save} className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-4">
              <div className="sm:col-span-2"><label className="label" htmlFor="q-topic">Topic</label><select id="q-topic" className="input" value={edit.topic_id} onChange={(e) => setEdit({ ...edit, topic_id: +e.target.value })}>{course.topics.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}</select></div>
              <div><label className="label" htmlFor="q-type">Type</label><select id="q-type" className="input" value={edit.type} onChange={(e) => setEdit({ ...edit, type: e.target.value, answer: e.target.value === "tf" ? "True" : "" })}>{Object.entries(TYPE_LABEL).map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></div>
              <div><label className="label" htmlFor="q-diff">Difficulty</label><select id="q-diff" className="input capitalize" value={edit.difficulty} onChange={(e) => setEdit({ ...edit, difficulty: e.target.value })}>{["easy", "medium", "hard"].map((d) => <option key={d}>{d}</option>)}</select></div>
            </div>
            <div><label className="label" htmlFor="q-text">Question</label><textarea id="q-text" className="input min-h-[80px]" required minLength={8} value={edit.text} onChange={(e) => setEdit({ ...edit, text: e.target.value })} /></div>
            {edit.type === "mcq" && (
              <fieldset><legend className="label">Options (select the correct one)</legend>
                <div className="space-y-2">{edit.options.map((o, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <input type="radio" name="correct" aria-label={`Option ${"ABCD"[i]} is correct`} className="h-4 w-4 accent-emerald-500" checked={!!o && o === edit.answer} onChange={() => setEdit({ ...edit, answer: o })} disabled={!o.trim()} />
                    <input className="input" placeholder={`Option ${"ABCD"[i] || i + 1}`} value={o} onChange={(e) => { const options = [...edit.options]; options[i] = e.target.value; setEdit({ ...edit, options, answer: edit.answer === o ? e.target.value : edit.answer }); }} />
                  </div>))}</div>
              </fieldset>
            )}
            {edit.type === "tf" && <div><span className="label">Correct answer</span><ChipSelect multi={false} value={edit.answer} onChange={(v) => setEdit({ ...edit, answer: v })} options={[{ value: "True", label: "True" }, { value: "False", label: "False" }]} /></div>}
            {edit.type === "short" && <div><label className="label" htmlFor="q-ans">Model answer</label><textarea id="q-ans" className="input" required value={edit.answer} onChange={(e) => setEdit({ ...edit, answer: e.target.value })} /></div>}
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="sm:col-span-2"><label className="label" htmlFor="q-exp">Explanation</label><input id="q-exp" className="input" value={edit.explanation} onChange={(e) => setEdit({ ...edit, explanation: e.target.value })} /></div>
              <div><label className="label" htmlFor="q-bloom">Bloom level</label><select id="q-bloom" className="input capitalize" value={edit.bloom} onChange={(e) => setEdit({ ...edit, bloom: e.target.value })}>{BLOOMS.map((b) => <option key={b}>{b}</option>)}</select></div>
            </div>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <Toggle checked={edit.status === "approved"} onChange={(v) => setEdit({ ...edit, status: v ? "approved" : "draft" })} label="Approved (visible to students)" />
              <div className="flex gap-2"><button type="button" className="btn-ghost" onClick={() => setEdit(null)}>Cancel</button><button className="btn-primary" disabled={busy || !edit.answer}>{busy ? <Loader2 className="h-4 w-4 animate-spin" /> : "Save question"}</button></div>
            </div>
          </form>
        )}
      </Modal>
    </div>
  );
}

/* ----------------------------------------------------------------- coverage */
function Coverage({ course, setTab }) {
  const { data, error, loading, reload } = useLoad(`/api/courses/${course.id}/coverage`);
  if (loading) return <Spinner />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  const max = Math.max(1, ...data.topics.flatMap((t) => Object.values(t.difficulty)));
  const cell = (n) => (
    <td className="px-1.5 py-1.5 text-center">
      <div className={cx("mx-auto flex h-9 min-w-[44px] items-center justify-center rounded-lg text-sm font-bold", n === 0 && "border border-dashed border-rose-400/60 text-rose-500")}
        style={n ? { background: `rgb(var(--brand) / ${0.12 + 0.6 * (n / max)})`, color: n / max > 0.55 ? "#fff" : "rgb(var(--ink))" } : undefined}>{n}</div>
    </td>
  );
  return (
    <div className="space-y-4">
      {data.uncovered.length > 0 && (
        <div className="card flex flex-wrap items-center gap-3 border-amber-500/50 p-4 text-sm">
          <AlertTriangle className="h-5 w-5 shrink-0 text-amber-500" />
          <span className="flex-1"><b>{data.uncovered.length} topic{data.uncovered.length > 1 ? "s have" : " has"} no questions:</b> {data.uncovered.join(", ")}</span>
          <button className="btn-soft btn-sm" onClick={() => setTab("generate")}>Generate</button>
        </div>
      )}
      <section className="card overflow-x-auto p-5">
        <h2 className="text-base font-bold">Syllabus coverage matrix</h2>
        <p className="text-xs text-mute">Questions per topic by difficulty, Bloom level and type. Useful as course-outcome coverage evidence.</p>
        <table className="mt-4 w-full min-w-[720px] border-separate border-spacing-0">
          <thead>
            <tr><th className="th" rowSpan={2}>Topic</th><th className="th text-center" colSpan={3}>Difficulty</th><th className="th text-center" colSpan={4}>Bloom level</th><th className="th text-center" colSpan={3}>Type</th><th className="th text-center" rowSpan={2}>Total</th></tr>
            <tr>{["Easy", "Med", "Hard", "Rem", "Und", "App", "Ana", "MCQ", "T/F", "Short"].map((h) => <th key={h} className="th px-1.5 text-center">{h}</th>)}</tr>
          </thead>
          <tbody>
            {data.topics.map((t) => (
              <tr key={t.id}>
                <td className="td max-w-[220px] border-t border-line font-semibold">{t.name}<div className="text-xs font-normal text-mute">{t.approved} approved</div></td>
                {["easy", "medium", "hard"].map((d) => <FragmentCell key={d}>{cell(t.difficulty[d])}</FragmentCell>)}
                {["remember", "understand", "apply", "analyze"].map((b) => <FragmentCell key={b}>{cell(t.bloom[b])}</FragmentCell>)}
                {["mcq", "tf", "short"].map((k) => <FragmentCell key={k}>{cell(t.type[k])}</FragmentCell>)}
                <td className="td border-t border-line text-center font-display text-base font-bold">{t.total}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
const FragmentCell = ({ children }) => children;

/* ---------------------------------------------------------- class analytics */
function ClassAnalytics({ course }) {
  const { data, error, loading, reload } = useLoad(`/api/courses/${course.id}/class-analytics`);
  if (loading) return <Spinner />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  if (!data.student_count) return <Empty icon={Users} title="No students yet">Publish the subject and share the class code <b className="font-mono">{course.join_code}</b>. Topic-wise mastery for every student will appear here.</Empty>;
  const tone = (p) => (p === null ? "rgb(var(--soft))" : p < 0.5 ? "#f43f5e" : p < 0.85 ? "#f59e0b" : "#10b981");
  const chart = data.topics.map((t) => ({ name: t.name, mastery: t.avg_mastery ?? 0, raw: t.avg_mastery }));
  const accuracy = data.total_attempts ? data.students.reduce((a, s) => a + s.accuracy * s.answered, 0) / data.total_attempts : 0;
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat icon={Users} label="Students" value={data.student_count} />
        <Stat icon={CheckCheck} label="Answers logged" value={data.total_attempts} tone="text-emerald-600 bg-emerald-500/10" />
        <Stat icon={Check} label="Class accuracy" value={pct(accuracy)} tone="text-sky-600 bg-sky-500/10" />
        <Stat icon={AlertTriangle} label="Weak topic flags" value={data.topics.reduce((a, t) => a + t.weak_students, 0)} tone="text-rose-600 bg-rose-500/10" />
      </div>
      <div className="grid items-start gap-4 lg:grid-cols-5">
        <section className="card p-5 lg:col-span-3">
          <h2 className="text-base font-bold">Average mastery by topic</h2>
          <p className="text-xs text-mute">Red below 50%, amber below 85%, green mastered</p>
          <div className="mt-3" style={{ height: Math.max(180, chart.length * 44) }}>
            <ResponsiveContainer>
              <BarChart data={chart} layout="vertical" margin={{ left: 8, right: 24 }}>
                <CartesianGrid horizontal={false} strokeDasharray="3 3" />
                <XAxis type="number" domain={[0, 1]} tickFormatter={pct} tickLine={false} axisLine={false} ticks={[0, 0.25, 0.5, 0.75, 1]} />
                <YAxis type="category" dataKey="name" width={150} tickLine={false} axisLine={false} tickFormatter={(s) => (s.length > 22 ? s.slice(0, 21) + "…" : s)} />
                <Tooltip cursor={{ fill: "rgb(var(--soft))" }} content={({ active, payload }) => active && payload?.length ? <div className="card px-3 py-2 text-xs"><b>{payload[0].payload.name}</b><div className="text-mute">{payload[0].payload.raw === null ? "Not practised yet" : `Average mastery ${pct(payload[0].value)}`}</div></div> : null} />
                <RBar dataKey="mastery" radius={[0, 6, 6, 0]} maxBarSize={22} isAnimationActive={false}>{chart.map((c) => <Cell key={c.name} fill={tone(c.raw)} />)}</RBar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>
        <section className="card p-5 lg:col-span-2">
          <h2 className="text-base font-bold">Questions students miss most</h2>
          {data.hardest_questions.length === 0 ? <p className="sub mt-4">Not enough attempts yet.</p> : (
            <ul className="mt-3 space-y-3">
              {data.hardest_questions.map((q) => (
                <li key={q.id} className="rounded-xl border border-line p-3">
                  <p className="line-clamp-3 text-sm font-medium">{q.text}</p>
                  <div className="mt-2 flex flex-wrap items-center gap-2 text-xs"><span className="chip py-0.5">{q.topic}</span><DiffPill value={q.difficulty} /><span className="ml-auto font-bold text-rose-600 dark:text-rose-300">{pct(q.accuracy)} correct · {q.attempts} tries</span></div>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
      <section className="card overflow-x-auto p-5">
        <h2 className="text-base font-bold">Student mastery heatmap</h2>
        <table className="mt-3 w-full min-w-[680px]">
          <thead><tr><th className="th">Student</th><th className="th text-right">XP</th><th className="th text-right">Accuracy</th>{data.topics.map((t, i) => <th key={t.id} className="th text-center" title={t.name}>T{i + 1}</th>)}<th className="th">Weak topics</th></tr></thead>
          <tbody>
            {data.students.map((s) => (
              <tr key={s.id} className="border-t border-line">
                <td className="td"><div className="font-semibold">{s.name}</div><div className="text-xs text-mute">{s.answered} answers</div></td>
                <td className="td text-right font-bold text-xp">{s.xp}</td>
                <td className="td text-right">{s.answered ? pct(s.accuracy) : "–"}</td>
                {data.topics.map((t) => { const p = s.topic_mastery[t.id]; return (
                  <td key={t.id} className="px-1 py-2 text-center"><div title={`${t.name}: ${p === null ? "not practised" : pct(p)}`} className="mx-auto flex h-8 w-11 items-center justify-center rounded-md text-[11px] font-bold" style={{ background: p === null ? "rgb(var(--soft))" : tone(p), color: p === null ? "rgb(var(--mute))" : "#fff" }}>{p === null ? "–" : Math.round(p * 100)}</div></td>
                ); })}
                <td className="td text-xs text-mute">{s.weak_topics.length ? s.weak_topics.join(", ") : "None"}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="mt-3 text-xs text-mute">{data.topics.map((t, i) => `T${i + 1}: ${t.name}`).join(" · ")}</p>
      </section>
    </div>
  );
}
