# 小红书签名方案 (xhs.md)

> 本文档说明小红书 API 签名的两种实现方案及其使用场景

---

## 一、两种方案对比

| 对比项 | 方案A: 浏览器签名 | 方案B: Node.js 补环境 |
|--------|------------------|---------------------|
| 实现方式 | MCP + 真实浏览器 | Node.js + 补环境脚本 |
| 依赖 | 需要登录的浏览器 | 仅需 Node.js |
| 签名函数 | `window._webmsxyw` | `window.mnsv2` |
| 适用场景 | 调试、验证、少量请求 | 批量爬取、自动化 |
| Cookie | 自动携带 | 需手动配置 |
| 维护成本 | 低（浏览器自动更新） | 高（签名算法变化需重新补环境） |

---

## 二、方案A: 浏览器签名（MCP 工具）

### 2.1 使用场景
- 调试 API 接口
- 验证签名是否正确
- 少量请求（不想维护补环境）

### 2.2 使用步骤

```bash
# 1. 启动真实浏览器
launch_real_chrome

# 2. 在浏览器中登录小红书，打开任意页面

# 3. 连接标签页
connect_existing_tab

# 4. 生成签名
xhs_sign /api/sns/web/v1/homefeed '{"cursor_score":"","num":20}'

# 5. 或直接请求 API
xhs_api_request /api/sns/web/v1/homefeed POST {"cursor_score":"","num":20}
```

### 2.3 MCP 工具列表

| 工具 | 功能 |
|------|------|
| `xhs_sign` | 生成 X-s 和 X-t 签名 |
| `xhs_decode_sign` | 解码 X-s 签名结构 |
| `xhs_api_request` | 用签名直接请求 API |

### 2.4 注意事项
- 必须在**小红书页面**上调用
- 需要用户**已登录**
- 依赖 `window._webmsxyw` 函数

---

## 三、方案B: Node.js 补环境

### 3.1 使用场景
- 批量爬取数据
- 自动化任务
- 脱离浏览器运行

### 3.2 文件结构

```
xhs_sign/
├── code.js          # 小红书签名核心代码（混淆）
├── ceshi.js         # 补环境脚本（开发调试用）
├── aa.js            # 补环境脚本（可运行版本）
├── get-xs.js        # Node.js 生成签名
├── get_data.py      # Python 爬虫（首页推荐）
├── get_search.py    # Python 爬虫（搜索）
└── skill.md         # 补环境技巧文档
```

### 3.3 签名生成

```javascript
// get-xs.js
const crypto = require('crypto');

// 加载补环境和签名代码
require('./aa.js');

// 生成签名
function getSign(url, data) {
    const a1 = crypto.randomBytes(16).toString('hex');
    const b1 = crypto.randomBytes(16).toString('hex');
    return window.mnsv2(url + JSON.stringify(data), a1, b1);
}

// 使用
const sign = getSign('/api/sns/web/v1/homefeed', {
    cursor_score: "",
    num: 20
});
console.log(sign);  // mns0201_xxx...
```

### 3.4 Python 调用

```python
# get_data.py 示例
import subprocess
import json

def get_xs(url, data):
    """调用 Node.js 生成签名"""
    payload = url + json.dumps(data, separators=(',', ':'))
    result = subprocess.run(
        ['node', 'get-xs.js', payload],
        capture_output=True,
        text=True
    )
    return result.stdout.strip()

# 请求头
headers = {
    'X-s': get_xs('/api/sns/web/v1/homefeed', data),
    'X-t': str(int(time.time() * 1000)),
    'Cookie': 'your_cookie_here',
    # ...
}
```

### 3.5 补环境要点

详见 [skill.md](./skill.md)

核心原则：
1. **原型链补完整** - DOM 对象补到 Node 或 EventTarget
2. **safeFunction 必加** - 所有函数都要伪装 toString
3. **监控要全面** - navigator、screen、document 都要 watch

---

## 四、选择建议

```
┌─────────────────────────────────────────────────────┐
│                     开始                             │
└─────────────────────────────────────────────────────┘
                        │
                        ▼
            ┌───────────────────────┐
            │   需要批量爬取吗？      │
            └───────────────────────┘
                   /        \
                 是           否
                 /              \
               ▼                ▼
      ┌────────────────┐  ┌────────────────┐
      │ 方案B:          │  │ 方案A:          │
      │ Node.js 补环境   │  │ 浏览器签名      │
      └────────────────┘  └────────────────┘
```

---

## 五、API 接口文档

### 5.1 首页推荐

```
POST https://edith.xiaohongshu.com/api/sns/web/v1/homefeed

请求体:
{
    "cursor_score": "",
    "num": 35,
    "refresh_type": 1,
    "note_index": 0,
    "unread_begin_note_id": "",
    "unread_end_note_id": "",
    "unread_note_count": 0,
    "category": "homefeed_recommend",
    "search_key": "",
    "need_num": 10,
    "image_formats": ["jpg", "webp", "avif"],
    "need_filter_image": false
}
```

### 5.2 搜索

```
POST https://edith.xiaohongshu.com/api/sns/web/v1/search/notes

请求体:
{
    "keyword": "搜索关键词",
    "page": 1,
    "page_size": 20,
    "search_id": "",
    "sort": "general",
    "note_type": 0,
    "ext_flags": [],
    "image_formats": ["jpg", "webp", "avif"]
}
```

### 5.3 请求头

| Header | 说明 |
|--------|------|
| `X-s` | 签名（mns0201_xxx 或 XYW_xxx） |
| `X-t` | 时间戳（毫秒） |
| `X-s-common` | 通用签名（部分接口需要） |
| `Cookie` | 登录凭证 |

---

## 六、常见问题

### Q1: 签名失败怎么办？
- 方案A: 确保在小红书页面上，且已登录
- 方案B: 检查补环境是否完整，参考 skill.md

### Q2: Cookie 怎么获取？
- 浏览器登录后，F12 → Network → 复制 Cookie

### Q3: 签名算法更新了怎么办？
- 方案A: 浏览器自动更新，无需处理
- 方案B: 重新抓取 code.js，重新补环境

### Q4: 两种方案的签名格式不同？
- `window._webmsxyw` 返回 `XYW_xxx` 格式
- `window.mnsv2` 返回 `mns0201_xxx` 格式
- 两种格式服务器都接受
