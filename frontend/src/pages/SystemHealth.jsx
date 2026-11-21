import { useEffect, useState } from "react";
import client from "@/lib/api";
import { PageHeader, Loading } from "@/components/Bits";
import { CheckCircle, WarningCircle } from "@phosphor-icons/react";
import { tr } from "@/lib/adminI18n";

export default function SystemHealth() {
  const [d, setD] = useState(null);
  useEffect(() => { client.get("/system/health").then((r) => setD(r.data)).catch(() => setD({ checks: [] })); }, []);
  if (!d) return <Loading />;
  return (
    <div data-testid="system-health-page">
      <PageHeader title="System Health" subtitle="Database, providers, delivery, background jobs and inventory sync" />
      <div className="grid md:grid-cols-2 gap-3">
        {d.checks.map((c) => (
          <div key={c.name} data-testid={`health-${c.name.split(" ")[0].toLowerCase()}`} className="border border-border rounded-[4px] bg-card p-4 flex gap-3">
            {c.ok ? <CheckCircle size={22} weight="fill" className="text-emerald-400 shrink-0" /> : <WarningCircle size={22} weight="fill" className="text-amber-400 shrink-0" />}
            <div><div className="font-medium">{tr(c.name)}</div><div className="text-xs text-muted-foreground font-mono-plex mt-0.5">{c.detail}</div></div>
          </div>
        ))}
      </div>
      <p className="text-xs text-muted-foreground mt-6 max-w-2xl">Failed emails/SMS can be retried from the Communication Center and failed automations from Automations. Database backups are handled by MongoDB Atlas (see DEPLOYMENT.md).</p>
    </div>
  );
}
