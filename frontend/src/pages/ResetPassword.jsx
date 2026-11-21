import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import client, { formatError } from "@/lib/api";

export default function ResetPassword() {
  const [params] = useSearchParams();
  const token = params.get("token") || "";
  const [pw, setPw] = useState("");
  const [pw2, setPw2] = useState("");
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    if (pw.length < 8) return setError("Password must be at least 8 characters.");
    if (pw !== pw2) return setError("Passwords do not match.");
    try { await client.post("/auth/reset-password", { token, password: pw }); setDone(true); }
    catch (err) { setError(formatError(err.response?.data?.detail)); }
  };
  const cls = "w-full rounded-[4px] border border-input bg-card px-3 py-2.5 text-sm outline-none focus:border-primary transition-colors duration-200";

  return (
    <div className="dark min-h-screen bg-background text-foreground flex items-center justify-center p-6">
      <div className="w-full max-w-sm" data-testid="reset-password-page">
        <h2 className="font-head font-extrabold text-2xl tracking-tight">Choose your password</h2>
        {done ? (
          <div className="mt-4 text-sm" data-testid="reset-success">Your password is set. <Link to="/login" className="text-primary hover:underline">Sign in</Link></div>
        ) : !token ? (
          <p className="mt-4 text-sm text-muted-foreground">This link is missing its token. Ask your administrator for a new one.</p>
        ) : (
          <form onSubmit={submit} className="mt-6 space-y-4">
            <input data-testid="reset-password-input" type="password" placeholder="New password (8+ characters)" value={pw} onChange={(e) => setPw(e.target.value)} className={cls} />
            <input data-testid="reset-password-confirm" type="password" placeholder="Confirm password" value={pw2} onChange={(e) => setPw2(e.target.value)} className={cls} />
            {error && <div data-testid="reset-error" className="text-sm text-destructive">{error}</div>}
            <button data-testid="reset-submit" className="w-full bg-primary text-primary-foreground font-semibold rounded-[4px] py-2.5 text-sm hover:opacity-90">Set password</button>
          </form>
        )}
      </div>
    </div>
  );
}
