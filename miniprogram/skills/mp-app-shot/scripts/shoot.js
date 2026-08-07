#!/usr/bin/env node
/**
 * 无头截图 + 视图模型读回。不需要开发者工具获得焦点。
 *   node shoot.js <项目绝对路径> <路由> <输出名> [等待毫秒]
 * 例：node shoot.js /path/to/proj /pages/index/index root 8000
 */
const path = require('path');
const [proj, route, out, waitMs] = process.argv.slice(2);
if (!proj || !route || !out) {
  console.error('usage: shoot.js <projectDir> <route> <outName> [waitMs]');
  process.exit(2);
}
const automator = require(path.join(proj, 'node_modules/miniprogram-automator'));

(async () => {
  const mp = await automator.connect({ wsEndpoint: 'ws://127.0.0.1:9420' });
  mp.on('console', (m) => {
    if (m.type === 'log') return;
    console.log('[console]', m.type, (m.args || []).map((a) => String(a && a.value !== undefined ? a.value : a)).join(' '));
  });
  mp.on('exception', (e) => console.log('[EXCEPTION]', e.message));

  await mp.reLaunch(route);
  await new Promise((r) => setTimeout(r, Number(waitMs || 8000)));

  const page = await mp.currentPage();
  const data = await page.data();
  const cap = await mp.evaluate(() => wx.getMenuButtonBoundingClientRect());
  const sys = await mp.evaluate(() => {
    const w = wx.getWindowInfo ? wx.getWindowInfo() : wx.getSystemInfoSync();
    return { statusBarHeight: w.statusBarHeight, screenHeight: w.screenHeight };
  });

  const file = path.join(proj, '.claude/shots', out + '.png');
  await mp.screenshot({ path: file });

  console.log('route      =', page.path);
  console.log('data keys  =', Object.keys(data || {}).join(','));
  console.log('data       =', JSON.stringify(data).slice(0, 1200));
  // 截图里看不见胶囊按钮 —— 必须用数字判
  console.log('capsule    =', JSON.stringify(cap), ' statusBar =', sys.statusBarHeight);
  console.log('顶部下界   =', Math.round(cap.bottom + (cap.top - sys.statusBarHeight)),
    '（内容起点必须 >= 它；右上角不得有元素落在 x∈[' + cap.left + ',' + cap.right + ']）');
  console.log('shot       =', file);
  await mp.disconnect();
})().catch((e) => { console.error('ERR', e.message); process.exit(1); });
