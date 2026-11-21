import { useState } from "react";
import client from "@/lib/api";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { inputCls } from "@/components/profile/shared";

const blankTier = (min) => ({ name: "", min_sales: min, max_sales: "", amount_per_sale: 0, percent_rate: 0 });

export function AgreementDialog({ group, onClose, onSaved }) {
  const [f, setF] = useState({
    commission_model: group.commission_model || "fixed", commission_rate: group.commission_rate || 0,
    commission_currency: group.commission_currency || "CAD", volume_period: group.volume_period || "monthly",
    volume_method: group.volume_method || "incremental", effective_date: "",
    volume_tiers: (group.volume_tiers || []).map((t) => ({ ...t, max_sales: t.max_sales ?? "" })),
  });
  const tiers = f.volume_tiers;
  const setTier = (i, k, v) => setF({ ...f, volume_tiers: tiers.map((t, j) => (j === i ? { ...t, [k]: v } : t)) });
  const save = async () => {
    const body = { ...f, commission_rate: Number(f.commission_rate) || 0, effective_date: f.effective_date || null,
      volume_tiers: tiers.map((t) => ({ name: t.name || null, min_sales: Number(t.min_sales), max_sales: t.max_sales === "" ? null : Number(t.max_sales),
        amount_per_sale: Number(t.amount_per_sale) || 0, percent_rate: Number(t.percent_rate) || 0 })) };
    try { await client.put(`/dealer-groups/${group.id}/commission-agreement`, body); toast.success("Agreement saved — applies to sales verified from now on"); onSaved(); }
    catch (e) { toast.error(typeof e.response?.data?.detail === "string" ? e.response.data.detail : "Please check the tiers"); }
  };
  const num = (v, on, id) => <input data-testid={id} type="number" value={v} onChange={(e) => on(e.target.value)} className={inputCls} />;
  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="dark bg-card text-foreground border-border max-w-2xl" data-testid="agreement-dialog">
        <DialogHeader><DialogTitle>Commission agreement · {group.name}{group.agreement_version ? ` (v${group.agreement_version})` : ""}</DialogTitle></DialogHeader>
        <div className="grid grid-cols-3 gap-3">
          <div><label className="text-xs text-muted-foreground">Model</label>
            <select data-testid="agreement-model" value={f.commission_model} onChange={(e) => setF({ ...f, commission_model: e.target.value })} className={`${inputCls} mt-1`}>
              <option value="fixed">Fixed $ / sale</option><option value="percent">% of sale</option><option value="volume">Volume tiers</option></select></div>
          {f.commission_model !== "volume" && <div><label className="text-xs text-muted-foreground">{f.commission_model === "percent" ? "Rate (%)" : "Amount ($)"}</label>{num(f.commission_rate, (v) => setF({ ...f, commission_rate: v }), "agreement-rate")}</div>}
          <div><label className="text-xs text-muted-foreground">Effective date</label>
            <input data-testid="agreement-effective" type="date" value={f.effective_date} onChange={(e) => setF({ ...f, effective_date: e.target.value })} className={`${inputCls} mt-1`} /></div>
        </div>
        {f.commission_model === "volume" && (
          <>
            <div className="grid grid-cols-2 gap-3">
              <div><label className="text-xs text-muted-foreground">Calculation period</label>
                <select data-testid="agreement-period" value={f.volume_period} onChange={(e) => setF({ ...f, volume_period: e.target.value })} className={`${inputCls} mt-1`}><option value="monthly">Monthly</option><option value="quarterly">Quarterly</option></select></div>
              <div><label className="text-xs text-muted-foreground">Method</label>
                <select data-testid="agreement-method" value={f.volume_method} onChange={(e) => setF({ ...f, volume_method: e.target.value })} className={`${inputCls} mt-1`}><option value="incremental">Incremental — each sale paid at the tier reached</option><option value="retroactive">Retroactive — whole period lifted to tier reached</option></select></div>
            </div>
            <div className="space-y-2">
              <div className="grid grid-cols-[1fr_80px_80px_100px_80px_24px] gap-2 text-[11px] font-mono-plex uppercase text-muted-foreground"><span>Tier</span><span>From</span><span>To</span><span>$ / sale</span><span>% sale</span><span /></div>
              {tiers.map((t, i) => (
                <div key={i} data-testid="agreement-tier" className="grid grid-cols-[1fr_80px_80px_100px_80px_24px] gap-2">
                  <input value={t.name || ""} placeholder={`Tier ${i + 1}`} onChange={(e) => setTier(i, "name", e.target.value)} className={inputCls} />
                  {num(t.min_sales, (v) => setTier(i, "min_sales", v), `tier-min-${i}`)}{num(t.max_sales, (v) => setTier(i, "max_sales", v), `tier-max-${i}`)}
                  {num(t.amount_per_sale, (v) => setTier(i, "amount_per_sale", v), `tier-amount-${i}`)}{num(t.percent_rate, (v) => setTier(i, "percent_rate", v), `tier-pct-${i}`)}
                  <button onClick={() => setF({ ...f, volume_tiers: tiers.filter((_, j) => j !== i) })} className="text-red-400">×</button>
                </div>
              ))}
              <button data-testid="agreement-add-tier" onClick={() => setF({ ...f, volume_tiers: [...tiers, blankTier(tiers.length ? Number(tiers[tiers.length - 1].max_sales || 0) + 1 : 1)] })} className="text-xs text-primary hover:underline">+ Add tier</button>
            </div>
            <p className="text-xs text-muted-foreground">Leave “To” empty on the last tier for “and above”. Retroactive uplifts are added as separate adjustment lines — existing commissions are never rewritten.</p>
          </>
        )}
        <button data-testid="agreement-save" onClick={save} className="bg-primary text-primary-foreground rounded-[4px] py-2 text-sm font-semibold hover:opacity-90">Save agreement</button>
      </DialogContent>
    </Dialog>
  );
}
