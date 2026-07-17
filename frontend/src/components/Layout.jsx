import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import {
  SquaresFour, Users, CalendarBlank, Car, ChartBar, GearSix, SignOut, Buildings, Robot, Copy,
} from "@phosphor-icons/react";
import { toast } from "sonner";

const NAV = [
  { to: "/app/dashboard", label: "Dashboard", icon: SquaresFour },
  { to: "/app/leads", label: "Leads", icon: Users },
  { to: "/app/appointments", label: "Appointments", icon: CalendarBlank },
  { to: "/app/inventory", label: "Inventory", icon: Car },
  { to: "/app/analytics", label: "Analytics", icon: ChartBar },
  { to: "/app/settings", label: "Settings", icon: GearSix },
];

export default function Layout() {
  const { user, org, logout } = useAuth();
  const navigate = useNavigate();
  const isPlatform = user?.role === "platform_admin";
  const sellUrl = org ? `${window.location.origin}/sell/${org.slug}` : "";

  return (
    <div className="dark min-h-screen bg-background text-foreground flex">
      {/* sidebar */}
      <aside className="w-16 lg:w-60 shrink-0 border-r border-border flex flex-col bg-card">
        <div className="h-16 flex items-center gap-2 px-4 border-b border-border">
          <div className="w-8 h-8 rounded-[4px] bg-primary flex items-center justify-center shrink-0">
            <Robot size={20} weight="bold" className="text-white" />
          </div>
          <span className="hidden lg:block font-head font-black tracking-tight text-lg leading-none">
            AutoAcquire<span className="text-primary">AI</span>
          </span>
        </div>
        <nav className="flex-1 py-4 space-y-1 px-2">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              data-testid={`nav-${n.label.toLowerCase()}`}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-[4px] text-sm font-medium transition-colors duration-200 ${
                  isActive ? "bg-primary/15 text-primary" : "text-muted-foreground hover:bg-secondary hover:text-foreground"
                }`
              }
            >
              <n.icon size={20} weight="bold" />
              <span className="hidden lg:block">{n.label}</span>
            </NavLink>
          ))}
          {isPlatform && (
            <NavLink to="/app/platform" data-testid="nav-platform"
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-[4px] text-sm font-medium transition-colors duration-200 ${
                  isActive ? "bg-primary/15 text-primary" : "text-muted-foreground hover:bg-secondary hover:text-foreground"
                }`}>
              <Buildings size={20} weight="bold" />
              <span className="hidden lg:block">Platform</span>
            </NavLink>
          )}
        </nav>
        <div className="p-2 border-t border-border">
          <button data-testid="logout-btn" onClick={() => { logout(); navigate("/login"); }}
            className="flex items-center gap-3 px-3 py-2.5 w-full rounded-[4px] text-sm text-muted-foreground hover:bg-secondary hover:text-foreground transition-colors duration-200">
            <SignOut size={20} weight="bold" />
            <span className="hidden lg:block">Log out</span>
          </button>
        </div>
      </aside>

      {/* main */}
      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-16 border-b border-border flex items-center justify-between px-4 lg:px-8 bg-card/50">
          <div className="min-w-0">
            <div className="font-head font-extrabold tracking-tight truncate">{org?.name || "Dealership"}</div>
            <div className="text-xs text-muted-foreground font-mono-plex">{user?.email} · {user?.role?.replace(/_/g, " ")}</div>
          </div>
          {sellUrl && (
            <button data-testid="copy-seller-url"
              onClick={() => { navigator.clipboard.writeText(sellUrl); toast.success("Seller conversation URL copied"); }}
              className="hidden sm:flex items-center gap-2 text-xs font-mono-plex bg-secondary hover:bg-accent px-3 py-2 rounded-[4px] transition-colors duration-200">
              <Copy size={14} /> Copy seller link
            </button>
          )}
        </header>
        <main className="flex-1 overflow-y-auto p-4 lg:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
