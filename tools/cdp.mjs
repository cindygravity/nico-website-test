// Usage: node --experimental-websocket cdp.mjs <url> <width> <height> <jsFile|-> [shot.png] [waitMs] [scrollY]
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
const [url, w, h, jsFile, shot, waitMs = '3500', scrollY = '0'] = process.argv.slice(2);
const port = 10000 + Math.floor(Math.random() * 40000);
const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'cdp-'));
const chrome = spawn('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', [
  '--headless=new', `--remote-debugging-port=${port}`, `--user-data-dir=${dir}`, '--no-first-run',
  '--hide-scrollbars', '--disable-gpu', `--window-size=${w},${h}`, 'about:blank'], { stdio: 'ignore' });
const sleep = ms => new Promise(r => setTimeout(r, ms));
let target;
for (let i = 0; i < 60; i++) {
  try { const l = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json(); target = l.find(t => t.type === 'page'); if (target) break; } catch {}
  await sleep(200);
}
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise(r => ws.addEventListener('open', r));
let id = 0; const pending = new Map();
ws.addEventListener('message', e => { const m = JSON.parse(e.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } });
const send = (method, params = {}) => new Promise(r => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
const mobile = Number(w) < 700;
await send('Emulation.setDeviceMetricsOverride', { width: Number(w), height: Number(h), deviceScaleFactor: 1, mobile });
if (mobile) await send('Emulation.setUserAgentOverride', { userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1' });
await send('Page.enable');
const net = []; if (process.env.NETLOG) { await send('Network.enable'); ws.addEventListener('message', e => { const m = JSON.parse(e.data); if (m.method === 'Network.responseReceived' && m.params.response.url.includes(process.env.NETLOG)) net.push([m.params.requestId, m.params.response.url]); }); }
await send('Page.navigate', { url });
await sleep(Number(waitMs));
const ev = async expr => { const r = await send('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true }); return r.result?.result?.value ?? r.result?.exceptionDetails ?? r; };
if (Number(scrollY)) { await ev(`window.scrollTo(0, ${scrollY})`); await sleep(1500); }
if (process.env.HOVER) { const [hx, hy] = process.env.HOVER.split(',').map(Number); await send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: hx, y: hy }); await sleep(1200); }
if (process.env.CLICK) { const [cx, cy] = process.env.CLICK.split(',').map(Number); await send('Input.dispatchMouseEvent', { type: 'mousePressed', x: cx, y: cy, button: 'left', clickCount: 1 }); await send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: cx, y: cy, button: 'left', clickCount: 1 }); await sleep(1800); }
if (jsFile && jsFile !== '-') console.log(JSON.stringify(await ev(fs.readFileSync(jsFile, 'utf8')), null, 1));
for (const [rid, u] of net) { const b = await send('Network.getResponseBody', { requestId: rid }); console.log('NET ' + u.slice(0, 300)); if (process.env.NETDIR) fs.writeFileSync(path.join(process.env.NETDIR, 'net_' + rid.replace(/\W/g, '') + '.json'), b.result?.body || ''); }
if (shot) { const r = await send('Page.captureScreenshot', { format: 'png' }); fs.writeFileSync(shot, Buffer.from(r.result.data, 'base64')); }
ws.close(); chrome.kill(); await sleep(300); fs.rmSync(dir, { recursive: true, force: true });
process.exit(0);
