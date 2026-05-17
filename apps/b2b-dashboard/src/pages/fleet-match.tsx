/**
 * Fleet match — load-matching marketplace UI. Operator shippers post an O-D
 * pair, the API returns ranked candidate fleets with bids and flood safety
 * flags.
 */
import { useMutation } from "@tanstack/react-query";

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
        <div className="card">
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
