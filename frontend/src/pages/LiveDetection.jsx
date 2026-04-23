import { useState, useEffect, useRef } from "react";

const API = "http://localhost:5000/api";

export default function LiveDetection() {
  const [streaming, setStreaming]   = useState(false);
  const [latest, setLatest]         = useState([]);
  const [totalSaved, setTotalSaved] = useState(0);
  const pollRef = useRef(null);
  const prevIds = useRef(new Set());

  function startStream() {
    setStreaming(true);

    // ✅ prevent multiple intervals
    if (!pollRef.current) {
      pollRef.current = setInterval(fetchLatest, 1500);
    }
  }

  async function stopStream() {
    await fetch(`${API}/stop`, { method: "POST" });

    setStreaming(false);

    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }

  async function fetchLatest() {
    const rows = await fetch(`${API}/detections?limit=20`).then(r => r.json());

    const newRows = rows.map(r => ({
      ...r,
      isNew: !prevIds.current.has(r.id)
    }));

    rows.forEach(r => prevIds.current.add(r.id));

    setLatest(newRows);
    setTotalSaved(rows.length > 0 ? rows[0].id : 0);
  }

  useEffect(() => {
    fetchLatest();

    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
      fetch(`${API}/stop`, { method: "POST" }).catch(() => {});
    };
  }, []);

  return (
    <div className="page">
      <div className="page-header">
        <h1>Live Detection</h1>
        <span className="stat-pill">{totalSaved} saved today</span>
      </div>

      <div className="live-layout">
        {/* Camera feed */}
        <div className="camera-card">
          <div className="camera-viewport">

            {/* ✅ ALWAYS mounted */}
            <img
              src={streaming ? `${API}/stream` : ""}
              alt="Live feed"
              className="camera-feed"
              style={{ display: streaming ? "block" : "none" }}
            />

            {/* Placeholder */}
            {!streaming && (
              <div className="camera-placeholder">
                <p>Camera is off</p>
              </div>
            )}

            {/* ✅ SINGLE LIVE indicator */}
            {streaming && (
              <div className="live-indicator">
                <span /> LIVE
              </div>
            )}
          </div>

          <div className="camera-controls">
            {!streaming ? (
              <button className="btn-primary" onClick={startStream}>
                ▶ Start Camera
              </button>
            ) : (
              <button className="btn-danger" onClick={stopStream}>
                ■ Stop Camera
              </button>
            )}

            <p className="camera-hint">
              {streaming
                ? "Detection is running. Plates are auto-saved to the database."
                : "Press Start to begin detecting license plates via webcam."}
            </p>
          </div>
        </div>

        {/* Detections */}
        <div className="card detections-live">
          <div className="card-header">
            <h2>Detected Plates</h2>
            <span className="badge">{latest.length}</span>
          </div>

          {latest.length === 0 ? (
            <p className="empty-msg">
              Plates appear here as they are detected.
            </p>
          ) : (
            <ul className="detection-list">
              {latest.map(r => (
                <li
                  key={r.id}
                  className={`detection-item ${r.isNew ? "new-item" : ""}`}
                >
                  <span className="plate-badge large">{r.plate}</span>

                  <div className="detection-meta">
                    <span className="conf">
                      {(r.confidence * 100).toFixed(0)}% confidence
                    </span>
                    <span className="ts">{r.timestamp}</span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}