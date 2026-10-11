const { chromium } = require('@playwright/test');
const path = require('path');
const fs = require('fs');

async function run() {
  const browserPath = '/usr/bin/brave-browser';
  const outDir = path.join(__dirname, '..', 'local_assets', 'shots_after');
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

  // 1. Take After Screenshots (at t=1.5s after loading)
  console.log('Capturing screenshots at 1440x900 and 390x844...');
  {
    const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
    await page.goto('http://localhost:3001', { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2000);
    await page.screenshot({ path: path.join(outDir, 'desktop_1440x900.png'), fullPage: false });
    console.log('Saved 1440x900 after screenshot.');
    await page.close();
  }

  {
    const page = await browser.newPage({ viewport: { width: 390, height: 844 }, isMobile: true });
    await page.goto('http://localhost:3001', { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2000);
    await page.screenshot({ path: path.join(outDir, 'mobile_390x844.png'), fullPage: false });
    console.log('Saved 390x844 after screenshot.');
    await page.close();
  }

  // Helper for probe measurement
  async function measurePerf(throttled = false, targetFrames = 150) {
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
      await page.waitForFunction(() => window.__AEGIS_PERF_DONE__ === true, null, { timeout: 120000 });
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

  console.log('Measuring normal performance (150 frames)...');
  const normalReport = await measurePerf(false, 150);
  console.log('Normal Report:', JSON.stringify(normalReport, null, 2));

  console.log('Measuring 4x CPU throttled performance (150 frames)...');
  const throttledReport = await measurePerf(true, 150);
  console.log('4x Throttled Report:', JSON.stringify(throttledReport, null, 2));

  await browser.close();

  const finalResult = {
    normal: normalReport,
    cpu_throttled_4x: throttledReport
  };

  const resultsPath = path.join(__dirname, '..', 'local_assets', 'after_perf.json');
  fs.writeFileSync(resultsPath, JSON.stringify(finalResult, null, 2));
  console.log('Saved after perf to', resultsPath);
  console.log('RESULTS_SUMMARY:', JSON.stringify(finalResult));
}

run().catch((err) => {
  console.error('Error during after measurement:', err);
  process.exit(1);
});
