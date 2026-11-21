import { tr } from "@/lib/adminI18n";
import { useEffect, useState } from "react";
import client from "@/lib/api";
import { toast } from "sonner";
import { titleize } from "@/components/ui/badges";
import { Card, inputCls, fmtDate } from "./shared";

const err = (e) => toast.error(e.response?.data?.detail || "Action failed");

function AssignStage({ p, reload, canAssign, readOnly }) {
  const [users, setUsers] = useState([]);
  useEffect(() => { if (canAssign) client.get("/users", { params: { status: "active" } }).then((r) => setUsers(r.data)).catch(() => {}); }, [canAssign]);
  const assign = async (uid) => { try { await client.post(`/leads/${p.lead.id}/assign`, { user_id: uid || null }); toast.success("Assignment updated"); reload(); } catch (e) { err(e); } };
  const stage = async (s) => {
    let lost_reason;
    if (s === "lost") { lost_reason = window.prompt("Reason the lead was lost?") || undefined; }
    try { await client.patch(`/leads/${p.lead.id}/stage`, { stage: s, lost_reason }); toast.success(`Moved to ${titleize(s)}`); reload(); } catch (e) { err(e); }
  };
  return (
    <div className="space-y-3">
      <div>
        <label className="text-[11px] font-mono-plex uppercase tracking-wider text-muted-foreground">{tr("Sales representative")}</label>
        {canAssign ? (
          <select data-testid="assign-select" value={p.lead.assigned_user_id || ""} onChange={(e) => assign(e.target.value)} className={`${inputCls} mt-1`}>
            <option value="">{tr("Unassigned")}</option>
            {users.filter((u) => ["dealership_representative", "dealership_manager"].includes(u.role) || u.id === p.lead.assigned_user_id).map((u) => <option key={u.id} value={u.id}>{u.first_name} {u.last_name} · {u.role_label}</option>)}
          </select>
        ) : <div className="text-sm mt-1">{p.overview.assigned_user?.name || "Unassigned"}</div>}
      </div>
      <div>
        <label className="text-[11px] font-mono-plex uppercase tracking-wider text-muted-foreground">{tr("Pipeline stage")}</label>
        <select data-testid="stage-select" disabled={readOnly} value={p.stage} onChange={(e) => stage(e.target.value)} className={`${inputCls} mt-1`}>
          {p.stages.map((s) => <option key={s} value={s}>{titleize(s)}</option>)}
        </select>
      </div>
    </div>
  );
}

function FollowUps({ p, reload }) {
  const [due, setDue] = useState("");
  const [note, setNote] = useState("");
  const add = async () => {
    if (!due) return toast.error("Pick a date and time");
    try { await client.post(`/leads/${p.lead.id}/follow-ups`, { due_at: new Date(due).toISOString(), note }); setDue(""); setNote(""); toast.success("Follow-up scheduled"); reload(); } catch (e) { err(e); }
  };
  const done = async (id) => { try { await client.post(`/follow-ups/${id}/complete`); toast.success("Follow-up completed"); reload(); } catch (e) { err(e); } };
  const open = p.follow_ups.filter((f) => f.status === "open");
  return (
    <div className="space-y-2">
      <input data-testid="followup-due" type="datetime-local" value={due} onChange={(e) => setDue(e.target.value)} className={inputCls} />
      <div className="flex gap-2">
        <input data-testid="followup-note" value={note} onChange={(e) => setNote(e.target.value)} placeholder={tr("What to do…")} className={inputCls} />
        <button data-testid="followup-add-btn" onClick={add} className="text-xs bg-secondary hover:bg-accent px-3 rounded-[4px] whitespace-nowrap">{tr("Schedule")}</button>
      </div>
      {open.map((f) => (
        <div key={f.id} data-testid="followup-item" className="flex items-center justify-between gap-2 text-xs border-l-2 border-amber-500/60 pl-2">
          <div><div>{fmtDate(f.due_at)}</div>{f.note && <div className="text-muted-foreground">{f.note}</div>}</div>
          <button data-testid="followup-done-btn" onClick={() => done(f.id)} className="text-primary hover:underline shrink-0">{tr("Done")}</button>
        </div>
      ))}
    </div>
  );
}

function AddNote({ p, reload }) {
  const [note, setNote] = useState("");
  const add = async () => {
    if (!note.trim()) return;
    try { await client.post(`/leads/${p.lead.id}/notes`, { content: note }); setNote(""); toast.success("Note added"); reload(); } catch (e) { err(e); }
  };
  return (
    <div className="flex gap-2">
      <input data-testid="profile-note-input" value={note} onChange={(e) => setNote(e.target.value)} onKeyDown={(e) => e.key === "Enter" && add()} placeholder={tr("Internal note…")} className={inputCls} />
      <button data-testid="profile-note-btn" onClick={add} className="text-xs bg-primary text-primary-foreground px-3 rounded-[4px]">{tr("Add")}</button>
    </div>
  );
}

export function ProfileActions({ p, reload, role }) {
  const readOnly = role === "platform_support";
  const canAssign = ["platform_admin", "dealership_admin", "dealership_manager"].includes(role);
  return (
    <div className="space-y-4" data-testid="profile-actions">
      <Card title="Ownership & stage"><AssignStage p={p} reload={reload} canAssign={canAssign} readOnly={readOnly} /></Card>
      {!readOnly && <Card title="Follow-ups"><FollowUps p={p} reload={reload} /></Card>}
      {!readOnly && <Card title="Add note"><AddNote p={p} reload={reload} /></Card>}
    </div>
  );
}
