#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Step 4: 调用 /api/v3/get 接口获取 token

依赖前置步骤:
- step2_getconf.py 获取 dt, zoneId
- step3_up.py 获取 irToken

本地生成:
- fp_encoder.js 生成 fp 参数
- cb_encoder.js 生成 cb 参数
"""

import requests
import execjs
import time
import random
import string
import urllib.parse
import json
import re
from pathlib import Path

# 固定参数
CAPTCHA_ID = '74b1d03fcaf944b4aa3a862b2a1893e1'
REFERER = 'https://dun.163.com/trial/sense'
VERSION = '2.28.5'
LOAD_VERSION = '2.5.4'
BASE_DIR = Path(__file__).resolve().parent.parent
ENCODERS_DIR = BASE_DIR / 'encoders'

def load_js_module(filepath):
    """加载 JS 模块"""
    with open(ENCODERS_DIR / filepath, 'r', encoding='utf-8') as f:
        return execjs.compile(f.read())

def generate_fp(host='dun.163.com'):
    """生成 fp 参数"""
    fp_module = load_js_module('fp_encoder.js')
    return fp_module.call('generateFpParam', {'host': host})

def generate_cb():
    """生成 cb 参数"""
    cb_module = load_js_module('cb_encoder.js')
    return cb_module.call('generateCb')

def generate_jsonp_callback():
    """生成 JSONP 回调函数名"""
    chars = string.ascii_lowercase + string.digits
    random_str = ''.join(random.choice(chars) for _ in range(7))
    return f'__JSONP_{random_str}_0'

def parse_jsonp_response(response_text, callback_name):
    """解析 JSONP 响应"""
    # JSONP 格式: callback_name({...})
    pattern = rf'{re.escape(callback_name)}\((.*)\)'
    match = re.search(pattern, response_text, re.DOTALL)
    if match:
        json_str = match.group(1)
        return json.loads(json_str)
    return None

def step4_get(dt, zone_id, ir_token):
    """
    调用 /api/v3/get 接口

    Args:
        dt: 从 getconf 获取的 dt
        zone_id: 从 getconf 获取的 zoneId
        ir_token: 从 up 接口获取的 irToken

    Returns:
        dict: 包含 token 等信息的响应
    """
    # 生成 fp 和 cb
    print('生成 fp 参数...')
    fp = generate_fp()
    print(f'  fp: {fp[:50]}...')

    print('生成 cb 参数...')
    cb = generate_cb()
    print(f'  cb: {cb}')

    # 生成回调函数名
    callback = generate_jsonp_callback()

    # 构建请求参数
    params = {
        'referer': REFERER,
        'zoneId': zone_id,
        'dt': dt,
        'id': CAPTCHA_ID,
        'fp': fp,
        'https': 'true',
        'type': '',
        'width': '0',
        'sizeType': '10',
        'version': VERSION,
        'dpr': '1',
        'dev': '3',
        'cb': cb,
        'ipv6': 'false',
        'runEnv': '10',
        'group': '',
        'scene': '',
        'sdkVersion': '',
        'loadVersion': LOAD_VERSION,
        'iv': '4',
        'user': '',
        'irToken': ir_token,
        'smsVersion': 'v3',
        'callback': callback
    }

    # 请求 URL
    url = 'https://c.dun.163.com/api/v3/get'

    # 请求头 (与浏览器一致)
    headers = {
        'Accept': '*/*',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'Pragma': 'no-cache',
        'Referer': 'https://dun.163.com/',
        'Sec-Fetch-Dest': 'script',
        'Sec-Fetch-Mode': 'no-cors',
        'Sec-Fetch-Site': 'same-site',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36',
        'sec-ch-ua': '"Chromium";v="146", "Not-A.Brand";v="24", "Google Chrome";v="146"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"'
    }

    print(f'\n请求 /api/v3/get...')
    print(f'  URL: {url}')

    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        print(f'  状态码: {response.status_code}')
        print(f'  响应长度: {len(response.text)}')

        # 解析 JSONP 响应
        result = parse_jsonp_response(response.text, callback)

        if result:
            print(f'\n响应解析成功:')
            print(f'  error: {result.get("error", "N/A")}')
            print(f'  token: {result.get("data", {}).get("token", "N/A")}')
            print(f'  type: {result.get("data", {}).get("type", "N/A")}')
            print(f'  zoneId: {result.get("data", {}).get("zoneId", "N/A")}')

            if result.get('error') == 0:
                return result.get('data', {})
            else:
                print(f'  错误信息: {result.get("msg", "未知错误")}')
                return None
        else:
            print(f'  JSONP 解析失败')
            print(f'  原始响应: {response.text[:500]}...')
            return None

    except Exception as e:
        print(f'  请求失败: {e}')
        return None

def step2_getconf():
    """Step 2: 获取 dt 和 zoneId"""
    print('\n[Step 2] 请求 /api/v2/getconf...')

    callback = generate_jsonp_callback()
    url = 'https://c.dun.163.com/api/v2/getconf'
    params = {
        'id': CAPTCHA_ID,
        'referer': REFERER,
        'zoneId': '',
        'ipv6': 'false',
        'runEnv': '10',
        'iv': '5',
        'loadVersion': LOAD_VERSION,
        'callback': callback
    }

    headers = {
        'Accept': '*/*',
        'Referer': REFERER,
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    response = requests.get(url, params=params, headers=headers, timeout=10)
    result = parse_jsonp_response(response.text, callback)

    if result and result.get('error') == 0:
        data = result.get('data', {})
        dt = data.get('dt', '')
        zone_id = data.get('zoneId', 'CN31')
        ir_pn = data.get('ir', {}).get('pn', '')
        print(f'  dt: {dt}')
        print(f'  zoneId: {zone_id}')
        print(f'  ir.pn: {ir_pn}')
        return dt, zone_id, ir_pn
    else:
        print(f'  获取配置失败: {result}')
        return None, None, None


def step3_up(ir_pn):
    """Step 3: 上传设备指纹，获取 irToken"""
    print('\n[Step 3] 请求 /v4/j/up...')

    # 加载 env.js 生成 d 和 n
    env_module = load_js_module('env.js')
    env_result = env_module.call('main')  # 调用 main 函数
    d = env_result.get('d', '')
    n = env_result.get('n', '')

    print(f'  d: {d[:50]}...')
    print(f'  n: {n}')

    url = 'https://ir-sdk.dun.163.com/v4/j/up'

    # 注意：必须用 JSON 格式发送，不能用 form 表单
    payload = {
        'p': ir_pn or 'YD00192283058223',
        'v': '2.0.13_yanzhengma',
        'vk': 'd44593ca',
        'n': n,
        'd': d
    }

    headers = {
        'Accept': '*/*',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Content-Type': 'text/plain',  # 重要：使用 text/plain
        'Origin': 'https://dun.163.com',
        'Referer': 'https://dun.163.com/',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36',
        'sec-ch-ua': '"Chromium";v="146", "Not-A.Brand";v="24", "Google Chrome";v="146"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"'
    }

    # 用 JSON 字符串发送
    response = requests.post(url, headers=headers, data=json.dumps(payload, separators=(',', ':')), timeout=10)
    result = response.json()

    if result.get('code') == 200:
        ir_token = result.get('data', {}).get('tk', '')
        print(f'  irToken: {ir_token}')
        return ir_token
    else:
        print(f'  获取 irToken 失败: {result}')
        return None


def main():
    """完整流程测试"""
    print('=' * 60)
    print('网易盾无感验证码 - 完整流程测试')
    print('=' * 60)

    # Step 2: 获取配置
    dt, zone_id, ir_pn = step2_getconf()
    if not dt:
        print('Step 2 失败，退出')
        return

    # Step 3: 上传指纹，获取 irToken
    ir_token = step3_up(ir_pn)
    if not ir_token:
        print('Step 3 失败，退出')
        return

    # Step 4: 获取 token
    print('\n[Step 4] 请求 /api/v3/get...')
    result = step4_get(dt, zone_id, ir_token)

    if result:
        print('\n' + '=' * 60)
        print('成功获取 token!')
        print('=' * 60)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return result
    else:
        print('\n' + '=' * 60)
        print('获取 token 失败')
        print('=' * 60)
        return None

if __name__ == '__main__':
    main()
