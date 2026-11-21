import { useEffect, useState } from "react";
import { AgreementDialog } from "@/components/sales/AgreementDialog";
import client from "@/lib/api";
import { PageHeader, Loading, Empty } from "@/components/Bits";
import { toast } from "sonner";
import {
  Plus, Buildings, Broadcast, Copy, ArrowsClockwise, Trash, CaretDown, CaretRight,
  Globe, CurrencyDollar, Database, PencilSimple,
} from "@phosphor-icons/react";

const SOURCE_TYPES = [
  { value: "csv_upload", label: "CSV upload (push)" },
  { value: "http_feed", label: "HTTP feed (CSV/XML/JSON URL)" },
  { value: "scraper", label: "Website scraper" },
  { value: "api", label: "API connection" },
];

const STATUS_COLOR = {
  success: "text-green-400 border-green-500/30 bg-green-500/10",
  failed: "text-red-400 border-red-500/30 bg-red-500/10",
  idle: "text-zinc-400 border-zinc-500/30 bg-zinc-500/10",
  never: "text-zinc-400 border-zinc-500/30 bg-zinc-500/10",
};

function SourceRow({ src, onChanged }) {
  const run = async () => {
    try {
      const { data } = await client.post(`/inventory-sources/${src.id}/run`);
      if (data.skipped_reason === "stub") toast.info(data.message);
      else if (data.skipped_reason === "push") toast.info(data.message);
      else toast.success(`Synced: +${data.imported} new, ${data.updated} updated, ${data.deactivated} hidden`);
      onChanged();
    } catch (e) { toast.error(e.response?.data?.detail || "Sync failed"); }
  };
  const del = async () => {
    if (!window.confirm(`Delete source "${src.name}"?`)) return;
    await client.delete(`/inventory-sources/${src.id}`); onChanged();
  };
  const copy = (t) => { navigator.clipboard.writeText(t); toast.success("Copied"); };

  return (
    <div data-testid="source-row" className="border border-border rounded-[4px] bg-background p-3">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-2">
          <Database size={15} className="text-primary" />
          <span className="text-sm font-medium">{src.name}</span>
          <span className="text-[11px] font-mono-plex text-muted-foreground border border-border rounded px-1.5 py-0.5">{src.type}</span>
          <span className={`text-[11px] font-mono-plex px-1.5 py-0.5 rounded border ${STATUS_COLOR[src.last_status] || STATUS_COLOR.never}`}>{src.last_status}</span>
        </div>
        <div className="flex items-center gap-2">
          {src.type !== "csv_upload" && (
            <button data-testid="run-source-btn" onClick={run} className="flex items-center gap-1 text-xs bg-secondary hover:bg-accent px-2.5 py-1.5 rounded-[4px] transition-colors"><ArrowsClockwise size={13} /> Run now</button>
          )}
          <button data-testid="delete-source-btn" onClick={del} className="text-muted-foreground hover:text-red-400 p-1.5 transition-colors"><Trash size={14} /></button>
        </div>
      </div>

      {src.type === "csv_upload" && src.push_url && (
        <div className="mt-2 space-y-1">
          <div className="flex items-center gap-2">
            <input readOnly value={src.push_url} className="flex-1 rounded-[4px] border border-input bg-card px-2 py-1 text-[11px] font-mono-plex outline-none" />
            <button onClick={() => copy(src.push_url)} className="flex items-center gap-1 text-[11px] bg-secondary hover:bg-accent px-2 py-1 rounded-[4px]"><Copy size={12} /> Incremental</button>
            <button onClick={() => copy(src.full_push_url)} className="flex items-center gap-1 text-[11px] bg-secondary hover:bg-accent px-2 py-1 rounded-[4px]"><Copy size={12} /> Full</button>
          </div>
        </div>
      )}
      {src.type === "http_feed" && (
        <div className="mt-1.5 text-[11px] text-muted-foreground font-mono-plex truncate">URL: {src.config?.url || "— not set —"}</div>
      )}
      {(src.type === "scraper" || src.type === "api") && (
        <div className="mt-1.5 text-[11px] text-muted-foreground">Framework ready — connect a {src.type} adapter when the source is available.</div>
      )}
      {(src.last_stats && (src.last_stats.imported || src.last_stats.updated || src.last_stats.deactivated)) ? (
        <div className="mt-1.5 text-[11px] text-muted-foreground flex gap-3">
          <span className="text-green-400">+{src.last_stats.imported} new</span>
          <span className="text-blue-400">{src.last_stats.updated} updated</span>
          {src.last_stats.deactivated > 0 && <span className="text-zinc-400">{src.last_stats.deactivated} hidden</span>}
          {src.last_run_at && <span>{new Date(src.last_run_at).toLocaleString()}</span>}
        </div>
      ) : null}
    </div>
  );
}

