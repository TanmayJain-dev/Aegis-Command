import { useState, useEffect, useCallback } from "react";

const STORAGE_KEY = "aegis:lite-mode";

export interface NetworkInformationLike {
  saveData?: boolean;
}

export interface LowPowerNavigatorLike {
  hardwareConcurrency?: number;
  deviceMemory?: number;
  connection?: NetworkInformationLike;
}

export interface LowPowerWindowLike {
  matchMedia?: (query: string) => { matches: boolean };
}

/**
 * Detects whether the current device is low-powered, bandwidth-constrained,
 * or requesting reduced animations.
 */
export function detectLowPowerDevice(
  nav?: LowPowerNavigatorLike,
  win?: LowPowerWindowLike
): boolean {
  const currentNav =
    nav ??
    (typeof navigator !== "undefined"
      ? (navigator as unknown as LowPowerNavigatorLike)
      : undefined);
  const currentWin =
    win ??
    (typeof window !== "undefined"
      ? (window as unknown as LowPowerWindowLike)
      : undefined);

  if (!currentNav && !currentWin) {
    return false;
  }

  // 1. Hardware Concurrency (cores <= 4)
  if (typeof currentNav?.hardwareConcurrency === "number" && currentNav.hardwareConcurrency <= 4) {
    return true;
  }

  // 2. Device Memory (RAM <= 4 GB)
  if (typeof currentNav?.deviceMemory === "number" && currentNav.deviceMemory <= 4) {
    return true;
  }

  // 3. Network Save-Data header preference
  if (currentNav?.connection?.saveData === true) {
    return true;
  }

  // 4. Operating System prefers-reduced-motion
  if (
    currentWin &&
    typeof currentWin.matchMedia === "function" &&
    currentWin.matchMedia("(prefers-reduced-motion: reduce)")?.matches
  ) {
    return true;
  }

  return false;
}

export interface UseLiteModeReturn {
  liteMode: boolean;
  setLiteMode: (enabled: boolean) => void;
  toggleLiteMode: () => void;
}

/**
 * Hook to manage high-efficiency Lite Mode across the tactical console.
 * Sets data-lite="true" on root element and persists manual preference in localStorage.
 */
export function useLiteMode(): UseLiteModeReturn {
  const [liteMode, setLiteModeState] = useState<boolean>(() => {
    if (typeof window === "undefined") return false;
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored !== null) {
        return stored === "true";
      }
    } catch {
      // Ignore localStorage errors (private browsing / disabled storage)
    }
    return detectLowPowerDevice();
  });

  useEffect(() => {
    if (typeof document === "undefined") return;
    document.documentElement.setAttribute("data-lite", liteMode ? "true" : "false");
  }, [liteMode]);

  const setLiteMode = useCallback((enabled: boolean) => {
    setLiteModeState(enabled);
    try {
      localStorage.setItem(STORAGE_KEY, enabled ? "true" : "false");
    } catch {
      // Ignore localStorage write failures
    }
  }, []);

  const toggleLiteMode = useCallback(() => {
    setLiteMode(!liteMode);
  }, [liteMode, setLiteMode]);

  return {
    liteMode,
    setLiteMode,
    toggleLiteMode,
  };
}
