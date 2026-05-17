import { NavLink, Route, Routes } from "react-router-dom";

import { DispatchPage } from "@/pages/dispatch";
import { TollYieldPage } from "@/pages/toll-yield";
import { SiteSelectionPage } from "@/pages/site-selection";
import { FleetMatchPage } from "@/pages/fleet-match";

export function App() {
  return (
    <div className="app">
      <aside className="sidebar">
        <h1>
          Road<span>Pulse</span>
        </h1>
        <nav>
          <NavLink to="/" end className={({ isActive }) => (isActive ? "active" : "")}>
            Dispatch
          </NavLink>
          <NavLink to="/toll-yield" className={({ isActive }) => (isActive ? "active" : "")}>
            Toll yield
          </NavLink>
          <NavLink to="/site-selection" className={({ isActive }) => (isActive ? "active" : "")}>
            Site selection
          </NavLink>
          <NavLink to="/fleet-match" className={({ isActive }) => (isActive ? "active" : "")}>
            Fleet match
          </NavLink>
        </nav>
        <div className="footer">
          v0.1.0 · HCMC · k-anon ≥ 50
          <br />© RoadPulse JSC · Vietnam
        </div>
      </aside>
      <main>
        <Routes>
          <Route index element={<DispatchPage />} />
          <Route path="toll-yield" element={<TollYieldPage />} />
          <Route path="site-selection" element={<SiteSelectionPage />} />
          <Route path="fleet-match" element={<FleetMatchPage />} />
        </Routes>
      </main>
    </div>
  );
}
