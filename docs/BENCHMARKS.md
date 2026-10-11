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
> - Baseline (Before 1080p): [`docs/results/frontend_perf_before.json`](results/frontend_perf_before.json) (commit `62de537`, 1080p source)
> - Same-Resolution Control (After 1080p): [`docs/results/frontend_perf_after_1080p.json`](results/frontend_perf_after_1080p.json) (`feat/accuracy-v2`, 1080p source)
> - Web Delivery Build (After 720p): [`docs/results/frontend_perf_after.json`](results/frontend_perf_after.json) (`feat/accuracy-v2`, 720p web source)
>
> **Methodology, Metric Definition & Positive Control**:
> - **Production Profiling**: All runs were executed against production builds compiled with `next build --profile`, ensuring React `<Profiler>` callbacks are preserved under `next start`.
> - **Positive Control Gate**: Before running any 300-frame test, the runner asserts that `window.__AEGIS_REACT_COMMITS__ > 0` upon hydration, triggers an interactive state change (e.g. LITE mode toggle or play/pause), and asserts that commit count increases. The probe fails immediately if commits read 0 or do not increase.
> - **Metric Definition**: The "Before" timer wrapped the legacy per-tick handler (`handleTimeUpdateRef.current()`), encompassing `console.log` serializations, binary search, canvas dimension resets (`canvas.width = video.clientWidth`), coordinate scaling, and box drawing. The Before metric thus represents **per-frame overlay cost**, not just isolated box rasterization. In the After version, `useVideoOverlay` eliminates per-frame canvas resizing, uses binary search over typed keyframes, and wraps `clearRect` + `sampleAt` + `drawDetections` in `onDrawTiming`.
> - **Testing Conditions**: Headless Brave browser (`--headless=new`), 300 frames per run, 3 consecutive runs per condition, measuring both normal 1x CPU and 4x CPU throttle via Chrome DevTools Protocol.

### Static Verification & Quality Gates
- **TypeScript (`tsc --noEmit`)**: Exit code `0` (Zero type errors)
- **ESLint (`eslint src`)**: Exit code `0` (**0 errors, 0 warnings** across entire `frontend/src` codebase, down from 25 problems)
- **Orchestrator Line Budget**: `frontend/src/app/page.tsx` reduced from 1,349 lines down to **345 lines** ($\le 350$ lines budget)
- **Package Manager & Clean Install**: Standardized on `npm`, verified with `npm ci && npm test && npx tsc --noEmit && npx eslint src && npm run build` from a clean state without pre-existing `node_modules`
- **Unit & Integration Tests**: 33 passing Vitest tests in frontend (`npm test`), 13 passing pytest tests in vision (`pytest vision/tests/`)
- **Next.js Production Build (`next build`)**: Succeeded in `26.6s` (Turbopack, Next.js 16.2.11)

---

### Same-Resolution Comparison (1080p Source Video)

Both Before (`62de537`) and After (`feat/accuracy-v2`) tested playing the identical 1080p source video (`vision/source/drone_feed.mp4`, 1920×1080, 24.6 MB).

Values show **Median [Min – Max]** across 3 runs of 300 frames:

#### Normal Playback (1x CPU, 1080p Source, 300 Frames)
| Metric | Before (`62de537`, 1080p) | After Control (`feat/accuracy-v2`, 1080p) | Comparison |
|---|---|---|---|
| **Mean Per-Frame Overlay Cost** | `9.219 ms` [9.091 – 9.934 ms] | `0.566 ms` [0.528 – 5.059 ms] | **~16.3× faster** (-93.9%) |
| **p95 Tail Overlay Cost** | `17.800 ms` [17.800 – 19.700 ms] | `1.800 ms` [1.600 – 3.600 ms] | **~9.9× faster** (-89.9%) |
| **Mean Boxes Drawn / Frame** | `1.56` [1.54 – 1.57] | `1.59` [1.30 – 1.59] | Validated non-zero |
| **Total React Commits (Profiler)** | `463` [459 – 467] | `99` [89 – 165] | **~4.7× fewer commits** (-78.6%) |
| **Commits per 100 Frames** | `154.33` [153.00 – 155.67] | `33.00` [29.67 – 55.00] | -78.6% React commit pressure |
| **300-Frame Playback Duration** | `60.64 s` [59.19 – 61.15 s] (~4.9 fps) | `26.47 s` [24.19 – 53.73 s] (~11.3 fps) | **~2.3× faster pace** |

