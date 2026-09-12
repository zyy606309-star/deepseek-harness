
# PDD Web anti_content 逆向

## 目标

```text
页面：https://www.pinduoduo.com/home/girlclothes/
接口：https://apiv2.pinduoduo.com/api/gindex/tf/query_tf_goods_info
参数：anti_content
```

## 浏览器入口链

```text
subject.js / jomW getGoods()
  -> TPp2.a()
  -> GET /api/server/_stm
  -> new fbeZ({ serverTime })
  -> generator.messagePackSync()
  -> ue()
  -> "0aq" + encode(deflate(payload + integrity))
```

`anti_content` 不是单一 hash，而是浏览器状态、行为事件、时间、Cookie 指纹和函数源码完整性共同组成的压缩包。

## 核心字段

```text
1/2    touchstart / mousedown
24/25  touchmove / mousemove
4      click
3      scroll
7      location.href / port
8      screen 可用尺寸
9      随机对 + serverTime
10     automation/headless bitset
11     当前 URL
12/13  orientation/motion API
14     Date.now() - serverTime 更新时间
15     User-Agent
16/17  nano cookie/storage fingerprint
18     referrer
19     pdd_user_id
20     api_uid
21     pack 调用次数
22     客户端初始时间
23     pdd_vds
26     浏览器类型 bitset
```

最终结构：

```text
collectors -> payload header -> pako.deflate -> custom encode -> "0aq" prefix
```

## 纯 Node 复现

`pdd_anti_content_pure_node.js` 会：

1. 下载或读取当前 `subject.js`。
2. 提取 `fbeZ` Webpack 模块。
3. 在 `node:vm` 中运行模块。
4. 模拟 `window/document/navigator/screen/history/location`。
5. 注入鼠标、点击和滚动事件。
6. 获取 `_stm.server_time`。
7. 调用 `messagePackSync()` 输出 `0aq...`。

运行：

```powershell
node .\pdd_anti_content_pure_node.js
node .\pdd_anti_content_pure_node.js --server-time 1784126311497
node .\pdd_anti_content_pure_node.js --help
```

使用本地 bundle 隔离网络变化：

```powershell
node .\pdd_anti_content_pure_node.js --bundle-file .\subject.js --server-time 1784126311497
```

## 分析工具

```powershell
node .\pdd_fbez_logic_analyzer.js --decoded
node .\probe_fbez.js
```

`pdd_fbez_logic_analyzer.js` 用于输出 `TPp2 -> fbeZ -> ue()`、prototype 方法和 collector tag 映射。`probe_fbez.js` 是早期最小探针，保留作回归定位。

## Python 请求集成

```powershell
python .\verify_api.py
```

Python 会调用 Node 生成实时 `anti_content`，再请求 `query_tf_goods_info`。若系统代理变量损坏，脚本使用：

```python
session = requests.Session()
session.trust_env = False
```

## 浏览器对照

`pdd_anti_content_browser.py` 可连接本地调试 Chrome，观察浏览器自身生成的请求参数：

```powershell
python .\pdd_anti_content_browser.py --port 9222 --timeout 20
```

它仅观察 outgoing request，不重放请求。

## 依赖与版本

- Node.js 18+（内置 `fetch`、`node:vm`、`zlib`）。若 PATH 中版本较旧，先设置 `CRAWLER_NODE` 为新版 `node.exe` 的完整路径。
- Python 3.8+。
- `requests`。
- 可选：`pyppeteer`，只供浏览器对照脚本使用。

## 常见失效点

1. `subject.js` URL 或模块 ID 更新。
2. `_stm` 网络失败或代理异常。
3. UA、页面 URL、Cookie 与生成环境不一致。
4. 事件时间差过小，被 collector 过滤。
5. `Wt.toString() + ue.toString()` 完整性源码变化。

先用固定 `--server-time` 和本地 bundle 分离网络问题，再用 analyzer 确认 `messagePackSync` 是否仍存在。
