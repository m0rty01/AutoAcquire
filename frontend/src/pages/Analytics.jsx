import { useEffect, useState } from "react";
import client from "@/lib/api";
import { PageHeader, MetricTile, Loading } from "@/components/Bits";
import { titleize } from "@/components/ui/badges";
import { PieChart, Pie, Cell, ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip } from "recharts";

const BAND_COLORS = { hot: "#EF4444", warm: "#F97316", nurture: "#EAB308", low: "#64748B" };

export default function Analytics() {
  const [a, setA] = useState(null);
  useEffect(() => { client.get("/analytics/overview").then((r) => setA(r.data)); }, []);
  if (!a) return <Loading />;

  const bandData = Object.entries(a.score_band_distribution).map(([name, value]) => ({ name, value }));
  const intentData = Object.entries(a.intent_distribution || {}).map(([name, value]) => ({ name: titleize(name), value }));

  return (
    <div>
      <PageHeader title="Analytics" subtitle="Pilot performance metrics." />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <MetricTile label="Total Leads" value={a.total_leads} />
        <MetricTile label="Qualified" value={a.qualified_leads} hint={`${a.qualification_rate}% rate`} accent="text-[#4ADE80]" />
        <MetricTile label="Lead → Appt" value={`${a.lead_to_appointment_rate}%`} />
        <MetricTile label="Hot Leads" value={a.hot_leads} accent="text-[#EF4444]" />
        <MetricTile label="Active Chats" value={a.active_conversations} />
        <MetricTile label="Appointments" value={a.appointments_booked} />
        <MetricTile label="Completion" value={`${a.appointment_completion_rate}%`} />
        <MetricTile label="No-show Rate" value={`${a.no_show_rate}%`} accent="text-[#F87171]" />
      </div>

      <div className="grid lg:grid-cols-2 gap-4">
        <div className="border border-border rounded-[4px] bg-card p-5">
          <h3 className="font-head font-bold tracking-tight mb-4">Score band distribution</h3>
          <ResponsiveContainer width="100%" height={240}>
            <PieChart>
              <Pie data={bandData} dataKey="value" nameKey="name" innerRadius={55} outerRadius={90} paddingAngle={3}>
                {bandData.map((e) => <Cell key={e.name} fill={BAND_COLORS[e.name]} />)}
              </Pie>
              <Tooltip contentStyle={{ background: "#121214", border: "1px solid #27272a", borderRadius: 4, fontSize: 12 }} />
            </PieChart>
          </ResponsiveContainer>
          <div className="flex justify-center gap-4 flex-wrap">
            {bandData.map((e) => (
              <div key={e.name} className="flex items-center gap-1.5 text-xs font-mono-plex">
                <span className="w-2.5 h-2.5 rounded-sm" style={{ background: BAND_COLORS[e.name] }} /> {titleize(e.name)} ({e.value})
              </div>
            ))}
          </div>
        </div>

        <div className="border border-border rounded-[4px] bg-card p-5">
          <h3 className="font-head font-bold tracking-tight mb-4">Leads by intent</h3>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={intentData} layout="vertical" margin={{ left: 20 }}>
              <XAxis type="number" hide />
              <YAxis type="category" dataKey="name" width={110} tick={{ fill: "#a1a1aa", fontSize: 12 }} />
              <Tooltip cursor={{ fill: "rgba(255,255,255,0.05)" }} contentStyle={{ background: "#121214", border: "1px solid #27272a", borderRadius: 4, fontSize: 12 }} />
              <Bar dataKey="value" fill="#3B82F6" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
