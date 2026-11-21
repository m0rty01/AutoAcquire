import { useState } from "react";
import client from "@/lib/api";
import { toast } from "sonner";
import { Copy } from "@phosphor-icons/react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { inputCls } from "@/components/profile/shared";

export function UserDialog({ mode, user, meta, groups, orgs, isPlatform, onClose, onSaved }) {
  const [f, setF] = useState({ first_name: user?.first_name || "", last_name: user?.last_name || "", email: user?.email || "",
    phone: user?.phone || "", role: user?.role || meta.manageable.find((r) => r === "dealership_representative") || meta.manageable[0],
    dealer_group_id: user?.dealer_group_id || "", organization_id: user?.organization_id || "" });
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const roles = meta.roles.filter((r) => meta.manageable.includes(r.value));
  const save = async () => {
    const body = { ...f, dealer_group_id: f.dealer_group_id || null, phone: f.phone || null };
    if (!isPlatform || !body.organization_id) delete body.organization_id;
    try {
      if (mode === "create") { const { data } = await client.post("/users", body); toast.success("User created"); onSaved(data); }
      else { delete body.email; await client.patch(`/users/${user.id}`, body); toast.success("User updated"); onSaved(); }
    } catch (e) { toast.error(typeof e.response?.data?.detail === "string" ? e.response.data.detail : "Please check the form"); }
  };
  const inp = (k, l, type = "text") => (
    <div><label className="text-xs text-muted-foreground">{l}</label>
      <input data-testid={`user-form-${k}`} type={type} value={f[k]} onChange={set(k)} disabled={k === "email" && mode === "edit"} className={`${inputCls} mt-1 disabled:opacity-60`} /></div>
  );
  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="dark bg-card text-foreground border-border" data-testid="user-dialog">
        <DialogHeader><DialogTitle>{mode === "create" ? "New user" : `Edit ${user.email}`}</DialogTitle></DialogHeader>
        <div className="grid grid-cols-2 gap-3">
          {inp("first_name", "First name")}{inp("last_name", "Last name")}
          {inp("email", "Email", "email")}{inp("phone", "Phone")}
          <div><label className="text-xs text-muted-foreground">Role</label>
            <select data-testid="user-form-role" value={f.role} onChange={set("role")} className={`${inputCls} mt-1`}>
              {roles.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}</select></div>
          <div><label className="text-xs text-muted-foreground">Dealer group</label>
            <select data-testid="user-form-dealer-group" value={f.dealer_group_id} onChange={set("dealer_group_id")} className={`${inputCls} mt-1`}>
              <option value="">None</option>{groups.map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}</select></div>
          {isPlatform && (
            <div className="col-span-2"><label className="text-xs text-muted-foreground">Dealership</label>
              <select data-testid="user-form-organization" value={f.organization_id} onChange={set("organization_id")} className={`${inputCls} mt-1`}>
                <option value="">My dealership</option>{orgs.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}</select></div>
          )}
        </div>
        {mode === "create" && <p className="text-xs text-muted-foreground">No password is set by you. The user receives a secure one-time link to choose their own password.</p>}
        <button data-testid="user-form-save" onClick={save} className="mt-1 bg-primary text-primary-foreground rounded-[4px] py-2 text-sm font-semibold hover:opacity-90">{mode === "create" ? "Create user" : "Save changes"}</button>
      </DialogContent>
    </Dialog>
  );
}

export function LinkDialog({ title, url, hours, email, onClose }) {
  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="dark bg-card text-foreground border-border" data-testid="link-dialog">
        <DialogHeader><DialogTitle>{title}</DialogTitle></DialogHeader>
        <p className="text-sm text-muted-foreground">
          A one-time link for <b className="text-foreground">{email}</b> was issued (valid {hours}h). The email could not be delivered (email provider not connected or failed) — share this link with the user securely. It is shown only once.
        </p>
        <div className="flex gap-2">
          <input data-testid="link-dialog-url" readOnly value={url} className={`${inputCls} font-mono-plex text-xs`} />
          <button data-testid="link-dialog-copy" onClick={() => { navigator.clipboard.writeText(url); toast.success("Link copied"); }} className="bg-secondary hover:bg-accent px-3 rounded-[4px]"><Copy size={16} /></button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
