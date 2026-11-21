import { useState } from "react";
import { Clock, Note } from "@phosphor-icons/react";
import { TDActions, NewTestDrive } from "@/components/testdrives/TDParts";
import { titleize } from "@/components/ui/badges";
import { Card, Empty, Pill, Table, fmtDate, fmtDay, money } from "./shared";

export function ActivitiesTab({ p }) {
  if (!p.activities.length) return <Empty testid="tab-panel-activities" label="No activity recorded yet." />;
  return (
    <Card testid="tab-panel-activities" title={`Activity timeline (${p.activities.length})`}>
      <div className="space-y-3">
        {p.activities.map((a) => (
          <div key={a.id} data-testid="activity-item" className="flex gap-3 text-sm border-l-2 border-primary/30 pl-3">
            {a.activity_type === "note" ? <Note size={15} className="text-primary mt-0.5 shrink-0" /> : <Clock size={15} className="text-muted-foreground mt-0.5 shrink-0" />}
            <div className="min-w-0">
              <div className="font-medium">{titleize(a.activity_type)}</div>
              {a.details && <div className="text-muted-foreground break-words">{a.details}</div>}
              <div className="text-[11px] text-muted-foreground font-mono-plex mt-0.5">{a.actor} · {fmtDate(a.created_at)}</div>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}

export function AppointmentsTab({ p }) {
  if (!p.appointments.length) return <Empty testid="tab-panel-appointments" label="No appointments for this customer." />;
  return (
    <Card testid="tab-panel-appointments" title="Appointments">
      <Table head={["Type", "Date & time", "Status", "Dealership", "Representative"]} rows={p.appointments.map((a) => [
        titleize(a.appointment_type), fmtDate(a.start_time), <Pill s={a.status} />,
        p.overview.dealer_group?.name || "—", a.assigned_user?.name || "Unassigned",
      ])} />
    </Card>
  );
}

export function TestDrivesTab({ p, reload, readOnly }) {
  const [open, setOpen] = useState(false);
  const action = !readOnly && <button data-testid="profile-request-td-btn" onClick={() => setOpen(true)} className="text-xs bg-primary text-primary-foreground px-3 py-1.5 rounded-[4px]">Request test drive</button>;
  return (
    <Card testid="tab-panel-test-drives" title="Test drives" action={action}>
      {!p.test_drives.length ? <Empty label="No test drives for this customer yet." /> : (
        <Table head={["Vehicle", "Requested", "Confirmed", "Status", "Notes / feedback", ""]} rows={p.test_drives.map((t) => [
          t.vehicle_label || "—", fmtDate(t.requested_at), fmtDate(t.confirmed_at), <Pill s={t.status} />,
          <div className="text-xs max-w-xs">{(t.notes || []).map((n) => n.content).join(" · ")}{t.customer_feedback && <div className="text-muted-foreground">“{t.customer_feedback}”</div>}</div>,
          readOnly ? null : <TDActions td={t} onDone={reload} />,
        ])} />
      )}
      {open && <NewTestDrive leadId={p.lead.id} onClose={() => setOpen(false)} onCreated={() => { setOpen(false); reload(); }} />}
    </Card>
  );
}

export function ReferralsTab({ p }) {
  if (!p.referrals.length) return <Empty testid="tab-panel-referrals" label="No referrals — the customer hasn't consented to share their details yet." />;
  return (
    <Card testid="tab-panel-referrals" title="Referrals">
      <Table head={["Referral ID", "Dealer group", "Vehicle of interest", "Created", "Consent", "Delivery status"]} rows={p.referrals.map((r) => [
        <span className="font-mono-plex text-xs">{r.id.slice(0, 8)}</span>, r.dealer_group_name || "—", r.vehicle_label || "—",
        fmtDay(r.created_at), <Pill s={r.consent_status} />, <Pill s={r.status} />,
      ])} />
    </Card>
  );
}

export function SalesTab({ p }) {
  if (!p.sales.length) return <Empty testid="tab-panel-sales" label="No sales reported for this customer." />;
  const head = ["Vehicle", "Dealer group", "Status", "Sale date", "Verified"];
  if (p.can_view_financials) head.push("Sale amount", "Commission");
  return (
    <Card testid="tab-panel-sales" title="Sales">
      <Table head={head} rows={p.sales.map((s) => {
        const r = [s.vehicle_label || "—", s.dealer_group_name || "—", <Pill s={s.status} />, fmtDay(s.sale_date), fmtDay(s.verified_at)];
        if (p.can_view_financials) r.push(money(s.sale_amount), s.commission ? `${money(s.commission.amount)} · ${titleize(s.commission.status)}` : "—");
        return r;
      })} />
    </Card>
  );
}
