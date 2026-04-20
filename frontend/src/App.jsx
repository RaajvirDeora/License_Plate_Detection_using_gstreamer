import { useState } from "react";
import LiveDetection from "./pages/LiveDetection";
import History from "./pages/History";
import Dashboard from "./pages/Dashboard";
import Navbar from "./components/Navbar";
import "./index.css";

export default function App() {
  const [page, setPage] = useState("dashboard");

  return (
    <div className="app-root">
      <Navbar page={page} setPage={setPage} />
      <main className="main-content">
        {page === "dashboard"  && <Dashboard setPage={setPage} />}
        {page === "live"       && <LiveDetection />}
        {page === "history"    && <History />}
      </main>
    </div>
  );
}
