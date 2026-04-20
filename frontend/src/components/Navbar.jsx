export default function Navbar({ page, setPage }) {
  const links = [
    { id: "dashboard", label: "Dashboard" },
    { id: "live",      label: "Live Detection" },
    { id: "history",   label: "History" },
  ];

  return (
    <nav className="navbar">
      <div className="navbar-brand">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <rect x="2" y="7" width="20" height="10" rx="2"/>
          <circle cx="6"  cy="12" r="1.5" fill="currentColor" stroke="none"/>
          <circle cx="18" cy="12" r="1.5" fill="currentColor" stroke="none"/>
          <path d="M8 9h8M8 15h8" strokeWidth="1"/>
        </svg>
        <span>PlateWatch</span>
      </div>
      <div className="navbar-links">
        {links.map(l => (
          <button
            key={l.id}
            className={`nav-btn ${page === l.id ? "active" : ""}`}
            onClick={() => setPage(l.id)}
          >
            {l.label}
          </button>
        ))}
      </div>
    </nav>
  );
}
