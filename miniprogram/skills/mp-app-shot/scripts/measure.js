#!/usr/bin/env node
/**
 * 元素几何实测。用来回答截图回答不了的问题（锚在视口还是文档、有没有被遮住、是否可滚）。
 *   node measure.js <项目绝对路径> <路由> <选择器...>
 * boundingClientRect 是**视口相对**的：文档 1248 / 视口 844 时，
 * 锚在视口 → bottom≈820；锚在文档 → bottom≈1224。不用滚动就能分辨。
 */
const path = require('path');
const [proj, route, ...sels] = process.argv.slice(2);
if (!proj || !route || sels.length === 0) {
  console.error('usage: measure.js <projectDir> <route> <selector...>');
  process.exit(2);
}
const automator = require(path.join(proj, 'node_modules/miniprogram-automator'));

(async () => {
  const mp = await automator.connect({ wsEndpoint: 'ws://127.0.0.1:9420' });
  await mp.reLaunch(route);
  await new Promise((r) => setTimeout(r, 2500));
  const res = await mp.evaluate((selectors) => new Promise((resolve) => {
    let q = wx.createSelectorQuery();
    selectors.forEach((s) => { q = q.select(s).boundingClientRect(); });
    q.selectViewport().scrollOffset().exec((r) => resolve(r));
  }), sels);
  const scroll = res[res.length - 1];
  sels.forEach((s, i) => {
    const r = res[i];
    console.log(r ? `${s.padEnd(24)} top=${Math.round(r.top)} bottom=${Math.round(r.bottom)} h=${Math.round(r.height)}`
                  : `${s.padEnd(24)} (未命中 —— 选择器错，或跑的还是旧包)`);
  });
  console.log('viewport'.padEnd(24) + `scrollTop=${scroll.scrollTop} scrollHeight=${scroll.scrollHeight}`);
  await mp.disconnect();
})().catch((e) => { console.error('ERR', e.message); process.exit(1); });
