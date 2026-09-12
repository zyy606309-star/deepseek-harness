# 瑞数 6 记录

## 这份记录的用途

这份文档不是讲原理，主要是防止以后隔太久又忘了怎么做。

目标只有一个：

1. 重新拿到首包挑战页
2. 提取动态输入
3. 本地跑 JS 生成 cookie
4. 带 cookie 发第二次请求
5. 拿到 `200` 的业务页

---

## 目录对应关系

```text
analysis/rs6/
├─ docs/
│  └─ flow.md
├─ encoders/
│  ├─ env.js
│  ├─ encrypt_js_code.js
│  ├─ decode_external.js
│  └─ request_main.js
├─ samples/
│  ├─ first_challenge_202.html
│  ├─ second_page_200.html
│  └─ server_cookies.json
└─ scripts/
   └─ extract_rs6_payload.py
```

文件作用：

1. `scripts/extract_rs6_payload.py`
   主流程脚本，正常情况下以后先跑它。
2. `encoders/env.js`
   Node 补环境模板。
3. `encoders/encrypt_js_code.js`
   首包页面里提取出的第一段内联 JS。
4. `encoders/decode_external.js`
   首包页面里提取出的外链 JS。
5. `encoders/request_main.js`
   运行入口，最终只输出 `document.cookie`。
6. `samples/first_challenge_202.html`
   成功抓到的首包挑战页样本。
7. `samples/second_page_200.html`
   成功抓到的第二次请求业务页样本。

---

## 最短使用步骤

以后忘了的时候，先只看这一节。

### 第 1 步：跑主流程

运行：

```powershell
python D:\网易\crawler-mcp\analysis\rs6\scripts\extract_rs6_payload.py
```

### 第 2 步：看 3 个关键结果

只看下面三件事：

1. 首次请求是不是 `202`
2. `request_main.js` 有没有成功输出 `js_cookie`
3. 第二次请求是不是 `200`

如果这三件事都对了，就说明整条链路已经通了。

### 第 3 步：看落盘文件

跑完以后，这几个文件应该已经更新：

1. `encoders/env.js`
2. `encoders/encrypt_js_code.js`
3. `encoders/decode_external.js`
4. `samples/server_cookies.json`

如果你还想保留页面内容，可以把本次抓到的：

1. 首包挑战页
2. 第二次请求业务页

另外存成样本。

---

## 标准操作链路

### 1. 发第一次请求

请求目标：

```text
http://epub.cnipa.gov.cn/
```

预期结果：

1. 返回 `202`
2. 返回挑战页 HTML
3. 响应 cookie 里至少有服务端首包 cookie

这一步的作用：

1. 拿挑战页
2. 拿动态输入
3. 拿服务端首包 cookie

### 2. 从挑战页提取 3 类东西

必须提：

1. `meta id="K5MK4FPPNWrv"` 的 `content`
2. 第一个 `<script type="text/javascript" r="m">` 里的内联 JS
3. 第一个外链 JS 的 URL 和内容

注意：

1. 这里只取第一个满足条件的内联脚本
2. 外链也只取当前链路真正用到的那一个

### 3. 更新本地运行文件

把刚提出来的内容写到：

1. `env.js`
   只更新 `content = "...";`
2. `encrypt_js_code.js`
   放内联 JS
3. `decode_external.js`
   放外链 JS

这里的原则是：

1. 动态输入必须每轮更新
2. 不能沿用上一轮的旧值

### 4. 本地执行 JS

运行入口是：

```javascript
require("./env.js");
require("./encrypt_js_code.js");
require("./decode_external.js");

function main() {
  setTimeout(() => {
    console.log(document.cookie);
    process.exit(0);
  }, 3000);
}

main();
```

也就是：

1. 先补环境
2. 再跑内联 JS
3. 再跑外链 JS
4. 最后只取 `document.cookie`

### 5. 提取 JS 产出的 cookie

从 `request_main.js` 输出里只取：

```text
name=value
```

不要带：

