# System & Performance Benchmarks

## Environment Baseline

- **Operating System**: Linux 6.8.0-52-generic (x86_64, 2 physical cores, ~4 GB RAM)
- **Python**: `3.12.3`
- **Virtual Environment**: `vision/.venv` (PyTorch 2.14.1, Ultralytics 8.4.175, OpenCV, FastAPI, Uvicorn)
- **GPU**: `no GPU` (CPU execution)
- **FFmpeg**: `6.1.1-3ubuntu5`
- **Node.js**: `v24.18.0`
- **Package Manager**: `npm` 12.x

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

---

## Detection & Track Distribution Baseline

Measured via `vision/eval/track_stats.py` on `frontend/public/detections.json` (33.02s UAV footage):

> [!NOTE]
> Per project governance, accuracy metrics (Precision, Recall, F1, mAP50-95) are NOT reported because human-verified ground-truth labels (`vision/eval/labels/VERIFIED`) are pending verification. The numbers below document the operational data distribution and tracking continuity of the legacy feed. Speed (`speed_kmh`) and geo-projection telemetry are simulated attributes.

### Volume & Rates
- **Total Detections**: 2,563
- **Video Duration**: 33.02 s
- **Detection Rate**: 77.62 detections/second
- **Unique Track IDs**: 84

### Track Continuity
- **Median Track Length**: 8.0 observations (mean: 30.51)
- **Median Track Duration**: 0.46 s (mean: 1.26 s)
- **Short Tracks ($\le 10$ observations)**: 47 out of 84 tracks (55.95%)

### Class Breakdown
| Class | Detections | Share (%) |
|---|---|---|
| `person` | 2,070 | 80.8% |
| `truck` | 476 | 18.6% |
| `car` | 17 | 0.7% |

### Confidence Distribution
- **Mean Confidence**: 0.5396
- **Median Confidence**: 0.5200
- **Detections below 0.50 confidence**: 1,116 (43.54%)

---

## Frontend Optimization & Measured Comparison (After)

Measured on branch `feat/accuracy-v2` after modular architecture refactoring and canvas overlay overhaul.

> [!IMPORTANT]
> All performance numbers in this section are extracted directly from committed raw test outputs:
> - Baseline (Before): [`docs/results/frontend_perf_before.json`](results/frontend_perf_before.json) (measured on worktree at commit `62de537`)
> - Optimized (After): [`docs/results/frontend_perf_after.json`](results/frontend_perf_after.json) (measured on branch `feat/accuracy-v2`)
>
> **Methodology & Equivalence Note**:
> Both versions were tested under identical test conditions: headless Brave browser (`--headless=new`), 300 frames per run, 3 consecutive runs per condition, measuring both unthrottled 1x CPU and 4x CPU throttle via Chrome DevTools Protocol.
>
> In the Before version, the application played the original 1080p source video (`drone_feed.mp4`, 24.6 MB). In the After version, the application played the transcoded 720p web video (`feeds/uav-alpha/video.mp4`, 9.74 MB). The draw timers in both versions specifically measure the end-to-end canvas drawing routine (`clearRect` + keyframe lookup/interpolation + bounding box and label rendering).
>
> Mean boxes drawn per frame was recorded to guarantee the probe does not time an empty canvas; both versions consistently rendered between 1.41 and 1.62 boxes per frame across all runs.

### Static Verification & Quality Gates
- **TypeScript (`tsc --noEmit`)**: Exit code `0` (Zero type errors)
- **ESLint (`eslint src`)**: Exit code `0` (**0 errors, 0 warnings** across entire `frontend/src` codebase, down from 25 problems)
- **Orchestrator Line Budget**: `frontend/src/app/page.tsx` reduced from 1,349 lines down to **345 lines** ($\le 350$ lines budget)
- **Package Manager & Clean Install**: Standardized on `npm`, verified with `npm ci && npm test && npx tsc --noEmit && npx eslint src && npm run build` from a clean state without pre-existing `node_modules`
- **Unit & Integration Tests**: 33 passing Vitest tests in frontend (`npm test`), 13 passing pytest tests in vision (`pytest vision/tests/`)
- **Next.js Production Build (`next build`)**: Succeeded in `26.6s` (Turbopack, Next.js 16.2.11)

### Measured Runtime Performance Comparison

Values show **Median [Min – Max]** across 3 runs of 300 frames each:

#### Normal Playback (1x CPU, 300 Frames)
| Metric | Before (1080p, commit `62de537`) | After (720p, `feat/accuracy-v2`) | Difference |
|---|---|---|---|
| **Mean Canvas Draw Time** | `10.402 ms` [10.106 – 10.989 ms] | `0.426 ms` [0.423 – 0.703 ms] | **~24.4× faster** (-95.9%) |
| **p95 Canvas Tail Draw Time** | `20.000 ms` [16.900 – 22.900 ms] | `0.900 ms` [0.900 – 1.000 ms] | **~22.2× faster** (-95.5%) |
| **Mean Boxes Drawn / Frame** | `1.53` [1.50 – 1.56] | `1.58` [1.55 – 1.60] | Validated non-zero |
| **Total React Commits (Profiler)** | `0` [0 – 0] | `0` [0 – 0] | Identical (0 commits / 100 frames) |
| **300-Frame Playback Duration** | `53.59 s` [53.20 – 53.85 s] (~5.6 fps) | `15.55 s` [15.44 – 15.60 s] (~19.3 fps) | **~3.4× faster headless pace** |

#### Throttled Playback (4x CPU Throttling, 300 Frames)
| Metric | Before (1080p, commit `62de537`) | After (720p, `feat/accuracy-v2`) | Difference |
|---|---|---|---|
| **Mean Canvas Draw Time** | `25.270 ms` [23.543 – 33.746 ms] | `1.842 ms` [1.825 – 1.879 ms] | **~13.7× faster** (-92.7%) |
| **p95 Canvas Tail Draw Time** | `58.200 ms` [57.500 – 61.600 ms] | `6.500 ms` [5.500 – 6.600 ms] | **~9.0× faster** (-88.8%) |
| **Mean Boxes Drawn / Frame** | `1.57` [1.55 – 1.58] | `1.43` [1.41 – 1.45] | Validated non-zero |
| **Total React Commits (Profiler)** | `0` [0 – 0] | `0` [0 – 0] | Identical (0 commits / 100 frames) |
| **300-Frame Playback Duration** | `85.67 s` [84.82 – 90.84 s] (~3.5 fps) | `29.75 s` [29.51 – 30.96 s] (~10.1 fps) | **~2.9× faster headless pace** |

### Analysis of Results
1. **Canvas Draw Speed**:
   Canvas frame drawing dropped from ~10.4 ms to ~0.43 ms unthrottled, and from ~25.3 ms to ~1.84 ms under 4x CPU throttle. This improvement is driven by avoiding canvas dimension resizing on every tick, using binary search on typed array keyframe timestamps, and rendering against a 720p canvas rather than resizing 1080p elements.
2. **React Commits**:
   During steady-state video playback without operator interaction, React commits remain at 0 in both versions because video frame playback is decoupled from React component state cycles. Commits only occur on explicit state changes (feed switching, scrubbing, threat modal opening, or search queries).
3. **Execution Pace**:
   Headless browser frame pacing improved substantially (from ~5.6 fps to ~19.3 fps normal, and from ~3.5 fps to ~10.1 fps throttled), reducing the execution time for 300 frames from ~54s to ~16s normal and from ~86s to ~30s throttled.

*Visual QA Reference captures: `local_assets/shots_after/desktop_1440x900.png` and `local_assets/shots_after/mobile_390x844.png`.*

