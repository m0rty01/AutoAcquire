import { useEffect, useState } from "react";
import client from "@/lib/api";
import { PageHeader, MetricTile, Loading, Empty } from "@/components/Bits";
import { titleize } from "@/components/ui/badges";

export default function PlatformAdmin() {
  const [orgs, setOrgs] = useState(null);
  const [failed, setFailed] = useState([]);
  useEffect(() => {
    client.get("/platform/organizations").then((r) => setOrgs(r.data)).catch(() => setOrgs([]));
    client.get("/platform/failed-workflows").then((r) => setFailed(r.data)).catch(() => {});
  }, []);
  if (!orgs) return <Loading />;

  const totalLeads = orgs.reduce((s, o) => s + o.lead_count, 0);
  const totalAppts = orgs.reduce((s, o) => s + o.appointment_count, 0);

  return (
    <div>
      <PageHeader title="Platform Administration" subtitle="Tenant oversight & system health." />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <MetricTile label="Organizations" value={orgs.length} />
        <MetricTile label="Total Leads" value={totalLeads} />
        <MetricTile label="Total Appointments" value={totalAppts} />
        <MetricTile label="Failed Workflows" value={failed.length} accent={failed.length ? "text-[#F87171]" : ""} />
      </div>

      <div className="border border-border rounded-[4px] bg-card overflow-x-auto mb-6">
        <table className="w-full text-sm">
          <thead><tr className="text-left text-xs font-mono-plex uppercase tracking-wider text-muted-foreground border-b border-border">
            <th className="p-3">Organization</th><th className="p-3">Status</th><th className="p-3">Users</th><th className="p-3">Leads</th><th className="p-3">Appts</th><th className="p-3">Plan</th>
          </tr></thead>
          <tbody>
            {orgs.map((o) => (
              <tr key={o.id} className="border-b border-border last:border-0 hover:bg-secondary transition-colors duration-150">
                <td className="p-3 font-medium">{o.name}</td>
                <td className="p-3"><span className="text-xs text-green-400 bg-green-500/10 border border-green-500/30 rounded-[4px] px-2 py-0.5 font-mono-plex">{titleize(o.status)}</span></td>
                <td className="p-3">{o.user_count}</td><td className="p-3">{o.lead_count}</td><td className="p-3">{o.appointment_count}</td>
                <td className="p-3 text-muted-foreground">{titleize(o.plan)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h3 className="font-head font-bold tracking-tight mb-3">Failed workflows</h3>
      {failed.length === 0 ? <Empty label="No failed workflows. System healthy." /> : (
        <div className="space-y-2">
          {failed.map((f) => (
            <div key={f.id} className="border border-red-500/25 bg-red-500/5 rounded-[4px] p-3 text-sm">
              <div className="font-mono-plex text-red-400">{f.event_type}</div>
              <div className="text-xs text-muted-foreground">{JSON.stringify(f.payload)} · {new Date(f.created_at).toLocaleString()}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
