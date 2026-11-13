import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight, BrainCircuit, FileUp, GraduationCap, Loader2, Presentation, Target, Trophy } from "lucide-react";
import { useApp } from "../store";
import { Logo } from "../components/Layout";
import { cx } from "../components/ui";

const FEATURES = [
  { icon: FileUp, title: "Upload any syllabus", text: "PDF, DOCX or pasted notes become a structured topic map." },
  { icon: BrainCircuit, title: "AI-generated questions", text: "Every question is traced back to the topic it came from." },
  { icon: Target, title: "Adaptive practice", text: "Knowledge tracing finds weak topics and targets them next." },
  { icon: Trophy, title: "XP, streaks and badges", text: "Progress that rewards real mastery, not just clicks." },
];

export default function Auth() {
  const { signIn } = useApp();
  const navigate = useNavigate();
  const [mode, setMode] = useState("login");
  const [role, setRole] = useState("student");
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");

  const run = async (key, path, body) => {
    setBusy(key);
    setError("");
    try {
      await signIn(path, body);
      navigate("/");
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy("");
    }
  };
  const submit = (e) => {
    e.preventDefault();
    if (mode === "login") run("form", "/api/auth/login", { email: form.email, password: form.password });
    else run("form", "/api/auth/register", { ...form, role });
  };
  const demo = (who) => run(who, "/api/auth/login", { email: `${who}@demo.edu`, password: "demo1234" });
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  return (
    <div className="grid min-h-full lg:grid-cols-[1.1fr_1fr]">
      <section className="relative hidden overflow-hidden bg-[#141234] p-12 text-white lg:flex lg:flex-col">
        <div className="pointer-events-none absolute -left-24 -top-24 h-96 w-96 rounded-full bg-[#5348E0] opacity-50 blur-[110px]" />
        <div className="pointer-events-none absolute -bottom-32 right-0 h-96 w-96 rounded-full bg-[#F59E0B] opacity-20 blur-[120px]" />
        <Logo className="relative [&_span]:text-white" />
        <div className="relative my-auto max-w-lg">
          <p className="mb-4 inline-flex rounded-full border border-white/15 bg-white/5 px-3 py-1 text-xs font-semibold uppercase tracking-widest text-amber-300">Syllabus → Quiz → Mastery</p>
          <h1 className="text-4xl font-extrabold leading-tight xl:text-5xl">Turn your syllabus into a game you actually want to play.</h1>
          <p className="mt-4 text-base text-white/70">An adaptive revision companion for students and a question-bank generator for faculty, built on one transparent topic-to-question map.</p>
          <div className="mt-10 grid gap-4 sm:grid-cols-2">
            {FEATURES.map((f) => (
              <div key={f.title} className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
                <f.icon className="h-5 w-5 text-amber-300" />
                <div className="mt-2 text-sm font-bold">{f.title}</div>
                <div className="mt-1 text-xs leading-relaxed text-white/60">{f.text}</div>
              </div>
            ))}
          </div>
        </div>
        <p className="relative text-xs text-white/40">Mini Project BIS586 · Dept. of ISE, Bangalore Institute of Technology</p>
      </section>

      <section className="flex items-center justify-center px-5 py-10">
        <div className="w-full max-w-sm">
          <Logo className="mb-8 lg:hidden" />
          <h2 className="text-2xl font-bold">{mode === "login" ? "Welcome back" : "Create your account"}</h2>
          <p className="sub mt-1">{mode === "login" ? "Sign in to continue your streak." : "Pick a role to get the right workspace."}</p>

          <form onSubmit={submit} className="mt-6 space-y-4">
            {mode === "register" && (
              <>
                <div className="grid grid-cols-2 gap-2">
                  {[["student", GraduationCap, "Student"], ["teacher", Presentation, "Teacher"]].map(([value, Icon, label]) => (
                    <button key={value} type="button" aria-pressed={role === value} onClick={() => setRole(value)}
                      className={cx("flex items-center justify-center gap-2 rounded-xl border px-3 py-3 text-sm font-semibold transition", role === value ? "border-brand bg-brand/10 text-brand" : "border-line text-mute hover:text-ink")}>
                      <Icon className="h-4 w-4" />{label}
                    </button>
                  ))}
                </div>
                <div>
                  <label className="label" htmlFor="name">Full name</label>
                  <input id="name" className="input" required minLength={2} value={form.name} onChange={set("name")} autoComplete="name" />
                </div>
              </>
            )}
            <div>
              <label className="label" htmlFor="email">Email</label>
              <input id="email" type="email" className="input" required value={form.email} onChange={set("email")} autoComplete="email" />
            </div>
            <div>
              <label className="label" htmlFor="password">Password</label>
              <input id="password" type="password" className="input" required minLength={6} value={form.password} onChange={set("password")} autoComplete={mode === "login" ? "current-password" : "new-password"} />
            </div>
            {error && <p role="alert" className="rounded-xl bg-rose-500/10 px-3 py-2 text-sm font-medium text-rose-600 dark:text-rose-300">{error}</p>}
            <button className="btn-primary w-full" disabled={!!busy}>
              {busy === "form" ? <Loader2 className="h-4 w-4 animate-spin" /> : <>{mode === "login" ? "Sign in" : "Create account"}<ArrowRight className="h-4 w-4" /></>}
            </button>
          </form>

          <p className="mt-4 text-center text-sm text-mute">
            {mode === "login" ? "New here?" : "Already have an account?"}{" "}
            <button className="font-semibold text-brand hover:underline" onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(""); }}>
              {mode === "login" ? "Create an account" : "Sign in"}
            </button>
          </p>

          <div className="my-6 flex items-center gap-3 text-xs font-semibold uppercase tracking-wide text-mute"><span className="h-px flex-1 bg-line" />or explore the demo<span className="h-px flex-1 bg-line" /></div>
          <div className="grid grid-cols-2 gap-2">
            <button className="btn-soft" disabled={!!busy} onClick={() => demo("student")}>{busy === "student" ? <Loader2 className="h-4 w-4 animate-spin" /> : <GraduationCap className="h-4 w-4" />}Demo student</button>
            <button className="btn-soft" disabled={!!busy} onClick={() => demo("teacher")}>{busy === "teacher" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Presentation className="h-4 w-4" />}Demo teacher</button>
          </div>
        </div>
      </section>
    </div>
  );
}
