import { useEffect, useState } from "react";
import client from "@/lib/api";
import { PageHeader, Loading } from "@/components/Bits";
import { toast } from "sonner";
import { MagnifyingGlass, Clock, Warning, X, Note, PaperPlaneRight } from "@phosphor-icons/react";

const LABELS = {
  new_lead: "New Lead", contact_required: "Contact Required", contacted: "Contacted", qualified: "Qualified",
  vehicle_matched: "Vehicle Matched", appointment_requested: "Appt Requested", appointment_confirmed: "Appt Confirmed",
  test_drive_scheduled: "Test Drive Scheduled", test_drive_completed: "Test Drive Done", negotiation: "Negotiation",
  sale_reported: "Sale Reported", sale_verified: "Sale Verified", lost: "Lost",
};

export default function Pipeline() {
  const [data, setData] = useState(null);
  const [search, setSearch] = useState("");
  const [drag, setDrag] = useState(null);
  const [active, setActive] = useState(null);
  const [acts, setActs] = useState([]);
  const [note, setNote] = useState("");

  const load = () => client.get("/pipeline", { params: { search: search || undefined } }).then((r) => setData(r.data));
  useEffect(() => { const t = setTimeout(load, 300); return () => clearTimeout(t); }, [search]);

  const move = async (leadId, stage) => {
    try {
      await client.patch(`/leads/${leadId}/stage`, { stage });
      toast.success(`Moved to ${LABELS[stage]}`);
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "Move failed"); }
  };

  const openCard = async (card) => {
    setActive(card); setActs([]);
    try { const { data } = await client.get(`/leads/${card.id}/activities`); setActs(data); } catch {}
  };
  const addNote = async () => {
    if (!note.trim()) return;
    try {
      await client.post(`/leads/${active.id}/notes`, { content: note });
      setNote(""); const { data } = await client.get(`/leads/${active.id}/activities`); setActs(data); load();
    } catch { toast.error("Failed to add note"); }
  };

  if (!data) return <Loading />;

  return (
    <div>
      <PageHeader title="Sales Pipeline" subtitle="Drag leads across stages">
        <div className="relative">
          <MagnifyingGlass size={15} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <input data-testid="pipeline-search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search customers…"
            className="pl-8 pr-3 py-2 text-sm rounded-[4px] border border-input bg-card outline-none focus:border-primary w-56" />
        </div>
      </PageHeader>

      <div className="flex gap-3 overflow-x-auto pb-4" data-testid="pipeline-board">
        {data.stages.map((stage) => {
          const cards = data.columns[stage] || [];
          return (
            <div key={stage} className="shrink-0 w-64" onDragOver={(e) => e.preventDefault()}
              onDrop={() => { if (drag && _stageChanged(drag, stage)) move(drag.id, stage); setDrag(null); }}>
              <div className="flex items-center justify-between mb-2 px-1">
                <span className="text-xs font-mono-plex uppercase tracking-wider text-muted-foreground">{LABELS[stage]}</span>
                <span className="text-xs text-muted-foreground bg-secondary rounded-full px-1.5">{cards.length}</span>
              </div>
              <div className="space-y-2 min-h-[60px]" data-testid={`col-${stage}`}>
                {cards.map((c) => (
                  <div key={c.id} data-testid="pipeline-card" draggable onDragStart={() => setDrag({ id: c.id, stage })}
                    onClick={() => openCard(c)}
                    className="bg-card border border-border rounded-[4px] p-3 cursor-grab active:cursor-grabbing hover:border-primary/50 transition-colors">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium text-sm truncate">{c.customer_name}</span>
                      {c.score != null && <span className="text-[11px] font-mono-plex bg-primary/15 text-primary rounded px-1.5">{c.score}</span>}
                    </div>
                    {c.vehicle_label && <div className="text-xs text-muted-foreground mt-1 truncate">{c.vehicle_label}</div>}
                    {c.dealer_group_name && <div className="text-[11px] text-muted-foreground mt-0.5">{c.dealer_group_name}</div>}
                    <div className="flex items-center gap-2 mt-2 text-[11px] text-muted-foreground font-mono-plex">
                      <Clock size={11} /> {c.age_days}d
                      {c.overdue && <span className="flex items-center gap-0.5 text-amber-400"><Warning size={11} weight="fill" /> {c.idle_days}d idle</span>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>

      {active && (
        <div className="fixed inset-0 z-50 flex justify-end bg-black/40" onClick={() => setActive(null)} data-testid="activity-drawer">
          <div className="w-full max-w-md bg-card h-full border-l border-border p-5 overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-1">
              <h3 className="font-head font-bold text-lg">{active.customer_name}</h3>
              <button onClick={() => setActive(null)} className="text-muted-foreground hover:text-foreground"><X size={20} /></button>
            </div>
            <div className="text-xs text-muted-foreground mb-4">{active.email || "—"} · {active.phone || "—"} · consent: {active.consent_status || "none"}</div>

            <div className="flex gap-2 mb-4">
              <input data-testid="note-input" value={note} onChange={(e) => setNote(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && addNote()} placeholder="Add a note…"
                className="flex-1 text-sm rounded-[4px] border border-input bg-background px-2 py-1.5 outline-none focus:border-primary" />
              <button data-testid="add-note-btn" onClick={addNote} className="bg-primary text-primary-foreground rounded-[4px] px-3 flex items-center"><PaperPlaneRight size={16} /></button>
            </div>

            <div className="text-xs font-mono-plex uppercase tracking-wider text-muted-foreground mb-2">Activity timeline</div>
            <div className="space-y-3">
              {acts.length === 0 ? <div className="text-sm text-muted-foreground">No activity yet.</div> : acts.map((a) => (
                <div key={a.id} data-testid="activity-item" className="flex gap-2 text-sm border-l-2 border-primary/30 pl-3">
                  {a.activity_type === "note" ? <Note size={15} className="text-primary mt-0.5 shrink-0" /> : <Clock size={15} className="text-muted-foreground mt-0.5 shrink-0" />}
                  <div>
                    <div className="font-medium">{a.activity_type.replace(/_/g, " ")}</div>
                    {a.details && <div className="text-muted-foreground">{a.details}</div>}
                    <div className="text-[11px] text-muted-foreground font-mono-plex mt-0.5">{a.actor} · {new Date(a.created_at).toLocaleString()}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function _stageChanged(drag, stage) { return drag.stage !== stage; }
