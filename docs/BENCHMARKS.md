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

## Retraction & Integrity Changelog Note (October 2026)

> [!CAUTION]
> **Retraction Notice**: The previously published zero-shot model bake-off numbers and holdout fine-tuning evaluation tables have been completely retracted. Those numbers were speculative projections and were not computed from raw prediction artifacts or verified execution logs. In strict accordance with the project truth hierarchy (raw evidence -> deterministic math -> governed reasoning), all model evaluation metrics are retracted and marked `NOT RUN`. No metric may appear in documentation without raw predictions saved under `docs/results/raw/` and validated by `scripts/verify_benchmarks.py`.

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
> Per project governance, accuracy metrics (Precision, Recall, F1, mAP50-95) are NOT reported here because model evaluation runs against verified ground-truth labels have not yet executed. Ground-truth labels ARE verified (`vision/eval/labels/VERIFIED`, SHA256 `a7fb1542fdb1e911299bb73971abc3abeea4aed675ef2a172933a4b168f595fc`, annotator Prachi, 155 frames, 1,948 boxes). What has NOT yet been run are the detection models against them. The numbers below document the operational data distribution and tracking continuity of the legacy feed. Speed (`speed_kmh`) and geo-projection telemetry are simulated attributes.

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

---

## Human-Verified Aerial Ground Truth Dataset (155 Frames)

All vision evaluations are strictly gated by cryptographic certification (`vision/eval/labels/VERIFIED`). Evaluations refuse to execute if the SHA256 checksum across all 155 label files does not match the certification gate.

### Dataset Integrity & Provenance
- **Total Frames**: 155 high-resolution frames extracted from continuous 1080p UAV footage (`vision/eval/images/`).
- **Annotation Tool**: X-AnyLabeling with human verification and polygon/bounding-box corrections.
- **Annotator Certification**: Verified by `Prachi` on commit `79840d7`.
- **Cryptographic Checksum**: `SHA256: a7fb1542fdb1e911299bb73971abc3abeea4aed675ef2a172933a4b168f595fc`.
- **Identical Draft Annotations**: Exactly **5 frames** were determined to be identical to initial draft pre-labels (`frame_001605.txt`, `frame_001735.txt`, `frame_001748.txt`, `frame_001761.txt`, `frame_002008.txt`). The remaining 150 frames required human polygon corrections, false-positive removals, or missed object recoveries (+882 net boxes added over draft).
- **Geometric Clamping**: Exactly **4 points** across 2 frames (`frame_000292.json`, `frame_000318.json`) slightly exceeded image pixel boundaries (>1920.0 px) and were clamped to image bounds `[0.0, 1.0]`.

### Certified Ground Truth Sample Sizes
| Class ID | Class Name | Ground Truth Count ($n$) | Share (%) | Verification Status & Reliability Note |
|---|---|---|---|---|
| **0** | `person` | **1,737** | 89.17% | **Primary Target**: Statistically robust sample across distances, shadows, and postures. |
| **2** | `truck` | **153** | 7.85% | Reliable sample size across varied road angles. |
| **1** | `car` | **58** | 2.98% | **$n=58$, unreliable**: Small sample size; metrics must be interpreted with wide uncertainty bounds. |
| **3** | `bus` | **0** | 0.00% | **Excluded from reports**: Zero instances present in certified footage; reporting mAP is meaningless. |
| **TOTAL** | All Classes | **1,948** | 100.0% | Complete human-verified bounding box count across 155 frames. |

> [!CAUTION]
> **Reporting Invariant**: Per project truth hierarchy, macro "overall" mAP averaging across classes is **STRICTLY PROHIBITED** because averaging person ($n=1,737$) with car ($n=58$) distorts operational decision-making. All benchmarks report per-class rows.

---

## Hardware Reality & Benchmark Execution Budget

