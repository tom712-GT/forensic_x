import { describe, it, expect } from "vitest";
import { createApi, ApiError, encId } from "./api.js";
import { shortId, formatBytes, formatSeconds, safeText } from "./format.js";

function mockResp(status, body, jsonFails = false) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => {
      if (jsonFails) throw new Error("not json");
      return body;
    },
  };
}

describe("own: api edge cases", () => {
  it("o01 base URL with trailing slash removes duplicate slashes", async () => {
    let seenUrl = null;
    const client = createApi(async (url) => {
      seenUrl = url;
      return mockResp(200, { ok: true });
    }, "http://localhost:8000/");

    await client.get("/api/cases");
    expect(seenUrl).toBe("http://localhost:8000/api/cases");

    await client.get("api/health");
    expect(seenUrl).toBe("http://localhost:8000/api/health");
  });

  it("o02 empty body 204 No Content returns null without crashing", async () => {
    const client = createApi(async () => mockResp(204, null, true), "http://localhost:8000");
    const res = await client.post("/api/empty", {});
    expect(res).toBeNull();
  });

  it("o03 error with object detail is serialized to JSON string", async () => {
    const client = createApi(
      async () => mockResp(400, { detail: { code: "INVALID_FIELD", field: "evidence_id" } }),
      "http://localhost:8000"
    );
    let err = null;
    try {
      await client.get("/fail");
    } catch (e) {
      err = e;
    }
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(400);
    expect(err.message).toBe('{"code":"INVALID_FIELD","field":"evidence_id"}');
  });

  it("o04 error with top-level message field falls back to message", async () => {
    const client = createApi(
      async () => mockResp(503, { message: "Service Temporarily Unavailable" }),
      "http://localhost:8000"
    );
    let err = null;
    try {
      await client.get("/err");
    } catch (e) {
      err = e;
    }
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(503);
    expect(err.message).toBe("Service Temporarily Unavailable");
  });

  it("o05 upload with File-like object and custom filename", async () => {
    let capturedOpts = null;
    const client = createApi(async (url, opts) => {
      capturedOpts = opts;
      return mockResp(200, { status: "INGESTED" });
    }, "http://localhost:8000");

    const blob = new Blob(["sample bytes"]);
    await client.upload("/upload", blob, "cctv_sample.bin");
    expect(capturedOpts.method).toBe("POST");
    expect(capturedOpts.body instanceof FormData).toBe(true);
    expect(capturedOpts.body.get("file")).toBeDefined();
  });

  it("o06 encId with null or undefined returns empty string", () => {
    expect(encId(null)).toBe("");
    expect(encId(undefined)).toBe("");
  });

  it("o07 encId converts numbers to safe encoded string", () => {
    expect(encId(12345)).toBe("12345");
    expect(encId("id#99?")).toBe("id%2399%3F");
  });
});

describe("own: format edge cases", () => {
  it("o08 shortId with long UUID extracts first 8 chars", () => {
    expect(shortId("5e8ff719-74d2-43e9-a29d-40787e9cf2ef")).toBe("5e8ff719");
  });

  it("o09 formatBytes boundary checks for 1023 B and 1024 B", () => {
    expect(formatBytes(1023)).toBe("1023 B");
    expect(formatBytes(1024)).toBe("1.0 KB");
  });

  it("o10 formatBytes handles invalid input or negative numbers by returning dash", () => {
    expect(formatBytes(-100)).toBe("-");
    expect(formatBytes(NaN)).toBe("-");
    expect(formatBytes("1024")).toBe("-");
  });

  it("o11 formatBytes large gigabyte and terabyte values", () => {
    expect(formatBytes(1073741824)).toBe("1.0 GB");
    expect(formatBytes(1099511627776)).toBe("1.0 TB");
  });

  it("o12 formatSeconds with floating point seconds floors correctly", () => {
    expect(formatSeconds(90.7)).toBe("1 min 30 s");
    expect(formatSeconds(0.4)).toBe("0 s");
  });

  it("o13 formatSeconds handles negative seconds by returning dash", () => {
    expect(formatSeconds(-10)).toBe("-");
    expect(formatSeconds(NaN)).toBe("-");
  });

  it("o14 formatSeconds with large durations", () => {
    expect(formatSeconds(7200)).toBe("2 h 0 min 0 s");
    expect(formatSeconds(3600)).toBe("1 h 0 min 0 s");
  });

  it("o15 safeText handles booleans and numbers properly", () => {
    expect(safeText(true)).toBe("true");
    expect(safeText(false)).toBe("false");
    expect(safeText(0)).toBe("0");
  });
});
