#!/usr/bin/env node

import fs from 'node:fs/promises';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { URL } from 'node:url';

const PORT = Number.parseInt(process.env.CDP_PROXY_PORT || process.env.WEB_ACCESS_PROXY_PORT || '3456', 10);
const REMOTE_DEBUG_PORT = Number.parseInt(process.env.CHROME_REMOTE_DEBUGGING_PORT || '9222', 10);
const AUTO_LAUNCH_CHROME = !['0', 'false', 'no', 'off'].includes(
  (process.env.WEB_ACCESS_AUTO_LAUNCH_CHROME || '1').trim().toLowerCase(),
);
const CHROME_HEADLESS = ['1', 'true', 'yes', 'on'].includes(
  (process.env.WEB_ACCESS_CHROME_HEADLESS || '1').trim().toLowerCase(),
);
const CHROME_USER_DATA_DIR = process.env.WEB_ACCESS_CHROME_USER_DATA_DIR
  || path.join(process.cwd(), '.horbot', 'runtime', 'chrome-web-access');
const COMMON_DEBUG_PORTS = [
  REMOTE_DEBUG_PORT,
  9229,
  9333,
];
const MACOS_CHROME_PATHS = [
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  path.join(os.homedir(), 'Applications/Google Chrome.app/Contents/MacOS/Google Chrome'),
  '/Applications/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing',
  path.join(os.homedir(), 'Applications/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing'),
  '/Applications/Chromium.app/Contents/MacOS/Chromium',
];
const WINDOWS_CHROME_PATHS = [
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files\\Chromium\\Application\\chrome.exe',
];
const LINUX_CHROME_PATHS = [
  '/usr/bin/google-chrome',
  '/usr/bin/google-chrome-stable',
  '/usr/bin/chromium',
  '/usr/bin/chromium-browser',
  '/snap/bin/chromium',
];

let WS = globalThis.WebSocket;
if (!WS) {
  try {
    WS = (await import('ws')).default;
  } catch {
    console.error('[web-access-proxy] Node.js 22+ or npm package "ws" is required.');
    process.exit(1);
  }
}

class ProxyUnavailableError extends Error {}
class CdpError extends Error {}

async function pathExists(candidate) {
  if (!candidate) {
    return false;
  }
  try {
    await fs.access(candidate);
    return true;
  } catch {
    return false;
  }
}

async function collectLocalChromeCandidates() {
  const repoRoot = process.cwd();
  const localRoot = path.join(repoRoot, '.playwright-browsers');
  const entries = [];
  try {
    for (const entry of await fs.readdir(localRoot, { withFileTypes: true })) {
      if (!entry.isDirectory() || !entry.name.startsWith('chromium-')) {
        continue;
      }
      const base = path.join(localRoot, entry.name);
      entries.push(
        path.join(base, 'chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing'),
        path.join(base, 'chrome-linux/chrome'),
        path.join(base, 'chrome-win/chrome.exe'),
      );
    }
  } catch {
    return [];
  }
  return entries;
}

async function findChromeExecutable() {
  const configured = (process.env.WEB_ACCESS_CHROME_EXECUTABLE || '').trim();
  const systemCandidates = process.platform === 'darwin'
    ? MACOS_CHROME_PATHS
    : process.platform === 'win32'
      ? WINDOWS_CHROME_PATHS
      : LINUX_CHROME_PATHS;
  const candidates = [
    configured,
    ...systemCandidates,
    ...(await collectLocalChromeCandidates()),
  ].filter(Boolean);

  for (const candidate of candidates) {
    if (await pathExists(candidate)) {
      return candidate;
    }
  }
  return null;
}

class ChromeProxy {
  constructor() {
    this.ws = null;
    this.connecting = null;
    this.cmdId = 0;
    this.pending = new Map();
    this.targetSessions = new Map();
    this.lastError = '';
    this.browserProcess = null;
    this.browserLaunching = null;
    this.browserLaunchedByProxy = false;
  }

  _isBrowserProcessAlive() {
    const pid = this.browserProcess?.pid;
    if (!pid) {
      return false;
    }
    try {
      process.kill(pid, 0);
      return true;
    } catch {
      return false;
    }
  }

