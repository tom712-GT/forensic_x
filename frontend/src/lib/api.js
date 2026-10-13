export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export function encId(id) {
  if (id === null || id === undefined) return "";
  return encodeURIComponent(String(id));
}

export function createApi(fetchImpl = globalThis.fetch, baseUrl = (typeof import.meta !== "undefined" && import.meta.env?.VITE_API_BASE) || "http://127.0.0.1:8000") {
  const cleanBase = baseUrl ? baseUrl.replace(/\/+$/, "") : "";

  function buildUrl(path) {
    if (!path.startsWith("/")) {
      return `${cleanBase}/${path}`;
    }
    return `${cleanBase}${path}`;
  }

  async function request(path, options = {}) {
    const url = buildUrl(path);
    let res;
    try {
      res = await fetchImpl(url, options);
    } catch (err) {
      throw new ApiError(0, `Network error: ${err?.message || "failed"}`);
    }

    if (!res.ok) {
      let body = null;
      try {
        body = await res.json();
      } catch {
        // unreadable body
      }

      let message = `HTTP ${res.status}`;
      if (body) {
        if (typeof body.detail === "string") {
          message = body.detail;
        } else if (Array.isArray(body.detail)) {
          message = body.detail.map((d) => (d && typeof d === "object" && d.msg ? d.msg : JSON.stringify(d))).join("; ");
        } else if (body.detail && typeof body.detail === "object") {
          message = JSON.stringify(body.detail);
        } else if (typeof body.message === "string") {
          message = body.message;
        } else if (typeof body === "string") {
          message = body;
        }
      }
      throw new ApiError(res.status, message);
    }

    try {
      return await res.json();
    } catch {
      return null;
    }
  }

  return {
    async get(path) {
      return request(path, { method: "GET" });
    },
    async post(path, body) {
      return request(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
    },
    async put(path, body) {
      return request(path, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
    },
    async upload(path, file, filename) {
      const formData = new FormData();
      if (filename) {
        formData.append("file", file, filename);
      } else {
        formData.append("file", file);
      }
      return request(path, {
        method: "POST",
        body: formData,
      });
    },
  };
}

export const api = createApi();
