import { useEffect, useState, useRef } from "react";
import client, { API } from "@/lib/api";
import { PageHeader, Loading, Empty } from "@/components/Bits";
import { titleize } from "@/components/ui/badges";
import { toast } from "sonner";
import { UploadSimple, DownloadSimple, Plus, MagnifyingGlass, Broadcast, ArrowsClockwise, Copy } from "@phosphor-icons/react";

export default function Inventory() {
  const [data, setData] = useState(null);
  const [search, setSearch] = useState("");
  const [importResult, setImportResult] = useState(null);
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState({ status: "available" });
  const [showFeed, setShowFeed] = useState(false);
  const [feedCfg, setFeedCfg] = useState(null);
  const fileRef = useRef(null);

  const load = () => client.get("/inventory", { params: { search, page_size: 200 } }).then((r) => setData(r.data));
  useEffect(() => { const t = setTimeout(load, 300); return () => clearTimeout(t); }, [search]);

  const loadFeed = async () => {
    if (!showFeed && !feedCfg) {
      try { const { data } = await client.get("/inventory/feed-config"); setFeedCfg(data); }
      catch { toast.error("Only dealership admins/managers can view the data feed"); return; }
    }
    setShowFeed(!showFeed);
  };

  const regenFeed = async () => {
    if (!window.confirm("Regenerate the feed key? The current connection details will stop working immediately.")) return;
    try {
      const { data } = await client.post("/inventory/feed-config/regenerate");
      setFeedCfg((c) => ({ ...c, ...data }));
      toast.success("New feed key generated");
    } catch { toast.error("Failed to regenerate key"); }
  };

  const copy = (text) => { navigator.clipboard.writeText(text); toast.success("Copied"); };

  const upload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    try {
      const { data } = await client.post("/inventory/import", fd, { headers: { "Content-Type": "multipart/form-data" } });
      setImportResult(data);
      toast.success(`Imported ${data.imported}, updated ${data.updated}`);
      load();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Import failed");
    }
    if (fileRef.current) fileRef.current.value = "";
  };

  const downloadTemplate = async () => {
    const { data } = await client.get("/inventory/template");
    const blob = new Blob([data], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = "inventory_template.csv"; a.click();
  };

  const addVehicle = async () => {
    try {
      await client.post("/inventory", {
        ...form, year: form.year ? Number(form.year) : null, price: form.price ? Number(form.price) : null,
        mileage: form.mileage ? Number(form.mileage) : null, seating_capacity: form.seating_capacity ? Number(form.seating_capacity) : null,
      });
      toast.success("Vehicle added"); setShowAdd(false); setForm({ status: "available" }); load();
    } catch { toast.error("Failed to add vehicle"); }
  };

  return (
    <div>
      <PageHeader title="Inventory" subtitle={data ? `${data.total} vehicles` : ""}>
        <div className="flex gap-2 flex-wrap">
          <button data-testid="download-template-btn" onClick={downloadTemplate} className="flex items-center gap-1.5 text-xs bg-secondary hover:bg-accent px-3 py-2 rounded-[4px] transition-colors duration-200"><DownloadSimple size={14} /> Template</button>
          <button data-testid="data-feed-btn" onClick={loadFeed} className="flex items-center gap-1.5 text-xs bg-secondary hover:bg-accent px-3 py-2 rounded-[4px] transition-colors duration-200"><Broadcast size={14} /> Data feed</button>
          <label data-testid="import-csv-btn" className="flex items-center gap-1.5 text-xs bg-secondary hover:bg-accent px-3 py-2 rounded-[4px] cursor-pointer transition-colors duration-200">
            <UploadSimple size={14} /> Import CSV
            <input ref={fileRef} type="file" accept=".csv" className="hidden" onChange={upload} />
          </label>
          <button data-testid="add-vehicle-btn" onClick={() => setShowAdd(!showAdd)} className="flex items-center gap-1.5 text-xs bg-primary text-primary-foreground px-3 py-2 rounded-[4px] hover:opacity-90 transition-opacity duration-200"><Plus size={14} weight="bold" /> Add vehicle</button>
        </div>
      </PageHeader>

      {showFeed && feedCfg && (
        <div data-testid="feed-config-panel" className="border border-primary/30 bg-primary/5 rounded-[4px] p-4 mb-4">
          <div className="flex items-start justify-between gap-3 mb-3">
            <div>
              <div className="text-sm font-semibold flex items-center gap-1.5"><Broadcast size={16} className="text-primary" /> Automated inventory feed</div>
              <p className="text-xs text-muted-foreground mt-1 max-w-2xl">Give this secure endpoint to your DMS/inventory provider. They POST the CSV export (multipart <span className="font-mono-plex">file</span> field) to this URL and inventory syncs automatically. Anyone with the URL can push, so treat it like a password.</p>
            </div>
            <button data-testid="regen-feed-btn" onClick={regenFeed} className="flex items-center gap-1.5 text-xs bg-secondary hover:bg-accent px-3 py-2 rounded-[4px] transition-colors duration-200 shrink-0"><ArrowsClockwise size={14} /> Regenerate key</button>
          </div>

          <label className="text-xs font-mono-plex uppercase tracking-wider text-muted-foreground">Push URL (HTTPS)</label>
          <div className="flex items-center gap-2 mt-1 mb-3">
            <input data-testid="feed-push-url" readOnly value={feedCfg.push_url} className="flex-1 rounded-[4px] border border-input bg-card px-2 py-1.5 text-xs font-mono-plex outline-none" />
            <button data-testid="copy-feed-url-btn" onClick={() => copy(feedCfg.push_url)} className="flex items-center gap-1.5 text-xs bg-secondary hover:bg-accent px-3 py-1.5 rounded-[4px] transition-colors duration-200"><Copy size={14} /> Copy</button>
          </div>

          <div className="text-xs text-muted-foreground font-mono-plex bg-card border border-border rounded-[4px] p-2 mb-3 overflow-x-auto">
            curl -X POST "{feedCfg.push_url}" -F "file=@inventory_export.csv"
          </div>

          {feedCfg.recent_imports?.length > 0 && (
            <div>
              <div className="text-xs font-mono-plex uppercase tracking-wider text-muted-foreground mb-1">Recent feed syncs</div>
              {feedCfg.recent_imports.map((r) => (
                <div key={r.id} data-testid="feed-import-row" className="text-xs text-muted-foreground flex gap-3 py-0.5">
                  <span className="font-mono-plex">{new Date(r.created_at).toLocaleString()}</span>
                  <span className="text-green-400">+{r.imported} new</span>
                  <span className="text-blue-400">{r.updated} updated</span>
                  {r.errors?.length > 0 && <span className="text-amber-400">{r.errors.length} skipped</span>}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {showAdd && (
        <div className="border border-border rounded-[4px] bg-card p-4 mb-4 grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[["stock_number", "Stock #"], ["make", "Make"], ["model", "Model"], ["year", "Year"], ["price", "Price"], ["mileage", "Mileage"], ["body_type", "Body type"], ["drivetrain", "Drivetrain"], ["seating_capacity", "Seats"]].map(([k, lbl]) => (
            <input key={k} data-testid={`inv-${k}`} placeholder={lbl} value={form[k] ?? ""} onChange={(e) => setForm({ ...form, [k]: e.target.value })}
              className="rounded-[4px] border border-input bg-card px-2 py-1.5 text-sm outline-none focus:border-primary transition-colors duration-200" />
          ))}
          <button data-testid="save-vehicle-inv-btn" onClick={addVehicle} className="bg-primary text-primary-foreground rounded-[4px] text-sm font-semibold hover:opacity-90 transition-opacity duration-200">Save</button>
        </div>
      )}

      {importResult?.errors?.length > 0 && (
        <div className="border border-amber-500/30 bg-amber-500/10 rounded-[4px] p-3 mb-4 text-sm">
          <div className="font-semibold text-amber-400 mb-1">{importResult.errors.length} invalid rows skipped</div>
          {importResult.errors.slice(0, 5).map((er, i) => <div key={i} className="text-xs font-mono-plex text-muted-foreground">Row {er.row}: {er.error}</div>)}
        </div>
      )}

      <div className="relative mb-4 max-w-sm">
        <MagnifyingGlass size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
        <input data-testid="inventory-search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search make, model, stock, VIN…"
          className="w-full pl-9 pr-3 py-2 rounded-[4px] border border-input bg-card text-sm outline-none focus:border-primary transition-colors duration-200" />
      </div>

      {!data ? <Loading /> : data.items.length === 0 ? <Empty label="No inventory. Import a CSV to get started." /> : (
        <div className="border border-border rounded-[4px] bg-card overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="border-b border-border text-left text-xs font-mono-plex uppercase tracking-wider text-muted-foreground">
              <th className="p-3">Stock</th><th className="p-3">Vehicle</th><th className="p-3 hidden sm:table-cell">Price</th>
              <th className="p-3 hidden md:table-cell">Mileage</th><th className="p-3 hidden lg:table-cell">Drivetrain</th><th className="p-3">Status</th>
            </tr></thead>
            <tbody>
              {data.items.map((v) => (
                <tr key={v.id} className="border-b border-border last:border-0 hover:bg-secondary transition-colors duration-150">
                  <td className="p-3 font-mono-plex text-muted-foreground">{v.stock_number}</td>
                  <td className="p-3 font-medium">{v.year} {v.make} {v.model} <span className="text-muted-foreground">{v.trim}</span></td>
                  <td className="p-3 hidden sm:table-cell">${v.price?.toLocaleString()}</td>
                  <td className="p-3 hidden md:table-cell text-muted-foreground">{v.mileage?.toLocaleString()} km</td>
                  <td className="p-3 hidden lg:table-cell text-muted-foreground">{v.drivetrain}</td>
                  <td className="p-3"><span className={`text-xs font-mono-plex px-2 py-0.5 rounded-[4px] border ${v.status === "available" ? "text-green-400 border-green-500/30 bg-green-500/10" : "text-zinc-400 border-zinc-500/30 bg-zinc-500/10"}`}>{titleize(v.status)}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
