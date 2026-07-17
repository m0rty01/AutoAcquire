import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import client from "@/lib/api";
import { PageHeader, Loading, Empty } from "@/components/Bits";
import { ScoreBadge, StatusBadge, titleize } from "@/components/ui/badges";
import { MagnifyingGlass } from "@phosphor-icons/react";

const BANDS = ["", "hot", "warm", "nurture", "low"];
const STATUSES = ["", "new", "ai_qualifying", "qualified", "needs_review", "appointment_offered",
  "appointment_booked", "human_takeover", "contacted", "purchased", "disqualified"];
const SORTS = [["newest", "Newest"], ["highest_score", "Highest score"], ["recent_activity", "Recent activity"]];

export default function Leads() {
  const [data, setData] = useState(null);
  const [search, setSearch] = useState("");
  const [band, setBand] = useState("");
  const [status, setStatus] = useState("");
  const [sort, setSort] = useState("newest");
  const navigate = useNavigate();

  const load = () => {
    const params = { sort, page_size: 100 };
    if (band) params.score_band = band;
    if (status) params.status = status;
    if (search) params.search = search;
    client.get("/leads", { params }).then((r) => setData(r.data));
  };

  useEffect(load, [band, status, sort]);
  useEffect(() => { const t = setTimeout(load, 350); return () => clearTimeout(t); }, [search]);

  return (
    <div>
      <PageHeader title="Leads" subtitle={data ? `${data.total} total leads` : ""} />

      <div className="flex flex-wrap gap-3 mb-4">
        <div className="relative flex-1 min-w-[200px]">
          <MagnifyingGlass size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <input data-testid="lead-search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search seller, vehicle, phone…"
            className="w-full pl-9 pr-3 py-2 rounded-[4px] border border-input bg-card text-sm outline-none focus:border-primary transition-colors duration-200" />
        </div>
        <Select testid="filter-band" value={band} onChange={setBand} options={BANDS} placeholder="All bands" />
        <Select testid="filter-status" value={status} onChange={setStatus} options={STATUSES} placeholder="All statuses" />
        <Select testid="filter-sort" value={sort} onChange={setSort} options={SORTS.map((s) => s[0])} labels={Object.fromEntries(SORTS)} />
      </div>

      {!data ? <Loading /> : data.items.length === 0 ? <Empty label="No leads match your filters" /> : (
        <div className="border border-border rounded-[4px] bg-card overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs font-mono-plex uppercase tracking-wider text-muted-foreground">
                <th className="p-3">Seller</th>
                <th className="p-3 hidden md:table-cell">Vehicle</th>
                <th className="p-3 hidden sm:table-cell">Intent</th>
                <th className="p-3">Score</th>
                <th className="p-3">Status</th>
                <th className="p-3 hidden lg:table-cell">Appt</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((l) => (
                <tr key={l.id} data-testid={`lead-row-${l.id}`} onClick={() => navigate(`/app/leads/${l.id}`)}
                  className="border-b border-border last:border-0 hover:bg-secondary cursor-pointer transition-colors duration-150">
                  <td className="p-3 font-medium">{l.seller_name}{l.requires_human_review && <span className="ml-2 text-[#FBBF24] text-xs">●</span>}</td>
                  <td className="p-3 hidden md:table-cell font-mono-plex text-muted-foreground">{l.vehicle_label}</td>
                  <td className="p-3 hidden sm:table-cell text-muted-foreground">{titleize(l.primary_intent || "—")}</td>
                  <td className="p-3"><ScoreBadge score={l.score} band={l.score_band} /></td>
                  <td className="p-3"><StatusBadge status={l.status} /></td>
                  <td className="p-3 hidden lg:table-cell text-muted-foreground">{l.appointment_status ? titleize(l.appointment_status) : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function Select({ value, onChange, options, labels, placeholder, testid }) {
  return (
    <select data-testid={testid} value={value} onChange={(e) => onChange(e.target.value)}
      className="rounded-[4px] border border-input bg-card px-3 py-2 text-sm outline-none focus:border-primary transition-colors duration-200">
      {options.map((o) => (
        <option key={o} value={o}>{o === "" ? placeholder : (labels ? labels[o] : titleize(o))}</option>
      ))}
    </select>
  );
}
