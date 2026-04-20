import { useEffect, useState } from "react";

const API = "http://localhost:5000/api";

export default function History() {
  const [rows, setRows]       = useState([]);
  const [search, setSearch]   = useState("");
  const [loading, setLoading] = useState(true);
  const [confirm, setConfirm] = useState(false);

  useEffect(() => { load(); }, []);

  async function load() {
    setLoading(true);
    const data = await fetch(`${API}/detections?limit=500`).then(r => r.json());
    setRows(data);
    setLoading(false);
  }

  async function deleteRow(id) {
    await fetch(`${API}/detections/${id}`, { method: "DELETE" });
    setRows(prev => prev.filter(r => r.id !== id));
  }

  async function clearAll() {
    await fetch(`${API}/detections`, { method: "DELETE" });
    setRows([]);
    setConfirm(false);
  }

  const filtered = rows.filter(r =>
    r.plate.toLowerCase().includes(search.toLowerCase()) ||
    r.timestamp.includes(search)
  );

  return (
    <div className="page">
      <div className="page-header">
        <h1>Detection History</h1>
        <span className="stat-pill">{rows.length} records</span>
      </div>

      <div className="toolbar">
        <input
          className="search-input"
          type="text"
          placeholder="Search by plate or date…"
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
        {!confirm
          ? <button className="btn-outline-danger" onClick={() => setConfirm(true)}>Clear All</button>
          : (
            <div className="confirm-row">
              <span>Are you sure?</span>
              <button className="btn-danger" onClick={clearAll}>Yes, delete all</button>
              <button className="btn-ghost" onClick={() => setConfirm(false)}>Cancel</button>
            </div>
          )
        }
      </div>

      {loading
        ? <p className="empty-msg">Loading…</p>
        : filtered.length === 0
          ? <p className="empty-msg">{search ? "No results found." : "No detections yet."}</p>
          : (
            <div className="card table-card">
              <table className="plate-table full-table">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Plate</th>
                    <th>Confidence</th>
                    <th>Timestamp</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((r, i) => (
                    <tr key={r.id}>
                      <td className="row-num">{i + 1}</td>
                      <td><span className="plate-badge">{r.plate}</span></td>
                      <td>
                        <div className="conf-bar-wrap">
                          <div className="conf-bar" style={{ width: `${r.confidence * 100}%` }} />
                          <span>{(r.confidence * 100).toFixed(0)}%</span>
                        </div>
                      </td>
                      <td>{r.timestamp}</td>
                      <td>
                        <button className="btn-icon-danger" onClick={() => deleteRow(r.id)} title="Delete">
                          ✕
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
      }
    </div>
  );
}
