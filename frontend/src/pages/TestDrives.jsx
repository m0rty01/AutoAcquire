import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import client from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { PageHeader, Loading, MetricTile } from "@/components/Bits";
import { toast } from "sonner";
import { Plus } from "@phosphor-icons/react";
import { Pill, Table, fmtDate, inputCls } from "@/components/profile/shared";
import { NewTestDrive, TDActions } from "@/components/testdrives/TDParts";

export default function TestDrives() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [rows, setRows] = useState(null);
  const [dash, setDash] = useState(null);
  const [groups, setGroups] = useState([]);
  const [reps, setReps] = useState([]);
  const [f, setF] = useState({ status: "", dealer_group_id: "", assigned_user_id: "", date_from: "", date_to: "" });
  const [creating, setCreating] = useState(false);
  const readOnly = user?.role === "platform_support";
  const isRep = user?.role === "dealership_representative";

  const load = useCallback(() => {
    const params = Object.fromEntries(Object.entries(f).filter(([, v]) => v));
    client.get("/test-drives", { params }).then((r) => setRows(r.data));
    const { status, ...d } = params;
    client.get("/test-drives/dashboard", { params: d }).then((r) => setDash(r.data));
  }, [f]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    client.get("/dealer-groups").then((r) => setGroups(r.data)).catch(() => {});
    if (!isRep) client.get("/users", { params: { status: "active" } }).then((r) => setReps(r.data.filter((u) => ["dealership_representative", "dealership_manager"].includes(u.role)))).catch(() => {});
  }, [isRep]);

  const sel = (k, opts, all) => (
    <select data-testid={`td-filter-${k}`} value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} className={`${inputCls} w-auto`}>
      <option value="">{all}</option>{opts.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
    </select>
  );
  if (!rows || !dash) return <Loading />;
  return (
    <div data-testid="test-drives-page">
      <PageHeader title="Test Drives" subtitle="Requests, confirmations, outcomes and conversion to sale">
        {!readOnly && <button data-testid="new-test-drive-btn" onClick={() => setCreating(true)} className="flex items-center gap-2 bg-primary text-primary-foreground px-4 py-2 rounded-[4px] text-sm font-semibold hover:opacity-90"><Plus size={14} weight="bold" /> New test drive</button>}
      </PageHeader>
      <div className="grid grid-cols-2 lg:grid-cols-6 gap-3 mb-6" data-testid="td-dashboard">
        <MetricTile label="Total" value={dash.total} />
        <MetricTile label="Upcoming" value={dash.upcoming} accent="text-primary" />
        <MetricTile label="Completed" value={dash.completed} accent="text-emerald-400" />
        <MetricTile label="Cancelled" value={dash.cancelled} />
        <MetricTile label="No-shows" value={dash.no_shows} accent="text-orange-400" />
        <MetricTile label="To sale" value={`${dash.conversion_rate}%`} hint={`${dash.converted_to_sale} of ${dash.completed} completed`} />
      </div>
      <div className="flex flex-wrap gap-2 mb-4">
        {sel("status", ["requested", "pending_confirmation", "confirmed", "completed", "cancelled", "no_show", "dealership_declined"].map((s) => [s, s.replace(/_/g, " ")]), "All statuses")}
        {groups.length > 0 && sel("dealer_group_id", groups.map((g) => [g.id, g.name]), "All dealerships")}
        {!isRep && sel("assigned_user_id", reps.map((u) => [u.id, `${u.first_name} ${u.last_name}`]), "All representatives")}
        <input data-testid="td-filter-date_from" type="date" value={f.date_from} onChange={(e) => setF({ ...f, date_from: e.target.value })} className={`${inputCls} w-auto`} />
        <input data-testid="td-filter-date_to" type="date" value={f.date_to} onChange={(e) => setF({ ...f, date_to: e.target.value })} className={`${inputCls} w-auto`} />
      </div>
      <div className="border border-border rounded-[4px] bg-card p-4">
        {rows.length === 0 ? <div className="text-sm text-muted-foreground text-center py-10">No test drives match these filters.</div> : (
          <Table testid="td-table" head={["When", "Customer", "Vehicle", "Dealership", "Representative", "Status", "Actions"]} rows={rows.map((t) => [
            <span className="text-xs font-mono-plex whitespace-nowrap">{fmtDate(t.scheduled_at)}</span>,
            <button className="text-primary hover:underline text-left" onClick={() => navigate(`/app/customers/${t.lead_id}?tab=test-drives`)}>{t.customer_name}</button>,
            t.vehicle_label || "—", t.dealer_group_name || "—", t.representative || "Unassigned",
            <div><Pill s={t.status} />{t.customer_feedback && <div className="text-[11px] text-muted-foreground mt-1 max-w-[200px]">“{t.customer_feedback}”</div>}</div>,
            readOnly ? null : <TDActions td={t} onDone={load} />,
          ])} />
        )}
      </div>
      {creating && <NewTestDrive onClose={() => setCreating(false)} onCreated={() => { setCreating(false); load(); toast.success("Test drive requested"); }} />}
    </div>
  );
}
