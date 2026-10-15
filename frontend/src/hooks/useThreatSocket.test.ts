import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { getWebSocketUrl } from "./useThreatSocket";

describe("getWebSocketUrl", () => {
  const originalEnv = { ...process.env };

  beforeEach(() => {
    delete process.env.NEXT_PUBLIC_WS_URL;
    delete process.env.NEXT_PUBLIC_BACKEND_URL;
  });

  afterEach(() => {
    process.env = { ...originalEnv };
  });

  it("prioritizes explicit NEXT_PUBLIC_WS_URL when set", () => {
    process.env.NEXT_PUBLIC_WS_URL = "wss://custom-ws.example.com/ws/threat-engine";
    expect(getWebSocketUrl()).toBe("wss://custom-ws.example.com/ws/threat-engine");
  });

  it("converts https NEXT_PUBLIC_BACKEND_URL to wss", () => {
    process.env.NEXT_PUBLIC_BACKEND_URL = "https://aegis-api.onrender.com";
    expect(getWebSocketUrl()).toBe("wss://aegis-api.onrender.com/ws/threat-engine");
  });

  it("converts http NEXT_PUBLIC_BACKEND_URL to ws", () => {
    process.env.NEXT_PUBLIC_BACKEND_URL = "http://127.0.0.1:8000/";
    expect(getWebSocketUrl()).toBe("ws://127.0.0.1:8000/ws/threat-engine");
  });

  it("returns fallback ws URL when env vars are unset", () => {
    const url = getWebSocketUrl();
    expect(url).toContain("/ws/threat-engine");
  });
});
