#!/usr/bin/env node
const { chromium } = require('@playwright/test');
const path = require('path');
const fs = require('fs');

async function measureSingleRun(browser, { port = 3001, throttled = false, targetFrames = 300, runIdx = 1 }) {
  console.log(`  -> Starting run #${runIdx} (${throttled ? '4x Throttled' : '1x Normal'}, ${targetFrames} frames)...`);
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  try {
    if (throttled) {
      const client = await page.context().newCDPSession(page);
      await client.send('Emulation.setCPUThrottlingRate', { rate: 4 });
    }

    await page.goto(`http://localhost:${port}/?perf=1&frames=${targetFrames}`, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('video', { timeout: 30000 });

    const playInterval = setInterval(async () => {
      try {
        await page.evaluate(() => {
          const v = document.querySelector('video');
          if (v && v.paused) {
            v.muted = true;
            v.play().catch(() => {});
          }
        });
      } catch (_) {}
    }, 500);

    const progressTimer = setInterval(async () => {
      try {
        const info = await page.evaluate(() => ({
          frames: window.__AEGIS_PERF_FRAMES__ || 0,
          commits: window.__AEGIS_REACT_COMMITS__ || 0,
          time: document.querySelector('video')?.currentTime,
          paused: document.querySelector('video')?.paused,
        }));
        process.stdout.write(`    [Progress] frames: ${info.frames}/${targetFrames}, time: ${info.time?.toFixed(1) || 0}s, paused: ${info.paused}\r`);
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
      { timeout: 300000 }
    );

    clearInterval(progressTimer);
    clearInterval(playInterval);
    console.log(''); // newline after progress
    const report = await reportHandle.jsonValue();

    if (!report) {
      throw new Error('No performance report returned from page');
    }
    if (report.status === 'FAIL_ZERO_BOXES' || report.mean_boxes === 0) {
      throw new Error(`Probe FAILED: mean boxes drawn per frame is ${report.mean_boxes} (status: ${report.status})`);
    }

    console.log(`    Result #${runIdx}: mean=${report.mean_draw_ms}ms, p95=${report.p95_draw_ms}ms, boxes=${report.mean_boxes}, commits/100f=${report.commits_per_100_frames}, dur=${report.duration_sec}s`);
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
  console.log('AEGIS BENCHMARK RUNNER: AFTER STATE (modular rVFC canvas overlay)');
  console.log(`Target: http://localhost:${port}`);
  console.log(`Frames per run: ${targetFrames} | Runs per condition: ${numRuns}`);
  console.log('Video Source: 720p feeds/uav-alpha/video.mp4');
  console.log('================================================================');

  const outShots = path.join(__dirname, '..', 'local_assets', 'shots_after');
  fs.mkdirSync(outShots, { recursive: true });

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

  // Capture fresh verification screenshots
  console.log('\nCapturing screenshots at 1440x900 and 390x844...');
  {
    const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
    await page.goto(`http://localhost:${port}`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2000);
    await page.screenshot({ path: path.join(outShots, 'desktop_1440x900.png'), fullPage: false });
    console.log('  Saved 1440x900 screenshot.');
    await page.close();
  }
  {
    const page = await browser.newPage({ viewport: { width: 390, height: 844 }, isMobile: true });
    await page.goto(`http://localhost:${port}`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2000);
    await page.screenshot({ path: path.join(outShots, 'mobile_390x844.png'), fullPage: false });
    console.log('  Saved 390x844 screenshot.');
    await page.close();
  }

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
      version: 'after (feat/accuracy-v2 modular)',
      video_source: '720p feeds/uav-alpha/video.mp4',
      target_frames: targetFrames,
      runs_per_condition: numRuns,
      measured_at: new Date().toISOString(),
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
  const outFile = path.join(outDir, 'frontend_perf_after.json');
  fs.writeFileSync(outFile, JSON.stringify(payload, null, 2));

  console.log('\n================================================================');
  console.log('AFTER BENCHMARK COMPLETE');
  console.log(`Saved raw results to: ${outFile}`);
  console.log('Normal 1x Stats:', JSON.stringify(normalStats, null, 2));
  console.log('4x Throttled Stats:', JSON.stringify(throttledStats, null, 2));
  console.log('================================================================');
}

run().catch((err) => {
  console.error('\nBenchmark failed:', err);
  process.exit(1);
});
