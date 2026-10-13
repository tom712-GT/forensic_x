import React, { useState, useEffect } from "react";
import { api, encId } from "../lib/api.js";
import { shortId, safeText } from "../lib/format.js";
import { ErrorBanner } from "../components/ErrorBanner.jsx";
import { Loading } from "../components/Loading.jsx";
import { Disclaimer } from "../components/Disclaimer.jsx";

const KINDS = [
  "EVIDENCE_REGISTERED",
  "EVIDENCE_INGESTED",
  "EVIDENCE_HASHED",
  "FORMAT_DETECTED",
  "VENDOR_DETECTED",
  "ACQUISITION_DECLARED",
  "METADATA_EXTRACTED",
  "CONTAINER_CREATION_TIME",
  "CONTAINER_MODIFICATION_TIME",
  "ARTIFACT_RECOVERED",
];

const TIME_SOURCES = ["TOOL_CLOCK", "USER_DECLARED", "CONTAINER_CLAIM"];

export function TimelineTab({ caseId }) {
  const [timeline, setTimeline] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Filters
  const [selectedKind, setSelectedKind] = useState("");
  const [selectedSource, setSelectedSource] = useState("");
  const [filterEvidenceId, setFilterEvidenceId] = useState("");
  const [startTime, setStartTime] = useState("");
  const [endTime, setEndTime] = useState("");

  // Paging
  const [limit, setLimit] = useState(50);
  const [offset, setOffset] = useState(0);

  async function loadTimeline(newOffset = offset) {
    try {
      setLoading(true);
      setError(null);

      const params = new URLSearchParams();
      params.set("limit", String(limit));
      params.set("offset", String(newOffset));

      if (selectedKind) params.set("kind", selectedKind);
      if (selectedSource) params.set("time_source", selectedSource);
      if (filterEvidenceId.trim()) params.set("evidence_id", filterEvidenceId.trim());
      if (startTime.trim()) params.set("start", startTime.trim());
      if (endTime.trim()) params.set("end", endTime.trim());

      const res = await api.get(`/api/cases/${encId(caseId)}/timeline?${params.toString()}`);
      setTimeline(res);
      setOffset(newOffset);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadTimeline(0);
  }, [caseId]);

  function handleFilterSubmit(e) {
    e.preventDefault();
    loadTimeline(0);
  }

  function handleResetFilters() {
    setSelectedKind("");
    setSelectedSource("");
    setFilterEvidenceId("");
    setStartTime("");
    setEndTime("");
  }

  const events = timeline?.events || [];
  const undated = timeline?.undated || [];
  const summary = timeline?.summary;
  const page = timeline?.page;

  return (
    <div className="tab-content timeline-tab">
      <div className="tab-header">
        <h2>Chronological Timeline</h2>
        <p className="subtitle">
          Unified provenance timeline across physical file lifecycle and container metadata claims.
        </p>
      </div>

      <ErrorBanner error={error} onDismiss={() => setError(null)} />

      <div className="card filters-card">
        <h3>Timeline Filters</h3>
        <form onSubmit={handleFilterSubmit} className="filters-grid">
          <div className="form-group">
            <label htmlFor="filter-kind">Event Kind</label>
            <select
              id="filter-kind"
              value={selectedKind}
              onChange={(e) => setSelectedKind(e.target.value)}
              disabled={loading}
            >
              <option value="">All Kinds</option>
              {KINDS.map((k) => (
                <option key={k} value={k}>
                  {k}
                </option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label htmlFor="filter-source">Time Source</label>
            <select
              id="filter-source"
              value={selectedSource}
              onChange={(e) => setSelectedSource(e.target.value)}
              disabled={loading}
            >
              <option value="">All Sources</option>
              {TIME_SOURCES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label htmlFor="filter-evidence">Evidence ID</label>
            <input
              id="filter-evidence"
              type="text"
              placeholder="e.g. 8e4f..."
              value={filterEvidenceId}
              onChange={(e) => setFilterEvidenceId(e.target.value)}
              disabled={loading}
            />
          </div>

          <div className="form-group">
            <label htmlFor="filter-start">Start Time</label>
            <input
              id="filter-start"
              type="text"
              placeholder="YYYY-MM-DDTHH:MM:SS"
              value={startTime}
              onChange={(e) => setStartTime(e.target.value)}
              disabled={loading}
            />
          </div>

          <div className="form-group">
            <label htmlFor="filter-end">End Time</label>
            <input
              id="filter-end"
              type="text"
              placeholder="YYYY-MM-DDTHH:MM:SS"
              value={endTime}
              onChange={(e) => setEndTime(e.target.value)}
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
              onClick={handleResetFilters}
              disabled={loading}
            >
              Reset
            </button>
          </div>
        </form>
      </div>

      {summary && (
        <div className="card summary-card">
          <h3>Timeline Summary</h3>
          {summary.truncated && (
            <div className="truncated-notice alert-notice" role="alert">
              <strong>Notice:</strong> Results have been truncated due to maximum capacity limits.
            </div>
          )}

          <div className="stats-grid">
            <div className="stat-card">
              <span className="stat-label">Dated Events:</span>
              <span className="stat-value">{summary.event_count}</span>
            </div>
            <div className="stat-card">
              <span className="stat-label">Undated Items:</span>
              <span className="stat-value">{summary.undated_count}</span>
            </div>
            <div className="stat-card">
              <span className="stat-label">Earliest Claim:</span>
              <span className="stat-value">{safeText(summary.earliest)}</span>
            </div>
            <div className="stat-card">
              <span className="stat-label">Latest Claim:</span>
              <span className="stat-value">{safeText(summary.latest)}</span>
            </div>
          </div>
        </div>
      )}

      <div className="card table-card">
        <div className="section-header-row">
          <h3>Dated Events</h3>
          <span className="page-indicator">
            {page ? `Showing offset ${page.offset} of ${page.total}` : ""}
          </span>
        </div>

        {loading ? (
          <Loading message="Loading timeline..." />
        ) : !events.length ? (
          <div className="empty-state">No matching timeline events found.</div>
        ) : (
          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Kind</th>
                  <th>Time Source</th>
                  <th>Flags</th>
                  <th>Evidence ID</th>
                  <th>Origin / Detail</th>
                </tr>
              </thead>
              <tbody>
                {events.map((ev) => (
                  <tr key={ev.event_id}>
                    <td>
                      <code>{safeText(ev.timestamp)}</code>
                    </td>
                    <td>
                      <span className="kind-badge">{safeText(ev.kind)}</span>
                    </td>
                    <td>
                      <span className="source-tag">{safeText(ev.time_source)}</span>
                    </td>
                    <td>
                      {ev.flags && ev.flags.length > 0
                        ? ev.flags.map((f, i) => (
                            <span key={i} className="flag-tag">
                              {f}
                            </span>
                          ))
                        : "-"}
                    </td>
                    <td>
                      <code>{shortId(ev.evidence_id)}</code>
                    </td>
                    <td>
                      {ev.source?.table ? (
                        <small>
                          {ev.source.table}.{ev.source.field}
                        </small>
                      ) : (
                        safeText(ev.raw_value)
                      )}
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
              onClick={() => loadTimeline(Math.max(0, offset - limit))}
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
              onClick={() => loadTimeline(offset + limit)}
            >
              Next Page &rarr;
            </button>
          </div>
        )}
      </div>

      {undated.length > 0 && (
        <div className="card undated-card">
          <h3>Undated Items ({undated.length})</h3>
          <p className="subtitle">
            Records with absent, zeroed, or unparseable timestamps preserved for provenance.
          </p>
          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Kind</th>
                  <th>Time Source</th>
                  <th>Evidence ID</th>
                  <th>Reason</th>
                  <th>Raw Value</th>
                </tr>
              </thead>
              <tbody>
                {undated.map((u, i) => (
                  <tr key={u.event_id || i}>
                    <td>{safeText(u.kind)}</td>
                    <td>{safeText(u.time_source)}</td>
                    <td><code>{shortId(u.evidence_id)}</code></td>
                    <td><span className="reason-tag">{safeText(u.reason)}</span></td>
                    <td>{safeText(u.raw_value)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {timeline?.disclaimer && (
        <Disclaimer text={timeline.disclaimer} title="Timeline Disclaimer" />
      )}
    </div>
  );
}