  async health({ allowAutoLaunch = false } = {}) {
    try {
      const endpoint = await this._discoverBrowserEndpoint({ allowAutoLaunch });
      if (!endpoint) {
        return {
          ok: false,
          chromeConnected: false,
          endpoint: null,
          error: this.lastError || 'Chrome remote debugging is not available',
        };
      }
      if (this.ws && this._isWsOpen()) {
        return {
          ok: true,
          chromeConnected: true,
          endpoint: endpoint.httpBase,
          error: '',
        };
      }
      return {
        ok: true,
        chromeConnected: false,
        endpoint: endpoint.httpBase,
        error: '',
      };
    } catch (error) {
      this.lastError = error instanceof Error ? error.message : String(error);
      return {
        ok: false,
        chromeConnected: false,
        endpoint: null,
        error: this.lastError,
      };
    }
  }

  _isWsOpen() {
    return this.ws && (this.ws.readyState === WS.OPEN || this.ws.readyState === 1);
  }

  async ensureConnected() {
    if (this._isWsOpen()) {
      return;
    }
    if (this.connecting) {
      return this.connecting;
    }

    this.connecting = (async () => {
      const endpoint = await this._discoverBrowserEndpoint();
      if (!endpoint) {
        throw new ProxyUnavailableError(
          'Chrome remote debugging is not available. Open chrome://inspect/#remote-debugging and enable it, or start Chrome with --remote-debugging-port=9222.'
        );
      }

      await new Promise((resolve, reject) => {
        const ws = new WS(endpoint.wsUrl);
        this.ws = ws;

        const cleanup = () => {
          if (ws.removeEventListener) {
            ws.removeEventListener('open', onOpen);
            ws.removeEventListener('error', onError);
          } else if (ws.off) {
            ws.off('open', onOpen);
            ws.off('error', onError);
          }
        };

        const onOpen = () => {
          cleanup();
          this.lastError = '';
          resolve();
        };

        const onError = (event) => {
          cleanup();
          this.ws = null;
          const message = event?.message || event?.error?.message || 'Failed to connect to Chrome DevTools';
          this.lastError = message;
          reject(new ProxyUnavailableError(message));
        };

        const onClose = () => {
          this.ws = null;
          this.targetSessions.clear();
          const pending = Array.from(this.pending.entries());
          this.pending.clear();
          for (const [, deferred] of pending) {
            clearTimeout(deferred.timer);
            deferred.reject(new ProxyUnavailableError('Chrome DevTools connection closed'));
          }
        };

        const onMessage = (event) => {
          const raw = typeof event?.data === 'string'
            ? event.data
            : Buffer.isBuffer(event?.data)
              ? event.data.toString('utf-8')
              : typeof event === 'string'
                ? event
                : Buffer.isBuffer(event)
                  ? event.toString('utf-8')
                  : '';
          if (!raw) {
            return;
          }
          let message;
          try {
            message = JSON.parse(raw);
          } catch {
            return;
          }
          if (message.method === 'Target.attachedToTarget') {
            const targetId = message.params?.targetInfo?.targetId;
            const sessionId = message.params?.sessionId;
            if (targetId && sessionId) {
              this.targetSessions.set(targetId, sessionId);
            }
          }
          if (message.id && this.pending.has(message.id)) {
            const deferred = this.pending.get(message.id);
            this.pending.delete(message.id);
            clearTimeout(deferred.timer);
            if (message.error) {
              deferred.reject(new CdpError(message.error.message || JSON.stringify(message.error)));
            } else {
              deferred.resolve(message.result ?? {});
            }
          }
        };

        if (ws.on) {
          ws.on('open', onOpen);
          ws.on('error', onError);
          ws.on('close', onClose);
          ws.on('message', onMessage);
        } else {
          ws.addEventListener('open', onOpen);
          ws.addEventListener('error', onError);
          ws.addEventListener('close', onClose);
          ws.addEventListener('message', onMessage);
        }
      });
    })();

    try {
      await this.connecting;
    } finally {
      this.connecting = null;
    }
  }

