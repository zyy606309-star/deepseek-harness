"""
Crawler MCP server backed by a pyppeteer-based BrowserManager.
"""

import asyncio
import json
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from browser import BrowserManager


server = Server("crawler-mcp")
browser_manager = BrowserManager()


def _tool(name: str, description: str, properties: dict | None = None, required: list[str] | None = None) -> Tool:
    schema: dict[str, Any] = {"type": "object", "properties": properties or {}}
    if required:
        schema["required"] = required
    return Tool(name=name, description=description, inputSchema=schema)


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        _tool(
            "open_browser",
            "Start or reuse Chrome, connect CDP, and optionally navigate in one call.",
            {
                "url": {"type": "string", "description": "Optional URL to open"},
                "port": {"type": "integer", "description": "Debug port", "default": 9222},
            },
        ),
        _tool(
            "launch_real_chrome",
            "Launch a real Chrome instance with remote debugging enabled.",
            {
                "port": {"type": "integer", "description": "Debug port", "default": 9222},
                "url": {"type": "string", "description": "Optional startup URL"},
            },
        ),
        _tool(
            "connect_browser",
            "Connect to an existing Chrome instance and enable network and console capture.",
            {"port": {"type": "integer", "description": "Debug port", "default": 9222}},
        ),
        _tool(
            "wait_for_new_tab",
            "Wait for the user to open a new tab and switch the active session to it.",
            {"timeout": {"type": "integer", "description": "Timeout in seconds", "default": 60}},
        ),
        _tool("list_pages", "List all open browser pages."),
        _tool("get_page_sessions", "Return per-page evidence counters while keeping raw session data local."),
        _tool(
            "switch_page",
            "Switch the active page by index.",
            {"index": {"type": "integer", "description": "Page index from list_pages"}},
            ["index"],
        ),
        _tool("close_browser", "Close the Chrome process started by launch_real_chrome."),
        _tool("get_page_info", "Return page title, URL, ready state, viewport, and document metrics."),
        _tool("get_cookies", "Return cookies visible to the active page."),
        _tool(
            "get_storage",
            "Return localStorage or sessionStorage items from the active page.",
            {"storage_type": {"type": "string", "description": "localStorage or sessionStorage", "default": "localStorage"}},
        ),
        _tool(
            "set_request_interception",
            "Enable or disable Fetch-based request interception.",
            {
                "enabled": {"type": "boolean", "description": "Whether interception is enabled", "default": True},
                "url_pattern": {"type": "string", "description": "CDP URL pattern", "default": "*"},
                "auto_continue": {"type": "boolean", "description": "Continue paused requests automatically", "default": True},
            },
        ),
        _tool("get_pending_interceptions", "List currently paused intercepted requests."),
        _tool(
            "continue_request",
            "Continue a paused intercepted request and optionally override parts of it.",
            {
                "request_id": {"type": "string", "description": "Paused Fetch request id"},
                "url": {"type": "string", "description": "Optional replacement URL"},
                "method": {"type": "string", "description": "Optional replacement HTTP method"},
                "post_data": {"type": "string", "description": "Optional replacement request body"},
                "headers": {"type": "object", "description": "Optional replacement headers"},
            },
            ["request_id"],
        ),
        _tool(
            "abort_request",
            "Abort a paused intercepted request.",
            {
                "request_id": {"type": "string", "description": "Paused Fetch request id"},
                "error_reason": {"type": "string", "description": "CDP error reason", "default": "Failed"},
            },
            ["request_id"],
        ),
        _tool(
            "fulfill_request",
            "Fulfill a paused intercepted request with a synthetic response.",
            {
                "request_id": {"type": "string", "description": "Paused Fetch request id"},
                "status": {"type": "integer", "description": "HTTP status code", "default": 200},
                "body": {"type": "string", "description": "Response body"},
                "headers": {"type": "object", "description": "Response headers"},
                "is_base64": {"type": "boolean", "description": "Whether body is already base64 encoded", "default": False},
            },
            ["request_id"],
        ),
        _tool(
            "wait_for_request",
            "Wait until a matching request is observed.",
            {
                "url_pattern": {"type": "string", "description": "Substring to match in request URL"},
                "timeout": {"type": "integer", "description": "Timeout in milliseconds", "default": 10000},
            },
        ),
        _tool(
            "wait_for_response",
            "Wait until a matching response is observed.",
            {
                "url_pattern": {"type": "string", "description": "Substring to match in response URL"},
                "status": {"type": "integer", "description": "Optional expected status code"},
                "timeout": {"type": "integer", "description": "Timeout in milliseconds", "default": 10000},
            },
        ),
        _tool(
            "navigate",
            "Navigate the active page to a URL.",
            {"url": {"type": "string", "description": "Target URL"}},
            ["url"],
        ),
        _tool("reload", "Reload the active page."),
        _tool("go_back", "Navigate back in the active page history."),
        _tool(
            "click",
            "Click a DOM element by CSS selector.",
            {
                "selector": {"type": "string", "description": "CSS selector"},
                "timeout": {"type": "integer", "description": "Timeout in milliseconds", "default": 5000},
            },
            ["selector"],
        ),
        _tool(
            "type_text",
            "Type text into an input matched by CSS selector.",
            {
                "selector": {"type": "string", "description": "CSS selector"},
                "text": {"type": "string", "description": "Text to type"},
                "delay": {"type": "integer", "description": "Delay between keystrokes in milliseconds", "default": 50},
            },
            ["selector", "text"],
        ),
        _tool(
            "execute_js",
            "Execute JavaScript in the active page context.",
            {"code": {"type": "string", "description": "JavaScript code"}},
            ["code"],
        ),
        _tool(
            "execute_js_with_details",
            "Execute JavaScript via Runtime.evaluate and return rich CDP details.",
            {"code": {"type": "string", "description": "JavaScript code"}},
            ["code"],
        ),
        _tool(
            "inject_script_on_new_document",
            "Inject JavaScript before any future document scripts run.",
            {"code": {"type": "string", "description": "JavaScript source code"}},
            ["code"],
        ),
        _tool("get_init_scripts", "List scripts registered for new-document injection."),
        _tool("clear_init_scripts", "Remove scripts registered for new-document injection."),
        _tool(
            "wait_for_selector",
            "Wait for a DOM element to appear.",
            {
                "selector": {"type": "string", "description": "CSS selector"},
                "timeout": {"type": "integer", "description": "Timeout in milliseconds", "default": 5000},
            },
            ["selector"],
        ),
        _tool(
            "screenshot",
            "Capture a screenshot of the active page.",
            {
                "path": {"type": "string", "description": "Output file path"},
                "full_page": {"type": "boolean", "description": "Capture the full page", "default": False},
            },
        ),
        _tool(
            "set_xhr_breakpoint",
            "Add a DevTools XHR/fetch breakpoint for matching URLs.",
            {"url_pattern": {"type": "string", "description": "URL substring to match"}},
            ["url_pattern"],
        ),
        _tool(
            "remove_xhr_breakpoint",
            "Remove a previously added XHR/fetch breakpoint.",
            {"url_pattern": {"type": "string", "description": "URL substring to match"}},
            ["url_pattern"],
        ),
        _tool(
            "set_breakpoint",
            "Set a JavaScript breakpoint by URL and line number.",
            {
                "url": {"type": "string", "description": "Script URL"},
                "line_number": {"type": "integer", "description": "1-based line number"},
                "column_number": {"type": "integer", "description": "0-based column number", "default": 0},
            },
            ["url", "line_number"],
        ),
        _tool(
            "remove_breakpoint",
            "Remove a JavaScript breakpoint created by set_breakpoint.",
            {"breakpoint_id": {"type": "string", "description": "Breakpoint ID from set_breakpoint"}},
            ["breakpoint_id"],
        ),
        _tool("clear_debugger_state", "Remove tracked JS/XHR breakpoints and clear paused debugger state."),
        _tool("start_action_recording", "Start recording MCP-driven page actions."),
        _tool(
            "stop_action_recording",
            "Stop action recording and optionally save the action list.",
            {"path": {"type": "string", "description": "Optional output JSON path"}},
        ),
        _tool(
            "replay_actions",
            "Replay recorded MCP-driven page actions.",
            {
                "actions": {"type": "array", "description": "Action list"},
                "path": {"type": "string", "description": "JSON action file path"},
                "stop_on_error": {"type": "boolean", "description": "Stop at first failed action", "default": True},
                "preserve_timing": {"type": "boolean", "description": "Replay recorded delays", "default": False},
                "max_delay": {"type": "integer", "minimum": 0, "maximum": 60000, "description": "Maximum delay per action in milliseconds", "default": 5000},
            },
        ),
        _tool(
            "replay_and_capture",
            "Replay actions and bind each action to matching request/response evidence.",
            {
                "actions": {"type": "array", "description": "Action list"},
                "path": {"type": "string", "description": "JSON action file path"},
                "url_pattern": {"type": "string", "description": "Optional response URL substring"},
                "timeout": {"type": "integer", "minimum": 1, "maximum": 120000, "default": 10000},
                "status": {"type": "integer", "description": "Optional expected response status"},
                "stop_on_error": {"type": "boolean", "default": True},
                "preserve_timing": {"type": "boolean", "default": False},
                "max_delay": {"type": "integer", "minimum": 0, "maximum": 60000, "default": 5000},
                "artifact_dir": {"type": "string", "description": "Optional directory for request/response bodies"},
                "body_preview": {"type": "integer", "minimum": 0, "maximum": 1000000, "default": 2000},
                "assertions": {"type": "object", "description": "Optional status/url/request/response preview assertions"},
            },
        ),
        _tool(
            "get_captured_requests",
            "Return captured network requests.",
            {
                "url_filter": {"type": "string", "description": "Optional URL substring filter"},
                "limit": {"type": "integer", "description": "Maximum number of requests", "default": 20},
            },
        ),
        _tool(
            "get_response_body",
            "Return the body for a captured request.",
            {
                "request_id": {"type": "string", "description": "Request ID from get_captured_requests"},
                "max_preview": {"type": "integer", "minimum": 0, "maximum": 1000000, "description": "Maximum decoded preview length", "default": 2000},
                "include_body": {"type": "boolean", "description": "Return the complete body; disabled by default", "default": False},
            },
            ["request_id"],
        ),
        _tool(
            "save_response_body",
            "Save a complete response body to a local task artifact without returning it to the context.",
            {
                "request_id": {"type": "string", "description": "Request ID from get_captured_requests"},
                "path": {"type": "string", "description": "Output file path"},
            },
            ["request_id", "path"],
        ),
        _tool(
            "get_request_body",
            "Read request post data on demand from CDP.",
            {
                "request_id": {"type": "string", "description": "Request ID from get_captured_requests"},
                "max_preview": {"type": "integer", "minimum": 0, "maximum": 1000000, "description": "Maximum preview length", "default": 2000},
                "include_body": {"type": "boolean", "description": "Return the complete request body", "default": False},
            },
            ["request_id"],
        ),
        _tool(
            "save_request_body",
            "Save a complete request body to a local task artifact.",
            {
                "request_id": {"type": "string", "description": "Request ID from get_captured_requests"},
                "path": {"type": "string", "description": "Output file path"},
            },
            ["request_id", "path"],
        ),
        _tool("clear_captured_requests", "Clear captured network request history."),
        _tool(
            "get_console_logs",
            "Return captured console logs.",
            {
                "limit": {"type": "integer", "description": "Maximum number of logs", "default": 50},
                "type_filter": {"type": "string", "description": "Optional log type filter: log, warn, error"},
            },
        ),
        _tool(
            "wait_for_console",
            "Wait until a matching console log is observed.",
            {
                "pattern": {"type": "string", "description": "Substring to match in console message"},
                "type_filter": {"type": "string", "description": "Optional log type filter: log, warn, error"},
                "timeout": {"type": "integer", "description": "Timeout in milliseconds", "default": 10000},
            },
        ),
        _tool("clear_console_logs", "Clear captured console logs."),
        _tool(
            "dump_session",
            "Return a bounded debug session snapshot.",
            {
                "console_limit": {"type": "integer", "minimum": 0, "maximum": 2000, "description": "Maximum console entries", "default": 20},
                "include_storage": {"type": "boolean", "description": "Include local/session storage", "default": True},
                "include_cookies": {"type": "boolean", "description": "Include cookies", "default": True},
            },
        ),
        _tool(
            "get_websocket_events",
            "Return captured WebSocket lifecycle and frame events.",
            {"request_id": {"type": "string", "description": "Optional WebSocket request ID"}, "limit": {"type": "integer", "default": 100}},
        ),
        _tool("get_special_network_events", "Return WebTransport, target, and other special CDP network events.", {"limit": {"type": "integer", "default": 100}}),
        _tool(
            "start_live_stream",
            "Start a decoded live WebSocket message stream from the active browser page.",
            {"output_path": {"type": "string", "description": "Optional JSONL output path"}, "websocket_url_pattern": {"type": "string", "default": "webcast"}, "include_raw": {"type": "boolean", "default": True}, "wait_timeout": {"type": "integer", "default": 15000}},
        ),
        _tool(
            "read_live_messages",
            "Read decoded live messages for a bounded duration from the active stream.",
            {"duration": {"type": "number", "default": 5}, "max_messages": {"type": "integer", "default": 100}, "poll_interval": {"type": "number", "default": 0.25}, "methods": {"type": "array", "description": "Optional method filter, e.g. WebcastChatMessage"}},
        ),
        _tool("stop_live_stream", "Stop the active live message stream."),
        _tool("health_check", "Check whether the browser, page, and CDP session are responsive."),
        _tool("reconnect_browser", "Reconnect using the last successful CDP port."),
        _tool("probe_capabilities", "Probe available CDP domains and external reverse-engineering tools."),
        _tool("adb_devices", "List connected Android devices using read-only adb devices -l.", {"timeout": {"type": "integer", "default": 10000}}),
        _tool(
            "find_signature_candidates",
            "Find likely signature globals and JavaScript resources in the active page.",
            {"keywords": {"type": "array", "description": "Optional keyword list"}},
        ),
        _tool(
            "export_evidence",
            "Export captured requests, console, WebSocket events, and actions to a JSON artifact.",
            {"path": {"type": "string", "description": "Output JSON path"}, "include_requests": {"type": "boolean", "default": True}, "include_console": {"type": "boolean", "default": True}, "include_websocket": {"type": "boolean", "default": True}},
            ["path"],
        ),
        _tool(
            "diff_requests",
            "Compare two captured request lists or JSON artifacts.",
            {"baseline": {"type": "array"}, "current": {"type": "array"}, "baseline_path": {"type": "string"}, "current_path": {"type": "string"}},
        ),
        _tool(
            "export_task_artifacts",
            "Export network/runtime evidence, report, and SHA-256 manifest to a task directory.",
            {"directory": {"type": "string", "description": "Task artifact directory"}, "include_bodies": {"type": "boolean", "default": False}},
            ["directory"],
        ),
        _tool(
            "get_element_info",
            "Return details for the first DOM element matching a CSS selector.",
            {"selector": {"type": "string", "description": "CSS selector"}},
            ["selector"],
        ),
        _tool(
            "query_selector_all",
            "Return summaries for all DOM elements matching a CSS selector.",
            {"selector": {"type": "string", "description": "CSS selector"}},
            ["selector"],
        ),
        _tool(
            "scroll",
            "Scroll the active page by a delta.",
            {
                "x": {"type": "integer", "description": "Horizontal delta", "default": 0},
                "y": {"type": "integer", "description": "Vertical delta", "default": 500},
            },
        ),
        _tool("debugger_resume", "Resume JavaScript execution after a breakpoint."),
        _tool("debugger_step_over", "Step over the next JavaScript statement."),
        _tool("debugger_step_into", "Step into the next JavaScript call."),
        _tool("debugger_step_out", "Step out of the current JavaScript frame."),
        _tool(
            "debugger_evaluate",
            "Evaluate an expression in the current debugger context.",
            {
                "expression": {"type": "string", "description": "Expression to evaluate"},
                "call_frame_id": {"type": "string", "description": "Optional call frame ID"},
            },
            ["expression"],
        ),
        _tool("debugger_get_call_stack", "Return the current debugger call stack."),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    arguments = arguments or {}

    try:
        if name == "open_browser":
            result = await browser_manager.open_browser(
                url=arguments.get("url"),
                port=arguments.get("port", 9222),
            )
        elif name == "launch_real_chrome":
            result = await browser_manager.launch_real_chrome(
                port=arguments.get("port", 9222),
                url=arguments.get("url"),
            )
        elif name == "connect_browser":
            result = await browser_manager.connect_browser(port=arguments.get("port", 9222))
        elif name == "wait_for_new_tab":
            result = await browser_manager.wait_for_new_tab(timeout=arguments.get("timeout", 60))
        elif name == "list_pages":
            result = await browser_manager.list_pages()
        elif name == "get_page_sessions":
            result = await browser_manager.get_page_sessions()
        elif name == "switch_page":
            result = await browser_manager.switch_page(index=arguments["index"])
        elif name == "close_browser":
            result = await browser_manager.close_browser()
        elif name == "get_page_info":
            result = await browser_manager.get_page_info()
        elif name == "get_cookies":
            result = await browser_manager.get_cookies()
        elif name == "get_storage":
            result = await browser_manager.get_storage(storage_type=arguments.get("storage_type", "localStorage"))
        elif name == "set_request_interception":
            result = await browser_manager.set_request_interception(
                enabled=arguments.get("enabled", True),
                url_pattern=arguments.get("url_pattern", "*"),
                auto_continue=arguments.get("auto_continue", True),
            )
        elif name == "get_pending_interceptions":
            result = await browser_manager.get_pending_interceptions()
        elif name == "continue_request":
            result = await browser_manager.continue_request(
                request_id=arguments["request_id"],
                url=arguments.get("url"),
                method=arguments.get("method"),
                post_data=arguments.get("post_data"),
                headers=arguments.get("headers"),
            )
        elif name == "abort_request":
            result = await browser_manager.abort_request(
                request_id=arguments["request_id"],
                error_reason=arguments.get("error_reason", "Failed"),
            )
        elif name == "fulfill_request":
            result = await browser_manager.fulfill_request(
                request_id=arguments["request_id"],
                status=arguments.get("status", 200),
                body=arguments.get("body", ""),
                headers=arguments.get("headers"),
                is_base64=arguments.get("is_base64", False),
            )
        elif name == "wait_for_request":
            result = await browser_manager.wait_for_request(
                url_pattern=arguments.get("url_pattern"),
                timeout=arguments.get("timeout", 10000),
            )
        elif name == "wait_for_response":
            result = await browser_manager.wait_for_response(
                url_pattern=arguments.get("url_pattern"),
                status=arguments.get("status"),
                timeout=arguments.get("timeout", 10000),
            )
        elif name == "navigate":
            result = await browser_manager.navigate(url=arguments["url"])
        elif name == "reload":
            result = await browser_manager.reload()
        elif name == "go_back":
            result = await browser_manager.go_back()
        elif name == "click":
            result = await browser_manager.click(
                selector=arguments["selector"],
                timeout=arguments.get("timeout", 5000),
            )
        elif name == "type_text":
            result = await browser_manager.type_text(
                selector=arguments["selector"],
                text=arguments["text"],
                delay=arguments.get("delay", 50),
            )
        elif name == "execute_js":
            result = await browser_manager.execute_js(code=arguments["code"])
        elif name == "execute_js_with_details":
            result = await browser_manager.execute_js_with_details(code=arguments["code"])
        elif name == "inject_script_on_new_document":
            result = await browser_manager.inject_script_on_new_document(code=arguments["code"])
        elif name == "get_init_scripts":
            result = await browser_manager.get_init_scripts()
        elif name == "clear_init_scripts":
            result = await browser_manager.clear_init_scripts()
        elif name == "wait_for_selector":
            result = await browser_manager.wait_for_selector(
                selector=arguments["selector"],
                timeout=arguments.get("timeout", 5000),
            )
        elif name == "screenshot":
            result = await browser_manager.screenshot(
                path=arguments.get("path"),
                full_page=arguments.get("full_page", False),
            )
        elif name == "set_xhr_breakpoint":
            result = await browser_manager.set_xhr_breakpoint(url_pattern=arguments["url_pattern"])
        elif name == "remove_xhr_breakpoint":
            result = await browser_manager.remove_xhr_breakpoint(url_pattern=arguments["url_pattern"])
        elif name == "set_breakpoint":
            result = await browser_manager.set_breakpoint(
                url=arguments["url"],
                line_number=arguments["line_number"],
                column_number=arguments.get("column_number", 0),
            )
        elif name == "remove_breakpoint":
            result = await browser_manager.remove_breakpoint(arguments["breakpoint_id"])
        elif name == "clear_debugger_state":
            result = await browser_manager.clear_debugger_state()
        elif name == "start_action_recording":
            result = await browser_manager.start_action_recording()
        elif name == "stop_action_recording":
            result = await browser_manager.stop_action_recording(path=arguments.get("path"))
        elif name == "replay_actions":
            result = await browser_manager.replay_actions(
                actions=arguments.get("actions"),
                path=arguments.get("path"),
                stop_on_error=arguments.get("stop_on_error", True),
                preserve_timing=arguments.get("preserve_timing", False),
                max_delay=arguments.get("max_delay", 5000),
            )
        elif name == "replay_and_capture":
            result = await browser_manager.replay_and_capture(
                actions=arguments.get("actions"),
                path=arguments.get("path"),
                url_pattern=arguments.get("url_pattern"),
                timeout=arguments.get("timeout", 10000),
                status=arguments.get("status"),
                stop_on_error=arguments.get("stop_on_error", True),
                preserve_timing=arguments.get("preserve_timing", False),
                max_delay=arguments.get("max_delay", 5000),
                artifact_dir=arguments.get("artifact_dir"),
                body_preview=arguments.get("body_preview", 2000),
                assertions=arguments.get("assertions"),
            )
        elif name == "get_captured_requests":
            result = await browser_manager.get_captured_requests(
                url_filter=arguments.get("url_filter"),
                limit=arguments.get("limit", 20),
            )
        elif name == "get_response_body":
            result = await browser_manager.get_response_body(
                request_id=arguments["request_id"],
                max_preview=arguments.get("max_preview", 2000),
                include_body=arguments.get("include_body", False),
            )
        elif name == "save_response_body":
            result = await browser_manager.save_response_body(
                request_id=arguments["request_id"],
                path=arguments["path"],
            )
        elif name == "get_request_body":
            result = await browser_manager.get_request_body(
                request_id=arguments["request_id"],
                max_preview=arguments.get("max_preview", 2000),
                include_body=arguments.get("include_body", False),
            )
        elif name == "save_request_body":
            result = await browser_manager.save_request_body(
                request_id=arguments["request_id"],
                path=arguments["path"],
            )
        elif name == "clear_captured_requests":
            result = await browser_manager.clear_captured_requests()
        elif name == "get_console_logs":
            result = await browser_manager.get_console_logs(
                limit=arguments.get("limit", 50),
                type_filter=arguments.get("type_filter"),
            )
        elif name == "wait_for_console":
            result = await browser_manager.wait_for_console(
                pattern=arguments.get("pattern"),
                type_filter=arguments.get("type_filter"),
                timeout=arguments.get("timeout", 10000),
            )
        elif name == "clear_console_logs":
            result = await browser_manager.clear_console_logs()
        elif name == "dump_session":
            result = await browser_manager.dump_session(
                console_limit=arguments.get("console_limit", 20),
                include_storage=arguments.get("include_storage", True),
                include_cookies=arguments.get("include_cookies", True),
            )
        elif name == "get_websocket_events":
            result = await browser_manager.get_websocket_events(
                request_id=arguments.get("request_id"), limit=arguments.get("limit", 100)
            )
        elif name == "get_special_network_events":
            result = await browser_manager.get_special_network_events(limit=arguments.get("limit", 100))
        elif name == "start_live_stream":
            result = await browser_manager.start_live_stream(
                output_path=arguments.get("output_path"),
                websocket_url_pattern=arguments.get("websocket_url_pattern", "webcast"),
                include_raw=arguments.get("include_raw", True),
                wait_timeout=arguments.get("wait_timeout", 15000),
            )
        elif name == "read_live_messages":
            result = await browser_manager.read_live_messages(
                duration=arguments.get("duration", 5),
                max_messages=arguments.get("max_messages", 100),
                poll_interval=arguments.get("poll_interval", 0.25),
                methods=arguments.get("methods"),
            )
        elif name == "stop_live_stream":
            result = await browser_manager.stop_live_stream()
        elif name == "health_check":
            result = await browser_manager.health_check()
        elif name == "reconnect_browser":
            result = await browser_manager.reconnect_browser()
        elif name == "probe_capabilities":
            result = await browser_manager.probe_capabilities()
        elif name == "adb_devices":
            result = await browser_manager.adb_devices(timeout=arguments.get("timeout", 10000))
        elif name == "find_signature_candidates":
            result = await browser_manager.find_signature_candidates(arguments.get("keywords"))
        elif name == "export_evidence":
            result = await browser_manager.export_evidence(
                path=arguments["path"],
                include_requests=arguments.get("include_requests", True),
                include_console=arguments.get("include_console", True),
                include_websocket=arguments.get("include_websocket", True),
            )
        elif name == "diff_requests":
            result = await browser_manager.diff_requests(
                baseline=arguments.get("baseline"),
                current=arguments.get("current"),
                baseline_path=arguments.get("baseline_path"),
                current_path=arguments.get("current_path"),
            )
        elif name == "export_task_artifacts":
            result = await browser_manager.export_task_artifacts(
                directory=arguments["directory"],
                include_bodies=arguments.get("include_bodies", False),
            )
        elif name == "get_element_info":
            result = await browser_manager.get_element_info(selector=arguments["selector"])
        elif name == "query_selector_all":
            result = await browser_manager.query_selector_all(selector=arguments["selector"])
        elif name == "scroll":
            result = await browser_manager.scroll(
                x=arguments.get("x", 0),
                y=arguments.get("y", 500),
            )
        elif name == "debugger_resume":
            result = await browser_manager.debugger_resume()
        elif name == "debugger_step_over":
            result = await browser_manager.debugger_step_over()
        elif name == "debugger_step_into":
            result = await browser_manager.debugger_step_into()
        elif name == "debugger_step_out":
            result = await browser_manager.debugger_step_out()
        elif name == "debugger_evaluate":
            result = await browser_manager.debugger_evaluate(
                expression=arguments["expression"],
                call_frame_id=arguments.get("call_frame_id"),
            )
        elif name == "debugger_get_call_stack":
            result = await browser_manager.debugger_get_call_stack()
        else:
            result = {"error": f"Unknown tool: {name}"}

        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]
    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}, ensure_ascii=False, indent=2))]


async def stdio() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(stdio())
