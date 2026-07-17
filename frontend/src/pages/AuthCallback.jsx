import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import client from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

// REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
export default function AuthCallback() {
  const navigate = useNavigate();
  const { login } = useAuth();
  const processed = useRef(false);

  useEffect(() => {
    if (processed.current) return;
    processed.current = true;
    const hash = window.location.hash || "";
    const sessionId = new URLSearchParams(hash.replace(/^#/, "")).get("session_id");
    if (!sessionId) { navigate("/login", { replace: true }); return; }
    (async () => {
      try {
        const { data } = await client.post("/auth/google/session", {}, { headers: { "X-Session-ID": sessionId } });
        window.history.replaceState(null, "", "/app/dashboard");
        login(data.token, data.user);
        navigate("/app/dashboard", { replace: true });
      } catch {
        navigate("/login", { replace: true });
      }
    })();
  }, [login, navigate]);

  return (
    <div className="min-h-screen bg-background flex items-center justify-center font-mono-plex text-muted-foreground">
      Signing you in…
    </div>
  );
}