  async _discoverBrowserEndpoint({ allowAutoLaunch = true } = {}) {
    const explicitUrl = (process.env.CHROME_REMOTE_DEBUGGING_URL || '').trim();
    if (explicitUrl) {
      return {
        wsUrl: explicitUrl,
        httpBase: explicitUrl.replace(/^ws/, 'http').replace(/\/devtools\/browser\/.*$/, ''),
      };
    }

    const activePort = await this._readDevToolsActivePort();
    if (activePort) {
      return activePort;
    }

    for (const port of COMMON_DEBUG_PORTS) {
      const endpoint = await this._queryDevToolsEndpoint(port);
      if (endpoint) {
        return endpoint;
      }
    }

    if (allowAutoLaunch) {
      await this._ensureChromeLaunched();
    }

    for (const port of COMMON_DEBUG_PORTS) {
      const endpoint = await this._queryDevToolsEndpoint(port);
      if (endpoint) {
        return endpoint;
      }
    }

    return null;
  }

  async _ensureChromeLaunched() {
    if (!AUTO_LAUNCH_CHROME) {
      return;
    }
    if (this._isBrowserProcessAlive()) {
      return;
    }
    if (this.browserLaunching) {
      await this.browserLaunching;
      return;
    }
    this.browserLaunching = this._launchChromeForDebugging();
    try {
      await this.browserLaunching;
    } finally {
      this.browserLaunching = null;
    }
  }

  async _launchChromeForDebugging() {
    const executable = await findChromeExecutable();
    if (!executable) {
      this.lastError = 'No Chrome executable found for web-access auto-launch';
      return;
    }

    await fs.mkdir(CHROME_USER_DATA_DIR, { recursive: true });

    const args = [
      `--remote-debugging-port=${REMOTE_DEBUG_PORT}`,
      `--user-data-dir=${CHROME_USER_DATA_DIR}`,
      '--no-first-run',
      '--no-default-browser-check',
      '--disable-background-networking',
      '--disable-component-update',
      '--disable-popup-blocking',
      'about:blank',
    ];
    if (CHROME_HEADLESS) {
      args.unshift('--headless=new');
    }

    await new Promise((resolve) => {
      try {
        const child = spawn(executable, args, {
          detached: process.platform !== 'win32',
          stdio: 'ignore',
        });
        child.on('error', (error) => {
          this.lastError = `Failed to launch Chrome for web-access: ${error instanceof Error ? error.message : String(error)}`;
          resolve();
        });
        child.unref();
        this.browserProcess = child;
        this.browserLaunchedByProxy = true;
        console.log(`[web-access-proxy] launched Chrome for remote debugging: ${executable}`);
      } catch (error) {
        this.lastError = `Failed to launch Chrome for web-access: ${error instanceof Error ? error.message : String(error)}`;
      }
      resolve();
    });

    const deadline = Date.now() + 15000;
    while (Date.now() < deadline) {
      const endpoint = await this._queryDevToolsEndpoint(REMOTE_DEBUG_PORT);
      if (endpoint) {
        this.lastError = '';
        return;
      }
      await new Promise((resolve) => setTimeout(resolve, 250));
    }

    if (!this.lastError) {
      this.lastError = `Chrome launched but remote debugging port ${REMOTE_DEBUG_PORT} is not ready`;
    }
  }

  async shutdown() {
    if (this.ws) {
      try {
        this.ws.close();
      } catch {
        // ignore shutdown close errors
      }
      this.ws = null;
    }
    if (!this.browserLaunchedByProxy || !this.browserProcess?.pid) {
      return;
    }
    try {
      if (process.platform === 'win32') {
        process.kill(this.browserProcess.pid, 'SIGTERM');
      } else {
        process.kill(-this.browserProcess.pid, 'SIGTERM');
      }
    } catch {
      try {
        process.kill(this.browserProcess.pid, 'SIGTERM');
      } catch {
        // ignore cleanup failures
      }
    }
  }

