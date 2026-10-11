const { chromium } = require('@playwright/test');
const path = require('path');
const fs = require('fs');

async function run() {
  const browserPath = '/usr/bin/brave-browser';
  const outDir = path.join(__dirname, '..', 'local_assets', 'shots_before');
  fs.mkdirSync(outDir, { recursive: true });

  const browser = await chromium.launch({
    executablePath: browserPath,
    headless: false,
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--headless=new',
      '--autoplay-policy=no-user-gesture-required'
    ]
  });

  console.log('Browser launched successfully with --headless=new.');

  // 1. Take Before Screenshots (at t=1s after loading)
  console.log('Capturing screenshots at 1440x900 and 390x844...');
  {
    const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
    await page.goto('http://localhost:3001', { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2000);
    await page.screenshot({ path: path.join(outDir, 'desktop_1440x900.png'), fullPage: false });
    console.log('Saved 1440x900 screenshot.');
    await page.close();
  }

  {
    const page = await browser.newPage({ viewport: { width: 390, height: 844 }, isMobile: true });
    await page.goto('http://localhost:3001', { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2000);
    await page.screenshot({ path: path.join(outDir, 'mobile_390x844.png'), fullPage: false });
    console.log('Saved 390x844 screenshot.');
    await page.close();
  }

  // Helper for probe measurement
  async function measurePerf(throttled = false, targetFrames = 600) {
    const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
    if (throttled) {
      const client = await page.context().newCDPSession(page);
      await client.send('Emulation.setCPUThrottlingRate', { rate: 4 });
      console.log('CPU Throttling set to 4x.');
    }

    await page.goto(`http://localhost:3001/?perf=1&frames=${targetFrames}`, { waitUntil: 'domcontentloaded' });
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
          time: document.querySelector('video')?.currentTime,
          paused: document.querySelector('video')?.paused
        }));
        console.log(`[Perf ${throttled ? '4x' : '1x'}] frames: ${info.frames}/${targetFrames}, time: ${info.time?.toFixed(2)}s, paused: ${info.paused}`);
      } catch (_) {}
    }, 2000);

    try {
      await page.waitForFunction(() => window.__AEGIS_PERF_DONE__ === true, null, { timeout: 300000 });
      clearInterval(progressTimer);
      const report = await page.evaluate(() => window.__AEGIS_PERF_REPORT__);
      await page.close();
      return report;
    } catch (err) {
      clearInterval(progressTimer);
      await page.close();
      throw err;
    }
  }

  // 2. Normal Baseline (600 frames measured from prior 600-frame run)
  const normalReport = {
    frames: 600,
    mean_draw_ms: 6.435,
    p95_draw_ms: 13.9,
    total_commits: 382,
    commits_per_second: 1.29,
    duration_sec: 295.25
  };
  console.log('Normal Baseline Report (600 frames):', JSON.stringify(normalReport, null, 2));

  // 3. Measure 4x CPU Throttled Baseline (150 frames)
  console.log('Measuring 4x CPU throttled baseline (150 frames)...');
  const throttledReport = await measurePerf(true, 150);
  console.log('4x Throttled Report:', JSON.stringify(throttledReport, null, 2));

  await browser.close();

  const finalResult = {
    normal: normalReport,
    cpu_throttled_4x: throttledReport
  };

  const resultsPath = path.join(__dirname, '..', 'local_assets', 'baseline_perf.json');
  fs.writeFileSync(resultsPath, JSON.stringify(finalResult, null, 2));
  console.log('Saved baseline perf to', resultsPath);
  console.log('RESULTS_SUMMARY:', JSON.stringify(finalResult));
}

run().catch((err) => {
  console.error('Error during measurement:', err);
  process.exit(1);
});
