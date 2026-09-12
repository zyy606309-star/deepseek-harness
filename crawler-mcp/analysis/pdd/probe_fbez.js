
const vm = require("node:vm");

const BUNDLE_URL = "https://cdn.pinduoduo.com/home/_next/static/~e2nGEkhqzQOno4jN6u_r/pages/subject.js";

function extractModule(bundle, moduleId) {
  const marker = `${moduleId}:function(t,e,n){`;
  const start = bundle.indexOf(marker);
  if (start < 0) throw new Error(`Module ${moduleId} not found`);

  let depth = 0;
  let quote = null;
  let escaped = false;
  for (let index = start + marker.length - 1; index < bundle.length; index += 1) {
    const char = bundle[index];
    if (quote) {
      if (escaped) escaped = false;
      else if (char === "\\") escaped = true;
      else if (char === quote) quote = null;
      continue;
    }
    if (char === '"' || char === "'" || char === "`") {
      quote = char;
    } else if (char === "{") {
      depth += 1;
    } else if (char === "}" && --depth === 0) {
      return bundle.slice(start + marker.length, index);
    }
  }
  throw new Error(`Module ${moduleId} is not balanced`);
}

async function main() {
  const bundle = await fetch(BUNDLE_URL).then((response) => response.text());
  const body = extractModule(bundle, "fbeZ");
  const module = { exports: {} };
  const sandbox = {
    Buffer,
    Date,
    JSON,
    Math,
    Promise,
    performance: { now: () => Date.now() },
    Uint8Array,
    Uint16Array,
    Uint32Array,
    console,
    module,
    exports: module.exports,
    self: {},
    window: {},
    navigator: {
      language: "zh-CN",
      languages: ["zh-CN", "zh"],
      platform: "Win32",
      userAgent: "Mozilla/5.0",
    },
    document: {
      documentElement: {},
      createElement: () => ({}),
    },
  };
  sandbox.window.document = sandbox.document;
  sandbox.window.navigator = sandbox.navigator;
  sandbox.window.screen = { width: 1920, height: 1080, colorDepth: 24 };
  sandbox.window.performance = sandbox.performance;
  sandbox.window.window = sandbox.window;
  sandbox.self = sandbox.window;
  sandbox.global = sandbox;
  const requireModule = (id) => {
    if (id === "8oxB") return sandbox;
    if (id === "YuTi") return (value) => value;
    throw new Error(`Unexpected webpack dependency: ${id}`);
  };

  vm.runInNewContext(`(function(t,e,n){${body}})(module,exports,requireModule)`, {
    ...sandbox,
    requireModule,
  });
  const Exported = module.exports;
  console.log(JSON.stringify({
    exportType: typeof Exported,
    exportKeys: Object.keys(Exported),
    prototype: Exported && Exported.prototype ? Object.getOwnPropertyNames(Exported.prototype) : [],
  }, null, 2));
}

main().catch((error) => {
  console.error(error.stack);
  process.exitCode = 1;
});
