import { titleize } from "@/components/ui/badges";
import { tr, fmtDateL, fmtDayL, moneyL } from "@/lib/adminI18n";

export const fmtDate = fmtDateL;
export const fmtDay = fmtDayL;
export const money = moneyL;

export const Card = ({ title, children, action, testid }) => (
  <div className="border border-border rounded-[4px] bg-card p-5" data-testid={testid}>
    {(title || action) && (
      <div className="flex items-center justify-between mb-3 gap-2">
        {title && <h3 className="font-head font-bold tracking-tight">{tr(title)}</h3>}
        {action}
      </div>
    )}
    {children}
  </div>
);

export const Fields = ({ rows, cols = "sm:grid-cols-3" }) => (
  <dl className={`grid grid-cols-2 ${cols} gap-y-4 gap-x-6 text-sm`}>
    {rows.map(([k, v, id]) => (
      <div key={k} data-testid={id}>
        <dt className="text-[11px] font-mono-plex uppercase tracking-wider text-muted-foreground">{tr(k)}</dt>
        <dd className="mt-0.5 break-words">{v === 0 ? 0 : v || "—"}</dd>
      </div>
    ))}
  </dl>
);

const TONE = {
  confirmed: "text-emerald-400 border-emerald-500/30 bg-emerald-500/10", accepted: "text-emerald-400 border-emerald-500/30 bg-emerald-500/10",
  verified: "text-emerald-400 border-emerald-500/30 bg-emerald-500/10", completed: "text-emerald-400 border-emerald-500/30 bg-emerald-500/10",
  delivered: "text-emerald-400 border-emerald-500/30 bg-emerald-500/10", sent: "text-sky-400 border-sky-500/30 bg-sky-500/10",
  requested: "text-amber-400 border-amber-500/30 bg-amber-500/10", reported: "text-amber-400 border-amber-500/30 bg-amber-500/10",
  open: "text-amber-400 border-amber-500/30 bg-amber-500/10", declined: "text-red-400 border-red-500/30 bg-red-500/10",
  rejected: "text-red-400 border-red-500/30 bg-red-500/10", withdrawn: "text-red-400 border-red-500/30 bg-red-500/10",
  failed: "text-red-400 border-red-500/30 bg-red-500/10", cancelled: "text-zinc-400 border-zinc-500/30 bg-zinc-500/10",
  no_show: "text-orange-400 border-orange-500/30 bg-orange-500/10",
};
export const Pill = ({ s }) => (
  <span className={`inline-flex items-center rounded-[4px] border px-2 py-0.5 text-[11px] font-mono-plex ${TONE[s] || "text-zinc-300 border-border bg-secondary"}`}>
    {titleize(s || "unknown")}
  </span>
);

export const Empty = ({ label, testid }) => (
  <div data-testid={testid} className="text-sm text-muted-foreground py-10 text-center border border-dashed border-border rounded-[4px]">{tr(label)}</div>
);

export function Table({ head, rows, testid }) {
  return (
    <div className="overflow-x-auto" data-testid={testid}>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-[11px] font-mono-plex uppercase tracking-wider text-muted-foreground border-b border-border">
            {head.map((h) => <th key={h} className="pb-2 pr-4 font-medium whitespace-nowrap">{tr(h)}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-b border-border last:border-0">
              {r.map((c, j) => <td key={j} className="py-2.5 pr-4 align-top">{c}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export const inputCls = "w-full rounded-[4px] border border-input bg-background px-2.5 py-1.5 text-sm outline-none focus:border-primary transition-colors duration-200";
