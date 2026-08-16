"""
第二步：请求 getconf 接口，获取 dt、zoneId 等配置
GET https://c.dun.163.com/api/v2/getconf (JSONP)

参数全部写死，callback 随机生成即可
响应返回：dt、zoneId、ir.pn、apiServer、resources 等
"""

import re
import json
import random
import string
import requests


def random_callback(suffix: int = 0) -> str:
    """生成随机 JSONP 回调名，格式：__JSONP_xxxxxxx_0"""
    rand = ''.join(random.choices(string.ascii_lowercase + string.digits, k=7))
    return f"__JSONP_{rand}_{suffix}"


def get_conf(referer: str, dt: str = "", zone_id: str = "") -> dict:
    callback = random_callback(0)
    params = {
        "referer": referer,
        "zoneId": zone_id,
        "id": "74b1d03fcaf944b4aa3a862b2a1893e1",
        "ipv6": "false",
        "runEnv": "10",
        "iv": "5",
        "loadVersion": "2.5.4",
        "callback": callback,
    }
    # 非首次请求才带 dt
    if dt:
        params["dt"] = dt

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
        "Referer": "https://dun.163.com/",
    }

    resp = requests.get(
        "https://c.dun.163.com/api/v2/getconf",
        params=params,
        headers=headers,
    )
    resp.raise_for_status()

    # JSONP 解析：__JSONP_xxx_0({...})
    body = resp.text
    match = re.search(r'\((\{.*\})\)', body, re.DOTALL)
    if not match:
        raise ValueError(f"JSONP 解析失败: {body[:200]}")

    data = json.loads(match.group(1))
    if data.get("error") != 0:
        raise ValueError(f"getconf 返回错误: {data}")

    result = {
        "dt": data["data"]["dt"],
        "zoneId": data["data"]["zoneId"],
        "ir_pn": data["data"]["ir"]["pn"],          # ir-sdk 产品ID，用于 v4/j/up
        "ir_token": data["data"]["ir"]["token"],     # ir-sdk token
        "apiServer": data["data"]["apiServer"][0],
    }
    print(f"dt:      {result['dt']}")
    print(f"zoneId:  {result['zoneId']}")
    print(f"ir_pn:   {result['ir_pn']}")
    return result


if __name__ == "__main__":
    result = get_conf(referer="https://dun.163.com/trial/sense")
    print(f"\n完整结果: {result}")
