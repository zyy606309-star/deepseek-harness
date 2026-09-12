"""Consume Douyin live messages through captured WebSocket or browser-free HTTP polling."""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import subprocess
import sys
import time
from urllib.parse import urlencode, urlparse, parse_qsl
from pathlib import Path

import requests
import websocket

# Allow launching this script from any working directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from browser import BrowserManager

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"


def generate_a_bogus(query, user_agent=USER_AGENT):
    signer = Path(__file__).with_name("douyin_abogus_cli.js")
    result = subprocess.run(
        ["node", str(signer), query, user_agent],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def _cookie_header(cookie):
    return cookie.strip()


def fetch_room_context(room_url, cookie):
    parsed = urlparse(room_url)
    web_rid = parsed.path.rstrip("/").split("/")[-1]
    params = [
        ("aid", "6383"), ("app_name", "douyin_web"), ("live_id", "1"),
        ("device_platform", "web"), ("language", "zh-CN"), ("enter_from", "link_share"),
        ("cookie_enabled", "true"), ("screen_width", "1920"), ("screen_height", "1080"),
        ("browser_language", "zh-CN"), ("browser_platform", "Win32"),
        ("browser_name", "Chrome"), ("browser_version", "150.0.0.0"),
        ("os_name", "Windows"), ("os_version", "10"), ("web_rid", web_rid),
        ("room_id_str", ""), ("enter_source", ""), ("is_need_double_stream", "false"),
        ("insert_task_id", ""), ("live_reason", ""),
    ]
    headers = {"User-Agent": USER_AGENT, "Referer": room_url, "Cookie": _cookie_header(cookie), "Accept": "application/json, text/plain, */*"}
    initial = urlencode(params)
    params.append(("a_bogus", generate_a_bogus(initial)))
    response = requests.get("https://live.douyin.com/webcast/room/web/enter/", params=params, headers=headers, timeout=20)
    response.raise_for_status()
    payload = response.json()
    rows = payload.get("data", {}).get("data", [])
    if not rows:
        raise RuntimeError(f"room enter returned no room data: {payload.get('status_code')}")
    room_id = rows[0].get("id_str") or payload.get("data", {}).get("enter_room_id")
    if not room_id:
        raise RuntimeError("room enter returned no room id")
    return {"roomId": str(room_id), "webRid": web_rid, "payload": payload}


def fetch_web_id(room_url, cookie):
    headers = {"User-Agent": USER_AGENT, "Referer": "https://live.douyin.com/", "Cookie": _cookie_header(cookie), "Content-Type": "application/json;charset=UTF-8"}
    body = {"app_id": 6383, "url": room_url, "user_agent": USER_AGENT, "referer": "", "user_unique_id": ""}
    response = requests.post("https://mcs.zijieapi.com/webid?aid=6383&sdk_version=5.1.24_dy", headers=headers, json=body, timeout=20)
    response.raise_for_status()
    value = response.json().get("web_id")
    if not value:
        raise RuntimeError(f"webid returned no web_id: {response.text[:300]}")
    return str(value)


def build_fetch_url(room_id, user_unique_id, cookie):
    return _build_fetch_url(room_id, user_unique_id, cursor="", internal_ext="")


def _build_fetch_url(room_id, user_unique_id, cursor="", internal_ext=""):
    params = [
        ("resp_content_type", "protobuf"), ("did_rule", "3"), ("device_id", ""),
        ("app_name", "douyin_web"), ("endpoint", "live_pc"), ("support_wrds", "1"),
        ("user_unique_id", user_unique_id), ("identity", "audience"), ("need_persist_msg_count", "15"),
        ("insert_task_id", ""), ("live_reason", ""), ("room_id", room_id), ("version_code", "180800"),
        ("last_rtt", "0"), ("live_id", "1"), ("aid", "6383"), ("fetch_rule", "1"),
        ("cursor", cursor), ("internal_ext", internal_ext), ("device_platform", "web"), ("cookie_enabled", "true"),
        ("screen_width", "1920"), ("screen_height", "1080"), ("browser_language", "zh-CN"),
        ("browser_platform", "Win32"), ("browser_name", "Mozilla"), ("browser_version", USER_AGENT.split("Chrome/")[1].split(" ")[0]),
        ("browser_online", "true"), ("tz_name", "Asia/Shanghai"),
    ]
    query = urlencode(params)
    params.append(("a_bogus", generate_a_bogus(query)))
    return "https://live.douyin.com/webcast/im/fetch/?" + urlencode(params)


def bootstrap_local(room_url, cookie):
    context = fetch_room_context(room_url, cookie)
    user_unique_id = fetch_web_id(room_url, cookie)
    fetch_url = build_fetch_url(context["roomId"], user_unique_id, cookie)
    headers = {"User-Agent": USER_AGENT, "Referer": room_url, "Cookie": _cookie_header(cookie), "Accept": "application/x-protobuf"}
    response = requests.get(fetch_url, headers=headers, timeout=20)
    response.raise_for_status()
    return {"roomId": context["roomId"], "userUniqueId": user_unique_id, "fetchUrl": fetch_url, "fetchBody": response.content, "headers": headers}


def _decode_fetch_body(raw):
    """Decode the protobuf response returned by /webcast/im/fetch/."""
    messages = []
    cursor = ""
    internal_ext = ""
    push_server = ""
    heartbeat = 0
    for number, wire_type, value in BrowserManager._proto_fields(raw):
        if number == 1 and wire_type == 2:
            fields = BrowserManager._proto_fields(value)
            method = next((v.decode("utf-8", "replace") for n, w, v in fields if n == 1 and w == 2), "")
            payload = next((v for n, w, v in fields if n == 2 and w == 2), b"")
            payload_fields = BrowserManager._proto_fields(payload)
            content = next((v.decode("utf-8", "replace") for n, w, v in payload_fields if n == 3 and w == 2), "")
            user_blob = next((v for n, w, v in payload_fields if n == 2 and w == 2), b"")
            user_fields = BrowserManager._proto_fields(user_blob)
            user_id = next((v for n, w, v in user_fields if n == 1 and w == 0), None)
            user_name = next((v.decode("utf-8", "replace") for n, w, v in user_fields if n == 3 and w == 2), "")
            if not user_name:
                user_name = next((v.decode("utf-8", "replace") for n, w, v in user_fields if n == 2 and w == 2), "")
            messages.append({
                "method": method,
                "content": content,
                "userId": str(user_id) if user_id is not None else None,
                "userName": user_name,
                "payloadLength": len(payload),
            })
        elif number == 2 and wire_type == 2:
            cursor = value.decode("utf-8", "replace")
        elif number == 5 and wire_type == 2:
            internal_ext = value.decode("utf-8", "replace")
        elif number == 8 and wire_type == 0:
            heartbeat = int(value)
        elif number in (10, 14) and wire_type == 2:
            push_server = value.decode("utf-8", "replace")
    return {"messages": messages, "cursor": cursor, "internal_ext": internal_ext, "pushServer": push_server, "heartbeat": heartbeat}


def consume_http(room_url, cookie, duration, methods, output_path=None):
    """Browser-free HTTP long-poll consumer. It is the stable fallback when WS device handshake is rejected."""
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

    def emit(value):
        try:
            print(json.dumps(value, ensure_ascii=False), flush=True)
            return True
        except (BrokenPipeError, OSError, UnicodeEncodeError):
            return False

    output = Path(output_path) if output_path else None
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Referer": room_url, "Cookie": _cookie_header(cookie), "Accept": "application/x-protobuf"})
    started = time.time()
    context = fetch_room_context(room_url, cookie)
    user_unique_id = fetch_web_id(room_url, cookie)
    room_id = context["roomId"]
    cursor = ""
    internal_ext = ""
    first = True
    if not emit({"event": "local_http_started", "roomId": room_id, "userUniqueId": user_unique_id, "methods": methods}):
        return "output_closed"
    try:
        while duration is None or time.time() - started < duration:
            url = _build_fetch_url(room_id, user_unique_id, cursor, internal_ext)
            response = session.get(url, timeout=35)
            response.raise_for_status()
            decoded = _decode_fetch_body(response.content)
            cursor = decoded.get("cursor") or cursor
            internal_ext = decoded.get("internal_ext") or internal_ext
            for item in decoded["messages"]:
                if methods and item.get("method") not in methods:
                    continue
                if not emit({"event": "message", **item}):
                    return "output_closed"
                if output:
                    with output.open("a", encoding="utf-8") as handle:
                        handle.write(json.dumps({"record": item}, ensure_ascii=False) + "\n")
            if first:
                emit({"event": "local_http_bootstrapped", "cursor": cursor, "heartbeat": decoded.get("heartbeat"), "messageCount": len(decoded["messages"])})
                first = False
        return "duration_elapsed"
    except requests.RequestException as exc:
        return f"http_error:{exc}"
    finally:
        emit({"event": "local_http_disconnected"})


def _encode_varint(value):
    out = bytearray()
    value = int(value)
    while value >= 0x80:
        out.append((value & 0x7F) | 0x80)
        value >>= 7
    out.append(value)
    return bytes(out)


def _encode_bytes_field(number, value):
    value = bytes(value)
    return _encode_varint((number << 3) | 2) + _encode_varint(len(value)) + value


def _ack_frame(payload):
    """Build the browser's protobuf ACK for one server WebSocket frame."""
    gzip_offset = payload.find(b"\x1f\x8b")
    if gzip_offset < 0:
        return None
    fields = BrowserManager._proto_fields(payload[:gzip_offset])
    message_id = next((value for number, wire_type, value in fields if number == 2 and wire_type == 0), None)
    internal_ext = None
    for number, wire_type, value in fields:
        if number != 5 or wire_type != 2:
            continue
        pair = BrowserManager._proto_fields(value)
        if len(pair) >= 2 and pair[0][2] == b"im-internal_ext":
            internal_ext = pair[1][2]
            break
    if message_id is None or not internal_ext:
        return None
    return _encode_varint(16) + _encode_varint(message_id) + _encode_bytes_field(7, b"ack") + _encode_bytes_field(8, internal_ext)


async def capture_handshake(port: int, reload_wait: float):
    browser = BrowserManager()
    result = await browser.connect_browser(port)
    if not result.get("success"):
        raise RuntimeError(result.get("error", "Chrome connection failed"))
    await browser.reload()
    await asyncio.sleep(reload_wait)
    url = next((e.get("url") for e in reversed(browser._websocket_events) if e.get("event") == "created" and "webcast" in e.get("url", "")), None)
    cookies = await browser._page.cookies()
    cookie = "; ".join(f"{item['name']}={item['value']}" for item in cookies if "douyin.com" in item.get("domain", ""))
    return url, cookie


def consume_once(ws_url, cookie, duration, methods, output_path=None):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

    def emit(value):
        try:
            print(json.dumps(value, ensure_ascii=False), flush=True)
            return True
        except (BrokenPipeError, OSError, UnicodeEncodeError):
            return False

    headers = ["User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"]
    ws = websocket.create_connection(ws_url, timeout=10, origin="https://live.douyin.com", cookie=cookie, header=headers)
    end = time.time() + duration if duration else None
    next_heartbeat = time.monotonic() + 10.0
    output = Path(output_path) if output_path else None
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
    if not emit({"event": "direct_started", "url": ws_url, "methods": methods}):
        ws.close()
        return "output_closed"
    ws.settimeout(2)
    try:
        while end is None or time.time() < end:
            if time.monotonic() >= next_heartbeat:
                ws.send(b":\x02hb", opcode=websocket.ABNF.OPCODE_BINARY)
                next_heartbeat = time.monotonic() + 10.0
            try:
                payload = ws.recv()
            except websocket.WebSocketTimeoutException:
                continue
            except websocket.WebSocketConnectionClosedException:
                return "connection_closed"
            if not payload:
                continue
            if isinstance(payload, str):
                payload = payload.encode()
            ack = _ack_frame(payload)
            if ack:
                ws.send(ack, opcode=websocket.ABNF.OPCODE_BINARY)
            decoded = BrowserManager._decode_live_frame(base64.b64encode(payload).decode())
            if not decoded:
                continue
            for item in decoded["messages"]:
                if methods and item.get("method") not in methods:
                    continue
                record = {"event": "message", **item}
                if not emit(record):
                    return "output_closed"
                if output:
                    with output.open("a", encoding="utf-8") as handle:
                        handle.write(json.dumps({"record": item, "rawFrame": base64.b64encode(payload).decode()}, ensure_ascii=False) + "\n")
        return "duration_elapsed"
    finally:
        ws.close()
        emit({"event": "direct_disconnected"})


def consume(ws_url, cookie, duration, methods, output_path=None):
    return consume_once(ws_url, cookie, duration, methods, output_path)


async def run(args):
    methods = args.method or ["WebcastChatMessage"]
    if args.local_http:
        cookie = Path(args.cookie_file).read_text(encoding="utf-8").strip() if args.cookie_file else ""
        reason = await asyncio.to_thread(consume_http, args.room_url, cookie, args.duration, methods, args.output)
        if reason in {"output_closed", "duration_elapsed"}:
            print(json.dumps({"event": "direct_stopped"}, ensure_ascii=False), flush=True)
        else:
            print(json.dumps({"event": "local_http_error", "reason": reason}, ensure_ascii=False), flush=True)
        return
    started_at = time.time()
    first = True
    while args.duration is None or time.time() - started_at < args.duration:
        if args.ws_url:
            ws_url = args.ws_url
            cookie = Path(args.cookie_file).read_text(encoding="utf-8").strip() if args.cookie_file else ""
        else:
            try:
                ws_url, cookie = await capture_handshake(args.port, args.reload_wait)
            except Exception as exc:
                print(json.dumps({"event": "reconnect_wait", "error": str(exc)}, ensure_ascii=False), flush=True)
                await asyncio.sleep(args.reconnect_delay)
                continue
            if not ws_url:
                await asyncio.sleep(args.reconnect_delay)
                continue
            if first and args.save_cookie:
                Path(args.save_cookie).write_text(cookie, encoding="utf-8")
            if first and args.save_ws_url:
                Path(args.save_ws_url).write_text(ws_url, encoding="utf-8")
        first = False
        remaining = None if args.duration is None else max(1.0, args.duration - (time.time() - started_at))
        reason = await asyncio.to_thread(consume_once, ws_url, cookie, remaining, methods, args.output)
        if reason in {"output_closed", "duration_elapsed"}:
            break
        print(json.dumps({"event": "reconnecting", "reason": reason}, ensure_ascii=False), flush=True)
        await asyncio.sleep(args.reconnect_delay)
    print(json.dumps({"event": "direct_stopped"}, ensure_ascii=False), flush=True)


def main():
    parser = argparse.ArgumentParser(description="本地消费抖音直播消息，支持捕获握手的 WebSocket 和纯 HTTP 模式")
    parser.add_argument("--port", type=int, default=9222, help="用于刷新并捕获握手的 Chrome CDP 端口")
    parser.add_argument("--ws-url", help="已捕获的 WebSocket URL；提供后不连接 Chrome")
    parser.add_argument("--cookie-file", help="Cookie 文本文件，供 --ws-url 或 --local-http 使用")
    parser.add_argument("--local-http", action="store_true", help="纯本地 HTTP 长轮询模式，不连接 Chrome/WebSocket")
    parser.add_argument("--room-url", default="https://live.douyin.com/594976188049", help="直播间 URL，配合 --local-http 使用")
    parser.add_argument("--save-cookie")
    parser.add_argument("--save-ws-url")
    parser.add_argument("--method", action="append")
    parser.add_argument("--output", help="可选 JSONL 输出路径")
    parser.add_argument("--duration", type=float, default=None, help="运行秒数；省略则持续运行")
    parser.add_argument("--reload-wait", type=float, default=4)
    parser.add_argument("--reconnect-delay", type=float, default=2)
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
