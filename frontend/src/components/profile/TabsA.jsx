import { tr } from "@/lib/adminI18n";
import { titleize } from "@/components/ui/badges";
import { Card, Fields, Empty, fmtDate, fmtDay, money } from "./shared";

const CAR_IMG = "https://images.unsplash.com/photo-1760312206290-d884595398d9?crop=entropy&cs=srgb&fm=jpg&q=85&w=400";

export function OverviewTab({ p }) {
  const { customer: c, lead, overview: o } = p;
  const name = `${c.first_name || ""} ${c.last_name || ""}`.trim() || "Anonymous customer";
  return (
    <div className="space-y-4" data-testid="tab-panel-overview">
      <Card title="Customer">
        <Fields rows={[
          ["Name", name, "ov-name"], ["Email", c.email, "ov-email"], ["Phone", c.phone, "ov-phone"],
          ["Preferred language", o.preferred_language === "fr" ? "Français" : "English", "ov-language"],
          ["Location", [c.city, c.province_state].filter(Boolean).join(", ")],
          ["Preferred contact", titleize(c.preferred_contact_method)],
        ]} />
      </Card>
      <Card title="Lead">
        <Fields rows={[
          ["Created", fmtDay(lead.created_at), "ov-created"], ["Lead source", titleize(lead.source), "ov-source"],
          ["Lead score", `${lead.score ?? 0} · ${lead.score_band || "—"}`, "ov-score"],
          ["Assigned dealership", o.dealer_group?.name, "ov-dealer"], ["Sales representative", o.assigned_user?.name || o.assigned_user?.email || tr("Unassigned"), "ov-rep"],
          ["Pipeline stage", titleize(p.stage), "ov-stage"], ["Last interaction", fmtDate(o.last_interaction), "ov-last"],
          ["Next follow-up", o.next_follow_up ? `${fmtDate(o.next_follow_up.due_at)}${o.next_follow_up.note ? ` · ${o.next_follow_up.note}` : ""}` : tr("None scheduled"), "ov-next-followup"],
          ["Customer status", titleize(lead.status), "ov-status"],
        ]} />
      </Card>
    </div>
  );
}

export function PreferencesTab({ p }) {
  const pr = p.preferences || {};
  const t = p.trade_in;
  const join = (a) => (Array.isArray(a) ? a.join(", ") : a);
  const budget = pr.min_price || pr.max_price ? `${money(pr.min_price)} – ${money(pr.max_price)}` : null;
  return (
    <div className="space-y-4" data-testid="tab-panel-preferences">
      <Card title="What they're looking for">
        {!p.preferences ? <Empty label="No vehicle preferences captured yet." /> : (
          <Fields rows={[
            ["Vehicle type", join(pr.preferred_body_types)], ["Make", join(pr.preferred_makes)], ["Model", join(pr.preferred_models)],
            ["Model year", pr.min_year || pr.max_year ? `${pr.min_year || "…"} – ${pr.max_year || "…"}` : null],
            ["Budget range", budget, "pref-budget"], ["Max mileage", pr.maximum_mileage ? `${pr.maximum_mileage.toLocaleString()} km` : null],
            ["Transmission", titleize(pr.transmission)], ["Fuel", join(pr.preferred_fuel_types || pr.fuel_type)],
            ["Drivetrain", join(pr.preferred_drivetrains)], ["Min. seating", pr.minimum_seating],
            ["Financing", pr.financing_required === undefined ? null : pr.financing_required ? `Yes${pr.monthly_budget ? ` · ${money(pr.monthly_budget)}/mo` : ""}` : "No"],
            ["Additional", pr.notes || pr.additional_requirements],
          ]} />
        )}
      </Card>
      <Card title="Trade-in">
        {!t ? <Empty label="No trade-in vehicle." /> : (
          <Fields rows={[
            ["Vehicle", [t.year, t.make, t.model, t.trim].filter(Boolean).join(" ")],
            ["Mileage", t.mileage ? `${t.mileage.toLocaleString()} ${t.mileage_unit || "km"}` : null],
            ["Condition", titleize(t.condition)], ["Ownership", titleize(t.ownership_status)],
            ["Loan balance", t.estimated_loan_balance ? money(t.estimated_loan_balance) : null], ["Asking price", t.asking_price ? money(t.asking_price) : null],
          ]} />
        )}
      </Card>
      <Card title={`Recommended & matched vehicles (${p.matches.length})`}>
        {p.matches.length === 0 ? <Empty label="No inventory matches yet." /> : (
          <div className="grid sm:grid-cols-2 gap-3">
            {p.matches.map((m) => (
              <div key={m.id} data-testid="pref-match" className="flex gap-3 border border-border rounded-[4px] p-3">
                <img src={m.vehicle?.image_url || CAR_IMG} alt="" className="w-20 h-16 object-cover rounded-[4px] shrink-0" />
                <div className="min-w-0">
                  <div className="font-medium text-sm truncate">{m.vehicle ? `${m.vehicle.year} ${m.vehicle.make} ${m.vehicle.model}` : "Vehicle no longer available"}</div>
                  <div className="text-xs font-mono-plex text-primary">#{m.ranking} · {m.match_score}% match</div>
                  <div className="text-xs text-muted-foreground">{money(m.vehicle?.price)} · {titleize(m.vehicle?.status)}</div>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}

export function ConversationTab({ p }) {
  const conv = p.conversation;
  if (!conv) return <Empty testid="tab-panel-conversation" label="No AI conversation linked to this customer." />;
  return (
    <Card testid="tab-panel-conversation" title="AI conversation"
      action={<span className="text-xs font-mono-plex text-muted-foreground">{conv.language === "fr" ? "Français" : "English"} · started {fmtDate(conv.started_at || conv.created_at)} · {p.messages.length} messages</span>}>
      <div className="space-y-3 max-h-[560px] overflow-y-auto pr-1">
        {p.messages.map((m) => {
          const recs = m.structured_payload?.recommendations || [];
          const cust = m.sender_type === "seller";
          return (
            <div key={m.id} data-testid="conv-message" className={`flex ${cust ? "justify-start" : "justify-end"}`}>
              <div className={`max-w-[80%] rounded-[8px] px-3 py-2 text-sm border ${cust ? "bg-secondary border-border" : m.sender_type === "human_agent" ? "bg-orange-500/10 border-orange-500/25" : "bg-primary/10 border-primary/25"}`}>
                <div className="text-[10px] font-mono-plex uppercase tracking-wider opacity-60 mb-0.5">
                  {cust ? "Customer" : m.sender_type === "human_agent" ? "Staff" : "AI"} · {fmtDate(m.created_at)}
                </div>
                <div className="whitespace-pre-wrap">{m.content}</div>
                {recs.length > 0 && <div className="mt-1 text-xs text-primary">Recommended: {recs.map((r) => `${r.year} ${r.make} ${r.model}`).join(", ")}</div>}
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}
