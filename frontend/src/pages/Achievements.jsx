import { useLoad } from "../store";
import { BadgeMedal, ErrorBox, Spinner, cx } from "../components/ui";

export default function Achievements() {
  const { data, error, loading, reload } = useLoad("/api/me/badges");
  if (loading) return <Spinner />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  const earned = data.filter((b) => b.earned).length;
  return (
    <div className="space-y-6">
      <div>
        <h1 className="h-page">Badges</h1>
        <p className="sub mt-1">{earned} of {data.length} unlocked. Badges reward mastery, consistency and comebacks.</p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {data.map((b, i) => (
          <div key={b.key} className={cx("card flex animate-rise items-center gap-4 p-4", !b.earned && "opacity-70")} style={{ animationDelay: `${i * 25}ms` }}>
            <BadgeMedal icon={b.icon} earned={b.earned} />
            <div className="min-w-0">
              <div className="font-bold">{b.name}</div>
              <div className="text-xs text-mute">{b.description}</div>
              {b.earned && <div className="mt-1 text-[11px] font-semibold text-emerald-600 dark:text-emerald-300">Unlocked {new Date(b.earned_at).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" })}</div>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
