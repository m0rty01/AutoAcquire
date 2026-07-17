export function PageHeader({ title, subtitle, children }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4 mb-6">
      <div>
        <h1 className="font-head font-black text-2xl sm:text-3xl tracking-tight">{title}</h1>
        {subtitle && <p className="text-sm text-muted-foreground mt-1">{subtitle}</p>}
      </div>
      {children}
    </div>
  );
}

export function MetricTile({ label, value, hint, accent }) {
  return (
    <div className="border border-border rounded-[4px] bg-card p-5 h-full flex flex-col justify-between">
      <div className="text-xs font-mono-plex uppercase tracking-[0.2em] text-muted-foreground">{label}</div>
      <div className={`font-head font-black text-4xl tracking-tighter mt-3 ${accent || ""}`}>{value}</div>
      {hint && <div className="text-xs text-muted-foreground mt-1">{hint}</div>}
    </div>
  );
}

export function Loading({ label = "Loading…" }) {
  return <div className="text-muted-foreground font-mono-plex text-sm py-12 text-center">{label}</div>;
}

export function Empty({ label }) {
  return <div className="text-muted-foreground text-sm py-12 text-center border border-dashed border-border rounded-[4px]">{label}</div>;
}
