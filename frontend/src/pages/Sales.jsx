import { useEffect, useState } from "react";
import client from "@/lib/api";
import { PageHeader, Loading, Empty } from "@/components/Bits";
import { useAuth } from "@/context/AuthContext";
import { CommissionLedger } from "@/components/sales/CommissionLedger";
import { toast } from "sonner";
import { CurrencyDollar, CheckCircle, Clock, SealCheck, XCircle } from "@phosphor-icons/react";

const SALE_STYLE = {
  reported: "text-amber-400 border-amber-500/30 bg-amber-500/10",
  verified: "text-green-400 border-green-500/30 bg-green-500/10",
  rejected: "text-red-400 border-red-500/30 bg-red-500/10",
};

function Stat({ icon: Icon, label, value }) {
  return (
    <div className="border border-border rounded-[4px] bg-card p-4 flex items-center gap-3">
      <div className="w-9 h-9 rounded-[4px] bg-primary/15 flex items-center justify-center"><Icon size={18} className="text-primary" /></div>
      <div><div className="text-xl font-bold font-head">{value}</div><div className="text-xs text-muted-foreground">{label}</div></div>
    </div>
  );
}

export default function Sales() {
  const { user } = useAuth();
  const finance = ["platform_admin", "dealership_admin", "dealership_manager", "platform_support"].includes(user?.role);
  const [sales, setSales] = useState(null);
  const [report, setReport] = useState(null);
  const [referrals, setReferrals] = useState([]);
  const [form, setForm] = useState({ referral_id: "", sale_amount: "", vehicle_vin: "" });

  const load = () => Promise.all([
    client.get("/sales"),
    client.get("/commissions/report").catch(() => ({ data: {} })),
    client.get("/referrals"),
  ]).then(([s, r, rf]) => { setSales({ ...s.data, report: r.data }); setReferrals(rf.data.referrals || []); });
  useEffect(() => { load(); }, []);

  const reportSale = async () => {
    if (!form.referral_id) { toast.error("Select a referral"); return; }
    try {
      await client.post("/sales", { referral_id: form.referral_id, sale_amount: form.sale_amount ? Number(form.sale_amount) : null, vehicle_vin: form.vehicle_vin || null });
      toast.success("Sale reported — pending verification"); setReport(false); setForm({ referral_id: "", sale_amount: "", vehicle_vin: "" }); load();
    } catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
  };
  const act = async (id, action) => {
    try { await client.post(`/sales/${id}/${action}`); toast.success(`Sale ${action === "verify" ? "verified — commission generated" : "rejected"}`); load(); }
    catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
  };

  if (!sales) return <Loading />;
  const rep = sales.report || {};
  const eligible = referrals.filter((r) => !["lost"].includes(r.status));

  return (
    <div>
      <PageHeader title="Sales & Commission" subtitle={`${rep.verified_sales || 0} verified`}>
        <button data-testid="report-sale-btn" onClick={() => setReport(!report)} className="flex items-center gap-1.5 text-xs bg-primary text-primary-foreground px-3 py-2 rounded-[4px] hover:opacity-90 transition-opacity"><CurrencyDollar size={14} weight="bold" /> Report a sale</button>
      </PageHeader>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-5">
        <Stat icon={Clock} label="Referrals" value={rep.total_referrals || 0} />
        <Stat icon={SealCheck} label="Verified sales" value={rep.verified_sales || 0} />
        <Stat icon={CheckCircle} label="Conversion" value={`${rep.conversion_rate || 0}%`} />
        {finance && <Stat icon={CurrencyDollar} label="Commission total" value={`$${(rep.total_commission || 0).toLocaleString()}`} />}
      </div>

      {report && (
        <div className="border border-primary/30 bg-primary/5 rounded-[4px] p-4 mb-4 grid sm:grid-cols-4 gap-2 items-center">
          <select data-testid="sale-referral-select" value={form.referral_id} onChange={(e) => setForm({ ...form, referral_id: e.target.value })} className="rounded-[4px] border border-input bg-card px-2 py-1.5 text-sm outline-none focus:border-primary">
            <option value="">Select referral…</option>
            {eligible.map((r) => <option key={r.id} value={r.id}>{r.seller_name} · {r.vehicle_label || "vehicle"} · {r.dealer_group_name}</option>)}
          </select>
          <input data-testid="sale-amount-input" type="number" placeholder="Sale amount ($)" value={form.sale_amount} onChange={(e) => setForm({ ...form, sale_amount: e.target.value })} className="rounded-[4px] border border-input bg-card px-2 py-1.5 text-sm outline-none focus:border-primary" />
          <input placeholder="VIN (optional)" value={form.vehicle_vin} onChange={(e) => setForm({ ...form, vehicle_vin: e.target.value })} className="rounded-[4px] border border-input bg-card px-2 py-1.5 text-sm outline-none focus:border-primary" />
          <button data-testid="submit-sale-btn" onClick={reportSale} className="bg-primary text-primary-foreground rounded-[4px] text-sm font-semibold py-1.5 hover:opacity-90">Submit</button>
        </div>
      )}

      {sales.sales.length === 0 ? <Empty label="No sales reported yet. Report a sale from a dealership referral to track commission." /> : (
        <div className="border border-border rounded-[4px] bg-card overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="border-b border-border text-left text-xs font-mono-plex uppercase tracking-wider text-muted-foreground">
              <th className="p-3">Vehicle</th><th className="p-3">Dealer group</th><th className="p-3">Amount</th><th className="p-3">Commission</th><th className="p-3">Status</th><th className="p-3">Actions</th>
            </tr></thead>
            <tbody>
              {sales.sales.map((s) => (
                <tr key={s.id} data-testid="sale-row" className="border-b border-border last:border-0 hover:bg-secondary transition-colors">
                  <td className="p-3 font-medium">{s.vehicle_label || "—"}</td>
                  <td className="p-3">{s.dealer_group_name || "—"}</td>
                  <td className="p-3 font-mono-plex">{s.sale_amount != null ? `$${s.sale_amount.toLocaleString()}` : "—"}</td>
                  <td className="p-3 font-mono-plex">{s.commission ? `$${(s.commission.amount || 0).toLocaleString()} ${s.commission.status === "cancelled" ? "(void)" : ""}` : "—"}{s.commission_adjustments > 0 && <span className="block text-[11px] text-primary">+ ${s.commission_adjustments.toLocaleString()} tier adjustment</span>}</td>
                  <td className="p-3"><span className={`text-xs font-mono-plex px-2 py-1 rounded border ${SALE_STYLE[s.status]}`}>{s.status}</span></td>
                  <td className="p-3">
                    {s.status === "reported" && (
                      <div className="flex gap-2">
                        <button data-testid={`verify-${s.id}`} onClick={() => act(s.id, "verify")} className="flex items-center gap-1 text-xs bg-primary text-primary-foreground px-2.5 py-1 rounded-[4px] font-semibold hover:opacity-90"><SealCheck size={13} /> Verify</button>
                        <button data-testid={`reject-${s.id}`} onClick={() => act(s.id, "reject")} className="flex items-center gap-1 text-xs text-destructive hover:bg-destructive/10 px-2.5 py-1 rounded-[4px]"><XCircle size={13} /> Reject</button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {finance && <CommissionLedger />}
    </div>
  );
}
