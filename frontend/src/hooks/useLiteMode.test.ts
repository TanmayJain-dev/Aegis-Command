import { describe, it, expect } from "vitest";
import {
  detectLowPowerDevice,
  LowPowerNavigatorLike,
  LowPowerWindowLike,
} from "./useLiteMode";

describe("Hardware & Network Low Power Detection", () => {
  it("detects low-power device when hardwareConcurrency <= 4", () => {
    expect(detectLowPowerDevice({ hardwareConcurrency: 2 })).toBe(true);
    expect(detectLowPowerDevice({ hardwareConcurrency: 4 })).toBe(true);
    expect(detectLowPowerDevice({ hardwareConcurrency: 8 })).toBe(false);
  });

  it("detects low-power device when deviceMemory <= 4 GB", () => {
    const lowMemNav: LowPowerNavigatorLike = { hardwareConcurrency: 8, deviceMemory: 4 };
    const highMemNav: LowPowerNavigatorLike = { hardwareConcurrency: 8, deviceMemory: 8 };
    expect(detectLowPowerDevice(lowMemNav)).toBe(true);
    expect(detectLowPowerDevice(highMemNav)).toBe(false);
  });

  it("detects low-power mode when connection.saveData is enabled", () => {
    const saveDataNav: LowPowerNavigatorLike = {
      hardwareConcurrency: 16,
      deviceMemory: 16,
      connection: { saveData: true },
    };
    const standardNav: LowPowerNavigatorLike = {
      hardwareConcurrency: 16,
      deviceMemory: 16,
      connection: { saveData: false },
    };
    expect(detectLowPowerDevice(saveDataNav)).toBe(true);
    expect(detectLowPowerDevice(standardNav)).toBe(false);
  });

  it("detects low-power mode when OS prefers reduced motion", () => {
    const mockWinReduced: LowPowerWindowLike = {
      matchMedia: (query: string) => ({
        matches: query.includes("prefers-reduced-motion: reduce"),
      }),
    };

    const mockWinNormal: LowPowerWindowLike = {
      matchMedia: () => ({
        matches: false,
      }),
    };

    const fastNav: LowPowerNavigatorLike = { hardwareConcurrency: 16, deviceMemory: 16 };

    expect(detectLowPowerDevice(fastNav, mockWinReduced)).toBe(true);
    expect(detectLowPowerDevice(fastNav, mockWinNormal)).toBe(false);
  });
});
