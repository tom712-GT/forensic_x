import { describe, it, expect } from "vitest";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createApi, ApiError, encId } from "./api.js";
import { shortId, formatBytes, formatSeconds, safeText } from "./format.js";

function resp(status, body, jsonFails = false) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => {
      if (jsonFails) throw new Error("not json");
      return body;
    },
  };
}

describe("api", () => {
  it("l01 get builds url from base and path and returns json", async () => {
    let seen;
    const api = createApi(async (url, opts) => { seen = [url, opts]; return resp(200, { a: 1 }); }, "http://h:1");
    const out = await api.get("/api/cases");
    expect(seen[0]).toBe("http://h:1/api/cases");
    expect(out).toEqual({ a: 1 });
  });

  it("l02 error with string detail throws ApiError with status and message", async () => {
    const api = createApi(async () => resp(404, { detail: "Case not found" }), "http://h");
    let err;
    try { await api.get("/x"); } catch (e) { err = e; }
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(404);
    expect(err.message).toBe("Case not found");
  });

  it("l03 422 array detail is joined into one message", async () => {
    const api = createApi(async () => resp(422, { detail: [{ msg: "bad one" }, { msg: "bad two" }] }), "http://h");
    let err;
    try { await api.post("/x", {}); } catch (e) { err = e; }
    expect(err.status).toBe(422);
    expect(err.message).toContain("bad one");
    expect(err.message).toContain("bad two");
  });

  it("l04 network failure becomes ApiError status 0", async () => {
    const api = createApi(async () => { throw new TypeError("failed"); }, "http://h");
    let err;
    try { await api.get("/x"); } catch (e) { err = e; }
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(0);
    expect(err.message.startsWith("Network error")).toBe(true);
  });

  it("l05 non-json error body gives HTTP status message", async () => {
    const api = createApi(async () => resp(500, null, true), "http://h");
    let err;
    try { await api.get("/x"); } catch (e) { err = e; }
    expect(err.status).toBe(500);
    expect(err.message).toBe("HTTP 500");
  });

  it("l06 post sends json body and content-type", async () => {
    let seen;
    const api = createApi(async (url, opts) => { seen = opts; return resp(201, {}); }, "http://h");
    await api.post("/x", { k: "v" });
    expect(seen.method).toBe("POST");
    expect(seen.headers["Content-Type"]).toBe("application/json");
    expect(seen.body).toBe(JSON.stringify({ k: "v" }));
  });

  it("l07 put uses PUT and upload sends FormData field file without content-type", async () => {
    let putOpts, upOpts;
    const api = createApi(async (url, opts) => {
      if (opts.method === "PUT") putOpts = opts; else upOpts = opts;
      return resp(200, {});
    }, "http://h");
    await api.put("/g", { group_label: "A" });
    expect(putOpts.method).toBe("PUT");
    const file = new Blob(["abc"]);
    await api.upload("/f", file, "a.bin");
    expect(upOpts.method).toBe("POST");
    expect(upOpts.body instanceof FormData).toBe(true);
    expect(upOpts.body.has("file")).toBe(true);
    expect((upOpts.headers || {})["Content-Type"]).toBeUndefined();
  });

  it("l08 encId encodes path characters", () => {
    expect(encId("a/b c")).toBe("a%2Fb%20c");
    expect(encId("<x>")).toBe("%3Cx%3E");
  });
});

describe("format", () => {
  it("l09 shortId", () => {
    expect(shortId("abcdefghijk")).toBe("abcdefgh");
    expect(shortId(null)).toBe("-");
    expect(shortId("")).toBe("-");
  });

  it("l10 formatBytes", () => {
    expect(formatBytes(0)).toBe("0 B");
    expect(formatBytes(1536)).toBe("1.5 KB");
    expect(formatBytes(1048576)).toBe("1.0 MB");
    expect(formatBytes(null)).toBe("-");
  });

  it("l11 formatSeconds", () => {
    expect(formatSeconds(0)).toBe("0 s");
    expect(formatSeconds(90)).toBe("1 min 30 s");
    expect(formatSeconds(3661)).toBe("1 h 1 min 1 s");
    expect(formatSeconds(null)).toBe("-");
  });

  it("l12 safeText", () => {
    expect(safeText(null)).toBe("-");
    expect(safeText(5)).toBe("5");
    expect(safeText({ a: 1 })).toBe('{"a":1}');
    expect(safeText("x".repeat(300)).length).toBe(201);
    expect(safeText("x".repeat(300)).endsWith("\u2026")).toBe(true);
    expect(safeText("<b>hi</b>")).toBe("<b>hi</b>");
  });
});

describe("source safety", () => {
  it("l13 no dangerous patterns, all requests via api layer, required files exist", () => {
    const srcDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
    const files = [];
    (function walk(d) {
      for (const n of fs.readdirSync(d)) {
        const p = path.join(d, n);
        if (fs.statSync(p).isDirectory()) walk(p);
        else if (/\.(js|jsx)$/.test(n) && !n.endsWith(".test.js")) files.push(p);
      }
    })(srcDir);
    expect(files.length).toBeGreaterThan(8);
    const forbidden = ["dangerouslySetInnerHTML", "innerHTML", "outerHTML", "crypto.subtle", "localStorage", "sessionStorage", "eval(", "document.write"];
    for (const f of files) {
      const text = fs.readFileSync(f, "utf8");
      for (const bad of forbidden) expect([f, text.includes(bad)]).toEqual([f, false]);
      if (!f.endsWith(path.join("lib", "api.js"))) expect([f, /\bfetch\(/.test(text)]).toEqual([f, false]);
    }
    for (const req of ["pages/CasesPage.jsx", "pages/CasePage.jsx", "pages/EvidenceTab.jsx", "pages/TimelineTab.jsx", "pages/TimeTab.jsx", "pages/GapsTab.jsx", "pages/CorrelationTab.jsx", "pages/ReportTab.jsx", "pages/AuditPanel.jsx"]) {
      expect([req, fs.existsSync(path.join(srcDir, req))]).toEqual([req, true]);
    }
  });
});
