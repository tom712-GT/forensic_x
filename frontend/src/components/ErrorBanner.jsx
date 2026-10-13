import React from "react";

export function ErrorBanner({ error, onDismiss }) {
  if (!error) return null;
  const message = typeof error === "string" ? error : error.message || "An error occurred";
  return (
    <div className="error-banner" role="alert">
      <span className="error-text">{message}</span>
      {onDismiss && (
        <button type="button" className="error-dismiss" onClick={onDismiss}>
          Dismiss
        </button>
      )}
    </div>
  );
}