  async _readDevToolsActivePort() {
    const home = os.homedir();
    const candidates = process.platform === 'darwin'
      ? [
          path.join(home, 'Library/Application Support/Google/Chrome/DevToolsActivePort'),
          path.join(home, 'Library/Application Support/Google/Chrome Canary/DevToolsActivePort'),
          path.join(home, 'Library/Application Support/Chromium/DevToolsActivePort'),
        ]
      : process.platform === 'linux'
        ? [
            path.join(home, '.config/google-chrome/DevToolsActivePort'),
            path.join(home, '.config/chromium/DevToolsActivePort'),
          ]
        : process.platform === 'win32'
          ? [
              path.join(process.env.LOCALAPPDATA || '', 'Google/Chrome/User Data/DevToolsActivePort'),
              path.join(process.env.LOCALAPPDATA || '', 'Chromium/User Data/DevToolsActivePort'),
            ]
          : [];

    for (const candidate of candidates) {
      try {
        const content = await fs.readFile(candidate, 'utf-8');
        const [portLine, wsPathLine] = content.trim().split('\n');
        const port = Number.parseInt(portLine, 10);
        if (!Number.isFinite(port)) {
          continue;
        }
        const wsPath = (wsPathLine || '').trim();
        if (wsPath) {
          return {
            wsUrl: `ws://127.0.0.1:${port}${wsPath}`,
            httpBase: `http://127.0.0.1:${port}`,
          };
        }
        const endpoint = await this._queryDevToolsEndpoint(port);
        if (endpoint) {
          return endpoint;
        }
      } catch {
        continue;
      }
    }

    return null;
  }

  async _queryDevToolsEndpoint(port) {
    try {
      const response = await fetch(`http://127.0.0.1:${port}/json/version`);
      if (!response.ok) {
        return null;
      }
      const payload = await response.json();
      const wsUrl = payload.webSocketDebuggerUrl;
      if (!wsUrl) {
        return null;
      }
      return {
        wsUrl,
        httpBase: `http://127.0.0.1:${port}`,
      };
    } catch {
      return null;
    }
  }

