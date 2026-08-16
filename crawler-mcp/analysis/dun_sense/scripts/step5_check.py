#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Step 5: 完整验证流程 - 包含 /api/v3/check 接口

整合所有步骤:
- Step 2: getconf 获取 dt, zoneId
- Step 3: up 获取 irToken
- Step 4: get 获取 token
- Step 5: check 提交验证
"""

import requests
import execjs
import time
import random
import string
import json
import re
from pathlib import Path

# ============ 固定参数 ============

CAPTCHA_ID = '74b1d03fcaf944b4aa3a862b2a1893e1'
REFERER = 'https://dun.163.com/trial/sense'
VERSION = '2.28.5'
LOAD_VERSION = '2.5.4'
BASE_DIR = Path(__file__).resolve().parent.parent
ENCODERS_DIR = BASE_DIR / 'encoders'

# ============ 工具函数 ============

def load_js_module(filepath):
    """加载 JS 模块"""
    with open(ENCODERS_DIR / filepath, 'r', encoding='utf-8') as f:
        return execjs.compile(f.read())

def generate_jsonp_callback():
    """生成 JSONP 回调函数名"""
    chars = string.ascii_lowercase + string.digits
    random_str = ''.join(random.choice(chars) for _ in range(7))
    return f'__JSONP_{random_str}_0'

def parse_jsonp_response(response_text, callback_name):
    """解析 JSONP 响应"""
    pattern = rf'{re.escape(callback_name)}\((.*)\)'
    match = re.search(pattern, response_text, re.DOTALL)
    if match:
        json_str = match.group(1)
        return json.loads(json_str)
    return None

def get_headers():
    """获取请求头"""
    return {
        'Accept': '*/*',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'Pragma': 'no-cache',
        'Referer': 'https://dun.163.com/',
        'Sec-Fetch-Dest': 'script',
        'Sec-Fetch-Mode': 'no-cors',
        'Sec-Fetch-Site': 'same-site',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36',
        'sec-ch-ua': '"Google Chrome";v="147", "Not.A/Brand";v="8", "Chromium";v="147"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"'
    }

# ============ JS 模块加载 ============

print('加载 JS 模块...')
fp_module = load_js_module('fp_encoder.js')
cb_module = load_js_module('cb_encoder.js')
env_module = load_js_module('env.js')
data_module = load_js_module('data_encoder.js')
print('JS 模块加载完成')

def generate_fp(host='dun.163.com'):
    """生成 fp 参数"""
    return fp_module.call('generateFpParam', {'host': host})

def generate_cb():
    """生成 cb 参数"""
    return cb_module.call('generateCb')

def generate_data(token, trace_data, click_info):
    """生成 data 参数"""
    return data_module.call('generateData', token, trace_data, click_info)

def generate_mock_trace():
    """生成模拟轨迹"""
    return data_module.call('generateMockTrace', 100, 50, 189, 16, 500)

# ============ 各步骤实现 ============

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

    response = requests.get(url, params=params, headers=get_headers(), timeout=10)
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

    env_result = env_module.call('main')
    d = env_result.get('d', '')
    n = env_result.get('n', '')

    print(f'  d: {d[:50]}...')
    print(f'  n: {n}')

    url = 'https://ir-sdk.dun.163.com/v4/j/up'
    payload = {
        'p': ir_pn or 'YD00192283058223',
        'v': '2.0.13_yanzhengma',
        'vk': 'd44593ca',
        'n': n,
        'd': d
    }

    headers = {
        'Accept': '*/*',
        'Content-Type': 'text/plain',
        'Origin': 'https://dun.163.com',
        'Referer': 'https://dun.163.com/',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    response = requests.post(url, headers=headers, data=json.dumps(payload, separators=(',', ':')), timeout=10)
    result = response.json()

    if result.get('code') == 200:
        ir_token = result.get('data', {}).get('tk', '')
        print(f'  irToken: {ir_token}')
        return ir_token
    else:
        print(f'  获取 irToken 失败: {result}')
        return None


def step4_get(dt, zone_id, ir_token):
    """Step 4: 获取 token"""
    print('\n[Step 4] 请求 /api/v3/get...')

    fp = generate_fp()
    cb = generate_cb()
    callback = generate_jsonp_callback()

    print(f'  fp: {fp[:50]}...')
    print(f'  cb: {cb}')

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

    url = 'https://c.dun.163.com/api/v3/get'
    response = requests.get(url, params=params, headers=get_headers(), timeout=10)
    result = parse_jsonp_response(response.text, callback)

    if result and result.get('error') == 0:
        data = result.get('data', {})
        token = data.get('token', '')
        print(f'  token: {token}')
        print(f'  type: {data.get("type", "N/A")}')
        return data
    else:
        print(f'  获取 token 失败: {result}')
        return None


def step5_check(dt, zone_id, token):
    """Step 5: 提交验证"""
    print('\n[Step 5] 请求 /api/v3/check...')

    # 生成 cb 参数
    cb = generate_cb()
    print(f'  cb: {cb}')

    # 生成模拟轨迹
    trace_data = generate_mock_trace()
    print(f'  轨迹点数: {len(trace_data)}')

    # 模拟点击信息
    click_info = {
        'x': 189,  # 相对点击位置
        'y': 16,
        'timeDelta': 300 + random.randint(50, 200),  # 随机延迟
        'isTrusted': True
    }
    print(f'  点击位置: ({click_info["x"]}, {click_info["y"]})')
    print(f'  时间差: {click_info["timeDelta"]}ms')

    # 生成 data 参数
    data_obj = generate_data(token, trace_data, click_info)
    data_json = json.dumps(data_obj, separators=(',', ':'))
    print(f'  data.d: {data_obj["d"] or "(空)"}')
    print(f'  data.m: {data_obj["m"][:40]}...')
    print(f'  data.p: {data_obj["p"][:40]}...')
    print(f'  data.ext: {data_obj["ext"][:40]}...')

    # 生成回调函数名
    callback = generate_jsonp_callback()

    # 构建请求参数
    params = {
        'referer': REFERER,
        'zoneId': zone_id,
        'dt': dt,
        'id': CAPTCHA_ID,
        'version': VERSION,
        'cb': cb,
        'user': '',
        'extraData': '',
        'bf': '0',
        'runEnv': '10',
        'sdkVersion': 'undefined',
        'loadVersion': LOAD_VERSION,
        'iv': '4',
        'token': token,
        'type': '5',  # 无感验证类型
        'width': '320',
        'data': data_json,
        'callback': callback
    }

    url = 'https://c.dun.163.com/api/v3/check'

    print(f'\n发送 check 请求...')
    response = requests.get(url, params=params, headers=get_headers(), timeout=10)
    result = parse_jsonp_response(response.text, callback)

    if result:
        print(f'\n响应:')
        print(f'  error: {result.get("error", "N/A")}')
        print(f'  msg: {result.get("msg", "N/A")}')

        data = result.get('data', {})
        if data:
            print(f'  result: {data.get("result", "N/A")}')
            print(f'  token: {data.get("token", "N/A")}')
            print(f'  validate: {data.get("validate", "N/A")[:50]}...' if data.get('validate') else '  validate: (空)')

        if result.get('error') == 0 and data.get('result') == True:
            return data
        else:
            print(f'\n验证失败!')
            return None
    else:
        print(f'  JSONP 解析失败')
        print(f'  原始响应: {response.text[:500]}...')
        return None


# ============ 主流程 ============

def main():
    """完整验证流程"""
    print('=' * 60)
    print('网易盾无感验证码 - 完整流程测试 (Step 2-5)')
    print('=' * 60)

    start_time = time.time()

    # Step 2: 获取配置
    dt, zone_id, ir_pn = step2_getconf()
    if not dt:
        print('\n❌ Step 2 失败')
        return None

    # Step 3: 上传指纹，获取 irToken
    ir_token = step3_up(ir_pn)
    if not ir_token:
        print('\n❌ Step 3 失败')
        return None

    # Step 4: 获取 token
    get_result = step4_get(dt, zone_id, ir_token)
    if not get_result:
        print('\n❌ Step 4 失败')
        return None

    token = get_result.get('token', '')

    # Step 5: 提交验证
    check_result = step5_check(dt, zone_id, token)

    elapsed = time.time() - start_time

    print('\n' + '=' * 60)
    if check_result and check_result.get('result') == True:
        print('[SUCCESS] 验证成功!')
        print(f'  耗时: {elapsed:.2f}s')
        print(f'  token: {check_result.get("token", "")}')
        print(f'  validate: {check_result.get("validate", "")[:80]}...')
    else:
        print('[FAILED] 验证失败')
        print(f'  耗时: {elapsed:.2f}s')
    print('=' * 60)

    return check_result


if __name__ == '__main__':
    result = main()

    if result:
        print('\n完整响应:')
        print(json.dumps(result, indent=2, ensure_ascii=False))
