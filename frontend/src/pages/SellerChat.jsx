import { useState, useEffect, useRef } from "react";
import { useParams } from "react-router-dom";
import client from "@/lib/api";
import { t } from "@/i18n";
import { toast } from "sonner";
import {
  PaperPlaneRight, CheckCircle, CalendarCheck, ShieldCheck, Calculator, CarProfile, X, Clock,
} from "@phosphor-icons/react";

const AI_AVATAR = "https://images.unsplash.com/photo-1535378620166-273708d44e4c?crop=entropy&cs=srgb&fm=jpg&q=85&w=200";
const STORAGE_KEY = (slug) => `aa_conv_${slug}`;
const LANG_KEY = (slug) => `aa_lang_${slug}`;

function fmtSlot(iso, lang) {
  const d = new Date(iso);
  return d.toLocaleString(lang === "fr" ? "fr-CA" : undefined, { weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}
const money = (n) => `$${Math.round(n).toLocaleString()}`;

export default function SellerChat() {
  const { slug } = useParams();
  const [dealer, setDealer] = useState(null);
  const [lang, setLang] = useState(() => localStorage.getItem(LANG_KEY(slug)) || "en");
  const [convId, setConvId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [slots, setSlots] = useState([]);
  const [showSlots, setShowSlots] = useState(false);
  const [financing, setFinancing] = useState(null);
  const [booked, setBooked] = useState(null);
  const [notFound, setNotFound] = useState(false);
  const [recommendations, setRecommendations] = useState([]);
  const [canRefer, setCanRefer] = useState(false);
  const [consentOpen, setConsentOpen] = useState(false);
  const [consent, setConsent] = useState(null);
  const [consentResult, setConsentResult] = useState(null);
  const endRef = useRef(null);
  const tr = (k) => t(lang, k);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await client.get(`/public/${slug}`);
        setDealer(data);
      } catch { setNotFound(true); return; }
      const existing = localStorage.getItem(STORAGE_KEY(slug));
      if (existing) {
        try {
          const { data } = await client.get(`/public/${slug}/conversations/${existing}`);
          setConvId(existing);
          setMessages(data.messages);
          if (data.conversation?.language) setLang(data.conversation.language);
          if (data.recommendations?.length) setRecommendations(data.recommendations);
          if (data.consent_status) setConsentResult(data.consent_status);
          else if (data.recommendations?.length) setCanRefer(true);
          if (data.booked_appointment) setBooked(data.booked_appointment);
          return;
        } catch { localStorage.removeItem(STORAGE_KEY(slug)); }
      }
      const { data } = await client.post(`/public/${slug}/conversations`, { consent: true, language: lang });
      setConvId(data.conversation_id);
      setMessages(data.messages);
      localStorage.setItem(STORAGE_KEY(slug), data.conversation_id);
    })();
  }, [slug]);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, sending, showSlots, recommendations]);

  const switchLang = (l) => { setLang(l); localStorage.setItem(LANG_KEY(slug), l); };

  const send = async () => {
    const text = input.trim();
    if (!text || sending) return;
    setInput("");
    setMessages((m) => [...m, { id: `tmp-${Date.now()}`, sender_type: "seller", content: text }]);
    setSending(true);
    try {
      const { data } = await client.post(`/public/${slug}/conversations/${convId}/messages`, { content: text, language: lang });
      setMessages(data.messages);
      if (data.recommendations) setRecommendations(data.recommendations);
      setCanRefer(!!data.can_refer);
      if (data.consented) setConsentResult("accepted");
      if (data.show_appointments) loadSlots();
    } catch {
      setMessages((m) => [...m, { id: `err-${Date.now()}`, sender_type: "ai", content: "Sorry, something went wrong. Please try again." }]);
    } finally { setSending(false); }
  };

  const loadSlots = async () => {
    try {
      client.get(`/public/${slug}/conversations/${convId}/financing-estimate`)
        .then((r) => { if (r.data?.available) setFinancing(r.data); }).catch(() => {});
      const { data } = await client.get(`/public/${slug}/conversations/${convId}/appointments/availability`);
      setSlots(data.slots || []);
      setShowSlots(true);
    } catch {}
  };

  const book = async (slot) => {
    try {
      const { data } = await client.post(`/public/${slug}/conversations/${convId}/appointments`, {
        start_time: slot.start_time, end_time: slot.end_time, appointment_type: slot.appointment_type,
      });
      setMessages(data.messages);
      setBooked(data.appointment);
      setShowSlots(false);
    } catch { loadSlots(); }
  };

  const openConsent = async () => {
    try {
      const { data } = await client.get(`/public/${slug}/conversations/${convId}/consent-agreement`, { params: { language: lang } });
      setConsent(data);
      setConsentOpen(true);
    } catch {}
  };

  const decideConsent = async (accepted) => {
    try {
      await client.post(`/public/${slug}/conversations/${convId}/consent`, {
        accepted, language: lang, recipient_dealer_group_id: consent?.recipient?.dealer_group_id,
      });
      setConsentResult(accepted ? "accepted" : "declined");
      setConsentOpen(false);
      setCanRefer(false);
    } catch { toast.error("Something went wrong. Please try again."); }
  };

  if (notFound)
    return <div className="min-h-screen flex items-center justify-center text-muted-foreground font-mono-plex">{tr("not_found")}</div>;

  return (
    <div className="min-h-screen bg-[#FAFAFA] text-[#0A0A0A] flex flex-col">
      <header className="sticky top-0 z-20 backdrop-blur-xl bg-white/80 border-b border-black/5">
        <div className="max-w-2xl mx-auto px-4 py-3 flex items-center gap-3">
          <img src={AI_AVATAR} alt="AI" className="w-10 h-10 rounded-full object-cover ring-2 ring-white shadow-sm" />
          <div className="min-w-0 flex-1">
            <div className="font-head font-extrabold tracking-tight leading-none truncate">{dealer?.organization?.name}</div>
            <div className="text-xs text-[#525252] flex items-center gap-1 mt-0.5">
              <span className="w-1.5 h-1.5 rounded-full bg-[#16A34A]" /> {tr("assistant_subtitle")}
            </div>
          </div>
          <div data-testid="lang-switcher" className="flex items-center rounded-full border border-black/10 overflow-hidden text-xs font-mono-plex">
            {["en", "fr"].map((l) => (
              <button key={l} data-testid={`lang-${l}`} onClick={() => switchLang(l)}
                className={`px-2.5 py-1 transition-colors duration-200 ${lang === l ? "bg-[#2563EB] text-white" : "text-[#525252] hover:bg-black/5"}`}>
                {l.toUpperCase()}
              </button>
            ))}
          </div>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto" aria-live="polite">
        <div className="max-w-2xl mx-auto px-4 py-6 space-y-4">
          {messages.map((m) => <Bubble key={m.id} msg={m} tr={tr} />)}
          {sending && (
            <div className="flex items-end gap-2 msg-in">
              <img src={AI_AVATAR} alt="AI" className="w-8 h-8 rounded-full object-cover" />
              <div className="bg-white border border-black/5 rounded-2xl rounded-bl-sm px-4 py-3 text-[#2563EB] shadow-sm">
                <span className="typing-dot" /><span className="typing-dot mx-1" /><span className="typing-dot" />
              </div>
            </div>
          )}

          {recommendations.length > 0 && !booked && (
            <div className="msg-in space-y-2" data-testid="recommendations">
              <div className="flex items-center gap-2 font-semibold text-sm text-[#525252]">
                <CarProfile size={18} weight="bold" className="text-[#2563EB]" /> {tr("recommended")}
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {recommendations.map((v) => <VehicleCard key={v.id} v={v} tr={tr} />)}
              </div>
            </div>
          )}

          {canRefer && !consentResult && (
            <button data-testid="connect-dealer-btn" onClick={openConsent}
              className="msg-in w-full bg-[#2563EB] text-white rounded-2xl px-4 py-3 font-semibold hover:opacity-90 transition-opacity duration-200 flex items-center justify-center gap-2">
              <ShieldCheck size={18} weight="bold" /> {tr("connect_dealer")}
            </button>
          )}

          {consentResult === "accepted" && (
            <div className="msg-in bg-[#16A34A]/10 border border-[#16A34A]/25 rounded-2xl p-4 flex items-center gap-3" data-testid="consent-accepted">
              <CheckCircle size={26} weight="fill" className="text-[#16A34A]" />
              <div>
                <div className="font-semibold text-[#16A34A]">{tr("consent_shared_title")}</div>
                <div className="text-sm text-[#525252]">{tr("consent_shared_body")}</div>
              </div>
            </div>
          )}
          {consentResult === "declined" && (
            <div className="msg-in bg-black/5 border border-black/10 rounded-2xl p-4" data-testid="consent-declined">
              <div className="font-semibold">{tr("consent_declined_title")}</div>
              <div className="text-sm text-[#525252]">{tr("consent_declined_body")}</div>
            </div>
          )}

          {financing && !booked && <FinancingCard f={financing} tr={tr} />}

          {showSlots && !booked && (
            <div className="msg-in bg-white border border-black/10 rounded-2xl p-4 shadow-sm" data-testid="slot-picker">
              <div className="flex items-center gap-2 font-semibold mb-3">
                <CalendarCheck size={20} weight="bold" className="text-[#2563EB]" /> {tr("choose_time")}
              </div>
              {slots.length === 0 ? (
                <div className="text-sm text-[#525252]">{tr("no_slots")}</div>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {slots.map((s) => (
                    <button key={s.start_time} data-testid="slot-option" onClick={() => book(s)}
                      className="text-left text-sm border border-black/10 rounded-[6px] px-3 py-2.5 hover:border-[#2563EB] hover:bg-[#2563EB]/5 transition-colors duration-200 font-mono-plex">
                      {fmtSlot(s.start_time, lang)}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          {booked && (
            <div className="msg-in bg-[#EAB308]/10 border border-[#EAB308]/25 rounded-2xl p-4 flex items-center gap-3" data-testid="booking-requested">
              <Clock size={28} weight="fill" className="text-[#B45309]" />
              <div>
                <div className="font-semibold text-[#B45309]">{tr("appt_requested")}</div>
                <div className="text-sm text-[#525252] font-mono-plex">{fmtSlot(booked.start_time, lang)}</div>
                <div className="text-xs text-[#525252] mt-0.5">{tr("appt_pending")}</div>
              </div>
            </div>
          )}
          <div ref={endRef} />
        </div>
      </div>

      <div className="sticky bottom-0 backdrop-blur-xl bg-white/85 border-t border-black/5">
        <div className="max-w-2xl mx-auto px-4 py-3">
          <div className="flex items-end gap-2">
            <textarea data-testid="chat-input" value={input} onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
              rows={1} placeholder={tr("type_message")}
              className="flex-1 resize-none rounded-2xl border border-black/10 bg-white px-4 py-3 text-base outline-none focus:border-[#2563EB] transition-colors duration-200 max-h-32" />
            <button data-testid="chat-send-button" onClick={send} disabled={sending || !input.trim()}
              className="w-11 h-11 shrink-0 rounded-full bg-[#2563EB] text-white flex items-center justify-center hover:opacity-90 transition-opacity duration-200 disabled:opacity-40">
              <PaperPlaneRight size={20} weight="fill" />
            </button>
          </div>
          <div className="text-[11px] text-[#525252] mt-2 text-center">{tr("disclaimer")}</div>
        </div>
      </div>

      {consentOpen && consent && (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/40 backdrop-blur-sm p-0 sm:p-4" data-testid="consent-modal">
          <div className="bg-white w-full sm:max-w-lg sm:rounded-2xl rounded-t-2xl shadow-2xl max-h-[88vh] flex flex-col">
            <div className="flex items-center justify-between px-5 py-4 border-b border-black/5">
              <div className="font-head font-bold text-lg">{tr("consent_title")}</div>
              <button onClick={() => setConsentOpen(false)} className="text-[#525252] hover:text-black"><X size={20} /></button>
            </div>
            <div className="px-5 py-4 overflow-y-auto">
              <p className="text-sm text-[#525252] mb-3">{tr("consent_review")}</p>
              <div className="text-sm whitespace-pre-line leading-relaxed text-[#262626]">{consent.body_text}</div>
            </div>
            <div className="px-5 py-4 border-t border-black/5 flex flex-col sm:flex-row gap-2">
              <button data-testid="consent-accept-btn" onClick={() => decideConsent(true)}
                className="flex-1 bg-[#2563EB] text-white rounded-[8px] px-4 py-3 font-semibold hover:opacity-90 transition-opacity">{tr("consent_accept")}</button>
              <button data-testid="consent-decline-btn" onClick={() => decideConsent(false)}
                className="flex-1 bg-black/5 rounded-[8px] px-4 py-3 font-semibold hover:bg-black/10 transition-colors">{tr("consent_decline")}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function VehicleCard({ v, tr }) {
  const title = [v.year, v.make, v.model].filter(Boolean).join(" ");
  return (
    <div data-testid="vehicle-card" className="bg-white border border-black/10 rounded-[10px] overflow-hidden shadow-sm">
      {v.image_url ? (
        <img src={v.image_url} alt={title} className="w-full h-32 object-cover" onError={(e) => { e.target.style.display = "none"; }} />
      ) : (
        <div className="w-full h-32 bg-[#2563EB]/5 flex items-center justify-center"><CarProfile size={40} className="text-[#2563EB]/40" /></div>
      )}
      <div className="p-3">
        <div className="font-head font-bold leading-tight">{title}{v.trim ? ` ${v.trim}` : ""}</div>
        {v.price != null && <div className="text-[#2563EB] font-bold mt-0.5">{money(v.price)}</div>}
        <div className="text-xs text-[#525252] mt-1 flex flex-wrap gap-x-2 font-mono-plex">
          {v.mileage != null && <span>{v.mileage.toLocaleString()} km</span>}
          {v.transmission && <span>· {v.transmission}</span>}
          {v.fuel_type && <span>· {v.fuel_type}</span>}
        </div>
        {v.match_reasons?.length > 0 && (
          <div className="mt-2 text-[11px] text-[#16A34A]">{tr("match_reasons")}: {v.match_reasons.slice(0, 2).join(", ")}</div>
        )}
      </div>
    </div>
  );
}

function FinancingCard({ f, tr }) {
  return (
    <div className="msg-in bg-white border border-black/10 rounded-2xl p-4 shadow-sm" data-testid="financing-card">
      <div className="flex items-center gap-2 font-semibold mb-1">
        <Calculator size={20} weight="bold" className="text-[#2563EB]" /> {tr("financing_preview")}
      </div>
      {f.matched_vehicle && <div className="text-sm text-[#525252] mb-3">{f.matched_vehicle} · {money(f.replacement_price)}</div>}
      <div className="grid grid-cols-2 gap-3 text-sm">
        <Stat label={tr("est_trade")} value={`${money(f.estimated_trade_value.low)}–${money(f.estimated_trade_value.high)}`} />
        <Stat label={tr("est_loan")} value={money(f.estimated_loan_balance)} />
        <Stat label={f.negative_equity ? tr("est_neg_equity") : tr("est_equity")} value={`${money(f.estimated_equity.low)}–${money(f.estimated_equity.high)}`}
          accent={f.negative_equity ? "text-[#E53E3E]" : "text-[#16A34A]"} />
        <Stat label={tr("est_financed")} value={`${money(f.amount_financed.low)}–${money(f.amount_financed.high)}`} />
      </div>
      <div className="mt-3 rounded-[8px] bg-[#2563EB]/5 border border-[#2563EB]/15 p-3">
        <div className="text-xs font-mono-plex uppercase tracking-wider text-[#525252]">{tr("est_monthly")}</div>
        <div className="font-head font-black text-2xl tracking-tighter text-[#2563EB]">
          {money(f.estimated_monthly_payment.low)}–{money(f.estimated_monthly_payment.high)}<span className="text-sm font-normal text-[#525252]">/mo</span>
        </div>
        <div className="text-[11px] text-[#525252] font-mono-plex mt-0.5">
          {f.assumptions.term_months}mo · ~{(f.assumptions.annual_interest_rate * 100).toFixed(2)}% APR
        </div>
      </div>
      <p className="text-[11px] text-[#525252] mt-3 leading-relaxed">{f.disclaimer}</p>
    </div>
  );
}
const Stat = ({ label, value, accent }) => (
  <div>
    <div className="text-xs font-mono-plex uppercase tracking-wider text-[#525252]">{label}</div>
    <div className={`font-semibold ${accent || ""}`}>{value}</div>
  </div>
);

function Bubble({ msg, tr }) {
  const isSeller = msg.sender_type === "seller";
  const isHuman = msg.sender_type === "human_agent";
  if (isSeller)
    return (
      <div className="flex justify-end msg-in">
        <div className="max-w-[80%] bg-[#2563EB] text-white rounded-2xl rounded-br-sm px-4 py-2.5 text-base leading-relaxed shadow-sm">{msg.content}</div>
      </div>
    );
  return (
    <div className="flex items-end gap-2 msg-in">
      <img src={AI_AVATAR} alt="AI" className="w-8 h-8 rounded-full object-cover shrink-0" />
      <div className="max-w-[80%]">
        {isHuman && <div className="text-[11px] text-[#525252] mb-1 font-mono-plex ml-1">{tr("rep")}</div>}
        <div className={`rounded-2xl rounded-bl-sm px-4 py-2.5 text-base leading-relaxed shadow-sm border whitespace-pre-line ${isHuman ? "bg-[#EAB308]/10 border-[#EAB308]/25" : "bg-white border-black/5"}`}>{msg.content}</div>
      </div>
    </div>
  );
}