  async send(method, params = {}, sessionId = null) {
    await this.ensureConnected();
    const id = ++this.cmdId;
    const payload = { id, method, params };
    if (sessionId) {
      payload.sessionId = sessionId;
    }
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new CdpError(`CDP command timed out: ${method}`));
      }, 30000);
      this.pending.set(id, { resolve, reject, timer });
      this.ws.send(JSON.stringify(payload));
    });
  }

  async ensureSession(targetId) {
    if (this.targetSessions.has(targetId)) {
      return this.targetSessions.get(targetId);
    }
    const attached = await this.send('Target.attachToTarget', { targetId, flatten: true });
    const sessionId = attached.sessionId;
    if (!sessionId) {
      throw new CdpError(`Unable to attach to target ${targetId}`);
    }
    this.targetSessions.set(targetId, sessionId);
    await Promise.allSettled([
      this.send('Page.enable', {}, sessionId),
      this.send('Runtime.enable', {}, sessionId),
      this.send('DOM.enable', {}, sessionId),
    ]);
    return sessionId;
  }

  async createTarget(url = 'about:blank') {
    const result = await this.send('Target.createTarget', { url });
    const targetId = result.targetId;
    const sessionId = await this.ensureSession(targetId);
    await this.waitForReady(sessionId, 15000);
    return { targetId, sessionId };
  }

  async waitForReady(sessionId, timeoutMs = 15000) {
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
      const state = await this.evaluate(sessionId, 'document.readyState');
      if (state === 'interactive' || state === 'complete') {
        return;
      }
      await new Promise((resolve) => setTimeout(resolve, 250));
    }
  }

  async evaluate(sessionId, expression, { returnByValue = true, awaitPromise = true } = {}) {
    const result = await this.send(
      'Runtime.evaluate',
      {
        expression,
        returnByValue,
        awaitPromise,
      },
      sessionId,
    );
    if (result.exceptionDetails) {
      throw new CdpError(result.exceptionDetails.text || 'Runtime.evaluate failed');
    }
    const remote = result.result || {};
    if (returnByValue && Object.prototype.hasOwnProperty.call(remote, 'value')) {
      return remote.value;
    }
    return remote.description || remote.value || '';
  }

  async click(targetId, selector) {
    const sessionId = await this.ensureSession(targetId);
    const expression = `
      (() => {
        const el = document.querySelector(${JSON.stringify(selector)});
        if (!el) throw new Error('Element not found: ${selector}');
        el.click();
        return 'clicked';
      })()
    `;
    return this.evaluate(sessionId, expression);
  }

  async clickAt(targetId, selector) {
    const sessionId = await this.ensureSession(targetId);
    const objectResult = await this.send(
      'Runtime.evaluate',
      {
        expression: `document.querySelector(${JSON.stringify(selector)})`,
        returnByValue: false,
      },
      sessionId,
    );
    const objectId = objectResult.result?.objectId;
    if (!objectId) {
      throw new CdpError(`Element not found: ${selector}`);
    }
    const node = await this.send('DOM.requestNode', { objectId }, sessionId);
    const model = await this.send('DOM.getBoxModel', { nodeId: node.nodeId }, sessionId);
    const content = model.model?.content || [];
    if (content.length < 8) {
      throw new CdpError(`Element box model unavailable: ${selector}`);
    }
    const x = (content[0] + content[4]) / 2;
    const y = (content[1] + content[5]) / 2;
    await this.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x, y, button: 'left', clickCount: 1 }, sessionId);
    await this.send('Input.dispatchMouseEvent', { type: 'mousePressed', x, y, button: 'left', clickCount: 1 }, sessionId);
    await this.send('Input.dispatchMouseEvent', { type: 'mouseReleased', x, y, button: 'left', clickCount: 1 }, sessionId);
    return 'clickedAt';
  }

  async setFiles(targetId, selector, files) {
    const sessionId = await this.ensureSession(targetId);
    const objectResult = await this.send(
      'Runtime.evaluate',
      {
        expression: `document.querySelector(${JSON.stringify(selector)})`,
        returnByValue: false,
      },
      sessionId,
    );
    const objectId = objectResult.result?.objectId;
    if (!objectId) {
      throw new CdpError(`File input not found: ${selector}`);
    }
    const node = await this.send('DOM.requestNode', { objectId }, sessionId);
    await this.send('DOM.setFileInputFiles', { files, nodeId: node.nodeId }, sessionId);
    return 'filesSet';
  }

  async screenshot(targetId, file) {
    const sessionId = await this.ensureSession(targetId);
    const shot = await this.send('Page.captureScreenshot', { format: 'png' }, sessionId);
    if (!shot.data) {
      throw new CdpError('Screenshot capture returned empty data');
    }
    await fs.mkdir(path.dirname(file), { recursive: true });
    await fs.writeFile(file, Buffer.from(shot.data, 'base64'));
    return file;
  }

  async scroll(targetId, direction = 'bottom') {
    const sessionId = await this.ensureSession(targetId);
    const expression = direction === 'top'
      ? `window.scrollTo({ top: 0, behavior: 'smooth' }); 'scrolled'`
      : direction === 'bottom'
        ? `window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' }); 'scrolled'`
        : `window.scrollBy({ top: ${direction === 'up' ? -600 : 600}, behavior: 'smooth' }); 'scrolled'`;
    return this.evaluate(sessionId, expression);
  }

  async getInfo(targetId) {
    const sessionId = await this.ensureSession(targetId);
    const [title, url] = await Promise.all([
      this.evaluate(sessionId, 'document.title'),
      this.evaluate(sessionId, 'window.location.href'),
    ]);
    return { title, url };
  }

  async closeTarget(targetId) {
    const result = await this.send('Target.closeTarget', { targetId });
    this.targetSessions.delete(targetId);
    return result.success ?? true;
  }
}

const proxy = new ChromeProxy();

async function readRequestBody(req) {
  const chunks = [];
  for await (const chunk of req) {
    chunks.push(Buffer.from(chunk));
  }
  return Buffer.concat(chunks).toString('utf-8');
}

function writeJson(res, statusCode, payload) {
  res.writeHead(statusCode, { 'content-type': 'application/json; charset=utf-8' });
  res.end(JSON.stringify(payload, null, 2));
}

function writeText(res, statusCode, text) {
  res.writeHead(statusCode, { 'content-type': 'text/plain; charset=utf-8' });
  res.end(text);
}

