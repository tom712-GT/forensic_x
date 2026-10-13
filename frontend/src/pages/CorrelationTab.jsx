import React, { useState, useEffect } from "react";
import { api, encId } from "../lib/api.js";
import { shortId, formatSeconds, safeText } from "../lib/format.js";
import { ErrorBanner } from "../components/ErrorBanner.jsx";
import { Loading } from "../components/Loading.jsx";
import { Disclaimer } from "../components/Disclaimer.jsx";

export function CorrelationTab({ caseId }) {
  const [corrData, setCorrData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Filters
  const [groupsInput, setGroupsInput] = useState("");
  const [minOverlapSec, setMinOverlapSec] = useState("0");
  const [minGroups, setMinGroups] = useState("2");

  // Paging
  const [limit, setLimit] = useState(50);
  const [offset, setOffset] = useState(0);

  async function loadCorrelation(newOffset = offset) {
    try {
      setLoading(true);
      setError(null);

      const params = new URLSearchParams();
      params.set("limit", String(limit));
      params.set("offset", String(newOffset));

      if (groupsInput.trim()) params.set("groups", groupsInput.trim());
      const minOv = parseFloat(minOverlapSec);
      if (!isNaN(minOv) && minOv >= 0) {
        params.set("min_overlap_seconds", String(minOv));
      }
      const mg = parseInt(minGroups, 10);
      if (!isNaN(mg) && mg >= 2) {
        params.set("min_groups", String(mg));
      }

      const res = await api.get(`/api/cases/${encId(caseId)}/correlation?${params.toString()}`);
      setCorrData(res);
      setOffset(newOffset);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadCorrelation(0);
  }, [caseId]);

  function handleFilterSubmit(e) {
    e.preventDefault();
    loadCorrelation(0);
  }

  const windows = corrData?.windows || [];
  const groups = corrData?.groups || [];
  const unknownLength = corrData?.unknown_length || [];
  const unplaced = corrData?.unplaced || [];
  const summary = corrData?.summary;
  const page = corrData?.page;

  return (
    <div className="tab-content correlation-tab">
      <div className="tab-header">
        <h2>Cross-Camera Temporal Correlation</h2>
        <div className="alert-box forensic-principle" role="note">
          <strong>Key Forensic Principle:</strong> Temporal overlap is not proof of the same event or person.
        </div>
      </div>

      <ErrorBanner error={error} onDismiss={() => setError(null)} />

      <div className="card filters-card">
        <h3>Correlation Parameters</h3>
        <form onSubmit={handleFilterSubmit} className="filters-grid">
          <div className="form-group">
            <label htmlFor="corr-groups">Groups (comma separated)</label>
            <input
              id="corr-groups"
              type="text"
              placeholder="e.g. CAM_01, CAM_02"
              value={groupsInput}
              onChange={(e) => setGroupsInput(e.target.value)}
              disabled={loading}
            />
          </div>

          <div className="form-group">
            <label htmlFor="corr-min-overlap">Min Overlap Seconds</label>
            <input
              id="corr-min-overlap"
              type="number"
              min="0"
              step="any"
              value={minOverlapSec}
              onChange={(e) => setMinOverlapSec(e.target.value)}
              disabled={loading}
            />
          </div>

          <div className="form-group">
            <label htmlFor="corr-min-groups">Min Simultaneous Groups</label>
            <input
              id="corr-min-groups"
              type="number"
              min="2"
              max="50"
              value={minGroups}
              onChange={(e) => setMinGroups(e.target.value)}
              disabled={loading}
            />
          </div>

          <div className="filter-actions-row">
            <button type="submit" className="btn-primary" disabled={loading}>
              Run Correlation
            </button>
            <button
              type="button"
              className="btn-secondary"
              onClick={() => {
                setGroupsInput("");
                setMinOverlapSec("0");
                setMinGroups("2");
              }}
              disabled={loading}
            >
              Reset
            </button>
          </div>
        </form>
      </div>

      {groups.length > 0 && (
        <div className="card groups-card">
          <h3>Analyzed Groups</h3>
          <div className="groups-badge-list">
            {groups.map((g) => (
              <div key={g.group_label} className="group-badge-card">
                <strong>{safeText(g.group_label)}</strong>
                <div className="group-badge-meta">Intervals: {g.interval_count}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {summary && (
        <div className="card summary-card">
          <h3>Correlation Summary</h3>
          {summary.truncated && (
            <div className="truncated-notice alert-notice" role="alert">
              <strong>Notice:</strong> Results were truncated due to system window limits.
            </div>
          )}

          <div className="stats-grid">
            <div className="stat-card">
              <span className="stat-label">Overlap Windows:</span>
              <span className="stat-value">{summary.window_count}</span>
            </div>
            <div className="stat-card">
              <span className="stat-label">Total Overlap:</span>
              <span className="stat-value">{formatSeconds(summary.total_overlap_seconds)}</span>
            </div>
            <div className="stat-card">
              <span className="stat-label">Longest Overlap:</span>
              <span className="stat-value">{formatSeconds(summary.longest_overlap_seconds)}</span>
            </div>
            <div className="stat-card">
              <span className="stat-label">Max Simultaneous Groups:</span>
              <span className="stat-value">{summary.max_simultaneous_groups}</span>
            </div>
          </div>
        </div>
      )}

      <div className="card table-card">
        <div className="section-header-row">
          <h3>Simultaneous Overlap Windows</h3>
          <span className="page-indicator">
            {page ? `Offset ${page.offset} of ${page.total}` : ""}
          </span>
        </div>

        {loading ? (
          <Loading message="Computing cross-camera overlap windows..." />
        ) : !windows.length ? (
          <div className="empty-state">No concurrent overlap windows found for given parameters.</div>
        ) : (
          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Window Start</th>
                  <th>Window End</th>
                  <th>Overlap Length</th>
                  <th>Group Count</th>
                  <th>Groups Involved</th>
                  <th>Uncertain?</th>
                  <th>Evidence Members</th>
                </tr>
              </thead>
              <tbody>
                {windows.map((w) => (
                  <tr key={w.window_id}>
                    <td><code>{safeText(w.start)}</code></td>
                    <td><code>{safeText(w.end)}</code></td>
                    <td>{formatSeconds(w.length_seconds)}</td>
                    <td><strong>{w.group_count}</strong></td>
                    <td>
                      {w.groups?.map((grp, i) => (
                        <span key={i} className="group-pill">
                          {grp}
                        </span>
                      ))}
                    </td>
                    <td>
                      <span className={`uncertain-badge ${w.uncertain ? "uncertain-yes" : "uncertain-no"}`}>
                        {w.uncertain ? "UNCERTAIN" : "EXACT"}
                      </span>
                    </td>
                    <td>
                      {w.members?.map((m, i) => (
                        <div key={i} className="member-line">
                          <strong>{m.group_label}:</strong>{" "}
                          {m.evidence_ids?.map((eid) => shortId(eid)).join(", ")}
                        </div>
                      ))}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {page && page.total > limit && (
          <div className="pagination-controls">
            <button
              type="button"
              className="btn-secondary"
              disabled={loading || offset <= 0}
              onClick={() => loadCorrelation(Math.max(0, offset - limit))}
            >
              &larr; Previous Page
            </button>
            <span className="page-range">
              Offset {offset} &ndash; {Math.min(offset + limit, page.total)} of {page.total}
            </span>
            <button
              type="button"
              className="btn-secondary"
              disabled={loading || offset + limit >= page.total}
              onClick={() => loadCorrelation(offset + limit)}
            >
              Next Page &rarr;
            </button>
          </div>
        )}
      </div>

      {unknownLength.length > 0 && (
        <div className="card unknown-length-card">
          <h3>Unknown Length Items ({unknownLength.length})</h3>
          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Evidence ID</th>
                  <th>Group</th>
                  <th>Start</th>
                  <th>Reason</th>
                </tr>
              </thead>
              <tbody>
                {unknownLength.map((u, i) => (
                  <tr key={u.evidence_id || i}>
                    <td><code>{shortId(u.evidence_id)}</code></td>
                    <td>{safeText(u.group_label)}</td>
                    <td><code>{safeText(u.start)}</code></td>
                    <td>{safeText(u.reason)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {unplaced.length > 0 && (
        <div className="card unplaced-card">
          <h3>Unplaced Items ({unplaced.length})</h3>
          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Evidence ID</th>
                  <th>Group</th>
                  <th>Reason</th>
                </tr>
              </thead>
              <tbody>
                {unplaced.map((u, i) => (
                  <tr key={u.evidence_id || i}>
                    <td><code>{shortId(u.evidence_id)}</code></td>
                    <td>{safeText(u.group_label)}</td>
                    <td>{safeText(u.reason)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {corrData?.disclaimer && (
        <Disclaimer text={corrData.disclaimer} title="Correlation Disclaimer" />
      )}
    </div>
  );
}
