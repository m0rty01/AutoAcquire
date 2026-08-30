import { Link } from "react-router-dom";
import {
  Robot, ArrowRight, ChatCircleDots, ChartLineUp, Car, Calculator,
  CalendarCheck, SquaresFour, Lightning, ShieldCheck, CaretRight,
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
    <span className="font-head font-black text-xl tracking-tight text-white">AutoAcquire<span className="text-primary">AI</span></span>
  </div>
);

const FEATURES = [
  { icon: ChatCircleDots, title: "AI seller chat", body: "A natural conversation extracts the vehicle, seller details, and intent — no forms, no drop-off." },
  { icon: ChartLineUp, title: "Deterministic scoring", body: "Every lead is scored on fixed, explainable rules — so your team works the deals worth working." },
  { icon: Car, title: "Inventory matching", body: "Upgrade and trade intents are matched against your live inventory in real time." },
  { icon: Calculator, title: "Financing estimator", body: "Trade equity and estimated monthly payments computed inside the chat, before booking." },
  { icon: CalendarCheck, title: "Appointment booking", body: "The AI offers only real open slots and books the appraisal directly on your calendar." },
  { icon: SquaresFour, title: "Dealer dashboard", body: "Leads, inventory, appointments, analytics, and live human takeover — all in one workspace." },
];

const STATS = [
  ["3.2x", "More qualified appointments"],
  ["<60s", "Average time to qualify"],
  ["24/7", "Always-on seller intake"],
  ["100%", "Explainable lead scores"],
];

