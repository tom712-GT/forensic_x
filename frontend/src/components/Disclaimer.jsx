import React from "react";

export function Disclaimer({ text, title = "Forensic Disclaimer" }) {
  if (!text) return null;
  return (
    <div className="disclaimer-box" role="note">
      <div className="disclaimer-title">{title}</div>
      <div className="disclaimer-content">{text}</div>
    </div>
  );
}
