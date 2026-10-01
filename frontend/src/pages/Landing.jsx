import { Link } from "react-router-dom";
import {
  Robot, ArrowRight, ChatCircleDots, ChartLineUp, Handshake,
  Lightning, ShieldCheck, CaretRight,
  Plugs, MagnifyingGlass, ArrowsClockwise, LockKey,
} from "@phosphor-icons/react";

const HERO_IMG = "https://images.unsplash.com/photo-1727434032773-af3cd98375ba?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjA1OTV8MHwxfHNlYXJjaHwyfHxhYnN0cmFjdCUyMGJsdWUlMjBkYXRhJTIwdGVjaG5vbG9neXxlbnwwfHx8fDE3ODgxMjQ0NjZ8MA&ixlib=rb-4.1.0&q=85";
const SHOWROOM_IMG = "https://images.unsplash.com/photo-1574023278981-0b48ba10e9ba?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjAzNDR8MHwxfHNlYXJjaHwxfHxtb2Rlcm4lMjBjYXIlMjBzaG93cm9vbSUyMGR1c2t8ZW58MHx8fHwxNzg4MTI0NDY2fDA&ixlib=rb-4.1.0&q=85";

const Eyebrow = ({ children }) => (
  <span className="font-mono-plex text-xs uppercase tracking-[0.25em] text-primary">{children}</span>
);

const Logo = () => (
  <div className="flex items-center gap-2">
    <div className="w-9 h-9 rounded-[4px] bg-primary flex items-center justify-center shadow-[0_0_24px_rgba(37,99,235,0.45)]">
      <Robot size={22} weight="bold" className="text-white" />
    </div>
    <span className="font-head font-black text-xl tracking-tight text-white">AutoNova<span className="text-primary">AI</span></span>
  </div>
);

const FEATURES = [
  { icon: ChatCircleDots, title: "AI buyer & seller chat", body: "A natural conversation captures the vehicle, needs, budget, financing and intent — no forms, no drop-off." },
  { icon: ChartLineUp, title: "Deterministic scoring", body: "Every lead is scored on fixed, explainable rules — so only serious, qualified opportunities move forward." },
  { icon: Plugs, title: "Connected inventory layer", body: "Plug in any dealer group via CSV, live feed, API or indexer. Every source is normalized into one clean catalog." },
  { icon: MagnifyingGlass, title: "Cross-dealer matching", body: "The AI searches inventory across every connected dealer group to find the right vehicle for each buyer." },
  { icon: Handshake, title: "Referral & commission tracking", body: "Qualified buyers are referred to the right dealership and tracked through to the commission on every converted sale." },
  { icon: ArrowsClockwise, title: "Always-fresh data", body: "Sources auto-refresh on a schedule; sold or removed vehicles drop out so the AI only ever offers what's available." },
];

const STATS = [
  ["∞", "Dealer groups you can connect"],
  ["<60s", "Average time to qualify"],
  ["24/7", "Always-on buyer intake"],
  ["100%", "Explainable lead scores"],
];

