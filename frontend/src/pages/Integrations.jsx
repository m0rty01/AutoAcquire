import { tr } from "@/lib/adminI18n";
import { useEffect, useState, useCallback } from "react";
import client from "@/lib/api";
import { PageHeader, Loading } from "@/components/Bits";
import { toast } from "sonner";
import { ArrowsClockwise, Flask } from "@phosphor-icons/react";
import { titleize } from "@/components/ui/badges";
import { Pill, Table, fmtDate, inputCls } from "@/components/profile/shared";

const TONE = { pending_credentials: "text-amber-400 border-amber-500/30 bg-amber-500/10", sandbox: "text-sky-400 border-sky-500/30 bg-sky-500/10",
  active: "text-emerald-400 border-emerald-500/30 bg-emerald-500/10", error: "text-red-400 border-red-500/30 bg-red-500/10", inactive: "text-zinc-400 border-border bg-secondary" };
const err = (e) => toast.error(e.response?.data?.detail || "Action failed");

function PartnerCard({ p, groups, reload }) {
  const patch = async (body) => { try { await client.patch(`/integrations/${p.partner_key}`, body); reload(); } catch (e) { err(e); } };
  const sync = async () => {
    try { const { data } = await client.post(`/integrations/${p.partner_key}/sync`); toast.success(`Sync done · ${data.stats.imported} new, ${data.stats.updated} updated`); reload(); } catch (e) { err(e); }
  };
  const s = p.last_stats || {};
  return (
    <div className="border border-border rounded-[4px] bg-card p-5" data-testid={`integration-${p.partner_key}`}>
      <div className="flex items-start justify-between gap-2 mb-3">
        <div><div className="font-head font-bold">{p.name}</div><div className="text-[11px] font-mono-plex text-muted-foreground">{p.kind === "code_mapping" ? "inventory-code mapping" : "inventory feed / API"}</div></div>
        <span data-testid={`integration-status-${p.partner_key}`} className={`text-[11px] font-mono-plex px-2 py-0.5 rounded-[4px] border ${TONE[p.status]}`}>{titleize(p.status).toUpperCase()}</span>
      </div>
      {p.status === "pending_credentials" && (
        <div className="text-xs text-muted-foreground mb-3">Waiting on partner: {p.required.join(" · ")}. No endpoints or credentials are assumed.</div>
      )}
      {p.kind === "inventory" && (
        <>
          <div className="grid grid-cols-4 gap-2 text-center mb-3">
            {[["Imported", s.imported], ["Updated", s.updated], ["Sold/removed", (s.sold || 0) + (s.removed || 0)], ["Failed", s.failed], ["Unmatched", s.unmatched], ["Conflicts", p.open_conflicts], ["Live vehicles", p.vehicle_count]].map(([k, v]) => (
              <div key={k} className="bg-secondary/50 rounded-[4px] py-2"><div className="font-head font-bold">{v ?? 0}</div><div className="text-[10px] text-muted-foreground">{k}</div></div>
            ))}
          </div>
          <div className="text-[11px] font-mono-plex text-muted-foreground mb-3">Last sync {fmtDate(p.last_sync_at)} · last success {fmtDate(p.last_success_at)}</div>
          {p.last_errors?.length > 0 && <div className="text-xs text-red-400 mb-3 space-y-0.5">{p.last_errors.slice(0, 3).map((e, i) => <div key={i}>{e}</div>)}</div>}
          <div className="flex flex-wrap items-center gap-2">
            <select data-testid={`integration-group-${p.partner_key}`} value={p.dealer_group_id || ""} onChange={(e) => patch({ dealer_group_id: e.target.value || null })} className={`${inputCls} w-auto`}>
              <option value="">No dealer group</option>{groups.map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}
            </select>
            <label className="flex items-center gap-1.5 text-xs"><input type="checkbox" data-testid={`integration-sandbox-${p.partner_key}`} checked={!!p.sandbox} onChange={(e) => patch({ sandbox: e.target.checked, active: e.target.checked ? p.active : false })} /><Flask size={13} /> Sandbox (sample data)</label>
            <button data-testid={`integration-toggle-${p.partner_key}`} onClick={() => patch({ active: !p.active })} className="text-xs bg-secondary hover:bg-accent px-3 py-1.5 rounded-[4px]">{p.active ? "Deactivate" : "Activate"}</button>
            {p.active && <button data-testid={`integration-sync-${p.partner_key}`} onClick={sync} className="text-xs bg-primary text-primary-foreground px-3 py-1.5 rounded-[4px] flex items-center gap-1"><ArrowsClockwise size={12} /> Sync now</button>}
          </div>
          {p.sandbox && <p className="text-[11px] text-sky-400 mt-2">Sandbox vehicles are labelled SAMPLE and are never recommended to customers.</p>}
        </>
      )}
    </div>
  );
}

