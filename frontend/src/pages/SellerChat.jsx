import { useState, useEffect, useRef } from "react";
import { useParams } from "react-router-dom";
import client from "@/lib/api";
import { Robot, PaperPlaneRight, CheckCircle, CalendarCheck, ShieldCheck } from "@phosphor-icons/react";

const AI_AVATAR = "https://images.unsplash.com/photo-1535378620166-273708d44e4c?crop=entropy&cs=srgb&fm=jpg&q=85&w=200";
const STORAGE_KEY = (slug) => `aa_conv_${slug}`;

function fmtSlot(iso) {
  const d = new Date(iso);
  return d.toLocaleString(undefined, { weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

export default function SellerChat() {
  const { slug } = useParams();
  const [dealer, setDealer] = useState(null);
  const [convId, setConvId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [slots, setSlots] = useState([]);
  const [showSlots, setShowSlots] = useState(false);
  const [booked, setBooked] = useState(null);
  const [notFound, setNotFound] = useState(false);
  const scrollRef = useRef(null);
  const endRef = useRef(null);

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
          return;
        } catch { localStorage.removeItem(STORAGE_KEY(slug)); }
      }
      const { data } = await client.post(`/public/${slug}/conversations`, { consent: true });
      setConvId(data.conversation_id);
      setMessages(data.messages);
      localStorage.setItem(STORAGE_KEY(slug), data.conversation_id);
    })();
  }, [slug]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending, showSlots]);

  const send = async () => {
    const text = input.trim();
    if (!text || sending) return;
    setInput("");
    setMessages((m) => [...m, { id: `tmp-${Date.now()}`, sender_type: "seller", content: text }]);
    setSending(true);
    try {
      const { data } = await client.post(`/public/${slug}/conversations/${convId}/messages`, { content: text });
      setMessages(data.messages);
      if (data.show_appointments) loadSlots();
    } catch {
      setMessages((m) => [...m, { id: `err-${Date.now()}`, sender_type: "ai", content: "Sorry, something went wrong. Please try again." }]);
    } finally { setSending(false); }
  };

  const loadSlots = async () => {
    try {
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
    } catch (e) {
      loadSlots();
    }
  };

  if (notFound)
    return <div className="min-h-screen flex items-center justify-center text-muted-foreground font-mono-plex">Dealership not found.</div>;

  return (
    <div className="min-h-screen bg-[#FAFAFA] text-[#0A0A0A] flex flex-col">
      {/* glass header */}
      <header className="sticky top-0 z-20 backdrop-blur-xl bg-white/80 border-b border-black/5">
        <div className="max-w-2xl mx-auto px-4 py-3 flex items-center gap-3">
          <img src={AI_AVATAR} alt="AI" className="w-10 h-10 rounded-full object-cover ring-2 ring-white shadow-sm" />
          <div className="min-w-0 flex-1">
            <div className="font-head font-extrabold tracking-tight leading-none truncate">{dealer?.organization?.name}</div>
            <div className="text-xs text-[#525252] flex items-center gap-1 mt-0.5">
              <span className="w-1.5 h-1.5 rounded-full bg-[#16A34A]" /> Virtual vehicle assistant · AI
            </div>
          </div>
          <div className="hidden sm:flex items-center gap-1 text-xs text-[#525252] font-mono-plex">
            <ShieldCheck size={14} /> Secure
          </div>
        </div>
      </header>

      {/* messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto" aria-live="polite">
        <div className="max-w-2xl mx-auto px-4 py-6 space-y-4">
          {messages.map((m) => (
            <Bubble key={m.id} msg={m} />
          ))}
          {sending && (
            <div className="flex items-end gap-2 msg-in">
              <img src={AI_AVATAR} alt="AI" className="w-8 h-8 rounded-full object-cover" />
              <div className="bg-white border border-black/5 rounded-2xl rounded-bl-sm px-4 py-3 text-[#2563EB] shadow-sm">
                <span className="typing-dot" /><span className="typing-dot mx-1" /><span className="typing-dot" />
              </div>
            </div>
          )}

          {showSlots && !booked && (
            <div className="msg-in bg-white border border-black/10 rounded-2xl p-4 shadow-sm" data-testid="slot-picker">
              <div className="flex items-center gap-2 font-semibold mb-3">
                <CalendarCheck size={20} weight="bold" className="text-[#2563EB]" /> Choose an appointment time
              </div>
              {slots.length === 0 ? (
                <div className="text-sm text-[#525252]">No slots available right now. A representative will reach out.</div>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {slots.map((s) => (
                    <button key={s.start_time} data-testid="slot-option" onClick={() => book(s)}
                      className="text-left text-sm border border-black/10 rounded-[6px] px-3 py-2.5 hover:border-[#2563EB] hover:bg-[#2563EB]/5 transition-colors duration-200 font-mono-plex">
                      {fmtSlot(s.start_time)}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          {booked && (
            <div className="msg-in bg-[#16A34A]/10 border border-[#16A34A]/25 rounded-2xl p-4 flex items-center gap-3" data-testid="booking-confirmed">
              <CheckCircle size={28} weight="fill" className="text-[#16A34A]" />
              <div>
                <div className="font-semibold text-[#16A34A]">Appointment confirmed</div>
                <div className="text-sm text-[#525252] font-mono-plex">{fmtSlot(booked.start_time)}</div>
              </div>
            </div>
          )}
          <div ref={endRef} />
        </div>
      </div>

      {/* input */}
      <div className="sticky bottom-0 backdrop-blur-xl bg-white/85 border-t border-black/5">
        <div className="max-w-2xl mx-auto px-4 py-3">
          <div className="flex items-end gap-2">
            <textarea
              data-testid="chat-input"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
              rows={1}
              placeholder="Type your message…"
              className="flex-1 resize-none rounded-2xl border border-black/10 bg-white px-4 py-3 text-base outline-none focus:border-[#2563EB] transition-colors duration-200 max-h-32"
            />
            <button data-testid="chat-send-button" onClick={send} disabled={sending || !input.trim()}
              className="w-11 h-11 shrink-0 rounded-full bg-[#2563EB] text-white flex items-center justify-center hover:opacity-90 transition-opacity duration-200 disabled:opacity-40">
              <PaperPlaneRight size={20} weight="fill" />
            </button>
          </div>
          <div className="text-[11px] text-[#525252] mt-2 text-center">
            You're chatting with an AI assistant. It won't guarantee prices or financing. Do not share banking passwords or SIN/SSN.
          </div>
        </div>
      </div>
    </div>
  );
}

function Bubble({ msg }) {
  const isSeller = msg.sender_type === "seller";
  const isHuman = msg.sender_type === "human_agent";
  if (isSeller)
    return (
      <div className="flex justify-end msg-in">
        <div className="max-w-[80%] bg-[#2563EB] text-white rounded-2xl rounded-br-sm px-4 py-2.5 text-base leading-relaxed shadow-sm">
          {msg.content}
        </div>
      </div>
    );
  return (
    <div className="flex items-end gap-2 msg-in">
      <img src={AI_AVATAR} alt="AI" className="w-8 h-8 rounded-full object-cover shrink-0" />
      <div className="max-w-[80%]">
        {isHuman && <div className="text-[11px] text-[#525252] mb-1 font-mono-plex ml-1">Dealership representative</div>}
        <div className={`rounded-2xl rounded-bl-sm px-4 py-2.5 text-base leading-relaxed shadow-sm border ${isHuman ? "bg-[#EAB308]/10 border-[#EAB308]/25" : "bg-white border-black/5"}`}>
          {msg.content}
        </div>
      </div>
    </div>
  );
}
