import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowRight, Check, ChevronDown, Compass, Flame, Loader2, RotateCcw, Timer, TrendingDown, TrendingUp, X, Zap } from "lucide-react";
import { api } from "../api";
import { useApp } from "../store";
import { BadgeMedal, Bar, DiffPill, ErrorBox, Ring, Spinner, STATUS, StatusPill, TYPE_LABEL, cx, pct } from "../components/ui";

function Confetti() {
  const colors = ["#5348E0", "#F59E0B", "#10B981", "#F43F5E", "#38BDF8"];
  return (
    <div className="pointer-events-none fixed inset-0 z-40 overflow-hidden" aria-hidden>
      {Array.from({ length: 36 }, (_, i) => (
        <span key={i} className="absolute top-0 h-2.5 w-1.5 animate-fall rounded-sm"
          style={{ left: `${(i * 37) % 100}%`, background: colors[i % 5], animationDelay: `${(i % 12) * 0.12}s`, animationDuration: `${2.2 + (i % 5) * 0.3}s` }} />
      ))}
    </div>
  );
}

function Results({ sessionId }) {
  const navigate = useNavigate();
  const { toast } = useApp();
  const [data, setData] = useState(null);
  const [open, setOpen] = useState(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { api.get(`/api/quiz/${sessionId}/summary`).then(setData).catch((e) => toast(e.message, "error")); }, [sessionId, toast]);
  if (!data) return <Spinner label="Scoring your quiz…" />;
  const again = async () => {
    setBusy(true);
    try {
      const r = await api.post("/api/quiz/start", { course_id: data.course_id, types: ["mcq", "tf"], length: Math.max(5, data.answered) });
      navigate(`/quiz/${r.session_id}`);
    } catch (e) { toast(e.message, "error"); setBusy(false); }
  };
  const headline = data.accuracy === 1 ? "Flawless!" : data.accuracy >= 0.8 ? "Great work!" : data.accuracy >= 0.5 ? "Solid progress" : "Good practice. Now you know what to fix";
  return (
    <div className="mx-auto max-w-3xl animate-rise space-y-5 px-4 py-8">
      {data.accuracy >= 0.8 && <Confetti />}
      <div className="card p-6 text-center sm:p-8">
        <Ring value={data.accuracy} size={132} stroke={11} color={data.accuracy >= 0.5 ? "#10b981" : "#f59e0b"}>
          <span className="font-display text-3xl font-extrabold">{pct(data.accuracy)}</span>
          <span className="text-xs text-mute">{data.correct}/{data.answered}</span>
        </Ring>
        <h1 className="mt-4 text-2xl font-bold">{headline}</h1>
        <div className="mx-auto mt-5 grid max-w-md grid-cols-3 gap-3">
          {[["XP earned", `+${data.xp}`, "text-xp"], ["Best combo", `${data.best_combo}x`, "text-orange-500"], ["Avg. time", `${(data.avg_time_ms / 1000).toFixed(1)}s`, "text-ink"]].map(([l, v, c]) => (
            <div key={l} className="rounded-xl bg-soft px-2 py-3"><div className={cx("font-display text-xl font-bold", c)}>{v}</div><div className="text-[11px] font-medium text-mute">{l}</div></div>
          ))}
        </div>
        <div className="mt-6 flex flex-wrap justify-center gap-2">
          <Link to={`/courses/${data.course_id}`} className="btn-soft">Back to course</Link>
          <button className="btn-primary" onClick={again} disabled={busy}>{busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <><RotateCcw className="h-4 w-4" />Next adaptive round</>}</button>
        </div>
      </div>

      <section className="card p-5">
        <h2 className="text-base font-bold">How your mastery moved</h2>
        <ul className="mt-3 space-y-3">
          {data.topics.map((t) => {
            const up = t.after >= t.before;
            return (
              <li key={t.id}>
                <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
                  <span className="font-semibold">{t.name}</span>
                  <span className="flex items-center gap-2 text-xs">
                    <span className="text-mute">{t.correct}/{t.total} correct</span>
                    <span className={cx("inline-flex items-center gap-1 font-bold", up ? "text-emerald-600 dark:text-emerald-300" : "text-rose-600 dark:text-rose-300")}>
                      {up ? <TrendingUp className="h-3.5 w-3.5" /> : <TrendingDown className="h-3.5 w-3.5" />}{pct(t.before)} → {pct(t.after)}
                    </span>
                    <StatusPill status={t.status} />
                  </span>
                </div>
                <Bar value={t.after} tone={STATUS[t.status].tone} className="mt-1.5 h-1.5" />
              </li>
            );
          })}
        </ul>
      </section>

      <section className="card divide-y divide-line">
        <h2 className="p-5 text-base font-bold">Review answers</h2>
        {data.review.map((r, i) => (
          <div key={i}>
            <button className="flex w-full items-start gap-3 px-5 py-3.5 text-left" onClick={() => setOpen(open === i ? null : i)} aria-expanded={open === i}>
              <span className={cx("mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-white", r.correct ? "bg-emerald-500" : "bg-rose-500")}>{r.correct ? <Check className="h-3 w-3" /> : <X className="h-3 w-3" />}</span>
              <span className="min-w-0 flex-1 text-sm">{r.text}</span>
              <ChevronDown className={cx("h-4 w-4 shrink-0 text-mute transition", open === i && "rotate-180")} />
            </button>
            {open === i && (
              <div className="space-y-1.5 px-5 pb-4 pl-[52px] text-sm">
                <div className="flex flex-wrap gap-2 text-xs"><span className="chip">{r.topic}</span><DiffPill value={r.difficulty} /></div>
                {!r.correct && <p><span className="text-mute">Your answer:</span> {r.your_answer || <i>no answer</i>}</p>}
                <p><span className="text-mute">Correct answer:</span> <b>{r.correct_answer}</b></p>
                {r.explanation && <p className="text-mute">{r.explanation}</p>}
              </div>
            )}
          </div>
        ))}
      </section>
    </div>
  );
}