function errorStatus(error) {
  if (error instanceof ProxyUnavailableError) {
    return 503;
  }
  return 500;
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url || '/', `http://${req.headers.host || `127.0.0.1:${PORT}`}`);
  try {
    if (req.method === 'GET' && url.pathname === '/health') {
      const health = await proxy.health({ allowAutoLaunch: false });
      writeJson(res, health.ok ? 200 : 503, {
        service: 'web-access-proxy',
        port: PORT,
        ...health,
      });
      return;
    }

    if (req.method === 'GET' && url.pathname === '/new') {
      const created = await proxy.createTarget(url.searchParams.get('url') || 'about:blank');
      writeJson(res, 200, created);
      return;
    }

    if (req.method === 'POST' && url.pathname === '/eval') {
      const target = url.searchParams.get('target') || '';
      const body = await readRequestBody(req);
      const sessionId = await proxy.ensureSession(target);
      const result = await proxy.evaluate(sessionId, body);
      writeText(res, 200, typeof result === 'string' ? result : JSON.stringify(result));
      return;
    }

    if (req.method === 'POST' && url.pathname === '/click') {
      const target = url.searchParams.get('target') || '';
      const selector = await readRequestBody(req);
      const result = await proxy.click(target, selector);
      writeText(res, 200, String(result));
      return;
    }

    if (req.method === 'POST' && url.pathname === '/clickAt') {
      const target = url.searchParams.get('target') || '';
      const selector = await readRequestBody(req);
      const result = await proxy.clickAt(target, selector);
      writeText(res, 200, String(result));
      return;
    }

    if (req.method === 'POST' && url.pathname === '/setFiles') {
      const target = url.searchParams.get('target') || '';
      const body = JSON.parse(await readRequestBody(req) || '{}');
      const result = await proxy.setFiles(target, String(body.selector || ''), Array.isArray(body.files) ? body.files : []);
      writeText(res, 200, String(result));
      return;
    }

    if (req.method === 'GET' && url.pathname === '/screenshot') {
      const target = url.searchParams.get('target') || '';
      const file = url.searchParams.get('file') || '';
      const saved = await proxy.screenshot(target, file);
      writeText(res, 200, saved);
      return;
    }

    if (req.method === 'GET' && url.pathname === '/scroll') {
      const target = url.searchParams.get('target') || '';
      const direction = url.searchParams.get('direction') || 'bottom';
      const result = await proxy.scroll(target, direction);
      writeText(res, 200, String(result));
      return;
    }

    if (req.method === 'GET' && url.pathname === '/info') {
      const target = url.searchParams.get('target') || '';
      const info = await proxy.getInfo(target);
      writeJson(res, 200, info);
      return;
    }

    if (req.method === 'GET' && url.pathname === '/close') {
      const target = url.searchParams.get('target') || '';
      const success = await proxy.closeTarget(target);
      writeJson(res, 200, { success });
      return;
    }

    writeJson(res, 404, {
      error: 'Not found',
      available: ['/health', '/new', '/eval', '/click', '/clickAt', '/setFiles', '/screenshot', '/scroll', '/info', '/close'],
    });
  } catch (error) {
    writeJson(res, errorStatus(error), {
      error: error instanceof Error ? error.message : String(error),
    });
  }
});

server.listen(PORT, '127.0.0.1', () => {
  console.log(`[web-access-proxy] listening on http://127.0.0.1:${PORT}`);
  proxy.health({ allowAutoLaunch: false }).then((health) => {
    if (health.ok) {
      console.log('[web-access-proxy] browser debugging endpoint is ready');
    } else if (health.error) {
      console.warn(`[web-access-proxy] browser debugging endpoint is not ready: ${health.error}`);
    }
  }).catch((error) => {
    console.warn(`[web-access-proxy] browser warmup failed: ${error instanceof Error ? error.message : String(error)}`);
  });
});

let shuttingDown = false;
async function shutdown(signal) {
  if (shuttingDown) {
    return;
  }
  shuttingDown = true;
  console.log(`[web-access-proxy] shutting down due to ${signal}`);
  server.close(() => {});
  await proxy.shutdown();
  process.exit(0);
}

process.on('SIGINT', () => {
  void shutdown('SIGINT');
});
process.on('SIGTERM', () => {
  void shutdown('SIGTERM');
});
