import { tr } from "@/lib/adminI18n";
import { useEffect, useState, useCallback } from "react";
import { Navigate } from "react-router-dom";
import client from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { PageHeader, Loading } from "@/components/Bits";
import { toast } from "sonner";
import { MagnifyingGlass, UserPlus } from "@phosphor-icons/react";
import { Pill, Table, fmtDate, inputCls } from "@/components/profile/shared";
import { UserDialog, LinkDialog } from "@/components/users/UserDialogs";

export default function UserManagement() {
  const { user: me } = useAuth();
  const [rows, setRows] = useState(null);
  const [meta, setMeta] = useState({ roles: [], manageable: [] });
  const [groups, setGroups] = useState([]);
  const [orgs, setOrgs] = useState([]);
  const [f, setF] = useState({ search: "", role: "", status: "", dealer_group_id: "", organization_id: "" });
  const [dialog, setDialog] = useState(null);
  const [link, setLink] = useState(null);
  const isPlatform = me?.role === "platform_admin";
  const allowed = ["platform_admin", "platform_support", "dealership_admin", "dealership_manager"].includes(me?.role);

  const load = useCallback(() => {
    const params = Object.fromEntries(Object.entries(f).filter(([, v]) => v));
    client.get("/users", { params }).then((r) => setRows(r.data)).catch(() => setRows([]));
  }, [f]);
  useEffect(() => { const t = setTimeout(load, 250); return () => clearTimeout(t); }, [load]);
  useEffect(() => {
    client.get("/users/roles").then((r) => setMeta(r.data));
    client.get("/dealer-groups").then((r) => setGroups(r.data)).catch(() => {});
    if (isPlatform) client.get("/platform/organizations").then((r) => setOrgs(r.data)).catch(() => {});
  }, [isPlatform]);

  if (me && !allowed) return <Navigate to="/app/dashboard" replace />;

  const act = async (u, action) => {
    if (action === "deactivate" && !window.confirm(`Deactivate ${u.email}? They will be signed out and unable to log in.`)) return;
    try {
      const { data } = await client.post(`/users/${u.id}/${action}`);
      if (action === "password-reset") {
        if (data.reset_url) setLink({ title: "Password reset link", url: data.reset_url, hours: data.expires_in_hours, email: u.email });
        else toast.success(`Reset email sent to ${u.email}`);
      }
      else toast.success(action === "deactivate" ? "Account deactivated" : "Account reactivated");
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "Action failed"); }
  };
  const can = (u) => meta.manageable.includes(u.role) && u.id !== me?.id;
  const sel = (k, opts, all) => (
    <select data-testid={`users-filter-${k}`} value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} className={`${inputCls} w-auto`}>
      <option value="">{all}</option>{opts.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
    </select>
  );

  return (
    <div data-testid="user-management">
      <PageHeader title="User Management" subtitle="Create, edit and control access for your team">
        {meta.manageable.length > 0 && (
          <button data-testid="create-user-btn" onClick={() => setDialog({ mode: "create" })}
            className="flex items-center gap-2 bg-primary text-primary-foreground px-4 py-2 rounded-[4px] text-sm font-semibold hover:opacity-90 transition-opacity">
            <UserPlus size={16} weight="bold" /> New user
          </button>
        )}
      </PageHeader>
      <div className="flex flex-wrap gap-2 mb-4">
        <div className="relative">
          <MagnifyingGlass size={15} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <input data-testid="users-search" value={f.search} onChange={(e) => setF({ ...f, search: e.target.value })} placeholder={tr("Search name or email…")} className={`${inputCls} pl-8 w-60`} />
        </div>
        {sel("role", meta.roles.map((r) => [r.value, r.label]), "All roles")}
        {sel("status", [["active", "Active"], ["invited", "Invited"], ["inactive", "Deactivated"]], "All statuses")}
        {groups.length > 0 && sel("dealer_group_id", groups.map((g) => [g.id, g.name]), "All dealer groups")}
        {isPlatform && sel("organization_id", orgs.map((o) => [o.id, o.name]), "All dealerships")}
      </div>
      {!rows ? <Loading /> : (
        <div className="border border-border rounded-[4px] bg-card p-4">
          <Table testid="users-table" head={["Name", "Email", "Role", "Dealership", "Dealer group", "Status", "Last login", ""]} rows={rows.map((u) => [
            <span data-testid={`user-row-${u.email}`} className="font-medium">{u.first_name} {u.last_name}</span>,
            <span className="text-muted-foreground">{u.email}</span>, u.role_label, u.organization_name || "—", u.dealer_group_name || "—",
            <Pill s={u.status} />, <span className="text-xs font-mono-plex">{u.last_login_at ? fmtDate(u.last_login_at) : "Never"}</span>,
            can(u) ? (
              <div className="flex gap-2 justify-end text-xs whitespace-nowrap">
                <button data-testid={`user-edit-${u.email}`} onClick={() => setDialog({ mode: "edit", user: u })} className="text-primary hover:underline">{tr("Edit")}</button>
                {u.status !== "inactive" && <button data-testid={`user-reset-${u.email}`} onClick={() => act(u, "password-reset")} className="hover:underline">{tr("Reset password")}</button>}
                {u.status === "inactive"
                  ? <button data-testid={`user-reactivate-${u.email}`} onClick={() => act(u, "reactivate")} className="text-emerald-400 hover:underline">{tr("Reactivate")}</button>
                  : <button data-testid={`user-deactivate-${u.email}`} onClick={() => act(u, "deactivate")} className="text-red-400 hover:underline">{tr("Deactivate")}</button>}
              </div>
            ) : <span className="text-xs text-muted-foreground">{u.id === me?.id ? "You" : ""}</span>,
          ])} />
          {rows.length === 0 && <div className="text-sm text-muted-foreground text-center py-8">No users match these filters.</div>}
        </div>
      )}
      {dialog && <UserDialog {...dialog} meta={meta} groups={groups} orgs={orgs} isPlatform={isPlatform}
        onClose={() => setDialog(null)} onSaved={(res) => { setDialog(null); load(); if (res && !res.setup_url) toast.success(`Invitation emailed to ${res.user.email}`); if (res?.setup_url) setLink({ title: "Account setup link", url: res.setup_url, hours: 72, email: res.user.email }); }} />}
      {link && <LinkDialog {...link} onClose={() => setLink(null)} />}
    </div>
  );
}
