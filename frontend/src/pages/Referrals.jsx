import { useEffect, useState } from "react";
import client from "@/lib/api";
import { PageHeader, Loading, Empty } from "@/components/Bits";
import { toast } from "sonner";
import { HandArrowDown, CheckCircle, Clock } from "@phosphor-icons/react";

const STATUS_STYLE = {
  identified: "text-zinc-400 border-zinc-500/30 bg-zinc-500/10",
  sent: "text-blue-400 border-blue-500/30 bg-blue-500/10",
  accepted: "text-indigo-400 border-indigo-500/30 bg-indigo-500/10",
  converted: "text-amber-400 border-amber-500/30 bg-amber-500/10",
  paid: "text-green-400 border-green-500/30 bg-green-500/10",
  lost: "text-red-400 border-red-500/30 bg-red-500/10",
};

function Stat({ icon: Icon, label, value }) {
  return (
    <div className="border border-border rounded-[4px] bg-card p-4 flex items-center gap-3">
      <div className="w-9 h-9 rounded-[4px] bg-primary/15 flex items-center justify-center"><Icon size={18} className="text-primary" /></div>
      <div>
        <div className="text-xl font-bold font-head">{value}</div>
        <div className="text-xs text-muted-foreground">{label}</div>
      </div>
    </div>
  );
}

export default function Referrals() {
  const [data, setData] = useState(null);
  const [statuses, setStatuses] = useState([]);
  const [editRef, setEditRef] = useState({});

  const load = () => client.get("/referrals").then((r) => { setData(r.data); setStatuses(r.data.statuses); });
  useEffect(() => { load(); }, []);

  const setStatus = async (id, status) => {
    try { await client.patch(`/referrals/${id}`, { status }); toast.success(`Marked ${status}`); load(); }
    catch { toast.error("Update failed"); }
  };
  const saveRef = async (id) => {
    try { await client.patch(`/referrals/${id}`, { external_reference: editRef[id] }); toast.success("Reference saved"); load(); }
    catch { toast.error("Save failed"); }
  };

  if (!data) return <Loading />;
  const { referrals, totals } = data;

  return (
    <div>
      <PageHeader title="Referrals" subtitle={`${totals.count} total`} />

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-5">
        <Stat icon={Clock} label="Pipeline value" value={`$${(totals.pipeline || 0).toLocaleString()}`} />
        <Stat icon={CheckCircle} label="Commission earned (paid)" value={`$${(totals.earned || 0).toLocaleString()}`} />
        <Stat icon={HandArrowDown} label="Total referrals" value={totals.count} />
      </div>

      {referrals.length === 0 ? <Empty label="No referrals yet. They appear automatically when the AI matches a qualified buyer to a dealer group's inventory." /> : (
        <div className="border border-border rounded-[4px] bg-card overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="border-b border-border text-left text-xs font-mono-plex uppercase tracking-wider text-muted-foreground">
              <th className="p-3">Customer</th><th className="p-3">Dealer group</th><th className="p-3 hidden md:table-cell">Vehicle</th>
              <th className="p-3">Commission</th><th className="p-3 hidden lg:table-cell">Mon Coéquipier ref</th><th className="p-3">Status</th>
            </tr></thead>
            <tbody>
              {referrals.map((r) => (
                <tr key={r.id} data-testid="referral-row" className="border-b border-border last:border-0 hover:bg-secondary transition-colors">
                  <td className="p-3 font-medium">{r.seller_name}</td>
                  <td className="p-3">{r.dealer_group_name || "—"}</td>
                  <td className="p-3 hidden md:table-cell text-muted-foreground">{r.vehicle_label || "—"}</td>
                  <td className="p-3 font-mono-plex">${(r.amount || 0).toLocaleString()}</td>
                  <td className="p-3 hidden lg:table-cell">
                    <div className="flex items-center gap-1">
                      <input data-testid="referral-ref-input" value={editRef[r.id] ?? r.external_reference ?? ""} onChange={(e) => setEditRef({ ...editRef, [r.id]: e.target.value })}
                        placeholder="ref #" className="w-28 rounded-[4px] border border-input bg-background px-2 py-1 text-xs outline-none focus:border-primary" />
                      {(editRef[r.id] !== undefined && editRef[r.id] !== (r.external_reference ?? "")) && (
                        <button data-testid="save-ref-btn" onClick={() => saveRef(r.id)} className="text-[11px] bg-secondary hover:bg-accent px-2 py-1 rounded-[4px]">Save</button>
                      )}
                    </div>
                  </td>
                  <td className="p-3">
                    <select data-testid="referral-status-select" value={r.status} onChange={(e) => setStatus(r.id, e.target.value)}
                      className={`text-xs font-mono-plex px-2 py-1 rounded-[4px] border outline-none cursor-pointer ${STATUS_STYLE[r.status] || STATUS_STYLE.identified}`}>
                      {statuses.map((s) => <option key={s} value={s} className="bg-card text-foreground">{s}</option>)}
                    </select>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
