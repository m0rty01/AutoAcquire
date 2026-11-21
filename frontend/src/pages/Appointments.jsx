import { useEffect, useState } from "react";
import client from "@/lib/api";
import { PageHeader, Loading, Empty } from "@/components/Bits";
import { StatusBadge, titleize } from "@/components/ui/badges";
import { toast } from "sonner";

export default function Appointments() {
  const [appts, setAppts] = useState(null);
  const load = () => client.get("/appointments").then((r) => setAppts(r.data));
  useEffect(() => { load(); }, []);

  const LABEL = { confirm: "confirmed", decline: "declined", complete: "completed", "no-show": "marked no-show", cancel: "cancelled" };
  const act = async (id, action) => {
    try {
      await client.post(`/appointments/${id}/${action}`);
      toast.success(`Appointment ${LABEL[action] || action}`);
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Action failed");
    }
  };

  if (!appts) return <Loading />;
  const requested = appts.filter((a) => ["requested", "proposed"].includes(a.status));
  const upcoming = appts.filter((a) => a.status === "confirmed");
  const past = appts.filter((a) => !["requested", "proposed", "confirmed"].includes(a.status));

  return (
    <div>
      <PageHeader title="Appointments" subtitle={`${requested.length} awaiting confirmation · ${upcoming.length} confirmed`} />
      {appts.length === 0 ? <Empty label="No appointments yet." /> : (
        <div className="space-y-6">
          <Section title="Awaiting your confirmation" list={requested} act={act} mode="pending" />
          <Section title="Confirmed" list={upcoming} act={act} mode="confirmed" />
          {past.length > 0 && <Section title="Past & closed" list={past} act={act} mode="past" />}
        </div>
      )}
    </div>
  );
}

function Section({ title, list, act, mode }) {
  if (list.length === 0) return null;
  return (
    <div>
      <h3 className="font-head font-bold mb-3 text-muted-foreground text-sm uppercase font-mono-plex tracking-wider">{title}</h3>
      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {list.map((a) => (
          <div key={a.id} className="border border-border rounded-[4px] bg-card p-4" data-testid={`appt-${a.id}`}>
            <div className="flex items-center justify-between mb-2">
              <span className="font-medium">{a.seller_name}</span>
              <StatusBadge status={a.status} />
            </div>
            <div className="text-sm text-muted-foreground">{titleize(a.appointment_type)}</div>
            <div className="text-sm font-mono-plex mt-1">{new Date(a.start_time).toLocaleString([], { weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}</div>
            {mode === "pending" && (
              <div className="flex gap-2 mt-3">
                <button data-testid={`confirm-${a.id}`} onClick={() => act(a.id, "confirm")} className="text-xs bg-primary text-primary-foreground px-2.5 py-1.5 rounded-[4px] font-semibold hover:opacity-90 transition-opacity">Confirm</button>
                <button data-testid={`decline-${a.id}`} onClick={() => act(a.id, "decline")} className="text-xs text-destructive hover:bg-destructive/10 px-2.5 py-1.5 rounded-[4px] transition-colors duration-200">Decline</button>
              </div>
            )}
            {mode === "confirmed" && (
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
