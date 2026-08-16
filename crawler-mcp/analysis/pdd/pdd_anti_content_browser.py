
"""Capture a locally browser-generated anti_content value from Pinduoduo's web app.

The value is produced by the site's own JavaScript in a real Chrome session. This
script only observes the outgoing request URL; it does not replay the request.
"""

import argparse
import asyncio
import json
from urllib.parse import parse_qs, urlparse
from urllib.request import urlopen

from pyppeteer import connect


HOME_URL = "https://www.pinduoduo.com/home/girlclothes/"
TARGET_PATH = "/api/gindex/tf/query_tf_goods_info"


def browser_ws_endpoint(port: int) -> str:
    with urlopen(f"http://127.0.0.1:{port}/json/version", timeout=5) as response:
        metadata = json.loads(response.read().decode("utf-8"))
    return metadata["webSocketDebuggerUrl"]


async def capture_anti_content(port: int, timeout: float) -> str:
    browser = await connect(browserWSEndpoint=browser_ws_endpoint(port), defaultViewport=None)
    page = await browser.newPage()
    captured = asyncio.get_running_loop().create_future()

    def on_request(request):
        parsed = urlparse(request.url)
        if parsed.netloc == "apiv2.pinduoduo.com" and parsed.path == TARGET_PATH:
            anti_content = parse_qs(parsed.query).get("anti_content", [None])[0]
            if anti_content and not captured.done():
                captured.set_result(anti_content)

    page.on("request", on_request)
    try:
        await page.goto(HOME_URL, {"waitUntil": "domcontentloaded", "timeout": int(timeout * 1000)})
        return await asyncio.wait_for(captured, timeout)
    finally:
        await page.close()
        await browser.disconnect()


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture a browser-generated Pinduoduo anti_content value.")
    parser.add_argument("--port", type=int, default=9222, help="Chrome remote debugging port (default: 9222)")
    parser.add_argument("--timeout", type=float, default=20, help="Capture timeout in seconds (default: 20)")
    args = parser.parse_args()

    anti_content = asyncio.run(capture_anti_content(args.port, args.timeout))
    print(anti_content)


if __name__ == "__main__":
    main()