export default function Quiz() {
  const { sessionId } = useParams();
  const { setUser, toast } = useApp();
  const [q, setQ] = useState(null);
  const [stats, setStats] = useState({ xp: 0, combo: 0, correct: 0 });
  const [picked, setPicked] = useState(null);
  const [text, setText] = useState("");
  const [fb, setFb] = useState(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");
  const [left, setLeft] = useState(null);
  const startedAt = useRef(Date.now());
  const submitted = useRef(false);

  const show = useCallback((question) => {
    setQ(question); setPicked(null); setText(""); setFb(null);
    submitted.current = false;
    startedAt.current = Date.now();
    setLeft(question.seconds || null);
  }, []);

  useEffect(() => {
    setDone(false); setQ(null);
    api.get(`/api/quiz/${sessionId}`).then((r) => {
      if (r.finished) return setDone(true);
      setStats({ xp: r.xp, combo: r.combo, correct: r.correct });
      show(r.question);
    }).catch((e) => setError(e.message));
  }, [sessionId, show]);

  const submit = useCallback(async (answer) => {
    if (submitted.current || !q) return;
    submitted.current = true;
    setPicked(answer);
    setBusy(true);
    try {
      const r = await api.post(`/api/quiz/${sessionId}/answer`, { question_id: q.id, answer, time_ms: Date.now() - startedAt.current });
      setFb(r);
      setStats({ xp: r.session.xp, combo: r.combo, correct: r.session.correct });
      setUser(r.user);
    } catch (e) {
      toast(e.message, "error");
      submitted.current = false;
    } finally {
      setBusy(false);
    }
  }, [q, sessionId, setUser, toast]);

  const next = useCallback(() => {
    if (!fb) return;
    if (fb.finished) setDone(true);
    else show(fb.next);
  }, [fb, show]);

  // countdown
  useEffect(() => {
    if (!q?.seconds || fb) return;
    const id = setInterval(() => {
      const remaining = q.seconds - (Date.now() - startedAt.current) / 1000;
      setLeft(Math.max(0, remaining));
      if (remaining <= 0) { clearInterval(id); submit(""); }
    }, 200);
    return () => clearInterval(id);
  }, [q, fb, submit]);

  // keyboard shortcuts
  useEffect(() => {
    const onKey = (e) => {
      if (e.target.tagName === "TEXTAREA") return;
      if (fb) { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); next(); } return; }
      if (!q || q.type === "short") return;
      const k = e.key.toLowerCase();
      const idx = q.type === "tf" ? { t: 0, f: 1, 1: 0, 2: 1 }[k] : { a: 0, b: 1, c: 2, d: 3, 1: 0, 2: 1, 3: 2, 4: 3 }[k];
      if (idx !== undefined && q.options[idx]) submit(q.options[idx]);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [q, fb, next, submit]);

  if (error) return <ErrorBox message={error} />;
  if (done) return <Results sessionId={sessionId} />;
  if (!q) return <Spinner label="Picking your first question…" />;

  const timed = q.seconds > 0;
  const low = timed && left !== null && left <= 8 && !fb;
  return (
    <div className="mx-auto flex min-h-full max-w-3xl flex-col px-4 py-5">
      <header className="flex items-center gap-4">
        <Link to="/courses" className="btn-ghost btn-sm" aria-label="Quit quiz"><X className="h-4 w-4" /></Link>
        <div className="flex-1">
          <Bar value={(q.number - (fb ? 0 : 1)) / q.total} className="h-2.5" />
        </div>
        <span className="text-xs font-bold text-mute">{q.number}/{q.total}</span>
        <span className={cx("flex items-center gap-1 text-sm font-bold", stats.combo >= 2 ? "text-orange-500" : "text-mute")} title="Combo: consecutive correct answers"><Flame className={cx("h-4 w-4", stats.combo >= 3 && "fill-orange-400")} />{stats.combo}</span>
        <span className="flex items-center gap-1 text-sm font-bold text-xp"><Zap className="h-4 w-4 fill-current" />{stats.xp}</span>
      </header>

      <div key={q.id} className="mt-6 flex-1 animate-rise">
        <div className="mb-3 flex items-start gap-2 rounded-xl bg-brand/10 px-3.5 py-2.5 text-xs font-medium text-brand">
          <Compass className="mt-0.5 h-3.5 w-3.5 shrink-0" /><span>{q.reason}</span>
        </div>
        <div className={cx("card p-5 sm:p-7", fb && !fb.correct && "animate-shake")}>
          <div className="flex flex-wrap items-center gap-2">
            <span className="chip chip-on">{q.topic.name}</span>
            <DiffPill value={q.difficulty} />
            <span className="chip capitalize">{q.bloom}</span>
            <span className="chip">{TYPE_LABEL[q.type]}</span>
            {timed && (
              <span className={cx("ml-auto flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-bold tabular-nums", low ? "bg-rose-500/10 text-rose-600 dark:text-rose-300" : "bg-soft text-mute")}>
                <Timer className="h-3.5 w-3.5" />{Math.ceil(left ?? q.seconds)}s
              </span>
            )}
          </div>
          {timed && <Bar value={(left ?? q.seconds) / q.seconds} tone={low ? "bg-rose-500" : "bg-brand/60"} className="mt-4 h-1" />}
          <h1 className="mt-5 font-sans text-lg font-semibold leading-relaxed sm:text-xl">{q.text}</h1>

          {q.type !== "short" ? (
            <div className={cx("mt-6 grid gap-3", q.type === "tf" && "sm:grid-cols-2")}>
              {q.options.map((opt, i) => {
                const isAnswer = fb && opt === fb.correct_answer;
                const isWrongPick = fb && opt === picked && !fb.correct;
                return (
                  <button key={opt} disabled={!!fb || busy} onClick={() => submit(opt)}
                    className={cx("flex w-full items-center gap-3 rounded-xl border-2 px-4 py-3.5 text-left text-sm font-medium transition",
                      isAnswer ? "border-emerald-500 bg-emerald-500/10" : isWrongPick ? "border-rose-500 bg-rose-500/10" : picked === opt ? "border-brand bg-brand/5" : "border-line hover:border-brand/60 hover:bg-soft/60",
                      fb && !isAnswer && !isWrongPick && "opacity-55")}>
                    <span className={cx("flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-xs font-bold",
                      isAnswer ? "bg-emerald-500 text-white" : isWrongPick ? "bg-rose-500 text-white" : "bg-soft text-mute")}>
                      {isAnswer ? <Check className="h-4 w-4" /> : isWrongPick ? <X className="h-4 w-4" /> : q.type === "tf" ? opt[0] : "ABCD"[i]}
                    </span>
                    <span className="flex-1">{opt}</span>
                  </button>
                );
              })}
            </div>
          ) : (
            <form className="mt-6" onSubmit={(e) => { e.preventDefault(); if (text.trim()) submit(text.trim()); }}>
              <textarea className="input min-h-[110px]" placeholder="Type your answer in one or two sentences…" value={text} disabled={!!fb} onChange={(e) => setText(e.target.value)} autoFocus />
              {!fb && <button className="btn-primary mt-3" disabled={busy || !text.trim()}>{busy ? <Loader2 className="h-4 w-4 animate-spin" /> : "Check answer"}</button>}
            </form>
          )}
        </div>

        {fb && (
          <div className={cx("card relative mt-4 animate-rise border-2 p-5", fb.correct ? "border-emerald-500/50" : "border-rose-500/50")} aria-live="polite">
            {fb.correct && <span className="absolute right-5 top-3 animate-floatup font-display text-xl font-extrabold text-xp">+{fb.xp_earned + fb.bonus_xp} XP</span>}
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
              <h2 className={cx("text-lg font-bold", fb.correct ? "text-emerald-600 dark:text-emerald-300" : "text-rose-600 dark:text-rose-300")}>
                {fb.correct ? (fb.combo >= 3 ? `Correct! ${fb.combo} in a row` : "Correct!") : picked === "" ? "Time's up" : "Not quite"}
              </h2>
              {fb.correct && <span className="text-sm font-bold text-xp">+{fb.xp_earned} XP{fb.bonus_xp ? ` · +${fb.bonus_xp} quiz bonus` : ""}</span>}
            </div>
            {(!fb.correct || q.type === "short") && <p className="mt-2 text-sm"><span className="text-mute">{q.type === "short" ? "Model answer:" : "Correct answer:"}</span> <b>{fb.correct_answer}</b></p>}
            {fb.explanation && <p className="mt-2 text-sm text-mute">{fb.explanation}</p>}
            <div className="mt-4 rounded-xl bg-soft/70 p-3">
              <div className="flex items-center justify-between text-xs font-semibold">
                <span className="text-mute">Mastery · {fb.mastery.topic}</span>
                <span className={fb.mastery.after >= fb.mastery.before ? "text-emerald-600 dark:text-emerald-300" : "text-rose-600 dark:text-rose-300"}>{pct(fb.mastery.before)} → {pct(fb.mastery.after)}</span>
              </div>
              <Bar value={fb.mastery.after} tone={STATUS[fb.mastery.status]?.tone} className="mt-2 h-1.5" />
            </div>
            {(fb.new_badges.length > 0 || fb.level_up) && (
              <div className="mt-3 flex flex-wrap items-center gap-3 rounded-xl bg-amber-500/10 p-3">
                {fb.level_up && <span className="rounded-full bg-xp px-3 py-1 text-xs font-extrabold text-white dark:text-amber-950">Level up! Now level {fb.user.level}</span>}
                {fb.new_badges.map((b) => (
                  <span key={b.key} className="flex animate-pop items-center gap-2 text-sm font-semibold"><BadgeMedal icon={b.icon} size="h-9 w-9" />{b.name} unlocked</span>
                ))}
              </div>
            )}
            <button className="btn-primary mt-4 w-full sm:w-auto" onClick={next} autoFocus>{fb.finished ? "See results" : "Next question"}<ArrowRight className="h-4 w-4" /></button>
          </div>
        )}
      </div>
      {!fb && q.type !== "short" && <p className="mt-4 hidden text-center text-xs text-mute sm:block">Tip: press {q.type === "tf" ? "T or F" : "A–D or 1–4"} to answer, Enter to continue</p>}
    </div>
  );
}
