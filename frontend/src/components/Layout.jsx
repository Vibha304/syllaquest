import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { BookOpen, Flame, LayoutDashboard, LibraryBig, LogOut, Medal, Moon, Sparkles, Sun, Trophy, Zap } from "lucide-react";
import { useApp } from "../store";
import { Bar, cx } from "./ui";

export function Logo({ className = "" }) {
  return (
    <div className={cx("flex items-center gap-2.5", className)}>
      <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand shadow-[0_6px_16px_-6px_rgb(var(--brand)/0.9)]">
        <Zap className="h-5 w-5 fill-amber-300 text-amber-300" />
      </div>
      <span className="font-display text-lg font-extrabold tracking-tight">Sylla<span className="text-brand">Quest</span></span>
    </div>
  );
}

export default function Layout() {
  const { user, signOut, theme, toggleTheme, meta } = useApp();
  const navigate = useNavigate();
  const teacher = user.role === "teacher";
  const links = teacher
    ? [{ to: "/", icon: LibraryBig, label: "Subjects" }]
    : [
        { to: "/", icon: LayoutDashboard, label: "Dashboard" },
        { to: "/courses", icon: BookOpen, label: "Courses" },
        { to: "/achievements", icon: Medal, label: "Badges" },
        { to: "/leaderboard", icon: Trophy, label: "Leaderboard" },
      ];
  const linkClass = ({ isActive }) =>
    cx("flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-semibold transition", isActive ? "bg-brand/10 text-brand" : "text-mute hover:bg-soft hover:text-ink");

  return (
    <div className="min-h-full lg:pl-64">
      {/* sidebar (desktop) */}
      <aside className="fixed inset-y-0 left-0 hidden w-64 flex-col border-r border-line bg-card px-4 py-5 lg:flex">
        <Logo className="px-2" />
        <nav className="mt-8 flex flex-col gap-1">
          {links.map((l) => (
            <NavLink key={l.to} to={l.to} end={l.to === "/"} className={linkClass}><l.icon className="h-[18px] w-[18px]" />{l.label}</NavLink>
          ))}
        </nav>

        {!teacher && (
          <div className="mt-6 rounded-2xl border border-line bg-soft/60 p-4">
            <div className="flex items-center justify-between text-xs font-semibold text-mute">
              <span>Level {user.level} · {user.title}</span>
              <span className="text-xp">{user.xp} XP</span>
            </div>
            <Bar value={user.progress} tone="bg-xp" className="mt-2 h-2" />
            <p className="mt-2 text-xs text-mute">{user.next_level_at - user.xp} XP to level {user.level + 1}</p>
          </div>
        )}

        <div className="mt-auto space-y-3">
          <div className="flex items-center gap-2 rounded-xl border border-line px-3 py-2 text-xs text-mute" title={meta.llm_model}>
            <Sparkles className={cx("h-4 w-4 shrink-0", meta.ai_enabled ? "text-emerald-500" : "text-amber-500")} />
            <span className="truncate">{meta.ai_enabled ? `AI engine: ${meta.llm_provider}` : "Offline question engine"}</span>
          </div>
          <div className="flex items-center gap-3 px-1">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-brand/15 text-sm font-bold text-brand">{user.name[0]?.toUpperCase()}</div>
            <div className="min-w-0 flex-1">
              <div className="truncate text-sm font-semibold">{user.name}</div>
              <div className="text-xs capitalize text-mute">{user.role}</div>
            </div>
            <button className="btn-ghost btn-sm" onClick={toggleTheme} aria-label="Toggle theme">{theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}</button>
            <button className="btn-ghost btn-sm" onClick={() => { signOut(); navigate("/login"); }} aria-label="Sign out"><LogOut className="h-4 w-4" /></button>
          </div>
        </div>
      </aside>

      {/* top bar (mobile) */}
      <header className="sticky top-0 z-30 flex items-center justify-between border-b border-line bg-card/90 px-4 py-3 backdrop-blur lg:hidden">
        <Logo />
        <div className="flex items-center gap-1">
          {!teacher && (
            <span className="mr-1 flex items-center gap-3 text-xs font-bold">
              <span className="flex items-center gap-1 text-orange-500"><Flame className="h-4 w-4" />{user.streak}</span>
              <span className="text-xp">{user.xp} XP</span>
            </span>
          )}
          <button className="btn-ghost btn-sm" onClick={toggleTheme} aria-label="Toggle theme">{theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}</button>
          <button className="btn-ghost btn-sm" onClick={() => { signOut(); navigate("/login"); }} aria-label="Sign out"><LogOut className="h-4 w-4" /></button>
        </div>
      </header>

      <main className="mx-auto w-full max-w-6xl px-4 pb-28 pt-6 sm:px-6 lg:px-8 lg:pb-12 lg:pt-8">
        <Outlet />
      </main>

      {/* bottom nav (mobile) */}
      {links.length > 1 && (
        <nav className="fixed inset-x-0 bottom-0 z-30 grid border-t border-line bg-card/95 backdrop-blur lg:hidden" style={{ gridTemplateColumns: `repeat(${links.length}, 1fr)` }}>
          {links.map((l) => (
            <NavLink key={l.to} to={l.to} end={l.to === "/"} className={({ isActive }) => cx("flex flex-col items-center gap-1 py-2.5 text-[11px] font-semibold", isActive ? "text-brand" : "text-mute")}>
              <l.icon className="h-5 w-5" />{l.label}
            </NavLink>
          ))}
        </nav>
      )}
    </div>
  );
}