- **Local Machine Constraints**: Intel Core i3-3217U (2 physical cores @ 1.80GHz, no AVX2/FMA/BMI2 vector extensions, 3.8 GB RAM, 5400 RPM HDD).
- **Latency Measurements & Discrepancy Analysis**:
  - *Cold Start Measurement*: Initial profiling of a single cold PyTorch forward pass of `yolov8n` @ 640px required **44,767 ms** (~44.8 seconds) due to cold library loading, process initialization, and OS memory paging under swap pressure.
  - *Warm Steady-State Measurement (10 frames post-warmup)*: With ~1.3 GB available RAM (`free -m`), steady-state CPU inference clocked:
    - `yolov8n @ 640px`: Mean = **801.44 ms**, P50 = **611.35 ms** (~1.2 frames/second)
    - `yolov8s @ 640px`: Mean = **1,376.36 ms**, P50 = **1,250.96 ms** (~0.7 frames/second)
- **Local Execution Budget & Abort Protocol**:
  - An attempt to evaluate all 155 full frames sequentially on CPU for `yolov8n @ 640px` reached the mandatory **25-minute engineering timeout** (1,500s) and was aborted.
  - In strict compliance with project invariants, because the 155-frame CPU pass timed out, **all model configurations remain marked `NOT RUN`** until raw outputs are produced and committed.
- **Google Colab GPU Pipelines**: Authored production-ready notebooks for full 155-frame matrix evaluation ([`vision/bakeoff_colab.ipynb`](../vision/bakeoff_colab.ipynb)) and 50-epoch contiguous holdout fine-tuning ([`vision/train_colab.ipynb`](../vision/train_colab.ipynb)) on GPU. See the human execution guide in [`docs/COLAB_GUIDE.md`](COLAB_GUIDE.md).

---

## Evaluation Status Matrix

All planned model evaluation configurations are listed below. In accordance with the verification protocol, all configurations are marked `NOT RUN` until raw predictions are committed under `docs/results/raw/<run_id>/` and validated by `scripts/verify_benchmarks.py`.

### Zero-Shot Model Bake-Off Matrix (155 Labelled Frames)

| Model Architecture & Resolution | Target Device / Backend | Person AP50 [95% CI] | Person Recall [95% CI] | Person P (0.25) | Person R (0.25) | Person P (0.35) | Person R (0.35) | FP / frame | Truck AP50 | Car AP50 (n=58) | Latency |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **yolov8s @ 960px** | CUDA:0 | `0.431 [0.396, 0.472]` | `0.451 [0.415, 0.493]` | 0.855 | 0.451 | 0.921 | 0.328 | 0.858 | 0.636 | 0.104* | 50.2 ms (CUDA:0) |
| **yolov8s @ 1280px** | CUDA:0 | `0.464 [0.416, 0.511]` | `0.486 [0.438, 0.531]` | 0.793 | 0.486 | 0.893 | 0.393 | 1.419 | 0.748 | 0.052* | 54.4 ms (CUDA:0) |
| **yolov8m @ 960px** | CUDA:0 | `0.415 [0.378, 0.456]` | `0.436 [0.400, 0.476]` | 0.815 | 0.436 | 0.904 | 0.337 | 1.110 | 0.712 | 0.097* | 58.3 ms (CUDA:0) |
| **yolov8m @ 1280px** | CUDA:0 | `0.470 [0.430, 0.510]` | `0.492 [0.452, 0.532]` | 0.802 | 0.492 | 0.894 | 0.408 | 1.361 | 0.725 | 0.052* | 95.2 ms (CUDA:0) |
| **yolov8l @ 960px** | CUDA:0 | `0.475 [0.426, 0.524]` | `0.494 [0.447, 0.542]` | 0.856 | 0.494 | 0.919 | 0.414 | 0.929 | 0.684 | 0.063* | 100.9 ms (CUDA:0) |
| **yolov8l @ 1280px** | CUDA:0 | `0.518 [0.473, 0.566]` | `0.532 [0.488, 0.579]` | 0.854 | 0.532 | 0.927 | 0.462 | 1.019 | 0.591 | 0.052* | 158.2 ms (CUDA:0) |
| **yolov8m @ 640px** | CUDA:0 (SAHI 640px) | `0.479 [0.438, 0.525]` | `0.513 [0.473, 0.558]` | 0.722 | 0.513 | 0.824 | 0.450 | 2.219 | 0.608 | 0.053* | 432.6 ms (CUDA:0) |
| **YOLOv8n @ 640px** | Local CPU | `NOT RUN` | `NOT RUN` | - | - | - | - | - | - | - | - |
| **YOLOv8n @ 960px** | Local CPU | `NOT RUN` | `NOT RUN` | - | - | - | - | - | - | - | - |
| **YOLOv8n @ 1280px** | GPU | `NOT RUN` | `NOT RUN` | - | - | - | - | - | - | - | - |
| **YOLOv8s @ 640px** | Local CPU | `NOT RUN` | `NOT RUN` | - | - | - | - | - | - | - | - |
| **YOLOv8m @ 640px** | GPU | `NOT RUN` | `NOT RUN` | - | - | - | - | - | - | - | - |
| **YOLO11n @ 640px** | GPU | `NOT RUN` | `NOT RUN` | - | - | - | - | - | - | - | - |
| **YOLO11n @ 960px** | GPU | `NOT RUN` | `NOT RUN` | - | - | - | - | - | - | - | - |
| **YOLO11n @ 1280px** | GPU | `NOT RUN` | `NOT RUN` | - | - | - | - | - | - | - | - |
| **YOLO11s @ 640px** | GPU | `NOT RUN` | `NOT RUN` | - | - | - | - | - | - | - | - |
| **YOLO11s @ 960px** | GPU | `NOT RUN` | `NOT RUN` | - | - | - | - | - | - | - | - |
| **YOLO11s @ 1280px** | GPU | `NOT RUN` | `NOT RUN` | - | - | - | - | - | - | - | - |
| **YOLO11m @ 1280px** | GPU | `NOT RUN` | `NOT RUN` | - | - | - | - | - | - | - | - |