export default function Landing() {
  return (
    <div className="min-h-screen bg-background text-foreground antialiased overflow-x-hidden">
      {/* NAV */}
      <nav data-testid="landing-nav" className="fixed top-0 inset-x-0 z-50 backdrop-blur-xl bg-black/60 border-b border-white/10">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <Link to="/" data-testid="nav-logo"><Logo /></Link>
          <div className="hidden md:flex items-center gap-8 font-mono-plex text-xs uppercase tracking-widest text-muted-foreground">
            <a href="#how" className="hover:text-foreground transition-colors duration-200">How it works</a>
            <a href="#features" className="hover:text-foreground transition-colors duration-200">Features</a>
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
      <header className="relative pt-36 pb-24 px-6">
        <div className="pointer-events-none absolute -top-40 -left-40 w-[36rem] h-[36rem] rounded-full" style={{ background: "radial-gradient(circle, rgba(37,99,235,0.18), transparent 60%)" }} />
        <div className="max-w-7xl mx-auto grid lg:grid-cols-12 gap-12 items-center relative">
          <div className="lg:col-span-7 animate-in fade-in slide-in-from-bottom-4 duration-700">
            <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 mb-6">
              <Lightning size={13} weight="fill" className="text-primary" />
              <span className="font-mono-plex text-[11px] uppercase tracking-widest text-muted-foreground">AI vehicle acquisition · Pilot · CA / US</span>
            </div>
            <h1 className="font-head font-black text-4xl sm:text-5xl lg:text-6xl tracking-tighter leading-[1.03] text-white">
              Turn seller conversations into <span className="text-primary">booked appointments.</span>
            </h1>
            <p className="mt-6 text-base sm:text-lg text-muted-foreground leading-relaxed max-w-xl">
              AutoAcquire AI qualifies private vehicle sellers, scores every lead on explainable rules, matches your inventory, estimates financing, and books the appraisal — so your team only works the deals worth working.
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
              <img src={HERO_IMG} alt="" className="w-full h-72 object-cover opacity-70" />
              <div className="absolute inset-0 bg-black/50" />
              {/* floating qualified-lead card */}
              <div className="absolute inset-x-4 bottom-4 rounded-[6px] border border-white/15 bg-black/70 backdrop-blur-md p-4">
                <div className="flex items-center justify-between">
                  <span className="font-mono-plex text-[10px] uppercase tracking-widest text-primary">Qualified lead</span>
                  <span className="text-xs font-semibold text-white bg-primary/20 border border-primary/30 rounded-full px-2 py-0.5">Score 87</span>
                </div>
                <div className="mt-2 font-head font-bold text-white">2021 Toyota RAV4 · 42,000 km</div>
                <div className="mt-1 text-xs text-muted-foreground">Intent: Trade-in · Financing est. ready · Appraisal offered</div>
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
      <section id="how" className="max-w-7xl mx-auto px-6 py-28">
        <Eyebrow>How it works</Eyebrow>
        <h2 className="mt-3 font-head font-black text-3xl sm:text-4xl tracking-tight text-white max-w-2xl">
          From a cold "is my car worth anything?" to a booked appraisal.
        </h2>
        <div className="mt-12 grid grid-cols-1 md:grid-cols-12 gap-6">
          <div className="md:col-span-8 rounded-[6px] border border-border bg-card p-8 hover:border-white/20 transition-colors duration-200">
            <div className="flex items-center gap-3">
              <ChatCircleDots size={22} weight="bold" className="text-primary" />
              <span className="font-mono-plex text-[11px] uppercase tracking-widest text-muted-foreground">Step 01 · Conversation</span>
            </div>
            <h3 className="mt-4 font-head font-bold text-2xl text-white">The AI talks to the seller like a person</h3>
            <p className="mt-3 text-muted-foreground leading-relaxed max-w-xl">
              It extracts the vehicle, mileage, condition, ownership status, and the seller's real intent — sell, trade, or upgrade — without a single form field.
            </p>
          </div>
          <div className="md:col-span-4 rounded-[6px] border border-border bg-card p-8 hover:border-white/20 transition-colors duration-200">
            <div className="flex items-center gap-3">
              <ChartLineUp size={22} weight="bold" className="text-primary" />
              <span className="font-mono-plex text-[11px] uppercase tracking-widest text-muted-foreground">Step 02 · Scoring</span>
            </div>
            <h3 className="mt-4 font-head font-bold text-2xl text-white">Every lead scored</h3>
            <p className="mt-3 text-muted-foreground leading-relaxed">Fixed, explainable rules decide who's hot — no black box.</p>
          </div>
          <div className="md:col-span-4 rounded-[6px] border border-border bg-card p-8 hover:border-white/20 transition-colors duration-200">
            <div className="flex items-center gap-3">
              <Car size={22} weight="bold" className="text-primary" />
              <span className="font-mono-plex text-[11px] uppercase tracking-widest text-muted-foreground">Step 03 · Match</span>
            </div>
            <h3 className="mt-4 font-head font-bold text-2xl text-white">Inventory match</h3>
            <p className="mt-3 text-muted-foreground leading-relaxed">Upgraders are paired with cars you actually have on the lot.</p>
          </div>
          <div className="md:col-span-8 rounded-[6px] border border-border bg-card p-8 hover:border-white/20 transition-colors duration-200 flex flex-col justify-between">
            <div>
              <div className="flex items-center gap-3">
                <CalendarCheck size={22} weight="bold" className="text-primary" />
                <span className="font-mono-plex text-[11px] uppercase tracking-widest text-muted-foreground">Step 04 · Appointment</span>
              </div>
              <h3 className="mt-4 font-head font-bold text-2xl text-white">Booked on your calendar, automatically</h3>
              <p className="mt-3 text-muted-foreground leading-relaxed max-w-xl">
                The AI offers only real, open slots and confirms the appraisal — then hands your team a fully-briefed, ready-to-work lead.
              </p>
            </div>
            <Link to="/login" data-testid="how-cta" className="mt-6 inline-flex items-center gap-1.5 text-sm font-semibold text-primary hover:gap-2.5 transition-all duration-200">
              See it in your dashboard <CaretRight size={15} weight="bold" />
            </Link>
          </div>
        </div>
      </section>

      {/* FEATURES */}
      <section id="features" className="border-t border-white/10 bg-card/30">
        <div className="max-w-7xl mx-auto px-6 py-28">
          <Eyebrow>The platform</Eyebrow>
          <h2 className="mt-3 font-head font-black text-3xl sm:text-4xl tracking-tight text-white max-w-2xl">
            Everything acquisition needs, in one deterministic system.
          </h2>
          <div className="mt-12 grid grid-cols-1 md:grid-cols-3 gap-6">
            {FEATURES.map((f) => (
              <div key={f.title} data-testid={`feature-${f.title.toLowerCase().replace(/\s+/g, "-")}`}
                className="group rounded-[6px] border border-border bg-background p-8 hover:border-white/20 hover:-translate-y-1 transition-[transform,border-color] duration-200">
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

      {/* FOR DEALERSHIPS */}
      <section id="dealers" className="max-w-7xl mx-auto px-6 py-32 grid lg:grid-cols-2 gap-14 items-center">
        <div>
          <Eyebrow>For dealerships</Eyebrow>
          <h2 className="mt-3 font-head font-black text-3xl sm:text-4xl tracking-tight text-white leading-tight">
            Stop chasing tire-kickers. Start filling the appraisal lane.
          </h2>
          <p className="mt-5 text-muted-foreground leading-relaxed">
            AutoAcquire runs 24/7 as your acquisition front-desk. Set your rules once — mileage caps, allowed makes, hours — and let the AI qualify and book while your team focuses on closing.
          </p>
          <ul className="mt-8 space-y-4">
            {[
              "Multi-tenant, role-based access for your whole team",
              "Live human takeover on any conversation, anytime",
              "Explainable scores you can defend to a GM",
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
        <div className="max-w-7xl mx-auto px-6 py-24">
          <div className="rounded-[8px] border border-white/10 bg-card p-10 sm:p-14 text-center relative overflow-hidden">
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
            <div className="font-mono-plex text-[11px] text-muted-foreground/60 tracking-wider">© 2026 AutoAcquire AI</div>
          </div>
        </div>
      </footer>
    </div>
  );
}
