import React, { useState, useEffect } from "react";
import { api, encId } from "../lib/api.js";
import { shortId, safeText } from "../lib/format.js";
import { ErrorBanner } from "../components/ErrorBanner.jsx";
import { Loading } from "../components/Loading.jsx";
import { Disclaimer } from "../components/Disclaimer.jsx";

export function TimeTab({ caseId }) {
  const [evidenceList, setEvidenceList] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [actionError, setActionError] = useState(null);

  // Selected evidence for calibration & group editing
  const [selectedEvidenceId, setSelectedEvidenceId] = useState("");
  const [calibrationData, setCalibrationData] = useState(null);
  const [groupLabel, setGroupLabel] = useState("");
  const [groupLoading, setGroupLoading] = useState(false);

  // Calibration form
  const [deviceTime, setDeviceTime] = useState("");
  const [refTime, setRefTime] = useState("");
  const [uncertaintySec, setUncertaintySec] = useState("0");
  const [note, setNote] = useState("");
  const [submittingCal, setSubmittingCal] = useState(false);

  // Calibrated times table
  const [calibratedTimes, setCalibratedTimes] = useState(null);
  const [calibratedLoading, setCalibratedLoading] = useState(false);

  async function loadInitialData() {
    try {
      setLoading(true);
      setError(null);
      const evs = await api.get(`/api/cases/${encId(caseId)}/evidence`);
      setEvidenceList(evs || []);
      if (evs && evs.length > 0) {
        setSelectedEvidenceId(evs[0].evidence_id);
      }
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }

  async function loadCalibratedTimes() {
    try {
      setCalibratedLoading(true);
      const res = await api.get(`/api/cases/${encId(caseId)}/calibrated-times`);
      setCalibratedTimes(res);
    } catch (err) {
      setActionError(err);
    } finally {
      setCalibratedLoading(false);
    }
  }

  useEffect(() => {
    loadInitialData();
    loadCalibratedTimes();
  }, [caseId]);

  async function loadEvidenceDetails(evidenceId) {
    if (!evidenceId) return;
    try {
      setGroupLoading(true);
      setActionError(null);

      // Load calibration history
      const calRes = await api.get(`/api/evidence/${encId(evidenceId)}/calibration`);
      setCalibrationData(calRes);

      // Load group
      const grpRes = await api.get(`/api/evidence/${encId(evidenceId)}/group`);
      setGroupLabel(grpRes?.group_label || "DEFAULT");
    } catch (err) {
      setActionError(err);
    } finally {
      setGroupLoading(false);
    }
  }

  useEffect(() => {
    if (selectedEvidenceId) {
      loadEvidenceDetails(selectedEvidenceId);
    }
  }, [selectedEvidenceId]);

  async function handleSetCalibration(e) {
    e.preventDefault();
    if (!selectedEvidenceId || !deviceTime.trim() || !refTime.trim()) return;

    const unc = parseFloat(uncertaintySec);
    if (isNaN(unc) || unc < 0) {
      setActionError("Uncertainty seconds must be a non-negative number.");
      return;
    }

    try {
      setSubmittingCal(true);
      setActionError(null);
      await api.post(`/api/evidence/${encId(selectedEvidenceId)}/calibration`, {
        device_time: deviceTime.trim(),
        reference_time: refTime.trim(),
        uncertainty_seconds: unc,
        note: note.trim() || undefined,
      });

      // Clear inputs
      setDeviceTime("");
      setRefTime("");
      setUncertaintySec("0");
      setNote("");

      // Refresh data
      await loadEvidenceDetails(selectedEvidenceId);
      await loadCalibratedTimes();
    } catch (err) {
      setActionError(err);
    } finally {
      setSubmittingCal(false);
    }
  }

  async function handleUpdateGroup(e) {
    e.preventDefault();
    if (!selectedEvidenceId || !groupLabel.trim()) return;

    try {
      setGroupLoading(true);
      setActionError(null);
      await api.put(`/api/evidence/${encId(selectedEvidenceId)}/group`, {
        group_label: groupLabel.trim(),
      });
      await loadEvidenceDetails(selectedEvidenceId);
      await loadCalibratedTimes();
    } catch (err) {
      setActionError(err);
    } finally {
      setGroupLoading(false);
    }
  }

  return (
    <div className="tab-content time-tab">
      <div className="tab-header">
        <h2>Time Calibration & Evidence Groups</h2>
        <p className="subtitle">
          Align unsynchronized DVR/NVR device clocks to real-world reference times with explicit uncertainty.
        </p>
      </div>

      <ErrorBanner error={error} onDismiss={() => setError(null)} />
      <ErrorBanner error={actionError} onDismiss={() => setActionError(null)} />

      {loading && !evidenceList.length ? (
        <Loading message="Loading evidence items..." />
      ) : !evidenceList.length ? (
        <div className="empty-state">No evidence records available in this case to calibrate.</div>
      ) : (
        <div className="time-controls-grid">
          <div className="card select-evidence-card">
            <h3>Select Evidence to Configure</h3>
            <div className="form-group">
              <label htmlFor="evidence-select">Evidence Item:</label>
              <select
                id="evidence-select"
                value={selectedEvidenceId}
                onChange={(e) => setSelectedEvidenceId(e.target.value)}
              >
                {evidenceList.map((ev) => (
                  <option key={ev.evidence_id} value={ev.evidence_id}>
                    {ev.original_filename} ({shortId(ev.evidence_id)})
                  </option>
                ))}
              </select>
            </div>

            <hr className="divider" />

            <h3>Evidence Group</h3>
            <form onSubmit={handleUpdateGroup} className="form-standard">
              <div className="form-group">
                <label htmlFor="group-label-input">Group Label (e.g. CAM_EAST, MAIN_ENTRANCE):</label>
                <div className="input-with-button">
                  <input
                    id="group-label-input"
                    type="text"
                    required
                    value={groupLabel}
                    onChange={(e) => setGroupLabel(e.target.value)}
                    disabled={groupLoading}
                  />
                  <button
                    type="submit"
                    className="btn-secondary"
                    disabled={groupLoading || !groupLabel.trim()}
                  >
                    Save Group
                  </button>
                </div>
              </div>
            </form>
          </div>

          <div className="card calibration-form-card">
            <h3>Set Clock Calibration</h3>
            <form onSubmit={handleSetCalibration} className="form-standard">
              <div className="form-group">
                <label htmlFor="cal-device-time">Device Time (Claimed by Video) *</label>
                <input
                  id="cal-device-time"
                  type="text"
                  required
                  placeholder="YYYY-MM-DDTHH:MM:SS"
                  value={deviceTime}
                  onChange={(e) => setDeviceTime(e.target.value)}
                  disabled={submittingCal}
                />
              </div>

              <div className="form-group">
                <label htmlFor="cal-ref-time">Reference Time (True Ground Time) *</label>
                <input
                  id="cal-ref-time"
                  type="text"
                  required
                  placeholder="YYYY-MM-DDTHH:MM:SS"
                  value={refTime}
                  onChange={(e) => setRefTime(e.target.value)}
                  disabled={submittingCal}
                />
              </div>

              <div className="form-group">
                <label htmlFor="cal-unc">Uncertainty Seconds *</label>
                <input
                  id="cal-unc"
                  type="number"
                  step="any"
                  min="0"
                  required
                  value={uncertaintySec}
                  onChange={(e) => setUncertaintySec(e.target.value)}
                  disabled={submittingCal}
                />
              </div>

              <div className="form-group">
                <label htmlFor="cal-note">Note / Calibration Source</label>
                <textarea
                  id="cal-note"
                  rows={2}
                  placeholder="e.g. GPS clock comparison, wristwatch in footage"
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  disabled={submittingCal}
                />
              </div>

              <button
                type="submit"
                className="btn-primary"
                disabled={submittingCal || !deviceTime.trim() || !refTime.trim()}
              >
                {submittingCal ? "Applying..." : "Set Calibration"}
              </button>
            </form>
          </div>
        </div>
      )}

      {calibrationData && (
        <div className="card calibration-history-card">
          <h3>Calibration Reference & History</h3>
          <div className="active-reference-box">
            <h4>Active Reference</h4>
            {calibrationData.active ? (
              <div className="ref-details">
                <div>Reference ID: <code>{shortId(calibrationData.active.reference_id)}</code></div>
                <div>Device Time: <strong>{safeText(calibrationData.active.device_time)}</strong></div>
                <div>Reference Time: <strong>{safeText(calibrationData.active.reference_time)}</strong></div>
                <div>Offset: <strong>{calibrationData.active.offset_seconds} s</strong></div>
                <div>Uncertainty: <strong>&plusmn;{calibrationData.active.uncertainty_seconds} s</strong></div>
                <div>Entered At: {safeText(calibrationData.active.entered_at)} by {safeText(calibrationData.active.entered_by)}</div>
                {calibrationData.active.note && <div>Note: {safeText(calibrationData.active.note)}</div>}
              </div>
            ) : (
              <div className="empty-substate">No active calibration reference set for this evidence.</div>
            )}
          </div>

          {calibrationData.history && calibrationData.history.length > 0 && (
            <div className="history-table-box">
              <h4>Superseded History ({calibrationData.history.length})</h4>
              <div className="table-container">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Ref ID</th>
                      <th>Device Time</th>
                      <th>Reference Time</th>
                      <th>Offset (s)</th>
                      <th>Uncertainty</th>
                      <th>Entered At</th>
                      <th>Superseded At</th>
                      <th>Note</th>
                    </tr>
                  </thead>
                  <tbody>
                    {calibrationData.history.map((h) => (
                      <tr key={h.reference_id}>
                        <td><code>{shortId(h.reference_id)}</code></td>
                        <td>{safeText(h.device_time)}</td>
                        <td>{safeText(h.reference_time)}</td>
                        <td>{h.offset_seconds}</td>
                        <td>&plusmn;{h.uncertainty_seconds}</td>
                        <td>{safeText(h.entered_at)}</td>
                        <td>{safeText(h.superseded_at)}</td>
                        <td>{safeText(h.note)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {calibrationData.disclaimer && (
            <Disclaimer text={calibrationData.disclaimer} title="Calibration Disclaimer" />
          )}
        </div>
      )}

      <div className="card calibrated-times-card">
        <div className="section-header-row">
          <h3>Calibrated Time Ranges</h3>
          <button
            type="button"
            className="btn-secondary"
            onClick={loadCalibratedTimes}
            disabled={calibratedLoading}
          >
            Refresh Times
          </button>
        </div>

        {calibratedLoading ? (
          <Loading message="Calculating calibrated times..." />
        ) : !calibratedTimes?.items?.length ? (
          <div className="empty-state">No calibrated items found for this case.</div>
        ) : (
          <>
            {calibratedTimes.summary && (
              <div className="stats-grid mb-4">
                <div className="stat-card">
                  <span className="stat-label">Total Items:</span>
                  <span className="stat-value">{calibratedTimes.summary.item_count}</span>
                </div>
                <div className="stat-card">
                  <span className="stat-label">Calibrated:</span>
                  <span className="stat-value">
                    {calibratedTimes.summary.by_status?.CALIBRATED || 0}
                  </span>
                </div>
                <div className="stat-card">
                  <span className="stat-label">Not Calibrated:</span>
                  <span className="stat-value">
                    {calibratedTimes.summary.by_status?.NOT_CALIBRATED || 0}
                  </span>
                </div>
                <div className="stat-card">
                  <span className="stat-label">Out of Range:</span>
                  <span className="stat-value">
                    {calibratedTimes.summary.by_status?.OUT_OF_RANGE || 0}
                  </span>
                </div>
              </div>
            )}

            <div className="table-container">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Evidence ID</th>
                    <th>Kind</th>
                    <th>Original Timestamp</th>
                    <th>Correction Status</th>
                    <th>Earliest Bound</th>
                    <th>Nominal Corrected</th>
                    <th>Latest Bound</th>
                    <th>Effective Time</th>
                  </tr>
                </thead>
                <tbody>
                  {calibratedTimes.items.map((item) => (
                    <tr key={item.event_id}>
                      <td><code>{shortId(item.evidence_id)}</code></td>
                      <td>{safeText(item.kind)}</td>
                      <td><code>{safeText(item.original_timestamp)}</code></td>
                      <td>
                        <span className={`status-pill status-${item.correction_status.toLowerCase().replace(/_/g, "-")}`}>
                          {item.correction_status}
                        </span>
                      </td>
                      <td>{item.corrected?.earliest ? <code>{item.corrected.earliest}</code> : "-"}</td>
                      <td>{item.corrected?.nominal ? <code>{item.corrected.nominal}</code> : "-"}</td>
                      <td>{item.corrected?.latest ? <code>{item.corrected.latest}</code> : "-"}</td>
                      <td><code>{safeText(item.effective_timestamp)}</code></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}

        {calibratedTimes?.disclaimer && (
          <Disclaimer text={calibratedTimes.disclaimer} title="Calibrated Times Disclaimer" />
        )}
      </div>
    </div>
  );
}
