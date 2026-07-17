import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import client, { formatError } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Robot, ArrowRight } from "@phosphor-icons/react";

const BG = "https://images.unsplash.com/photo-1780319234030-281034892350?crop=entropy&cs=srgb&fm=jpg&q=85&w=1600";

export default function Login() {
  const [email, setEmail] = useState("admin@autoacquire.ai");
  const [password, setPassword] = useState("Admin123!");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const submit = async (e) => {
    e.preventDefault();
    setError(""); setLoading(true);
    try {
      const { data } = await client.post("/auth/login", { email, password });
      login(data.token, data.user);
      navigate("/app/dashboard");
    } catch (err) {
      setError(formatError(err.response?.data?.detail) || err.message);
    } finally { setLoading(false); }
  };

  // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
  const googleLogin = () => {
    const redirectUrl = window.location.origin + "/app/dashboard";
    window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
  };

  return (
    <div className="min-h-screen grid lg:grid-cols-2 bg-background">
      {/* left brand panel */}
      <div className="relative hidden lg:flex flex-col justify-between p-12 overflow-hidden">
        <img src={BG} alt="Dealership" className="absolute inset-0 w-full h-full object-cover" />
        <div className="absolute inset-0 bg-black/65" />
        <div className="relative flex items-center gap-2 text-white">
          <div className="w-9 h-9 rounded-[4px] bg-primary flex items-center justify-center">
            <Robot size={22} weight="bold" />
          </div>
          <span className="font-head font-black text-xl tracking-tight">AutoAcquire<span className="text-primary">AI</span></span>
        </div>
        <div className="relative text-white max-w-md">
          <h1 className="font-head font-black text-4xl lg:text-5xl tracking-tighter leading-[1.05]">
            Turn seller conversations into booked appointments.
          </h1>
          <p className="mt-4 text-white/70 text-base leading-relaxed">
            AI qualifies private vehicle sellers, scores every lead, matches inventory, and books appraisals — so your team works only the deals worth working.
          </p>
        </div>
        <div className="relative font-mono-plex text-xs text-white/50 tracking-wider">PILOT · CANADA / US</div>
      </div>

      {/* right form */}
      <div className="flex items-center justify-center p-6 sm:p-12">
        <div className="w-full max-w-sm">
          <div className="lg:hidden flex items-center gap-2 mb-8">
            <div className="w-9 h-9 rounded-[4px] bg-primary flex items-center justify-center">
              <Robot size={22} weight="bold" className="text-white" />
            </div>
            <span className="font-head font-black text-xl tracking-tight">AutoAcquire<span className="text-primary">AI</span></span>
          </div>
          <h2 className="font-head font-extrabold text-2xl tracking-tight">Sign in</h2>
          <p className="text-sm text-muted-foreground mt-1">Dealership workspace access.</p>

          <form onSubmit={submit} className="mt-8 space-y-4">
            <div>
              <label className="text-xs font-mono-plex uppercase tracking-[0.15em] text-muted-foreground">Email</label>
              <input data-testid="login-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                className="mt-1.5 w-full rounded-[4px] border border-input bg-card px-3 py-2.5 text-sm outline-none focus:border-primary focus:ring-1 focus:ring-primary transition-colors duration-200" />
            </div>
            <div>
              <div className="flex justify-between items-center">
                <label className="text-xs font-mono-plex uppercase tracking-[0.15em] text-muted-foreground">Password</label>
                <Link to="/forgot-password" className="text-xs text-primary hover:underline">Forgot?</Link>
              </div>
              <input data-testid="login-password" type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                className="mt-1.5 w-full rounded-[4px] border border-input bg-card px-3 py-2.5 text-sm outline-none focus:border-primary focus:ring-1 focus:ring-primary transition-colors duration-200" />
            </div>
            {error && <div data-testid="login-error" className="text-sm text-destructive bg-destructive/10 border border-destructive/20 rounded-[4px] px-3 py-2">{error}</div>}
            <button data-testid="login-submit" disabled={loading}
              className="w-full flex items-center justify-center gap-2 bg-primary text-primary-foreground font-semibold rounded-[4px] py-2.5 text-sm hover:opacity-90 transition-opacity duration-200 disabled:opacity-50">
              {loading ? "Signing in…" : <>Sign in <ArrowRight size={16} weight="bold" /></>}
            </button>
          </form>

          <div className="flex items-center gap-3 my-5">
            <div className="h-px flex-1 bg-border" />
            <span className="text-xs font-mono-plex text-muted-foreground uppercase tracking-wider">or</span>
            <div className="h-px flex-1 bg-border" />
          </div>

          <button data-testid="google-login-btn" onClick={googleLogin}
            className="w-full flex items-center justify-center gap-3 border border-border bg-card rounded-[4px] py-2.5 text-sm font-medium hover:bg-secondary transition-colors duration-200">
            <img src="https://www.gstatic.com/firebasejs/ui/2.0.0/images/auth/google.svg" alt="" className="w-4 h-4" />
            Continue with Google
          </button>

          <div className="mt-8 rounded-[4px] border border-border bg-secondary/50 p-4 text-xs font-mono-plex text-muted-foreground space-y-1">
            <div className="text-foreground font-semibold mb-1">Demo accounts</div>
            <div>admin@autoacquire.ai · Admin123!</div>
            <div>manager@autoacquire.ai · Manager123!</div>
            <div>rep1@autoacquire.ai · Rep123!</div>
          </div>
        </div>
      </div>
    </div>
  );
}
