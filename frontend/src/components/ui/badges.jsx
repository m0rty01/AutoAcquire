export const bandClass = (band) =>
  ({ hot: "band-hot", warm: "band-warm", nurture: "band-nurture", low: "band-low" }[band] || "band-low");

export function ScoreBadge({ score, band }) {
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-[4px] border px-2 py-0.5 text-xs font-mono-plex font-semibold uppercase tracking-wider ${bandClass(band)}`}>
      <span>{score}</span>
      <span className="opacity-70">{band}</span>
    </span>
  );
}

export const titleize = (s) =>
  (s || "").split("_").map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(" ");

const STATUS_COLORS = {
  new: "text-blue-400 bg-blue-500/10 border-blue-500/20",
  ai_qualifying: "text-sky-400 bg-sky-500/10 border-sky-500/20",
  qualified: "text-green-400 bg-green-500/10 border-green-500/20",
  needs_review: "text-amber-400 bg-amber-500/10 border-amber-500/20",
  appointment_offered: "text-purple-400 bg-purple-500/10 border-purple-500/20",
  appointment_booked: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
  human_takeover: "text-orange-400 bg-orange-500/10 border-orange-500/20",
  contacted: "text-cyan-400 bg-cyan-500/10 border-cyan-500/20",
  purchased: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
  disqualified: "text-red-400 bg-red-500/10 border-red-500/20",
  lost: "text-zinc-400 bg-zinc-500/10 border-zinc-500/20",
};

export function StatusBadge({ status }) {
  const c = STATUS_COLORS[status] || "text-zinc-400 bg-zinc-500/10 border-zinc-500/20";
  return (
    <span className={`inline-flex items-center rounded-[4px] border px-2 py-0.5 text-xs font-mono-plex tracking-wide ${c}`}>
      {titleize(status)}
    </span>
  );
}
