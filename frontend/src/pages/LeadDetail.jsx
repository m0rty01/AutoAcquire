import { useEffect, useState, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import client from "@/lib/api";
import { Loading } from "@/components/Bits";
import { ScoreBadge, StatusBadge, titleize } from "@/components/ui/badges";
import { toast } from "sonner";
import {
  ArrowLeft, PaperPlaneRight, PencilSimple, ArrowsClockwise, Handshake, Robot, Note,
} from "@phosphor-icons/react";

const CAR_IMG = "https://images.unsplash.com/photo-1760312206290-d884595398d9?crop=entropy&cs=srgb&fm=jpg&q=85&w=400";

export default function LeadDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [d, setD] = useState(null);
  const [msg, setMsg] = useState("");
  const [note, setNote] = useState("");
  const [editVeh, setEditVeh] = useState(false);
  const [vehForm, setVehForm] = useState({});
  const endRef = useRef(null);

  const load = () => client.get(`/leads/${id}`).then((r) => { setD(r.data); setVehForm(r.data.vehicle || {}); });
  useEffect(() => { load(); }, [id]);
  useEffect(() => { endRef.current?.scrollIntoView(); }, [d?.messages?.length]);

  if (!d) return <Loading />;
  const { lead, seller, vehicle, conversation, messages, score, matches, appointment, notes, activity } = d;
  const aiActive = conversation?.ai_active;

  const act = async (fn, ok) => { try { await fn(); toast.success(ok); load(); } catch (e) { toast.error("Action failed"); } };

  const sendMsg = async () => {
    if (!msg.trim()) return;
    const text = msg; setMsg("");
    await client.post(`/leads/${id}/messages`, { content: text });
    load();
  };
  const addNote = async () => {
    if (!note.trim()) return;
    await client.post(`/leads/${id}/notes`, { content: note });
    setNote(""); load(); toast.success("Note added");
  };
  const saveVeh = async () => {
    const fields = {};
    ["year", "make", "model", "trim", "mileage", "condition", "ownership_status", "asking_price", "accident_history"].forEach((k) => {
      if (vehForm[k] !== undefined && vehForm[k] !== null && vehForm[k] !== "") {
        fields[k] = ["year", "mileage", "asking_price"].includes(k) ? Number(vehForm[k]) : vehForm[k];
      }
    });
    await client.patch(`/leads/${id}/vehicle`, { fields });
    setEditVeh(false); load(); toast.success("Vehicle updated & score recalculated");
  };

  return (
    <div>
      <button onClick={() => navigate("/app/leads")} className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground mb-4 transition-colors duration-200">
        <ArrowLeft size={16} /> Back to leads
      </button>

      <div className="flex flex-wrap items-start justify-between gap-4 mb-6">
        <div>
          <h1 className="font-head font-black text-2xl sm:text-3xl tracking-tight">{seller?.first_name ? `${seller.first_name} ${seller.last_name || ""}` : "Unknown seller"}</h1>
          <div className="flex items-center gap-2 mt-2 flex-wrap">
            <ScoreBadge score={lead.score} band={lead.score_band} />
            <StatusBadge status={lead.status} />
            <span className="text-xs font-mono-plex text-muted-foreground border border-border rounded-[4px] px-2 py-0.5">{titleize(lead.qualification_status)}</span>
          </div>
        </div>
        <div className="flex gap-2">
          <button data-testid="recalc-score-btn" onClick={() => act(() => client.post(`/leads/${id}/recalculate-score`), "Score recalculated")}
            className="flex items-center gap-1.5 text-xs bg-secondary hover:bg-accent px-3 py-2 rounded-[4px] transition-colors duration-200">
            <ArrowsClockwise size={14} /> Recalc score
          </button>
          <button data-testid="run-match-btn" onClick={() => act(() => client.post(`/leads/${id}/run-inventory-match`), "Inventory matched")}
            className="flex items-center gap-1.5 text-xs bg-secondary hover:bg-accent px-3 py-2 rounded-[4px] transition-colors duration-200">
            <Handshake size={14} /> Match inventory
          </button>
        </div>
      </div>

      <div className="grid lg:grid-cols-3 gap-4">
        {/* left column */}
        <div className="lg:col-span-2 space-y-4">
          {/* conversation */}
          <Card>
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-head font-bold tracking-tight flex items-center gap-2"><Robot size={18} weight="bold" className="text-primary" /> Conversation</h3>
              <div className="flex items-center gap-2">
                <span className={`text-xs font-mono-plex px-2 py-0.5 rounded-[4px] border ${aiActive ? "text-green-400 border-green-500/30 bg-green-500/10" : "text-orange-400 border-orange-500/30 bg-orange-500/10"}`}>
                  {aiActive ? "AI ACTIVE" : "HUMAN ACTIVE"}
                </span>
                {aiActive ? (
                  <button data-testid="takeover-btn" onClick={() => act(() => client.post(`/leads/${id}/takeover`), "You've taken over")}
                    className="text-xs bg-primary text-primary-foreground px-3 py-1.5 rounded-[4px] hover:opacity-90 transition-opacity duration-200">Take over</button>
                ) : (
                  <button data-testid="resume-ai-btn" onClick={() => act(() => client.post(`/leads/${id}/resume-ai`), "AI resumed")}
                    className="text-xs bg-secondary hover:bg-accent px-3 py-1.5 rounded-[4px] transition-colors duration-200">Resume AI</button>
                )}
              </div>
            </div>
            <div className="max-h-96 overflow-y-auto space-y-3 pr-1">
              {messages.map((m) => (
                <div key={m.id} className={`flex ${m.sender_type === "seller" ? "justify-start" : "justify-end"}`}>
                  <div className={`max-w-[75%] rounded-[8px] px-3 py-2 text-sm leading-relaxed border ${
                    m.sender_type === "seller" ? "bg-secondary border-border" :
                    m.sender_type === "human_agent" ? "bg-orange-500/10 border-orange-500/25" : "bg-primary/10 border-primary/25"}`}>
                    <div className="text-[10px] font-mono-plex uppercase tracking-wider opacity-60 mb-0.5">
                      {m.sender_type === "seller" ? "Seller" : m.sender_type === "human_agent" ? "You" : "AI"}
                    </div>
                    {m.content}
                  </div>
                </div>
              ))}
              <div ref={endRef} />
            </div>
            {!aiActive && (
              <div className="flex gap-2 mt-3">
                <input data-testid="manual-message-input" value={msg} onChange={(e) => setMsg(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && sendMsg()} placeholder="Type a message to the seller…"
                  className="flex-1 rounded-[4px] border border-input bg-card px-3 py-2 text-sm outline-none focus:border-primary transition-colors duration-200" />
                <button data-testid="manual-message-send" onClick={sendMsg} className="bg-primary text-primary-foreground px-3 rounded-[4px] hover:opacity-90 transition-opacity duration-200">
                  <PaperPlaneRight size={18} weight="fill" />
                </button>
              </div>
            )}
          </Card>

          {/* vehicle */}
          <Card>
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-head font-bold tracking-tight">Vehicle information</h3>
              <button data-testid="edit-vehicle-btn" onClick={() => setEditVeh(!editVeh)} className="flex items-center gap-1 text-xs text-primary hover:underline">
                <PencilSimple size={14} /> {editVeh ? "Cancel" : "Correct"}
              </button>
            </div>
            {editVeh ? (
              <div className="grid grid-cols-2 gap-3">
                {[["year", "Year"], ["make", "Make"], ["model", "Model"], ["trim", "Trim"], ["mileage", "Mileage"], ["asking_price", "Asking price"]].map(([k, lbl]) => (
                  <div key={k}>
                    <label className="text-xs text-muted-foreground">{lbl}</label>
                    <input data-testid={`veh-${k}`} value={vehForm[k] ?? ""} onChange={(e) => setVehForm({ ...vehForm, [k]: e.target.value })}
                      className="mt-1 w-full rounded-[4px] border border-input bg-card px-2 py-1.5 text-sm outline-none focus:border-primary transition-colors duration-200" />
                  </div>
                ))}
                <div>
                  <label className="text-xs text-muted-foreground">Condition</label>
                  <select value={vehForm.condition ?? ""} onChange={(e) => setVehForm({ ...vehForm, condition: e.target.value })}
                    className="mt-1 w-full rounded-[4px] border border-input bg-card px-2 py-1.5 text-sm">
                    {["excellent", "good", "fair", "poor", "damaged", "unknown"].map((c) => <option key={c} value={c}>{titleize(c)}</option>)}
                  </select>
                </div>
                <div>
                  <label className="text-xs text-muted-foreground">Ownership</label>
                  <select value={vehForm.ownership_status ?? ""} onChange={(e) => setVehForm({ ...vehForm, ownership_status: e.target.value })}
                    className="mt-1 w-full rounded-[4px] border border-input bg-card px-2 py-1.5 text-sm">
                    {["owned_outright", "financed", "leased", "unknown"].map((c) => <option key={c} value={c}>{titleize(c)}</option>)}
                  </select>
                </div>
                <button data-testid="save-vehicle-btn" onClick={saveVeh} className="col-span-2 bg-primary text-primary-foreground rounded-[4px] py-2 text-sm font-semibold hover:opacity-90 transition-opacity duration-200">Save & recalculate</button>
              </div>
            ) : (
              <dl className="grid grid-cols-2 sm:grid-cols-3 gap-y-3 gap-x-4 text-sm">
                {[["Year", vehicle?.year], ["Make", vehicle?.make], ["Model", vehicle?.model], ["Trim", vehicle?.trim],
                  ["Mileage", vehicle?.mileage ? `${vehicle.mileage.toLocaleString()} ${vehicle.mileage_unit || "km"}` : null],
                  ["Condition", vehicle?.condition && titleize(vehicle.condition)], ["Ownership", vehicle?.ownership_status && titleize(vehicle.ownership_status)],
                  ["Loan balance", vehicle?.estimated_loan_balance ? `$${vehicle.estimated_loan_balance.toLocaleString()}` : null],
                  ["Asking price", vehicle?.asking_price ? `$${vehicle.asking_price.toLocaleString()}` : null],
                  ["Accident", vehicle?.accident_history && titleize(vehicle.accident_history)]].map(([k, v]) => (
                  <div key={k}>
                    <dt className="text-xs font-mono-plex uppercase tracking-wide text-muted-foreground">{k}</dt>
                    <dd className="mt-0.5">{v || "—"}</dd>
                  </div>
                ))}
              </dl>
            )}
          </Card>

          {/* inventory matches */}
          <Card>
            <h3 className="font-head font-bold tracking-tight mb-3">Inventory matches</h3>
            {matches.length === 0 ? <div className="text-sm text-muted-foreground">No matches yet. Run inventory match if the seller wants a replacement.</div> : (
              <div className="space-y-3">
                {matches.map((m) => (
                  <div key={m.id} className="flex gap-3 border border-border rounded-[4px] p-3" data-testid={`match-${m.id}`}>
                    <img src={m.vehicle?.image_url || CAR_IMG} alt="" className="w-20 h-16 object-cover rounded-[4px]" />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between">
                        <div className="font-medium text-sm">{m.vehicle?.year} {m.vehicle?.make} {m.vehicle?.model}</div>
                        <span className="text-xs font-mono-plex text-primary">#{m.ranking} · {m.match_score}%</span>
                      </div>
                      <div className="text-xs text-muted-foreground font-mono-plex">${m.vehicle?.price?.toLocaleString()} · {m.vehicle?.drivetrain} · {m.vehicle?.seating_capacity} seats</div>
                      <div className="text-xs text-muted-foreground mt-1">{(m.match_reasons || []).slice(0, 2).join(" · ")}</div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>

        {/* right column */}
        <div className="space-y-4">
          <Card>
            <h3 className="font-head font-bold tracking-tight mb-3">Seller</h3>
            <dl className="space-y-2 text-sm">
              <Field k="Phone" v={seller?.phone} />
              <Field k="Email" v={seller?.email} />
              <Field k="Location" v={[seller?.city, seller?.province_state].filter(Boolean).join(", ")} />
              <Field k="Consent" v={seller?.consent_status && titleize(seller.consent_status)} />
              <Field k="Intent" v={titleize(lead.primary_intent || "—")} />
              <Field k="Timeline" v={titleize(lead.timeline || "—")} />
            </dl>
          </Card>

          {score && (
            <Card>
              <h3 className="font-head font-bold tracking-tight mb-3">Score breakdown</h3>
              <div className="space-y-1.5 text-sm">
                {[["Intent", score.intent_score, 20], ["Urgency", score.urgency_score, 15], ["Vehicle", score.vehicle_score, 20],
                  ["Price", score.price_score, 15], ["Completeness", score.completeness_score, 10],
                  ["Geographic", score.geographic_score, 10], ["Appointment", score.appointment_score, 10]].map(([k, v, max]) => (
                  <div key={k}>
                    <div className="flex justify-between text-xs"><span className="text-muted-foreground">{k}</span><span className="font-mono-plex">{v}/{max}</span></div>
                    <div className="h-1.5 bg-secondary rounded-full mt-0.5"><div className="h-full bg-primary rounded-full" style={{ width: `${(v / max) * 100}%` }} /></div>
                  </div>
                ))}
                {score.penalties?.length > 0 && (
                  <div className="pt-2 mt-2 border-t border-border">
                    {score.penalties.map((p, i) => (
                      <div key={i} className="flex justify-between text-xs text-destructive"><span>{p.reason}</span><span className="font-mono-plex">{p.points}</span></div>
                    ))}
                  </div>
                )}
              </div>
            </Card>
          )}

          {appointment && (
            <Card>
              <h3 className="font-head font-bold tracking-tight mb-3">Appointment</h3>
              <div className="text-sm">{titleize(appointment.appointment_type)}</div>
              <div className="text-sm font-mono-plex text-muted-foreground">{new Date(appointment.start_time).toLocaleString()}</div>
              <StatusBadge status={appointment.status} />
            </Card>
          )}

          <Card>
            <h3 className="font-head font-bold tracking-tight mb-3 flex items-center gap-2"><Note size={16} weight="bold" /> Notes</h3>
            <div className="flex gap-2 mb-3">
              <input data-testid="note-input" value={note} onChange={(e) => setNote(e.target.value)} onKeyDown={(e) => e.key === "Enter" && addNote()}
                placeholder="Add internal note…" className="flex-1 rounded-[4px] border border-input bg-card px-2 py-1.5 text-sm outline-none focus:border-primary transition-colors duration-200" />
              <button data-testid="add-note-btn" onClick={addNote} className="bg-secondary hover:bg-accent px-3 rounded-[4px] text-sm transition-colors duration-200">Add</button>
            </div>
            <div className="space-y-2 max-h-48 overflow-y-auto">
              {notes.map((n) => (
                <div key={n.id} className="text-xs border-l-2 border-primary pl-2">
                  <div>{n.content}</div>
                  <div className="text-muted-foreground font-mono-plex mt-0.5">{n.user_name} · {new Date(n.created_at).toLocaleDateString()}</div>
                </div>
              ))}
              {notes.length === 0 && <div className="text-xs text-muted-foreground">No notes yet.</div>}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}

const Card = ({ children }) => <div className="border border-border rounded-[4px] bg-card p-5">{children}</div>;
const Field = ({ k, v }) => (
  <div className="flex justify-between gap-3">
    <dt className="text-muted-foreground text-xs font-mono-plex uppercase tracking-wide shrink-0">{k}</dt>
    <dd className="text-right truncate">{v || "—"}</dd>
  </div>
);
