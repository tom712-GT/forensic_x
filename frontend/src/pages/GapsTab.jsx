import React, { useState, useEffect } from "react";
import { api, encId } from "../lib/api.js";
import { shortId, formatSeconds, safeText } from "../lib/format.js";
import { ErrorBanner } from "../components/ErrorBanner.jsx";
import { Loading } from "../components/Loading.jsx";
import { Disclaimer } from "../components/Disclaimer.jsx";

export function GapsTab({ caseId }) {
  const [gapsData, setGapsData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Filters
  const [groupFilter, setGroupFilter] = useState("");
  const [minGapSeconds, setMinGapSeconds] = useState("0");

  // Paging
  const [limit, setLimit] = useState(50);
  const [offset, setOffset] = useState(0);

  async function loadGaps(newOffset = offset) {
    try {
      setLoading(true);
      setError(null);

      const params = new URLSearchParams();
      params.set("limit", String(limit));
      params.set("offset", String(newOffset));

      if (groupFilter.trim()) params.set("group", groupFilter.trim());
      const minSec = parseFloat(minGapSeconds);
      if (!isNaN(minSec) && minSec >= 0) {
        params.set("min_gap_seconds", String(minSec));
      }

      const res = await api.get(`/api/cases/${encId(caseId)}/gaps?${params.toString()}`);
      setGapsData(res);
      setOffset(newOffset);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadGaps(0);
  }, [caseId]);

  function handleFilterSubmit(e) {
    e.preventDefault();
    loadGaps(0);
  }

  const gaps = gapsData?.gaps || [];
  const groups = gapsData?.groups || [];
  const unknownLength = gapsData?.unknown_length || [];
  const unplaced = gapsData?.unplaced || [];
  const summary = gapsData?.summary;
  const page = gapsData?.page;

  return (
    <div className="tab-content gaps-tab">
      <div className="tab-header">
        <h2>Coverage Gap Analysis</h2>
        <div className="alert-box forensic-principle" role="note">
          <strong>Key Forensic Principle:</strong> A gap is not proof of deletion.
        </div>
      </div>

      <ErrorBanner error={error} onDismiss={() => setError(null)} />

      <div className="card filters-card">
        <h3>Filter Gaps</h3>
        <form onSubmit={handleFilterSubmit} className="filters-grid">
          <div className="form-group">
            <label htmlFor="gap-group-filter">Group Label</label>
            <input
              id="gap-group-filter"
              type="text"
              placeholder="e.g. CAM_EAST"
              value={groupFilter}
              onChange={(e) => setGroupFilter(e.target.value)}
              disabled={loading}
            />
          </div>

          <div className="form-group">
            <label htmlFor="gap-min-seconds">Min Gap Seconds</label>
            <input
              id="gap-min-seconds"
              type="number"
              min="0"
              step="any"
              value={minGapSeconds}
              onChange={(e) => setMinGapSeconds(e.target.value)}
              disabled={loading}
            />
          </div>

          <div className="filter-actions-row">
            <button type="submit" className="btn-primary" disabled={loading}>
              Apply Filters
            </button>
            <button
              type="button"
              className="btn-secondary"
              onClick={() => {
                setGroupFilter("");
                setMinGapSeconds("0");
              }}
              disabled={loading}
            >
              Reset
            </button>
          </div>
        </form>
      </div>

      {groups.length > 0 && (
        <div className="card groups-summary-card">
          <h3>Evidence Groups Coverage</h3>
          <div className="groups-badge-list">
            {groups.map((g) => (
              <div key={g.group_label} className="group-badge-card">
                <strong>{safeText(g.group_label)}</strong>
                <div className="group-badge-meta">
                  <span>Intervals: {g.interval_count}</span>
                  <span>Gaps: {g.gap_count}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {summary && (
        <div className="card summary-card">
          <h3>Gaps Summary</h3>
          {summary.truncated && (
            <div className="truncated-notice alert-notice" role="alert">
              <strong>Notice:</strong> Results were truncated due to system limits.
            </div>
          )}

          <div className="stats-grid">
            <div className="stat-card">
              <span className="stat-label">Total Gaps:</span>
              <span className="stat-value">{summary.gap_count}</span>
            </div>
            <div className="stat-card">
              <span className="stat-label">Total Gap Duration:</span>
              <span className="stat-value">{formatSeconds(summary.total_gap_seconds)}</span>
            </div>
            <div className="stat-card">
              <span className="stat-label">Longest Gap:</span>
              <span className="stat-value">{formatSeconds(summary.longest_gap_seconds)}</span>
            </div>
          </div>
        </div>
      )}

      <div className="card table-card">
        <div className="section-header-row">
          <h3>Detected Temporal Gaps</h3>
          <span className="page-indicator">
            {page ? `Offset ${page.offset} of ${page.total}` : ""}
          </span>
        </div>

        {loading ? (
          <Loading message="Analyzing coverage gaps..." />
        ) : !gaps.length ? (
          <div className="empty-state">No temporal gaps detected matching current criteria.</div>
        ) : (
          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Group</th>
                  <th>Start</th>
                  <th>End</th>
                  <th>Nominal Length</th>
                  <th>Min Length</th>
                  <th>Max Length</th>
                  <th>Certainty</th>
                  <th>Before Ev ID</th>
                  <th>After Ev ID</th>
                </tr>
              </thead>
              <tbody>
                {gaps.map((gap) => (
                  <tr key={gap.gap_id}>
                    <td><strong>{safeText(gap.group_label)}</strong></td>
                    <td><code>{safeText(gap.start)}</code></td>
                    <td><code>{safeText(gap.end)}</code></td>
                    <td>{formatSeconds(gap.length_seconds)}</td>
                    <td>{formatSeconds(gap.length_min_seconds)}</td>
                    <td>{formatSeconds(gap.length_max_seconds)}</td>
                    <td>
                      <span className={`certainty-badge certainty-${String(gap.certainty).toLowerCase()}`}>
                        {safeText(gap.certainty)}
                      </span>
                    </td>
                    <td><code>{shortId(gap.before_evidence_id)}</code></td>
                    <td><code>{shortId(gap.after_evidence_id)}</code></td>
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
              onClick={() => loadGaps(Math.max(0, offset - limit))}
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
              onClick={() => loadGaps(offset + limit)}
            >
              Next Page &rarr;
            </button>
          </div>
        )}
      </div>

      {unknownLength.length > 0 && (
        <div className="card unknown-length-card">
          <h3>Unknown Length Items ({unknownLength.length})</h3>
          <p className="subtitle">
            Evidence segments with a known start point but unverified or missing duration.
          </p>
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
          <h3>Unplaced Evidence ({unplaced.length})</h3>
          <p className="subtitle">
            Evidence files that could not be assigned to a timeline or group.
          </p>
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

      {gapsData?.disclaimer && (
        <Disclaimer text={gapsData.disclaimer} title="Gap Analysis Disclaimer" />
      )}
    </div>
  );
}
