import { useEffect } from "react";
import {
  Award, Brain, Calendar, CalendarCheck, CalendarHeart, Crown, Flag, Flame, Footprints, Loader2, Shield, Star,
  Target, Timer, TrendingUp, Trophy, Upload, X, Zap, Lock,
} from "lucide-react";

export const pct = (x) => `${Math.round((x || 0) * 100)}%`;
export const cx = (...a) => a.filter(Boolean).join(" ");

export function Spinner({ label }) {
  return (
    <div className="flex items-center justify-center gap-3 py-16 text-mute">
      <Loader2 className="h-5 w-5 animate-spin" /> <span className="text-sm">{label || "Loading…"}</span>
    </div>
  );
}

export function ErrorBox({ message, onRetry }) {
  return (
    <div className="card mx-auto mt-10 max-w-md p-6 text-center">
      <p className="font-semibold">Something went wrong</p>
      <p className="sub mt-1">{message}</p>
      {onRetry && <button className="btn-soft mt-4" onClick={onRetry}>Try again</button>}
    </div>
  );
}

export function Empty({ icon: Icon, title, children, action }) {
  return (
    <div className="card grid-bg flex flex-col items-center px-6 py-12 text-center">
      {Icon && <div className="mb-4 rounded-2xl bg-brand/10 p-3.5 text-brand"><Icon className="h-6 w-6" /></div>}
      <h3 className="text-lg font-bold">{title}</h3>
      <p className="sub mt-1 max-w-md">{children}</p>
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

export function Modal({ open, onClose, title, children, wide }) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e) => e.key === "Escape" && onClose?.();
    window.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => { window.removeEventListener("keydown", onKey); document.body.style.overflow = ""; };
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/50 p-0 backdrop-blur-sm sm:items-center sm:p-4" onMouseDown={(e) => e.target === e.currentTarget && onClose?.()}>
      <div role="dialog" aria-modal="true" aria-label={title} className={cx("card flex max-h-[92vh] w-full animate-pop flex-col rounded-b-none sm:rounded-2xl", wide ? "sm:max-w-3xl" : "sm:max-w-lg")}>
        <div className="flex items-center justify-between border-b border-line px-5 py-4">
          <h2 className="text-lg font-bold">{title}</h2>
          {onClose && <button className="btn-ghost btn-sm" onClick={onClose} aria-label="Close"><X className="h-4 w-4" /></button>}
        </div>
        <div className="overflow-y-auto px-5 py-5">{children}</div>
      </div>
    </div>
  );
}

export function Bar({ value, tone = "bg-brand", className = "h-2" }) {
  return (
    <div className={cx("w-full overflow-hidden rounded-full bg-soft", className)}>
      <div className={cx("h-full rounded-full transition-[width] duration-700 ease-out", tone)} style={{ width: `${Math.max(0, Math.min(1, value || 0)) * 100}%` }} />
    </div>
  );
}

export function Ring({ value, size = 96, stroke = 9, children, color = "rgb(var(--brand))" }) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="rgb(var(--soft))" strokeWidth={stroke} />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth={stroke} strokeLinecap="round"
          strokeDasharray={c} strokeDashoffset={c * (1 - Math.max(0, Math.min(1, value || 0)))} style={{ transition: "stroke-dashoffset .8s ease-out" }} />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">{children}</div>
    </div>
  );
}

export const STATUS = {
  weak: { label: "Weak", tone: "bg-rose-500", text: "text-rose-600 dark:text-rose-300", soft: "bg-rose-500/10", color: "#f43f5e" },
  learning: { label: "Learning", tone: "bg-amber-500", text: "text-amber-700 dark:text-amber-300", soft: "bg-amber-500/10", color: "#f59e0b" },
  mastered: { label: "Mastered", tone: "bg-emerald-500", text: "text-emerald-700 dark:text-emerald-300", soft: "bg-emerald-500/10", color: "#10b981" },
  new: { label: "Not started", tone: "bg-slate-400", text: "text-mute", soft: "bg-soft", color: "#94a3b8" },
};

export function StatusPill({ status }) {
  const s = STATUS[status] || STATUS.new;
  return <span className={cx("inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold", s.soft, s.text)}><span className={cx("h-1.5 w-1.5 rounded-full", s.tone)} />{s.label}</span>;
}

const DIFF = {
  easy: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
  medium: "bg-amber-500/10 text-amber-700 dark:text-amber-300",
  hard: "bg-rose-500/10 text-rose-700 dark:text-rose-300",
};
export function DiffPill({ value }) {
  return <span className={cx("rounded-full px-2.5 py-1 text-xs font-semibold capitalize", DIFF[value])}>{value}</span>;
}
export const TYPE_LABEL = { mcq: "Multiple choice", tf: "True / False", short: "Short answer" };

export function Stat({ icon: Icon, label, value, hint, tone = "text-brand bg-brand/10" }) {
  return (
    <div className="card flex items-center gap-4 p-4">
      <div className={cx("rounded-xl p-2.5", tone)}><Icon className="h-5 w-5" /></div>
      <div className="min-w-0">
        <div className="font-display text-2xl font-bold leading-tight">{value}</div>
        <div className="truncate text-xs font-medium text-mute">{label}{hint ? ` · ${hint}` : ""}</div>
      </div>
    </div>
  );
}

const BADGE_ICONS = {
  footprints: Footprints, flag: Flag, target: Target, flame: Flame, zap: Zap, calendar: Calendar,
  "calendar-check": CalendarCheck, "calendar-heart": CalendarHeart, award: Award, crown: Crown, trophy: Trophy,
  "trending-up": TrendingUp, timer: Timer, brain: Brain, shield: Shield, upload: Upload, star: Star,
};
export function BadgeMedal({ icon, earned = true, size = "h-14 w-14" }) {
  const Icon = BADGE_ICONS[icon] || Award;
  return (
    <div className={cx("relative flex shrink-0 items-center justify-center rounded-2xl", size,
      earned ? "bg-gradient-to-br from-amber-300 to-amber-500 text-amber-950 shadow-[0_8px_20px_-8px_rgb(245_158_11/0.8)]" : "bg-soft text-mute/60")}>
      <Icon className="h-1/2 w-1/2" strokeWidth={2.2} />
      {!earned && <Lock className="absolute -bottom-1 -right-1 h-4 w-4 rounded-full bg-card p-0.5 text-mute" />}
    </div>
  );
}

export function Toggle({ checked, onChange, label }) {
  return (
    <button type="button" role="switch" aria-checked={checked} onClick={() => onChange(!checked)} className="inline-flex items-center gap-2.5 text-sm font-medium">
      <span className={cx("relative h-6 w-11 rounded-full transition", checked ? "bg-brand" : "bg-line")}>
        <span className={cx("absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-all", checked ? "left-[22px]" : "left-0.5")} />
      </span>
      {label}
    </button>
  );
}

export function ChipSelect({ options, value, onChange, multi = true }) {
  const set = new Set(multi ? value : [value]);
  return (
    <div className="flex flex-wrap gap-2">
      {options.map((o) => {
        const on = set.has(o.value);
        return (
          <button key={String(o.value)} type="button" aria-pressed={on} className={cx("chip cursor-pointer px-3 py-1.5 transition hover:border-brand/60", on && "chip-on")}
            onClick={() => {
              if (!multi) return onChange(o.value);
              const next = new Set(set);
              on ? next.delete(o.value) : next.add(o.value);
              onChange([...next]);
            }}>
            {o.label}
          </button>
        );
      })}
    </div>
  );
}
