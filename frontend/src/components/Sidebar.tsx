/**
 * ThreatTron AI — Sidebar Navigation
 */

import { NavLink } from "react-router-dom";

const links = [
  { to: "/", label: "Dashboard", icon: "📊" },
  { to: "/analytics", label: "Analytics", icon: "📈" },
  { to: "/sandbox", label: "ML Sandbox", icon: "🧪" },
];

export default function Sidebar() {
  return (
    <aside className="fixed left-0 top-0 bottom-0 w-60 bg-navy-950/80 backdrop-blur-xl border-r border-white/5 flex flex-col z-50">
      {/* Logo */}
      <div className="px-6 py-6 border-b border-white/5">
        <h1 className="text-lg font-bold tracking-tight">
          <span className="text-cyan-400">Threat</span>
          <span className="text-purple-400">Tron</span>
          <span className="text-white/60 ml-1.5 text-sm font-medium">AI</span>
        </h1>
        <p className="text-[10px] text-white/30 mt-1 tracking-wider uppercase">
          Behavioral Fraud Detection
        </p>
      </div>

      {/* Nav */}
      <nav className="flex-1 py-4 px-3 space-y-1">
        {links.map((link) => (
          <NavLink
            key={link.to}
            to={link.to}
            className={({ isActive }) =>
              `flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all duration-200 ${
                isActive
                  ? "bg-cyan-500/15 text-cyan-400 shadow-lg shadow-cyan-500/5"
                  : "text-white/50 hover:text-white/80 hover:bg-white/5"
              }`
            }
          >
            <span className="text-base">{link.icon}</span>
            {link.label}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="px-6 py-4 border-t border-white/5">
        <p className="text-[10px] text-white/20 text-center">
          ThreatTron AI v1.0
        </p>
      </div>
    </aside>
  );
}
