import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { BookOpen, KeyRound, Loader2, Plus, Users } from "lucide-react";
import { api } from "../api";
import { useApp, useLoad } from "../store";
import CreateCourse from "../components/CreateCourse";
import { Bar, Empty, ErrorBox, Spinner, pct } from "../components/ui";

export default function Courses() {
  const { toast } = useApp();
  const navigate = useNavigate();
  const { data, error, loading, reload } = useLoad("/api/courses");
  const [creating, setCreating] = useState(false);
  const [code, setCode] = useState("");
  const [joining, setJoining] = useState(false);

  const join = async (e) => {
    e.preventDefault();
    setJoining(true);
    try {
      const c = await api.post("/api/courses/join", { code });
      toast(`Joined ${c.name}`, "success");
      navigate(`/courses/${c.id}`);
    } catch (err) {
      toast(err.message, "error");
    } finally {
      setJoining(false);
    }
  };

  if (loading) return <Spinner />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="h-page">Courses</h1>
          <p className="sub mt-1">Classes you joined and courses built from your own material.</p>
        </div>
        <button className="btn-primary" onClick={() => setCreating(true)}><Plus className="h-4 w-4" />Upload syllabus</button>
      </div>

      <form onSubmit={join} className="card flex flex-wrap items-center gap-3 p-4">
        <KeyRound className="h-5 w-5 text-brand" />
        <label htmlFor="join" className="text-sm font-semibold">Have a class code?</label>
        <input id="join" className="input w-40 font-mono uppercase tracking-widest" placeholder="CN2026" maxLength={8} value={code} onChange={(e) => setCode(e.target.value.toUpperCase())} />
        <button className="btn-soft" disabled={joining || code.length < 4}>{joining ? <Loader2 className="h-4 w-4 animate-spin" /> : "Join class"}</button>
      </form>

      {data.length === 0 ? (
        <Empty icon={BookOpen} title="No courses yet" action={<button className="btn-primary" onClick={() => setCreating(true)}>Upload a syllabus</button>}>
          Upload a syllabus, chapter or notes and SyllaQuest will find its topics and write questions for each one.
        </Empty>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {data.map((c, i) => (
            <Link key={c.id} to={`/courses/${c.id}`} className="card group flex animate-rise flex-col p-5 transition hover:-translate-y-0.5 hover:border-brand/50" style={{ animationDelay: `${i * 40}ms` }}>
              <div className="flex items-start justify-between gap-3">
                <span className="chip">{c.kind === "class" ? <><Users className="h-3 w-3" />Class</> : "Personal"}</span>
                {c.weak_count > 0 && <span className="rounded-full bg-rose-500/10 px-2.5 py-1 text-xs font-semibold text-rose-600 dark:text-rose-300">{c.weak_count} weak</span>}
              </div>
              <h2 className="mt-3 text-lg font-bold leading-snug group-hover:text-brand">{c.name}</h2>
              <p className="mt-0.5 text-xs text-mute">{c.code ? `${c.code} · ` : ""}{c.kind === "class" ? c.owner_name : c.source_name || "Your upload"}</p>
              <div className="mt-auto pt-5">
                <div className="mb-1.5 flex justify-between text-xs font-medium text-mute">
                  <span>{c.topic_count} topics · {c.question_count} questions</span>
                  <span className="font-bold text-ink">{pct(c.mastery)}</span>
                </div>
                <Bar value={c.mastery} />
              </div>
            </Link>
          ))}
        </div>
      )}
      <CreateCourse open={creating} onClose={() => setCreating(false)} onCreated={reload} />
    </div>
  );
}
