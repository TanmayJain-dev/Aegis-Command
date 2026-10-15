import { describe, it, expect } from "vitest";
import { POST } from "./route";

function makeRequest(query: string) {
  return new Request("http://localhost:3000/api/intel/search", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });
}

describe("Next.js Embedded Tactical Intelligence Search Route", () => {
  it("returns INTEL-9999 pickup truck intercept for 'truck'", async () => {
    const res = await POST(makeRequest("truck"));
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.status).toBe("success");
    expect(body.data).toHaveLength(1);
    expect(body.data[0].id).toBe("INTEL-9999");
    expect(body.data[0].score).toBe(0.94);
  });

  it("returns INTEL-1437 patrol intercept for 'person moving NE'", async () => {
    const res = await POST(makeRequest("person moving NE"));
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.status).toBe("success");
    expect(body.data).toHaveLength(1);
    expect(body.data[0].id).toBe("INTEL-1437");
    expect(body.data[0].score).toBe(0.88);
  });

  it("returns INTEL-1603 drone ingress intercept for 'drone'", async () => {
    const res = await POST(makeRequest("drone"));
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.status).toBe("success");
    expect(body.data).toHaveLength(1);
    expect(body.data[0].id).toBe("INTEL-1603");
    expect(body.data[0].score).toBe(0.91);
  });

  it("returns explicit empty results for irrelevant query 'banana'", async () => {
    const res = await POST(makeRequest("banana"));
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.status).toBe("success");
    expect(body.data).toHaveLength(0);
    expect(body.message).toBe("No relevant intelligence found.");
  });

  it("returns explicit empty results for gibberish query 'asdf'", async () => {
    const res = await POST(makeRequest("asdf"));
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.status).toBe("success");
    expect(body.data).toHaveLength(0);
    expect(body.message).toBe("No relevant intelligence found.");
  });

  it("returns explicit empty results for empty query", async () => {
    const res = await POST(makeRequest("   "));
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.status).toBe("success");
    expect(body.data).toHaveLength(0);
  });
});
