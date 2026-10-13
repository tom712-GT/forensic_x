import React, { useState } from "react";
import { api, encId } from "../lib/api.js";
import { safeText } from "../lib/format.js";
import { ErrorBanner } from "../components/ErrorBanner.jsx";
import { Loading } from "../components/Loading.jsx";
import { Disclaimer } from "../components/Disclaimer.jsx";

export function ReportTab({ caseId }) {
  const [reportData, setReportData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Verification state
  const [verifyHashInput, setVerifyHashInput] = useState("");
  const [verifyReportInput, setVerifyReportInput] = useState("");
  const [verifying, setVerifying] = useState(false);
  const [verifyResult, setVerifyResult] = useState(null);
  const [verifyError, setVerifyError] = useState(null);

  // Copy hash feedback
  const [copiedHash, setCopiedHash] = useState(false);

  async function handleGenerateReport() {
    try {
      setLoading(true);
      setError(null);
      const res = await api.get(`/api/cases/${encId(caseId)}/report`);
      setReportData(res);
      setVerifyHashInput(res?.report_sha256 || "");
      setVerifyReportInput("");
      setVerifyResult(null);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }

  function handleCopyHash() {
    if (!reportData?.report_sha256) return;
    if (navigator?.clipboard?.writeText) {
      navigator.clipboard.writeText(reportData.report_sha256);
      setCopiedHash(true);
      setTimeout(() => setCopiedHash(false), 2000);
    }
  }

  function handleDownloadJson() {
    if (!reportData?.report) return;
    // Build Blob from the SAME parsed object returned by the API
    const jsonStr = JSON.stringify(reportData.report, null, 2);
    const blob = new Blob([jsonStr], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `case_${caseId}_report.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  async function handleVerify(e) {
    if (e) e.preventDefault();

    let targetReport = reportData?.report;
    let targetHash = verifyHashInput.trim();

    if (verifyReportInput.trim()) {
      try {
        targetReport = JSON.parse(verifyReportInput.trim());
      } catch {
        setVerifyError("Invalid JSON in report verification input.");
        return;
      }
    }

    if (!targetReport) {
      setVerifyError("No report available to verify. Please generate or paste a report JSON.");
      return;
    }

    if (!/^[0-9a-f]{64}$/.test(targetHash)) {
      setVerifyError("Report SHA-256 must be 64 lowercase hexadecimal characters.");
      return;
    }

    try {
      setVerifying(true);
      setVerifyError(null);
      const res = await api.post("/api/reports/verify", {
        report: targetReport,
        report_sha256: targetHash,
      });
      setVerifyResult(res);
    } catch (err) {
      setVerifyError(err);
    } finally {
      setVerifying(false);
    }
  }

  const report = reportData?.report;
  const sections = report?.sections;

  return (
    <div className="tab-content report-tab">
      <div className="tab-header">
        <h2>Forensic Report & Cryptographic Certificate</h2>
        <div className="alert-box integrity-note" role="note">
          <strong>Important:</strong> Keep the hash outside this system. A hash stored only here proves little.
        </div>
      </div>

      <ErrorBanner error={error} onDismiss={() => setError(null)} />
      <ErrorBanner error={verifyError} onDismiss={() => setVerifyError(null)} />

      <div className="card action-bar-card">
        <button
          type="button"
          className="btn-primary btn-large"
          disabled={loading}
          onClick={handleGenerateReport}
        >
          {loading ? "Generating Report..." : "Generate report"}
        </button>
      </div>

      {loading && <Loading message="Generating comprehensive forensic report..." />}

      {reportData && (
        <>
          <div className="card certificate-card">
            <h3>Report Integrity Certificate</h3>
            <div className="cert-meta-grid">
              <div className="cert-field">
                <span className="field-label">Algorithm:</span>
                <span className="field-value">{safeText(reportData.algorithm)}</span>
              </div>
              <div className="cert-field">
                <span className="field-label">Canonicalization:</span>
                <span className="field-value">{safeText(reportData.canonicalization)}</span>
              </div>
              <div className="cert-field full-width">
                <span className="field-label">Report SHA-256 Digest:</span>
                <code className="report-hash-display">{reportData.report_sha256}</code>
              </div>
            </div>

            <div className="cert-actions-row">
              <button
                type="button"
                className="btn-secondary"
                onClick={handleCopyHash}
              >
                {copiedHash ? "Copied to Clipboard!" : "Copy hash"}
              </button>
              <button
                type="button"
                className="btn-secondary"
                onClick={handleDownloadJson}
              >
                Download report JSON
              </button>
            </div>
          </div>

          <div className="card report-content-card">
            <h3>Case Report Summary</h3>
            <div className="case-overview-grid">
              <div><strong>Case ID:</strong> {safeText(report?.case?.case_id)}</div>
              <div><strong>Case Name:</strong> {safeText(report?.case?.case_name)}</div>
              <div><strong>Generated At:</strong> {safeText(report?.generated_at)}</div>
              <div><strong>Evidence Count:</strong> {report?.evidence?.length || 0}</div>
            </div>

            {sections && (
              <div className="sections-container">
                <div className="section-block">
                  <h4>1. Timeline Overview</h4>
                  <div className="section-body">
                    <div>Dated Events: {sections.timeline?.event_count}</div>
                    <div>Undated Events: {sections.timeline?.undated_count}</div>
                    <div>Earliest Claim: {safeText(sections.timeline?.earliest)}</div>
                    <div>Latest Claim: {sections.timeline?.latest ? safeText(sections.timeline.latest) : "-"}</div>
                    <div>Truncated: {sections.timeline?.truncated ? "Yes" : "No"}</div>
                  </div>
                </div>

                <div className="section-block">
                  <h4>2. Clock Calibration</h4>
                  <div className="section-body">
                    <div>Calibrated Evidence Count: {sections.calibration?.calibrated_evidence_count}</div>
                    <div>References Configured: {sections.calibration?.references?.length || 0}</div>
                  </div>
                </div>

                <div className="section-block">
                  <h4>3. Coverage Gaps</h4>
                  <div className="section-body">
                    <div>Total Gaps: {sections.gaps?.gap_count}</div>
                    <div>Total Gap Duration: {safeText(sections.gaps?.total_gap_seconds)} s</div>
                    <div>Longest Gap: {safeText(sections.gaps?.longest_gap_seconds)} s</div>
                    <div>Unknown Length Count: {sections.gaps?.unknown_length_count}</div>
                    <div>Unplaced Count: {sections.gaps?.unplaced_count}</div>
                  </div>
                </div>

                <div className="section-block">
                  <h4>4. Temporal Correlation</h4>
                  <div className="section-body">
                    <div>Overlap Windows: {sections.correlation?.window_count}</div>
                    <div>Total Overlap Duration: {safeText(sections.correlation?.total_overlap_seconds)} s</div>
                    <div>Max Simultaneous Groups: {sections.correlation?.max_simultaneous_groups}</div>
                  </div>
                </div>

                <div className="section-block">
                  <h4>5. Audit Hash Chain</h4>
                  <div className="section-body">
                    <div>Chain Status: <span className="status-badge">{safeText(sections.audit_chain?.status)}</span></div>
                    <div>Total Entries: {sections.audit_chain?.total_count}</div>
                    <div>Chained Entries: {sections.audit_chain?.chained_count}</div>
                    <div>Verified Entries: {sections.audit_chain?.verified_count}</div>
                  </div>
                </div>
              </div>
            )}

            {report?.limitations && (
              <div className="limitations-section">
                <h4>Systemic Forensic Limitations</h4>
                <ul className="limitations-list">
                  {report.limitations.map((lim, idx) => (
                    <li key={idx}>{lim}</li>
                  ))}
                </ul>
              </div>
            )}

            {report?.disclaimer && (
              <Disclaimer text={report.disclaimer} title="Report Disclaimer" />
            )}
          </div>

          <div className="card verify-report-card">
            <h3>Verify Report Hash</h3>
            <p className="subtitle">
              Verify that a report JSON object has not been altered or tampered with by checking against a hash digest.
            </p>
            <form onSubmit={handleVerify} className="form-standard">
              <div className="form-group">
                <label htmlFor="verify-hash-input">Report SHA-256 Hash to Verify *</label>
                <input
                  id="verify-hash-input"
                  type="text"
                  required
                  placeholder="64 hex lowercase characters"
                  value={verifyHashInput}
                  onChange={(e) => setVerifyHashInput(e.target.value)}
                  disabled={verifying}
                />
              </div>

              <div className="form-group">
                <label htmlFor="verify-json-input">Custom / External Report JSON (Optional - defaults to currently held report)</label>
                <textarea
                  id="verify-json-input"
                  rows={4}
                  placeholder="Paste report JSON here if verifying external file..."
                  value={verifyReportInput}
                  onChange={(e) => setVerifyReportInput(e.target.value)}
                  disabled={verifying}
                />
              </div>

              <button
                type="submit"
                className="btn-primary"
                disabled={verifying || !verifyHashInput.trim()}
              >
                {verifying ? "Verifying..." : "Verify"}
              </button>
            </form>

            {verifyResult && (
              <div className="verify-outcome-box">
                <h4>Verification Outcome:</h4>
                <div className="outcome-pill-container">
                  <span className={`verify-status-banner ${verifyResult.valid ? "outcome-valid" : "outcome-invalid"}`}>
                    {verifyResult.valid ? "VALID" : "NOT VALID"}
                  </span>
                </div>
                <div className="computed-hash-row">
                  <span>Computed SHA-256:</span>
                  <code>{verifyResult.computed_sha256}</code>
                </div>
                {verifyResult.disclaimer && (
                  <Disclaimer text={verifyResult.disclaimer} title="Verification Disclaimer" />
                )}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