function AddSourceForm({ groupId, onAdded }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ name: "", type: "csv_upload", url: "", format: "csv" });
  const save = async () => {
    if (!form.name) { toast.error("Name required"); return; }
    const config = form.type === "http_feed" ? { url: form.url, format: form.format } :
      form.type === "scraper" ? { start_url: form.url } : {};
    try {
      await client.post("/inventory-sources", { dealer_group_id: groupId, name: form.name, type: form.type, config });
      toast.success("Source added"); setOpen(false); setForm({ name: "", type: "csv_upload", url: "", format: "csv" }); onAdded();
    } catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
  };
  if (!open) return (
    <button data-testid="add-source-btn" onClick={() => setOpen(true)} className="flex items-center gap-1.5 text-xs text-primary hover:underline mt-1"><Plus size={13} weight="bold" /> Add inventory source</button>
  );
  return (
    <div className="border border-primary/30 rounded-[4px] bg-primary/5 p-3 space-y-2">
      <div className="grid grid-cols-2 gap-2">
        <input data-testid="source-name-input" placeholder="Source name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="rounded-[4px] border border-input bg-card px-2 py-1.5 text-sm outline-none focus:border-primary" />
        <select data-testid="source-type-select" value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })} className="rounded-[4px] border border-input bg-card px-2 py-1.5 text-sm outline-none focus:border-primary">
          {SOURCE_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
        </select>
      </div>
      {(form.type === "http_feed" || form.type === "scraper") && (
        <div className="grid grid-cols-3 gap-2">
          <input data-testid="source-url-input" placeholder={form.type === "scraper" ? "Start URL" : "Feed URL"} value={form.url} onChange={(e) => setForm({ ...form, url: e.target.value })} className="col-span-2 rounded-[4px] border border-input bg-card px-2 py-1.5 text-sm outline-none focus:border-primary" />
          {form.type === "http_feed" && (
            <select value={form.format} onChange={(e) => setForm({ ...form, format: e.target.value })} className="rounded-[4px] border border-input bg-card px-2 py-1.5 text-sm outline-none focus:border-primary">
              <option value="csv">CSV</option><option value="xml">XML</option><option value="json">JSON</option>
            </select>
          )}
        </div>
      )}
      <div className="flex gap-2">
        <button data-testid="save-source-btn" onClick={save} className="text-xs bg-primary text-primary-foreground px-3 py-1.5 rounded-[4px] font-semibold hover:opacity-90">Add source</button>
        <button onClick={() => setOpen(false)} className="text-xs bg-secondary px-3 py-1.5 rounded-[4px] hover:bg-accent">Cancel</button>
      </div>
    </div>
  );
}

