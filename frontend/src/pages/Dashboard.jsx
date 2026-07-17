import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import client from "@/lib/api";
import { PageHeader, MetricTile, Loading, Empty } from "@/components/Bits";
import { ScoreBadge, StatusBadge, titleize } from "@/components/ui/badges";
import { Fire, Warning, CalendarBlank, UserPlus } from "@phosphor-icons/react";

export default function Dashboard() {
  const [home, setHome] = useState(null);
  const [analytics, setAnalytics] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    client.get("/dashboard/home").then((r) => setHome(r.data));
    client.get("/analytics/overview").then((r) => setAnalytics(r.data));
  }, []);

  if (!home || !analytics) return <Loading />;

  const goLead = (id) => navigate(`/app/leads/${id}`);

  return (
    <div>
      <PageHeader title="Dashboard" subtitle="Your acquisition command center." />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <MetricTile label="Hot Leads" value={analytics.hot_leads} accent="text-[#EF4444]" hint="Awaiting action" />
        <MetricTile label="Qualification Rate" value={`${analytics.qualification_rate}%`} accent="text-[#4ADE80]" />
        <MetricTile label="Appointments" value={analytics.appointments_booked} hint="Booked" />
        <MetricTile label="Avg Score" value={analytics.average_lead_score} hint="Across all leads" />
      </div>

      <div className="grid lg:grid-cols-3 gap-4">
        <Panel icon={Fire} iconClass="text-[#EF4444]" title="Hot leads" testid="panel-hot">
          {home.hot_leads.length === 0 ? <Empty label="No hot leads yet" /> :
            home.hot_leads.map((l) => (
              <Row key={l.id} onClick={() => goLead(l.id)} testid={`hot-lead-${l.id}`}>
                <div className="min-w-0">
                  <div className="font-medium truncate">{l.seller_name}</div>
                  <div className="text-xs text-muted-foreground font-mono-plex truncate">{l.vehicle_label}</div>
                </div>
                <ScoreBadge score={l.score} band={l.score_band} />
              </Row>
            ))}
        </Panel>

        <Panel icon={Warning} iconClass="text-[#FBBF24]" title="Needs review" testid="panel-review">
          {home.review_leads.length === 0 ? <Empty label="Nothing to review" /> :
            home.review_leads.map((l) => (
              <Row key={l.id} onClick={() => goLead(l.id)} testid={`review-lead-${l.id}`}>
                <div className="min-w-0">
                  <div className="font-medium truncate">{l.seller_name}</div>
                  <div className="text-xs text-muted-foreground font-mono-plex truncate">{l.vehicle_label}</div>
                </div>
                <StatusBadge status={l.status} />
              </Row>
            ))}
        </Panel>

        <Panel icon={UserPlus} iconClass="text-[#3B82F6]" title="New leads" testid="panel-new">
          {home.new_leads.length === 0 ? <Empty label="No new leads" /> :
            home.new_leads.map((l) => (
              <Row key={l.id} onClick={() => goLead(l.id)} testid={`new-lead-${l.id}`}>
                <div className="min-w-0">
                  <div className="font-medium truncate">{l.seller_name}</div>
                  <div className="text-xs text-muted-foreground font-mono-plex truncate">{l.vehicle_label || "—"}</div>
                </div>
                <span className="text-xs text-muted-foreground">{titleize(l.primary_intent || "unclear")}</span>
              </Row>
            ))}
        </Panel>
      </div>

      <div className="mt-4 border border-border rounded-[4px] bg-card p-5">
        <div className="flex items-center gap-2 mb-4">
          <CalendarBlank size={18} weight="bold" className="text-primary" />
          <h3 className="font-head font-bold tracking-tight">Appointments today</h3>
        </div>
        {home.today_appointments.length === 0 ? <Empty label="No appointments scheduled today" /> : (
          <div className="space-y-2">
            {home.today_appointments.map((a) => (
              <div key={a.id} className="flex justify-between items-center text-sm border-b border-border pb-2">
                <span>{titleize(a.appointment_type)}</span>
                <span className="font-mono-plex text-muted-foreground">{new Date(a.start_time).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function Panel({ icon: Icon, iconClass, title, children, testid }) {
  return (
    <div className="border border-border rounded-[4px] bg-card p-5" data-testid={testid}>
      <div className="flex items-center gap-2 mb-4">
        <Icon size={18} weight="bold" className={iconClass} />
        <h3 className="font-head font-bold tracking-tight">{title}</h3>
      </div>
      <div className="space-y-1">{children}</div>
    </div>
  );
}

function Row({ children, onClick, testid }) {
  return (
    <button onClick={onClick} data-testid={testid}
      className="w-full flex items-center justify-between gap-3 px-2 py-2 rounded-[4px] hover:bg-secondary transition-colors duration-200 text-left">
      {children}
    </button>
  );
}
