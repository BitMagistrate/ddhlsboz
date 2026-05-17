/**
 * Fleet match — load-matching marketplace UI. Operator shippers post an O-D
 * pair, the API returns ranked candidate fleets with bids and flood safety
 * flags.
 */
import { useMutation } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { api } from "@/lib/api";

const DEMO = {
  origin:      { lat: 10.806, lng: 106.700 },
  destination: { lat: 10.737, lng: 106.722 },
};

export function FleetMatchPage() {
  const match = useMutation({ mutationFn: () => api.fleetMatch(DEMO.origin, DEMO.destination) });
  return (
    <section>
      <header className="page-header">
        <div>
          <h2>Fleet match</h2>
          <div className="muted">Load-matching marketplace · ranked by ETA, bid &amp; flood safety</div>
        </div>
        <button
          type="button"
          className="button"
          disabled={match.isPending}
          onClick={() => match.mutate()}
        >
          {match.isPending ? "Matching…" : "Find fleets"}
        </button>
      </header>

      {match.isError && <p style={{ color: "var(--rp-bad)" }}>{(match.error as Error).message}</p>}

      {match.data && (
        <div className="chart-grid">
          <div className="chart-card">
            <h3>Bids by fleet (₫)</h3>
            <div className="muted">Green = flood-safe, amber = re-route advised</div>
            <div style={{ width: "100%", height: 240 }}>
              <ResponsiveContainer>
                <BarChart
                  data={match.data.candidates.map((c) => ({
                    fleet_name: c.fleet_name,
                    bid_vnd: c.bid_vnd,
                  }))}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="fleet_name" stroke="#475569" fontSize={11} />
                  <YAxis stroke="#475569" />
                  <Tooltip formatter={(v: number) => `${v.toLocaleString("vi-VN")} ₫`} />
                  <Bar dataKey="bid_vnd">
                    {match.data.candidates.map((c) => (
                      <Cell key={c.fleet_id} fill={c.flood_safe ? "#16A34A" : "#F59E0B"} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      )}

      {match.data && (
        <div className="card section">
          <table>
            <thead>
              <tr>
                <th>Fleet</th>
                <th>Vehicle</th>
                <th>ETA</th>
                <th>Bid</th>
                <th>Flood-safe</th>
              </tr>
            </thead>
            <tbody>
              {match.data.candidates.map((c) => (
                <tr key={c.fleet_id}>
                  <td>{c.fleet_name}</td>
                  <td>{c.vehicle_class}</td>
                  <td>{Math.round(c.eta_s / 60)} min</td>
                  <td>{c.bid_vnd.toLocaleString("vi-VN")} ₫</td>
                  <td>
                    <span className={`pill ${c.flood_safe ? "good" : "hazard"}`}>
                      {c.flood_safe ? "Yes" : "Re-route advised"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
