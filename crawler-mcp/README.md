# Crawler MCP

一个基于 `pyppeteer + Chrome DevTools Protocol` 的 MCP 服务，用于控制真实 Chrome、监听网络请求、设置断点，并配合本地补环境完成前端 JS 逆向分析。

## 当前定位

- 真实 Chrome 启动与连接
- 页面导航、点击、输入、滚动、截图
- 网络请求监听、响应体抓取、请求拦截
- XHR 断点、JS 断点、调用栈查看、断点处求值
- 页面信息、Cookie、Storage、Console 日志采集
- 逆向任务规范、补环境规范、任务产物模板

当前实现主链：

- [server.py](D:/网易/crawler-mcp/server.py)
- [browser.py](D:/网易/crawler-mcp/browser.py)

## 配置 MCP

```json
{
  "mcpServers": {
    "crawler": {
      "type": "stdio",
      "command": "python",
      "args": ["D:/网易/crawler-mcp/server.py"]
    }
  }
}
```

## 标准逆向入口

如果你是做 JS 逆向，不要直接跳进站点专题，默认先看：

- [00_JS逆向作业规范.md](D:/网易/crawler-mcp/skills/00_JS逆向作业规范.md)

仓库现在把逆向流程统一为：

1. Observe
2. Capture
3. Rebuild
4. Patch
5. DeepDive

对应参考文档：

- [reverse-workflow.md](D:/网易/crawler-mcp/docs/reference/reverse-workflow.md)
- [env-patching.md](D:/网易/crawler-mcp/docs/reference/env-patching.md)
- [fallbacks.md](D:/网易/crawler-mcp/docs/reference/fallbacks.md)
- [output-contract.md](D:/网易/crawler-mcp/docs/reference/output-contract.md)
- [task-input-template.md](D:/网易/crawler-mcp/docs/reference/task-input-template.md)
- [reverse-artifacts.md](D:/网易/crawler-mcp/docs/reference/reverse-artifacts.md)

## 任务产物模板

如果某个逆向任务要持续推进、隔天继续或交给下一个模型，先复制：

- [artifacts/tasks/_TEMPLATE](D:/网易/crawler-mcp/artifacts/tasks/_TEMPLATE)

推荐最少保留：

- `task.json`
- `network.jsonl`
- `runtime-evidence.jsonl`
- `scripts.jsonl`
- `report.md`
- `env/`
- `run/`

示例任务：

- [xhs-search-xs-20260423](D:/网易/crawler-mcp/artifacts/tasks/xhs-search-xs-20260423)

## 站点专题能力

- PDD Web `anti_content`：见 [13_PDD_anti_content逆向.md](<D:/网易/crawler-mcp/skills/13_PDD_anti_content逆向.md>)，实现位于 [analysis/pdd](D:/网易/crawler-mcp/analysis/pdd)。
- X Web `x-client-transaction-id` 与 SearchTimeline：见 [14_X_transaction_search逆向.md](<D:/网易/crawler-mcp/skills/14_X_transaction_search逆向.md>)，实现位于 [analysis/x](D:/网易/crawler-mcp/analysis/x)。

离线回归：

```powershell
python D:\网易\crawler-mcp\utils\test_site_reverse.py
node --check D:\网易\crawler-mcp\analysis\pdd\pdd_anti_content_pure_node.js
```

PDD 实时生成需要 Node.js 18+；若当前 PATH 的 Node 较旧，可通过 `CRAWLER_NODE` 指定新版 `node.exe`。X 登录态默认从 `analysis/x/config.local.json` 读取，模板见 `analysis/x/config.example.json`；环境变量可覆盖 JSON。不要提交真实凭证。

## 常用工具

当前 `server.py` 注册 71 个工具。真实工具清单可用下面命令导出：

直播弹幕可以直接复用已登录 Chrome 持续输出：

```powershell
python D:\网易\crawler-mcp\utils\douyin_live_cli.py --port 9222 --raw-output D:\网易\crawler-mcp\artifacts\live.jsonl
```

默认只输出 `WebcastChatMessage`；可用 `--method WebcastGiftMessage` 或重复参数增加礼物、点赞等消息。

捕获浏览器握手后的本地 WebSocket 消费：

```powershell
python D:\网易\crawler-mcp\utils\douyin_live_direct.py --port 9222 --duration 30 --output D:\网易\crawler-mcp\artifacts\direct-live.jsonl
```

该脚本启动时从当前 Chrome 刷新页面，提取真实握手 URL 和 Cookie，然后由本地 `websocket-client` 直接接收二进制帧；后续可用 `--save-cookie`、`--save-ws-url` 保存会话材料，短期脱离 CDP 运行。省略 `--duration` 时持续运行，连接关闭后自动重新捕获握手并重连。

完全不连接 Chrome/CDP 的 HTTP 弹幕模式：

```powershell
python D:\网易\crawler-mcp\utils\douyin_live_direct.py `
  --local-http `
  --room-url https://live.douyin.com/<WEB_RID> `
  --cookie-file D:\path\to\cookie.txt `
  --method WebcastChatMessage `
  --output D:\网易\crawler-mcp\artifacts\douyin-live-http.jsonl
