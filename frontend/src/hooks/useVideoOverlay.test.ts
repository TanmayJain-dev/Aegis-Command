import { describe, it, expect } from "vitest";
import {
  computeDisplayedVideoRect,
  computeOverlayScale,
} from "./useVideoOverlay";

describe("useVideoOverlay geometry & letterbox/pillarbox alignment", () => {
  describe("computeDisplayedVideoRect", () => {
    it("handles pillarboxed container (wider than 16:9, e.g. Desktop 1440x900)", () => {
      // Desktop container: 800x298 (ratio ~2.68:1 > 1.777:1)
      const rect = computeDisplayedVideoRect(800, 298, 1280, 720);
      expect(rect.height).toBe(298);
      expect(rect.width).toBeCloseTo(298 * (16 / 9), 2);
      expect(rect.offsetX).toBeCloseTo((800 - 298 * (16 / 9)) / 2, 2);
      expect(rect.offsetY).toBe(0);
    });

    it("handles pillarboxed container (Tablet 1100x700)", () => {
      // Tablet container: 602x298 (ratio ~2.02:1 > 1.777:1)
      const rect = computeDisplayedVideoRect(602, 298, 1280, 720);
      expect(rect.height).toBe(298);
      expect(rect.width).toBeCloseTo(298 * (16 / 9), 2);
      expect(rect.offsetX).toBeCloseTo((602 - 298 * (16 / 9)) / 2, 2);
      expect(rect.offsetY).toBe(0);
    });

    it("handles letterboxed container (taller than 16:9, e.g. Mobile 390x844)", () => {
      // Mobile container: 364x238 (ratio ~1.53:1 < 1.777:1)
      const rect = computeDisplayedVideoRect(364, 238, 1280, 720);
      expect(rect.width).toBe(364);
      expect(rect.height).toBeCloseTo(364 / (16 / 9), 2);
      expect(rect.offsetX).toBe(0);
      expect(rect.offsetY).toBeCloseTo((238 - 364 / (16 / 9)) / 2, 2);
    });

    it("safely handles zero or negative dimensions", () => {
      const rect = computeDisplayedVideoRect(0, 0, 1920, 1080);
      expect(rect.width).toBe(0);
      expect(rect.height).toBe(0);
      expect(rect.offsetX).toBe(0);
      expect(rect.offsetY).toBe(0);
    });
  });

  describe("Audit Table Test Cases (Zero Coordinate Error Verification)", () => {
    const AUDIT_CASES = [
      {
        id: "Vehicle-105",
        cls: "person",
        time: 2.2,
        sourceBox: [1864.0, 303.0, 1896.3, 355.8] as [number, number, number, number],
      },
      {
        id: "Vehicle-294",
        cls: "truck",
        time: 9.99,
        sourceBox: [1117.7, 516.2, 1446.6, 748.9] as [number, number, number, number],
      },
      {
        id: "Vehicle-986",
        cls: "person",
        time: 20.15,
        sourceBox: [957.6, 254.9, 982.3, 307.9] as [number, number, number, number],
      },
    ];

    const VIEWPORTS = [
      { name: "desktop_1440x900", cw: 800, ch: 298 },
      { name: "tablet_1100x700", cw: 602, ch: 298 },
      { name: "mobile_390x844", cw: 364, ch: 238 },
    ];

    VIEWPORTS.forEach((vp) => {
      describe(`Viewport ${vp.name}`, () => {
        AUDIT_CASES.forEach((det) => {
          it(`renders ${det.id} [${det.cls}] with 0.0px coordinate error against physical video rect`, () => {
            const scale = computeOverlayScale(vp.cw, vp.ch, 1920, 1080, 1280, 720);

            // Compute rendered box position
            const renderedX1 = (scale.offsetX ?? 0) + det.sourceBox[0] * scale.scaleX;
            const renderedY1 = (scale.offsetY ?? 0) + det.sourceBox[1] * scale.scaleY;
            const renderedW = (det.sourceBox[2] - det.sourceBox[0]) * scale.scaleX;
            const renderedH = (det.sourceBox[3] - det.sourceBox[1]) * scale.scaleY;

            // Compute expected physical position from displayed video frame
            const disp = computeDisplayedVideoRect(vp.cw, vp.ch, 1280, 720);
            const expectedScaleX = disp.width / 1920;
            const expectedScaleY = disp.height / 1080;
            const expectedX1 = disp.offsetX + det.sourceBox[0] * expectedScaleX;
            const expectedY1 = disp.offsetY + det.sourceBox[1] * expectedScaleY;
            const expectedW = (det.sourceBox[2] - det.sourceBox[0]) * expectedScaleX;
            const expectedH = (det.sourceBox[3] - det.sourceBox[1]) * expectedScaleY;

            // Difference must be strictly 0.0px (within floating point precision)
            expect(Math.abs(renderedX1 - expectedX1)).toBeLessThan(1e-4);
            expect(Math.abs(renderedY1 - expectedY1)).toBeLessThan(1e-4);
            expect(Math.abs(renderedW - expectedW)).toBeLessThan(1e-4);
            expect(Math.abs(renderedH - expectedH)).toBeLessThan(1e-4);
          });
        });
      });
    });
  });
});
