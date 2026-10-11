#!/usr/bin/env node
const { chromium } = require('@playwright/test');
const path = require('path');
const fs = require('fs');

async function verifyPositiveControlBefore(browser, port) {
  console.log('\n================================================================');
  console.log('[Positive Control Check] Verifying React Profiler commit counter (BEFORE)...');
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  try {
    await page.goto(`http://localhost:${port}/?perf=1&frames=300`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2000);

    const initialCommits = await page.evaluate(() => window.__AEGIS_REACT_COMMITS__ || 0);
    console.log(`  Initial commits at load: ${initialCommits}`);
    if (initialCommits === 0) {
      throw new Error('POSITIVE CONTROL FAILED: window.__AEGIS_REACT_COMMITS__ is 0. React Profiler is stripped or disabled in build!');
    }

    // Trigger state change in BEFORE (e.g. click video to toggle play/pause or click a tab)
    const clicked = await page.evaluate(() => {
      const v = document.querySelector('video');
      if (v) {
        v.click();
        return true;
      }
      return false;
    });
    if (!clicked) {
      throw new Error('Could not find video element to trigger click event');
    }
    await page.waitForTimeout(500);

    let afterCommits = await page.evaluate(() => window.__AEGIS_REACT_COMMITS__ || 0);
    console.log(`  Commits after clicking video element: ${afterCommits}`);
    if (afterCommits <= initialCommits) {
      // Try clicking a button
      await page.evaluate(() => {
        const btn = document.querySelector('button');
        if (btn) btn.click();
      });
      await page.waitForTimeout(500);
      afterCommits = await page.evaluate(() => window.__AEGIS_REACT_COMMITS__ || 0);
      console.log(`  Commits after clicking button: ${afterCommits}`);
    }

    if (afterCommits <= initialCommits) {
      throw new Error(`POSITIVE CONTROL FAILED: commits did not increase after state change (before: ${initialCommits}, after: ${afterCommits})`);
    }

    console.log('  -> POSITIVE CONTROL PASSED: React Profiler successfully tracks state transitions in BEFORE.');
    console.log('================================================================\n');

    return { initialCommits, afterCommits };
  } finally {
    await page.close();
  }
}

