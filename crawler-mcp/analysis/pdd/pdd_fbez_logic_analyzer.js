
const vm = require("node:vm");

const BUNDLE_URL =
  "https://cdn.pinduoduo.com/home/_next/static/~e2nGEkhqzQOno4jN6u_r/pages/subject.js";

function extractModule(bundle, moduleId) {
  const marker = `${moduleId}:function(t,e,n){`;
  const markerIndex = bundle.indexOf(marker);
  if (markerIndex < 0) {
    throw new Error(`Module ${moduleId} not found`);
  }

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

function makeBrowserLikeSandbox() {
  const win = {};
  const document = {
    cookie: "",
    referrer: "",
    documentElement: { scrollTop: 0 },
    body: { scrollTop: 0 },
    addEventListener() {},
    removeEventListener() {},
    createElement() {
      return { style: {} };
    },
    getElementById() {
      return null;
    },
  };
  const navigator = {
    userAgent:
      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
    platform: "Win32",
    language: "zh-CN",
    languages: ["zh-CN", "zh"],
    plugins: [1],
    webdriver: false,
    cookieEnabled: true,
    hasOwnProperty: Object.prototype.hasOwnProperty,
  };
  const screen = {
    width: 1920,
    height: 1080,
    availWidth: 1920,
    availHeight: 1040,
    colorDepth: 24,
    pixelDepth: 24,
  };
  const location = {
    href: "https://www.pinduoduo.com/home/girlclothes/",
    protocol: "https:",
    host: "www.pinduoduo.com",
    hostname: "www.pinduoduo.com",
    port: "",
    pathname: "/home/girlclothes/",
    search: "",
    hash: "",
  };
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
    module,
    exports: module.exports,
    history: { length: 1, back() {} },
    location,
    navigator,
    document,
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
    addEventListener() {},
    clearTimeout,
    document,
    history: sandbox.history,
    location,
    navigator,
    parseFloat,
    parseInt,
    removeEventListener() {},
    screen,
    self: win,
    setTimeout,
    window: win,
  });

  sandbox.global = sandbox;
  sandbox.globalThis = sandbox;
  return sandbox;
}

function loadFbeZ(fbeZBody) {
  const module = { exports: {} };
  const sandbox = makeBrowserLikeSandbox();
  sandbox.module = module;
  sandbox.exports = module.exports;

  const patchedBody = fbeZBody.replace(
    "W=f,x=W(",
    "W=(globalThis.__decodeString=f),x=W("
  );
  const context = vm.createContext(sandbox);
  context.requireModule = (id) => {
    if (id === "8oxB") return sandbox;
    if (id === "YuTi") return (value) => value;
    throw new Error(`Unexpected webpack dependency: ${id}`);
  };

  vm.runInContext(
    `(function(t,e,n){${patchedBody}})(module,exports,requireModule)`,
    context
  );

  return {
    decodeString: context.__decodeString,
    exported: context.module.exports,
  };
}

