
# PDD anti_content 逆向技能

用途：维护 PDD Web `anti_content` 本地复现与请求验证流程。

当前项目脚本：

```text
D:\网易\crawler-mcp\analysis\pdd\pdd_anti_content_pure_node.js
D:\网易\crawler-mcp\analysis\pdd\pdd_fbez_logic_analyzer.js
D:\网易\crawler-mcp\analysis\pdd\verify_api.py
```

入口链：

```text
subject.js / TPp2.a()
  -> /api/server/_stm
  -> new fbeZ({ serverTime })
  -> messagePackSync()
  -> ue()
  -> "0aq" + encode(deflate(payload + integrity))
```

常用命令：

```powershell
node D:\网易\crawler-mcp\analysis\pdd\pdd_anti_content_pure_node.js
node D:\网易\crawler-mcp\analysis\pdd\pdd_anti_content_pure_node.js --server-time 1784126311497
node D:\网易\crawler-mcp\analysis\pdd\pdd_fbez_logic_analyzer.js --decoded
python D:\网易\crawler-mcp\analysis\pdd\verify_api.py
```

请求成功判据：

```text
HTTP 200
{"success":true,"error_code":1000000,"result":[...]}
```

排错：

- Python `ProxyError`：使用 `requests.Session()` 并设置 `session.trust_env = False`。
- 生成失败：先 `node --check`，再跑 analyzer 确认 `messagePackSync` 仍存在。
- 接口不成功：对比 UA、Referer、cookie、`tf_id`、`size` 和 `anti_content` 长度。