1. `path=`
2. `expires=`
3. 其它属性

只要 cookie pair。

### 6. 把 JS cookie 加进 session

这一步不要单独拼裸请求，直接沿用 `requests.Session()`。

原因：

1. 首包 cookie 需要继承
2. JS cookie 只是在首包基础上追加

正确思路：

1. 第一次请求得到 session
2. session 里已经有首包 cookie
3. 把 JS 生成的 cookie 再塞进去
4. 用同一个 session 发第二次请求

### 7. 发第二次请求

还是请求：

```text
http://epub.cnipa.gov.cn/
```

预期结果：

1. 返回 `200`
2. 返回业务页 HTML
3. 页面里出现正常首页内容，而不是挑战页

---

## 这次实际证明过的关键点

### 1. 这次链路能跑通

这条链路已经验证过是通的：

```text
首包 202 -> 提取动态输入 -> 本地跑 JS -> 生成 cookie -> 二次请求 200
```

以后先相信这条链路，不要重新瞎试别的顺序。

### 2. session 必须复用

不要把第二次请求写成“完全独立的新请求”。

必须：

1. 第一次请求用 `Session`
2. JS cookie 追加到同一个 `Session`
3. 第二次请求继续用这个 `Session`

### 3. 第二次请求的 HTML 要单独保存

不要只看状态码。

最好至少保存：

1. 首包挑战页
2. 第二次业务页

这样以后忘了时可以直接对照。

### 4. `request_main.js` 只负责吐 cookie

这个文件不要写复杂逻辑。

它最合适的职责就是：

1. 加载 3 个 JS 文件
2. 等 3 秒
3. 输出 `document.cookie`
4. 退出

这样最稳，也最好调。

---

## 这次补环境时踩过的坑

### 1. 不要执着于想当然的检测点

不要先假设“它一定会走某个 DOM 检测”。

正确做法：

1. 先看真实日志
2. 看它实际调用了什么
3. 再补当前真正在走的路径

### 2. 集合接口不要轻易改成非空

像：

1. `getElementsByTagName`
2. `querySelectorAll`

这类接口默认先返回空集合。

原因：

1. 非空集合会直接改变业务分支
2. 容易把脚本带进错误路径
3. 一旦带偏，就会出现大量重复日志或执行不结束

### 3. 参数日志优先于复杂返回值

先看：

1. `getElementById` 查了什么
2. `getElementsByTagName` 查了什么
3. `setAttribute` 写了什么

再决定是否补返回值。

### 4. 高频日志必须限流

像 `innerHTML` 这种高频字段，如果不做限流，很快就看不到真正的新缺口了。

### 5. 成功链路比局部猜测更重要

一旦已经稳定拿到第二次 `200` 页面，就不要继续在无效分支上深挖。

先把成功链路记录下来，后面再说。

---

## 以后忘了时怎么排查

### 情况 1：首包不是 202

先查：

1. 请求头是否变了
2. 目标站点是否换规则了
3. 当前网络环境是否有差异

### 情况 2：`request_main.js` 没输出 cookie

先查：

1. `env.js` 里的 `content` 是否已更新
2. `encrypt_js_code.js` 是否是本轮首包内容
3. `decode_external.js` 是否是本轮外链内容
4. 补环境是否改坏了

### 情况 3：第二次请求不是 200

先查：

1. 是否复用了同一个 `Session`
2. JS cookie 是否只取了 `name=value`
3. session 里是否同时带了首包 cookie 和 JS cookie
4. 当前页面动态输入是否和本轮页面匹配

### 情况 4：补环境越补越乱

先做：

1. 回到最小环境
2. 保留吐环境脚本
3. 只补当前明确缺口
4. 不要一次补太多

---

## 以后建议的使用习惯

以后再做类似站点时，建议固定保留：

1. 主流程脚本
2. 最小 env 模板
3. request_main.js
4. 一份首包样本
5. 一份二次请求成功页样本
6. 一份“忘了就看这里”的流程文档

这样下次再捡起来时，不用从零回忆。
