import { describe, it, expect } from "vitest";
import { GET } from "./route";

describe("Incidents History Proxy Route", () => {
  it("returns a graceful success response with count and records", async () => {
    const req = new Request("http://localhost:3000/api/incidents/history");
    const res = await GET(req);
    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data.status).toBe("success");
    expect(Array.isArray(data.records)).toBe(true);
    expect(typeof data.count).toBe("number");
  });
});
