import { useState } from "react";
import { Link } from "react-router-dom";
import client, { formatError } from "@/lib/api";
import { ArrowLeft } from "@phosphor-icons/react";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    try {
      await client.post("/auth/forgot-password", { email });
      setSent(true);
    } catch (err) {
      setError(formatError(err.response?.data?.detail));
    }
  };

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-6">
      <div className="w-full max-w-sm">
        <Link to="/login" className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground mb-6 transition-colors duration-200">
          <ArrowLeft size={16} /> Back to sign in
        </Link>
        <h2 className="font-head font-extrabold text-2xl tracking-tight">Reset password</h2>
        {sent ? (
          <p className="mt-4 text-sm text-muted-foreground">If an account exists for <b>{email}</b>, a reset link has been generated (check the server logs in this demo).</p>
        ) : (
          <form onSubmit={submit} className="mt-6 space-y-4">
            <input data-testid="forgot-email" type="email" placeholder="you@dealership.com" value={email} onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-[4px] border border-input bg-card px-3 py-2.5 text-sm outline-none focus:border-primary focus:ring-1 focus:ring-primary transition-colors duration-200" />
            {error && <div className="text-sm text-destructive">{error}</div>}
            <button data-testid="forgot-submit" className="w-full bg-primary text-primary-foreground font-semibold rounded-[4px] py-2.5 text-sm hover:opacity-90 transition-opacity duration-200">
              Send reset link
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
