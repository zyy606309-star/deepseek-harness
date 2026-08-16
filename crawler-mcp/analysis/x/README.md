
# X Web transaction ID 与 SearchTimeline 逆向

## 目标

```text
接口：https://x.com/i/api/graphql/{queryId}/SearchTimeline
关键头：x-client-transaction-id
认证：authorization + Cookie + x-csrf-token
```

## 浏览器定位链

在 `main.*.js` 搜索 `x-client-transaction-id`，得到：

```js
r.e(59924)
  .then(r.bind(r, 208932))
  .then(module => resolve(module.default()));
```

Webpack runtime 关系：

```text
r.e(chunkId)    ensure/load chunk
r.u(chunkId)    chunk ID -> filename
r.p             public path
r(208932)       execute module and return exports
```

当前观察版本：

```text
chunk ID：59924
module ID：208932
文件：ondemand.s.7fac826a.js
```

这些 ID/hash 会随前端部署变化，不能作为永久常量。纯 Python 实现会从当前首页和当前 `ondemand.s` 动态提取数据。

## 模块结构

```text
module 208932 default export
  -> factory()
  -> 初始化 verification key 和 SVG animation
  -> 返回 async generator(path, method)
  -> 生成 transaction ID
```

## 生成算法

页面输入：

```text
meta[name="twitter-site-verification"]
loading-x-anim-0 ... loading-x-anim-3
当前 ondemand.s 中的 key byte indices
```

当前索引：

```text
SVG group = key[5] % 4
row index = key[24] % 16
frame time = (key[29] % 16) * (key[31] % 16) * (key[22] % 16)
```

SVG path 中编码起止 RGB、旋转角和 cubic-bezier 控制点。插值得到 `animationKey`。

Hash 输入：

```text
METHOD + "!" + path + "!" + relativeTime
+ "obfiowerehiring"
+ animationKey
```

时间：

```text
relativeTime = floor(unixTime - 1682924400)
```

最终 payload：

```text
1 byte   random mask
48 bytes twitter-site-verification key
4 bytes  relativeTime, little-endian
16 bytes SHA-256 prefix
1 byte   version = 3
```

除首字节外均与 random mask XOR，随后 Base64 并去除 `=`：

```text
70 raw bytes -> 94 Base64 chars
```

## 运行

依赖：

```powershell
pip install -r .\requirements.txt
```

复制 JSON 配置模板并填写本机登录态：

```powershell
Copy-Item .\config.example.json .\config.local.json
python .\search_timeline.py
```

Cookie 要求：

```text
cookies 至少包含 auth_token 和 ct0
x-csrf-token 默认自动使用 cookies.ct0
```

`authorization` 不是 `auth_token` Cookie。应从浏览器真实 SearchTimeline 请求头复制完整的 `Authorization: Bearer ...` 值。

默认读取脚本同目录的 `config.local.json`，不需要重复配置 `csrf_token`。也可通过 `X_CONFIG_FILE` 指定其他 JSON 路径；已有的 `X_AUTHORIZATION`、`X_CSRF_TOKEN`、`X_COOKIES_JSON`、`X_PROXY` 等环境变量仍可覆盖 JSON，便于 CI 或临时调试。

`graphql_url` 可以省略，脚本默认使用当前案例已验证的 SearchTimeline operation。若 X 更新了 query ID，再在配置中添加完整 `graphql_url` 覆盖。

脚本每次请求前会：

1. GET `https://x.com/home`。
2. 解析 verification meta 和 SVG。
3. 发现当前 `ondemand.s` URL 和 indices。
4. 生成新的 transaction ID。
5. 请求 `SearchTimeline`。
6. 输出帖子链接、正文、作者、评论数、点赞数和北京时间。

## 评论

评论通过 `TweetDetail` 获取。默认关闭；在 `config.local.json` 中开启：

```json
"comments": {
  "enabled": true,
  "max_posts": 3,
  "max_pages": 1,
  "graphql_url": "https://x.com/i/api/graphql/rZA6K31W4E90vZKBmxXV3g/TweetDetail",
  "controller_data": ""
}
```

`max_posts` 限制从搜索结果中抓多少条帖子的评论，`max_pages` 限制每条帖子的 Bottom cursor 页数。脚本会按 TweetDetail URL path 重新生成 `x-client-transaction-id`。当前抓包的 `controller_data` 已作为默认值；若现场请求更新，可在配置中覆盖。

## 搜索参数

```text
X_SEARCH_QUERY    rawQuery，默认“遗忘之海”
X_SEARCH_PRODUCT  Top 或 Latest
X_QUERY_SOURCE    typed_query / recent_search_click
```

`variables/features/cursor` 不参与 transaction ID hash；transaction ID 绑定的是 method、path、页面派生值和时间。

## 已验证结论

- `authorization` 必须存在。
- `x-csrf-token` 必须存在并与 `ct0` 一致。
- `x-client-transaction-id` 必须存在且有效。
- 错误 CSRF/transaction 可能触发短时间伪 404 冷却。
- 正确 transaction ID 可连续请求，不是一次性 nonce。
- 写死 transaction ID 会因时间和页面 verification/SVG 轮换失效。

## 常见失效点

1. GraphQL `queryId` 更新，需要从浏览器重新抓 `SearchTimeline`。
2. 登录 Cookie 或 CSRF 过期。
3. `ondemand.s` 混淆结构改变，indices 正则失效。
4. 代理未配置且目标网络不可直连。
5. 错误请求触发短时 404，需等待冷却后用完整基线复测。
