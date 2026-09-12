
# X transaction ID 与搜索接口逆向

## 适用范围

用于 X Web：

- `SearchTimeline` GraphQL 请求抓取与重放；
- `x-client-transaction-id` 动态定位；
- Webpack chunk/module 解析；
- `ondemand.s`、verification meta、SVG animation；
- 搜索结果解析与 Top/Latest 对比。

## 定位工作流

```text
Network 抓 SearchTimeline
  -> Sources 搜 x-client-transaction-id
  -> main.js filter
  -> r.e(chunkId)
  -> r.bind(r, moduleId)
  -> r.u(chunkId) 得到 ondemand.s 文件
  -> module default factory
  -> async generator(path, method)
```

不要把 Webpack 先验当成现场证据。需要时依次验证：

```js
r.e.toString()
Object.keys(r.f)
r.f.j.toString()
r.u(chunkId)
r.p
```

## 当前算法摘要

```text
key = Base64Decode(twitter-site-verification)        # 48 bytes
time = floor(unixTime - 1682924400)                  # 4 bytes LE
animationKey = SVG frames + cubic-bezier interpolation
hash = SHA256(METHOD!path!time + obfiowerehiring + animationKey)[:16]
plain = key + time + hash + byte(3)
output = randomByte + XOR(plain, randomByte)
transaction = Base64(output).rstrip("=")
```

## 请求要求

```text
authorization              required
Cookie auth_token          required for logged-in search
x-csrf-token               required
Cookie ct0                 must equal x-csrf-token
x-client-transaction-id    required and time/page dependent
```

错误值可能造成约一分钟的伪 404 冷却。做单变量实验时，每个实验前后运行完整成功基线，避免把冷却误判为字段绑定。

## 代码

当前项目：

```text
D:\网易\crawler-mcp\analysis\x\x_client_transaction.py
D:\网易\crawler-mcp\analysis\x\search_timeline.py
D:\网易\crawler-mcp\analysis\x\config.example.json
```

纯 Python 实现不依赖浏览器或 BeautifulSoup，只依赖 `requests`；搜索模板额外使用 `loguru`。

## 搜索相关性

```text
variables.product = Top       相关性/质量排序
variables.product = Latest    时间排序
variables.rawQuery            支持精确词、lang、filter、from、since 等操作符
cursor                        只负责分页
```

比较相关性时固定 Cookie、queryId、features、count 和时间窗口，每次只改一个变量，并记录前 10 个 tweet ID。