async function measureSingleRun(browser, { port = 3001, throttled = false, targetFrames = 300, runIdx = 1 }) {
  console.log(`  -> Starting run #${runIdx} (${throttled ? '4x Throttled' : '1x Normal'}, ${targetFrames} frames)...`);
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  try {
    if (throttled) {
      const client = await page.context().newCDPSession(page);
      await client.send('Emulation.setCPUThrottlingRate', { rate: 4 });
    }

    await page.goto(`http://localhost:${port}/?perf=1&frames=${targetFrames}`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(1000);

    await page.evaluate(async () => {
      const v = document.querySelector('video');
      if (v) {
        v.muted = true;
        try { await v.play(); } catch (_) {}
      }
    });

    const progressTimer = setInterval(async () => {
      try {
        const info = await page.evaluate(() => ({
          frames: window.__AEGIS_PERF_FRAMES__ || 0,
          commits: window.__AEGIS_REACT_COMMITS__ || 0,
          time: document.querySelector('video')?.currentTime,
          paused: document.querySelector('video')?.paused,
        }));
        process.stdout.write(`    [Progress] frames: ${info.frames}/${targetFrames}, time: ${info.time?.toFixed(1) || 0}s\r`);
      } catch (_) {}
    }, 2000);

    const reportHandle = await page.waitForFunction(
      () => {
        if (window.__AEGIS_PERF_DONE__ === true) {
          return window.__AEGIS_PERF_REPORT__;
        }
        return false;
      },
      null,
      { timeout: 240000 }
    );

    clearInterval(progressTimer);
    console.log(''); // newline after progress
    const report = await reportHandle.jsonValue();

    if (!report) {
      throw new Error('No performance report returned from page');
    }
    if (report.status === 'FAIL_PROFILER_DISABLED') {
      throw new Error('Probe FAILED: React Profiler was not active (status: FAIL_PROFILER_DISABLED)');
    }
    if (report.status === 'FAIL_ZERO_BOXES' || report.mean_boxes === 0) {
      throw new Error(`Probe FAILED: mean boxes drawn per frame is ${report.mean_boxes} (status: ${report.status})`);
    }

    console.log(`    Result #${runIdx}: mean=${report.mean_draw_ms}ms, p95=${report.p95_draw_ms}ms, boxes=${report.mean_boxes}, commits=${report.total_commits} (${report.commits_per_100_frames}/100f), dur=${report.duration_sec}s`);
    return report;
  } finally {
    await page.close();
  }
}

function computeStats(runs) {
  function getRange(key) {
    const sorted = runs.map(r => r[key]).sort((a, b) => a - b);
    const min = sorted[0];
    const max = sorted[sorted.length - 1];
    const median = sorted[Math.floor(sorted.length / 2)];
    return {
      median: Number(median.toFixed(3)),
      min: Number(min.toFixed(3)),
      max: Number(max.toFixed(3)),
      values: sorted,
    };
  }

  return {
    mean_draw_ms: getRange('mean_draw_ms'),
    p95_draw_ms: getRange('p95_draw_ms'),
    mean_boxes: getRange('mean_boxes'),
    total_commits: getRange('total_commits'),
    commits_per_100_frames: getRange('commits_per_100_frames'),
    duration_sec: getRange('duration_sec'),
  };
}

async function run() {
  const browserPath = '/usr/bin/brave-browser';
  const port = process.env.PORT ? parseInt(process.env.PORT, 10) : 3001;
  const targetFrames = 300;
  const numRuns = 3;

  console.log('================================================================');
  console.log('AEGIS BENCHMARK RUNNER: BEFORE STATE (commit 62de537)');
  console.log(`Target: http://localhost:${port}`);
  console.log(`Frames per run: ${targetFrames} | Runs per condition: ${numRuns}`);
  console.log('Video Source: 1080p drone_feed.mp4');
  console.log('Note: Timer covers old per-tick handler (per-frame overlay cost)');
  console.log('================================================================');

  const browser = await chromium.launch({
    executablePath: browserPath,
    headless: false,
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--headless=new',
      '--autoplay-policy=no-user-gesture-required',
    ],
  });

  // Verify positive control
  const controlResult = await verifyPositiveControlBefore(browser, port);

  const normalRuns = [];
  console.log('\n[Condition 1/2] Normal 1x Playback (3 runs):');
  for (let i = 1; i <= numRuns; i++) {
    const res = await measureSingleRun(browser, { port, throttled: false, targetFrames, runIdx: i });
    normalRuns.push(res);
  }

  const throttledRuns = [];
  console.log('\n[Condition 2/2] 4x CPU Throttled Playback (3 runs):');
  for (let i = 1; i <= numRuns; i++) {
    const res = await measureSingleRun(browser, { port, throttled: true, targetFrames, runIdx: i });
    throttledRuns.push(res);
  }

  await browser.close();

  const normalStats = computeStats(normalRuns);
  const throttledStats = computeStats(throttledRuns);

  const payload = {
    metadata: {
      version: 'before (commit 62de537)',
      video_source: '1080p drone_feed.mp4',
      resolution: '1080p',
      target_frames: targetFrames,
      runs_per_condition: numRuns,
      measured_at: new Date().toISOString(),
      positive_control: {
        status: 'PASSED',
        initial_commits: controlResult.initialCommits,
        commits_after_state_change: controlResult.afterCommits,
      },
    },
    normal: {
      stats: normalStats,
      runs: normalRuns,
    },
    cpu_throttled_4x: {
      stats: throttledStats,
      runs: throttledRuns,
    },
  };

  const outDir = path.join(__dirname, '..', 'docs', 'results');
  fs.mkdirSync(outDir, { recursive: true });
  const outFile = path.join(outDir, 'frontend_perf_before.json');
  fs.writeFileSync(outFile, JSON.stringify(payload, null, 2));

  console.log('\n================================================================');
  console.log('BEFORE BENCHMARK COMPLETE');
  console.log(`Saved raw results to: ${outFile}`);
  console.log('Normal 1x Stats:', JSON.stringify(normalStats, null, 2));
  console.log('4x Throttled Stats:', JSON.stringify(throttledStats, null, 2));
  console.log('================================================================');
}

run().catch((err) => {
  console.error('\nBenchmark failed:', err);
  process.exit(1);
});
