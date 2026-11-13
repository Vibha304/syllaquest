import { Flame, Trophy } from "lucide-react";
import { useLoad } from "../store";
import { Empty, ErrorBox, Spinner, cx } from "../components/ui";

const MEDAL = ["bg-amber-400 text-amber-950", "bg-slate-300 text-slate-800", "bg-orange-400 text-orange-950"];

export default function Leaderboard() {
  const { data, error, loading, reload } = useLoad("/api/leaderboard");
  if (loading) return <Spinner />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  return (
    <div className="space-y-6">
      <div>
        <h1 className="h-page">Leaderboard</h1>
        <p className="sub mt-1">All students, ranked by total XP.</p>
      </div>
      {data.rows.length === 0 ? <Empty icon={Trophy} title="No scores yet">Finish a quiz to appear here.</Empty> : (
        <div className="card divide-y divide-line overflow-hidden">
          {data.rows.map((r) => (
            <div key={r.user_id} className={cx("flex items-center gap-4 px-4 py-3.5 sm:px-5", r.user_id === data.me && "bg-brand/10")}>
              <span className={cx("flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-bold", MEDAL[r.rank - 1] || "bg-soft text-mute")}>{r.rank}</span>
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-semibold">{r.name}{r.user_id === data.me ? " (you)" : ""}</div>
                <div className="text-xs text-mute">Level {r.level} · {r.title}</div>
              </div>
              {r.streak > 0 && <span className="hidden items-center gap-1 text-xs font-bold text-orange-500 sm:flex"><Flame className="h-3.5 w-3.5" />{r.streak}</span>}
              <span className="w-20 text-right font-display text-base font-bold text-xp">{r.xp} XP</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
