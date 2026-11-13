import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Crosshair, Loader2, LogOut, Play, Sparkles, Trash2, Trophy } from "lucide-react";
import { api } from "../api";
import { useApp, useLoad } from "../store";
import TopicGraph from "../components/TopicGraph";
import ExamPapers from "../components/ExamPapers";
import { generateForTopics, TYPE_OPTIONS } from "../components/CreateCourse";
import { Bar, ChipSelect, ErrorBox, Modal, Spinner, STATUS, StatusPill, cx, pct } from "../components/ui";

export default function Course() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { toast, user } = useApp();
  const { data: course, error, loading, reload } = useLoad(`/api/courses/${id}`);
  const board = useLoad(`/api/courses/${id}/leaderboard`);
  const [setup, setSetup] = useState(null); // quiz config modal
  const [starting, setStarting] = useState(false);
  const [gen, setGen] = useState(null);

  if (loading) return <Spinner />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  const weak = course.topics.filter((t) => t.mastery.status === "weak");
  const playable = course.question_count > 0;

  const openSetup = (topicIds = []) => setSetup({ topic_ids: topicIds, length: 10, types: ["mcq", "tf"], seconds_per_question: 45 });
  const start = async () => {
    setStarting(true);
    try {
      const r = await api.post("/api/quiz/start", { course_id: course.id, ...setup });
      navigate(`/quiz/${r.session_id}`);
    } catch (e) {
      toast(e.message, "error");
      setStarting(false);
    }
  };
  const moreQuestions = async () => {
    setGen({ index: 0, total: course.topics.length, topic: course.topics[0]?.name });
    const r = await generateForTopics(course.id, course.topics, { count: 5, types: ["mcq", "tf", "short"], difficulties: ["easy", "medium", "hard"] }, setGen);
    setGen(null);
    toast(r.created ? `${r.created} new questions added` : "No new questions could be generated", r.created ? "success" : "error");
    reload();
  };
  const remove = async () => {
    if (!confirm(course.is_owner ? "Delete this course and all its questions and progress?" : "Leave this class?")) return;
    await (course.is_owner ? api.del(`/api/courses/${course.id}`) : api.del(`/api/courses/${course.id}/enrollment`));
    navigate("/courses");
  };

  return (
    <div className="space-y-6">
      <Link to="/courses" className="inline-flex items-center gap-1.5 text-sm font-semibold text-mute hover:text-ink"><ArrowLeft className="h-4 w-4" />Courses</Link>
      <div className="card relative overflow-hidden p-6">
        <div className="pointer-events-none absolute -right-16 -top-16 h-56 w-56 rounded-full bg-brand/15 blur-3xl" />
        <div className="relative flex flex-wrap items-end justify-between gap-4">
          <div className="min-w-0">
            <p className="text-xs font-semibold uppercase tracking-widest text-brand">{course.code || (course.kind === "class" ? "Class" : "Personal course")}</p>
            <h1 className="h-page mt-1">{course.name}</h1>
            <p className="sub mt-1">{course.kind === "class" ? `Taught by ${course.owner_name}` : `From ${course.source_name || "your upload"}`} · {course.topic_count} topics · {course.question_count} questions</p>
            <div className="mt-4 flex max-w-sm items-center gap-3">
              <Bar value={course.mastery} className="h-2.5" /><span className="text-sm font-bold">{pct(course.mastery)}</span>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            {weak.length > 0 && <button className="btn-soft" onClick={() => openSetup(weak.map((t) => t.id))}><Crosshair className="h-4 w-4" />Fix {weak.length} weak topic{weak.length > 1 ? "s" : ""}</button>}
            <button className="btn-primary" disabled={!playable} onClick={() => openSetup([])}><Play className="h-4 w-4" />Start adaptive quiz</button>
          </div>
        </div>
      </div>

      {!playable && (
        <div className="card flex flex-wrap items-center justify-between gap-3 border-amber-500/40 p-4 text-sm">
          <span>{course.is_owner ? "This course has no questions yet." : "Your teacher has not published any questions for this class yet."}</span>
          {course.is_owner && course.topics.length > 0 && <button className="btn-primary btn-sm" onClick={moreQuestions} disabled={!!gen}><Sparkles className="h-3.5 w-3.5" />Generate questions</button>}
        </div>
      )}

      <div className="grid items-start gap-4 lg:grid-cols-5">
        <section className="card p-5 lg:col-span-3">
          <h2 className="text-base font-bold">Topics and mastery</h2>
          <p className="text-xs text-mute">Estimated with Bayesian Knowledge Tracing after every answer</p>
          <ul className="mt-4 space-y-2.5">
            {course.topics.map((t) => {
              const st = STATUS[t.mastery.status];
              return (
                <li key={t.id} className="rounded-xl border border-line p-3.5">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="min-w-0 flex-1">
                      <div className="text-sm font-semibold">{t.name}</div>
                      <div className="text-xs text-mute">{t.counts.total} questions · {t.mastery.attempts} attempts</div>
                    </div>
                    <StatusPill status={t.mastery.status} />
                    <button className="btn-soft btn-sm" disabled={!t.counts.total} onClick={() => openSetup([t.id])}>Practise</button>
                  </div>
                  <div className="mt-2.5 flex items-center gap-3">
                    <Bar value={t.mastery.p} tone={st.tone} className="h-1.5" />
                    <span className={cx("w-9 text-right text-xs font-bold", st.text)}>{pct(t.mastery.p)}</span>
                  </div>
                </li>
              );
            })}
          </ul>
        </section>

        <div className="space-y-4 lg:col-span-2">
          <section className="card p-5">
            <h2 className="text-base font-bold">Syllabus map</h2>
            <p className="text-xs text-mute">Each dot is a question linked to its topic</p>
            <TopicGraph course={course} onSelect={(t) => t.counts.total && openSetup([t.id])} />
          </section>
          <section className="card p-5">
            <h2 className="flex items-center gap-2 text-base font-bold"><Trophy className="h-4 w-4 text-xp" />Class leaderboard</h2>
            {board.data?.rows?.length ? (
              <ol className="mt-3 space-y-1.5">
                {board.data.rows.slice(0, 6).map((r) => (
                  <li key={r.user_id} className={cx("flex items-center gap-3 rounded-lg px-2.5 py-2 text-sm", r.user_id === user.id && "bg-brand/10 font-semibold")}>
                    <span className="w-5 text-center text-xs font-bold text-mute">{r.rank}</span>
                    <span className="min-w-0 flex-1 truncate">{r.name}{r.user_id === user.id ? " (you)" : ""}</span>
                    <span className="text-xs font-bold text-xp">{r.xp} XP</span>
                  </li>
                ))}
              </ol>
            ) : <p className="sub mt-3">Be the first on the board.</p>}
          </section>
        </div>
      </div>

      <section className="space-y-3">
        <h2 className="text-xl font-bold">VTU exam papers</h2>
        <ExamPapers course={course} />
      </section>

      <div className="flex flex-wrap gap-2">
        {course.is_owner && course.topics.length > 0 && playable && (
          <button className="btn-soft" onClick={moreQuestions} disabled={!!gen}>
            {gen ? <><Loader2 className="h-4 w-4 animate-spin" />{gen.topic ? `Generating: ${gen.topic}` : "Finishing…"}</> : <><Sparkles className="h-4 w-4" />Generate more questions</>}
          </button>
        )}
        <button className="btn-danger" onClick={remove}>{course.is_owner ? <><Trash2 className="h-4 w-4" />Delete course</> : <><LogOut className="h-4 w-4" />Leave class</>}</button>
      </div>

      <Modal open={!!setup} onClose={() => setSetup(null)} title="Quiz setup">
        {setup && (
          <div className="space-y-5">
            <div>
              <span className="label">Focus</span>
              <ChipSelect multi={false} value={setup.topic_ids.length ? "pick" : "all"} onChange={(v) => setSetup({ ...setup, topic_ids: v === "all" ? [] : (weak.length ? weak : course.topics).map((t) => t.id) })}
                options={[{ value: "all", label: "Adaptive · all topics" }, { value: "pick", label: "Selected topics" }]} />
              {setup.topic_ids.length > 0 && (
                <div className="mt-3"><ChipSelect value={setup.topic_ids} onChange={(v) => setSetup({ ...setup, topic_ids: v })}
                  options={course.topics.filter((t) => t.counts.total).map((t) => ({ value: t.id, label: t.name }))} /></div>
              )}
            </div>
            <div><span className="label">Questions</span><ChipSelect multi={false} value={setup.length} onChange={(v) => setSetup({ ...setup, length: v })} options={[5, 10, 15, 20].map((n) => ({ value: n, label: String(n) }))} /></div>
            <div><span className="label">Question types</span><ChipSelect value={setup.types} onChange={(v) => v.length && setSetup({ ...setup, types: v })} options={TYPE_OPTIONS} /></div>
            <div><span className="label">Timer per question</span><ChipSelect multi={false} value={setup.seconds_per_question} onChange={(v) => setSetup({ ...setup, seconds_per_question: v })}
              options={[{ value: 0, label: "Off" }, { value: 30, label: "30s" }, { value: 45, label: "45s" }, { value: 60, label: "60s" }, { value: 90, label: "90s" }]} /></div>
            <p className="rounded-xl bg-soft px-3.5 py-3 text-xs text-mute">The engine picks each next question from your weakest topics and steps difficulty up after a correct answer and down after a miss.</p>
            <button className="btn-primary w-full" onClick={start} disabled={starting}>{starting ? <Loader2 className="h-4 w-4 animate-spin" /> : <><Play className="h-4 w-4" />Start quiz</>}</button>
          </div>
        )}
      </Modal>
    </div>
  );
}
