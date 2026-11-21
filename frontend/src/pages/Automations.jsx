import { tr } from "@/lib/adminI18n";
import { useEffect, useState, useCallback } from "react";
import { Navigate } from "react-router-dom";
import client from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { PageHeader, Loading } from "@/components/Bits";
import { toast } from "sonner";
import { Play, ArrowClockwise } from "@phosphor-icons/react";
import { titleize } from "@/components/ui/badges";
import { Pill, Table, fmtDate, inputCls } from "@/components/profile/shared";

function RuleCard({ rule, templates, users, canEdit, onSaved }) {
  const [r, setR] = useState(rule);
  const dirty = JSON.stringify(r) !== JSON.stringify(rule);
  const toggleCh = (ch) => setR({ ...r, channels: r.channels.includes(ch) ? r.channels.filter((c) => c !== ch) : [...r.channels, ch] });
  const save = async (patch) => {
    const body = patch || { enabled: r.enabled, delay_minutes: Number(r.delay_minutes), channels: r.channels, template: r.template, language: r.language, assign_to_user_id: r.assign_to_user_id || null, params: r.params };
    try { await client.patch(`/automations/${rule.key}`, body); toast.success("Automation saved"); onSaved(); } catch (e) { toast.error(e.response?.data?.detail || "Save failed"); }
  };
  return (
    <div className="border border-border rounded-[4px] bg-card p-5" data-testid={`rule-${rule.key}`}>
      <div className="flex items-center justify-between gap-3 mb-3">
        <div>
          <div className="font-head font-bold">{rule.name}</div>
          <div className="text-[11px] font-mono-plex text-muted-foreground">trigger: {rule.trigger} · ✓ {rule.stats.success} · ✕ {rule.stats.failed} · ⏱ {rule.stats.scheduled}</div>
        </div>
        <label className="flex items-center gap-2 text-xs">
          <input type="checkbox" data-testid={`rule-enabled-${rule.key}`} disabled={!canEdit} checked={r.enabled}
            onChange={(e) => { setR({ ...r, enabled: e.target.checked }); save({ enabled: e.target.checked }); }} />
          {r.enabled ? "Enabled" : "Disabled"}
        </label>
      </div>
      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3 text-sm">
        <div><label className="text-xs text-muted-foreground">Delay (minutes)</label>
          <input data-testid={`rule-delay-${rule.key}`} type="number" min={0} disabled={!canEdit} value={r.delay_minutes} onChange={(e) => setR({ ...r, delay_minutes: e.target.value })} className={`${inputCls} mt-1`} /></div>
        <div><label className="text-xs text-muted-foreground">Template</label>
          <select data-testid={`rule-template-${rule.key}`} disabled={!canEdit} value={r.template} onChange={(e) => setR({ ...r, template: e.target.value })} className={`${inputCls} mt-1`}>
            {templates.map((t) => <option key={t.key} value={t.key}>{titleize(t.key)}</option>)}</select></div>
        <div><label className="text-xs text-muted-foreground">Language</label>
          <select data-testid={`rule-language-${rule.key}`} disabled={!canEdit} value={r.language} onChange={(e) => setR({ ...r, language: e.target.value })} className={`${inputCls} mt-1`}>
            <option value="customer">Customer's language</option><option value="en">English</option><option value="fr">Français</option></select></div>
        <div><label className="text-xs text-muted-foreground">Channels</label>
          <div className="flex gap-3 mt-2">{["email", "sms"].map((ch) => (
            <label key={ch} className="flex items-center gap-1.5 text-xs"><input type="checkbox" data-testid={`rule-ch-${ch}-${rule.key}`} disabled={!canEdit} checked={r.channels.includes(ch)} onChange={() => toggleCh(ch)} />{ch.toUpperCase()}</label>
          ))}</div></div>
        {rule.key === "new_lead" && (
          <div><label className="text-xs text-muted-foreground">Assign to</label>
            <select data-testid="rule-assignee-new_lead" disabled={!canEdit} value={r.assign_to_user_id || ""} onChange={(e) => setR({ ...r, assign_to_user_id: e.target.value })} className={`${inputCls} mt-1`}>
              <option value="">Least-busy representative</option>{users.map((u) => <option key={u.id} value={u.id}>{u.first_name} {u.last_name}</option>)}</select></div>
        )}
        {Object.entries(r.params || {}).filter(([, v]) => typeof v !== "string").map(([k, v]) => (
          <div key={k}><label className="text-xs text-muted-foreground">{titleize(k)}</label>
            {typeof v === "boolean"
              ? <div className="mt-2"><input type="checkbox" data-testid={`rule-param-${k}-${rule.key}`} disabled={!canEdit} checked={v} onChange={(e) => setR({ ...r, params: { ...r.params, [k]: e.target.checked } })} /></div>
              : <input type="number" data-testid={`rule-param-${k}-${rule.key}`} disabled={!canEdit} value={v} onChange={(e) => setR({ ...r, params: { ...r.params, [k]: Number(e.target.value) } })} className={`${inputCls} mt-1`} />}
          </div>
        ))}
      </div>
      {canEdit && dirty && <button data-testid={`rule-save-${rule.key}`} onClick={() => save()} className="mt-3 text-xs bg-primary text-primary-foreground px-3 py-1.5 rounded-[4px] hover:opacity-90">{tr("Save changes")}</button>}
    </div>
  );
}

