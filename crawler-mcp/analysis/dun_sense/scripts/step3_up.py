import requests
import json
import execjs
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
ENCODERS_DIR = BASE_DIR / "encoders"

js = execjs.compile((ENCODERS_DIR / "env.js").read_text(encoding="utf-8"))
result = js.call("main")

headers = {
    "Accept": "*/*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "Origin": "https://dun.163.com",
    "Pragma": "no-cache",
    "Referer": "https://dun.163.com/",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
    "content-type": "text/plain",
    "sec-ch-ua": "\"Chromium\";v=\"146\", \"Not-A.Brand\";v=\"24\", \"Google Chrome\";v=\"146\"",
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": "\"Windows\""
}
url = "https://ir-sdk.dun.163.com/v4/j/up"
data = {
    "p": "YD00192283058223",
    "v": "2.0.13_yanzhengma",
    "vk": "d44593ca",
    "n": result['n'],
    "d": result['d']
}
data = json.dumps(data, separators=(',', ':'))
response = requests.post(url, headers=headers, data=data)

print(response.text)
print(response)
