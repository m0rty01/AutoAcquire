import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import Login from "@/pages/Login";
import ForgotPassword from "@/pages/ForgotPassword";
import AuthCallback from "@/pages/AuthCallback";
import SellerChat from "@/pages/SellerChat";
import Layout from "@/components/Layout";
import Dashboard from "@/pages/Dashboard";
import Leads from "@/pages/Leads";
import LeadDetail from "@/pages/LeadDetail";
import Inventory from "@/pages/Inventory";
import Appointments from "@/pages/Appointments";
import Analytics from "@/pages/Analytics";
import Settings from "@/pages/Settings";
import PlatformAdmin from "@/pages/PlatformAdmin";
import "@/App.css";

function Protected({ children }) {
  const { authed } = useAuth();
  if (authed === null)
    return <div className="min-h-screen bg-background flex items-center justify-center font-mono-plex text-muted-foreground">Loading…</div>;
  if (!authed) return <Navigate to="/login" replace />;
  return children;
}

function RootRouter() {
  const location = useLocation();
  // Handle Emergent Google OAuth callback (session_id in URL fragment) before any route/auth check
  if (location.hash?.includes("session_id=")) return <AuthCallback />;
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/login" replace />} />
      <Route path="/login" element={<Login />} />
      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route path="/sell/:slug" element={<SellerChat />} />
      <Route path="/app" element={<Protected><Layout /></Protected>}>
        <Route index element={<Navigate to="/app/dashboard" replace />} />
        <Route path="dashboard" element={<Dashboard />} />
        <Route path="leads" element={<Leads />} />
        <Route path="leads/:id" element={<LeadDetail />} />
        <Route path="inventory" element={<Inventory />} />
        <Route path="appointments" element={<Appointments />} />
        <Route path="analytics" element={<Analytics />} />
        <Route path="settings" element={<Settings />} />
        <Route path="platform" element={<PlatformAdmin />} />
      </Route>
    </Routes>
  );
}

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <RootRouter />
      </BrowserRouter>
      <Toaster position="top-right" richColors />
    </AuthProvider>
  );
}

export default App;