function decodeWCalls(source, decodeString) {
  return source.replace(
    /\b[A-Za-z_$][\w$]*\("((?:0x)?[0-9a-f]+)","([^"\\]*(?:\\.[^"\\]*)*)"\)/gi,
    (match, index, rawKey) => {
      try {
        const key = JSON.parse(`"${rawKey}"`);
        return JSON.stringify(decodeString(index, key));
      } catch {
        return match;
      }
    }
  );
}

function compactSource(source) {
  return source
    .replace(/\s+/g, " ")
    .replace(/;(?=(?:var|function|\w+\[|\w+\.) )/g, ";\n");
}

function printTpP2Flow(tpP2Body) {
  console.log("TPp2 flow:");
  console.log("  exports.b -> init wrapper");
  console.log("  exports.a -> anti_content wrapper");
  console.log("  init: GET https://apiv2.pinduoduo.com/api/server/_stm");
  console.log("  init: new fbeZ({ serverTime: response.server_time })");
  console.log("  generate: await singleton.messagePackSync()");
  console.log("");
  console.log("TPp2 body head:");
  console.log(compactSource(tpP2Body.slice(0, 1800)));
}

function printFbeZSummary(exported) {
  const instance = exported();
  const prototype = Object.getPrototypeOf(instance);
  console.log("");
  console.log("fbeZ exported shape:");
  console.log(`  export type: ${typeof exported}`);
  console.log(`  instance own keys: ${Object.keys(instance).join(", ") || "(none)"}`);
  console.log(`  prototype methods: ${Object.getOwnPropertyNames(prototype).join(", ")}`);
}

function printKnownCollectors() {
  const collectors = [
    ["pt", "1/2", "touchstart or mousedown event buffer"],
    ["_t", "24/25", "touchmove or mousemove event buffer"],
    ["vt", "4", "click event buffer plus click/mousedown template checksum"],
    ["yt", "3", "scrollTop event buffer"],
    ["Ct", "7", "location.href and location.port"],
    ["Ot", "8", "screen.availWidth and screen.availHeight"],
    ["Pt", "9", "random number pair plus serverTime"],
    ["Gt", "10", "automation/headless environment bitset"],
    ["zt", "11", "current href encoded bytes"],
    ["Nt", "12", "DeviceOrientationEvent presence"],
    ["Ft", "13", "DeviceMotionEvent presence"],
    ["Bt", "14", "Date.now() minus updateServerTime timestamp"],
    ["At", "15", "navigator.userAgent"],
    ["Et", "16/17", "nano_cookie_fp and nano_storage_fp"],
    ["Dt", "18", "document.referrer without query string"],
    ["Zt", "19", "pdd_user_id cookie"],
    ["It", "20", "api_uid cookie"],
    ["Yt", "21", "messagePack/messagePackSync call counter"],
    ["$t", "22", "initial client Date.now() value"],
    ["ee", "23", "pdd_vds cookie"],
    ["re", "26", "browser family bitset"],
  ];

  console.log("");
  console.log("collector map:");
  for (const [name, tag, meaning] of collectors) {
    console.log(`  ${name.padEnd(3)} tag ${tag.padEnd(5)} ${meaning}`);
  }
}

function printDecodedRegion(name, decodedBody, anchor, before = 1200, after = 2200) {
  const index = decodedBody.indexOf(anchor);
  console.log("");
  console.log(`${name}:`);
  if (index < 0) {
    console.log(`  anchor not found: ${anchor}`);
    return;
  }
  console.log(compactSource(decodedBody.slice(Math.max(0, index - before), index + after)));
}

async function main() {
  const showDecoded = process.argv.includes("--decoded");
  const bundle = await fetch(BUNDLE_URL).then((response) => {
    if (!response.ok) throw new Error(`Fetch failed: ${response.status}`);
    return response.text();
  });

  const tpP2Body = extractModule(bundle, "TPp2");
  const fbeZBody = extractModule(bundle, "fbeZ");
  const { exported } = loadFbeZ(fbeZBody);

  printTpP2Flow(tpP2Body);
  printFbeZSummary(exported);
  printKnownCollectors();

  console.log("");
  console.log("final pack pipeline:");
  console.log("  1. collectors.packN() values are concatenated into byte array a");
  console.log("  2. payload = [3] + [1, 0, 0] + lengthBytes + a");
  console.log("  3. payload is compressed with embedded pako.deflate");
  console.log("  4. compressed binary string is concatenated with et integrity bytes");
  console.log('  5. custom encode() is applied and prefixed with "0aq"');

  if (showDecoded) {
    const { decodeString } = loadFbeZ(fbeZBody);
    const decodeStart = fbeZBody.indexOf("W=f,x=W(");
    const decodedFbeZ =
      decodeStart < 0
        ? decodeWCalls(fbeZBody, decodeString)
        : fbeZBody.slice(0, decodeStart) +
          decodeWCalls(fbeZBody.slice(decodeStart), decodeString);
    printDecodedRegion("environment probe Wt()", decodedFbeZ, "var Wt=function");
    printDecodedRegion("event normalizer xt()", decodedFbeZ, "function xt");
    printDecodedRegion("final pack ue()", decodedFbeZ, "function ue");
    printDecodedRegion("generator class de()", decodedFbeZ, "function de");
  }
}

main().catch((error) => {
  console.error(error.stack || error.message);
  process.exitCode = 1;
});
