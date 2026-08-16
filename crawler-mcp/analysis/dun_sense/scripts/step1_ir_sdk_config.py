"""
第一步：请求 ir-sdk 配置接口
GET https://ir-sdk.dun.163.com/v4/j/c

参数：
  p  : 产品ID，固定 YD00615509752509
  v  : SDK版本，固定 1.0.1
  vk : 固定 d44593ca
  n  : 随机MD5（32位hex）
"""

import uuid
import hashlib
import requests


def get_ir_sdk_config():
    # n 是随机 MD5，用 uuid 生成随机字符串再 md5
    n = hashlib.md5(uuid.uuid4().bytes).hexdigest()

    url = "https://ir-sdk.dun.163.com/v4/j/c"
    params = {
        "p": "YD00615509752509",
        "v": "1.0.1",
        "vk": "d44593ca",
        "n": n,
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
        "Referer": "https://dun.163.com/",
        "content-type": "application/x-www-form-urlencoded",
    }

    resp = requests.get(url, params=params, headers=headers)
    resp.raise_for_status()
    data = resp.json()
    print(f"状态码: {resp.status_code}")
    print(f"响应: {data}")
    return data


if __name__ == "__main__":
    result = get_ir_sdk_config()
