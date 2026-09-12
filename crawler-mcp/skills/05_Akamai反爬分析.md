# Akamai _abck 验证流程

> 如果这是一个完整逆向任务，建议先读 [00_JS逆向作业规范.md](/D:/网易/crawler-mcp/skills/00_JS逆向作业规范.md)，再决定是只做浏览器自动化复现，还是继续进入本地重建与补环境。

## 核心流程

> 下面是某类 Akamai Bot Manager 流程的成功样本，不是所有站点和版本的固定协议。必须以当前页面的请求、响应头、Cookie 变化和脚本行为确认。

```
1. GET HTML
   ↓
   Response: Set-Cookie: _abck=xxx~-1~xxx (初始未验证)
   提取: <script src="/lUuI09H8kk2lCTn.../dlZdB/nwEPFIB">

2. GET JS 外部链接
   ↓
   /lUuI09H8kk2lCTn.../dlZdB/nwEPFIB
   返回: 一大段混淆 JS (创建 bmak 对象，收集指纹)

3. JS 自动执行
   ↓
   bmak.get_telemetry() 生成 sensor_data

4. POST 同一个外部链接
   ↓
   POST /lUuI09H8kk2lCTn.../dlZdB/nwEPFIB
   Body: {"sensor_data": "3;0;1;65536;..."}
   ↓
   Response: Set-Cookie: _abck=xxx~0~xxx

5. 检查状态
   ↓
   part[1] == '-1' → 该样本显示未验证
   part[1] == '0'  → 该样本显示验证通过
```

## 关键点

- **同一个 URL**: 既能 GET (返回JS) 又能 POST (验证)
- **样本状态位**: 该样本中 `_abck` Cookie 的第二段是 `~-1~` 或 `~0~`
- **验证标准**: 只能在当前站点确认该状态位与后续业务请求成功存在相关性

## 实现方式

### 推荐：浏览器自动化

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto("https://www.dhl.com/tracking.html")
    page.wait_for_timeout(3000)  # 等待验证完成
    cookies = page.context.cookies()
    browser.close()
```

验证时至少保存：初始 Cookie、脚本 URL、POST 请求摘要、更新后的 Cookie、业务请求结果和时间窗口。只看 `_abck` 字符串不能证明页面已经通过验证。

### 不推荐：手动模拟

- 需要逆向混淆 JS
- 需要生成动态 sensor_data (极难)
- 硬编码会被识别为重放攻击
