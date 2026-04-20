import { useEffect, useState } from "react";

const API = "http://localhost:5000/api";

export default function Dashboard({ setPage }) {
  const [stats, setStats]   = useState({ total: 0, today: 0, unique: 0 });
  const [recent, setRecent] = useState([]);
  const [health, setHealth] = useState(null);

  useEffect(() => {
    fetchAll();
    const t = setInterval(fetchAll, 5000);
    return () => clearInterval(t);
  }, []);

  async function fetchAll() {
    try {
      const [s, d, h] = await Promise.all([
        fetch(`${API}/stats`).then(r => r.json()),
        fetch(`${API}/detections?limit=5`).then(r => r.json()),
        fetch(`${API}/health`).then(r => r.json()),
      ]);
      setStats(s);
      setRecent(d);
      setHealth(h.status);
    } catch {
      setHealth("offline");
    }
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1>Dashboard</h1>
        <span className={`status-pill ${health === "ok" ? "online" : "offline"}`}>
          {health === "ok" ? "Backend Online" : "Backend Offline"}
        </span>
      </div>

      <div className="stats-grid">
        <StatCard label="Total Detections" value={stats.total} color="blue" />
        <StatCard label="Today"            value={stats.today} color="green" />
        <StatCard label="Unique Plates"    value={stats.unique} color="amber" />
      </div>

      <div className="card">
        <div className="card-header">
          <h2>Recent Detections</h2>
          <button className="btn-text" onClick={() => setPage("history")}>View all →</button>
        </div>
        {recent.length === 0
          ? <p className="empty-msg">No detections yet. Start the live camera to begin.</p>
          : (
            <table className="plate-table">
              <thead>
                <tr><th>Plate</th><th>Confidence</th><th>Timestamp</th></tr>
              </thead>
              <tbody>
                {recent.map(r => (
                  <tr key={r.id}>
                    <td><span className="plate-badge">{r.plate}</span></td>
                    <td>{(r.confidence * 100).toFixed(0)}%</td>
                    <td>{r.timestamp}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )
        }
      </div>

      <div className="card cta-card">
        <h2>Start Detection</h2>
        <p>Point your webcam at a vehicle plate and let PlateWatch read it automatically.</p>
        <button className="btn-primary" onClick={() => setPage("live")}>
          Open Live Camera
        </button>
      </div>
    </div>
  );
}

function StatCard({ label, value, color }) {
  return (
    <div className={`stat-card stat-${color}`}>
      <span className="stat-value">{value}</span>
      <span className="stat-label">{label}</span>
    </div>
  );
}
