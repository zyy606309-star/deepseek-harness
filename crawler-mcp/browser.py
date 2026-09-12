"""
Crawler-MCP Browser Manager
==========================
功能：
1. 请求监听 - 自动拦截所有 XHR/Fetch，获取 URL、Headers、Body
2. DevTools 控制 - Console 日志捕获、XHR 断点、JS 断点、执行代码
3. 浏览器控制 - 点击、输入、滚动、截图、导航
"""

import asyncio
import base64
import gzip
import os
import subprocess
import json
import shutil
import hashlib
from datetime import datetime
from pathlib import Path
from pyppeteer import connect


class BrowserManager:
    def __init__(self):
        self._max_captured_requests = 5000
        self._max_console_logs = 2000
        self._browser = None
        self._page = None
        self._cdp = None  # CDP Session
        self._chrome_process = None  # 保存启动的 Chrome 进程

        # 请求监听数据
        self._requests = {}  # requestId -> request data
        self._captured_requests = []  # 完整的请求列表
        self._websocket_events = []
        self._special_network_events = []

        # Console 日志
        self._console_logs = []

        # 监听状态
        self._network_enabled = False
        self._console_enabled = False
        self._fetch_enabled = False
        self._fetch_auto_continue = True
        self._fetch_patterns = None
        self._paused_requests = {}
        self._request_waiters = []
        self._response_waiters = []
        self._console_waiters = []
        self._init_scripts = []
        self._init_script_ids = []
        self._fetch_listener_attached = False
        self._debugger_listener_attached = False
        self._paused_call_frames = []
        self._paused_reason = ""
        self._breakpoint_ids = set()
        self._xhr_breakpoints = set()
        self._connected_port = None
        self._recording_actions = False
        self._replaying_actions = False
        self._recorded_actions = []
        self._page_sessions = {}
        self._live_stream = None

    @staticmethod
    def _page_session_key(page):
        target = getattr(page, "target", None)
        target_id = getattr(target, "_targetId", None)
        return str(target_id or id(page))

    def _save_page_session(self):
        if not self._page:
            return
        key = self._page_session_key(self._page)
        self._page_sessions[key] = {
            "url": self._page.url,
            "requests": dict(self._requests),
            "capturedRequests": list(self._captured_requests),
            "consoleLogs": list(self._console_logs),
            "websocketEvents": list(self._websocket_events),
            "specialNetworkEvents": list(self._special_network_events),
        }

    def _restore_page_session(self, page):
        state = self._page_sessions.get(self._page_session_key(page))
        if not state:
            return
        self._requests = dict(state.get("requests", {}))
        self._captured_requests = list(state.get("capturedRequests", []))
        self._console_logs = list(state.get("consoleLogs", []))
        self._websocket_events = list(state.get("websocketEvents", []))
        self._special_network_events = list(state.get("specialNetworkEvents", []))

    def _record_action(self, action, **payload):
        if self._recording_actions and not self._replaying_actions:
            self._recorded_actions.append({
                "action": action,
                "timestamp": datetime.now().isoformat(),
                **payload,
            })

    def _reset_session_state(self):
        """切换页面或重新连接时重置监听状态"""
        self._network_enabled = False
        self._console_enabled = False
        self._fetch_enabled = False
        self._paused_requests = {}
        self._fetch_listener_attached = False
        self._debugger_listener_attached = False
        self._paused_call_frames = []
        self._paused_reason = ""
        self._breakpoint_ids = set()
        self._xhr_breakpoints = set()
        self._init_script_ids = []
        self._requests.clear()
        self._captured_requests.clear()
        self._console_logs.clear()
        self._websocket_events.clear()
        self._special_network_events.clear()
        for waiter in (*self._request_waiters, *self._response_waiters, *self._console_waiters):
            future = waiter.get("future")
            if future is not None and not future.done():
                future.cancel()
        self._request_waiters.clear()
        self._response_waiters.clear()
        self._console_waiters.clear()

    async def _attach_to_page(self, page):
        """将当前会话绑定到指定页面并开启监听"""
        if self._page is not None and self._page != page:
            self._save_page_session()
        self._page = page

        # 禁用页面的 viewport 设置，让页面跟随浏览器窗口
        try:
            self._page._emulationManager._emulatingMobile = False
            self._page._emulationManager._hasTouch = False
        except Exception:
            pass

        # 创建 CDP Session
        self._cdp = await self._page.target.createCDPSession()

        # 禁用 viewport 覆盖，让页面跟随浏览器窗口真实尺寸
        try:
            await self._cdp.send("Emulation.setDeviceMetricsOverride", {
                "width": 0,
                "height": 0,
                "deviceScaleFactor": 0,
                "mobile": False
            })
        except Exception:
            pass

        self._reset_session_state()
        self._restore_page_session(page)
        await self._enable_network()
        await self._enable_console()
        await self._restore_init_scripts()

    async def _list_pages(self):
        """列出当前浏览器中的页面"""
        if not self._browser:
            return []

        pages = await self._browser.pages()
        results = []
        for index, page in enumerate(pages):
            url = page.url or "about:blank"
            title = ""
            try:
                title = await page.title()
            except Exception:
                title = ""

            results.append({
                "index": index,
                "title": title,
                "url": url,
                "isCurrent": page == self._page,
            })

        return results

    async def _pick_default_page(self):
        """优先选择可交互的普通页面，而不是 chrome:// 内部页"""
        pages = await self._browser.pages()
        if not pages:
            return await self._browser.newPage()

        def score(page):
            url = page.url or ""
            if url.startswith(("http://", "https://")):
                return 3
            if url == "about:blank":
                return 2
            return 1

        return sorted(pages, key=score, reverse=True)[0]

    def _find_chrome_path(self):
        """查找 Chrome 安装路径"""
        paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        ]
        for p in paths:
            if os.path.exists(p):
                return p
        return None

    async def _get_debug_metadata(self, port, timeout=0.35):
        """Read Chrome debug metadata without blocking the asyncio event loop."""
        import requests

        def fetch():
            try:
                response = requests.get(
                    f"http://127.0.0.1:{port}/json/version",
                    timeout=timeout,
                )
                response.raise_for_status()
                return response.json()
            except (requests.RequestException, ValueError):
                return None

        return await asyncio.to_thread(fetch)

    async def _wait_for_debug_port(self, port, timeout=5.0):
        deadline = asyncio.get_running_loop().time() + timeout
        while asyncio.get_running_loop().time() < deadline:
            metadata = await self._get_debug_metadata(port)
            if metadata and metadata.get("webSocketDebuggerUrl"):
                return metadata
            await asyncio.sleep(0.05)
        return None

    # ==================== 浏览器启动和连接 ====================

    async def launch_real_chrome(self, port=9222, url=None):
        """启动真实的 Chrome 浏览器（支持完整 DevTools）"""
        started_at = asyncio.get_running_loop().time()
        existing = await self._get_debug_metadata(port)
        if existing and existing.get("webSocketDebuggerUrl"):
            return {
                "success": True,
                "port": port,
                "reused": True,
                "chrome_version": existing.get("Browser", "unknown"),
                "startup_ms": round((asyncio.get_running_loop().time() - started_at) * 1000),
                "message": f"调试端口 {port} 已就绪，复用现有 Chrome",
            }

        chrome = self._find_chrome_path()
        if not chrome:
            return {"error": "未找到 Chrome 浏览器"}

        user_dir = os.path.join(os.environ.get("TEMP", "C:\\temp"), f"chrome_debug_{port}")
        cmd = [
            chrome,
            f"--remote-debugging-port={port}",
            f"--user-data-dir={user_dir}",
            "--no-first-run",
            "--no-default-browser-check",
        ]
        if url:
            cmd.append(url)

        self._chrome_process = subprocess.Popen(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )

        metadata = await self._wait_for_debug_port(port)
        if not metadata:
            return {"error": f"Chrome 已启动，但调试端口 {port} 在 5 秒内未就绪"}
        return {
            "success": True,
            "port": port,
            "reused": False,
            "chrome_version": metadata.get("Browser", "unknown"),
            "startup_ms": round((asyncio.get_running_loop().time() - started_at) * 1000),
            "message": f"Chrome 已启动，调试端口: {port}",
        }

    async def connect_browser(self, port=9222):
        """连接到已启动的浏览器，自动开启请求监听和 Console 捕获"""
        try:
            if self._browser and self._page and self._connected_port == port:
                return {
                    "success": True,
                    "reused": True,
                    "message": "复用现有浏览器连接",
                    "current_url": self._page.url,
                }

            self._save_page_session()
            data = await self._get_debug_metadata(port, timeout=1.0)
            if not data:
                return {"error": f"无法连接到端口 {port}，请先启动 Chrome"}
            ws_url = data.get("webSocketDebuggerUrl")

            if not ws_url:
                return {"error": "无法获取 WebSocket URL"}

            # 连接浏览器，禁用默认 viewport 以保持浏览器原始窗口大小
            self._browser = await connect(browserWSEndpoint=ws_url, defaultViewport=None)
            self._connected_port = port

            # 获取优先级最高的普通页面
            page = await self._pick_default_page()
            await self._attach_to_page(page)

            return {
                "success": True,
                "message": "已连接浏览器，请求监听和 Console 捕获已开启",
                "chrome_version": data.get("Browser", "unknown"),
                "current_url": self._page.url
            }

        except Exception as e:
            return {"error": f"连接失败: {str(e)}"}

    async def open_browser(self, url=None, port=9222):
        """Ensure Chrome is running, connect CDP, and optionally navigate in one call."""
        started_at = asyncio.get_running_loop().time()
        launch_result = await self.launch_real_chrome(port=port, url=url)
        if not launch_result.get("success"):
            return launch_result

        connect_result = await self.connect_browser(port=port)
        if not connect_result.get("success"):
            return connect_result

        if url and self._page and self._page.url != url:
            navigate_result = await self.navigate(url)
            if not navigate_result.get("success"):
                return navigate_result

        return {
            "success": True,
            "port": port,
            "url": self._page.url if self._page else url,
            "chrome_version": launch_result.get("chrome_version") or connect_result.get("chrome_version"),
            "launched": not launch_result.get("reused", False),
            "connection_reused": connect_result.get("reused", False),
            "elapsed_ms": round((asyncio.get_running_loop().time() - started_at) * 1000),
        }

    async def reconnect_browser(self):
        """使用上次端口重新建立 CDP 连接。"""
        if not self._connected_port:
            return {"error": "没有可重连的端口"}
        return await self.connect_browser(self._connected_port)

    async def probe_capabilities(self):
        tools = {}
        for name in ("adb", "frida", "objection", "mitmproxy", "jadx", "apktool"):
            path = shutil.which(name)
            info = {"available": bool(path), "path": path}
            if path:
                for args in (("--version",), ("version",), ("-version",)):
                    try:
                        proc = subprocess.run([path, *args], capture_output=True, text=True, timeout=3)
                        output = (proc.stdout or proc.stderr).strip()
                        if output:
                            info["version"] = output.splitlines()[0][:300]
                            break
                    except (OSError, subprocess.SubprocessError):
                        pass
            tools[name] = info
        cdp = []
        if self._cdp:
            cdp = ["Network", "Runtime", "Debugger", "Fetch", "Page", "DOMDebugger"]
        return {
            "success": True,
            "cdpDomains": cdp,
            "externalTools": tools,
            "webTransport": False,
            "serviceWorker": "partial",
            "note": "External tools are capability probes only; no process is started.",
        }

    async def adb_devices(self, timeout=10000):
        """List connected Android devices without changing device state."""
        adb = shutil.which("adb")
        if not adb:
            return {"success": False, "error": "未找到 adb"}
        try:
            proc = await asyncio.to_thread(
                subprocess.run, [adb, "devices", "-l"], capture_output=True, text=True,
                timeout=max(1, int(timeout) / 1000), check=False,
            )
            lines = []
            for raw in proc.stdout.splitlines()[1:]:
                raw = raw.strip()
                if not raw:
                    continue
                parts = raw.split()
                lines.append({"serial": parts[0], "state": parts[1] if len(parts) > 1 else "unknown", "details": parts[2:]})
            return {"success": proc.returncode == 0, "devices": lines, "stderr": proc.stderr.strip(), "returncode": proc.returncode}
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "adb devices 超时", "timeout": timeout}
        except OSError as e:
            return {"success": False, "error": str(e)}

    async def find_signature_candidates(self, keywords=None):
        """Heuristically locate likely signature globals and script resources."""
        if not self._page:
            return {"error": "未连接浏览器"}
        keywords = keywords or ["sign", "signature", "webmsxyw", "x-s", "x-t", "token", "encrypt"]
        js = """(keywords) => ({
            globals: Object.keys(window).filter(k => keywords.some(x => k.toLowerCase().includes(x.toLowerCase()))).slice(0, 200),
            scripts: Array.from(document.scripts).map(s => s.src).filter(Boolean),
            resourceHints: performance.getEntriesByType('resource').map(x => x.name).filter(x => /\\.js(?:[?#]|$)/i.test(x)).slice(-200)
        })"""
        try:
            result = await self._page.evaluate(js, keywords)
            return {"success": True, "keywords": keywords, **result}
        except Exception as e:
            return {"error": f"查找签名候选失败: {str(e)}"}

    async def wait_for_new_tab(self, timeout=60):
        """等待用户创建新标签页，自动切换并开启监听"""
        if not self._browser:
            return {"error": "浏览器未连接"}

        start_pages = await self._browser.pages()
        start_count = len(start_pages)

        for _ in range(timeout * 2):
            await asyncio.sleep(0.5)
            current_pages = await self._browser.pages()
            if len(current_pages) > start_count:
                await self._attach_to_page(current_pages[-1])

                return {
                    "success": True,
                    "message": "检测到新标签页，已切换并开启监听",
                    "url": self._page.url
                }

        return {"error": "等待超时，未检测到新标签页"}

    # ==================== 请求监听 ====================

    async def _enable_network(self):
        """启用网络监听"""
        if self._network_enabled:
            return

        # 启用 Network 域
        await self._cdp.send("Network.enable")

        # 监听请求发送
        self._cdp.on("Network.requestWillBeSent", self._on_request)

        # 监听响应接收
        self._cdp.on("Network.responseReceived", self._on_response)
        self._cdp.on("Network.loadingFailed", self._on_loading_failed)
        self._cdp.on("Network.webSocketCreated", self._on_websocket_created)
        self._cdp.on("Network.webSocketWillSendHandshakeRequest", self._on_websocket_handshake)
        self._cdp.on("Network.webSocketFrameSent", lambda event: self._on_websocket_frame(event, "sent"))
        self._cdp.on("Network.webSocketFrameReceived", lambda event: self._on_websocket_frame(event, "received"))
        self._cdp.on("Network.webSocketClosed", self._on_websocket_closed)
        self._cdp.on("Network.webTransportCreated", self._on_web_transport)
        self._cdp.on("Network.webTransportConnectionEstablished", self._on_web_transport)
        self._cdp.on("Network.webTransportClosed", self._on_web_transport)
        self._cdp.on("Target.attachedToTarget", self._on_target_attached)
        self._cdp.on("Target.detachedFromTarget", self._on_target_detached)

        self._network_enabled = True

    async def _restore_init_scripts(self):
        """在新页面会话上重新注入初始化脚本"""
        if not self._cdp or not self._init_scripts:
            return

        try:
            await self._cdp.send("Page.enable")
        except Exception:
            pass

        for script in self._init_scripts:
            try:
                result = await self._cdp.send("Page.addScriptToEvaluateOnNewDocument", {"source": script})
                self._init_script_ids.append(result.get("identifier"))
            except Exception:
                pass

    def _on_request(self, event):
        """处理请求事件"""
        request_id = event.get("requestId")
        request = event.get("request", {})
        req_type = event.get("type", "")

        # 捕获所有类型的请求（XHR、Fetch、Script、Document、Stylesheet、Image等）
        self._requests[request_id] = {
            "requestId": request_id,
            "url": request.get("url"),
            "method": request.get("method"),
            "headers": request.get("headers", {}),
            "postData": request.get("postData"),
            "type": req_type,
            "timestamp": datetime.now().isoformat(),
            "response": None
        }
        self._notify_request_waiters(self._requests[request_id])

    def _on_response(self, event):
        """处理响应事件"""
        request_id = event.get("requestId")
        response = event.get("response", {})

        if request_id in self._requests:
            self._requests[request_id]["response"] = {
                "status": response.get("status"),
                "statusText": response.get("statusText"),
                "headers": response.get("headers", {}),
                "mimeType": response.get("mimeType")
            }
            # 移动到已完成列表
            completed_request = self._requests.pop(request_id)
            self._captured_requests.append(completed_request)
            if len(self._captured_requests) > self._max_captured_requests:
                del self._captured_requests[:-self._max_captured_requests]
            self._notify_response_waiters(completed_request)

    def _on_loading_failed(self, event):
        """记录没有正常收到响应的请求，保留失败原因供逆向定位。"""
        request_id = event.get("requestId")
        request = self._requests.pop(request_id, None)
        if not request:
            return
        request["failed"] = True
        request["failure"] = {
            "errorText": event.get("errorText"),
            "canceled": event.get("canceled", False),
            "blockedReason": event.get("blockedReason"),
            "corsError": event.get("corsError"),
        }
        self._captured_requests.append(request)
        if len(self._captured_requests) > self._max_captured_requests:
            del self._captured_requests[:-self._max_captured_requests]
        self._notify_response_waiters(request)

    def _record_websocket(self, event_type, event, direction=None):
        item = {"event": event_type, "timestamp": datetime.now().isoformat()}
        if direction:
            item["direction"] = direction
        for key in ("requestId", "url", "timestamp", "response", "opcode", "mask", "errorMessage"):
            if key in event:
                item[key] = event[key]
        if "response" in event and isinstance(event["response"], dict):
            item["payloadData"] = event["response"].get("payloadData", "")
        elif "request" in event and isinstance(event["request"], dict):
            item["payloadData"] = event["request"].get("payloadData", "")
        self._websocket_events.append(item)
        if len(self._websocket_events) > self._max_captured_requests:
            del self._websocket_events[:-self._max_captured_requests]

    def _on_websocket_created(self, event):
        self._record_websocket("created", event)

    def _on_websocket_handshake(self, event):
        self._record_websocket("handshake", event)

    def _on_websocket_frame(self, event, direction="received"):
        self._record_websocket("frame", event, direction=direction)

    def _on_websocket_closed(self, event):
        self._record_websocket("closed", event)

    def _on_web_transport(self, event):
        item = {"event": event.get("type", "webTransport"), "timestamp": datetime.now().isoformat()}
        item.update({key: value for key, value in event.items() if key != "type"})
        self._special_network_events.append(item)

    def _on_target_attached(self, event):
        self._special_network_events.append({"event": "targetAttached", "timestamp": datetime.now().isoformat(), "target": event})

    def _on_target_detached(self, event):
        self._special_network_events.append({"event": "targetDetached", "timestamp": datetime.now().isoformat(), "target": event})

    async def get_websocket_events(self, request_id=None, limit=100):
        events = self._websocket_events
        if request_id:
            events = [item for item in events if item.get("requestId") == request_id]
        return {"success": True, "count": len(events[-limit:]), "events": events[-limit:]}

    @staticmethod
    def _proto_varint(data, offset):
        value = 0
        shift = 0
        while offset < len(data):
            byte = data[offset]
            offset += 1
            value |= (byte & 0x7F) << shift
            if byte < 0x80:
                return value, offset
            shift += 7
            if shift > 70:
                raise ValueError("protobuf varint too long")
        raise ValueError("truncated protobuf varint")

    @classmethod
    def _proto_fields(cls, data):
        fields = []
        offset = 0
        while offset < len(data):
            try:
                tag, offset = cls._proto_varint(data, offset)
                number, wire_type = tag >> 3, tag & 7
                if wire_type == 0:
                    value, offset = cls._proto_varint(data, offset)
                elif wire_type == 1:
                    value, offset = data[offset:offset + 8], offset + 8
                elif wire_type == 2:
                    length, offset = cls._proto_varint(data, offset)
                    value, offset = data[offset:offset + length], offset + length
                elif wire_type == 5:
                    value, offset = data[offset:offset + 4], offset + 4
                else:
                    break
                fields.append((number, wire_type, value))
            except (ValueError, IndexError):
                break
        return fields

    @classmethod
    def _decode_live_frame(cls, payload_data):
        """Decode Douyin Webcast's outer protobuf + gzip message envelope."""
        try:
            raw = base64.b64decode(payload_data)
            gzip_offset = raw.find(b"\x1f\x8b")
            if gzip_offset < 0:
                return None
            outer = cls._proto_fields(raw[:gzip_offset])
            body = gzip.decompress(raw[gzip_offset:])
            messages = []
            for number, wire_type, envelope in cls._proto_fields(body):
                if number != 1 or wire_type != 2:
                    continue
                envelope_fields = cls._proto_fields(envelope)
                method = next((value.decode("utf-8", "replace") for no, wt, value in envelope_fields if no == 1 and wt == 2), "")
                payload = next((value for no, wt, value in envelope_fields if no == 2 and wt == 2), b"")
                payload_fields = cls._proto_fields(payload)
                content = next((value.decode("utf-8", "replace") for no, wt, value in payload_fields if no == 3 and wt == 2), "")
                user_blob = next((value for no, wt, value in payload_fields if no == 2 and wt == 2), b"")
                user_fields = cls._proto_fields(user_blob)
                user_id = next((value for no, wt, value in user_fields if no == 1 and wt == 0), None)
                user_name = next((value.decode("utf-8", "replace") for no, wt, value in user_fields if no == 3 and wt == 2), "")
                if not user_name:
                    user_name = next((value.decode("utf-8", "replace") for no, wt, value in user_fields if no == 2 and wt == 2), "")
                messages.append({
                    "method": method,
                    "content": content,
                    "userId": str(user_id) if user_id is not None else None,
                    "userName": user_name,
                    "payloadLength": len(payload),
                })
            metadata = []
            for no, wt, value in outer:
                if no == 5 and wt == 2:
                    pair = cls._proto_fields(value)
                    if len(pair) >= 2 and isinstance(pair[0][2], bytes) and isinstance(pair[1][2], bytes):
                        metadata.append({"name": pair[0][2].decode("utf-8", "replace"), "value": pair[1][2].decode("utf-8", "replace")})
            return {"messages": messages, "metadata": metadata, "bodyLength": len(body)}
        except (ValueError, OSError, EOFError, gzip.BadGzipFile):
            return None

    async def start_live_stream(self, output_path=None, websocket_url_pattern="webcast", include_raw=True, wait_timeout=15000):
        if not self._page:
            return {"error": "未连接浏览器"}
        request_id = None
        for event in reversed(self._websocket_events):
            if event.get("event") == "created" and websocket_url_pattern in event.get("url", ""):
                request_id = event.get("requestId")
                break
        if not request_id:
            deadline = asyncio.get_running_loop().time() + max(0.1, min(float(wait_timeout) / 1000, 60.0))
            while asyncio.get_running_loop().time() < deadline and not request_id:
                await asyncio.sleep(0.25)
                for event in reversed(self._websocket_events):
                    if event.get("event") == "created" and websocket_url_pattern in event.get("url", ""):
                        request_id = event.get("requestId")
                        break
        if not request_id:
            return {"error": "未找到匹配的直播 WebSocket，请先打开直播间并等待连接建立", "waitTimeout": wait_timeout}
        path = Path(output_path) if output_path else None
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)
        self._live_stream = {"requestId": request_id, "eventIndex": len(self._websocket_events), "path": str(path) if path else None, "includeRaw": bool(include_raw), "urlPattern": websocket_url_pattern}
        return {"success": True, "requestId": request_id, "outputPath": str(path) if path else None, "eventIndex": self._live_stream["eventIndex"]}

    async def read_live_messages(self, duration=5, max_messages=100, poll_interval=0.25, methods=None):
        if not self._live_stream:
            return {"error": "直播流未启动，请先调用 start_live_stream"}
        state = self._live_stream
        deadline = asyncio.get_running_loop().time() + max(0.1, min(float(duration), 300.0))
        messages = []
        method_filter = set(methods or [])
        output = Path(state["path"]) if state.get("path") else None
        while asyncio.get_running_loop().time() < deadline and len(messages) < max(1, int(max_messages)):
            events = self._websocket_events[state["eventIndex"]:]
            state["eventIndex"] = len(self._websocket_events)
            closed = any(event.get("event") == "closed" and event.get("requestId") == state["requestId"] for event in events)
            for event in events:
                if event.get("event") != "frame" or event.get("requestId") != state["requestId"]:
                    continue
                decoded = self._decode_live_frame(event.get("payloadData", ""))
                if not decoded:
                    continue
                for item in decoded["messages"]:
                    if method_filter and item.get("method") not in method_filter:
                        continue
                    record = {"timestamp": event.get("timestamp"), "requestId": state["requestId"], **item}
                    messages.append(record)
                    if output:
                        with output.open("a", encoding="utf-8") as handle:
                            handle.write(json.dumps({"record": record, "rawFrame": event.get("payloadData") if state.get("includeRaw") else None}, ensure_ascii=False) + "\n")
                    if len(messages) >= max_messages:
                        break
                if len(messages) >= max_messages:
                    break
            if len(messages) < max_messages:
                if closed:
                    for event in reversed(self._websocket_events):
                        if event.get("event") == "created" and state.get("urlPattern", "webcast") in event.get("url", ""):
                            state["requestId"] = event.get("requestId")
                            break
                await asyncio.sleep(max(0.05, min(float(poll_interval), 2.0)))
        return {"success": True, "count": len(messages), "messages": messages, "requestId": state["requestId"], "nextEventIndex": state["eventIndex"]}

    async def stop_live_stream(self):
        if not self._live_stream:
            return {"success": True, "stopped": False}
        state = self._live_stream
        self._live_stream = None
        return {"success": True, "stopped": True, "requestId": state.get("requestId"), "outputPath": state.get("path")}

    async def get_special_network_events(self, limit=100):
        return {"success": True, "count": len(self._special_network_events[-limit:]), "events": self._special_network_events[-limit:]}

    def _matches_pattern(self, value, pattern=None):
        if not pattern:
            return True
        return pattern in (value or "")

    def _notify_request_waiters(self, request_data):
        matched = []
        for waiter in self._request_waiters:
            if self._matches_pattern(request_data.get("url"), waiter["url_pattern"]):
                if not waiter["future"].done():
                    waiter["future"].set_result(request_data)
                matched.append(waiter)

        for waiter in matched:
            self._request_waiters.remove(waiter)

    def _notify_response_waiters(self, request_data):
        matched = []
        for waiter in self._response_waiters:
            if self._matches_pattern(request_data.get("url"), waiter["url_pattern"]):
                status = request_data.get("response", {}).get("status")
                if waiter["status"] is None or waiter["status"] == status:
                    if not waiter["future"].done():
                        waiter["future"].set_result(request_data)
                    matched.append(waiter)

        for waiter in matched:
            self._response_waiters.remove(waiter)

    def _notify_console_waiters(self, log_entry):
        matched = []
        for waiter in self._console_waiters:
            if self._matches_pattern(log_entry.get("message"), waiter["pattern"]):
                if waiter["type_filter"] is None or waiter["type_filter"] == log_entry.get("type"):
                    if not waiter["future"].done():
                        waiter["future"].set_result(log_entry)
                    matched.append(waiter)

        for waiter in matched:
            self._console_waiters.remove(waiter)

    async def _set_fetch_enabled(self, enabled, patterns=None, auto_continue=True):
        if not self._cdp:
            return {"error": "未连接浏览器"}

        if enabled:
            self._fetch_patterns = patterns or [{"urlPattern": "*"}]
            self._fetch_auto_continue = auto_continue
            await self._cdp.send("Fetch.enable", {"patterns": self._fetch_patterns})
            if not self._fetch_listener_attached:
                self._cdp.on("Fetch.requestPaused", self._on_request_paused)
                self._fetch_listener_attached = True
            self._fetch_enabled = True
            return {
                "success": True,
                "enabled": True,
                "autoContinue": auto_continue,
                "patterns": self._fetch_patterns,
            }

        if self._fetch_enabled:
            try:
                await self._cdp.send("Fetch.disable")
            except Exception:
                pass
        self._fetch_enabled = False
        self._paused_requests.clear()
        return {"success": True, "enabled": False}

    def _on_request_paused(self, event):
        request_id = event.get("requestId")
        request = event.get("request", {})
        paused = {
            "requestId": request_id,
            "url": request.get("url"),
            "method": request.get("method"),
            "headers": request.get("headers", {}),
            "postData": request.get("postData"),
            "resourceType": event.get("resourceType"),
            "networkId": event.get("networkId"),
            "timestamp": datetime.now().isoformat(),
        }
        self._paused_requests[request_id] = paused

        if self._fetch_auto_continue:
            asyncio.create_task(self._continue_paused_request(request_id))

    async def get_captured_requests(self, url_filter=None, limit=20):
        """获取捕获的请求列表"""
        if url_filter:
            requests = [r for r in self._captured_requests if url_filter in r.get("url", "")]
            requests = requests[-limit:] if limit else requests
        else:
            requests = self._captured_requests[-limit:] if limit else list(self._captured_requests)

        return {
            "success": True,
            "count": len(requests),
            "requests": requests
        }

    async def wait_for_request(self, url_pattern=None, timeout=10000):
        """等待匹配的请求发出"""
        if not self._page:
            return {"error": "未连接浏览器"}

        for request in reversed(self._captured_requests):
            if self._matches_pattern(request.get("url"), url_pattern):
                return {"success": True, "request": request, "source": "history"}
        for request in self._requests.values():
            if self._matches_pattern(request.get("url"), url_pattern):
                return {"success": True, "request": request, "source": "inflight"}

        loop = asyncio.get_running_loop()
        future = loop.create_future()
        waiter = {"future": future, "url_pattern": url_pattern}
        self._request_waiters.append(waiter)

        try:
            request = await asyncio.wait_for(future, timeout=timeout / 1000)
            return {"success": True, "request": request, "source": "live"}
        except asyncio.TimeoutError:
            if waiter in self._request_waiters:
                self._request_waiters.remove(waiter)
            return {"error": "等待请求超时", "urlPattern": url_pattern, "timeout": timeout}

    async def wait_for_response(self, url_pattern=None, status=None, timeout=10000):
        """等待匹配的响应完成"""
        if not self._page:
            return {"error": "未连接浏览器"}

        for request in reversed(self._captured_requests):
            if self._matches_pattern(request.get("url"), url_pattern):
                response_status = request.get("response", {}).get("status")
                if status is None or status == response_status:
                    return {"success": True, "request": request, "source": "history"}

        loop = asyncio.get_running_loop()
        future = loop.create_future()
        waiter = {"future": future, "url_pattern": url_pattern, "status": status}
        self._response_waiters.append(waiter)

        try:
            request = await asyncio.wait_for(future, timeout=timeout / 1000)
            return {"success": True, "request": request, "source": "live"}
        except asyncio.TimeoutError:
            if waiter in self._response_waiters:
                self._response_waiters.remove(waiter)
            return {
                "error": "等待响应超时",
                "urlPattern": url_pattern,
                "status": status,
                "timeout": timeout,
            }

    async def get_response_body(self, request_id, max_preview=2000, include_body=False):
        """获取指定请求的响应内容"""
        max_preview = max(0, min(int(max_preview), 1_000_000))
        try:
            result = await self._cdp.send("Network.getResponseBody", {"requestId": request_id})
            body = result.get("body")
            base64_encoded = result.get("base64Encoded", False)
            decoded_preview = None

            if body is not None:
                try:
                    if base64_encoded:
                        decoded_bytes = base64.b64decode(body)
                        decoded_preview = decoded_bytes.decode("utf-8", errors="replace")[:max_preview]
                    else:
                        decoded_preview = body[:max_preview]
                except Exception:
                    decoded_preview = None

            return {
                "success": True,
                "body": body if include_body else None,
                "bodyIncluded": include_body,
                "bodyLength": len(body) if body is not None else 0,
                "base64Encoded": base64_encoded,
                "decodedPreview": decoded_preview,
            }
        except Exception as e:
            return {"error": str(e)}

    async def get_request_body(self, request_id, max_preview=2000, include_body=False):
        """主动读取请求体，适用于 requestWillBeSent 未带完整 postData 的情况。"""
        max_preview = max(0, min(int(max_preview), 1_000_000))
        if not self._cdp:
            return {"error": "未连接浏览器"}
        try:
            result = await self._cdp.send("Network.getRequestPostData", {"requestId": request_id})
            body = result.get("postData", "")
            return {
                "success": True,
                "body": body if include_body else None,
                "bodyIncluded": include_body,
                "bodyLength": len(body),
                "preview": body[:max_preview],
            }
        except Exception as e:
            return {"error": f"读取请求体失败: {str(e)}", "requestId": request_id}

    async def save_request_body(self, request_id, path):
        """主动读取并保存完整请求体。"""
        result = await self.get_request_body(request_id, include_body=True)
        if not result.get("success"):
            return result
        try:
            output = Path(path)
            output.parent.mkdir(parents=True, exist_ok=True)
            data = (result.get("body") or "").encode("utf-8")
            output.write_bytes(data)
            return {"success": True, "path": str(output), "bytes": len(data)}
        except Exception as e:
            return {"error": f"保存请求体失败: {str(e)}", "path": path}

    async def save_response_body(self, request_id, path):
        """把完整响应体保存到任务目录，避免把大 body 返回到 MCP 上下文。"""
        if not self._cdp:
            return {"error": "未连接浏览器"}
        try:
            result = await self._cdp.send("Network.getResponseBody", {"requestId": request_id})
            body = result.get("body", "")
            data = base64.b64decode(body) if result.get("base64Encoded") else body.encode("utf-8")
            output = Path(path)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(data)
            return {"success": True, "path": str(output), "bytes": len(data), "base64Encoded": result.get("base64Encoded", False)}
        except Exception as e:
            return {"error": f"保存响应体失败: {str(e)}", "path": path}

    async def list_pages(self):
        """列出当前浏览器页面，便于选择正确标签页"""
        if not self._browser:
            return {"error": "浏览器未连接"}

        pages = await self._list_pages()
        return {"success": True, "count": len(pages), "pages": pages}

    async def switch_page(self, index):
        """切换当前操作页面"""
        if not self._browser:
            return {"error": "浏览器未连接"}

        pages = await self._browser.pages()
        if index < 0 or index >= len(pages):
            return {"error": f"页面索引越界: {index}"}

        await self._attach_to_page(pages[index])
        return {
            "success": True,
            "index": index,
            "url": self._page.url,
            "message": "已切换当前页面"
        }

    async def get_page_sessions(self):
        """Return per-page evidence counts without exposing raw authenticated data."""
        if not self._browser:
            return {"error": "浏览器未连接"}
        self._save_page_session()
        pages = await self._browser.pages()
        sessions = []
        for index, page in enumerate(pages):
            state = self._page_sessions.get(self._page_session_key(page), {})
            sessions.append({
                "index": index,
                "url": page.url,
                "isCurrent": page == self._page,
                "requestCount": len(state.get("capturedRequests", [])) if page != self._page else len(self._captured_requests),
                "consoleCount": len(state.get("consoleLogs", [])) if page != self._page else len(self._console_logs),
                "websocketCount": len(state.get("websocketEvents", [])) if page != self._page else len(self._websocket_events),
                "specialEventCount": len(state.get("specialNetworkEvents", [])) if page != self._page else len(self._special_network_events),
            })
        return {"success": True, "sessions": sessions}

    async def clear_captured_requests(self):
        """清空已捕获的请求"""
        self._captured_requests.clear()
        self._requests.clear()
        return {"success": True, "message": "已清空请求记录"}

    async def set_request_interception(self, enabled=True, url_pattern="*", auto_continue=True):
        """启用或关闭 Fetch 请求拦截"""
        patterns = [{"urlPattern": url_pattern or "*"}] if enabled else None
        return await self._set_fetch_enabled(enabled, patterns=patterns, auto_continue=auto_continue)

    async def get_pending_interceptions(self):
        """返回当前挂起的拦截请求"""
        pending = list(self._paused_requests.values())
        return {"success": True, "count": len(pending), "requests": pending}

    async def _continue_paused_request(self, request_id, url=None, method=None, post_data=None, headers=None):
        payload = {"requestId": request_id}
        if url is not None:
            payload["url"] = url
        if method is not None:
            payload["method"] = method
        if post_data is not None:
            payload["postData"] = post_data
        if headers is not None:
            payload["headers"] = [{"name": k, "value": str(v)} for k, v in headers.items()]

        await self._cdp.send("Fetch.continueRequest", payload)
        self._paused_requests.pop(request_id, None)
        return {"success": True, "requestId": request_id, "action": "continued"}

    async def continue_request(self, request_id, url=None, method=None, post_data=None, headers=None):
        """继续已暂停的请求，可选修改 url/method/body/headers"""
        if not self._cdp:
            return {"error": "未连接浏览器"}
        if request_id not in self._paused_requests:
            return {"error": f"未找到挂起请求: {request_id}"}

        try:
            return await self._continue_paused_request(
                request_id,
                url=url,
                method=method,
                post_data=post_data,
                headers=headers,
            )
        except Exception as e:
            return {"error": f"继续请求失败: {str(e)}", "requestId": request_id}

    async def abort_request(self, request_id, error_reason="Failed"):
        """终止已暂停的请求"""
        if not self._cdp:
            return {"error": "未连接浏览器"}
        if request_id not in self._paused_requests:
            return {"error": f"未找到挂起请求: {request_id}"}

        try:
            await self._cdp.send("Fetch.failRequest", {"requestId": request_id, "errorReason": error_reason})
            self._paused_requests.pop(request_id, None)
            return {"success": True, "requestId": request_id, "action": "aborted", "errorReason": error_reason}
        except Exception as e:
            return {"error": f"终止请求失败: {str(e)}", "requestId": request_id}

    async def fulfill_request(self, request_id, status=200, body="", headers=None, is_base64=False):
        """直接伪造响应返回给页面"""
        if not self._cdp:
            return {"error": "未连接浏览器"}
        if request_id not in self._paused_requests:
            return {"error": f"未找到挂起请求: {request_id}"}

        try:
            if is_base64:
                encoded_body = body
            else:
                encoded_body = base64.b64encode(body.encode("utf-8")).decode("ascii")

            response_headers = [{"name": k, "value": str(v)} for k, v in (headers or {}).items()]
            await self._cdp.send("Fetch.fulfillRequest", {
                "requestId": request_id,
                "responseCode": status,
                "body": encoded_body,
                "responseHeaders": response_headers,
            })
            self._paused_requests.pop(request_id, None)
            return {"success": True, "requestId": request_id, "action": "fulfilled", "status": status}
        except Exception as e:
            return {"error": f"伪造响应失败: {str(e)}", "requestId": request_id}

    # ==================== Console 日志捕获 ====================

    async def _enable_console(self):
        """启用 Console 日志捕获"""
        if self._console_enabled:
            return

        await self._cdp.send("Runtime.enable")
        self._cdp.on("Runtime.consoleAPICalled", self._on_console)
        self._console_enabled = True

    def _on_console(self, event):
        """处理 Console 事件"""
        log_type = event.get("type", "log")
        args = event.get("args", [])

        # 提取日志内容
        messages = []
        for arg in args:
            value = arg.get("value")
            if value is not None:
                messages.append(str(value))
            elif arg.get("type") == "object":
                # 对象类型，获取描述
                desc = arg.get("description", arg.get("className", "Object"))
                messages.append(desc)

            self._console_logs.append({
            "type": log_type,
            "message": " ".join(messages),
            "timestamp": datetime.now().isoformat()
        })
        self._notify_console_waiters(self._console_logs[-1])

    async def get_console_logs(self, limit=50, type_filter=None):
        """获取 Console 日志"""
        limit = max(0, min(int(limit), self._max_console_logs))
        logs = self._console_logs[-limit:]

        if type_filter:
            logs = [l for l in logs if l.get("type") == type_filter]

        return {
            "success": True,
            "count": len(logs),
            "logs": logs
        }

    async def clear_console_logs(self):
        """清空 Console 日志"""
        self._console_logs.clear()
        return {"success": True, "message": "已清空 Console 日志"}

    async def wait_for_console(self, pattern=None, type_filter=None, timeout=10000):
        """等待匹配的 console 日志"""
        if not self._page:
            return {"error": "未连接浏览器"}

        for log in reversed(self._console_logs):
            if self._matches_pattern(log.get("message"), pattern):
                if type_filter is None or type_filter == log.get("type"):
                    return {"success": True, "log": log, "source": "history"}

        loop = asyncio.get_running_loop()
        future = loop.create_future()
        waiter = {"future": future, "pattern": pattern, "type_filter": type_filter}
        self._console_waiters.append(waiter)

        try:
            log = await asyncio.wait_for(future, timeout=timeout / 1000)
            return {"success": True, "log": log, "source": "live"}
        except asyncio.TimeoutError:
            if waiter in self._console_waiters:
                self._console_waiters.remove(waiter)
            return {
                "error": "等待 Console 超时",
                "pattern": pattern,
                "typeFilter": type_filter,
                "timeout": timeout,
            }

    async def get_page_info(self):
        """返回当前页面基础状态"""
        if not self._page:
            return {"error": "未连接浏览器"}

        try:
            title = await self._page.title()
        except Exception:
            title = ""

        try:
            info = await self._page.evaluate(
                """(() => ({
                    url: location.href,
                    readyState: document.readyState,
                    referrer: document.referrer,
                    htmlLang: document.documentElement.lang || "",
                    viewport: {
                        width: window.innerWidth,
                        height: window.innerHeight,
                        devicePixelRatio: window.devicePixelRatio
                    },
                    documentSize: {
                        scrollWidth: document.documentElement.scrollWidth,
                        scrollHeight: document.documentElement.scrollHeight
                    },
                    cookieEnabled: navigator.cookieEnabled,
                    userAgent: navigator.userAgent
                }))()""",
                force_expr=True,
            )
        except Exception as e:
            return {"error": f"获取页面信息失败: {str(e)}"}

        info["title"] = title
        return {"success": True, "page": info}

    async def get_cookies(self):
        """读取当前页面 cookies"""
        if not self._page:
            return {"error": "未连接浏览器"}

        try:
            cookies = await self._page.cookies()
            return {"success": True, "count": len(cookies), "cookies": cookies}
        except Exception as e:
            return {"error": f"获取 cookies 失败: {str(e)}"}

    async def get_storage(self, storage_type="localStorage"):
        """读取 localStorage 或 sessionStorage"""
        if not self._page:
            return {"error": "未连接浏览器"}

        if storage_type not in {"localStorage", "sessionStorage"}:
            return {"error": f"不支持的 storage_type: {storage_type}"}

        try:
            data = await self._page.evaluate(
                f"""(() => {{
                    const storage = window[{json.dumps(storage_type)}];
                    const result = {{}};
                    for (let i = 0; i < storage.length; i += 1) {{
                        const key = storage.key(i);
                        result[key] = storage.getItem(key);
                    }}
                    return result;
                }})()""",
                force_expr=True,
            )
            return {"success": True, "storageType": storage_type, "count": len(data), "items": data}
        except Exception as e:
            return {"error": f"获取 {storage_type} 失败: {str(e)}"}

    async def dump_session(self, console_limit=20, include_storage=True, include_cookies=True):
        """导出当前页面调试会话快照，默认限制敏感和高体积数据。"""
        console_limit = max(0, min(int(console_limit), self._max_console_logs))
        if not self._page:
            return {"error": "未连接浏览器"}

        page_info = await self.get_page_info()
        cookies = await self.get_cookies() if include_cookies else {"cookies": []}
        local_storage = await self.get_storage("localStorage") if include_storage else {"items": {}}
        session_storage = await self.get_storage("sessionStorage") if include_storage else {"items": {}}
        console_logs = await self.get_console_logs(limit=console_limit)

        return {
            "success": True,
            "snapshot": {
                "page": page_info.get("page"),
                "cookies": cookies.get("cookies", []),
                "localStorage": local_storage.get("items", {}),
                "sessionStorage": session_storage.get("items", {}),
                "consoleLogs": console_logs.get("logs", []),
                "websocketEvents": self._websocket_events[-50:],
                "specialNetworkEvents": self._special_network_events[-50:],
            }
        }

    async def health_check(self):
        if not self._browser or not self._page or not self._cdp:
            return {"healthy": False, "reason": "browser/page/cdp not connected"}
        try:
            url = self._page.url
            await self._cdp.send("Runtime.evaluate", {"expression": "1+1", "returnByValue": True})
            return {"healthy": True, "url": url, "pageCount": len(await self._browser.pages())}
        except Exception as e:
            return {"healthy": False, "reason": str(e), "reconnectable": True}

    async def export_evidence(self, path, include_requests=True, include_console=True, include_websocket=True):
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        evidence = {
            "exportedAt": datetime.now().isoformat(),
            "page": (await self.get_page_info()).get("page"),
            "requests": self._captured_requests if include_requests else [],
            "consoleLogs": self._console_logs if include_console else [],
            "websocketEvents": self._websocket_events if include_websocket else [],
            "specialNetworkEvents": self._special_network_events,
            "actions": list(self._recorded_actions),
        }
        output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"success": True, "path": str(output), "requestCount": len(evidence["requests"]), "websocketCount": len(evidence["websocketEvents"])}

    async def diff_requests(self, baseline=None, current=None, baseline_path=None, current_path=None):
        def load(value, file_path):
            if value is not None:
                return value
            if file_path:
                return json.loads(Path(file_path).read_text(encoding="utf-8"))
            return []
        left = load(baseline, baseline_path)
        right = load(current, current_path)
        def key(item):
            return (item.get("method"), item.get("url"), item.get("type"))
        left_map = {key(item): item for item in left if isinstance(item, dict)}
        right_map = {key(item): item for item in right if isinstance(item, dict)}
        added = [right_map[k] for k in right_map.keys() - left_map.keys()]
        removed = [left_map[k] for k in left_map.keys() - right_map.keys()]
        def field_diff(a, b, path=""):
            if isinstance(a, dict) and isinstance(b, dict):
                changes = []
                for name in sorted(set(a) | set(b)):
                    child = f"{path}.{name}" if path else name
                    if name not in a:
                        changes.append({"path": child, "kind": "added", "current": b[name]})
                    elif name not in b:
                        changes.append({"path": child, "kind": "removed", "baseline": a[name]})
                    else:
                        changes.extend(field_diff(a[name], b[name], child))
                return changes
            if isinstance(a, list) and isinstance(b, list):
                changes = []
                for index in range(max(len(a), len(b))):
                    child = f"{path}[{index}]"
                    if index >= len(a):
                        changes.append({"path": child, "kind": "added", "current": b[index]})
                    elif index >= len(b):
                        changes.append({"path": child, "kind": "removed", "baseline": a[index]})
                    else:
                        changes.extend(field_diff(a[index], b[index], child))
                return changes
            return [] if a == b else [{"path": path, "kind": "changed", "baseline": a, "current": b}]

        def normalize_body(value):
            if not isinstance(value, str):
                return value
            try:
                return json.loads(value)
            except (TypeError, ValueError):
                return value

        changed = []
        for k in left_map.keys() & right_map.keys():
            a, b = left_map[k], right_map[k]
            details = []
            details.extend(field_diff(a.get("headers", {}), b.get("headers", {}), "headers"))
            details.extend(field_diff(normalize_body(a.get("postData")), normalize_body(b.get("postData")), "postData"))
            details.extend(field_diff(a.get("response", {}), b.get("response", {}), "response"))
            if details:
                changed.append({"key": k, "baseline": a, "current": b, "details": details})
        return {"success": True, "added": added, "removed": removed, "changed": changed, "summary": {"added": len(added), "removed": len(removed), "changed": len(changed)}}

    async def export_task_artifacts(self, directory, include_bodies=False):
        """Export a deterministic, reviewable task evidence directory."""
        root = Path(directory)
        root.mkdir(parents=True, exist_ok=True)
        network_path = root / "network.jsonl"
        runtime_path = root / "runtime-evidence.jsonl"
        report_path = root / "report.md"
        sessions_path = root / "page-sessions.json"
        manifest_path = root / "manifest.sha256"
        with network_path.open("w", encoding="utf-8") as handle:
            for item in self._captured_requests:
                handle.write(json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n")
        runtime_items = []
        runtime_items.extend({"source": "console", **item} for item in self._console_logs)
        runtime_items.extend({"source": "websocket", **item} for item in self._websocket_events)
        runtime_items.extend({"source": "special-network", **item} for item in self._special_network_events)
        runtime_items.extend({"source": "action", **item} for item in self._recorded_actions)
        with runtime_path.open("w", encoding="utf-8") as handle:
            for item in runtime_items:
                handle.write(json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n")
        page = (await self.get_page_info()).get("page", {})
        sessions = (await self.get_page_sessions()).get("sessions", [])
        sessions_path.write_text(json.dumps(sessions, ensure_ascii=False, indent=2), encoding="utf-8")
        report = "# Task Evidence\n\n"
        report += f"- Exported: `{datetime.now().isoformat()}`\n"
        report += f"- URL: `{page.get('url', '')}`\n"
        report += f"- Requests: `{len(self._captured_requests)}`\n"
        report += f"- Runtime events: `{len(runtime_items)}`\n\n"
        report += f"- Page sessions: `{len(sessions)}`\n"
        report += "Raw authenticated evidence remains in this task directory and is not copied into the report.\n"
        report_path.write_text(report, encoding="utf-8")
        files = [network_path, runtime_path, report_path, sessions_path]
        if include_bodies:
            files.extend(p for p in root.rglob("*") if p.is_file() and p.name != manifest_path.name and p not in files)
        with manifest_path.open("w", encoding="utf-8") as handle:
            for path in sorted(set(files), key=lambda p: str(p)):
                handle.write(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(root).as_posix()}\n")
        return {"success": True, "directory": str(root), "files": [str(p) for p in [network_path, runtime_path, report_path, sessions_path, manifest_path]], "requestCount": len(self._captured_requests), "runtimeEventCount": len(runtime_items), "pageSessionCount": len(sessions)}

    # ==================== DevTools 断点控制 ====================

    async def set_xhr_breakpoint(self, url_pattern):
        """设置 XHR 断点（会显示在 DevTools 的 XHR/fetch Breakpoints）"""
        if not self._cdp:
            return {"error": "未连接浏览器"}

        # 必须先启用 Debugger 域！
        await self._cdp.send("Debugger.enable")

        # 监听 paused 事件，保存调用栈信息
        if not self._debugger_listener_attached:
            self._cdp.on("Debugger.paused", self._on_debugger_paused)
            self._debugger_listener_attached = True

        await self._cdp.send("DOMDebugger.setXHRBreakpoint", {"url": url_pattern})
        self._xhr_breakpoints.add(url_pattern)
        return {"success": True, "message": f"XHR 断点已设置: {url_pattern}"}

    def _on_debugger_paused(self, event):
        """处理调试器暂停事件，保存调用栈"""
        self._paused_call_frames = event.get("callFrames", [])
        self._paused_reason = event.get("reason", "")

    async def remove_xhr_breakpoint(self, url_pattern):
        """移除 XHR 断点"""
        if not self._cdp:
            return {"error": "未连接浏览器"}

        await self._cdp.send("DOMDebugger.removeXHRBreakpoint", {"url": url_pattern})
        self._xhr_breakpoints.discard(url_pattern)
        return {"success": True, "message": f"XHR 断点已移除: {url_pattern}"}

    async def clear_debugger_state(self):
        """清理当前会话登记的断点，并清空暂停状态。"""
        if not self._cdp:
            return {"error": "未连接浏览器"}
        removed_breakpoints = 0
        for breakpoint_id in list(self._breakpoint_ids):
            try:
                await self._cdp.send("Debugger.removeBreakpoint", {"breakpointId": breakpoint_id})
                removed_breakpoints += 1
            except Exception:
                pass
        removed_xhr = 0
        for pattern in list(self._xhr_breakpoints):
            try:
                await self._cdp.send("DOMDebugger.removeXHRBreakpoint", {"url": pattern})
                removed_xhr += 1
            except Exception:
                pass
        self._breakpoint_ids.clear()
        self._xhr_breakpoints.clear()
        self._paused_call_frames = []
        self._paused_reason = ""
        return {"success": True, "removedBreakpoints": removed_breakpoints, "removedXhrBreakpoints": removed_xhr}

    async def set_breakpoint(self, url, line_number, column_number=0):
        """设置 JS 代码断点"""
        if not self._cdp:
            return {"error": "未连接浏览器"}

        # 启用 Debugger
        await self._cdp.send("Debugger.enable")

        result = await self._cdp.send("Debugger.setBreakpointByUrl", {
            "lineNumber": line_number - 1,  # CDP 行号从 0 开始
            "url": url,
            "columnNumber": column_number
        })
        breakpoint_id = result.get("breakpointId")
        if breakpoint_id:
            self._breakpoint_ids.add(breakpoint_id)

        return {
            "success": True,
            "breakpointId": breakpoint_id,
            "message": f"断点已设置: {url}:{line_number}"
        }

    async def remove_breakpoint(self, breakpoint_id):
        """移除 set_breakpoint 创建的普通 JS 断点。"""
        if not self._cdp:
            return {"error": "未连接浏览器"}
        if breakpoint_id not in self._breakpoint_ids:
            return {"error": f"未找到当前会话断点: {breakpoint_id}"}
        try:
            await self._cdp.send("Debugger.removeBreakpoint", {"breakpointId": breakpoint_id})
            self._breakpoint_ids.discard(breakpoint_id)
            return {"success": True, "breakpointId": breakpoint_id, "action": "removed"}
        except Exception as e:
            return {"error": f"移除断点失败: {str(e)}", "breakpointId": breakpoint_id}

    # ==================== 调试控制 ====================

    async def debugger_resume(self):
        """继续执行（F8）"""
        if not self._cdp:
            return {"error": "未连接浏览器"}

        await self._cdp.send("Debugger.resume")
        self._paused_call_frames = []
        self._paused_reason = ""
        return {"success": True, "message": "已继续执行"}

    async def debugger_step_over(self):
        """单步执行，跳过函数（F10）"""
        if not self._cdp:
            return {"error": "未连接浏览器"}

        await self._cdp.send("Debugger.stepOver")
        self._paused_call_frames = []
        return {"success": True, "message": "Step Over"}

    async def debugger_step_into(self):
        """单步执行，进入函数（F11）"""
        if not self._cdp:
            return {"error": "未连接浏览器"}

        await self._cdp.send("Debugger.stepInto")
        self._paused_call_frames = []
        return {"success": True, "message": "Step Into"}

    async def debugger_step_out(self):
        """单步跳出当前函数（Shift+F11）"""
        if not self._cdp:
            return {"error": "未连接浏览器"}

        await self._cdp.send("Debugger.stepOut")
        self._paused_call_frames = []
        return {"success": True, "message": "Step Out"}

    async def debugger_get_call_stack(self):
        """获取当前调用栈和局部变量"""
        if not self._cdp:
            return {"error": "未连接浏览器"}

        if not hasattr(self, '_paused_call_frames') or not self._paused_call_frames:
            return {"error": "当前没有暂停的断点，请先触发断点"}

        result = []
        for i, frame in enumerate(self._paused_call_frames[:5]):  # 只取前5个调用帧
            frame_info = {
                "index": i,
                "callFrameId": frame.get("callFrameId"),
                "functionName": frame.get("functionName") or "(anonymous)",
                "url": frame.get("url", "")[-50:],  # 截取后50字符
                "lineNumber": frame.get("location", {}).get("lineNumber", 0) + 1,
            }

            # 获取该帧的局部变量
            scope_chain = frame.get("scopeChain", [])
            local_vars = {}
            for scope in scope_chain:
                if scope.get("type") == "local":
                    obj_id = scope.get("object", {}).get("objectId")
                    if obj_id:
                        try:
                            props = await self._cdp.send("Runtime.getProperties", {
                                "objectId": obj_id,
                                "ownProperties": True
                            })
                            for prop in props.get("result", [])[:10]:  # 只取前10个
                                name = prop.get("name")
                                value = prop.get("value", {})
                                local_vars[name] = {
                                    "type": value.get("type"),
                                    "value": value.get("value") if value.get("type") != "object" else value.get("description", "Object")
                                }
                        except:
                            pass
                    break

            frame_info["localVariables"] = local_vars
            result.append(frame_info)

        return {
            "success": True,
            "reason": getattr(self, '_paused_reason', ''),
            "callFrames": result
        }

    async def debugger_evaluate(self, expression, call_frame_id=None):
        """在当前断点位置执行表达式查看变量"""
        if not self._cdp:
            return {"error": "未连接浏览器"}

        try:
            if call_frame_id:
                # 在指定的调用帧上执行
                result = await self._cdp.send("Debugger.evaluateOnCallFrame", {
                    "callFrameId": call_frame_id,
                    "expression": expression,
                    "returnByValue": True
                })
            else:
                # 在全局上下文执行
                result = await self._cdp.send("Runtime.evaluate", {
                    "expression": expression,
                    "returnByValue": True
                })

            return {
                "success": True,
                "result": result.get("result", {}),
                "exceptionDetails": result.get("exceptionDetails")
            }
        except Exception as e:
            return {"error": str(e)}

    # ==================== 执行 JavaScript ====================

    async def execute_js(self, code):
        """在页面执行 JavaScript 代码（用于补环境验证）"""
        if not self._page:
            return {"error": "未连接浏览器"}

        try:
            result = await self._page.evaluate(code)
            return {"success": True, "result": result}
        except Exception as e:
            try:
                result = await self._page.evaluate(code, force_expr=True)
                return {"success": True, "result": result}
            except Exception:
                return {"error": str(e)}

    async def inject_script_on_new_document(self, code):
        """在每个新文档创建前注入脚本"""
        if not self._cdp:
            return {"error": "未连接浏览器"}

        try:
            await self._cdp.send("Page.enable")
            result = await self._cdp.send("Page.addScriptToEvaluateOnNewDocument", {"source": code})
            self._init_scripts.append(code)
            self._init_script_ids.append(result.get("identifier"))
            return {"success": True, "count": len(self._init_scripts)}
        except Exception as e:
            return {"error": f"注入初始化脚本失败: {str(e)}"}

    async def get_init_scripts(self):
        """返回当前登记的初始化脚本"""
        return {"success": True, "count": len(self._init_scripts), "scripts": self._init_scripts}

    async def clear_init_scripts(self):
        """移除当前会话登记的初始化脚本。"""
        if not self._cdp:
            return {"error": "未连接浏览器"}

        removed = 0
        for identifier in list(self._init_script_ids):
            if not identifier:
                continue
            try:
                await self._cdp.send("Page.removeScriptToEvaluateOnNewDocument", {"identifier": identifier})
                removed += 1
            except Exception:
                pass
        self._init_scripts.clear()
        self._init_script_ids.clear()
        return {"success": True, "removed": removed}

    async def execute_js_with_details(self, code):
        """执行 JS 并获取详细结果（包括对象属性）"""
        if not self._cdp:
            return {"error": "未连接浏览器"}

        try:
            result = await self._cdp.send("Runtime.evaluate", {
                "expression": code,
                "returnByValue": True,
                "generatePreview": True
            })
            if len(self._console_logs) > self._max_console_logs:
                del self._console_logs[:-self._max_console_logs]

            return {
                "success": True,
                "result": result.get("result", {}),
                "exceptionDetails": result.get("exceptionDetails")
            }
        except Exception as e:
            return {"error": str(e)}

    async def wait_for_selector(self, selector, timeout=5000):
        """等待元素出现"""
        if not self._page:
            return {"error": "未连接浏览器"}

        try:
            await self._page.waitForSelector(selector, {"timeout": timeout})
            self._record_action("wait_for_selector", selector=selector, timeout=timeout)
            return {"success": True, "selector": selector, "timeout": timeout}
        except Exception as e:
            return {"error": f"等待元素失败: {str(e)}", "selector": selector, "timeout": timeout}

    # ==================== 浏览器控制 ====================

    async def navigate(self, url):
        """导航到指定 URL"""
        if not self._page:
            return {"error": "未连接浏览器"}

        await self._page.goto(url, waitUntil='domcontentloaded')
        self._record_action("navigate", url=url)
        return {"success": True, "url": url}

    async def reload(self):
        """刷新页面"""
        if not self._page:
            return {"error": "未连接浏览器"}

        await self._page.reload()
        self._record_action("reload")
        return {"success": True}

    async def go_back(self):
        """浏览器后退"""
        if not self._page:
            return {"error": "未连接浏览器"}

        await self._page.goBack()
        self._record_action("go_back")
        return {"success": True}

    async def click(self, selector, timeout=5000):
        """点击元素"""
        if not self._page:
            return {"error": "未连接浏览器"}

        await self._page.click(selector, timeout=timeout)
        self._record_action("click", selector=selector, timeout=timeout)
        return {"success": True, "selector": selector}

    async def type_text(self, selector, text, delay=50):
        """在输入框输入文本"""
        if not self._page:
            return {"error": "未连接浏览器"}

        await self._page.type(selector, text, delay=delay)
        self._record_action("type_text", selector=selector, text=text, delay=delay)
        return {"success": True, "selector": selector}

    async def scroll(self, x=0, y=500):
        """滚动页面"""
        if not self._page:
            return {"error": "未连接浏览器"}

        await self._page.evaluate(f"window.scrollBy({x}, {y})")
        self._record_action("scroll", x=x, y=y)
        return {"success": True, "scrolled": {"x": x, "y": y}}

    async def start_action_recording(self):
        self._recorded_actions = []
        self._recording_actions = True
        return {"success": True, "recording": True}

    async def stop_action_recording(self, path=None):
        self._recording_actions = False
        actions = list(self._recorded_actions)
        result = {"success": True, "recording": False, "count": len(actions), "actions": actions}
        if path:
            output = Path(path)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(actions, ensure_ascii=False, indent=2), encoding="utf-8")
            result["path"] = str(output)
        return result

    async def _execute_recorded_action(self, item):
        action = item.get("action")
        args = {k: v for k, v in item.items() if k not in {"action", "timestamp"}}
        if action == "navigate":
            return await self.navigate(args["url"])
        if action == "reload":
            return await self.reload()
        if action == "go_back":
            return await self.go_back()
        if action == "click":
            return await self.click(args["selector"], args.get("timeout", 5000))
        if action == "type_text":
            return await self.type_text(args["selector"], args["text"], args.get("delay", 50))
        if action == "scroll":
            return await self.scroll(args.get("x", 0), args.get("y", 500))
        if action == "wait_for_selector":
            return await self.wait_for_selector(args["selector"], args.get("timeout", 5000))
        return {"error": f"不支持的动作: {action}"}

    async def replay_actions(self, actions=None, path=None, stop_on_error=True, preserve_timing=False, max_delay=5000):
        if actions is None and path:
            actions = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(actions, list):
            return {"error": "actions 必须是数组"}
        results = []
        self._replaying_actions = True
        try:
            for index, item in enumerate(actions):
                action = item.get("action")
                args = {k: v for k, v in item.items() if k not in {"action", "timestamp"}}
                try:
                    if preserve_timing and index > 0 and item.get("timestamp") and actions[index - 1].get("timestamp"):
                        previous = datetime.fromisoformat(actions[index - 1]["timestamp"])
                        current = datetime.fromisoformat(item["timestamp"])
                        delay = max(0.0, min((current - previous).total_seconds(), max_delay / 1000))
                        if delay:
                            await asyncio.sleep(delay)
                    result = await self._execute_recorded_action(item)
                except Exception as e:
                    result = {"error": str(e)}
                results.append({"index": index, "action": action, "result": result})
                if stop_on_error and not result.get("success"):
                    break
        finally:
            self._replaying_actions = False
        return {"success": all(item["result"].get("success", False) for item in results), "count": len(results), "results": results}

    async def replay_and_capture(
        self,
        actions=None,
        path=None,
        url_pattern=None,
        timeout=10000,
        status=None,
        stop_on_error=True,
        preserve_timing=False,
        max_delay=5000,
        artifact_dir=None,
        body_preview=2000,
        assertions=None,
    ):
        """Replay actions and bind each action to the requests it triggers."""
        if actions is None and path:
            actions = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(actions, list):
            return {"error": "actions 必须是数组"}

        results = []
        self._replaying_actions = True
        try:
            for index, item in enumerate(actions):
                action = item.get("action")
                if preserve_timing and index > 0 and item.get("timestamp") and actions[index - 1].get("timestamp"):
                    try:
                        previous = datetime.fromisoformat(actions[index - 1]["timestamp"])
                        current = datetime.fromisoformat(item["timestamp"])
                        delay = max(0.0, min((current - previous).total_seconds(), max_delay / 1000))
                        if delay:
                            await asyncio.sleep(delay)
                    except (TypeError, ValueError):
                        pass

                await self.clear_captured_requests()
                try:
                    action_result = await self._execute_recorded_action(item)
                except Exception as e:
                    action_result = {"error": str(e)}

                evidence = {"requests": [], "response": None}
                if action_result.get("success"):
                    if url_pattern:
                        evidence["response"] = await self.wait_for_response(
                            url_pattern=url_pattern, status=status, timeout=timeout
                        )
                        if evidence["response"].get("success"):
                            request = evidence["response"].get("request", {})
                            request_id = request.get("requestId")
                            if request_id:
                                evidence["requestBody"] = await self.get_request_body(
                                    request_id, max_preview=body_preview, include_body=False
                                )
                                evidence["responseBody"] = await self.get_response_body(
                                    request_id, max_preview=body_preview, include_body=False
                                )
                                if artifact_dir:
                                    base = Path(artifact_dir)
                                    evidence["requestArtifact"] = await self.save_request_body(
                                        request_id, str(base / f"{index:04d}_request.body")
                                    )
                                    evidence["responseArtifact"] = await self.save_response_body(
                                        request_id, str(base / f"{index:04d}_response.body")
                                    )
                    else:
                        evidence["requests"] = (await self.get_captured_requests(limit=50)).get("requests", [])

                record = {"index": index, "action": action, "result": action_result, "evidence": evidence}
                record["assertions"] = self._check_replay_assertions(record, assertions or {})
                results.append(record)
                if stop_on_error and (not action_result.get("success") or not record["assertions"].get("success", True)):
                    break
        finally:
            self._replaying_actions = False
        overall_success = all(
            item.get("result", {}).get("success", False)
            and item.get("evidence", {}).get("response", {}).get("success", True)
            and item.get("assertions", {}).get("success", True)
            for item in results
        )
        return {"success": overall_success, "count": len(results), "results": results}

    @staticmethod
    def _check_replay_assertions(record, assertions):
        if not assertions:
            return {"success": True, "checks": []}
        checks = []
        evidence = record.get("evidence", {})
        response = evidence.get("response", {}).get("request", {}) if evidence.get("response") else {}
        status = response.get("response", {}).get("status")
        if "status" in assertions:
            checks.append({"name": "status", "success": status == assertions["status"], "actual": status, "expected": assertions["status"]})
        if "url_contains" in assertions:
            checks.append({"name": "url_contains", "success": assertions["url_contains"] in response.get("url", ""), "actual": response.get("url"), "expected": assertions["url_contains"]})
        if "request_preview_contains" in assertions:
            actual = evidence.get("requestBody", {}).get("preview", "")
            checks.append({"name": "request_preview_contains", "success": assertions["request_preview_contains"] in actual})
        if "response_preview_contains" in assertions:
            actual = evidence.get("responseBody", {}).get("decodedPreview", "")
            checks.append({"name": "response_preview_contains", "success": assertions["response_preview_contains"] in actual})
        return {"success": all(item["success"] for item in checks), "checks": checks}

    async def screenshot(self, path=None, full_page=False):
        """截图"""
        if not self._page:
            return {"error": "未连接浏览器"}

        if not path:
            path = f"screenshot_{int(datetime.now().timestamp())}.png"

        try:
            output_path = Path(path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            if full_page and self._cdp:
                metrics = await self._cdp.send("Page.getLayoutMetrics")
                content_size = metrics.get("contentSize", {})
                width = max(1, int(content_size.get("width", 1)))
                height = max(1, int(content_size.get("height", 1)))

                screenshot = await asyncio.wait_for(
                    self._cdp.send("Page.captureScreenshot", {
                        "format": "png",
                        "captureBeyondViewport": True,
                        "fromSurface": True,
                        "clip": {
                            "x": 0,
                            "y": 0,
                            "width": width,
                            "height": height,
                            "scale": 1,
                        },
                    }),
                    timeout=30,
                )
                with open(path, "wb") as f:
                    f.write(base64.b64decode(screenshot["data"]))
            else:
                await asyncio.wait_for(
                    self._page.screenshot(path=path, fullPage=full_page),
                    timeout=30,
                )
        except Exception as e:
            return {
                "error": f"截图失败: {str(e)}",
                "path": path,
                "full_page": full_page,
            }

        return {"success": True, "path": path, "full_page": full_page}

    async def close_browser(self):
        """关闭浏览器（只关闭由 launch_real_chrome 启动的浏览器）"""
        if self._browser:
            try:
                if self._cdp and self._fetch_enabled:
                    try:
                        await self._cdp.send("Fetch.disable")
                    except Exception:
                        pass
                await self._browser.disconnect()
            except Exception:
                pass
            finally:
                self._browser = None
                self._page = None
                self._cdp = None
                self._reset_session_state()
                self._request_waiters.clear()
                self._response_waiters.clear()

        if self._chrome_process:
            # 关闭我们启动的 Chrome 进程
            self._chrome_process.terminate()
            try:
                self._chrome_process.wait(timeout=5)
            except:
                self._chrome_process.kill()
            self._chrome_process = None
            return {"success": True, "message": "已关闭浏览器"}
        else:
            return {"error": "没有通过 launch_real_chrome 启动的浏览器"}

    # ==================== DOM 分析 ====================

    async def get_element_info(self, selector):
        """获取元素信息"""
        if not self._page:
            return {"error": "未连接浏览器"}

        try:
            js_selector = json.dumps(selector, ensure_ascii=False)
            info = await self._page.evaluate(
                f"""(() => {{
                    const selector = {js_selector};
                    const el = document.querySelector(selector);
                    if (!el) return null;
                    const rect = el.getBoundingClientRect();
                    return {{
                        tagName: el.tagName,
                        id: el.id,
                        className: el.className,
                        innerText: el.innerText?.substring(0, 200),
                        innerHTML: el.innerHTML?.substring(0, 500),
                        attributes: Object.fromEntries([...el.attributes].map(a => [a.name, a.value])),
                        rect: {{ top: rect.top, left: rect.left, width: rect.width, height: rect.height }}
                    }};
                }})()""",
                force_expr=True,
            )
        except Exception as e:
            return {"error": f"查询元素失败: {str(e)}", "selector": selector}

        return {"success": True, "element": info} if info else {"error": "元素未找到"}

    async def query_selector_all(self, selector):
        """查询所有匹配的元素"""
        if not self._page:
            return {"error": "未连接浏览器"}

        try:
            js_selector = json.dumps(selector, ensure_ascii=False)
            elements = await self._page.evaluate(
                f"""(() => {{
                    const selector = {js_selector};
                    const els = document.querySelectorAll(selector);
                    return [...els].map((el, i) => ({{
                        index: i,
                        tagName: el.tagName,
                        id: el.id,
                        className: el.className,
                        text: el.innerText?.substring(0, 100)
                    }}));
                }})()""",
                force_expr=True,
            )
        except Exception as e:
            return {"error": f"查询元素列表失败: {str(e)}", "selector": selector}

        return {"success": True, "count": len(elements), "elements": elements}
