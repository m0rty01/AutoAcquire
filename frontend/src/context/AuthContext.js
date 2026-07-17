import { createContext, useContext, useEffect, useState } from "react";
import client from "@/lib/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null); // null = checking
  const [org, setOrg] = useState(null);
  const [authed, setAuthed] = useState(null); // null checking, true/false

  const load = async () => {
    const token = localStorage.getItem("aa_token");
    if (!token) { setAuthed(false); return; }
    try {
      const { data } = await client.get("/auth/me");
      setUser(data.user);
      setOrg(data.organization);
      setAuthed(true);
    } catch {
      localStorage.removeItem("aa_token");
      setAuthed(false);
    }
  };

  useEffect(() => { load(); }, []);

  const login = (token, u) => {
    localStorage.setItem("aa_token", token);
    setUser(u);
    setAuthed(true);
    load();
  };

  const logout = () => {
    localStorage.removeItem("aa_token");
    setUser(null);
    setOrg(null);
    setAuthed(false);
  };

  return (
    <AuthContext.Provider value={{ user, org, authed, login, logout, refresh: load }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
