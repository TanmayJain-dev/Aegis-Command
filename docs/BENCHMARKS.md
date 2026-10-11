# System & Performance Benchmarks

## Environment Baseline

- **Operating System**: Linux 6.8.0-52-generic (x86_64, 2 physical cores, ~4 GB RAM)
- **Python**: `3.12.3`
- **Virtual Environment**: `vision/.venv` (PyTorch 2.14.1, Ultralytics 8.4.175, OpenCV, FastAPI, Uvicorn)
- **GPU**: `no GPU` (CPU execution)
- **FFmpeg**: `6.1.1-3ubuntu5`
- **Node.js**: `v24.18.0`
- **Package Manager**: `pnpm` 10.x / `npm` 11.x

---

## Frontend Baseline

Measured on branch `feat/accuracy-v2` prior to refactoring (Task 0).

### Static Verification & Build
- **TypeScript (`tsc --noEmit`)**: Exit code `0`
- **ESLint (`eslint src`)**: `25 problems (14 errors, 11 warnings)`
  - Errors:
    - 10 × `@typescript-eslint/no-explicit-any` (9 in `page.tsx`, 1 in `Map.tsx`)
    - 1 × `react-hooks/refs` (`Cannot access refs during render` on `seekToTime` callback in timeline scrub markers)
    - 2 × `react/no-unescaped-entities` (unescaped quotes in `page.tsx`)
    - 1 × `react/jsx-no-comment-textnodes` (unwrapped comment in JSX children)
  - Warnings:
    - 10 × `@typescript-eslint/no-unused-vars`
    - 1 × `@typescript-eslint/no-unused-expressions`
- **Next.js Production Build (`next build`)**:
  - Status: Succeeded in `25.9s` (Turbopack, Next.js 16.2.11)
  - Static chunks payload size: `~880 KB` across 11 bundles (`.next/static/chunks/`)

### Runtime Performance Probe (`?perf=1`)

Measured using Playwright running headless Brave (`--headless=new`) playing `frontend/public/drone_feed.mp4`:

| Configuration | Frames Sampled | Mean Draw Time (ms) | p95 Draw Time (ms) | Total React Commits | Commits / sec | Test Duration (s) |
|---|---|---|---|---|---|---|
| **Normal Playback (1x CPU)** | 600 | 6.435 ms | 13.900 ms | 382 | 1.29 | 295.25 s |
| **Throttled Playback (4x CPU via CDP)** | 150 | 29.211 ms | 65.300 ms | 67 | 0.26 | 262.47 s |

*Note: Visual baseline reference captures recorded at `local_assets/shots_before/desktop_1440x900.png` and `local_assets/shots_before/mobile_390x844.png`.*
