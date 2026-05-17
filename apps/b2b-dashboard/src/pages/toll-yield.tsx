/**
 * Toll yield mini-widget — visualises the 5% upside lift on dynamic toll
 * pricing that we forecast in the pitch (section 4.2.B).
 */
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

const ROWS = Array.from({ length: 12 }).map((_, i) => ({
  month: `M${i + 1}`,
  baseline: 110 + i * 4 + (i % 3 === 0 ? 6 : 0),
  withRoadPulse: 110 + i * 4 + (i % 3 === 0 ? 6 : 0) + 6 + i * 0.5,
}));

const NEXT_GANTRY = [
  { name: "Long Thành expressway · gantry 3",  recommended_vnd: 47_500, baseline_vnd: 45_000, delta_pct: 5.5 },
  { name: "Trung Lương expressway · gantry 1", recommended_vnd: 41_000, baseline_vnd: 40_000, delta_pct: 2.5 },
  { name: "Hà Nội — Hải Phòng · gantry 5",    recommended_vnd: 32_000, baseline_vnd: 30_000, delta_pct: 6.7 },
];

export function TollYieldPage() {
  return (
    <section>
      <header className="page-header">
        <div>
          <h2>Toll yield</h2>
          <div className="muted">Dynamic pricing recommendation engine · VEC / TASCO concessionaires</div>
        </div>
        <span className="pill good">+5.4% yield (90-day rolling)</span>
      </header>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Monthly revenue, ₫bn</h3>
        <div style={{ width: "100%", height: 300 }}>
          <ResponsiveContainer>
            <AreaChart data={ROWS} margin={{ top: 12, right: 12, bottom: 4, left: 4 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="month" stroke="#475569" />
              <YAxis stroke="#475569" />
              <Tooltip />
              <Area type="monotone" dataKey="baseline" stroke="#94a3b8" fill="#cbd5f5" />
              <Area type="monotone" dataKey="withRoadPulse" stroke="#2563EB" fill="#dbeafe" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="card section">
        <h3 style={{ marginTop: 0 }}>Next-gantry price recommendations</h3>
        <table>
          <thead>
            <tr>
              <th>Gantry</th>
              <th>Baseline</th>
              <th>Recommended</th>
              <th>Δ</th>
            </tr>
          </thead>
          <tbody>
            {NEXT_GANTRY.map((g) => (
              <tr key={g.name}>
                <td>{g.name}</td>
                <td>{g.baseline_vnd.toLocaleString("vi-VN")} ₫</td>
                <td>{g.recommended_vnd.toLocaleString("vi-VN")} ₫</td>
                <td>
                  <span className={`pill ${g.delta_pct >= 5 ? "good" : "hazard"}`}>
                    +{g.delta_pct.toFixed(1)}%
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
