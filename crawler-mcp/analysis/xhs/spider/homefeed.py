"""
小红书首页推荐爬虫
"""
import json
import subprocess
import time
from pathlib import Path
import requests
from loguru import logger

# ==================== 配置 ====================

BASE_DIR = Path(__file__).parent.parent
CORE_DIR = BASE_DIR / 'core'
LOG_DIR = BASE_DIR / 'logs'

# 日志配置
LOG_DIR.mkdir(exist_ok=True)
logger.add(
    LOG_DIR / "homefeed.log",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level:^7} | {message}",
    rotation="00:00",
    retention="7 days",
    encoding="utf-8",
    level="DEBUG"
)

# API 配置
API_URL = "https://edith.xiaohongshu.com/api/sns/web/v1/homefeed"
API_PATH = "/api/sns/web/v1/homefeed"

# 请求配置（需要替换为有效的 Cookie）
COOKIES = {
    "a1": "19d0909dafbyj1rgamailt8t9s9gbqcvio3cyqpsn50000101968",
    "web_session": "040069b1de3bf4578efe8aecf53b4b20e6b4d2",
    "webId": "6d1ee706e57415efdc991b4922521984",
    "xsecappid": "xhs-pc-web",
}

HEADERS = {
    "content-type": "application/json;charset=UTF-8",
    "origin": "https://www.xiaohongshu.com",
    "referer": "https://www.xiaohongshu.com/",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/134.0.0.0 Safari/537.36",
}


# ==================== 核心函数 ====================

def get_signature(data: dict) -> str:
    """调用 Node.js 生成签名"""
    sign_js = CORE_DIR / 'sign.js'
    cmd = ['node', str(sign_js), API_PATH, json.dumps(data, ensure_ascii=False)]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', timeout=5)
    output = result.stdout.strip()
    # 提取签名（跳过调试输出）
    for line in output.split('\n'):
        if line.startswith('XYS_') or line.startswith('mns'):
            return line
    return output.split('\n')[-1] if output else ''


def fetch_homefeed(cursor_score: str = "", num: int = 35) -> dict:
    """获取首页推荐"""
    data = {
        "cursor_score": cursor_score,
        "num": num,
        "refresh_type": 1,
        "note_index": 0,
        "unread_begin_note_id": "",
        "unread_end_note_id": "",
        "unread_note_count": 0,
        "category": "homefeed_recommend",
        "search_key": "",
        "need_num": 10,
        "image_formats": ["jpg", "webp", "avif"],
        "need_filter_image": False
    }

    headers = HEADERS.copy()
    headers["x-s"] = get_signature(data)
    headers["x-t"] = str(int(time.time() * 1000))

    resp = requests.post(
        API_URL,
        headers=headers,
        cookies=COOKIES,
        data=json.dumps(data, separators=(',', ':'))
    )
    return resp.json()


def fetch_all(max_pages: int = 10, delay: float = 1.0) -> list:
    """获取多页推荐，自动去重"""
    seen_ids = set()
    results = []
    cursor_score = ""

    for page in range(1, max_pages + 1):
        logger.info(f"获取首页推荐 - 第 {page} 页")

        try:
            data = fetch_homefeed(cursor_score)
            items = data.get('data', {}).get('items', [])

            if not items:
                logger.info("没有更多数据")
                break

            for item in items:
                item_id = item.get('id')
                if item_id and item_id not in seen_ids:
                    seen_ids.add(item_id)
                    results.append(item)

            cursor_score = data.get('data', {}).get('cursor_score', '')
            logger.info(f"当前页新增 {len(items)} 条，总计 {len(results)} 条")
            time.sleep(delay)

        except Exception as e:
            logger.error(f"第 {page} 页失败: {e}")
            break

    return results


# ==================== 主程序 ====================

if __name__ == "__main__":
    results = fetch_all(max_pages=5)

    # 保存结果
    output_file = LOG_DIR / f"homefeed_{int(time.time())}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    logger.info(f"获取完成，共 {len(results)} 条，保存到 {output_file}")
