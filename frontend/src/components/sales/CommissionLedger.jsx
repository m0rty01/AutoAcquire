import { useEffect, useState, useCallback } from "react";
import client from "@/lib/api";
import { toast } from "sonner";
import { DownloadSimple } from "@phosphor-icons/react";
import { Pill, Table, inputCls, money } from "@/components/profile/shared";

export function CommissionLedger() {
  const [groups, setGroups] = useState([]);
  const [f, setF] = useState({ date_from: "", date_to: "", dealer_group_id: "", commission_status: "", sale_status: "" });
  const [data, setData] = useState(null);
  const params = Object.fromEntries(Object.entries(f).filter(([, v]) => v));
  const load = useCallback(() => { client.get("/commissions/ledger", { params }).then((r) => setData(r.data)).catch(() => setData({ rows: [] })); }, [JSON.stringify(params)]); // eslint-disable-line
  useEffect(() => { load(); }, [load]);
  useEffect(() => { client.get("/dealer-groups").then((r) => setGroups(r.data)).catch(() => {}); }, []);

  const download = async (format) => {
    try {
      const r = await client.get("/commissions/export", { params: { ...params, format }, responseType: "blob" });
      const url = URL.createObjectURL(r.data);
      const a = document.createElement("a");
      a.href = url; a.download = `autonova-commissions-${new Date().toISOString().slice(0, 10)}.${format}`; a.click();
      URL.revokeObjectURL(url);
    } catch { toast.error("Export failed"); }
  };
  const sel = (k, opts, all) => (
    <select data-testid={`ledger-filter-${k}`} value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} className={`${inputCls} w-auto`}>
      <option value="">{all}</option>{opts.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
    </select>
  );
  return (
    <div className="mt-8" data-testid="commission-ledger">
      <div className="flex flex-wrap items-end justify-between gap-3 mb-3">
        <div><h2 className="font-head font-bold text-lg">Commission ledger</h2>
          {data && <p className="text-xs text-muted-foreground font-mono-plex" data-testid="ledger-total">{data.rows.length} rows · commission {money(data.total_commission)} (excl. cancelled)</p>}</div>
        <div className="flex gap-2">
          <button data-testid="export-csv-btn" onClick={() => download("csv")} className="flex items-center gap-1.5 text-xs bg-secondary hover:bg-accent px-3 py-2 rounded-[4px]"><DownloadSimple size={14} /> CSV</button>
          <button data-testid="export-pdf-btn" onClick={() => download("pdf")} className="flex items-center gap-1.5 text-xs bg-secondary hover:bg-accent px-3 py-2 rounded-[4px]"><DownloadSimple size={14} /> PDF</button>
        </div>
      </div>
      <div className="flex flex-wrap gap-2 mb-3">
        <input data-testid="ledger-filter-date_from" type="date" value={f.date_from} onChange={(e) => setF({ ...f, date_from: e.target.value })} className={`${inputCls} w-auto`} />
        <input data-testid="ledger-filter-date_to" type="date" value={f.date_to} onChange={(e) => setF({ ...f, date_to: e.target.value })} className={`${inputCls} w-auto`} />
        {sel("dealer_group_id", groups.map((g) => [g.id, g.name]), "All dealer groups")}
        {sel("commission_status", [["payable", "Payable"], ["paid", "Paid"], ["cancelled", "Cancelled"]], "All commission statuses")}
        {sel("sale_status", [["verified", "Verified sales"], ["reported", "Reported"], ["rejected", "Rejected"]], "All sales")}
      </div>
      <div className="border border-border rounded-[4px] bg-card p-4">
        {!data ? null : data.rows.length === 0 ? <div className="text-sm text-muted-foreground text-center py-8">No rows for these filters.</div> : (
          <Table testid="ledger-table" head={["Sale date", "Verified", "Vehicle", "Dealership", "Sale $", "Model", "Type", "Commission", "Status", "Basis"]} rows={data.rows.map((r) => [
            r.sale_date, r.verification_date || "—", r.vehicle || "—", r.dealership || "—", money(r.sale_amount), r.commission_model || "—",
            r.commission_type || "—", money(r.commission_amount), r.commission_status ? <Pill s={r.commission_status} /> : "—",
            <span className="text-xs text-muted-foreground">{r.basis}</span>,
          ])} />
        )}
      </div>
    </div>
  );
}
