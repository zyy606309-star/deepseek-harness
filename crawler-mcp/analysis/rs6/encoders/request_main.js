require("./env.js");
require("./encrypt_js_code.js");
require("./decode_external.js");

function main() {
  setTimeout(() => {
    console.log(document.cookie);
    process.exit(0);
  }, 3000);
}

main();