export default function Landing() {
  return (
    <div className="dark min-h-screen bg-background text-foreground antialiased overflow-x-hidden">
      {/* NAV */}
      <nav data-testid="landing-nav" className="fixed top-0 inset-x-0 z-50 backdrop-blur-xl bg-black/60 border-b border-white/10">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <Link to="/" data-testid="nav-logo"><Logo /></Link>
          <div className="hidden md:flex items-center gap-8 font-mono-plex text-xs uppercase tracking-widest text-muted-foreground">
            <a href="#how" className="hover:text-foreground transition-colors duration-200">How it works</a>
            <a href="#features" className="hover:text-foreground transition-colors duration-200">Features</a>
            <a href="#network" className="hover:text-foreground transition-colors duration-200">Inventory</a>
            <a href="#dealers" className="hover:text-foreground transition-colors duration-200">For dealerships</a>
          </div>
          <div className="flex items-center gap-3">
            <Link to="/login" data-testid="nav-signin"
              className="hidden sm:inline-flex items-center px-4 py-2 rounded-[4px] text-sm font-medium text-white border border-white/20 hover:bg-white/5 transition-colors duration-200">
              Sign in
            </Link>
            <Link to="/login" data-testid="nav-signup"
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-[4px] text-sm font-semibold bg-primary text-primary-foreground hover:-translate-y-0.5 hover:shadow-[0_0_18px_rgba(37,99,235,0.5)] transition-[transform,box-shadow] duration-200">
              Get started <ArrowRight size={15} weight="bold" />
            </Link>
          </div>
        </div>
      </nav>

      {/* HERO */}
      <header className="relative pt-28 md:pt-36 pb-16 md:pb-24 px-6">
        <div className="pointer-events-none absolute -top-40 -left-40 w-[36rem] h-[36rem] rounded-full" style={{ background: "radial-gradient(circle, rgba(37,99,235,0.18), transparent 60%)" }} />
        <div className="max-w-7xl mx-auto grid lg:grid-cols-12 gap-12 items-center relative">
          <div className="lg:col-span-7 animate-in fade-in slide-in-from-bottom-4 duration-700">
            <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 mb-6">
              <Lightning size={13} weight="fill" className="text-primary" />
              <span className="font-mono-plex text-[11px] uppercase tracking-widest text-muted-foreground">AI lead generation & matching · Pilot · CA / US</span>
            </div>
            <h1 className="font-head font-black text-4xl sm:text-5xl lg:text-6xl tracking-tighter leading-[1.03] text-white">
              Qualify the buyer. Match the vehicle. <span className="text-primary">Refer the deal.</span>
            </h1>
            <p className="mt-6 text-base sm:text-lg text-muted-foreground leading-relaxed max-w-xl">
              AutoNova AI qualifies vehicle buyers and sellers in conversation, searches inventory across every connected dealer group to find the right car, then refers each qualified opportunity to the right dealership — and tracks it through to commission.
            </p>
            <div className="mt-9 flex flex-wrap items-center gap-4">
              <Link to="/login" data-testid="hero-signup-button"
                className="inline-flex items-center gap-2 px-6 py-3 rounded-[4px] text-sm font-semibold bg-primary text-primary-foreground hover:-translate-y-0.5 hover:shadow-[0_0_22px_rgba(37,99,235,0.5)] transition-[transform,box-shadow] duration-200">
                Get started free <ArrowRight size={16} weight="bold" />
              </Link>
              <Link to="/login" data-testid="hero-signin-button"
                className="inline-flex items-center gap-2 px-6 py-3 rounded-[4px] text-sm font-medium text-white border border-white/20 hover:bg-white/5 transition-colors duration-200">
                Sign in to workspace
              </Link>
            </div>
          </div>

          {/* hero visual */}
          <div className="lg:col-span-5 relative animate-in fade-in slide-in-from-bottom-6 duration-1000">
            <div className="relative rounded-[8px] border border-white/10 overflow-hidden shadow-[0_0_60px_rgba(37,99,235,0.15)]">
              <img src={HERO_IMG} alt="" className="w-full h-56 md:h-72 object-cover opacity-70" />
              <div className="absolute inset-0 bg-black/50" />
              {/* floating qualified-lead card */}
              <div className="absolute inset-x-4 bottom-4 rounded-[6px] border border-white/15 bg-black/70 backdrop-blur-md p-4">
                <div className="flex items-center justify-between">
                  <span className="font-mono-plex text-[10px] uppercase tracking-widest text-primary">Matched & referred</span>
                  <span className="text-xs font-semibold text-white bg-primary/20 border border-primary/30 rounded-full px-2 py-0.5">Score 87</span>
                </div>
                <div className="mt-2 font-head font-bold text-white">2024 Honda CR-V · $33,000</div>
                <div className="mt-1 text-xs text-muted-foreground">Le Prix du Gros · Referral sent · $200 commission</div>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* STATS RIBBON */}
      <section className="border-y border-white/10 bg-card/40">
        <div className="max-w-7xl mx-auto px-6 py-10 grid grid-cols-2 md:grid-cols-4 gap-8">
          {STATS.map(([n, l]) => (
            <div key={l}>
              <div className="font-head font-black text-3xl text-white">{n}</div>
              <div className="mt-1 font-mono-plex text-[11px] uppercase tracking-widest text-muted-foreground">{l}</div>
            </div>
          ))}
        </div>
      </section>

      {/* HOW IT WORKS — bento */}
      <section id="how" className="scroll-mt-24 max-w-7xl mx-auto px-6 py-20 md:py-28">
        <Eyebrow>How it works</Eyebrow>
        <h2 className="mt-3 font-head font-black text-3xl sm:text-4xl tracking-tight text-white max-w-2xl">
          From a cold "what should I drive next?" to a referred, commission-ready deal.
        </h2>
        <div className="mt-12 grid grid-cols-1 md:grid-cols-12 gap-6">
          <div className="md:col-span-8 rounded-[6px] border border-border bg-card p-6 md:p-8 hover:border-white/20 transition-colors duration-200">
            <div className="flex items-center gap-3">
              <ChatCircleDots size={22} weight="bold" className="text-primary" />
              <span className="font-mono-plex text-[11px] uppercase tracking-widest text-muted-foreground">Step 01 · Conversation</span>
            </div>
            <h3 className="mt-4 font-head font-bold text-2xl text-white">The AI talks to the customer like a person</h3>
            <p className="mt-3 text-muted-foreground leading-relaxed max-w-xl">
              It captures the vehicle type, budget, financing, trade-in, location and preferences — and the customer's real intent — without a single form field.
            </p>
          </div>
          <div className="md:col-span-4 rounded-[6px] border border-border bg-card p-6 md:p-8 hover:border-white/20 transition-colors duration-200">
            <div className="flex items-center gap-3">
              <ChartLineUp size={22} weight="bold" className="text-primary" />
              <span className="font-mono-plex text-[11px] uppercase tracking-widest text-muted-foreground">Step 02 · Scoring</span>
            </div>
            <h3 className="mt-4 font-head font-bold text-2xl text-white">Every lead scored</h3>
            <p className="mt-3 text-muted-foreground leading-relaxed">Fixed, explainable rules decide who's a serious buyer — no black box.</p>
          </div>
          <div className="md:col-span-4 rounded-[6px] border border-border bg-card p-6 md:p-8 hover:border-white/20 transition-colors duration-200">
            <div className="flex items-center gap-3">
              <MagnifyingGlass size={22} weight="bold" className="text-primary" />
              <span className="font-mono-plex text-[11px] uppercase tracking-widest text-muted-foreground">Step 03 · Match</span>
            </div>
            <h3 className="mt-4 font-head font-bold text-2xl text-white">Match across the network</h3>
            <p className="mt-3 text-muted-foreground leading-relaxed">The AI finds the best vehicle for the buyer across every connected dealer group's inventory.</p>
          </div>
          <div className="md:col-span-8 rounded-[6px] border border-border bg-card p-6 md:p-8 hover:border-white/20 transition-colors duration-200 flex flex-col justify-between">
            <div>
              <div className="flex items-center gap-3">
                <Handshake size={22} weight="bold" className="text-primary" />
                <span className="font-mono-plex text-[11px] uppercase tracking-widest text-muted-foreground">Step 04 · Refer</span>
              </div>
              <h3 className="mt-4 font-head font-bold text-2xl text-white">Referred to the right dealership — and tracked to commission</h3>
              <p className="mt-3 text-muted-foreground leading-relaxed max-w-xl">
                Each qualified, matched buyer is handed to the right dealer group with the vehicle and full context, then tracked through the referral program to the commission on every sale.
              </p>
            </div>
            <Link to="/login" data-testid="how-cta" className="mt-6 inline-flex items-center gap-1.5 text-sm font-semibold text-primary hover:gap-2.5 transition-all duration-200">
              See it in your dashboard <CaretRight size={15} weight="bold" />
            </Link>
          </div>
        </div>
      </section>

      {/* FEATURES */}
      <section id="features" className="scroll-mt-24 border-t border-white/10 bg-card/30">
        <div className="max-w-7xl mx-auto px-6 py-20 md:py-28">
          <Eyebrow>The platform</Eyebrow>
          <h2 className="mt-3 font-head font-black text-3xl sm:text-4xl tracking-tight text-white max-w-2xl">
            One deterministic engine — from first message to tracked commission.
          </h2>
          <div className="mt-12 grid grid-cols-1 md:grid-cols-3 gap-6">
            {FEATURES.map((f) => (
              <div key={f.title} data-testid={`feature-${f.title.toLowerCase().replace(/\s+/g, "-")}`}
                className="group rounded-[6px] border border-border bg-background p-6 md:p-8 hover:border-white/20 hover:-translate-y-1 transition-[transform,border-color] duration-200">
                <div className="w-11 h-11 rounded-[4px] bg-primary/10 border border-primary/20 flex items-center justify-center group-hover:bg-primary/20 transition-colors duration-200">
                  <f.icon size={22} weight="bold" className="text-primary" />
                </div>
                <h3 className="mt-5 font-head font-bold text-lg text-white">{f.title}</h3>
                <p className="mt-2 text-sm text-muted-foreground leading-relaxed">{f.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* INVENTORY NETWORK */}
      <section id="network" className="scroll-mt-24 border-t border-white/10">
        <div className="max-w-7xl mx-auto px-6 py-20 md:py-28">
          <div className="max-w-2xl">
            <Eyebrow>Inventory layer</Eyebrow>
            <h2 className="mt-3 font-head font-black text-3xl sm:text-4xl tracking-tight text-white">
              Connect any source. One clean, always-fresh catalog.
            </h2>
            <p className="mt-5 text-muted-foreground leading-relaxed">
              AutoNova's inventory layer is built independently of the source. Connect a dealer group through a CSV export, a live feed, a private API, or an indexer — every source is normalized into the same catalog the AI searches. Swap one source for another later without rebuilding a thing.
            </p>
          </div>

          <div className="mt-12 grid grid-cols-1 md:grid-cols-4 gap-4">
            {[
              { n: "01", t: "Connect", d: "CSV upload, HTTP feed, API, or indexer — per dealer group." },
              { n: "02", t: "Normalize", d: "Make, model, price, mileage, location, stock # mapped to one schema." },
              { n: "03", t: "Refresh", d: "Auto-syncs on schedule; sold or removed vehicles drop out automatically." },
              { n: "04", t: "Match & refer", d: "The AI matches buyers and refers them to the right dealership." },
            ].map((s) => (
              <div key={s.n} className="rounded-[6px] border border-border bg-card p-6 hover:border-white/20 transition-colors duration-200">
                <div className="font-mono-plex text-[11px] text-primary tracking-widest">{s.n}</div>
                <h3 className="mt-3 font-head font-bold text-lg text-white">{s.t}</h3>
                <p className="mt-2 text-sm text-muted-foreground leading-relaxed">{s.d}</p>
              </div>
            ))}
          </div>

          <div className="mt-8 flex items-start gap-3 rounded-[6px] border border-primary/20 bg-primary/5 p-5 max-w-3xl">
            <LockKey size={20} weight="bold" className="text-primary mt-0.5 shrink-0" />
            <p className="text-sm text-foreground leading-relaxed">
              <span className="font-semibold">Private by design.</span> Dealer inventory is used only behind the scenes to power AI matching and referrals — it is never republished or displayed publicly.
            </p>
          </div>
        </div>
      </section>

      {/* FOR DEALERSHIPS */}
      <section id="dealers" className="scroll-mt-24 max-w-7xl mx-auto px-6 py-20 md:py-32 grid lg:grid-cols-2 gap-10 md:gap-14 items-center">
        <div>
          <Eyebrow>For dealerships</Eyebrow>
          <h2 className="mt-3 font-head font-black text-3xl sm:text-4xl tracking-tight text-white leading-tight">
            Qualified buyers, matched to your cars, delivered to your lane.
          </h2>
          <p className="mt-5 text-muted-foreground leading-relaxed">
            Connect your inventory once and AutoNova sends you serious, pre-qualified buyers already matched to a vehicle you have — you pay per referred deal, not per tire-kicker. Run it across one rooftop or an entire dealer group.
          </p>
          <ul className="mt-8 space-y-4">
            {[
              "Connect inventory via CSV, live feed, API or indexer",
              "Per-dealer referral agreements and commission tracking",
              "Live human takeover and explainable scores you can defend to a GM",
            ].map((t) => (
              <li key={t} className="flex items-start gap-3">
                <ShieldCheck size={20} weight="bold" className="text-primary mt-0.5 shrink-0" />
                <span className="text-sm text-foreground">{t}</span>
              </li>
            ))}
          </ul>
          <Link to="/login" data-testid="dealers-signup-button"
            className="mt-10 inline-flex items-center gap-2 px-6 py-3 rounded-[4px] text-sm font-semibold bg-primary text-primary-foreground hover:-translate-y-0.5 hover:shadow-[0_0_22px_rgba(37,99,235,0.5)] transition-[transform,box-shadow] duration-200">
            Create your workspace <ArrowRight size={16} weight="bold" />
          </Link>
        </div>
        <div className="relative rounded-[8px] border border-white/10 overflow-hidden shadow-[0_0_60px_rgba(37,99,235,0.12)]">
          <img src={SHOWROOM_IMG} alt="Modern car showroom at dusk" className="w-full h-[26rem] object-cover" />
          <div className="absolute inset-0 bg-gradient-to-t from-black/70 to-transparent" />
        </div>
      </section>

      {/* FOOTER CTA */}
      <footer className="border-t border-white/10">
        <div className="max-w-7xl mx-auto px-6 py-16 md:py-24">
          <div className="rounded-[8px] border border-white/10 bg-card p-8 sm:p-14 text-center relative overflow-hidden">
            <div className="pointer-events-none absolute -top-24 left-1/2 -translate-x-1/2 w-[30rem] h-[30rem] rounded-full" style={{ background: "radial-gradient(circle, rgba(37,99,235,0.16), transparent 60%)" }} />
            <h2 className="relative font-head font-black text-3xl sm:text-5xl tracking-tighter text-white">Ready to acquire?</h2>
            <p className="relative mt-4 text-muted-foreground max-w-xl mx-auto">Spin up your dealership workspace in minutes and put your seller intake on autopilot.</p>
            <div className="relative mt-8 flex flex-wrap items-center justify-center gap-4">
              <Link to="/login" data-testid="footer-signup-button"
                className="inline-flex items-center gap-2 px-7 py-3 rounded-[4px] text-sm font-semibold bg-primary text-primary-foreground hover:-translate-y-0.5 hover:shadow-[0_0_22px_rgba(37,99,235,0.5)] transition-[transform,box-shadow] duration-200">
                Get started free <ArrowRight size={16} weight="bold" />
              </Link>
              <Link to="/login" data-testid="footer-signin-link" className="text-sm font-medium text-white hover:text-primary transition-colors duration-200">
                or sign in →
              </Link>
            </div>
          </div>

          <div className="mt-14 flex flex-col sm:flex-row items-center justify-between gap-6">
            <Logo />
            <div className="flex items-center gap-8 font-mono-plex text-[11px] uppercase tracking-widest text-muted-foreground">
              <a href="#how" className="hover:text-foreground transition-colors duration-200">How it works</a>
              <a href="#features" className="hover:text-foreground transition-colors duration-200">Features</a>
              <Link to="/login" data-testid="footer-nav-signin" className="hover:text-foreground transition-colors duration-200">Sign in</Link>
            </div>
            <div className="font-mono-plex text-[11px] text-muted-foreground/60 tracking-wider">© 2026 AutoNova AI</div>
          </div>
        </div>
      </footer>
    </div>
  );
}
