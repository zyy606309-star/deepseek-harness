
const fs = require("node:fs");
const vm = require("node:vm");

const DEFAULT_BUNDLE_URL =
  "https://cdn.pinduoduo.com/home/_next/static/~e2nGEkhqzQOno4jN6u_r/pages/subject.js";
const DEFAULT_STM_URL = "https://apiv2.pinduoduo.com/api/server/_stm";
const DEFAULT_PAGE_URL = "https://www.pinduoduo.com/home/girlclothes/";
const DEFAULT_UA =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36";

function ensureRuntime() {
  const major = Number(process.versions.node.split(".")[0]);
  if (!Number.isFinite(major) || major < 18) {
    throw new Error(
      `Node.js 18+ is required (current: ${process.versions.node}). ` +
        "Set CRAWLER_NODE to a newer node.exe when using verify_api.py."
    );
  }
}

function parseArgs(argv) {
  const args = {
    bundleFile: "",
    bundleUrl: DEFAULT_BUNDLE_URL,
    cookie: "",
    events: true,
    pageUrl: DEFAULT_PAGE_URL,
    serverTime: 0,
    stmUrl: DEFAULT_STM_URL,
    userAgent: DEFAULT_UA,
  };

  for (let index = 2; index < argv.length; index += 1) {
    const arg = argv[index];
    const readValue = () => {
      index += 1;
      if (index >= argv.length) throw new Error(`Missing value for ${arg}`);
      return argv[index];
    };

    if (arg === "--bundle-file") args.bundleFile = readValue();
    else if (arg === "--bundle-url") args.bundleUrl = readValue();
    else if (arg === "--cookie") args.cookie = readValue();
    else if (arg === "--no-events") args.events = false;
    else if (arg === "--page-url") args.pageUrl = readValue();
    else if (arg === "--server-time") args.serverTime = Number(readValue());
    else if (arg === "--stm-url") args.stmUrl = readValue();
    else if (arg === "--user-agent") args.userAgent = readValue();
    else if (arg === "--help" || arg === "-h") {
      printHelp();
      process.exit(0);
    } else {
      throw new Error(`Unknown argument: ${arg}`);
    }
  }

  return args;
}

function printHelp() {
  console.log(`Usage:
  node pdd_anti_content_pure_node.js [options]

Options:
  --server-time <ms>      Use a known _stm server_time value.
  --cookie <cookie>       Browser cookie string to expose to document.cookie.
  --page-url <url>        Page URL for mocked window.location.
  --user-agent <ua>       User-Agent for mocked navigator.userAgent.
  --bundle-file <path>    Load subject.js from local file instead of CDN.
  --bundle-url <url>      subject.js URL. Default is the currently observed bundle.
  --stm-url <url>         _stm endpoint. Default: ${DEFAULT_STM_URL}
  --no-events             Do not inject synthetic mouse/click events.
  -h, --help              Show this help.
`);
}

function extractModule(bundle, moduleId) {
  const marker = `${moduleId}:function(t,e,n){`;
  const markerIndex = bundle.indexOf(marker);
  if (markerIndex < 0) throw new Error(`Module ${moduleId} not found`);

  const start = markerIndex + marker.length;
  let depth = 1;
  let quote = null;
  let escaped = false;

  for (let index = start; index < bundle.length; index += 1) {
    const char = bundle[index];
    if (quote) {
      if (escaped) escaped = false;
      else if (char === "\\") escaped = true;
      else if (char === quote) quote = null;
      continue;
    }

    if (char === '"' || char === "'" || char === "`") quote = char;
    else if (char === "{") depth += 1;
    else if (char === "}" && --depth === 0) return bundle.slice(start, index);
  }

  throw new Error(`Module ${moduleId} is not balanced`);
}

async function readTextFromUrl(url) {
  const response = await fetch(url, {
    headers: {
      accept: "*/*",
      "user-agent": DEFAULT_UA,
    },
  });
  if (!response.ok) throw new Error(`GET ${url} failed: ${response.status}`);
  return response.text();
}

async function loadBundle(args) {
  if (args.bundleFile) return fs.readFileSync(args.bundleFile, "utf8");
  return readTextFromUrl(args.bundleUrl);
}

async function loadServerTime(args) {
  if (Number.isFinite(args.serverTime) && args.serverTime > 0) {
    return args.serverTime;
  }
  const response = await fetch(args.stmUrl, {
    headers: {
      accept: "application/json, text/plain, */*",
      origin: "https://www.pinduoduo.com",
      referer: args.pageUrl,
      "user-agent": args.userAgent,
    },
  });
  if (!response.ok) throw new Error(`GET ${args.stmUrl} failed: ${response.status}`);
  const body = await response.json();
  if (!body || !body.server_time) throw new Error(`No server_time in _stm response`);
  return body.server_time;
}

