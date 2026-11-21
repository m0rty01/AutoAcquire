import { useEffect, useState } from "react";
import client from "@/lib/api";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { inputCls } from "@/components/profile/shared";

const err = (e) => toast.error(e.response?.data?.detail || "Action failed");
const local = (iso) => (iso ? new Date(iso).toISOString().slice(0, 16) : "");

export function TDActions({ td, onDone }) {
  const post = async (action, body = {}) => {
    try { await client.post(`/test-drives/${td.id}/${action}`, body); toast.success(`Test drive ${action.replace("-", " ")}`); onDone(); } catch (e) { err(e); }
  };
  const ask = (q, def = "") => window.prompt(q, def);
  const btn = (key, label, fn, cls = "text-primary") => (
    <button key={key} data-testid={`td-${key}-${td.id}`} onClick={fn} className={`${cls} hover:underline`}>{label}</button>
  );
  const s = td.status;
  const items = [];
  if (["requested", "pending_confirmation"].includes(s)) {
    items.push(btn("confirm", "Confirm", () => post("confirm")));
    items.push(btn("decline", "Decline", () => { const r = ask("Reason for declining?"); if (r !== null) post("decline", { reason: r }); }, "text-red-400"));
  }
  if (["requested", "pending_confirmation", "confirmed"].includes(s)) {
    items.push(btn("reschedule", "Reschedule", () => { const t = ask("New date & time (YYYY-MM-DDTHH:MM)", local(td.scheduled_at)); if (t) post("reschedule", { time: new Date(t).toISOString() }); }, "text-foreground"));
    items.push(btn("cancel", "Cancel", () => { const r = ask("Cancellation reason?"); if (r !== null) post("cancel", { reason: r }); }, "text-muted-foreground"));
  }
  if (s === "confirmed") {
    items.push(btn("complete", "Complete", () => { const fb = ask("Customer feedback (optional)"); if (fb !== null) post("complete", { feedback: fb || null }); }, "text-emerald-400"));
    items.push(btn("no-show", "No-show", () => post("no-show"), "text-orange-400"));
  }
  items.push(btn("note", "Note", async () => {
    const n = ask("Representative note"); if (!n) return;
    try { await client.post(`/test-drives/${td.id}/notes`, { content: n }); toast.success("Note added"); onDone(); } catch (e) { err(e); }
  }, "text-muted-foreground"));
  return <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs">{items}</div>;
}

export function NewTestDrive({ onClose, onCreated, leadId }) {
  const [leads, setLeads] = useState([]);
  const [search, setSearch] = useState("");
  const [f, setF] = useState({ lead_id: leadId || "", time: "", notes: "" });
  useEffect(() => {
    if (leadId) return;
    const t = setTimeout(() => client.get("/leads", { params: { search: search || undefined, page_size: 30 } }).then((r) => setLeads(r.data.items)), 250);
    return () => clearTimeout(t);
  }, [search, leadId]);
  const save = async () => {
    if (!f.lead_id || !f.time) return toast.error("Choose a customer and a time");
    try { await client.post("/test-drives", { lead_id: f.lead_id, requested_time: new Date(f.time).toISOString(), notes: f.notes || null }); onCreated(); } catch (e) { err(e); }
  };
  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="dark bg-card text-foreground border-border" data-testid="new-td-dialog">
        <DialogHeader><DialogTitle>Request a test drive</DialogTitle></DialogHeader>
        {!leadId && (
          <>
            <input data-testid="new-td-search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search customer…" className={inputCls} />
            <select data-testid="new-td-lead" value={f.lead_id} onChange={(e) => setF({ ...f, lead_id: e.target.value })} className={inputCls}>
              <option value="">Select customer…</option>{leads.map((l) => <option key={l.id} value={l.id}>{l.seller_name} · {l.vehicle_label}</option>)}
            </select>
          </>
        )}
        <input data-testid="new-td-time" type="datetime-local" value={f.time} onChange={(e) => setF({ ...f, time: e.target.value })} className={inputCls} />
        <input data-testid="new-td-notes" value={f.notes} onChange={(e) => setF({ ...f, notes: e.target.value })} placeholder="Notes (optional)" className={inputCls} />
        <p className="text-xs text-muted-foreground">The vehicle is taken from the customer's referral or top inventory match.</p>
        <button data-testid="new-td-save" onClick={save} className="bg-primary text-primary-foreground rounded-[4px] py-2 text-sm font-semibold hover:opacity-90">Request test drive</button>
      </DialogContent>
    </Dialog>
  );
}
