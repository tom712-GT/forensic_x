import React, { useState, useEffect } from "react";
import { api, encId } from "../lib/api.js";
import { shortId, safeText } from "../lib/format.js";
import { ErrorBanner } from "../components/ErrorBanner.jsx";
import { Loading } from "../components/Loading.jsx";
import { Disclaimer } from "../components/Disclaimer.jsx";

export function AuditPanel({ onClose }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [auditRows, setAuditRows] = useState([]);
  const [verification, setVerification] = useState(null);
  const [anchorInput, setAnchorInput] = useState("");
  const [anchorError, setAnchorError] = useState("");

  async function loadAuditLog() {
    try {
      setLoading(true);
      setError(null);
      const rows = await api.get("/api/audit-log?limit=50");
      setAuditRows(rows || []);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadAuditLog();
  }, []);

  async function handleVerify(customAnchor) {
    let anchorParam = "";
    const anc = customAnchor !== undefined ? customAnchor : anchorInput.trim();
    if (anc) {
      if (!/^[0-9a-f]{64}$/.test(anc)) {
        setAnchorError("Anchor must be exactly 64 lowercase hexadecimal characters.");
        return;
      }
      setAnchorError("");
      anchorParam = `?anchor=${encId(anc)}`;
    } else {
      setAnchorError("");
    }

    try {
      setLoading(true);
      setError(null);
      const res = await api.get(`/api/audit-log/verify${anchorParam}`);
      setVerification(res);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="panel audit-panel">
      <div className="panel-header">
        <h2>Audit Hash Chain & Integrity</h2>
        {onClose && (
          <button type="button" className="btn-secondary" onClick={onClose}>
            Close Panel
          </button>
        )}
      </div>

      <ErrorBanner error={error} onDismiss={() => setError(null)} />
      {anchorError && <div className="validation-error">{anchorError}</div>}

      <div className="audit-controls card">
        <div className="audit-actions">
          <button
            type="button"
            className="btn-primary"
            disabled={loading}
            onClick={() => handleVerify()}
          >
            {loading ? "Verifying..." : "Verify chain"}
          </button>
          <button
            type="button"
            className="btn-secondary"
            disabled={loading}
            onClick={loadAuditLog}
          >
            Refresh Log
          </button>
        </div>

        <div className="form-group anchor-group">
          <label htmlFor="audit-anchor-input">External Anchor (64 lowercase hex):</label>
          <div className="input-with-button">
            <input
              id="audit-anchor-input"
              type="text"
              value={anchorInput}
              placeholder="e.g. 5e8ff7... (64 hex characters)"
              onChange={(e) => setAnchorInput(e.target.value)}
              disabled={loading}
            />
            <button
              type="button"
              className="btn-secondary"
              disabled={loading || !anchorInput.trim()}
              onClick={() => handleVerify(anchorInput.trim())}
            >
              Verify with Anchor
            </button>
          </div>
        </div>
      </div>

      {verification && (
        <div className="verification-results card">
          <h3>Verification Status</h3>
          <div className="status-badge-row">
            <span className={`status-badge ${verification.status === "OK" ? "status-ok" : "status-broken"}`}>
              Status: {verification.status}
            </span>
          </div>

          <div className="stats-grid">
            <div className="stat-card">
              <span className="stat-label">Total Rows:</span>
              <span className="stat-value">{verification.total_count}</span>
            </div>
            <div className="stat-card">
              <span className="stat-label">Pre-chain Rows:</span>
              <span className="stat-value">{verification.pre_chain_count}</span>
            </div>
            <div className="stat-card">
              <span className="stat-label">Chained Rows:</span>
              <span className="stat-value">{verification.chained_count}</span>
            </div>
            <div className="stat-card">
              <span className="stat-label">Verified Rows:</span>
              <span className="stat-value">{verification.verified_count}</span>
            </div>
          </div>

          {verification.first_break && (
            <div className="first-break-alert">
              <strong>First Break Detected:</strong> Audit ID {verification.first_break.audit_id} - {verification.first_break.reason}
            </div>
          )}

          {verification.anchor && (
            <div className="anchor-info">
              <div><strong>Latest Chained Anchor:</strong> Audit ID {verification.anchor.audit_id}</div>
              <code className="hash-code">{verification.anchor.row_hash}</code>
            </div>
          )}

          {verification.anchor_check && (
            <div className="anchor-check-results">
              <h4>Anchor Check:</h4>
              <div>
                Matched: <strong>{verification.anchor_check.matched ? "YES" : "NO"}</strong>
              </div>
              {verification.anchor_check.audit_id != null && (
                <div>Matched at Audit ID: {verification.anchor_check.audit_id}</div>
              )}
              {verification.anchor_check.rows_after_anchor != null && (
                <div>Rows after anchor: {verification.anchor_check.rows_after_anchor}</div>
              )}
            </div>
          )}

          <Disclaimer text={verification.disclaimer} title="Audit Integrity Disclaimer" />
        </div>
      )}

      <div className="audit-table-section card">
        <h3>Recent Audit Log Entries</h3>
        {loading && !auditRows.length ? (
          <Loading message="Loading audit log entries..." />
        ) : !auditRows.length ? (
          <div className="empty-state">No audit log entries recorded.</div>
        ) : (
          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Timestamp</th>
                  <th>Action</th>
                  <th>Outcome</th>
                  <th>HTTP</th>
                  <th>Actor</th>
                  <th>Case ID</th>
                  <th>Evidence ID</th>
                  <th>Details</th>
                </tr>
              </thead>
              <tbody>
                {auditRows.map((row) => (
                  <tr key={row.audit_id}>
                    <td>{row.audit_id}</td>
                    <td>{safeText(row.timestamp)}</td>
                    <td>{safeText(row.action)}</td>
                    <td>
                      <span className={`outcome-pill outcome-${String(row.outcome).toLowerCase()}`}>
                        {safeText(row.outcome)}
                      </span>
                    </td>
                    <td>{row.http_status}</td>
                    <td>{safeText(row.actor)}</td>
                    <td>{shortId(row.case_id)}</td>
                    <td>{shortId(row.evidence_id)}</td>
                    <td className="details-col">{safeText(row.details)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
