import { useEffect, useState } from "react";
import client from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { PageHeader, Loading } from "@/components/Bits";
import { titleize } from "@/components/ui/badges";
import { toast } from "sonner";

const TABS = ["Profile", "Users", "Qualification Rules", "Availability", "AI Behavior", "Audit Log"];

export default function Settings() {
  const { user } = useAuth();
  const [tab, setTab] = useState("Profile");
  return (
    <div>
      <PageHeader title="Settings" subtitle="Configure your dealership workspace." />
      <div className="flex gap-1 border-b border-border mb-6 overflow-x-auto">
        {TABS.map((t) => (
          <button key={t} data-testid={`tab-${t.toLowerCase().replace(/ /g, "-")}`} onClick={() => setTab(t)}
            className={`px-4 py-2.5 text-sm font-medium whitespace-nowrap border-b-2 transition-colors duration-200 ${tab === t ? "border-primary text-foreground" : "border-transparent text-muted-foreground hover:text-foreground"}`}>
            {t}
          </button>
        ))}
      </div>
      {tab === "Profile" && <Profile />}
      {tab === "Users" && <Users canManage={user?.role === "dealership_admin"} />}
      {tab === "Qualification Rules" && <Rules canManage={user?.role === "dealership_admin"} />}
      {tab === "Availability" && <Availability />}
      {tab === "AI Behavior" && <AIBehavior />}
      {tab === "Audit Log" && <AuditLog />}
    </div>
  );
}

function Card({ children }) { return <div className="border border-border rounded-[4px] bg-card p-5 max-w-2xl">{children}</div>; }

function Profile() {
  const [data, setData] = useState(null);
  useEffect(() => { client.get("/organizations/current").then((r) => setData(r.data)); }, []);
  if (!data) return <Loading />;
  const { organization: o, location: l } = data;
  return (
    <Card>
      <h3 className="font-head font-bold tracking-tight mb-4">Dealership profile</h3>
      <dl className="grid grid-cols-2 gap-4 text-sm">
        {[["Name", o.name], ["Slug", o.slug], ["Country", o.country], ["Time zone", o.time_zone], ["Plan", titleize(o.plan)],
          ["Location", l?.name], ["Address", l?.address_line_1], ["City", `${l?.city || ""}, ${l?.province_state || ""}`],
          ["Phone", l?.phone], ["Service radius", l?.service_radius_km ? `${l.service_radius_km} km` : "—"]].map(([k, v]) => (
          <div key={k}><dt className="text-xs font-mono-plex uppercase tracking-wide text-muted-foreground">{k}</dt><dd className="mt-0.5">{v || "—"}</dd></div>
        ))}
      </dl>
      <div className="mt-4 pt-4 border-t border-border text-sm">
        <span className="text-muted-foreground">Public seller URL: </span>
        <span className="font-mono-plex text-primary">/sell/{o.slug}</span>
      </div>
    </Card>
  );
}

function Users({ canManage }) {
  const [users, setUsers] = useState(null);
  const [form, setForm] = useState({ role: "dealership_representative" });
  const load = () => client.get("/users").then((r) => setUsers(r.data));
  useEffect(() => { load(); }, []);
  const invite = async () => {
    try {
      const { data } = await client.post("/users/invite", form);
      toast.success(`Invited. Temp password: ${data.temp_password}`); load();
      setForm({ role: "dealership_representative" });
    } catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
  };
  if (!users) return <Loading />;
  return (
    <div className="space-y-4">
      {canManage && (
        <Card>
          <h3 className="font-head font-bold tracking-tight mb-3">Invite user</h3>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            <input data-testid="invite-fn" placeholder="First name" value={form.first_name ?? ""} onChange={(e) => setForm({ ...form, first_name: e.target.value })} className="rounded-[4px] border border-input bg-card px-2 py-1.5 text-sm" />
            <input data-testid="invite-ln" placeholder="Last name" value={form.last_name ?? ""} onChange={(e) => setForm({ ...form, last_name: e.target.value })} className="rounded-[4px] border border-input bg-card px-2 py-1.5 text-sm" />
            <input data-testid="invite-email" placeholder="Email" value={form.email ?? ""} onChange={(e) => setForm({ ...form, email: e.target.value })} className="rounded-[4px] border border-input bg-card px-2 py-1.5 text-sm" />
            <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })} className="rounded-[4px] border border-input bg-card px-2 py-1.5 text-sm">
              <option value="dealership_manager">Manager</option>
              <option value="dealership_representative">Representative</option>
              <option value="dealership_admin">Admin</option>
            </select>
          </div>
          <button data-testid="invite-btn" onClick={invite} className="mt-3 bg-primary text-primary-foreground px-4 py-2 rounded-[4px] text-sm font-semibold hover:opacity-90 transition-opacity duration-200">Send invite</button>
        </Card>
      )}
      <Card>
        <table className="w-full text-sm">
          <thead><tr className="text-left text-xs font-mono-plex uppercase tracking-wider text-muted-foreground border-b border-border"><th className="pb-2">Name</th><th className="pb-2">Email</th><th className="pb-2">Role</th></tr></thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id} className="border-b border-border last:border-0"><td className="py-2">{u.first_name} {u.last_name}</td><td className="py-2 text-muted-foreground">{u.email}</td><td className="py-2">{titleize(u.role)}</td></tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}

