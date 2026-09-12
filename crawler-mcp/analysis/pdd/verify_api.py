
import os
import subprocess
from pathlib import Path

import requests


BASE_DIR = Path(__file__).resolve().parent
ANTI_JS = BASE_DIR / "pdd_anti_content_pure_node.js"


headers = {
    "Accept": "application/json, text/javascript",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Connection": "keep-alive",
    "Origin": "https://www.pinduoduo.com",
    "Referer": "https://www.pinduoduo.com/",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36",
    "sec-ch-ua": "\"Not;A=Brand\";v=\"8\", \"Chromium\";v=\"150\", \"Google Chrome\";v=\"150\"",
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": "\"Windows\""
}
cookies = {}


def cookie_header(cookies_dict):
    return "; ".join(f"{key}={value}" for key, value in cookies_dict.items())


def make_anti_content():
    node_binary = os.getenv("CRAWLER_NODE", "node")
    cmd = [
        node_binary,
        str(ANTI_JS),
        "--page-url",
        "https://www.pinduoduo.com/home/girlclothes/",
        "--user-agent",
        headers["User-Agent"],
    ]
    cookie = cookie_header(cookies)
    if cookie:
        cmd.extend(["--cookie", cookie])
    completed = subprocess.run(
        cmd,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )
    return completed.stdout.strip()


def main():
    url = "https://apiv2.pinduoduo.com/api/gindex/tf/query_tf_goods_info"
    params = {
        "tf_id": "TFRQ0v00000Y_13396",
        "page": "1",
        "size": "39",
        "anti_content": make_anti_content(),
    }
    session = requests.Session()
    session.trust_env = False
    response = session.get(url, headers=headers, cookies=cookies, params=params, timeout=20)
    response.raise_for_status()
    print(response.text)
    print(response)


if __name__ == "__main__":
    main()
