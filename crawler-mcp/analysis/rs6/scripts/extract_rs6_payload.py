import json
import re
import subprocess
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin

import requests


class PayloadParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.meta_content = None
        self.script_code = []
        self.external_scripts = []
        self._capture_script = False
        self._captured_first_script = False

    def handle_starttag(self, tag, attrs):
        attr_map = dict(attrs)
        if tag == "meta" and attr_map.get("id") == "K5MK4FPPNWrv":
            self.meta_content = attr_map.get("content")
        elif tag == "script":
            src = attr_map.get("src")
            if src:
                self.external_scripts.append(
                    {
                        "src": src,
                        "type": attr_map.get("type", ""),
                        "r": attr_map.get("r", ""),
                    }
                )
            if (
                not self._captured_first_script
                and attr_map.get("type") == "text/javascript"
                and attr_map.get("r") == "m"
            ):
                self._capture_script = True

    def handle_endtag(self, tag):
        if tag == "script" and self._capture_script:
            self._capture_script = False
            self._captured_first_script = True

    def handle_data(self, data):
        if self._capture_script:
            self.script_code.append(data)


def build_first_request_headers(url):
    return {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Cache-Control": "max-age=0",
        "Connection": "keep-alive",
        "Referer": url,
        "Upgrade-Insecure-Requests": "1",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
    }


def build_second_request_headers(url):
    return {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Connection": "keep-alive",
        "Referer": url,
        "Upgrade-Insecure-Requests": "1",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
    }


def fetch_first_request(session):
    url = "http://epub.cnipa.gov.cn/"
    headers = build_first_request_headers(url)
    response = session.get(
        url,
        headers=headers,
        verify=False,
        timeout=15,
    )
    response.raise_for_status()
    return url, headers, response


def fetch_external_script(session, base_url, headers, script_src):
    script_url = urljoin(base_url, script_src)
    response = session.get(
        script_url,
        headers=headers,
        verify=False,
        timeout=15,
    )
    response.raise_for_status()
    return script_url, response.text


def update_env_content(env_js_path, meta_content):
    env_text = env_js_path.read_text(encoding="utf-8")
    content_line = f'content = "{meta_content or ""}";'
    if re.search(r"^\s*content\s*=\s*.*?;?\s*$", env_text, flags=re.MULTILINE):
        updated = re.sub(
            r"^\s*content\s*=\s*.*?;?\s*$",
            content_line,
            env_text,
            count=1,
            flags=re.MULTILINE,
        )
    else:
        updated = f"{content_line}\n\n{env_text}"
    env_js_path.write_text(updated, encoding="utf-8")


def run_request_main(base_dir):
    process = subprocess.run(
        ["node", "request_main.js"],
        cwd=base_dir,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=15,
    )
    if process.returncode != 0:
        raise RuntimeError(
            "request_main.js 执行失败\n"
            f"stdout:\n{process.stdout}\n"
            f"stderr:\n{process.stderr}"
        )
    lines = [line.strip() for line in process.stdout.splitlines() if line.strip()]
    if not lines:
        raise RuntimeError("request_main.js 未输出 cookie")
    return lines[-1]


def extract_cookie_pair(cookie_line):
    cookie_pair = cookie_line.split(";", 1)[0].strip()
    if "=" not in cookie_pair:
        raise RuntimeError(f"无法解析 js_cookie: {cookie_line}")
    return cookie_pair


def apply_js_cookie(session, cookie_pair):
    name, value = cookie_pair.split("=", 1)
    session.cookies.set(
        name,
        value,
        domain="epub.cnipa.gov.cn",
        path="/",
    )
    return {"name": name, "value": value, "cookie_pair": cookie_pair}


def fetch_second_request(session, url, headers):
    response = session.get(
        url,
        headers=headers,
        verify=False,
        timeout=15,
    )
    return response


def extract_payload(html):
    parser = PayloadParser()
    parser.feed(html)
    return {
        "meta_content": parser.meta_content,
        "script_code": "".join(parser.script_code).strip(),
        "external_scripts": parser.external_scripts,
    }


def main():
    session = requests.Session()
    base_url, first_headers, response = fetch_first_request(session)
    result = extract_payload(response.text)
    base_dir = Path(__file__).resolve().parent
    env_js_path = base_dir / "env.js"
    encrypt_js_code_path = base_dir / "encrypt_js_code.js"
    cookies_json_path = base_dir / "server_cookies.json"
    decode_external_js_path = base_dir / "decode_external.js"

    update_env_content(env_js_path, result["meta_content"])
    encrypt_js_code_path.write_text(
        result["script_code"] or "",
        encoding="utf-8",
    )
    cookies_json_path.write_text(
        json.dumps(
            requests.utils.dict_from_cookiejar(response.cookies),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    decode_script_url = None
    if result["external_scripts"]:
        decode_script_url, decode_script_code = fetch_external_script(
            session,
            base_url,
            first_headers,
            result["external_scripts"][0]["src"],
        )
        decode_external_js_path.write_text(
            decode_script_code,
            encoding="utf-8",
        )

    js_cookie_raw = run_request_main(base_dir)
    js_cookie = extract_cookie_pair(js_cookie_raw)
    applied_js_cookie = apply_js_cookie(session, js_cookie)
    second_headers = build_second_request_headers(base_url)
    second_response = fetch_second_request(session, base_url, second_headers)

    output = {
        "meta_content": result["meta_content"],
        "script_code": result["script_code"],
        "decode_script_url": decode_script_url,
        "js_cookie": js_cookie,
        "js_cookie_raw": js_cookie_raw,
        "applied_js_cookie": applied_js_cookie,
        "first_request": {
            "url": response.url,
            "status_code": response.status_code,
            "cookies": requests.utils.dict_from_cookiejar(response.cookies),
            "headers": first_headers,
        },
        "second_request": {
            "url": second_response.url,
            "status_code": second_response.status_code,
            "cookies": requests.utils.dict_from_cookiejar(session.cookies),
            "headers": second_headers,
            "request_cookie_header": second_response.request.headers.get("Cookie", ""),
            "response_preview": second_response.text[:200],
        },
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    print("\nserver_cookies:")
    print(
        json.dumps(
            requests.utils.dict_from_cookiejar(response.cookies),
            ensure_ascii=False,
            indent=2,
        )
    )
    print("\njs_cookie:")
    print(js_cookie)
    print(f"\nwritten: {env_js_path}")
    print(f"written: {encrypt_js_code_path}")
    print(f"written: {cookies_json_path}")
    if decode_script_url:
        print(f"written: {decode_external_js_path}")


if __name__ == "__main__":
    main()
