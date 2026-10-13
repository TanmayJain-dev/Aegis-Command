/**
 * Aegis Command - Tactical Audio Synthesizer.
 * Generates an immediate tactical down-chirp tone (880Hz -> 440Hz)
 * via the native Web Audio API, with zero external asset dependencies.
 */

export function playTacticalAlertTone(): void {
  if (typeof window === "undefined") return;

  try {
    const AudioContextClass =
      window.AudioContext ||
      (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;

    if (!AudioContextClass) return;

    const ctx = new AudioContextClass();
    if (ctx.state === "suspended") {
      ctx.resume().catch(() => {});
    }

    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    osc.type = "sine";
    const now = ctx.currentTime;

    // Tactical down-chirp frequency modulation (880 Hz to 440 Hz over 180ms)
    osc.frequency.setValueAtTime(880, now);
    osc.frequency.exponentialRampToValueAtTime(440, now + 0.18);

    // Fast decay envelope to prevent clipping
    gain.gain.setValueAtTime(0.2, now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.18);

    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.start(now);
    osc.stop(now + 0.18);

    // Close context after playback completes
    setTimeout(() => {
      ctx.close().catch(() => {});
    }, 250);
  } catch {
    // Silently continue if audio policy blocks autoplay prior to user interaction
  }
}
