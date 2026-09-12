"""
小红书搜索爬虫
"""
import json
import subprocess
import time
import random
import string
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
    LOG_DIR / "search.log",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level:^7} | {message}",
    rotation="00:00",
    retention="7 days",
    encoding="utf-8",
    level="DEBUG"
)

# API 配置
API_URL = "https://edith.xiaohongshu.com/api/sns/web/v1/search/notes"
API_PATH = "/api/sns/web/v1/search/notes"

# 请求配置（需要替换为有效的 Cookie）
COOKIES = {
    "abRequestId": "76e1e0e3-c960-56c2-9ee7-d63b5bfe55a6",
    "xsecappid": "xhs-pc-web",
    "a1": "19d0909dafbyj1rgamailt8t9s9gbqcvio3cyqpsn50000101968",
    "webId": "6d1ee706e57415efdc991b4922521984",
    "web_session": "040069b1de3bf4578efe8aecf53b4b20e6b4d2",
}

HEADERS = {
    "content-type": "application/json;charset=UTF-8",
    "origin": "https://www.xiaohongshu.com",
    "referer": "https://www.xiaohongshu.com/",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/134.0.0.0 Safari/537.36",
    "x-b3-traceid": "4d5b161112607ec8",
    "x-s-common": "2UQAPsHC+aIjqArjwjHjNsQhPsHCH0rjNsQhPaHCH0c1PUhUHjIj2eHjwjQgynEDJ74AHjIj2ePjwjQhyoPTqBPT49pjHjIj2ecjwjH9N0r1PjHVHdWMH0ijP/SDPeDIwnzY8fQEy0bU89bTGnSV4eYFwgPE89QlG78kJA+02gbIq9hMPeZIPerIP/D9wsHVHdW9H0ijHjIj2eqjwjHjNsQhwsHCHDDAwoQH8B4AyfRI8FS98g+Dpd4daLP3JFSb/BMsn0pSPM87nrldzSzQ2bPAGdb7zgQB8nph8emSy9E0cgk+zSS1qgzianYt8p+1/LzN4gzaa/+NqMS6qS4HLozoqfQnPbZEp98QyaRSp9P98pSl4oSzcgmca/P78nTTL08z/sVManD9q9z1J9p/8db8aob7JeQl4epsPrz6agW3Lr4ryaRApdz3agYDq7YM47HFqgzkanYMGLSbP9LA/bGIa/+nprSe+9LI4gzVPDbrJg+P4fprLFTALMm7+LSb4d+kpdzt/7b7wrQM498cqBzSpr8g/FSh+bzQygL9nSm7qSmM4epQ4flY/BQdqA+l4oYQ2BpAPp87arS34nMQyFSE8nkdqMD6pMzd8/4SL7bF8aRr+7+rG7mkqBpD8pSUzozQcA8Szb87PDSb/d+/qgzVJfl/4LExpdzQ4fRSy7bFP9+y+7+nJAzdaLp/2LSiz/Yz8dbMagYiJdbCwB4QyFSfJ7b7yFSenS4oJA+A8BlO8p8c4A+Q4DbSPB8d8ncIyFkQy/pAPFSUz0QM4rbQyLTAynz98nTy/fpLLocFJDbO8p4c4FpQ4SSPGFb98n8c4FpPwLkAL7p7nDDAzgQQ2rLM/op749bl4UTU8nTinDbw8/b+/fLILoqEaL+wqM8PJ9p/GDSBanT6qM+U+7+nJD8kanTdqM8n4rMQygpDqgb7t7zl4b4QPAmSPMm7aLSiJ9LA4gclanSOq9kM4e+74gz1qMm7nrSeG9lQPFSUP04VyAQQ+nLl4gzeaLp/NFSbadPILoz1qbSQcLuIafp88DclaLpULrRc4rT6qgqAa/+O8gYl4b4z/epSyn+mqA+Iyo4QyBRAPASOqA+M4o+wLozNanDA8n8n498Qy94A+0mgqDSea9pDJURSpM8FPFDA+9pnqg4fwrQ8qDSiLLSQyn4Sp7kOqMq6J7+fqFbS2op7wLSbpr8QcMkUNMm7cFS3qgmQyFESnnP3LB4AN7PILo4kanDh/URl4ebzpAFRHjIj2eDjwjFlPeZI+/G9+AZhNsQhP/Zjw0ZVHdWlPaHCHfE6qfMYJsHVHdWlPjHCH0r7+AcI+AqU+erhw/rvP/q7P0rhP/q9+AG9+sQR",
}


# ==================== 工具函数 ====================

def generate_search_id():
    """生成随机 search_id"""
    chars = string.ascii_lowercase + string.digits
    part1 = ''.join(random.choices(chars, k=20))
    part2 = ''.join(random.choices(chars, k=20))
    return f"{part1}@{part2}"


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


# ==================== 搜索函数 ====================

def search(keyword: str, page: int = 1, page_size: int = 20, search_id: str = None) -> dict:
    """搜索笔记"""
    if search_id is None:
        search_id = generate_search_id()

    data = {
        "keyword": keyword,
        "page": page,
        "page_size": page_size,
        "search_id": search_id,
        "sort": "general",
        "note_type": 0,
        "ext_flags": [],
        "filters": [
            {"tags": ["general"], "type": "sort_type"},
            {"tags": ["不限"], "type": "filter_note_type"},
            {"tags": ["一天内"], "type": "filter_note_time"},
            {"tags": ["不限"], "type": "filter_note_range"},
            {"tags": ["不限"], "type": "filter_pos_distance"}
        ],
        "geo": "",
        "image_formats": ["jpg", "webp", "avif"]
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


def search_all(keyword: str, max_pages: int = 10, delay: float = 1.0) -> list:
    """搜索所有页面，自动去重"""
    seen_ids = set()
    results = []
    search_id = generate_search_id()

    for page in range(1, max_pages + 1):
        logger.info(f"搜索 '{keyword}' - 第 {page} 页")

        try:
            data = search(keyword, page, search_id=search_id)
            items = data.get('data', {}).get('items', [])

            if not items:
                logger.info("没有更多数据")
                break

            for item in items:
                item_id = item.get('id')
                if item_id and item_id not in seen_ids:
                    seen_ids.add(item_id)
                    results.append(item)

            logger.info(f"当前页新增 {len(items)} 条，总计 {len(results)} 条")
            time.sleep(delay)

        except Exception as e:
            logger.error(f"第 {page} 页失败: {e}")
            break

    return results


# ==================== 主程序 ====================

if __name__ == "__main__":
    keyword = "鸣潮"
    results = search_all(keyword, max_pages=5)

    # 保存结果
    output_file = LOG_DIR / f"search_{keyword}_{int(time.time())}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    logger.info(f"搜索完成，共 {len(results)} 条，保存到 {output_file}")
