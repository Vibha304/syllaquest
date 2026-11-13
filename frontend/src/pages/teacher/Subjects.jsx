import { useState } from "react";
import { Link } from "react-router-dom";
import { FileQuestion, LibraryBig, ListTree, Plus, Users } from "lucide-react";
import { useApp, useLoad } from "../../store";
import CreateCourse from "../../components/CreateCourse";
import { Empty, ErrorBox, Spinner, Stat, cx } from "../../components/ui";

export default function Subjects() {
  const { user } = useApp();
  const { data, error, loading, reload } = useLoad("/api/courses");
  const [creating, setCreating] = useState(false);
  if (loading) return <Spinner />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  const sum = (k) => data.reduce((a, c) => a + (c[k] || 0), 0);
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="h-page">Subjects</h1>
          <p className="sub mt-1">Welcome, {user.name}. Build a question bank for each subject you teach.</p>
        </div>
        <button className="btn-primary" onClick={() => setCreating(true)}><Plus className="h-4 w-4" />New subject</button>
      </div>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat icon={LibraryBig} label="Subjects" value={data.length} />
        <Stat icon={FileQuestion} label="Approved questions" value={sum("question_count")} tone="text-emerald-600 bg-emerald-500/10" />
        <Stat icon={ListTree} label="Drafts to review" value={sum("draft_count")} tone="text-xp bg-amber-500/10" />
        <Stat icon={Users} label="Students enrolled" value={sum("student_count")} tone="text-sky-600 bg-sky-500/10" />
      </div>

      {data.length === 0 ? (
        <Empty icon={LibraryBig} title="Create your first subject" action={<button className="btn-primary" onClick={() => setCreating(true)}>New subject</button>}>
          Upload a syllabus or textbook chapter. Topics are extracted automatically and a difficulty-graded question bank is generated for you to review.
        </Empty>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {data.map((c, i) => (
            <Link key={c.id} to={`/subjects/${c.id}`} className="card group flex animate-rise flex-col p-5 transition hover:-translate-y-0.5 hover:border-brand/50" style={{ animationDelay: `${i * 40}ms` }}>
              <div className="flex items-center justify-between">
                <span className="font-mono text-xs font-semibold text-brand">{c.code || "SUBJECT"}</span>
                <span className={cx("rounded-full px-2.5 py-1 text-xs font-semibold", c.published ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300" : "bg-soft text-mute")}>{c.published ? "Published" : "Private"}</span>
              </div>
              <h2 className="mt-2 text-lg font-bold leading-snug group-hover:text-brand">{c.name}</h2>
              <p className="mt-1 line-clamp-2 text-xs text-mute">{c.description || c.source_name || "No description"}</p>
              <dl className="mt-5 grid grid-cols-4 gap-2 border-t border-line pt-4 text-center">
                {[["Topics", c.topic_count], ["Questions", c.question_count], ["Drafts", c.draft_count], ["Students", c.student_count]].map(([l, v]) => (
                  <div key={l}><dd className="font-display text-lg font-bold">{v}</dd><dt className="text-[11px] text-mute">{l}</dt></div>
                ))}
              </dl>
            </Link>
          ))}
        </div>
      )}
      <CreateCourse open={creating} onClose={() => setCreating(false)} onCreated={reload} />
    </div>
  );
}