function makeLocation(pageUrl) {
  const parsed = new URL(pageUrl);
  return {
    hash: parsed.hash,
    host: parsed.host,
    hostname: parsed.hostname,
    href: parsed.href,
    pathname: parsed.pathname,
    port: parsed.port,
    protocol: parsed.protocol,
    search: parsed.search,
  };
}

function makeSandbox(args) {
  const listeners = new Map();
  const win = {};
  const document = {
    body: { scrollTop: 0 },
    cookie: args.cookie,
    documentElement: { scrollTop: 0 },
    referrer: "",
    addEventListener(type, handler) {
      if (!listeners.has(type)) listeners.set(type, []);
      listeners.get(type).push(handler);
    },
    removeEventListener() {},
    createElement() {
      return { style: {} };
    },
    getElementById() {
      return null;
    },
  };
  const navigator = {
    cookieEnabled: true,
    hasOwnProperty: Object.prototype.hasOwnProperty,
    language: "zh-CN",
    languages: ["zh-CN", "zh"],
    platform: "Win32",
    plugins: [1, 2, 3],
    userAgent: args.userAgent,
    webdriver: false,
  };
  const screen = {
    availHeight: 1040,
    availWidth: 1920,
    colorDepth: 24,
    height: 1080,
    pixelDepth: 24,
    width: 1920,
  };
  const location = makeLocation(args.pageUrl);
  const module = { exports: {} };
  const sandbox = {
    Buffer,
    Date,
    Error,
    Function,
    Int32Array,
    JSON,
    Math,
    Object,
    Promise,
    String,
    Uint8Array,
    Uint16Array,
    Uint32Array,
    clearTimeout,
    console,
    decodeURIComponent,
    document,
    env: { BROWSER: true },
    exports: module.exports,
    global: null,
    globalThis: null,
    history: { length: 1, back() {} },
    location,
    module,
    navigator,
    parseFloat,
    parseInt,
    screen,
    self: win,
    setTimeout,
    window: win,
  };

  Object.assign(win, {
    Date,
    Error,
    Function,
    Math,
    Object,
    String,
    addEventListener(type, handler) {
      if (!listeners.has(type)) listeners.set(type, []);
      listeners.get(type).push(handler);
    },
    chrome: { runtime: {} },
    clearTimeout,
    document,
    history: sandbox.history,
    location,
    navigator,
    outerHeight: 1080,
    outerWidth: 1920,
    parseFloat,
    parseInt,
    removeEventListener() {},
    screen,
    self: win,
    setTimeout,
    vendor: "Google Inc.",
    window: win,
  });

  sandbox.global = sandbox;
  sandbox.globalThis = sandbox;
  sandbox.__listeners = listeners;
  return sandbox;
}

function loadFbeZ(fbeZBody, sandbox) {
  const context = vm.createContext(sandbox);
  context.requireModule = (id) => {
    if (id === "8oxB") return sandbox;
    if (id === "YuTi") return (value) => value;
    throw new Error(`Unexpected webpack dependency: ${id}`);
  };
  vm.runInContext(
    `(function(t,e,n){${fbeZBody}})(module,exports,requireModule)`,
    context
  );
  return context.module.exports;
}

function dispatchSyntheticEvents(generator, sandbox) {
  const target = { id: "goods-list" };
  const now = Date.now();
  const events = [
    { type: "mousedown", target, timeStamp: now, clientX: 533, clientY: 417 },
    { type: "mousemove", target, timeStamp: now + 25, clientX: 546, clientY: 424 },
    { type: "mousemove", target, timeStamp: now + 55, clientX: 562, clientY: 438 },
    { type: "click", target, timeStamp: now + 95, clientX: 562, clientY: 438 },
  ];

  for (const event of events) {
    if (typeof generator.swallow === "function") generator.swallow(event);
    const handlers = sandbox.__listeners.get(event.type) || [];
    for (const handler of handlers) {
      if (typeof handler === "function") handler(event);
      else if (handler && typeof handler.handleEvent === "function") {
        handler.handleEvent(event);
      }
    }
  }
}

async function main() {
  const args = parseArgs(process.argv);
  ensureRuntime();
  const [bundle, serverTime] = await Promise.all([loadBundle(args), loadServerTime(args)]);
  const fbeZBody = extractModule(bundle, "fbeZ");
  const sandbox = makeSandbox(args);
  const createGenerator = loadFbeZ(fbeZBody, sandbox);
  const generator = createGenerator({ serverTime });

  if (args.events) dispatchSyntheticEvents(generator, sandbox);

  const antiContent = await generator.messagePackSync();
  console.log(antiContent);
}

main().catch((error) => {
  console.error(error.stack || error.message);
  process.exitCode = 1;
});