function Rules({ canManage }) {
  const [rules, setRules] = useState(null);
  const load = () => client.get("/qualification-rules").then((r) => setRules(r.data));
  useEffect(() => { load(); }, []);
  const toggle = async (r) => { await client.patch(`/qualification-rules/${r.id}`, { active: !r.active }); load(); };
  if (!rules) return <Loading />;
  return (
    <div className="space-y-3 max-w-3xl">
      {rules.map((r) => (
        <div key={r.id} className="border border-border rounded-[4px] bg-card p-4 flex items-center justify-between" data-testid={`rule-${r.id}`}>
          <div>
            <div className="font-medium">{r.name}</div>
            <div className="text-xs font-mono-plex text-muted-foreground mt-1">{r.field_name} {r.operator.replace(/_/g, " ")} {JSON.stringify(r.comparison_value)} → fail: {titleize(r.failure_result)} ({r.score_adjustment})</div>
          </div>
          {canManage && (
            <button data-testid={`rule-toggle-${r.id}`} onClick={() => toggle(r)} className={`text-xs px-3 py-1.5 rounded-[4px] transition-colors duration-200 ${r.active ? "bg-green-500/15 text-green-400" : "bg-secondary text-muted-foreground"}`}>
              {r.active ? "Active" : "Inactive"}
            </button>
          )}
        </div>
      ))}
    </div>
  );
}

function Availability() {
  const [rows, setRows] = useState(null);
  useEffect(() => { client.get("/availability").then((r) => setRows(r.data)); }, []);
  if (!rows) return <Loading />;
  return (
    <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3 max-w-3xl">
      {rows.map((a) => (
        <div key={a.id} className="border border-border rounded-[4px] bg-card p-4">
          <div className="font-medium capitalize">{a.day_of_week}</div>
          <div className="text-sm font-mono-plex text-muted-foreground">{a.start_time}–{a.end_time}</div>
          <div className="text-xs text-muted-foreground mt-1">{a.duration_minutes}min · {titleize(a.appointment_type)}</div>
        </div>
      ))}
    </div>
  );
}

function AIBehavior() {
  const [data, setData] = useState(null);
  useEffect(() => { client.get("/organizations/current").then((r) => setData(r.data)); }, []);
  if (!data) return <Loading />;
  const policies = data.organization.ai_policies || [];
  return (
    <Card>
      <h3 className="font-head font-bold tracking-tight mb-1">AI policies</h3>
      <p className="text-sm text-muted-foreground mb-4">Guardrails the AI assistant follows in every conversation.</p>
      <ul className="space-y-2">
        {policies.map((p, i) => (
          <li key={i} className="flex items-start gap-2 text-sm"><span className="text-primary mt-1">▪</span> {p}</li>
        ))}
      </ul>
    </Card>
  );
}

function AuditLog() {
  const [logs, setLogs] = useState(null);
  useEffect(() => { client.get("/audit-logs").then((r) => setLogs(r.data)).catch(() => setLogs([])); }, []);
  if (!logs) return <Loading />;
  return (
    <div className="border border-border rounded-[4px] bg-card overflow-x-auto max-w-4xl">
      <table className="w-full text-sm">
        <thead><tr className="text-left text-xs font-mono-plex uppercase tracking-wider text-muted-foreground border-b border-border"><th className="p-3">Action</th><th className="p-3">Entity</th><th className="p-3">Actor</th><th className="p-3">When</th></tr></thead>
        <tbody>
          {logs.map((l) => (
            <tr key={l.id} className="border-b border-border last:border-0"><td className="p-3">{titleize(l.action)}</td><td className="p-3 text-muted-foreground">{l.entity_type}</td><td className="p-3 text-muted-foreground">{l.actor_type}</td><td className="p-3 font-mono-plex text-muted-foreground text-xs">{new Date(l.created_at).toLocaleString()}</td></tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
