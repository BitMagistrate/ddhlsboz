import { NavLink, Route, Routes } from "react-router-dom";

import { DispatchPage } from "@/pages/dispatch";
import { FloodWatchPage } from "@/pages/flood-watch";
import { TollYieldPage } from "@/pages/toll-yield";
import { SiteSelectionPage } from "@/pages/site-selection";
import { FleetMatchPage } from "@/pages/fleet-match";

const LINK = ({ isActive }: { isActive: boolean }) => (isActive ? "active" : "");

export function App() {
  return (
    <div className="app">
      <aside className="sidebar">
        <h1>
          Road<span>Pulse</span>
        </h1>
        <div className="data-banner" role="status">
          synthetic-fixtures · no real VETC feed yet
        </div>
        <nav>
          <NavLink to="/" end className={LINK}>Dispatch</NavLink>
          <NavLink to="/flood-watch" className={LINK}>Flood watch</NavLink>
          <NavLink to="/toll-yield" className={LINK}>Toll yield</NavLink>
          <NavLink to="/site-selection" className={LINK}>Site selection</NavLink>
          <NavLink to="/fleet-match" className={LINK}>Fleet match</NavLink>
        </nav>
        <div className="footer">
          v0.1.0 · HCMC · k-anon ≥ 50
          <br />© RoadPulse JSC · Vietnam
        </div>
      </aside>
      <main>
        <Routes>
          <Route index element={<DispatchPage />} />
          <Route path="flood-watch" element={<FloodWatchPage />} />
          <Route path="toll-yield" element={<TollYieldPage />} />
          <Route path="site-selection" element={<SiteSelectionPage />} />
          <Route path="fleet-match" element={<FleetMatchPage />} />
        </Routes>
      </main>
    </div>
  );
}
