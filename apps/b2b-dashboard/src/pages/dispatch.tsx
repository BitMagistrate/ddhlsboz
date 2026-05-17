/**
 * Dispatch — operator console for last-mile fleets. Renders a live batch ETA
 * table plus a flood-aware re-route suggestion column. Inspired by the
 * COO-level "tower" view in the pitch (section 4.2.A).
 */
import { useMutation } from "@tanstack/react-query";
import { useMemo } from "react";

import { api, type EtaBatchItem } from "@/lib/api";

const DEMO_BATCH: EtaBatchItem[] = [
  { order_id: "ORD-22001", origin: { lat: 10.776, lng: 106.700 }, destination: { lat: 10.737, lng: 106.722 } },
  { order_id: "ORD-22002", origin: { lat: 10.762, lng: 106.660 }, destination: { lat: 10.797, lng: 106.679 } },
  { order_id: "ORD-22003", origin: { lat: 10.785, lng: 106.659 }, destination: { lat: 10.751, lng: 106.740 } },
  { order_id: "ORD-22004", origin: { lat: 10.790, lng: 106.700 }, destination: { lat: 10.772, lng: 106.668 } },
  { order_id: "ORD-22005", origin: { lat: 10.745, lng: 106.681 }, destination: { lat: 10.806, lng: 106.720 } },
  { order_id: "ORD-22006", origin: { lat: 10.802, lng: 106.700 }, destination: { lat: 10.770, lng: 106.700 } },
];

export function DispatchPage() {
  const eta = useMutation({ mutationFn: () => api.etaBatch(DEMO_BATCH) });
  const summary = useMemo(() => {
    if (!eta.data) return null;
    const preds = eta.data.predictions;
    const onTime = preds.filter((p) => p.flood_score < 0.4).length;
    const flooded = preds.filter((p) => p.flood_score >= 0.4).length;
    const avgEta = preds.reduce((acc, p) => acc + p.eta_s, 0) / Math.max(preds.length, 1);
    return { onTime, flooded, avgEta };
  }, [eta.data]);

  return (
    <section>
      <header className="page-header">
        <div>
          <h2>Dispatch tower</h2>
          <div className="muted">Last-mile fleets · batch ETA · flood-aware re-route</div>
        </div>
        <button
          type="button"
          className="button"
          disabled={eta.isPending}
          onClick={() => eta.mutate()}
        >
          {eta.isPending ? "Predicting…" : "Run batch ETA"}
        </button>
      </header>

      {summary && (
        <div className="kpi-grid">
          <Kpi label="Orders in batch" value={DEMO_BATCH.length.toString()} />
          <Kpi label="On-time forecast" value={summary.onTime.toString()} />
          <Kpi label="Flood-risk orders" value={summary.flooded.toString()} tone="hazard" />
          <Kpi label="Avg ETA" value={`${Math.round(summary.avgEta / 60)} min`} />
        </div>
      )}

      {eta.isError && <p style={{ color: "var(--rp-bad)" }}>{(eta.error as Error).message}</p>}

      {eta.data && (
        <div className="card">
          <table>
            <thead>
              <tr>
                <th>Order</th>
                <th>Distance</th>
                <th>ETA</th>
                <th>P10–P90</th>
                <th>Flood</th>
                <th>Confidence</th>
              </tr>
            </thead>
            <tbody>
              {eta.data.predictions.map((p) => (
                <tr key={p.order_id}>
                  <td>{p.order_id}</td>
                  <td>{(p.distance_m / 1000).toFixed(2)} km</td>
                  <td>{Math.round(p.eta_s / 60)} min</td>
                  <td>
                    {Math.round(p.eta_p10_s / 60)} – {Math.round(p.eta_p90_s / 60)} min
                  </td>
                  <td>
                    <span className={`pill ${p.flood_score >= 0.7 ? "bad" : p.flood_score >= 0.4 ? "hazard" : "good"}`}>
                      {(p.flood_score * 100).toFixed(0)}%
                    </span>
                  </td>
                  <td>{p.confidence}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function Kpi({ label, value, tone }: { label: string; value: string; tone?: "hazard" }) {
  return (
    <div className="kpi-card" style={tone === "hazard" ? { borderColor: "var(--rp-hazard)" } : undefined}>
      <div className="kpi-label">{label}</div>
      <div className="kpi-value" style={tone === "hazard" ? { color: "var(--rp-hazard)" } : undefined}>
        {value}
      </div>
    </div>
  );
}
