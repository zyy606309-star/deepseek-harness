"use strict";

const fs = require("fs");
const vm = require("vm");

const source = fs.readFileSync(__dirname + "/douyin_abogus.js", "utf8") +
  "\nmodule.exports = { generate_a_bogus };\n";
const context = { module: { exports: {} }, console, Math, Date, encodeURIComponent };
vm.runInNewContext(source, context, { filename: "douyin_abogus.js" });

const [query, userAgent] = process.argv.slice(2);
if (!query || !userAgent) {
  process.stderr.write("usage: node douyin_abogus_cli.js <query> <user-agent>\n");
  process.exit(2);
}
process.stdout.write(context.module.exports.generate_a_bogus(query, userAgent));