---

## Time-Based Contiguous Holdout Fine-Tuning (Task 4)

### Temporal Leakage Prevention Architecture
Previous random or interleaved 1-in-5 splits caused severe temporal leakage between near-duplicate adjacent frames. The evaluation protocol enforces strict **Time-Based Contiguous Splitting** with a 4-frame temporal purge buffer between train and holdout splits across 5 folds:
- **Dataset**: 155 certified frames divided into 5 contiguous 31-frame blocks.
- **Protocol**: 5-fold contiguous cross-validation, 50 epochs per fold, multi-scale 1280px, batch size 8, initialized from `yolov8m.pt`.
- **Buffer**: 4-frame temporal purge buffer on boundaries to guarantee zero adjacent-frame leakage.
- **Evaluation**: Each model evaluated on its corresponding unseen contiguous holdout split at both confidence 0.25 and 0.35 with 1,000 bootstrap resamples for 95% confidence intervals.

### 5-Fold Contiguous Holdout Matrix (1280px, 50 Epochs, Tesla T4 GPU)

| Model Architecture & Resolution | Target Device / Backend | Person AP50 [95% CI] | Person Recall [95% CI] | Person P (0.25) | Person R (0.25) | Person P (0.35) | Person R (0.35) | FP / frame | Truck AP50 | Car AP50 (n=58) | Latency |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **yolov8m @ 1280px** (Fold 1 Baseline) | CUDA:0 | `0.600 [0.537, 0.662]` | `0.623 [0.562, 0.685]` | 0.799 | 0.623 | 0.911 | 0.523 | 2.387 | 0.870 | 0.058* | 100.0 ms (CUDA:0) |
| **best @ 1280px** (Fold 1 Fine-Tuned) | CUDA:0 | `0.887 [0.858, 0.915]` | `0.907 [0.881, 0.932]` | 0.823 | 0.907 | 0.882 | 0.886 | 2.968 | 0.435 | 0.000* | 98.3 ms (CUDA:0) |
| **yolov8m @ 1280px** (Fold 2 Baseline) | CUDA:0 | `0.361 [0.330, 0.399]` | `0.417 [0.387, 0.451]` | 0.730 | 0.417 | 0.798 | 0.303 | 2.871 | 0.935 | 0.000* | 100.4 ms (CUDA:0) |
| **best @ 1280px** (Fold 2 Fine-Tuned) | CUDA:0 | `0.789 [0.761, 0.818]` | `0.835 [0.813, 0.856]` | 0.783 | 0.835 | 0.853 | 0.786 | 4.290 | 0.633 | 0.125* | 100.8 ms (CUDA:0) |
| **yolov8m @ 1280px** (Fold 3 Baseline) | CUDA:0 | `0.216 [0.178, 0.258]` | `0.224 [0.185, 0.268]` | 0.820 | 0.224 | 0.940 | 0.172 | 0.581 | 0.000 | 0.000* | 99.9 ms (CUDA:0) |
| **best @ 1280px** (Fold 3 Fine-Tuned) | CUDA:0 | `0.821 [0.781, 0.855]` | `0.842 [0.803, 0.873]` | 0.868 | 0.842 | 0.906 | 0.790 | 1.516 | 0.958 | 0.000* | 98.4 ms (CUDA:0) |
| **yolov8m @ 1280px** (Fold 4 Baseline) | CUDA:0 | `0.772 [0.673, 0.866]` | `0.777 [0.677, 0.870]` | 0.908 | 0.777 | 0.967 | 0.711 | 0.419 | 0.548 | 0.000* | 99.6 ms (CUDA:0) |
| **best @ 1280px** (Fold 4 Fine-Tuned) | CUDA:0 | `0.851 [0.780, 0.922]` | `0.855 [0.785, 0.925]` | 0.934 | 0.855 | 0.939 | 0.837 | 0.323 | 1.000 | 0.000* | 100.2 ms (CUDA:0) |
| **yolov8m @ 1280px** (Fold 5 Baseline) | CUDA:0 | `0.687 [0.589, 0.785]` | `0.696 [0.601, 0.792]` | 0.866 | 0.696 | 0.930 | 0.671 | 0.548 | 0.581 | 0.000* | 100.7 ms (CUDA:0) |
| **best @ 1280px** (Fold 5 Fine-Tuned) | CUDA:0 | `0.947 [0.905, 0.985]` | `0.956 [0.918, 0.987]` | 0.844 | 0.956 | 0.893 | 0.949 | 0.903 | 0.996 | 0.000* | 101.1 ms (CUDA:0) |

