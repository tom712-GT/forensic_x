import React, { useState, useEffect } from "react";
import { api, encId } from "../lib/api.js";
import { shortId, safeText } from "../lib/format.js";
import { ErrorBanner } from "../components/ErrorBanner.jsx";
import { Loading } from "../components/Loading.jsx";
import { EvidenceTab } from "./EvidenceTab.jsx";
import { TimelineTab } from "./TimelineTab.jsx";
import { TimeTab } from "./TimeTab.jsx";
import { GapsTab } from "./GapsTab.jsx";
import { CorrelationTab } from "./CorrelationTab.jsx";
import { ReportTab } from "./ReportTab.jsx";

const TABS = [
  { id: "evidence", label: "Evidence" },
  { id: "timeline", label: "Timeline" },
  { id: "time", label: "Time" },
  { id: "gaps", label: "Gaps" },
  { id: "correlation", label: "Correlation" },
  { id: "report", label: "Report" },
];

export function CasePage({ caseId }) {
  const [caseObj, setCaseObj] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState("evidence");

  async function loadCaseData() {
    try {
      setLoading(true);
      setError(null);
      setCaseObj(null);
      const res = await api.get(`/api/cases/${encId(caseId)}`);
      setCaseObj(res);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    setActiveTab("evidence");
    loadCaseData();
  }, [caseId]);

  if (loading) {
    return (
      <div className="page case-page">
        <Loading message="Loading case details..." />
      </div>
    );
  }

  if (error || !caseObj) {
    const isNotFound = error?.status === 404 || !caseObj;
    return (
      <div className="page case-page error-page">
        <div className="card not-found-card">
          <h2>{isNotFound ? "Case not found" : "Error Loading Case"}</h2>
          <p className="subtitle">
            {error?.message || "The requested case identifier could not be located."}
          </p>
          <div className="mt-4">
            <a href="#/" className="btn-primary">
              &larr; Back to Cases List
            </a>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="page case-page">
      <header className="case-header card">
        <div className="case-breadcrumb">
          <a href="#/" className="back-link">&larr; All Cases</a>
        </div>
        <div className="case-title-row">
          <h1>{safeText(caseObj.case_name)}</h1>
          <span className="case-id-badge">ID: {shortId(caseObj.case_id)}</span>
          <span className="status-badge">{safeText(caseObj.status)}</span>
        </div>
        {caseObj.description && (
          <p className="case-description">{safeText(caseObj.description)}</p>
        )}
      </header>

      <nav className="case-tabs-nav" aria-label="Case Sections">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            className={`tab-btn ${activeTab === tab.id ? "tab-active" : ""}`}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      <main className="tab-container">
        {activeTab === "evidence" && <EvidenceTab caseId={caseObj.case_id} />}
        {activeTab === "timeline" && <TimelineTab caseId={caseObj.case_id} />}
        {activeTab === "time" && <TimeTab caseId={caseObj.case_id} />}
        {activeTab === "gaps" && <GapsTab caseId={caseObj.case_id} />}
        {activeTab === "correlation" && <CorrelationTab caseId={caseObj.case_id} />}
        {activeTab === "report" && <ReportTab caseId={caseObj.case_id} />}
      </main>
    </div>
  );
}
