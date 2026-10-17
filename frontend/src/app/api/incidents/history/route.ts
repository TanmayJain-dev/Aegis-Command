import { NextResponse } from "next/server";

export async function GET(req: Request) {
  const backendUrl = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_BACKEND_URL;
  const { searchParams } = new URL(req.url);
  const limit = searchParams.get("limit") || "100";
  const threatLevel = searchParams.get("threat_level") || "";

  if (backendUrl && !backendUrl.includes("localhost") && !backendUrl.includes("backend:8000")) {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 4000);
      const url = new URL(`${backendUrl.replace(/\/+$/, "")}/api/incidents/history`);
      url.searchParams.set("limit", limit);
      if (threatLevel) {
        url.searchParams.set("threat_level", threatLevel);
      }

      const res = await fetch(url.toString(), {
        headers: { "Content-Type": "application/json" },
        signal: controller.signal,
      });
      clearTimeout(timeoutId);

      if (res.ok) {
        const data = await res.json();
        return NextResponse.json(data);
      }
    } catch (err) {
      console.warn("Backend incidents/history proxy unavailable, serving local graceful empty response:", err);
    }
  }

  // Graceful response when backend is offline or unconfigured
  return NextResponse.json({
    status: "success",
    count: 0,
    records: [],
    message: "Backend offline. Running on local seed history."
  });
}