export default function Automations() {
  const { user } = useAuth();
  const canEdit = ["platform_admin", "dealership_admin", "dealership_manager"].includes(user?.role);
  const [rules, setRules] = useState(null);
  const [runs, setRuns] = useState([]);
  const [cfg, setCfg] = useState({ templates: [] });
  const [users, setUsers] = useState([]);
  const [status, setStatus] = useState("");
  const load = useCallback(() => {
    client.get("/automations").then((r) => setRules(r.data)).catch(() => { setRules([]); toast.error("Could not load automations"); });
    client.get("/automations/runs", { params: { status: status || undefined } }).then((r) => setRuns(r.data)).catch(() => setRuns([]));
  }, [status]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    client.get("/communications/config").then((r) => setCfg(r.data)).catch(() => {});
    client.get("/users", { params: { role: "dealership_representative", status: "active" } }).then((r) => setUsers(r.data)).catch(() => {});
  }, []);
  if (user && !canEdit && user.role !== "platform_support") return <Navigate to="/app/dashboard" replace />;
  const runNow = async () => { try { await client.post("/automations/process"); toast.success("Automation checks executed"); load(); } catch (e) { toast.error(e.response?.data?.detail || "Failed"); } };
  const retry = async (id) => { try { const { data } = await client.post(`/automations/runs/${id}/retry`); toast.success(`Retry: ${data.status}`); load(); } catch (e) { toast.error(e.response?.data?.detail || "Retry failed"); } };
  if (!rules) return <Loading />;
  return (
    <div data-testid="automations-page">
      <PageHeader title="Follow-up Automations" subtitle="Triggers, delays, templates and channels — runs every 15 minutes">
        {canEdit && <button data-testid="automations-run-now" onClick={runNow} className="flex items-center gap-2 bg-primary text-primary-foreground px-4 py-2 rounded-[4px] text-sm font-semibold hover:opacity-90"><Play size={14} weight="fill" /> Run checks now</button>}
      </PageHeader>
      <div className="space-y-3 mb-8">
        {rules.map((r) => <RuleCard key={r.id + r.updated_at} rule={r} templates={cfg.templates} users={users} canEdit={canEdit} onSaved={load} />)}
      </div>
      <div className="flex items-center justify-between mb-3">
        <h2 className="font-head font-bold text-lg">Execution history</h2>
        <select data-testid="runs-filter-status" value={status} onChange={(e) => setStatus(e.target.value)} className={`${inputCls} w-auto`}>
          <option value="">All</option>{["success", "failed", "scheduled", "skipped"].map((s) => <option key={s} value={s}>{titleize(s)}</option>)}
        </select>
      </div>
      <div className="border border-border rounded-[4px] bg-card p-4">
        {runs.length === 0 ? <div className="text-sm text-muted-foreground text-center py-8">No executions yet.</div> : (
          <Table testid="runs-table" head={["Created", "Automation", "Kind", "Status", "Run at", "Actions / error", ""]} rows={runs.map((x) => [
            <span className="text-xs font-mono-plex whitespace-nowrap">{fmtDate(x.created_at)}</span>, titleize(x.rule_key), titleize(x.kind), <Pill s={x.status} />,
            <span className="text-xs font-mono-plex">{fmtDate(x.run_at)}</span>,
            <div className="text-xs max-w-md">{(x.actions || []).join(" · ")}{x.error && <div className="text-red-400">{x.error}</div>}</div>,
            x.status === "failed" && canEdit ? <button data-testid={`run-retry-${x.id}`} onClick={() => retry(x.id)} className="text-xs text-primary flex items-center gap-1"><ArrowClockwise size={12} /> Retry</button> : null,
          ])} />
        )}
      </div>
    </div>
  );
}
