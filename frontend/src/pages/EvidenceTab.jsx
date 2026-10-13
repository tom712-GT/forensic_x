import React, { useState, useEffect } from "react";
import { api, encId } from "../lib/api.js";
import { shortId, formatBytes, safeText } from "../lib/format.js";
import { ErrorBanner } from "../components/ErrorBanner.jsx";
import { Loading } from "../components/Loading.jsx";

const MAX_UPLOAD_BYTES = 100 * 1024 * 1024; // 100 MB

export function EvidenceTab({ caseId }) {
  const [evidenceList, setEvidenceList] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [actionError, setActionError] = useState(null);
  const [actionRunning, setActionRunning] = useState(false);

  // Registration form state
  const [filename, setFilename] = useState("");
  const [evidenceType, setEvidenceType] = useState("DVR_FORENSIC_IMAGE");
  const [declaredSize, setDeclaredSize] = useState("");
  const [registering, setRegistering] = useState(false);

  // Shortcut file picker
  const [shortcutFile, setShortcutFile] = useState(null);

  // Verification results map: evidence_id -> { match, baseline, computed, verified_at }
  const [verifyResults, setVerifyResults] = useState({});

  // Metadata modal/viewer state
  const [selectedMeta, setSelectedMeta] = useState(null);
  const [loadingMetaId, setLoadingMetaId] = useState(null);

  async function loadEvidence() {
    try {
      setLoading(true);
      setError(null);
      const res = await api.get(`/api/cases/${encId(caseId)}/evidence`);
      setEvidenceList(res || []);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadEvidence();
  }, [caseId]);

  async function handleRegister(e) {
    e.preventDefault();
    const sizeNum = parseInt(declaredSize, 10);
    if (!filename.trim() || isNaN(sizeNum) || sizeNum < 0) {
      setActionError("Please provide a valid filename and non-negative declared size.");
      return;
    }

    try {
      setRegistering(true);
      setActionError(null);
      await api.post(`/api/cases/${encId(caseId)}/evidence`, {
        original_filename: filename.trim(),
        evidence_type: evidenceType.trim(),
        file_size: sizeNum,
      });
      setFilename("");
      setDeclaredSize("");
      await loadEvidence();
    } catch (err) {
      setActionError(err);
    } finally {
      setRegistering(false);
    }
  }

  async function handleRegisterAndUpload(e) {
    e.preventDefault();
    if (!shortcutFile) {
      setActionError("Please choose a file to register and upload.");
      return;
    }
    if (shortcutFile.size > MAX_UPLOAD_BYTES) {
      setActionError(`File exceeds maximum allowed upload size of 100 MB (${formatBytes(shortcutFile.size)}).`);
      return;
    }

    try {
      setRegistering(true);
      setActionError(null);
      // Register
      const newEv = await api.post(`/api/cases/${encId(caseId)}/evidence`, {
        original_filename: shortcutFile.name,
        evidence_type: evidenceType.trim() || "DVR_FORENSIC_IMAGE",
        file_size: shortcutFile.size,
      });
      // Upload immediately
      if (newEv?.evidence_id) {
        await api.upload(`/api/evidence/${encId(newEv.evidence_id)}/file`, shortcutFile, shortcutFile.name);
      }
      setShortcutFile(null);
      await loadEvidence();
    } catch (err) {
      setActionError(err);
    } finally {
      setRegistering(false);
    }
  }

  async function handleUpload(evidenceId, file) {
    if (!file) return;
    if (file.size > MAX_UPLOAD_BYTES) {
      setActionError(`File exceeds maximum allowed upload size of 100 MB (${formatBytes(file.size)}).`);
      return;
    }

    try {
      setActionRunning(true);
      setActionError(null);
      await api.upload(`/api/evidence/${encId(evidenceId)}/file`, file, file.name);
      await loadEvidence();
    } catch (err) {
      setActionError(err);
    } finally {
      setActionRunning(false);
    }
  }

  async function handleAction(endpoint, evidenceId) {
    try {
      setActionRunning(true);
      setActionError(null);
      const res = await api.post(`/api/evidence/${encId(evidenceId)}/${endpoint}`, {});
      if (endpoint === "verify") {
        setVerifyResults((prev) => ({
          ...prev,
          [evidenceId]: res,
        }));
      }
      await loadEvidence();
      return res;
    } catch (err) {
      setActionError(err);
    } finally {
      setActionRunning(false);
    }
  }

  async function handleViewMetadata(evidenceId) {
    try {
      setLoadingMetaId(evidenceId);
      setActionError(null);
      const res = await api.get(`/api/evidence/${encId(evidenceId)}/metadata`);
      setSelectedMeta(res);
    } catch (err) {
      setActionError(err);
    } finally {
      setLoadingMetaId(null);
    }
  }

  return (
    <div className="tab-content evidence-tab">
      <div className="tab-header">
        <h2>Evidence Management</h2>
        <div className="vendor-indicator-note note-box">
          <strong>Note:</strong> Vendor detection is an indicator, not proof.
        </div>
      </div>

      <ErrorBanner error={error} onDismiss={() => setError(null)} />
      <ErrorBanner error={actionError} onDismiss={() => setActionError(null)} />

      <div className="evidence-forms-grid">
        <div className="card register-card">
          <h3>Register Evidence Metadata</h3>
          <form onSubmit={handleRegister} className="form-standard">
            <div className="form-group">
              <label htmlFor="reg-filename">Original Filename *</label>
              <input
                id="reg-filename"
                type="text"
                required
                value={filename}
                placeholder="e.g. cam01_20261012.h264"
                onChange={(e) => setFilename(e.target.value)}
                disabled={registering}
              />
            </div>
            <div className="form-group">
              <label htmlFor="reg-type">Evidence Type *</label>
              <input
                id="reg-type"
                type="text"
                required
                value={evidenceType}
                placeholder="DVR_FORENSIC_IMAGE"
                onChange={(e) => setEvidenceType(e.target.value)}
                disabled={registering}
              />
            </div>
            <div className="form-group">
              <label htmlFor="reg-size">Declared File Size (bytes) *</label>
              <input
                id="reg-size"
                type="number"
                min="0"
                required
                value={declaredSize}
                placeholder="1048576"
                onChange={(e) => setDeclaredSize(e.target.value)}
                disabled={registering}
              />
            </div>
            <button
              type="submit"
              className="btn-primary"
              disabled={registering || !filename.trim() || declaredSize === ""}
            >
              {registering ? "Registering..." : "Register Metadata"}
            </button>
          </form>
        </div>

        <div className="card shortcut-card">
          <h3>Shortcut: Register & Upload</h3>
          <p className="shortcut-desc">
            Select a raw video or image file. The system will declare the size from the file and upload immediately.
          </p>
          <form onSubmit={handleRegisterAndUpload} className="form-standard">
            <div className="form-group">
              <label htmlFor="shortcut-file">Choose File (Max 100 MB) *</label>
              <input
                id="shortcut-file"
                type="file"
                required
                onChange={(e) => setShortcutFile(e.target.files?.[0] || null)}
                disabled={registering}
              />
            </div>
            {shortcutFile && (
              <div className="file-info-preview">
                Selected: <strong>{shortcutFile.name}</strong> ({formatBytes(shortcutFile.size)})
              </div>
            )}
            <button
              type="submit"
              className="btn-secondary"
              disabled={registering || !shortcutFile}
            >
              {registering ? "Uploading..." : "Register & Upload Now"}
            </button>
          </form>
        </div>
      </div>

      <div className="card table-card">
        <div className="section-header-row">
          <h3>Registered Evidence Items</h3>
          <button
            type="button"
            className="btn-secondary"
            onClick={loadEvidence}
            disabled={loading || actionRunning}
          >
            Refresh List
          </button>
        </div>

        {loading && !evidenceList.length ? (
          <Loading message="Loading evidence..." />
        ) : !evidenceList.length ? (
          <div className="empty-state">No evidence records found for this case. Register one above.</div>
        ) : (
          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Original Filename</th>
                  <th>Type</th>
                  <th>Declared Size</th>
                  <th>Stored Size</th>
                  <th>Status</th>
                  <th>SHA-256</th>
                  <th>Format</th>
                  <th>Vendor</th>
                  <th>Integrity</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {evidenceList.map((ev) => {
                  const vRes = verifyResults[ev.evidence_id];
                  const formatStr = ev.format_detection?.detected_format || "-";
                  const vendorStr = ev.vendor_detection?.vendor || "-";

                  return (
                    <tr key={ev.evidence_id}>
                      <td>
                        <strong>{safeText(ev.original_filename)}</strong>
                        <div className="id-subtext">ID: {shortId(ev.evidence_id)}</div>
                      </td>
                      <td>{safeText(ev.evidence_type)}</td>
                      <td>{formatBytes(ev.file_size)}</td>
                      <td>{ev.stored_size != null ? formatBytes(ev.stored_size) : "-"}</td>
                      <td>
                        <span className={`status-pill status-${String(ev.status).toLowerCase()}`}>
                          {safeText(ev.status)}
                        </span>
                      </td>
                      <td>
                        <code>{shortId(ev.sha256)}</code>
                      </td>
                      <td>{safeText(formatStr)}</td>
                      <td>{safeText(vendorStr)}</td>
                      <td>
                        {vRes ? (
                          <span className={`verify-pill ${vRes.match ? "verify-match" : "verify-mismatch"}`}>
                            {vRes.match ? "MATCH" : "MISMATCH"}
                          </span>
                        ) : (
                          "-"
                        )}
                      </td>
                      <td className="actions-cell">
                        <div className="btn-group-actions">
                          {ev.status === "REGISTERED" && (
                            <label className="btn-upload-label">
                              Upload
                              <input
                                type="file"
                                style={{ display: "none" }}
                                disabled={actionRunning}
                                onChange={(e) => {
                                  const f = e.target.files?.[0];
                                  if (f) handleUpload(ev.evidence_id, f);
                                }}
                              />
                            </label>
                          )}

                          {ev.status === "INGESTED" && (
                            <button
                              type="button"
                              className="btn-action-small"
                              disabled={actionRunning}
                              onClick={() => handleAction("hash", ev.evidence_id)}
                            >
                              Hash
                            </button>
                          )}

                          {ev.status === "HASHED" && (
                            <button
                              type="button"
                              className="btn-action-small"
                              disabled={actionRunning}
                              onClick={() => handleAction("verify", ev.evidence_id)}
                            >
                              Verify
                            </button>
                          )}

                          {ev.status !== "REGISTERED" && (
                            <>
                              <button
                                type="button"
                                className="btn-action-small"
                                disabled={actionRunning}
                                onClick={() => handleAction("detect-format", ev.evidence_id)}
                              >
                                Detect Format
                              </button>
                              <button
                                type="button"
                                className="btn-action-small"
                                disabled={actionRunning}
                                onClick={() => handleAction("detect-vendor", ev.evidence_id)}
                              >
                                Detect Vendor
                              </button>
                              <button
                                type="button"
                                className="btn-action-small"
                                disabled={actionRunning}
                                onClick={() => handleAction("analyze-filesystem", ev.evidence_id)}
                              >
                                Analyze FS
                              </button>
                              <button
                                type="button"
                                className="btn-action-small"
                                disabled={actionRunning}
                                onClick={() => handleAction("extract-metadata", ev.evidence_id)}
                              >
                                Extract Metadata
                              </button>
                              <button
                                type="button"
                                className="btn-action-small"
                                disabled={actionRunning || loadingMetaId === ev.evidence_id}
                                onClick={() => handleViewMetadata(ev.evidence_id)}
                              >
                                {loadingMetaId === ev.evidence_id ? "Loading..." : "View Metadata"}
                              </button>
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {selectedMeta && (
        <div className="card metadata-viewer-card">
          <div className="section-header-row">
            <h3>Metadata Viewer: Evidence {shortId(selectedMeta.subject_id)}</h3>
            <button
              type="button"
              className="btn-secondary"
              onClick={() => setSelectedMeta(null)}
            >
              Close Metadata
            </button>
          </div>

          <div className="meta-summary-bar">
            <span>Container: <strong>{safeText(selectedMeta.container)}</strong></span>
            <span>Parser Version: <strong>{safeText(selectedMeta.parser_version)}</strong></span>
            <span>Status: <strong>{safeText(selectedMeta.status)}</strong></span>
            <span>Extracted: <strong>{safeText(selectedMeta.extracted_at)}</strong></span>
          </div>

          {selectedMeta.result?.fields && selectedMeta.result.fields.length > 0 ? (
            <div className="table-container">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Field</th>
                    <th>Raw Value</th>
                    <th>Interpreted Value</th>
                    <th>Source</th>
                    <th>Byte Offset</th>
                    <th>Note</th>
                  </tr>
                </thead>
                <tbody>
                  {selectedMeta.result.fields.map((fld, idx) => (
                    <tr key={idx}>
                      <td><code>{safeText(fld.field)}</code></td>
                      <td>{safeText(fld.raw_value)}</td>
                      <td>{safeText(fld.interpreted_value)}</td>
                      <td>{safeText(fld.source)}</td>
                      <td>{fld.byte_offset != null ? fld.byte_offset : "-"}</td>
                      <td>{safeText(fld.note)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="empty-state">No fields extracted in metadata.</div>
          )}
        </div>
      )}
    </div>
  );
}
