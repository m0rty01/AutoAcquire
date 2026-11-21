import { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate, useSearchParams } from "react-router-dom";
import client from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Loading } from "@/components/Bits";
import { tr } from "@/lib/adminI18n";
import { ScoreBadge, StatusBadge, titleize } from "@/components/ui/badges";
import { ArrowLeft, PencilSimple, ChatsCircle } from "@phosphor-icons/react";
import { OverviewTab, PreferencesTab, ConversationTab } from "@/components/profile/TabsA";
import { ActivitiesTab, AppointmentsTab, TestDrivesTab, ReferralsTab, SalesTab } from "@/components/profile/TabsB";
import { CommunicationsTab, ConsentTab } from "@/components/profile/TabsC";
import { ProfileActions } from "@/components/profile/ProfileActions";
import { EditCustomer } from "@/components/profile/EditCustomer";

const TABS = [
  ["overview", "Overview", OverviewTab], ["preferences", "Vehicle Preferences", PreferencesTab],
  ["conversation", "Conversation History", ConversationTab], ["activities", "Activities", ActivitiesTab],
  ["appointments", "Appointments", AppointmentsTab], ["test-drives", "Test Drives", TestDrivesTab],
  ["referrals", "Referrals", ReferralsTab], ["sales", "Sales", SalesTab],
  ["communications", "Communications", CommunicationsTab], ["consent", "Consent & Privacy", ConsentTab],
];
const COUNT = { activities: "activities", appointments: "appointments", "test-drives": "test_drives", referrals: "referrals", sales: "sales", communications: "communications" };

export default function CustomerProfile() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") || "overview";
  const [p, setP] = useState(null);
  const [error, setError] = useState(null);
  const [editing, setEditing] = useState(false);
  const load = useCallback(() => client.get(`/leads/${id}/profile`).then((r) => setP(r.data))
    .catch((e) => setError(e.response?.status === 403 ? "This customer isn't assigned to you." : "Customer not found.")), [id]);
  useEffect(() => { load(); }, [load]);

  if (error) return <div data-testid="profile-error" className="text-sm text-muted-foreground py-16 text-center">{error}</div>;
  if (!p) return <Loading />;
  const readOnly = user?.role === "platform_support";
  const name = `${p.customer.first_name || ""} ${p.customer.last_name || ""}`.trim() || "Anonymous customer";
  const Active = (TABS.find((t) => t[0] === tab) || TABS[0])[2];

  return (
    <div data-testid="customer-profile">
      <button data-testid="profile-back-btn" onClick={() => navigate(-1)} className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground mb-4 transition-colors">
        <ArrowLeft size={16} /> Back
      </button>
      <div className="flex flex-wrap items-start justify-between gap-4 mb-6">
        <div>
          <div className="text-[11px] font-mono-plex uppercase tracking-[0.2em] text-muted-foreground">{tr("Customer profile")}</div>
          <h1 data-testid="profile-name" className="font-head font-black text-3xl sm:text-4xl tracking-tight mt-1">{name}</h1>
          <div className="flex items-center gap-2 mt-2 flex-wrap">
            <ScoreBadge score={p.lead.score} band={p.lead.score_band} />
            <StatusBadge status={p.lead.status} />
            <span data-testid="profile-stage" className="text-xs font-mono-plex text-primary border border-primary/30 bg-primary/10 rounded-[4px] px-2 py-0.5">{titleize(p.stage)}</span>
          </div>
        </div>
        <div className="flex gap-2">
          {!readOnly && <button data-testid="edit-customer-btn" onClick={() => setEditing(true)} className="flex items-center gap-1.5 text-xs bg-secondary hover:bg-accent px-3 py-2 rounded-[4px] transition-colors"><PencilSimple size={14} /> Edit customer</button>}
          <button data-testid="open-lead-workspace-btn" onClick={() => navigate(`/app/leads/${id}`)} className="flex items-center gap-1.5 text-xs bg-secondary hover:bg-accent px-3 py-2 rounded-[4px] transition-colors"><ChatsCircle size={14} /> Conversation workspace</button>
        </div>
      </div>

      <div className="flex gap-1 border-b border-border mb-5 overflow-x-auto" data-testid="profile-tabs">
        {TABS.map(([key, label]) => (
          <button key={key} data-testid={`profile-tab-${key}`} onClick={() => setParams({ tab: key }, { replace: true })}
            className={`px-3.5 py-2.5 text-sm font-medium whitespace-nowrap border-b-2 transition-colors duration-200 ${tab === key ? "border-primary text-foreground" : "border-transparent text-muted-foreground hover:text-foreground"}`}>
            {tr(label)}{COUNT[key] && p[COUNT[key]].length > 0 && <span className="ml-1.5 text-[10px] font-mono-plex bg-secondary rounded-full px-1.5">{p[COUNT[key]].length}</span>}
          </button>
        ))}
      </div>

      <div className="grid xl:grid-cols-[1fr_320px] gap-5 items-start">
        <div className="min-w-0"><Active p={p} reload={load} readOnly={readOnly} /></div>
        <ProfileActions p={p} reload={load} role={user?.role} />
      </div>
      {editing && <EditCustomer p={p} open={editing} onClose={() => setEditing(false)} reload={load} />}
    </div>
  );
}