#### Throttled Playback (4x CPU Throttling, 1080p Source, 300 Frames)
| Metric | Before (`62de537`, 1080p) | After Control (`feat/accuracy-v2`, 1080p) | Comparison |
|---|---|---|---|
| **Mean Per-Frame Overlay Cost** | `21.905 ms` [18.392 – 22.881 ms] | `1.939 ms` [1.848 – 2.215 ms] | **~11.3× faster** (-91.1%) |
| **p95 Tail Overlay Cost** | `54.100 ms` [52.200 – 64.200 ms] | `6.200 ms` [5.800 – 7.100 ms] | **~8.7× faster** (-88.5%) |
| **Mean Boxes Drawn / Frame** | `1.57` [1.49 – 1.58] | `1.41` [1.38 – 1.43] | Validated non-zero |
| **Total React Commits (Profiler)** | `382` [332 – 428] | `181` [181 – 186] | **~2.1× fewer commits** (-52.6%) |
| **Commits per 100 Frames** | `127.33` [110.67 – 142.67] | `60.33` [60.33 – 62.00] | -52.6% React commit pressure |
| **300-Frame Playback Duration** | `119.57 s` [116.73 – 121.36 s] (~2.5 fps) | `63.95 s` [62.63 – 68.18 s] (~4.7 fps) | **~1.9× faster pace** |

---

### Web Delivery Build (720p Transcoded Video)

Measured on branch `feat/accuracy-v2` playing the optimized 720p web video (`feeds/uav-alpha/video.mp4`, 1280×720, 9.74 MB):

| Metric | Normal 1x CPU (720p) | 4x CPU Throttling (720p) |
|---|---|---|
| **Mean Canvas Draw Time** | `0.466 ms` [0.369 – 0.486 ms] | `1.693 ms` [1.664 – 1.719 ms] |
| **p95 Tail Draw Time** | `0.900 ms` [0.800 – 1.100 ms] | `5.700 ms` [5.500 – 6.100 ms] |
| **Mean Boxes Drawn / Frame** | `1.57` [1.56 – 1.59] | `1.44` [1.43 – 1.49] |
| **Total React Commits (Profiler)** | `59` [57 – 60] | `159` [156 – 161] |
| **Commits per 100 Frames** | `19.67` [19.00 – 20.00] | `53.00` [52.00 – 53.67] |
| **300-Frame Playback Duration** | `15.61 s` [15.17 – 15.75 s] (~19.2 fps) | `52.04 s` [51.76 – 53.83 s] (~5.8 fps) |

---

### Analysis of Results
1. **Per-Frame Overlay Cost at 1080p**:
   When holding resolution constant at 1080p, per-frame overlay cost dropped from 9.22 ms to 0.57 ms under normal CPU (a ~16.3× speedup) and from 21.91 ms to 1.94 ms under 4x CPU throttle (a ~11.3× speedup). This demonstrates that the architectural optimizations (removing repetitive canvas dimension mutations, pre-indexing keyframe observations, and eliminating console serialization) yield substantial per-frame savings independent of resolution.
2. **React Commit Pressure**:
   Under production profiling (`--profile`), React commits dropped from 463 to 99 commits per 300 frames at 1080p normal (-78.6%), and from 382 to 181 commits under 4x throttle (-52.6%). In the Before architecture, `handleTimeUpdate` triggered frequent re-renders through per-tick updates and video element handlers. In the modular architecture, canvas rendering is handled directly via `useVideoOverlay`, with React commits primarily reflecting real state events (e.g. threat evaluation triggers, UI controls).
3. **Playback Pace & Resolution Impact**:
   At the same 1080p resolution, headless playback duration decreased from 60.6 s to 26.5 s normal (~2.3× faster pace) and from 119.6 s to 64.0 s throttled (~1.9× faster pace). Transcoding to the 720p web delivery asset further reduces decode overhead and payload size (from 24.6 MB down to 9.74 MB), bringing 300-frame duration down to 15.6 s normal (~19.2 fps) and mean draw time to 0.47 ms.

*Visual QA Reference captures: `local_assets/shots_after/desktop_1440x900.png` and `local_assets/shots_after/mobile_390x844.png`.*