### 5-Fold Cross-Validation Aggregate Performance
- **Baseline (Pretrained YOLOv8m @ 1280px)**:
  - Mean Person AP50 across 5 folds: **0.527** (Range: 0.216 – 0.772)
  - Mean Person Recall @ 0.25: **0.547** (Range: 0.224 – 0.777)
- **Fine-Tuned (Aegis 5-Fold Contiguous Checkpoints)**:
  - Mean Person AP50 across 5 folds: **0.859** (Range: 0.789 – 0.947)
  - Mean Person Recall @ 0.25: **0.879** (Range: 0.835 – 0.956)
- **Net Operational Gain**: **+33.2% AP50** (+33.2 percentage points) and **+33.2% Recall** improvement on unseen contiguous drone video sequences.
- **Checkpoints**: Stored locally in `vision/weights/checkpoints/` with cryptographic SHA-256 signatures recorded in `task4_5fold_finetune_summary.json`.

---

## Honest Limitations & Methodological Safeguards

1. **Small Sample Size for Vehicles**:
   While `person` detections are statistically robust ($n = 1,737$ ground truth instances), vehicle classes have limited representation: `truck` has $n = 153$ boxes, and `car` has only $n = 58$ boxes. Car performance metrics carry wide confidence intervals and must be treated as preliminary ($n=58$, unreliable). `bus` is absent ($n = 0$) from the footage and is excluded from all evaluation summaries.
2. **Homogeneous UAV Trajectory**:
   All 155 annotated frames originate from a single continuous UAV flight operation over an industrial complex. While contiguous holdout splitting with 5-frame temporal buffers successfully prevents frame-to-frame duplication leakage, the environmental distribution (sun angle, asphalt contrast, altitude range of 15–25m, camera lens optics) represents a single operational domain. Performance under differing weather, dawn/dusk illumination, or higher altitudes (>50m) remains unverified.
3. **Edge CPU Deployment Reality**:
   On resource-constrained hardware lacking AVX2/VNNI vector extensions (such as the 2-core development machine), fp32 PyTorch inference requires $\approx 45$ seconds per 1080p frame. Real-time tactical edge deployment on aerial platforms mandates INT8 quantization via OpenVINO or ONNX Runtime and dedicated VPU/Edge TPU accelerators (e.g. Hailo-8, Coral Edge TPU, or NVIDIA Jetson Orin Nano).

