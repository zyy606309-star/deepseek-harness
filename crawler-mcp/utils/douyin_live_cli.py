"""Print decoded Douyin live messages from an already running CDP Chrome."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Allow launching this script from any working directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from browser import BrowserManager


async def run(args):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

    def emit(value):
        try:
            print(json.dumps(value, ensure_ascii=False), flush=True)
            return True
        except (BrokenPipeError, OSError):
            return False

    browser = BrowserManager()
    connected = await browser.connect_browser(args.port)
    if not connected.get("success"):
        raise SystemExit(connected.get("error", "Chrome connection failed"))
    if args.reload:
        await browser.reload()
        await asyncio.sleep(args.reload_wait)
    started = await browser.start_live_stream(
        output_path=args.raw_output,
        websocket_url_pattern=args.websocket_pattern,
        include_raw=bool(args.raw_output),
        wait_timeout=args.wait_timeout,
    )
    if not started.get("success"):
        raise SystemExit(started.get("error", "Live WebSocket not found"))
    methods = args.method or ["WebcastChatMessage"]
    if not emit({"event": "started", **started, "methods": methods}):
        return
    deadline = asyncio.get_running_loop().time() + args.duration if args.duration else None
    try:
        while deadline is None or asyncio.get_running_loop().time() < deadline:
            result = await browser.read_live_messages(
                duration=args.batch_seconds,
                max_messages=args.batch_size,
                methods=methods,
            )
            for item in result.get("messages", []):
                if not emit({"event": "message", **item}):
                    return
    except KeyboardInterrupt:
        pass
    finally:
        emit({"event": "stopped", **(await browser.stop_live_stream())})


def main():
    parser = argparse.ArgumentParser(description="持续输出抖音直播弹幕，复用已登录 Chrome 会话")
    parser.add_argument("--port", type=int, default=9222)
    parser.add_argument("--method", action="append", help="消息方法，可重复；默认 WebcastChatMessage")
    parser.add_argument("--raw-output", help="可选 JSONL 原始帧和解析结果输出路径")
    parser.add_argument("--websocket-pattern", default="webcast")
    parser.add_argument("--wait-timeout", type=int, default=15000)
    parser.add_argument("--batch-seconds", type=float, default=2.0)
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--reload", action="store_true", default=True, help="启动时刷新当前直播页以建立可观测 WebSocket")
    parser.add_argument("--reload-wait", type=float, default=3.0)
    parser.add_argument("--duration", type=float, default=None, help="演示模式运行秒数；省略则持续运行")
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
