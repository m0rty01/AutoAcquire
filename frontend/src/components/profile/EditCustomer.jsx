import { useState } from "react";
import client from "@/lib/api";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { inputCls } from "./shared";

const FIELDS = [["first_name", "First name"], ["last_name", "Last name"], ["email", "Email"], ["phone", "Phone"], ["city", "City"], ["province_state", "Province"]];

export function EditCustomer({ p, open, onClose, reload }) {
  const c = p.customer;
  const [f, setF] = useState(() => Object.fromEntries([...FIELDS.map(([k]) => [k, c[k] || ""]), ["preferred_language", p.overview.preferred_language], ["preferred_contact_method", c.preferred_contact_method || ""]]));
  const save = async () => {
    const body = Object.fromEntries(Object.entries(f).filter(([k, v]) => v !== "" && v !== (k === "preferred_language" ? p.overview.preferred_language : c[k] || "")));
    try { await client.patch(`/leads/${p.lead.id}/customer`, body); toast.success("Customer updated"); onClose(); reload(); }
    catch (e) { toast.error(e.response?.data?.detail || "Update failed"); }
  };
  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="dark bg-card text-foreground border-border" data-testid="edit-customer-dialog">
        <DialogHeader><DialogTitle>Edit customer</DialogTitle></DialogHeader>
        <div className="grid grid-cols-2 gap-3">
          {FIELDS.map(([k, l]) => (
            <div key={k}><label className="text-xs text-muted-foreground">{l}</label>
              <input data-testid={`edit-${k}`} value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} className={`${inputCls} mt-1`} /></div>
          ))}
          <div><label className="text-xs text-muted-foreground">Language</label>
            <select data-testid="edit-language" value={f.preferred_language} onChange={(e) => setF({ ...f, preferred_language: e.target.value })} className={`${inputCls} mt-1`}>
              <option value="en">English</option><option value="fr">Français</option></select></div>
          <div><label className="text-xs text-muted-foreground">Contact method</label>
            <select data-testid="edit-contact-method" value={f.preferred_contact_method} onChange={(e) => setF({ ...f, preferred_contact_method: e.target.value })} className={`${inputCls} mt-1`}>
              <option value="">—</option><option value="phone">Phone</option><option value="sms">SMS</option><option value="email">Email</option></select></div>
        </div>
        <button data-testid="edit-customer-save" onClick={save} className="mt-2 bg-primary text-primary-foreground rounded-[4px] py-2 text-sm font-semibold hover:opacity-90">Save changes</button>
      </DialogContent>
    </Dialog>
  );
}
