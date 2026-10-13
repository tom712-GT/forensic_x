import React from "react";

export function Loading({ message = "Loading..." }) {
  return (
    <div className="loading-state" role="status">
      <div className="loading-spinner"></div>
      <span className="loading-text">{message}</span>
    </div>
  );
}