function CodeMappingForm({ reload }) {
  const [f, setF] = useState({ ldda_code: "", lpdg_code: "", vin: "" });
  const add = async () => {
    try { const { data } = await client.post("/integrations/code-mappings", { ...f, vin: f.vin || null }); toast[data.status === "conflict" ? "warning" : "success"](`Mapping ${data.status}`); setF({ ldda_code: "", lpdg_code: "", vin: "" }); reload(); } catch (e) { err(e); }
  };
  return (
    <div className="flex flex-wrap gap-2 mb-3">
      <input data-testid="map-ldda-code" placeholder="Le Don de L'Auto code" value={f.ldda_code} onChange={(e) => setF({ ...f, ldda_code: e.target.value })} className={`${inputCls} w-48`} />
      <input data-testid="map-lpdg-code" placeholder="Le Prix du Gros code" value={f.lpdg_code} onChange={(e) => setF({ ...f, lpdg_code: e.target.value })} className={`${inputCls} w-48`} />
      <input data-testid="map-vin" placeholder="VIN (optional, preferred)" value={f.vin} onChange={(e) => setF({ ...f, vin: e.target.value })} className={`${inputCls} w-56`} />
      <button data-testid="map-add-btn" onClick={add} className="text-xs bg-primary text-primary-foreground px-3 rounded-[4px]">{tr("Add mapping")}</button>
    </div>
  );
}

export default function Integrations() {
  const [items, setItems] = useState(null);
  const [maps, setMaps] = useState({ vehicle_mappings: [], code_mappings: [] });
  const [groups, setGroups] = useState([]);
  const [mstatus, setMstatus] = useState("");
  const load = useCallback(() => {
    client.get("/integrations").then((r) => setItems(r.data)).catch(() => setItems([]));
    client.get("/integrations/mappings", { params: { status: mstatus || undefined } }).then((r) => setMaps(r.data)).catch(() => {});
  }, [mstatus]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { client.get("/dealer-groups").then((r) => setGroups(r.data)).catch(() => {}); }, []);
  const resolve = async (id, action) => { try { await client.post(`/integrations/mappings/${id}/resolve`, { action }); toast.success("Conflict resolved"); load(); } catch (e) { err(e); } };
  if (!items) return <Loading />;
  const rows = [...maps.code_mappings.map((m) => ({ ...m, kind: "LDDA ↔ LPDG", ext: `${m.ldda_code} → ${m.lpdg_code}` })),
    ...maps.vehicle_mappings.map((m) => ({ ...m, kind: titleize(m.source), ext: `${m.external_vehicle_id} (${m.inventory_code || "—"})` }))];
  return (
    <div data-testid="integrations-page">
      <PageHeader title="Inventory Integrations" subtitle="Authorized partner feeds, external ID mapping and conflict review" />
      <div className="grid lg:grid-cols-3 gap-4 mb-8">{items.map((p) => <PartnerCard key={p.partner_key} p={p} groups={groups} reload={load} />)}</div>
      <div className="flex items-center justify-between mb-3">
        <h2 className="font-head font-bold text-lg">External mappings</h2>
        <select data-testid="mappings-filter-status" value={mstatus} onChange={(e) => setMstatus(e.target.value)} className={`${inputCls} w-auto`}>
          <option value="">All</option><option value="conflict">Conflicts</option><option value="unmatched">Unmatched</option><option value="active">Active</option>
        </select>
      </div>
      <CodeMappingForm reload={load} />
      <div className="border border-border rounded-[4px] bg-card p-4">
        {rows.length === 0 ? <div className="text-sm text-muted-foreground text-center py-8">No mappings yet.</div> : (
          <Table testid="mappings-table" head={["Type", "External / codes", "VIN", "Internal vehicle", "Status", "Proposed change", ""]} rows={rows.map((m) => [
            m.kind, <span className="font-mono-plex text-xs">{m.ext}</span>, <span className="font-mono-plex text-xs">{m.vin || "—"}</span>,
            <span className="font-mono-plex text-xs">{m.internal_vehicle_id ? m.internal_vehicle_id.slice(0, 8) : "—"}</span>, <Pill s={m.status} />,
            m.proposed ? <span className="text-xs font-mono-plex">{Object.entries(m.proposed).filter(([k]) => !["at", "by"].includes(k)).map(([k, v]) => `${k}: ${v ?? "—"}`).join(" · ")}</span> : "—",
            m.status === "conflict" ? (
              <div className="flex gap-2 text-xs whitespace-nowrap">
                <button data-testid={`resolve-accept-${m.id}`} onClick={() => resolve(m.id, "accept_proposed")} className="text-primary hover:underline">{tr("Accept new")}</button>
                <button data-testid={`resolve-keep-${m.id}`} onClick={() => resolve(m.id, "keep_existing")} className="hover:underline">{tr("Keep existing")}</button>
              </div>
            ) : null,
          ])} />
        )}
      </div>
    </div>
  );
}
