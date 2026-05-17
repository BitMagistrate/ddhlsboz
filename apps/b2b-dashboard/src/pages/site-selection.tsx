/**
 * Site selection — ranks hex cells by hourly O-D flow for retail / dark-store
 * planners. The bounding box defaults to inner HCMC.
 */
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { api } from "@/lib/api";

const HCMC_BBOX = { north: 10.82, south: 10.72, east: 106.76, west: 106.65 };

export function SiteSelectionPage() {
  const [hour, setHour] = useState(96);
  const sites = useQuery({
    queryKey: ["site-selection", hour],
    queryFn: () => api.siteSelection(HCMC_BBOX, hour),
  });

  return (
    <section>
      <header className="page-header">
        <div>
          <h2>Site selection</h2>
          <div className="muted">Hex-level O-D flow ranking for retail / dark-store rollouts</div>
        </div>
      </header>

      <div className="toolbar">
        <label htmlFor="hour-input">Hour of week</label>
        <input
          id="hour-input"
          type="number"
          min={0}
          max={167}
          value={hour}
          onChange={(e) => setHour(Number(e.target.value))}
        />
        <span className="muted">0 = Monday 00:00 · 96 = Friday 00:00</span>
      </div>

      <div className="card">
        {sites.isPending && <p>Crunching aggregated VETC flows…</p>}
        {sites.isError && <p style={{ color: "var(--rp-bad)" }}>{(sites.error as Error).message}</p>}
        {sites.data && (
          <table>
            <thead>
              <tr>
                <th>Rank</th>
                <th>Hex</th>
                <th>Origin flows</th>
                <th>Destination flows</th>
              </tr>
            </thead>
            <tbody>
              {sites.data.ranked.map((cell) => (
                <tr key={cell.hex_id}>
                  <td>#{cell.rank}</td>
                  <td>{cell.hex_id}</td>
                  <td>{cell.origin_flows.toLocaleString("vi-VN")}</td>
                  <td>{cell.destination_flows.toLocaleString("vi-VN")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}
