import { useState } from "react";
import client from "@/lib/api";
import { toast } from "sonner";
import { titleize } from "@/components/ui/badges";
import { Card, Empty, Pill, Table, fmtDate, inputCls } from "./shared";

const PERMS = [["operational", "Operational notifications"], ["appointment", "Appointment-related"], ["promotional", "Promotional / marketing"]];

function PermissionEditor({ p, reload, readOnly }) {
  const [perm, setPerm] = useState(p.communication_permissions);
  const save = async () => {
    try { await client.put(`/leads/${p.lead.id}/communication-permissions`, perm); toast.success("Communication permissions recorded"); reload(); }
    catch (e) { toast.error(e.response?.data?.detail || "Failed to save"); }
  };
  return (
    <div className="space-y-2">
      {PERMS.map(([k, label]) => (
        <label key={k} className="flex items-center gap-2 text-sm">
          <input type="checkbox" data-testid={`perm-${k}`} disabled={readOnly} checked={!!perm[k]}
            onChange={(e) => setPerm({ ...perm, [k]: e.target.checked })} className="accent-[hsl(var(--primary))]" />
          {label}
        </label>
      ))}
      <p className="text-xs text-muted-foreground">Dealership referral consent does not authorize promotional messages. Record only what the customer explicitly agreed to.</p>
      {!readOnly && <button data-testid="perm-save-btn" onClick={save} className="text-xs bg-primary text-primary-foreground px-3 py-1.5 rounded-[4px] hover:opacity-90">Save permissions</button>}
    </div>
  );
}

export function CommunicationsTab({ p, reload, readOnly }) {
  const rows = [...p.communications, ...p.legacy_notifications.map((n) => ({ ...n, legacy: true }))];
  return (
    <div className="space-y-4" data-testid="tab-panel-communications">
      <Card title="Communication history">
        {rows.length === 0 ? <Empty label="No emails or SMS sent to this customer yet." /> : (
          <Table head={["Channel", "Template / subject", "To", "Status", "Sent"]} rows={rows.map((c) => [
            titleize(c.channel), titleize(c.template || c.subject), c.to || c.recipient_id,
            <span className="inline-flex items-center gap-1"><Pill s={c.status} />{c.legacy && <span className="text-[10px] text-muted-foreground">simulated</span>}</span>,
            fmtDate(c.sent_at || c.created_at),
          ])} />
        )}
      </Card>
      <Card title="Communication preferences">
        <PermissionEditor p={p} reload={reload} readOnly={readOnly} />
      </Card>
    </div>
  );
}

export function ConsentTab({ p, reload, readOnly }) {
  const [reason, setReason] = useState("");
  const active = p.lead.consent_status === "granted";
  const withdraw = async () => {
    if (!window.confirm("Record that this customer has withdrawn consent? Historical records are kept.")) return;
    try { await client.post(`/leads/${p.lead.id}/consent/withdraw`, { reason }); toast.success("Withdrawal recorded"); setReason(""); reload(); }
    catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
  };
  return (
    <div className="space-y-4" data-testid="tab-panel-consent">
      <Card title="Current status" action={<Pill s={p.lead.consent_status || "none"} />}>
        <div className="grid sm:grid-cols-3 gap-4 text-sm">
          {PERMS.map(([k, label]) => (
            <div key={k}><div className="text-[11px] font-mono-plex uppercase tracking-wider text-muted-foreground">{label}</div>
              <div data-testid={`consent-perm-${k}`}>{p.communication_permissions[k] ? "Permitted" : "Not permitted"}</div></div>
          ))}
        </div>
        {active && !readOnly && (
          <div className="flex gap-2 mt-4">
            <input data-testid="withdraw-reason" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Reason (optional)" className={inputCls} />
            <button data-testid="withdraw-consent-btn" onClick={withdraw} className="text-xs whitespace-nowrap border border-red-500/40 text-red-400 px-3 rounded-[4px] hover:bg-red-500/10">Record withdrawal</button>
          </div>
        )}
      </Card>
      <Card title="Consent records (read-only)">
        {p.consents.length === 0 ? <Empty label="No consent decision recorded." /> : (
          <Table testid="consent-records" head={["Status", "Agreement version", "Language", "Recipients", "Data shared", "Timestamp"]} rows={p.consents.map((c) => [
            <Pill s={c.status} />, c.agreement_version || "—", (c.language || "—").toUpperCase(),
            c.recipient_names.join(", ") || "—", (c.categories || []).map(titleize).join(", "),
            fmtDate(c.accepted_at || c.withdrawn_at || c.created_at),
          ])} />
        )}
      </Card>
      {p.communication_permission_history.length > 0 && (
        <Card title="Communication permission history">
          <Table head={["Operational", "Appointment", "Promotional", "Source", "Recorded"]} rows={p.communication_permission_history.slice().reverse().map((h) => [
            h.operational ? "Yes" : "No", h.appointment ? "Yes" : "No", h.promotional ? "Yes" : "No", titleize(h.source), fmtDate(h.at),
          ])} />
        </Card>
      )}
    </div>
  );
}
