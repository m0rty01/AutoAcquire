import { useEffect, useState } from "react";
import client from "@/lib/api";
import { PageHeader, Loading, Empty } from "@/components/Bits";
import { StatusBadge, titleize } from "@/components/ui/badges";
import { toast } from "sonner";

export default function Appointments() {
  const [appts, setAppts] = useState(null);
  const load = () => client.get("/appointments").then((r) => setAppts(r.data));
  useEffect(() => { load(); }, []);

  const act = async (id, action) => {
    await client.post(`/appointments/${id}/${action}`);
    toast.success(`Appointment ${action.replace("-", " ")}`);
    load();
  };

  if (!appts) return <Loading />;
  const upcoming = appts.filter((a) => ["confirmed", "proposed"].includes(a.status));
  const past = appts.filter((a) => !["confirmed", "proposed"].includes(a.status));

  return (
    <div>
      <PageHeader title="Appointments" subtitle={`${upcoming.length} upcoming`} />
      {appts.length === 0 ? <Empty label="No appointments booked yet." /> : (
        <div className="space-y-6">
          <Section title="Upcoming" list={upcoming} act={act} showActions />
          {past.length > 0 && <Section title="Past & closed" list={past} act={act} />}
        </div>
      )}
    </div>
  );
}

function Section({ title, list, act, showActions }) {
  if (list.length === 0) return null;
  return (
    <div>
      <h3 className="font-head font-bold tracking-tight mb-3 text-muted-foreground text-sm uppercase font-mono-plex tracking-wider">{title}</h3>
      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {list.map((a) => (
          <div key={a.id} className="border border-border rounded-[4px] bg-card p-4" data-testid={`appt-${a.id}`}>
            <div className="flex items-center justify-between mb-2">
              <span className="font-medium">{a.seller_name}</span>
              <StatusBadge status={a.status} />
            </div>
            <div className="text-sm text-muted-foreground">{titleize(a.appointment_type)}</div>
            <div className="text-sm font-mono-plex mt-1">{new Date(a.start_time).toLocaleString([], { weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}</div>
            {showActions && (
              <div className="flex gap-2 mt-3">
                <button data-testid={`complete-${a.id}`} onClick={() => act(a.id, "complete")} className="text-xs bg-secondary hover:bg-accent px-2.5 py-1.5 rounded-[4px] transition-colors duration-200">Complete</button>
                <button data-testid={`noshow-${a.id}`} onClick={() => act(a.id, "no-show")} className="text-xs bg-secondary hover:bg-accent px-2.5 py-1.5 rounded-[4px] transition-colors duration-200">No-show</button>
                <button data-testid={`cancel-${a.id}`} onClick={() => act(a.id, "cancel")} className="text-xs text-destructive hover:bg-destructive/10 px-2.5 py-1.5 rounded-[4px] transition-colors duration-200">Cancel</button>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
