"""
阶段 1: 验证流程确认
捕获 DHL 网站的 Akamai 验证流程中的所有请求
"""

import asyncio
import json
import sys
import os

# 添加父目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from browser import BrowserManager


async def main():
    """主函数"""
    browser_manager = BrowserManager()

    try:
        print("=" * 60)
        print("阶段 1: 验证流程确认")
        print("=" * 60)

        # 步骤 1: 启动真实 Chrome 浏览器
        print("\n[1/5] 启动真实 Chrome 浏览器（端口 9222）...")
        result = await browser_manager.launch_real_chrome(port=9222)
        print(f"✓ {result}")

        # 步骤 2: 等待用户创建新标签页
        print("\n[2/5] 等待用户在浏览器中创建新标签页...")
        print("提示: 请在 Chrome 中按 Ctrl+T 创建新标签页")
        result = await browser_manager.wait_for_new_tab(timeout=60)
        print(f"✓ {result}")

        # 步骤 3: 清空请求记录
        print("\n[3/5] 清空网络请求记录...")
        await browser_manager.clear_captured_requests()
        print("✓ 请求记录已清空")

        # 步骤 4: 导航到目标页面
        print("\n[4/5] 访问 DHL 追踪页面...")
        url = "https://www.dhl.com/us-en/home/tracking.html?tracking-id=12345678&submit=1"
        result = await browser_manager.navigate(url)
        print(f"✓ {result}")

        # 等待页面加载和 Akamai 验证完成
        print("\n等待 Akamai 验证完成（10 秒）...")
        await asyncio.sleep(10)

        # 步骤 5: 获取所有捕获的请求
        print("\n[5/5] 获取捕获的请求...")
        requests = await browser_manager.get_captured_requests(limit=200)

        print(f"\n✓ 共捕获 {len(requests)} 个请求")

        # 分析请求
        print("\n" + "=" * 60)
        print("请求分析")
        print("=" * 60)

        akamai_requests = []
        html_requests = []
        other_requests = []

        for req in requests:
            url = req.get('url', '')
            method = req.get('method', '')

            if 'dlZdB' in url or 'akam' in url.lower():
                akamai_requests.append(req)
                print(f"\n[Akamai] {method} {url[:100]}")
                if req.get('postData'):
                    print(f"  Body: {req['postData'][:200]}")
            elif 'tracking.html' in url:
                html_requests.append(req)
                print(f"\n[HTML] {method} {url[:100]}")
            else:
                other_requests.append(req)

        # 保存完整请求列表
        output_file = "01_requests.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(requests, f, indent=2, ensure_ascii=False)
        print(f"\n✓ 完整请求列表已保存到: {output_file}")

        # 保存 Akamai 请求
        akamai_file = "01_akamai_requests.json"
        with open(akamai_file, 'w', encoding='utf-8') as f:
            json.dump(akamai_requests, f, indent=2, ensure_ascii=False)
        print(f"✓ Akamai 请求已保存到: {akamai_file}")

        # 获取 Cookie
        print("\n" + "=" * 60)
        print("Cookie 分析")
        print("=" * 60)

        result = await browser_manager.execute_js("document.cookie")
        cookies = result.split('; ')

        abck_cookie = None
        for cookie in cookies:
            if cookie.startswith('_abck='):
                abck_cookie = cookie
                parts = cookie.split('~')
                print(f"\n_abck Cookie 找到:")
                print(f"  完整值: {cookie[:100]}...")
                if len(parts) >= 2:
                    status = parts[1]
                    if status == '-1':
                        print(f"  状态: 未验证 (~-1~)")
                    elif status == '0':
                        print(f"  状态: 验证通过 (~0~)")
                    else:
                        print(f"  状态: {status}")
                break

        if not abck_cookie:
            print("\n⚠ 未找到 _abck cookie")

        # 保存 Cookie
        cookie_file = "01_cookies.txt"
        with open(cookie_file, 'w', encoding='utf-8') as f:
            f.write(result)
        print(f"\n✓ Cookie 已保存到: {cookie_file}")

        # 生成流程图
        print("\n" + "=" * 60)
        print("生成验证流程图")
        print("=" * 60)

        flow_diagram = """# DHL Akamai 验证流程图

## 捕获时间
{timestamp}

## 验证流程（5 步）

```
Step 1: GET /tracking.html
  ↓ Response: Set-Cookie: _abck=xxx~-1~xxx (初始未验证)
  ↓ HTML 中提取: <script src="/lUuI09H8kk2lCTn.../dlZdB/nwEPFIB">

Step 2: GET /lUuI09H8kk2lCTn.../dlZdB/nwEPFIB
  ↓ Response: 混淆 JS 代码（创建 bmak 对象）

Step 3: JS 自动执行
  ↓ bmak.get_telemetry() 生成 sensor_data

Step 4: POST /lUuI09H8kk2lCTn.../dlZdB/nwEPFIB
  ↓ Body: {{"sensor_data": "3;0;1;65536;..."}}
  ↓ Response: Set-Cookie: _abck=xxx~0~xxx (验证通过)

Step 5: 验证通过
  ↓ _abck 的第二段从 ~-1~ 变为 ~0~
```

## 捕获的请求统计

- 总请求数: {total}
- Akamai 相关: {akamai}
- HTML 请求: {html}
- 其他请求: {other}

## 关键 URL

### HTML 请求
{html_urls}

### Akamai 请求
{akamai_urls}

## Cookie 状态

```
{cookie_status}
```

## 下一步

进入阶段 2: bmak 对象定位
- 设置 XHR 断点拦截 sensor_data POST 请求
- 获取调用栈
- 探索 bmak 对象结构
"""

        import datetime

        html_urls_str = "\n".join([f"- {req['method']} {req['url']}" for req in html_requests[:5]])
        akamai_urls_str = "\n".join([f"- {req['method']} {req['url'][:150]}" for req in akamai_requests[:10]])

        flow_content = flow_diagram.format(
            timestamp=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            total=len(requests),
            akamai=len(akamai_requests),
            html=len(html_requests),
            other=len(other_requests),
            html_urls=html_urls_str or "无",
            akamai_urls=akamai_urls_str or "无",
            cookie_status=abck_cookie or "未找到 _abck cookie"
        )

        flow_file = "01_flow_diagram.md"
        with open(flow_file, 'w', encoding='utf-8') as f:
            f.write(flow_content)
        print(f"\n✓ 验证流程图已保存到: {flow_file}")

        print("\n" + "=" * 60)
        print("阶段 1 完成！")
        print("=" * 60)
        print(f"\n产出文件:")
        print(f"  - {flow_file}")
        print(f"  - {output_file}")
        print(f"  - {akamai_file}")
        print(f"  - {cookie_file}")

    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # 不关闭浏览器，留给后续阶段使用
        print("\n提示: 浏览器保持打开状态，供后续阶段使用")


if __name__ == "__main__":
    asyncio.run(main())