function GroupCard({ group, onChanged }) {
  const [expanded, setExpanded] = useState(false);
  const [sources, setSources] = useState(null);
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState(group);

  const loadSources = () => client.get("/inventory-sources", { params: { dealer_group_id: group.id } }).then((r) => setSources(r.data));
  useEffect(() => { if (expanded && sources === null) loadSources(); }, [expanded]);

  const [agreement, setAgreement] = useState(false);
  const saveEdit = async () => {
    try {
      await client.patch(`/dealer-groups/${group.id}`, {
        name: form.name, website: form.website, referral_amount: Number(form.referral_amount) || 0,
        referral_program: form.referral_program, status: form.status,
        notification_email: form.notification_email || null,
      });
      toast.success("Updated"); setEditing(false); onChanged();
    } catch { toast.error("Update failed"); }
  };
  const del = async () => {
    if (!window.confirm(`Delete dealer group "${group.name}"? Its sources will be removed.`)) return;
    try { await client.delete(`/dealer-groups/${group.id}`); onChanged(); }
    catch (e) { toast.error(e.response?.data?.detail || "Delete failed"); }
  };

  return (
    <div data-testid="dealer-group-card" className="border border-border rounded-[4px] bg-card">
      <div className="p-4 flex items-start justify-between gap-3">
        <div className="flex items-start gap-3 min-w-0">
          <div className="w-9 h-9 rounded-[4px] bg-primary/15 flex items-center justify-center shrink-0"><Buildings size={18} className="text-primary" /></div>
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-semibold">{group.name}</span>
              {group.is_default && <span className="text-[11px] font-mono-plex text-muted-foreground border border-border rounded px-1.5 py-0.5">default</span>}
              <span className={`text-[11px] font-mono-plex px-1.5 py-0.5 rounded border ${group.status === "active" ? "text-green-400 border-green-500/30 bg-green-500/10" : "text-zinc-400 border-zinc-500/30 bg-zinc-500/10"}`}>{group.status}</span>
            </div>
            <div className="flex items-center gap-3 text-xs text-muted-foreground mt-1 flex-wrap">
              {group.website && <span className="flex items-center gap-1"><Globe size={12} /> {group.website.replace(/^https?:\/\//, "")}</span>}
              <span data-testid="group-commission-summary" className="flex items-center gap-1"><CurrencyDollar size={12} /> {group.commission_model === "volume" ? `Volume · ${(group.volume_tiers || []).length} tiers · ${group.volume_method || "incremental"}` : group.commission_model === "percent" ? `${group.commission_rate || 0}% of sale` : `$${group.commission_rate || group.referral_amount || 0} / sale`}{group.referral_program ? ` · ${group.referral_program}` : ""}</span>
              <span>{group.vehicle_count} vehicles</span>
              <span>{group.source_count} source(s)</span>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <button data-testid="agreement-btn" onClick={() => setAgreement(true)} className="text-xs text-primary hover:underline px-1.5">Commission{group.commission_model === "volume" ? " · tiers" : ""}</button>
          <button data-testid="edit-group-btn" onClick={() => { setForm(group); setEditing(!editing); }} className="text-muted-foreground hover:text-foreground p-1.5"><PencilSimple size={15} /></button>
          {!group.is_default && <button data-testid="delete-group-btn" onClick={del} className="text-muted-foreground hover:text-red-400 p-1.5"><Trash size={15} /></button>}
          <button data-testid="expand-group-btn" onClick={() => setExpanded(!expanded)} className="text-muted-foreground hover:text-foreground p-1.5">{expanded ? <CaretDown size={16} /> : <CaretRight size={16} />}</button>
        </div>
      </div>

      {agreement && <AgreementDialog group={group} onClose={() => setAgreement(false)} onSaved={() => { setAgreement(false); onChanged(); }} />}
      {editing && (
        <div className="px-4 pb-4 grid grid-cols-2 gap-2 border-t border-border pt-3">
          <input placeholder="Name" value={form.name || ""} onChange={(e) => setForm({ ...form, name: e.target.value })} className="rounded-[4px] border border-input bg-background px-2 py-1.5 text-sm outline-none focus:border-primary" />
          <input placeholder="Website" value={form.website || ""} onChange={(e) => setForm({ ...form, website: e.target.value })} className="rounded-[4px] border border-input bg-background px-2 py-1.5 text-sm outline-none focus:border-primary" />
          <input type="number" placeholder="Referral amount ($)" value={form.referral_amount ?? ""} onChange={(e) => setForm({ ...form, referral_amount: e.target.value })} className="rounded-[4px] border border-input bg-background px-2 py-1.5 text-sm outline-none focus:border-primary" />
          <input placeholder="Referral program (e.g. Mon Coéquipier)" value={form.referral_program || ""} onChange={(e) => setForm({ ...form, referral_program: e.target.value })} className="rounded-[4px] border border-input bg-background px-2 py-1.5 text-sm outline-none focus:border-primary" />
          <select value={form.status || "active"} onChange={(e) => setForm({ ...form, status: e.target.value })} className="rounded-[4px] border border-input bg-background px-2 py-1.5 text-sm outline-none focus:border-primary"><option value="active">active</option><option value="paused">paused</option></select>
          <input data-testid="group-notification-email" type="email" placeholder="Referral notification email" value={form.notification_email || ""} onChange={(e) => setForm({ ...form, notification_email: e.target.value })} className="rounded-[4px] border border-input bg-background px-2 py-1.5 text-sm outline-none focus:border-primary" />
          <button data-testid="save-group-btn" onClick={saveEdit} className="bg-primary text-primary-foreground rounded-[4px] text-sm font-semibold hover:opacity-90">Save</button>
        </div>
      )}

      {expanded && (
        <div className="px-4 pb-4 border-t border-border pt-3 space-y-2">
          <div className="text-xs font-mono-plex uppercase tracking-wider text-muted-foreground">Inventory sources</div>
          {sources === null ? <Loading /> : sources.length === 0 ? <div className="text-xs text-muted-foreground">No sources yet.</div> :
            sources.map((s) => <SourceRow key={s.id} src={s} onChanged={() => { loadSources(); onChanged(); }} />)}
          <AddSourceForm groupId={group.id} onAdded={() => { loadSources(); onChanged(); }} />
        </div>
      )}
    </div>
  );
}

export default function Partners() {
  const [groups, setGroups] = useState(null);
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({ name: "", website: "", referral_amount: "", referral_program: "" });

  const load = () => client.get("/dealer-groups").then((r) => setGroups(r.data));
  useEffect(() => { load(); }, []);

  const create = async () => {
    if (!form.name) { toast.error("Name required"); return; }
    try {
      await client.post("/dealer-groups", { ...form, referral_amount: Number(form.referral_amount) || 0 });
      toast.success("Dealer group added"); setAdding(false);
      setForm({ name: "", website: "", referral_amount: "", referral_program: "" }); load();
    } catch { toast.error("Failed to create"); }
  };

  return (
    <div>
      <PageHeader title="Partners" subtitle={groups ? `${groups.length} dealer group(s)` : ""}>
        <button data-testid="add-group-btn" onClick={() => setAdding(!adding)} className="flex items-center gap-1.5 text-xs bg-primary text-primary-foreground px-3 py-2 rounded-[4px] hover:opacity-90 transition-opacity"><Plus size={14} weight="bold" /> Add dealer group</button>
      </PageHeader>

      <p className="text-sm text-muted-foreground mb-4 max-w-3xl">Connect dealer groups and their inventory sources. Vehicle data is used internally by the AI to match qualified buyers — it is never published on your public site. Swap a scraper for a clean feed or API later without rebuilding anything.</p>

      {adding && (
        <div className="border border-primary/30 bg-primary/5 rounded-[4px] p-4 mb-4 grid grid-cols-2 gap-2">
          <input data-testid="group-name-input" placeholder="Dealer group name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="rounded-[4px] border border-input bg-card px-2 py-1.5 text-sm outline-none focus:border-primary" />
          <input placeholder="Website (optional)" value={form.website} onChange={(e) => setForm({ ...form, website: e.target.value })} className="rounded-[4px] border border-input bg-card px-2 py-1.5 text-sm outline-none focus:border-primary" />
          <input type="number" placeholder="Referral amount ($)" value={form.referral_amount} onChange={(e) => setForm({ ...form, referral_amount: e.target.value })} className="rounded-[4px] border border-input bg-card px-2 py-1.5 text-sm outline-none focus:border-primary" />
          <input placeholder="Referral program (e.g. Mon Coéquipier)" value={form.referral_program} onChange={(e) => setForm({ ...form, referral_program: e.target.value })} className="rounded-[4px] border border-input bg-card px-2 py-1.5 text-sm outline-none focus:border-primary" />
          <button data-testid="create-group-btn" onClick={create} className="bg-primary text-primary-foreground rounded-[4px] text-sm font-semibold hover:opacity-90">Create</button>
        </div>
      )}

      {!groups ? <Loading /> : groups.length === 0 ? <Empty label="No dealer groups yet." /> : (
        <div className="space-y-3">{groups.map((g) => <GroupCard key={g.id} group={g} onChanged={load} />)}</div>
      )}
    </div>
  );
}