```

该模式通过 room enter 获取真实 `room_id`，再获取 `web_id`，使用带 `a_bogus` 的 `/webcast/im/fetch/` protobuf 接口持续拉取，并逐轮更新 `cursor` 与 `internal_ext`。当前纯本地 HTTP 已验证；从零构造纯本地 WebSocket 握手仍受设备签名校验限制。完整流程见 [12_抖音直播逆向与纯本地弹幕.md](<D:/网易/crawler-mcp/skills/12_抖音直播逆向与纯本地弹幕.md>)。

```powershell
python D:\\网易\\crawler-mcp\\utils\\export_mcp_tools.py --format markdown
```

### 浏览器控制

- `open_browser`
- `launch_real_chrome`
- `connect_browser`
- `wait_for_new_tab`
- `list_pages`
- `switch_page`
- `navigate`
- `reload`
- `go_back`
- `click`
- `type_text`
- `scroll`
- `screenshot`

### 页面与环境查看

- `get_page_info`
- `get_cookies`
- `get_storage`
- `get_element_info`
- `query_selector_all`
- `execute_js`
- `execute_js_with_details`
- `inject_script_on_new_document`
- `get_init_scripts`

### 网络与拦截

- `get_captured_requests`
- `get_response_body`
- `save_response_body`
- `get_request_body`
- `save_request_body`
- `clear_captured_requests`
- `wait_for_request`
- `wait_for_response`
- `set_request_interception`
- `get_pending_interceptions`
- `continue_request`
- `abort_request`
- `fulfill_request`

### 调试器

- `set_xhr_breakpoint`
- `remove_xhr_breakpoint`
- `set_breakpoint`
- `debugger_get_call_stack`
- `debugger_evaluate`
- `debugger_resume`
- `debugger_step_over`
- `debugger_step_into`
- `debugger_step_out`
- `remove_breakpoint`
- `clear_debugger_state`
- `start_action_recording`
- `stop_action_recording`
- `replay_actions`
- `replay_and_capture`
- `get_special_network_events`
- `clear_init_scripts`
- `get_console_logs`
- `clear_console_logs`
- `wait_for_console`

## 使用示例

### 分析接口请求

1. `open_browser`（传入目标 URL）
2. `clear_captured_requests`
3. 在页面上触发目标操作
4. `get_captured_requests`
5. `get_response_body`
6. 如响应体较大，使用 `save_response_body` 落盘
7. 需要重复触发时，使用 `start_action_recording` / `stop_action_recording` 保存动作，再用 `replay_actions` 回放
8. 需要把动作和请求证据绑定时，使用 `replay_and_capture`

### 分析签名生成

1. `open_browser`（传入目标 URL）
2. `set_xhr_breakpoint`
3. 刷新页面或触发请求
4. `debugger_get_call_stack`
5. `debugger_evaluate`

### 开始一个标准逆向任务

1. 先填写 [task-input-template.md](D:/网易/crawler-mcp/docs/reference/task-input-template.md)
2. 复制 [artifacts/tasks/_TEMPLATE](D:/网易/crawler-mcp/artifacts/tasks/_TEMPLATE)
3. 按 [reverse-workflow.md](D:/网易/crawler-mcp/docs/reference/reverse-workflow.md) 推进
4. 结束时满足 [output-contract.md](D:/网易/crawler-mcp/docs/reference/output-contract.md)
5. 可参考 [xhs-search-xs-20260423](D:/网易/crawler-mcp/artifacts/tasks/xhs-search-xs-20260423) 看一份脱敏样例

## 目录说明

```text
crawler-mcp/
├── server.py
├── browser.py
├── skills/
├── docs/reference/
├── artifacts/tasks/_TEMPLATE/
├── analysis/
├── templates/
├── utils/
└── xhs/
```

## 说明

- `get_response_body` 默认只返回长度和解码预览；需要完整响应体时显式传 `include_body: true`。
- 请求记录和 Console 日志有内存上限；长任务应定期导出到 `artifacts/tasks/<task-id>/` 并清空内存记录。
- `Network.loadingFailed` 失败请求会进入捕获列表，并包含 `failure.errorText`、取消状态和阻断原因。
- `dump_session` 支持限制 Console 数量以及关闭 Cookie/Storage 导出。逆向复现阶段通常应保留原始登录态证据；交接或报告阶段引用摘要，避免重复展开凭证。
- 动作录制会保存 `type_text` 的输入内容；登录复现很有用，但动作 JSON 应与请求证据一样放在受控任务目录。

- 当前仓库核心是 CDP 调试与网络分析，不再把 DOM 分析器、指纹库、Playwright 能力作为主功能描述。
- 站点专题技能是实战层，总纲和 `docs/reference` 是规范层。
- 文档若与代码不一致，以 [server.py](D:/网易/crawler-mcp/server.py) 中注册的工具为准。
