import { useEffect, useState, useCallback } from "react";
import client from "@/lib/api";
import { PageHeader, Loading } from "@/components/Bits";
import { toast } from "sonner";
import { EnvelopeSimple, ChatText, ArrowClockwise } from "@phosphor-icons/react";
import { titleize } from "@/components/ui/badges";
import { Pill, Table, fmtDate, inputCls } from "@/components/profile/shared";

function ProviderCard({ icon: Icon, title, p, extra }) {
  return (
    <div className="border border-border rounded-[4px] bg-card p-5" data-testid={`provider-${title.toLowerCase()}`}>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2 font-head font-bold"><Icon size={18} weight="bold" className="text-primary" /> {title} · {p.provider}</div>
        <span data-testid={`provider-${title.toLowerCase()}-status`} className={`text-[11px] font-mono-plex px-2 py-0.5 rounded-[4px] border ${p.configured ? "text-emerald-400 border-emerald-500/30 bg-emerald-500/10" : "text-amber-400 border-amber-500/30 bg-amber-500/10"}`}>
          {p.configured ? "CONNECTED" : "PENDING CREDENTIALS"}
        </span>
      </div>
      <div className="text-xs text-muted-foreground space-y-1 font-mono-plex break-all">
        <div>From: {p.from || "—"}</div>
        {extra.map(([k, v]) => <div key={k}>{k}: {v}</div>)}
      </div>
      {!p.configured && <p className="text-xs text-amber-400/90 mt-2">Messages are recorded as “Not Configured” and are not delivered until credentials are added.</p>}
    </div>
  );
}

export default function Communications() {
  const [cfg, setCfg] = useState(null);
  const [data, setData] = useState(null);
  const [f, setF] = useState({ channel: "", status: "", direction: "" });
  const load = useCallback(() => {
    client.get("/communications", { params: Object.fromEntries(Object.entries(f).filter(([, v]) => v)) }).then((r) => setData(r.data)).catch(() => { setData({ items: [], summary: {} }); toast.error("Could not load communications"); });
  }, [f]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { client.get("/communications/config").then((r) => setCfg(r.data)).catch(() => setCfg({ email: { provider: "Resend", configured: false }, sms: { provider: "Twilio", configured: false } })); }, []);
  const retry = async (id) => {
    try { const { data } = await client.post(`/communications/${id}/retry`); toast.success(`Retried · ${titleize(data.status)}`); load(); }
    catch (e) { toast.error(e.response?.data?.detail || "Retry failed"); }
  };
  const sel = (k, opts, all) => (
    <select data-testid={`comms-filter-${k}`} value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} className={`${inputCls} w-auto`}>
      <option value="">{all}</option>{opts.map((o) => <option key={o} value={o}>{titleize(o)}</option>)}
    </select>
  );
  if (!cfg || !data) return <Loading />;
  return (
    <div data-testid="communication-center">
      <PageHeader title="Communication Center" subtitle="Every email and SMS sent to customers, dealerships and staff" />
      <div className="grid md:grid-cols-2 gap-4 mb-6">
        <ProviderCard icon={EnvelopeSimple} title="Email" p={cfg.email} extra={[["Webhook", cfg.email.webhook_url], ["Signing secret", cfg.email.webhook_signing ? "set" : "not set"]]} />
        <ProviderCard icon={ChatText} title="SMS" p={cfg.sms} extra={[["Status webhook", cfg.sms.status_webhook_url], ["Inbound webhook", cfg.sms.inbound_webhook_url]]} />
      </div>
      <div className="flex flex-wrap items-center gap-2 mb-4">
        {sel("channel", ["email", "sms"], "All channels")}
        {sel("status", ["queued", "sent", "delivered", "bounced", "failed", "undelivered", "blocked", "not_configured", "received"], "All statuses")}
        {sel("direction", ["outbound", "inbound"], "Both directions")}
        <div className="flex gap-2 ml-auto text-xs font-mono-plex text-muted-foreground" data-testid="comms-summary">
          {Object.entries(data.summary).map(([k, v]) => <span key={k}>{titleize(k)}: {v}</span>)}
        </div>
      </div>
      <div className="border border-border rounded-[4px] bg-card p-4">
        {data.items.length === 0 ? <div className="text-sm text-muted-foreground text-center py-10">No communications yet.</div> : (
          <Table testid="comms-table" head={["When", "Channel", "Dir.", "Template", "Customer", "Recipient", "Rep", "Status", ""]} rows={data.items.map((c) => [
            <span className="text-xs font-mono-plex whitespace-nowrap">{fmtDate(c.created_at)}</span>, titleize(c.channel), titleize(c.direction),
            titleize(c.template || c.category), c.customer_name || <span className="text-muted-foreground">{titleize(c.recipient_type)}</span>,
            <span className="text-xs break-all">{c.direction === "inbound" ? c.from : c.to || "—"}</span>, c.representative || "—",
            <div><Pill s={c.status} />{c.error && <div className="text-[11px] text-muted-foreground mt-1 max-w-[220px]">{c.error}</div>}</div>,
            ["failed", "not_configured"].includes(c.status) ? <button data-testid={`comm-retry-${c.id}`} onClick={() => retry(c.id)} className="text-xs text-primary flex items-center gap-1 hover:underline"><ArrowClockwise size={12} /> Retry</button> : null,
          ])} />
        )}
      </div>
    </div>
  );
}
