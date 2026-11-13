import { STATUS } from "./ui";

/** Radial syllabus -> topic -> question graph. Each dot is a question (colour = difficulty);
 *  the ring around a topic shows the learner's mastery of it. */
const DOT = { easy: "#10b981", medium: "#f59e0b", hard: "#f43f5e" };

export default function TopicGraph({ course, onSelect, showMastery = true }) {
  const topics = course.topics;
  const n = topics.length;
  if (!n) return null;
  const W = 600, H = 500, cx = W / 2, cy = H / 2 - 6;
  const R = Math.min(165, 100 + n * 10);
  const short = (s, m = 18) => (s.length > m ? s.slice(0, m - 1) + "…" : s);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Topic to question map">
      {topics.map((t, i) => {
        const a = (i / n) * Math.PI * 2 - Math.PI / 2;
        const x = cx + R * Math.cos(a), y = cy + R * Math.sin(a) * 0.72;
        const st = STATUS[showMastery ? t.mastery.status : "new"];
        const dots = [];
        ["easy", "medium", "hard"].forEach((d) => { for (let k = 0; k < t.counts[d]; k++) dots.push(d); });
        const shown = dots.slice(0, 24);
        const p = showMastery ? t.mastery.p : 0;
        const rr = 30, circ = 2 * Math.PI * rr;
        const anchor = "middle";
        const lx = Math.max(95, Math.min(W - 95, x));
        const ly = anchor === "middle" ? y + (Math.sin(a) > 0 ? 78 : -84) : y + (Math.sin(a) > 0 ? 82 : -80);
        return (
          <g key={t.id} className={onSelect ? "cursor-pointer" : ""} onClick={() => onSelect?.(t)}>
            <line x1={cx} y1={cy} x2={x} y2={y} stroke="rgb(var(--line))" strokeWidth="2" />
            {shown.map((d, k) => {
              const ring = Math.floor(k / 12), idx = k % 12;
              const da = (idx / 12) * Math.PI * 2 + ring * 0.26;
              const dr = 45 + ring * 11;
              return <circle key={k} cx={x + dr * Math.cos(da)} cy={y + dr * Math.sin(da)} r="4.2" fill={DOT[d]} opacity="0.9" />;
            })}
            <circle cx={x} cy={y} r={rr} fill="rgb(var(--card))" stroke="rgb(var(--soft))" strokeWidth="6" />
            {showMastery && <circle cx={x} cy={y} r={rr} fill="none" stroke={st.color} strokeWidth="6" strokeLinecap="round"
              strokeDasharray={circ} strokeDashoffset={circ * (1 - p)} transform={`rotate(-90 ${x} ${y})`} />}
            <text x={x} y={y + 5} textAnchor="middle" fontSize="15" fontWeight="700" fill="rgb(var(--ink))">
              {showMastery ? `${Math.round(p * 100)}%` : t.counts.total + t.counts.draft}
            </text>
            <text x={lx} y={ly} textAnchor={anchor} fontSize="15" fontWeight="600" fill="rgb(var(--ink))">{short(t.name)}</text>
            <text x={lx} y={ly + 17} textAnchor={anchor} fontSize="13" fill="rgb(var(--mute))">
              {t.counts.total} question{t.counts.total === 1 ? "" : "s"}{t.counts.draft ? ` · ${t.counts.draft} draft` : ""}
            </text>
          </g>
        );
      })}
      <circle cx={cx} cy={cy} r="50" fill="rgb(var(--brand))" />
      <text x={cx} y={cy - 1} textAnchor="middle" fontSize="15" fontWeight="700" fill="#fff">{short(course.code || "Syllabus", 10)}</text>
      <text x={cx} y={cy + 17} textAnchor="middle" fontSize="12" fill="#fff" opacity="0.8">{n} topics</text>
      <g transform={`translate(16 ${H - 12})`} fontSize="13" fill="rgb(var(--mute))">
        {Object.entries(DOT).map(([k, c], i) => (
          <g key={k} transform={`translate(${i * 92} 0)`}><circle cx="5" cy="-4" r="4" fill={c} /><text x="14" y="0">{k}</text></g>
        ))}
      </g>
    </svg>
  );
}
