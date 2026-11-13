import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Area, AreaChart, Bar as RBar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ArrowRight, BookOpen, CheckCircle2, Crosshair, Flame, Loader2, Play, Target, Zap } from "lucide-react";
import { api } from "../api";
import { useApp, useLoad } from "../store";
import { BadgeMedal, Bar, Empty, ErrorBox, Ring, Spinner, Stat, STATUS, pct } from "../components/ui";

const day = (iso) => new Date(iso + "T00:00:00").toLocaleDateString(undefined, { day: "numeric", month: "short" });

export function ChartTip({ active, payload, label, unit }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="card px-3 py-2 text-xs">
      <div className="font-semibold">{day(label)}</div>
      {payload.map((p) => <div key={p.dataKey} className="text-mute">{p.name}: <b className="text-ink">{unit === "%" ? pct(p.value) : p.value}</b></div>)}
    </div>
  );
}

export default function Dashboard() {
  const { user, toast } = useApp();
  const navigate = useNavigate();
  const { data, error, loading, reload } = useLoad("/api/me/dashboard");
  const [starting, setStarting] = useState(false);
  if (loading) return <Spinner />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  const { totals, weak_topics: weak, activity, trend } = data;

  const practise = async (courseId, topicIds = []) => {
    setStarting(true);
    try {
      const r = await api.post("/api/quiz/start", { course_id: courseId, topic_ids: topicIds, types: ["mcq", "tf"], length: 8 });
      navigate(`/quiz/${r.session_id}`);
    } catch (e) {
      toast(e.message, "error");
      setStarting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="h-page">Hi, {user.name.split(" ")[0]}</h1>
          <p className="sub mt-1">{weak.length ? `You have ${weak.length} weak topic${weak.length > 1 ? "s" : ""} to work on today.` : totals.answered ? "No weak topics right now. Keep the streak alive." : "Start a quiz to see your mastery build up here."}</p>
        </div>
        <Link to="/courses" className="btn-primary"><Play className="h-4 w-4" />Practise now</Link>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="card flex items-center gap-5 p-5 lg:col-span-1">
          <Ring value={user.progress} size={104} color="rgb(var(--xp))">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-mute">Level</span>
            <span className="font-display text-3xl font-extrabold leading-none">{user.level}</span>
          </Ring>
          <div className="min-w-0">
            <div className="font-display text-lg font-bold">{user.title}</div>
            <div className="text-sm font-semibold text-xp">{user.xp} XP</div>
            <div className="mt-1 text-xs text-mute">{user.next_level_at - user.xp} XP to level {user.level + 1}</div>
            <div className="mt-3 inline-flex items-center gap-1.5 rounded-full bg-orange-500/10 px-2.5 py-1 text-xs font-bold text-orange-600 dark:text-orange-300">
              <Flame className="h-3.5 w-3.5" />{user.streak}-day streak
            </div>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-4 lg:col-span-2">
          <Stat icon={CheckCircle2} label="Questions answered" value={totals.answered} tone="text-emerald-600 bg-emerald-500/10" />
          <Stat icon={Target} label="Accuracy" value={pct(totals.accuracy)} />
          <Stat icon={Zap} label="Topics mastered" value={totals.topics_mastered} tone="text-xp bg-amber-500/10" />
          <Stat icon={Crosshair} label="Weak topics" value={totals.topics_weak} tone="text-rose-600 bg-rose-500/10" />
        </div>
      </div>

      {totals.answered === 0 ? (
        <Empty icon={BookOpen} title="Your learning loop starts here" action={<Link to="/courses" className="btn-primary">Go to courses</Link>}>
          Join a class with a code from your teacher, or upload your own syllabus or notes and get a quiz mapped to its topics.
        </Empty>
      ) : (
        <>
          <div className="grid items-start gap-4 lg:grid-cols-5">
            <section className="card p-5 lg:col-span-3">
              <div className="flex items-center justify-between">
                <h2 className="text-base font-bold">Weak topics to target</h2>
                <span className="text-xs text-mute">mastery below 50%</span>
              </div>
              {weak.length === 0 ? (
                <p className="sub mt-6 text-center">Nothing flagged. The adaptive engine will keep checking as you practise.</p>
              ) : (
                <ul className="mt-4 space-y-3">
                  {weak.map((t) => (
                    <li key={t.topic_id} className="flex items-center gap-4 rounded-xl border border-line p-3">
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-sm font-semibold">{t.topic}</div>
                        <div className="truncate text-xs text-mute">{t.course} · {t.attempts} attempts · {pct(t.accuracy)} correct</div>
                        <Bar value={t.p} tone={STATUS.weak.tone} className="mt-2 h-1.5" />
                      </div>
                      <span className="w-10 text-right text-sm font-bold text-rose-600 dark:text-rose-300">{pct(t.p)}</span>
                      <button className="btn-soft btn-sm" disabled={starting} onClick={() => practise(t.course_id, [t.topic_id])}>
                        {starting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <>Fix it<ArrowRight className="h-3.5 w-3.5" /></>}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </section>
            <section className="card p-5 lg:col-span-2">
              <h2 className="text-base font-bold">Mastery over time</h2>
              <p className="text-xs text-mute">average across the topics you have practised</p>
              <div className="mt-3 h-52">
                <ResponsiveContainer>
                  <AreaChart data={trend} margin={{ left: -18, right: 8, top: 8 }}>
                    <defs><linearGradient id="m" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="rgb(var(--brand))" stopOpacity={0.35} /><stop offset="1" stopColor="rgb(var(--brand))" stopOpacity={0} /></linearGradient></defs>
                    <CartesianGrid vertical={false} strokeDasharray="3 3" />
                    <XAxis dataKey="date" tickFormatter={day} tickLine={false} axisLine={false} minTickGap={24} />
                    <YAxis domain={[0, 1]} tickFormatter={pct} tickLine={false} axisLine={false} ticks={[0, 0.5, 1]} />
                    <Tooltip content={<ChartTip unit="%" />} />
                    <Area type="monotone" dataKey="mastery" name="Mastery" stroke="rgb(var(--brand))" strokeWidth={2.5} isAnimationActive={false} fill="url(#m)" dot={{ r: 3, fill: "rgb(var(--brand))" }} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </section>
          </div>

          <div className="grid items-start gap-4 lg:grid-cols-5">
            <section className="card p-5 lg:col-span-3">
              <h2 className="text-base font-bold">XP earned, last 14 days</h2>
              <div className="mt-3 h-52">
                <ResponsiveContainer>
                  <BarChart data={activity} margin={{ left: -18, right: 8, top: 8 }}>
                    <CartesianGrid vertical={false} strokeDasharray="3 3" />
                    <XAxis dataKey="date" tickFormatter={day} tickLine={false} axisLine={false} minTickGap={18} />
                    <YAxis tickLine={false} axisLine={false} allowDecimals={false} />
                    <Tooltip cursor={{ fill: "rgb(var(--soft))" }} content={<ChartTip />} />
                    <RBar dataKey="xp" name="XP" fill="rgb(var(--xp))" radius={[6, 6, 0, 0]} maxBarSize={28} isAnimationActive={false} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </section>
            <section className="card p-5 lg:col-span-2">
              <div className="flex items-center justify-between">
                <h2 className="text-base font-bold">Recent quizzes</h2>
                <Link to="/achievements" className="text-xs font-semibold text-brand hover:underline">Badges</Link>
              </div>
              <ul className="mt-3 divide-y divide-line">
                {data.recent_sessions.map((s) => (
                  <li key={s.id} className="flex items-center justify-between gap-3 py-2.5 text-sm">
                    <div className="min-w-0">
                      <Link to={`/courses/${s.course_id}`} className="block truncate font-semibold hover:text-brand">{s.course}</Link>
                      <div className="text-xs text-mute">{new Date(s.date).toLocaleDateString(undefined, { day: "numeric", month: "short" })} · {s.correct}/{s.answered} correct</div>
                    </div>
                    <span className="shrink-0 text-xs font-bold text-xp">+{s.xp} XP</span>
                  </li>
                ))}
              </ul>
              {data.recent_badges.length > 0 && (
                <div className="mt-4 flex items-center gap-3 border-t border-line pt-4">
                  {data.recent_badges.map((b) => <div key={b.key} title={b.name}><BadgeMedal icon={b.icon} size="h-10 w-10" /></div>)}
                  <span className="text-xs text-mute">latest badges</span>
                </div>
              )}
            </section>
          </div>
        </>
      )}
    </div>
  );
}
