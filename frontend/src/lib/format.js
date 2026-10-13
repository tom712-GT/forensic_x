export function shortId(id) {
  if (id === null || id === undefined || id === "") return "-";
  const s = String(id);
  if (s.length === 0) return "-";
  return s.slice(0, 8);
}

export function formatBytes(bytes) {
  if (bytes === null || bytes === undefined || typeof bytes !== "number" || isNaN(bytes)) return "-";
  if (bytes < 0) return "-";
  if (bytes === 0) return "0 B";
  if (bytes < 1024) return `${bytes} B`;
  const units = ["B", "KB", "MB", "GB", "TB", "PB"];
  let i = Math.floor(Math.log(bytes) / Math.log(1024));
  if (i >= units.length) i = units.length - 1;
  const val = bytes / Math.pow(1024, i);
  return `${val.toFixed(1)} ${units[i]}`;
}

export function formatSeconds(sec) {
  if (sec === null || sec === undefined || typeof sec !== "number" || isNaN(sec)) return "-";
  if (sec < 0) return "-";
  const total = Math.floor(sec);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  if (h > 0) return `${h} h ${m} min ${s} s`;
  if (m > 0) return `${m} min ${s} s`;
  return `${s} s`;
}

export function safeText(val) {
  if (val === null || val === undefined) return "-";
  const str = typeof val === "string" ? val : JSON.stringify(val);
  if (typeof str !== "string") return "-";
  if (str.length > 200) {
    return str.slice(0, 200) + "\u2026";
  }
  return str;
}
