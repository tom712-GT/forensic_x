import React, { useState, useEffect } from "react";
import { api, encId } from "../lib/api.js";
import { shortId, safeText } from "../lib/format.js";
import { ErrorBanner } from "../components/ErrorBanner.jsx";
import { Loading } from "../components/Loading.jsx";

export function CasesPage() {
  const [cases, setCases] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const [caseName, setCaseName] = useState("");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function loadCases() {
    try {
      setLoading(true);
      setError(null);
      const res = await api.get("/api/cases");
      setCases(res || []);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadCases();
  }, []);

  async function handleCreateCase(e) {
    e.preventDefault();
    if (!caseName.trim()) return;

    try {
      setSubmitting(true);
      setError(null);
      const newCase = await api.post("/api/cases", {
        case_name: caseName.trim(),
        description: description.trim() || undefined,
      });
      setCaseName("");
      setDescription("");
      await loadCases();
      if (newCase?.case_id) {
        window.location.hash = `#/case/${encId(newCase.case_id)}`;
      }
    } catch (err) {
      setError(err);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="page cases-page">
      <header className="page-header">
        <h1>Forensic Investigations</h1>
        <p className="subtitle">Digital Video & Surveillance Evidence Management</p>
      </header>

      <ErrorBanner error={error} onDismiss={() => setError(null)} />

      <section className="create-case-section card">
        <h2>Create New Case</h2>
        <form onSubmit={handleCreateCase} className="case-form">
          <div className="form-group">
            <label htmlFor="case-name">Case Name *</label>
            <input
              id="case-name"
              type="text"
              required
              placeholder="e.g. CCTV Ingestion - Branch 104"
              value={caseName}
              onChange={(e) => setCaseName(e.target.value)}
              disabled={submitting}
            />
          </div>
          <div className="form-group">
            <label htmlFor="case-desc">Description (Optional)</label>
            <textarea
              id="case-desc"
              rows={3}
              placeholder="Incident details, location, evidence scope..."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              disabled={submitting}
            />
          </div>
          <button
            type="submit"
            className="btn-primary"
            disabled={submitting || !caseName.trim()}
          >
            {submitting ? "Creating..." : "Create Case"}
          </button>
        </form>
      </section>

      <section className="cases-list-section card">
        <div className="section-header-row">
          <h2>Active Cases</h2>
          <button
            type="button"
            className="btn-secondary"
            onClick={loadCases}
            disabled={loading}
          >
            Refresh
          </button>
        </div>

        {loading && !cases.length ? (
          <Loading message="Loading cases..." />
        ) : !cases.length ? (
          <div className="empty-state">No cases registered yet. Create one above to begin.</div>
        ) : (
          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Case ID</th>
                  <th>Name</th>
                  <th>Description</th>
                  <th>Status</th>
                  <th>Created</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {cases.map((c) => (
                  <tr key={c.case_id}>
                    <td>
                      <code>{shortId(c.case_id)}</code>
                    </td>
                    <td>
                      <a href={`#/case/${encId(c.case_id)}`} className="case-title-link">
                        {safeText(c.case_name)}
                      </a>
                    </td>
                    <td>{safeText(c.description)}</td>
                    <td>
                      <span className="status-badge">{safeText(c.status)}</span>
                    </td>
                    <td>{safeText(c.created_at)}</td>
                    <td>
                      <a
                        href={`#/case/${encId(c.case_id)}`}
                        className="btn-table-action"
                      >
                        Open Case &rarr;
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
