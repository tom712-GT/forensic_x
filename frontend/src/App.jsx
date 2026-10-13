import React, { useState, useEffect } from "react";
import { CasesPage } from "./pages/CasesPage.jsx";
import { CasePage } from "./pages/CasePage.jsx";
import { AuditPanel } from "./pages/AuditPanel.jsx";

export function App() {
  const [hash, setHash] = useState(window.location.hash || "#/");
  const [showAuditPanel, setShowAuditPanel] = useState(false);

  useEffect(() => {
    function handleHashChange() {
      setHash(window.location.hash || "#/");
    }
    window.addEventListener("hashchange", handleHashChange);
    return () => window.removeEventListener("hashchange", handleHashChange);
  }, []);

  let content = null;

  if (hash.startsWith("#/case/")) {
    const rawId = hash.slice("#/case/".length);
    let decodedId = "";
    try {
      decodedId = decodeURIComponent(rawId);
    } catch {
      decodedId = "";
    }

    if (!decodedId) {
      content = (
        <div className="page error-page">
          <div className="card not-found-card">
            <h2>Case not found</h2>
            <p className="subtitle">The case ID in the URL is invalid or malformed.</p>
            <div className="mt-4">
              <a href="#/" className="btn-primary">
                &larr; Back to Cases
              </a>
            </div>
          </div>
        </div>
      );
    } else {
      content = <CasePage key={decodedId} caseId={decodedId} />;
    }
  } else {
    content = <CasesPage />;
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-branding">
          <a href="#/" className="brand-logo">
            <span className="logo-icon">&#x1F50E;</span>
            <span className="brand-name">FORENSIC-X</span>
          </a>
          <span className="brand-tagline">Surveillance DVR/NVR Forensic Suite</span>
        </div>

        <nav className="header-nav">
          <a href="#/" className={`nav-link ${!hash.startsWith("#/case/") ? "nav-active" : ""}`}>
            Cases
          </a>
          <button
            type="button"
            className={`btn-audit-toggle ${showAuditPanel ? "active" : ""}`}
            onClick={() => setShowAuditPanel((prev) => !prev)}
          >
            Audit Log & Chain
          </button>
        </nav>
      </header>

      {showAuditPanel && (
        <div className="audit-panel-modal-backdrop">
          <div className="audit-panel-modal">
            <AuditPanel onClose={() => setShowAuditPanel(false)} />
          </div>
        </div>
      )}

      <main className="app-main-content">{content}</main>

      <footer className="app-footer">
        <p>
          FORENSIC-X &bull; Timestamps are claims &bull; A gap is not deletion &bull; Temporal overlap is not identity &bull; A hash proves byte equality not authenticity
        </p>
      </footer>
    </div>
  );
}
